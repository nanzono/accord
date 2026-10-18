"""語彙の操作（語彙に語を足す・語彙から語を消す）のテスト。

語彙は経歴データの置き場の vocabulary.md に、種類ごとの節に語を 1 行ずつ書く。足す操作は種類の節の末尾に
1 行足し、消す操作はその語の行を消す。正本の節が使っている語は消さない。
同梱の見本の一時的な写しの上で走らせ、本物のデータの置き場には触れない。
"""

from __future__ import annotations

from datetime import date

import pytest

from accord.models.results import PositioningDraft
from accord.services.positioning import PositioningService
from accord.services.recording import (
    TERM_FORMAT,
    TERM_IN_USE,
    TERM_MISSING,
    VOCABULARY_KIND,
    VocabularyService,
)
from accord.vocabulary.settings import VOCABULARY_KINDS, load_settings, parse_vocabulary
from conftest import git, sample_settings, source_digest

REASON = "テストで語彙を変える"
KINDS = [kind for kind, _ in VOCABULARY_KINDS]


def _words(settings, kind: str) -> list[str]:
    return parse_vocabulary(settings.vocabulary_path.read_text(encoding="utf-8"))[kind]


def _commit_count(directory) -> int:
    return int(git(directory, "rev-list", "--count", "HEAD").strip())


# ---------------------------------------------------------------- 足す


def test_REQ_508_adding_a_term_appends_a_line_to_the_end_of_the_kind(settings) -> None:
    """語を足すと、その種類の節の末尾に 1 行足し、ほかの節と行は変えず、1 件のコミットにする。"""
    data = settings.source_dir
    before_text = settings.vocabulary_path.read_text(encoding="utf-8")
    before = _words(settings, "公開記録の種類")
    commits = _commit_count(data)

    result = VocabularyService(settings).add_term("公開記録の種類", "見本の配信", REASON)

    assert result.accepted is True, result.rejection
    assert _words(settings, "公開記録の種類") == [*before, "見本の配信"]
    after_text = settings.vocabulary_path.read_text(encoding="utf-8")
    assert after_text.replace("- 見本の配信\n", "", 1) == before_text
    assert result.recorded["語の一覧"] == [*before, "見本の配信"]
    assert result.recorded["種類"] == "公開記録の種類"
    assert result.recorded["語"] == "見本の配信"
    assert result.recorded["理由"] == REASON
    assert _commit_count(data) == commits + 1
    assert "Accord-Operation: add_term" in git(data, "log", "-1", "--format=%B")
    assert any("git にコミットした" in note for note in result.warnings)


def test_REQ_508_adding_a_term_to_an_empty_kind(settings) -> None:
    """語が 0 件の種類の節にも足せ、足した後の語彙を読み直すと、その語が読める。"""
    result = VocabularyService(settings).add_term("決めの適用先", "見本のホームページ", REASON)

    assert result.accepted is True, result.rejection
    reloaded = load_settings(settings.source_dir, settings.presentations_dir)
    assert reloaded.positioning_targets == ["見本のホームページ"]
    assert settings.positioning_targets == ["見本のホームページ"]
    assert _words(settings, "機能の分類") == _words(reloaded, "機能の分類")


def test_REQ_508_an_added_term_is_usable_right_away(settings) -> None:
    """足した語は、同じ設定のまま次の書き込みで使える（語を直す順の 1 つ目）。"""
    VocabularyService(settings).add_term("媒体", "見本の新しい媒体", REASON)

    result = PositioningService(settings).record(
        PositioningDraft(
            decided_on=date(2026, 9, 20),
            scope="見本の新しい媒体",
            headline_package="requirements-and-progress",
            rationale="足した語を適用範囲に使えることを見るための決め。",
        )
    )

    assert result.accepted is True, result.rejection


