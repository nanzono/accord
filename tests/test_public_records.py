"""公開記録を登記する操作のテスト。

見るのは 3 つ。通らない入力を書かずに拒否して次の一手を返すこと、通った入力が 1 ブロックとして
積まれてそのまま読み戻せること、そして公開記録の置き場を設定に書いていない正本では、
書き足す先が無いことを鍵の名前つきで断ることである。
すべて同梱のサンプルの一時的な写しの上で走らせる。
"""

from __future__ import annotations

from pathlib import Path

from accord.models.results import PublicRecordDraft
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.public_records import PublicRecordService
from accord.vocabulary.settings import Settings, load_settings
from conftest import source_digest

# 同梱のサンプルにある受託案件の ID と、その見出し。通る入力の土台にして、1 か所だけ崩す。
KNOWN_SECTION = "nagisa-publishing"
KNOWN_SECTION_HEADING = "ナギサ書房 刊行計画の進行管理"

# 設定から抜くと、公開記録を使わない正本（この段より前の設定と同じ形）になる 3 行の書き出し。
PUBLIC_RECORD_SETTING_LINES = (
    "public_records = ",
    "public_record_kinds = ",
    "public_record_roles = ",
)


def _register(settings: Settings, **changes) -> object:
    """通る公開記録の入力を土台に、渡された欄だけを差し替えて登記を呼ぶ。"""
    draft = {
        "id": "data-meetup-talk",
        "name": "配送データの集約を話した勉強会の発表",
        "kind": settings.public_record_kinds[1],
        "published_on": "2026-03-14",
        "url": "https://example.com/events/report/data-meetup/",
        "publisher": "データの置き場づくりを持ち寄る勉強会（架空の催し）",
        "role": settings.public_record_roles[0],
        "origin_section": KNOWN_SECTION,
    }
    draft.update(changes)
    return PublicRecordService(settings).register(PublicRecordDraft(**draft))


def _without_public_records(settings: Settings) -> Settings:
    """写しの設定から、公開記録の置き場と語彙の 3 行を抜いて読み直す。"""
    path: Path = settings.config_path
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.startswith(PUBLIC_RECORD_SETTING_LINES)]
    assert len(kept) == len(lines) - 3, "写しの設定から抜く 3 行が見つからない"
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return load_settings(path)


def _records(settings: Settings) -> list:
    """写しの正本を読み直して、公開記録の一覧を返す。"""
    return MarkdownRepository(settings).load().public_records


def test_public_record_without_required_fields_is_rejected_with_their_names(
    settings: Settings,
) -> None:
    """名前と役割を空にすると、欠けた欄の名前と書き方の例を返し、正本を 1 バイトも変えない。"""
    before = source_digest(settings.source_dir)

    result = _register(settings, name="", role="")

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "公開記録の必須欄"
    next_action = result.rejection.next_action
    assert next_action.missing_fields == ["名前", "役割"]
    assert "名前" in next_action.example
    assert "役割" in next_action.example
    assert source_digest(settings.source_dir) == before


def test_kind_outside_the_vocabulary_is_rejected_with_the_word_list(settings: Settings) -> None:
    """設定に無い種類の語は受け付けず、設定が持つ種類の語をそのまま候補に返す。"""
    before = source_digest(settings.source_dir)

    result = _register(settings, kind="ポッドキャスト")

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "公開記録の種類と役割の語彙"
    assert result.rejection.next_action.candidates == settings.public_record_kinds
    assert source_digest(settings.source_dir) == before


def test_role_outside_the_vocabulary_is_rejected_with_the_word_list(settings: Settings) -> None:
    """設定に無い役割の語も、同じ制約で受け付けず、役割の語を候補に返す。"""
    before = source_digest(settings.source_dir)

    result = _register(settings, role="司会")

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "公開記録の種類と役割の語彙"
    assert result.rejection.next_action.candidates == settings.public_record_roles
    assert source_digest(settings.source_dir) == before


def test_origin_section_that_does_not_exist_is_rejected_with_close_headings(
    settings: Settings,
) -> None:
    """実在しない見出しを由来の節にすると、実在する見出しのうち近いものを候補に返す。"""
    before = source_digest(settings.source_dir)
    headings = MarkdownRepository(settings).load().section_headings()

    result = _register(settings, origin_section="nagisa-publishng")

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "由来の節の実在"
    candidates = result.rejection.next_action.candidates
    assert candidates
    # 候補はそのまま渡せる ID だけで、表示名は拒否の文の側に出る。
    assert all(candidate in headings for candidate in candidates)
    assert KNOWN_SECTION in candidates, candidates
    assert KNOWN_SECTION_HEADING in result.rejection.reason, result.rejection.reason
    assert source_digest(settings.source_dir) == before


def test_accepted_record_is_appended_as_one_block_and_reads_back(settings: Settings) -> None:
    """通る入力は末尾に 1 ブロック積まれ、読み直すと公開記録が 1 件増える。"""
    before = len(_records(settings))

    result = _register(settings)

    assert result.accepted is True, result.model_dump()
    records = _records(settings)
    assert len(records) == before + 1
    written = records[-1]
    assert written.id == "data-meetup-talk"
    assert written.name == "配送データの集約を話した勉強会の発表"
    assert written.url == "https://example.com/events/report/data-meetup/"
    assert written.origin_section == KNOWN_SECTION
    # 過去のブロックは書き換えず、末尾に積む。
    assert [record.name for record in records[:before]] == [
        record.name for record in _records(settings)[:before]
    ]


def test_record_without_url_is_accepted_and_reads_back_as_no_url(settings: Settings) -> None:
    """URL を渡さない入力は通り、「- URL: なし」で書かれ、読み戻すと URL を持たない。"""
    result = _register(
        settings, id="paper-progress-article", name="紙の雑誌に書いた進行管理の記事", url=None
    )

    assert result.accepted is True, result.model_dump()
    text = settings.path_for("public_records").read_text(encoding="utf-8")
    assert "- URL: なし" in text
    written = _records(settings)[-1]
    assert written.name == "紙の雑誌に書いた進行管理の記事"
    assert written.url is None


def test_register_without_the_public_record_file_is_rejected_with_the_setting_keys(
    settings: Settings,
) -> None:
    """公開記録の置き場を書いていない設定では、足す鍵 3 つを返して書かずに拒否する。"""
    plain = _without_public_records(settings)
    before = source_digest(plain.source_dir)

    result = PublicRecordService(plain).register(
        PublicRecordDraft(
            id="data-meetup-talk",
            name="配送データの集約を話した勉強会の発表",
            kind="登壇",
            published_on="2026-03-14",
            publisher="データの置き場づくりを持ち寄る勉強会（架空の催し）",
            role="登壇者",
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    listed = result.rejection.next_action.model_dump_json()
    for key in ("public_records", "public_record_kinds", "public_record_roles"):
        assert key in listed, listed
    assert source_digest(plain.source_dir) == before