def test_REQ_509_a_duplicate_term_is_refused_with_the_current_terms(settings) -> None:
    """その種類に既にある語は、書かずに、いまの語の一覧を返して断る。"""
    before = source_digest(settings.source_dir)
    words = _words(settings, "パッケージの仮説の状態")

    result = VocabularyService(settings).add_term("パッケージの仮説の状態", words[0], REASON)

    assert result.accepted is False
    assert result.rejection.constraint == TERM_FORMAT
    assert result.rejection.next_action.candidates == words
    assert source_digest(settings.source_dir) == before


def test_REQ_509_an_empty_or_multiline_term_is_refused(settings) -> None:
    """空の語と改行を含む語は、書かずに、いまの語の一覧を返して断る。"""
    before = source_digest(settings.source_dir)
    service = VocabularyService(settings)

    for term in ("", "   ", "1 行目\n2 行目"):
        result = service.add_term("機能の分類", term, REASON)
        assert result.accepted is False, term
        assert result.rejection.constraint == TERM_FORMAT
        assert result.rejection.next_action.candidates == _words(settings, "機能の分類")
    assert source_digest(settings.source_dir) == before


@pytest.mark.parametrize(
    ("term", "named"),
    [
        ("../x", "パスの区切り"),
        ("a/b", "パスの区切り"),
        ("a\\b", "パスの区切り"),
        (".hidden", "「.」で始まる"),
        (".", "「.」"),
        ("..", "「..」"),
        ("a\tb", "制御文字"),
        ("a\x00b", "制御文字"),
    ],
)
def test_REQ_559_a_channel_term_that_could_leave_the_presentations_is_refused(settings, term, named) -> None:
    """媒体に足す語が、パスの区切りか制御文字を含むか、. か .. か、. で始まるなら、書かずに媒体の語の一覧を返す。"""
    before = (source_digest(settings.source_dir), source_digest(settings.presentations_dir))
    commits = _commit_count(settings.source_dir)
    words = _words(settings, "媒体")

    result = VocabularyService(settings).add_term("媒体", term, REASON)

    assert result.accepted is False, term
    assert result.rejection.constraint == TERM_FORMAT
    assert named in result.rejection.reason
    assert result.rejection.next_action.candidates == words
    assert result.rejection.next_action.operation == "add_term"
    assert (source_digest(settings.source_dir), source_digest(settings.presentations_dir)) == before
    assert _commit_count(settings.source_dir) == commits


def test_REQ_559_other_kinds_still_take_a_slash(settings) -> None:
    """媒体のほかの種類の語には文字の制限を掛けず、パスの区切りを含む語も今までどおり足せる。"""
    result = VocabularyService(settings).add_term("機能の分類", "a/b", REASON)

    assert result.accepted is True, result.rejection
    assert _words(settings, "機能の分類")[-1] == "a/b"


def test_REQ_559_a_plain_channel_name_is_still_added(settings) -> None:
    """経路の文字を持たない媒体の語は、今までどおり足せる（途中の . も足せる）。"""
    result = VocabularyService(settings).add_term("媒体", "sample.channel", REASON)

    assert result.accepted is True, result.rejection
    assert _words(settings, "媒体")[-1] == "sample.channel"


# ---------------------------------------------------------------- 消す


def test_REQ_510_removing_a_term_removes_its_line(settings) -> None:
    """使われていない語を消すと、その種類の節からその語の行を消し、1 件のコミットにする。"""
    data = settings.source_dir
    words = _words(settings, "パッケージの仮説の状態")
    assert "仮説のみ" in words
    commits = _commit_count(data)

    result = VocabularyService(settings).remove_term("パッケージの仮説の状態", "仮説のみ", REASON)

    assert result.accepted is True, result.rejection
    assert _words(settings, "パッケージの仮説の状態") == [word for word in words if word != "仮説のみ"]
    assert "仮説のみ" not in settings.package_hypothesis_states
    assert result.recorded["語の一覧"] == [word for word in words if word != "仮説のみ"]
    assert _commit_count(data) == commits + 1
    assert "Accord-Operation: remove_term" in git(data, "log", "-1", "--format=%B")


def test_REQ_510_adding_then_removing_restores_the_file(settings) -> None:
    """足した語をそのまま消すと、語彙のファイルは足す前と 1 バイトも違わない。"""
    before = settings.vocabulary_path.read_text(encoding="utf-8")
    service = VocabularyService(settings)

    assert service.add_term("決めの適用先", "見本の行き先", REASON).accepted is True
    assert service.remove_term("決めの適用先", "見本の行き先", REASON).accepted is True

    assert settings.vocabulary_path.read_text(encoding="utf-8") == before


def test_REQ_511_a_term_used_by_a_package_is_not_removed(settings) -> None:
    """パッケージ定義の仮説の状態が使っている語は、書かずに、使っている節の道筋と節を直す操作を返して断る。"""
    before = source_digest(settings.source_dir)

    result = VocabularyService(settings).remove_term("パッケージの仮説の状態", "検証中", REASON)

    assert result.accepted is False
    assert result.rejection.constraint == TERM_IN_USE
    assert result.rejection.next_action.operation == "revise_section"
    assert any(path.endswith("要件定義と進行管理") for path in result.rejection.next_action.candidates)
    assert source_digest(settings.source_dir) == before


def test_REQ_511_terms_used_by_records_categories_and_positionings_are_not_removed(settings) -> None:
    """公開記録の種類と役割、機能の分類の節の見出し、売り方の決めの適用範囲が使っている語も消さない。"""
    PositioningService(settings).record(
        PositioningDraft(
            decided_on=date(2026, 9, 20),
            scope="nagiho",
            headline_package="requirements-and-progress",
            rationale="媒体の語を適用範囲に使うための決め。",
        )
    )
    service = VocabularyService(settings)

    cases = {
        ("公開記録の種類", "登壇"): "刊行計画の進め方を話した勉強会の発表",
        ("公開記録の役割", "著者"): "分かれた数字を 1 か所に集める手順の寄稿",
        ("機能の分類", "データの置き場をつくる"): "データの置き場をつくる",
        ("媒体", "nagiho"): "2026-09-20",
    }
    for (kind, term), heading in cases.items():
        result = service.remove_term(kind, term, REASON)
        assert result.accepted is False, (kind, term)
        assert result.rejection.constraint == TERM_IN_USE
        assert any(heading in path for path in result.rejection.next_action.candidates), (
            kind,
            result.rejection.next_action.candidates,
        )


def test_REQ_511_after_fixing_the_section_the_old_term_can_be_removed(settings) -> None:
    """語を直す順（足す・使っている節を直す・消す）で、古い語を消せる。"""
    from accord.services.sections import SectionService

    vocabulary = VocabularyService(settings)
    sections = SectionService(settings)
    assert vocabulary.add_term("公開記録の役割", "見本の話し手", REASON).accepted is True
    refused = vocabulary.remove_term("公開記録の役割", "登壇者", REASON)
    assert refused.accepted is False
    [path] = refused.rejection.next_action.candidates
    read = sections.read_section(path)
    body = read.body.replace("- 役割: 登壇者", "- 役割: 見本の話し手")
    assert sections.revise_section(read.heading_path, body, read.fingerprint, REASON).accepted is True

    result = vocabulary.remove_term("公開記録の役割", "登壇者", REASON)

    assert result.accepted is True, result.rejection


def test_REQ_542_removing_a_missing_term_is_refused_with_the_current_terms(settings) -> None:
    """その種類に無い語を消そうとすると、書かずに、いまの語の一覧を返して断る。"""
    before = source_digest(settings.source_dir)

    result = VocabularyService(settings).remove_term("媒体", "無い媒体", REASON)

    assert result.accepted is False
    assert result.rejection.constraint == TERM_MISSING
    assert result.rejection.next_action.candidates == _words(settings, "媒体")
    assert source_digest(settings.source_dir) == before


# ---------------------------------------------------------------- 種類と理由


def test_REQ_512_an_unknown_kind_is_refused_with_the_six_kinds(settings) -> None:
    """6 つのどれでもない種類は、足すときも消すときも、書かずに、6 つの種類の名前を返して断る。"""
    before = source_digest(settings.source_dir)
    service = VocabularyService(settings)

    for result in (
        service.add_term("無い種類", "語", REASON),
        service.remove_term("無い種類", "語", REASON),
    ):
        assert result.accepted is False
        assert result.rejection.constraint == VOCABULARY_KIND
        assert result.rejection.next_action.candidates == KINDS
    assert source_digest(settings.source_dir) == before


def test_REQ_508_an_empty_reason_is_refused(settings) -> None:
    """理由が空なら、書かずに、欠けた欄の名前を返して断る。"""
    before = source_digest(settings.source_dir)

    result = VocabularyService(settings).add_term("媒体", "見本の媒体", " ")

    assert result.accepted is False
    assert result.rejection.constraint == "書き換えの理由"
    assert result.rejection.next_action.missing_fields == ["理由"]
    assert source_digest(settings.source_dir) == before


# ---------------------------------------------------------------- 媒体の語と提示物の置き場


def test_REQ_554_a_channel_with_a_presentation_directory_is_not_removed(settings) -> None:
    """提示物の置き場に媒体の語と同じ名前のディレクトリがあれば、書かずに、そのディレクトリの名前を返して断る。"""
    assert (settings.presentations_dir / "tsukikusa").is_dir()
    before = source_digest(settings.source_dir)

    result = VocabularyService(settings).remove_term("媒体", "tsukikusa", REASON)

    assert result.accepted is False
    assert result.rejection.constraint == TERM_IN_USE
    assert result.rejection.next_action.operation == "remove_term"
    assert result.rejection.next_action.candidates == ["tsukikusa"]
    assert "tsukikusa" in result.rejection.reason
    assert source_digest(settings.source_dir) == before


def test_REQ_554_a_channel_without_a_presentation_directory_can_be_removed(sample_copy) -> None:
    """提示物の置き場にその媒体のディレクトリが無ければ、媒体の語を消せる。"""
    import shutil

    shutil.rmtree(sample_copy / "presentations" / "nagiho")
    settings = sample_settings(sample_copy)

    result = VocabularyService(settings).remove_term("媒体", "nagiho", REASON)

    assert result.accepted is True, result.rejection
    assert "nagiho" not in _words(settings, "媒体")


def test_REQ_554_without_the_presentations_argument_a_channel_can_be_removed(sample_copy) -> None:
    """起動の引数で提示物の置き場を渡さなければ、提示物は 0 件なので、媒体の語を消せる。"""
    settings = load_settings(sample_copy / "data")

    result = VocabularyService(settings).remove_term("媒体", "tsukikusa", REASON)

    assert result.accepted is True, result.rejection
    assert "tsukikusa" not in _words(settings, "媒体")


def test_REQ_554_a_channel_used_by_a_section_and_a_directory_names_both(settings) -> None:
    """節でも使われ、提示物の置き場に同じ名前のディレクトリもあれば、1 つの断りの候補に節の道筋とディレクトリの名前を並べる。"""
    PositioningService(settings).record(
        PositioningDraft(
            decided_on=date(2026, 9, 20),
            scope="tsukikusa",
            headline_package="requirements-and-progress",
            rationale="媒体の語を節と提示物の両方で使うための決め。",
        )
    )
    assert (settings.presentations_dir / "tsukikusa").is_dir()
    before = source_digest(settings.source_dir)

    result = VocabularyService(settings).remove_term("媒体", "tsukikusa", REASON)

    assert result.accepted is False
    assert result.rejection.constraint == TERM_IN_USE
    assert result.rejection.next_action.operation == "revise_section"
    candidates = result.rejection.next_action.candidates
    assert candidates[-1] == "tsukikusa"
    assert any("2026-09-20" in path for path in candidates[:-1]), candidates
    assert "remove_term" in result.rejection.next_action.example
    assert source_digest(settings.source_dir) == before
