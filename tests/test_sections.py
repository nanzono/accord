"""正本のファイルを節で読み書きする操作と、正本の書き出しのテスト。

読みの 3 つ（節の一覧・節の読み・事実の検索）、書きの 2 つ（事実の登記・節の書き換え）、
書き出しを、要件 1 件につき 1 本以上で見る。書きのテストは、断るときに正本が 1 バイトも
変わらないことも見る。すべて同梱のサンプルの一時的な写しの上で走らせる。
主に 2 つ目の見本（職歴の枠と受託案件を 1 つのファイルに入れ子で持つ正本）を使う。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from accord.repository.markdown_repository import MarkdownRepository
from accord.repository.sections import section_fingerprint
from accord.services.sections import SectionService
from conftest import git, source_digest

CAREER = "career_master.md"
LEDGER = "keirekisho/daicho.md"
CAREER_TITLE = "経歴の正本"
CAREER_ROOT = f"{CAREER_TITLE} > 職歴・案件（新しい順）"
FREELANCE_ID = "freelance-solo"
FREELANCE_PATH = f"{CAREER_ROOT} > 2021-04〜現在 フリーランス"
TERAMINA_ID = "teramina-delivery"
TERAMINA_HEADING = "テラミナ物流 配送データの置き場づくり"
TERAMINA_PATH = f"{FREELANCE_PATH} > {TERAMINA_HEADING}"
BASIC_PATH = f"{CAREER_TITLE} > 基本情報"

FACT = "取り込みが失敗した朝に、担当者へ知らせる仕組みを足した"
FACT_SOURCE = "引き渡しの報告書"
FACT_DATE = "2026-10-01"
FACT_LINE = f"- {FACT}（{FACT_DATE}、出所: {FACT_SOURCE}）"


def _service(settings) -> SectionService:
    return SectionService(settings)


def _career_text(settings) -> str:
    return settings.path_for("career").read_text(encoding="utf-8")


def _headings(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("#")]


# ---------------------------------------------------------------- 節の一覧


def test_REQ_425_list_sections_returns_every_section_in_source_order(alt_settings) -> None:
    """正本の各ファイルの節を、ファイルの名前・見出しの道筋・指紋・字数つきで、正本の並びの順に返す。"""
    result = _service(alt_settings).list_sections()

    files = list(dict.fromkeys(entry.file for entry in result.sections))
    assert files == alt_settings.source_file_names()
    career = [entry for entry in result.sections if entry.file == CAREER]
    assert len(career) == len(_headings(_career_text(alt_settings)))
    teramina = next(entry for entry in career if entry.heading_path == TERAMINA_PATH)
    body = _service(alt_settings).read_section(TERAMINA_PATH).body
    assert teramina.fingerprint == section_fingerprint(body)
    assert teramina.chars == len(body)


def test_REQ_426_listed_sections_with_an_id_carry_the_id_and_disclosure(alt_settings) -> None:
    """ID の欄を持つ節には ID と公開可否が付き、持たない節には付かない。"""
    result = _service(alt_settings).list_sections(CAREER)

    by_path = {entry.heading_path: entry for entry in result.sections}
    assert by_path[TERAMINA_PATH].id == TERAMINA_ID
    assert by_path[TERAMINA_PATH].disclosure == "公開可"
    assert by_path[BASIC_PATH].id is None
    assert by_path[BASIC_PATH].disclosure is None


def test_REQ_427_list_sections_of_one_file_returns_only_that_file(alt_settings) -> None:
    """ファイルの名前を渡すと、そのファイルの節だけを返す。"""
    result = _service(alt_settings).list_sections(LEDGER)

    assert result.sections
    assert {entry.file for entry in result.sections} == {LEDGER}


def test_REQ_428_an_unknown_file_name_returns_every_source_file_as_candidates(
    alt_settings,
) -> None:
    """正本のファイルに無い名前を渡すと、正本のファイルの名前をすべて候補に返す。"""
    result = _service(alt_settings).list_sections("career.md")

    assert result.sections == []
    assert result.candidates == alt_settings.source_file_names()


# ---------------------------------------------------------------- 節の読み


def test_REQ_429_read_section_by_id_or_path_returns_body_and_fingerprint(alt_settings) -> None:
    """ID でも見出しの道筋でも、その節の本文と指紋が返る。"""
    by_id = _service(alt_settings).read_section(TERAMINA_ID)
    by_path = _service(alt_settings).read_section(TERAMINA_PATH)

    assert by_id.body == by_path.body
    assert "6 拠点の実績を 1 つの置き場に集め" in by_id.body
    assert by_id.fingerprint == section_fingerprint(by_id.body)
    assert by_id.file == CAREER


def test_REQ_430_read_section_excludes_subsections(alt_settings) -> None:
    """読んだ本文に、下位の見出しの節の本文を含めない。"""
    result = _service(alt_settings).read_section(FREELANCE_ID)

    assert "3 社の案件を" in result.body
    assert "6 拠点の実績" not in result.body
    assert TERAMINA_HEADING not in result.body


def test_REQ_431_an_unknown_section_returns_close_paths(alt_settings) -> None:
    """当たる節が無いときは、本文を返さずに、近い見出しの道筋を候補に返す。"""
    result = _service(alt_settings).read_section(TERAMINA_HEADING)

    assert result.body is None
    assert TERAMINA_PATH in result.candidates


def test_REQ_432_a_path_found_in_two_files_returns_qualified_candidates(settings) -> None:
    """同じ見出しの道筋の節が 2 つ以上あるときは、本文を返さず、ファイルの名前つきの道筋を候補に返す。"""
    for key in ("presentation_rules", "packages"):
        with settings.path_for(key).open("a", encoding="utf-8") as handle:
            handle.write("\n# 稼働条件\n\n別のファイルに置いた、同じ見出しの節。\n")

    result = _service(settings).read_section("稼働条件")

    assert result.body is None
    assert result.candidates == ["product/packages.md :: 稼働条件", "misekata_master.md :: 稼働条件"]
    again = _service(settings).read_section(result.candidates[1])
    assert again.body == "別のファイルに置いた、同じ見出しの節。"


# ---------------------------------------------------------------- 事実の検索


def test_REQ_433_search_returns_lines_with_file_and_path(alt_settings) -> None:
    """語を含む行を、ファイルの名前と見出しの道筋と行の文で返す。"""
    result = _service(alt_settings).search_facts("6 拠点")

    hit = next(item for item in result.hits if item.file == CAREER)
    assert hit.heading_path == TERAMINA_PATH
    assert "6 拠点の実績を 1 つの置き場に集め" in hit.line


def test_REQ_434_search_ignores_width_and_case(alt_settings) -> None:
    """全角と半角、大文字と小文字の違いを同じ文字として扱う。"""
    plain = _service(alt_settings).search_facts("SQL")
    wide = _service(alt_settings).search_facts("ｓｑｌ")

    assert plain.total > 0
    assert [hit.line for hit in wide.hits] == [hit.line for hit in plain.hits]


def test_REQ_435_more_than_fifty_hits_are_cut_with_the_total(alt_settings) -> None:
    """当たった行が 50 件を超えたら、先頭の 50 件と当たった総数を返す。"""
    expected = 0
    for name in alt_settings.source_file_names():
        text = (alt_settings.source_dir / name).read_text(encoding="utf-8")
        expected += sum(1 for line in text.splitlines() if "の" in line)

    result = _service(alt_settings).search_facts("の")

    assert expected > 50
    assert result.total == expected
    assert len(result.hits) == 50


def test_REQ_436_reading_operations_never_rewrite_the_source(alt_settings) -> None:
    """節の一覧と節の読みと事実の検索は、正本のファイルを 1 バイトも書き換えない。"""
    before = source_digest(alt_settings.source_dir)
    service = _service(alt_settings)

    service.list_sections()
    service.read_section(TERAMINA_ID)
    service.search_facts("置き場")

    assert source_digest(alt_settings.source_dir) == before


# ---------------------------------------------------------------- 事実の登記


def _record(settings, section=TERAMINA_ID, fact=FACT, source=FACT_SOURCE, day=FACT_DATE):
    return _service(settings).record_fact(section, fact, source, day)


def test_REQ_437_record_fact_appends_one_line_at_the_end_of_the_section(alt_settings) -> None:
    """節の本文の末尾（下位の見出しの前）に、事実の文と日付と出所の箇条を 1 行足す。"""
    result = _record(alt_settings, section=FREELANCE_ID)

    assert result.accepted is True, result.rejection
    body = _service(alt_settings).read_section(FREELANCE_ID).body
    assert body.splitlines()[-1] == FACT_LINE
    text = _career_text(alt_settings)
    assert text.index(FACT_LINE) < text.index(f"#### {TERAMINA_HEADING}")
    assert text.count(FACT_LINE) == 1


def test_REQ_438_record_fact_outside_the_career_source_is_refused(alt_settings) -> None:
    """経歴の正本に無い節を渡すと、書かずに、近い見出しの道筋を候補にして断る。"""
    before = source_digest(alt_settings.source_dir)

    missing = _record(alt_settings, section=TERAMINA_HEADING)
    elsewhere = _record(alt_settings, section="requirements-and-progress")

    assert missing.accepted is False
    assert TERAMINA_PATH in missing.rejection.next_action.candidates
    assert elsewhere.accepted is False
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_439_record_fact_without_the_fact_or_source_names_the_missing_field(
    alt_settings,
) -> None:
    """事実の文か出所が空なら、書かずに、欠けた欄の名前を断りに返す。"""
    before = source_digest(alt_settings.source_dir)

    no_fact = _record(alt_settings, fact=" ")
    no_source = _record(alt_settings, source="")

    assert no_fact.accepted is False
    assert no_fact.rejection.next_action.missing_fields == ["事実の文"]
    assert no_source.rejection.next_action.missing_fields == ["出所"]
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_440_record_fact_with_an_unreadable_date_gives_an_example(alt_settings) -> None:
    """日付が読めないなら、書かずに、日付の書き方の例を断りに返す。"""
    before = source_digest(alt_settings.source_dir)

    result = _record(alt_settings, day="10月1日")

    assert result.accepted is False
    assert "2026-10-13" in result.rejection.next_action.example
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_441_record_fact_with_a_line_break_is_refused(alt_settings) -> None:
    """事実の文が改行を含むなら、書かずに、1 件 1 行で登記することを断りに返す。"""
    before = source_digest(alt_settings.source_dir)

    result = _record(alt_settings, fact="1 つ目の事実\n2 つ目の事実")

    assert result.accepted is False
    assert "1 件 1 行" in result.rejection.reason
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_442_record_fact_returns_the_line_and_the_new_fingerprint(alt_settings) -> None:
    """登記が通ると、足した行とその節の新しい指紋を返す。"""
    result = _record(alt_settings)

    assert result.recorded["足した行"] == FACT_LINE
    assert result.recorded["新しい指紋"] == _service(alt_settings).read_section(TERAMINA_ID).fingerprint


# ---------------------------------------------------------------- 節の書き換え


def _revise(settings, section, body, fingerprint=None, reason="契約書で確かめ直した"):
    current = _service(settings).read_section(section)
    return _service(settings).revise_section(
        section, body, current.fingerprint if fingerprint is None else fingerprint, reason
    )


NEW_BASIC = "- 名前の読み: きりさわ ちかげ\n- 拠点: 在宅だけ\n- 連絡の手段: メール"


def test_REQ_443_revise_section_replaces_the_body(alt_settings) -> None:
    """節と新しい本文と読んだときの指紋と理由を渡すと、その節の本文を新しい本文に置き換える。"""
    result = _revise(alt_settings, BASIC_PATH, NEW_BASIC)

    assert result.accepted is True, result.rejection
    assert _service(alt_settings).read_section(BASIC_PATH).body == NEW_BASIC


def test_REQ_444_revise_section_keeps_the_heading_and_subsections(alt_settings) -> None:
    """節の書き換えは、その節の見出しの行と下位の見出しの節を変えない。"""
    text = _career_text(alt_settings)
    children = text[text.index(f"#### {TERAMINA_HEADING}") : text.index("### 2016-04")]
    body = _service(alt_settings).read_section(FREELANCE_ID).body.replace("1 人で担当した", "ひとりで担当した")

    result = _revise(alt_settings, FREELANCE_ID, body)

    assert result.accepted is True, result.rejection
    after = _career_text(alt_settings)
    assert children in after
    assert "### 2021-04〜現在 フリーランス" in after
    assert _headings(after) == _headings(text)


def test_REQ_445_a_stale_fingerprint_is_refused_with_the_current_one(alt_settings) -> None:
    """渡された指紋がいまの指紋と違うなら、書かずに、いまの指紋と読み直すことを返す。"""
    before = source_digest(alt_settings.source_dir)
    current = _service(alt_settings).read_section(BASIC_PATH).fingerprint

    result = _revise(alt_settings, BASIC_PATH, NEW_BASIC, fingerprint="00000000")

    assert result.accepted is False
    assert current in result.rejection.reason
    assert current in result.rejection.next_action.candidates
    assert "read_section" in result.rejection.reason
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_446_a_body_with_a_heading_line_is_refused(alt_settings) -> None:
    """新しい本文が見出しの行を含むなら、書かずに、節の新設と見出しの変更はできないことを返す。"""
    before = source_digest(alt_settings.source_dir)

    result = _revise(alt_settings, BASIC_PATH, NEW_BASIC + "\n\n## 新しい節\n\n中身")

    assert result.accepted is False
    assert "節の新設と見出しの変更" in result.rejection.reason
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_447_removing_or_changing_the_id_field_is_refused(alt_settings) -> None:
    """新しい本文で ID の欄が消えるか値が変わるなら、書かずに、元の値のまま残すことを返す。"""
    before = source_digest(alt_settings.source_dir)
    body = _service(alt_settings).read_section(TERAMINA_ID).body

    removed = _revise(alt_settings, TERAMINA_ID, body.replace(f"- ID: {TERAMINA_ID}\n", ""))
    changed = _revise(alt_settings, TERAMINA_ID, body.replace(TERAMINA_ID, "teramina-routes"))

    for result in (removed, changed):
        assert result.accepted is False
        assert "元の値のまま残す" in result.rejection.reason
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_448_a_revision_without_a_reason_names_the_missing_field(alt_settings) -> None:
    """書き換えの理由が空なら、書かずに、欠けた欄の名前を返す。"""
    before = source_digest(alt_settings.source_dir)

    result = _revise(alt_settings, BASIC_PATH, NEW_BASIC, reason="  ")

    assert result.accepted is False
    assert result.rejection.next_action.missing_fields == ["理由"]
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_449_a_revision_returns_the_new_fingerprint(alt_settings) -> None:
    """書き換えが通ると、その節の新しい指紋を返す。"""
    result = _revise(alt_settings, BASIC_PATH, NEW_BASIC)

    assert result.recorded["新しい指紋"] == section_fingerprint(NEW_BASIC)
    assert result.recorded["新しい指紋"] == _service(alt_settings).read_section(BASIC_PATH).fingerprint


def test_REQ_450_writing_a_copied_section_names_the_copy_to_compare(alt_settings) -> None:
    """書いたことで新しく出た「写しの鮮度」の違反を、読み比べる写しの名前を添えて返す。"""
    body = _service(alt_settings).read_section(TERAMINA_ID).body.replace(
        "毎朝の取り込み", "毎朝 6 時の取り込み"
    )

    revised = _revise(alt_settings, TERAMINA_ID, body)
    recorded = _record(alt_settings)

    for result in (revised, recorded):
        assert result.accepted is True, result.rejection
        copies = result.recorded["読み比べる写し"]
        assert copies and all(item.startswith(LEDGER) for item in copies), copies
        assert any(note.startswith("写しの鮮度") for note in result.warnings), result.warnings


def test_REQ_450_a_record_without_a_copy_names_no_copy(alt_settings) -> None:
    """どの写しも出典にしていない節に書いたときは、読み比べる写しを返さない。"""
    result = _revise(alt_settings, BASIC_PATH, NEW_BASIC)

    assert result.recorded["読み比べる写し"] == []


def test_REQ_467_a_write_that_brings_a_new_violation_is_refused(alt_settings) -> None:
    """書いた後の正本に、書く前に無かった写しの鮮度以外の違反が出るなら、書かずにその違反を返す。"""
    before = source_digest(alt_settings.source_dir)
    # 機能の裏づけに使われている受託案件から、必須の欄「出所」を消す。ID と公開可否には触れない。
    body = "\n".join(
        line
        for line in _service(alt_settings).read_section(TERAMINA_ID).body.splitlines()
        if not line.startswith("- 出所:")
    )

    result = _revise(alt_settings, TERAMINA_ID, body)

    assert result.accepted is False
    assert result.rejection.constraint == "裏づけ節名の実在"
    assert "書く前に無かった整合の検査の違反" in result.rejection.reason
    assert source_digest(alt_settings.source_dir) == before


# ---------------------------------------------------------------- 書き出し


def test_REQ_525_export_writes_every_source_file_to_the_given_path(settings, tmp_path) -> None:
    """渡された書き出し先に、正本の各ファイルの中身を、ファイルの名前の見出しを付けて 1 つの Markdown で書く。"""
    destination = tmp_path / "exported" / "all.md"

    result = _service(settings).export_source(str(destination))

    assert result.written is True
    text = destination.read_text(encoding="utf-8")
    for name in settings.source_file_names():
        assert f"# {name}\n" in text
        first = (settings.source_dir / name).read_text(encoding="utf-8").strip().splitlines()[-1]
        assert first in text


def test_REQ_525_an_export_path_inside_the_data_is_refused(settings) -> None:
    """書き出し先が経歴データの置き場の中なら、書かずに断る。置き場は 1 バイトも変わらない。"""
    before = source_digest(settings.source_dir)

    result = _service(settings).export_source(str(settings.source_dir / "export.md"))

    assert result.written is False
    assert result.rejection.constraint == "書き出し先は置き場の外"
    assert result.rejection.next_action.operation == "export_source"
    assert source_digest(settings.source_dir) == before


def test_REQ_455_export_returns_the_name_and_size_without_the_path(settings, tmp_path) -> None:
    """書き出しが通ると、書いたファイルの名前と字数を返し、書き出し先の絶対パスを返さない。"""
    destination = tmp_path / "exported" / "all.md"

    result = _service(settings).export_source(str(destination))

    assert result.file_name == "all.md"
    assert result.chars == len(destination.read_text(encoding="utf-8"))
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert str(destination.parent) not in dumped
    assert str(destination.parent.parent) not in dumped


def test_REQ_469_a_fact_written_as_a_field_is_refused(alt_settings) -> None:
    """足す行が ID か公開可否の欄として読まれて値が変わるなら、書かずに、欄の書き方で書かないことを返す。"""
    before = source_digest(alt_settings.source_dir)

    disclosure = _record(alt_settings, fact="公開可否: 公開不可")
    identifier = _record(alt_settings, fact="ID: teramina-routes")

    for result in (disclosure, identifier):
        assert result.accepted is False
        assert result.rejection.constraint == "事実の文を欄の書き方で書かない"
    assert source_digest(alt_settings.source_dir) == before


@pytest.mark.parametrize(
    "fact",
    ["公開可否：公開不可", "公開可否:公開不可", "公開可否（再確認）: 公開不可", "公開可否 : 公開不可"],
    ids=["全角のコロン", "空白なし", "括弧書き", "コロンの前に空白"],
)
def test_REQ_469_other_ways_of_writing_a_field_in_a_fact_are_refused(alt_settings, fact) -> None:
    """欄の書き方の揺れ（全角のコロン・空白・括弧書き）で公開可否を書いた事実の行も、書かずに断る。"""
    before = source_digest(alt_settings.source_dir)

    result = _record(alt_settings, fact=fact)

    assert result.accepted is False
    assert result.rejection.constraint == "事実の文を欄の書き方で書かない"
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_469_a_bold_label_line_is_read_as_the_disclosure_and_refused(alt_settings) -> None:
    """太字のラベルで書いた公開可否の行も公開可否の欄として読むので、事実の行に書くと断る。"""
    before = source_digest(alt_settings.source_dir)

    outside = _record(alt_settings, fact="**公開可否**: 公開不可")
    inside = _record(alt_settings, fact="**公開可否：**公開不可")

    for result in (outside, inside):
        assert result.accepted is False
        assert result.rejection.constraint == "事実の文を欄の書き方で書かない"
    assert source_digest(alt_settings.source_dir) == before
    snapshot = MarkdownRepository(alt_settings).load()
    assert snapshot.disclosure_of(TERAMINA_ID) == "公開可"


# ---------------------------------------------------------------- 節の構造と公開可否を変える
#
# 構造の操作と公開可否を変える操作は、書き込みの記録が有効な置き場でだけ書く。だからこの節の
# テストは、写しを git のリポジトリにして書き込みの記録を有効にした設定（recording）で走らせる。

OUTSIDE = f"{CAREER_TITLE} > 職歴の外の活動"
STUDY_PATH = f"{OUTSIDE} > 社外の勉強会の運営"
WRITING_PATH = f"{OUTSIDE} > 技術記事の執筆"
AGENCY_ID = "agency-employee"
GROUP_PATH = f"{FREELANCE_PATH} > 2025 年から続いている案件"
NAGISA_PATH = f"{GROUP_PATH} > ナギサ書房 刊行計画の進行管理"
LEDGER_ENTRY = "職務経歴書の台帳 > 案件1｜配送データの置き場づくり"
STRUCTURE_REASON = "職歴の並びを整える"


@pytest.fixture
def recording(settings):
    """写しの経歴データの置き場（git の作業ツリーの根）を指す見本の設定を返す。書き込みはいつも記録される。"""
    return settings


def _fingerprint(settings, section) -> str:
    return _service(settings).read_section(section).fingerprint


def _commits(settings) -> int:
    return int(git(settings.source_dir, "rev-list", "--count", "HEAD").strip())


def _last_commit_files(settings) -> list[str]:
    return git(settings.source_dir, "show", "--name-only", "--format=", "HEAD").split()


def _rename(settings, section, heading, fingerprint=None, reason=STRUCTURE_REASON):
    current = _fingerprint(settings, section) if fingerprint is None else fingerprint
    return _service(settings).rename_heading(section, heading, current, reason)


def _add(settings, parent, heading, body="", reason=STRUCTURE_REASON, before=None):
    return _service(settings).add_section(parent, heading, body, reason, before)


def _remove(settings, section, fingerprint=None, reason=STRUCTURE_REASON):
    current = _fingerprint(settings, section) if fingerprint is None else fingerprint
    return _service(settings).remove_section(section, current, reason)


def _move(settings, section, parent, fingerprint=None, reason=STRUCTURE_REASON, before=None):
    current = _fingerprint(settings, section) if fingerprint is None else fingerprint
    return _service(settings).move_section(section, parent, current, reason, before)


def _disclose(settings, section, value, fingerprint=None, reason=STRUCTURE_REASON):
    current = _fingerprint(settings, section) if fingerprint is None else fingerprint
    return _service(settings).set_disclosure(section, value, current, reason)


def _paths(settings, file=CAREER) -> list[str]:
    return [entry.heading_path for entry in _service(settings).list_sections(file).sections]


# ---------------------------------------------------------------- 見出しを変える


def test_REQ_470_rename_changes_only_the_heading_text(recording) -> None:
    """見出しの文字だけを置き換え、見出しの深さと本文と下位の節を変えない。"""
    text = _career_text(recording)
    body = _service(recording).read_section(FREELANCE_ID).body
    new_heading = "2021-04〜現在 フリーランス（屋号なし）"

    result = _rename(recording, FREELANCE_PATH, new_heading)

    assert result.accepted is True, result.rejection
    after = _career_text(recording)
    assert after == text.replace("### 2021-04〜現在 フリーランス\n", f"### {new_heading}\n", 1)
    assert _service(recording).read_section(FREELANCE_ID).body == body
    new_path = f"{CAREER_ROOT} > {new_heading}"
    assert f"{new_path} > {TERAMINA_HEADING}" in _paths(recording)
    assert result.recorded["見出しの道筋"] == new_path


def test_REQ_470_rename_changes_the_first_heading_of_the_file(recording) -> None:
    """ファイルの 1 行目の見出しも、この操作で変える。"""
    result = _rename(recording, CAREER_TITLE, "経歴の正本（霧沢 千景）")

    assert result.accepted is True, result.rejection
    assert "\n# 経歴の正本（霧沢 千景）\n" in _career_text(recording)
    assert _paths(recording)[0] == "経歴の正本（霧沢 千景）"


@pytest.mark.parametrize("heading", ["", "  ", "上の行\n下の行", "## 深さを書いた見出し"])
def test_REQ_471_a_bad_heading_is_refused_with_an_example(recording, heading) -> None:
    """新しい見出しが空か、改行を含むか、「#」で始まるなら、書かずに、見出しの書き方の例を返す。"""
    before = source_digest(recording.source_dir)

    result = _rename(recording, WRITING_PATH, heading)

    assert result.accepted is False
    assert result.rejection.constraint == "見出しの書き方"
    assert "「#」を付けない" in result.rejection.next_action.example
    assert source_digest(recording.source_dir) == before


# ---------------------------------------------------------------- 節を足す


def test_REQ_472_add_puts_the_section_at_the_end_of_the_parent(recording) -> None:
    """親より 1 段深い見出しの節を、親の下位の節の末尾に足す。"""
    commits = _commits(recording)

    result = _add(recording, OUTSIDE, "登壇の記録", "年に 2 回ほど、勉強会で話している。")

    assert result.accepted is True, result.rejection
    paths = _paths(recording)
    assert paths[-3:] == [STUDY_PATH, WRITING_PATH, f"{OUTSIDE} > 登壇の記録"]
    assert "\n### 登壇の記録\n\n年に 2 回ほど、勉強会で話している。\n" in _career_text(recording)
    assert _service(recording).read_section(f"{OUTSIDE} > 登壇の記録").body == "年に 2 回ほど、勉強会で話している。"
    assert _commits(recording) == commits + 1


def test_REQ_473_add_before_a_child_puts_the_section_just_before_it(recording) -> None:
    """前に置く節を渡すと、足す節を、親の下位にあるその節の直前に置く。"""
    result = _add(recording, OUTSIDE, "登壇の記録", "年に 2 回ほど話している。", before=STUDY_PATH)

    assert result.accepted is True, result.rejection
    paths = _paths(recording)
    assert paths.index(f"{OUTSIDE} > 登壇の記録") + 1 == paths.index(STUDY_PATH)


def test_REQ_474_a_preceding_section_outside_the_parent_is_refused(recording) -> None:
    """前に置く節が親の直下の節でないなら、書かずに、親の直下の節の見出しの道筋を候補に返す。"""
    before = source_digest(recording.source_dir)

    added = _add(recording, OUTSIDE, "登壇の記録", "中身", before=TERAMINA_PATH)
    moved = _move(recording, WRITING_PATH, CAREER_TITLE, before=TERAMINA_PATH)

    assert added.accepted is False
    assert added.rejection.next_action.candidates == [STUDY_PATH, WRITING_PATH]
    assert moved.accepted is False
    assert f"{CAREER_TITLE} > 基本情報" in moved.rejection.next_action.candidates
    assert source_digest(recording.source_dir) == before


def test_REQ_475_a_parent_at_depth_six_is_refused(recording) -> None:
    """親の見出しの深さが 6 なら、書かずに、それより深い見出しを作れないことを返す。"""
    deep = _add(recording, NAGISA_PATH, "社内の記録", "週 1 回の確認の場の記録。")
    assert deep.accepted is True, deep.rejection
    assert "\n###### 社内の記録\n" in _career_text(recording)
    before = source_digest(recording.source_dir)

    result = _add(recording, f"{NAGISA_PATH} > 社内の記録", "さらに深い節", "中身")

    assert result.accepted is False
    assert "それより深い見出しは作れない" in result.rejection.reason
    assert source_digest(recording.source_dir) == before


# ---------------------------------------------------------------- 節を消す


def test_REQ_476_remove_deletes_the_heading_and_the_body(recording) -> None:
    """節の見出しの行と本文を消す。ほかの節は変えない。"""
    text = _career_text(recording)
    body = _service(recording).read_section(WRITING_PATH).body

    result = _remove(recording, WRITING_PATH)

    assert result.accepted is True, result.rejection
    after = _career_text(recording)
    assert "### 技術記事の執筆" not in after
    assert body not in after
    assert WRITING_PATH not in _paths(recording)
    assert after.rstrip("\n") == text[: text.index("### 技術記事の執筆")].rstrip("\n")
    assert _last_commit_files(recording) == [CAREER]


def test_REQ_477_a_section_with_subsections_is_not_removed(recording) -> None:
    """下位の節を持つ節は、書かずに、先に下位の節を消すことと下位の節の見出しの道筋を返す。"""
    before = source_digest(recording.source_dir)

    result = _remove(recording, OUTSIDE)

    assert result.accepted is False
    assert "先に下位の節" in result.rejection.reason
    assert result.rejection.next_action.candidates == [STUDY_PATH, WRITING_PATH]
    assert source_digest(recording.source_dir) == before


# ---------------------------------------------------------------- 節を動かす


def test_REQ_491_move_carries_the_subsections_and_shifts_their_depth(recording) -> None:
    """節を下位の節ごと新しい親の末尾へ移し、深さを新しい親より 1 段深くそろえ、1 回の書き込みにする。"""
    bodies = {
        path: _service(recording).read_section(path).body for path in (OUTSIDE, STUDY_PATH, WRITING_PATH)
    }
    commits = _commits(recording)

    result = _move(recording, OUTSIDE, BASIC_PATH)

    assert result.accepted is True, result.rejection
    new_root = f"{BASIC_PATH} > 職歴の外の活動"
    assert result.recorded["見出しの道筋"] == new_root
    text = _career_text(recording)
    assert "\n### 職歴の外の活動\n" in text
    assert "\n#### 社外の勉強会の運営\n" in text
    assert "\n#### 技術記事の執筆\n" in text
    for path, body in bodies.items():
        moved = path.replace(OUTSIDE, new_root, 1)
        assert _service(recording).read_section(moved).body == body
    assert _commits(recording) == commits + 1
    assert _last_commit_files(recording) == [CAREER]


def test_REQ_492_move_before_a_child_reorders_within_the_parent(recording) -> None:
    """前に置く節を渡すと、新しい親の直下のその節の直前に置く（同じ親の中の並べ替え）。"""
    body = _service(recording).read_section(WRITING_PATH).body

    result = _move(recording, WRITING_PATH, OUTSIDE, before=STUDY_PATH)

    assert result.accepted is True, result.rejection
    paths = _paths(recording)
    assert paths.index(WRITING_PATH) + 1 == paths.index(STUDY_PATH)
    assert _service(recording).read_section(WRITING_PATH).body == body


def test_REQ_493_a_section_is_not_moved_under_itself(recording) -> None:
    """新しい親が動かす節そのものかその下位の節なら、書かずに、自分の下へは動かせないことを返す。"""
    before = source_digest(recording.source_dir)

    into_child = _move(recording, FREELANCE_PATH, TERAMINA_PATH)
    into_self = _move(recording, FREELANCE_PATH, FREELANCE_PATH)

    for result in (into_child, into_self):
        assert result.accepted is False
        assert "自分の下へは動かせない" in result.rejection.reason
    assert source_digest(recording.source_dir) == before


def test_REQ_494_a_move_deeper_than_six_is_refused(recording) -> None:
    """動かした後に深さが 6 を超える見出しが出るなら、書かずに、超える見出しの道筋を返す。"""
    before = source_digest(recording.source_dir)
    agency = f"{CAREER_ROOT} > 2016-04〜2021-03 受託開発の会社"

    result = _move(recording, agency, NAGISA_PATH)

    assert result.accepted is False
    assert "深さが足りない" in result.rejection.reason
    assert result.rejection.next_action.candidates == [f"{agency} > 在籍中の社内の取り組み"]
    assert source_digest(recording.source_dir) == before


def test_REQ_495_a_move_across_files_is_refused(recording) -> None:
    """動かす節と新しい親が別のファイルにあるなら、書かずに、ファイルをまたいで動かせないことを返す。"""
    before = source_digest(recording.source_dir)

    result = _move(recording, WRITING_PATH, "外に出したもの > 刊行計画の進め方を話した勉強会の発表")

    assert result.accepted is False
    assert "ファイルをまたいで" in result.rejection.reason
    assert source_digest(recording.source_dir) == before


# ---------------------------------------------------------------- 公開可否を変える


def test_REQ_496_set_disclosure_replaces_only_the_value(recording) -> None:
    """公開可否の欄の値だけを置き換える。"""
    text = _career_text(recording)
    new_value = "公開可（社名は出さない）"

    result = _disclose(recording, TERAMINA_ID, new_value)

    assert result.accepted is True, result.rejection
    after = _career_text(recording)
    teramina_at = text.index(f"#### {TERAMINA_HEADING}")
    expected = text[:teramina_at] + text[teramina_at:].replace("- 公開可否: 公開可\n", f"- 公開可否: {new_value}\n", 1)
    assert after == expected
    assert _service(recording).read_section(TERAMINA_ID).disclosure == new_value


def test_REQ_496_set_disclosure_adds_the_field_after_the_id_line(recording) -> None:
    """公開可否の欄が無ければ、ID の欄の行の直後に公開可否の欄の行を足す。"""
    text = _career_text(recording)

    result = _disclose(recording, "study-group-host", "公開可")

    assert result.accepted is True, result.rejection
    assert _career_text(recording) == text.replace(
        "- ID: study-group-host\n", "- ID: study-group-host\n- 公開可否: 公開可\n", 1
    )


def test_REQ_497_a_section_without_an_id_has_no_disclosure(recording) -> None:
    """ID の欄を持たない節なら、書かずに、公開可否は ID の欄を持つ節にだけ置くことを返す。"""
    before = source_digest(recording.source_dir)

    result = _disclose(recording, BASIC_PATH, "公開可")

    assert result.accepted is False
    assert "ID の欄を持つ節にだけ置く" in result.rejection.reason
    assert source_digest(recording.source_dir) == before


@pytest.mark.parametrize("value", ["", "  ", "公開可\n公開不可"])
def test_REQ_498_an_empty_or_multiline_disclosure_is_refused(recording, value) -> None:
    """新しい公開可否が空か改行を含むなら、書かずに、公開可否の書き方の例を返す。"""
    before = source_digest(recording.source_dir)

    result = _disclose(recording, TERAMINA_ID, value)

    assert result.accepted is False
    assert result.rejection.constraint == "公開可否の書き方"
    assert "公開不可（" in result.rejection.next_action.example
    assert source_digest(recording.source_dir) == before


def test_REQ_499_lifting_a_private_section_reports_it_and_writes_both_values(recording) -> None:
    """「公開不可」から外すと、材料に新しく出ることと元の値・新しい値・理由を返し、コミットの説明にも書く。"""
    old_value = _service(recording).read_section(AGENCY_ID).disclosure
    new_value = "公開可（社名は出さない）"
    reason = "在籍先との約束の期限が過ぎた"

    result = _disclose(recording, AGENCY_ID, new_value, reason=reason)

    assert result.accepted is True, result.rejection
    assert old_value.startswith("公開不可")
    assert result.recorded["材料に新しく出る"] is True
    assert result.recorded["元の公開可否"] == old_value
    assert result.recorded["新しい公開可否"] == new_value
    assert result.recorded["理由"] == reason
    assert any("材料の取り出しに新しく出る" in note for note in result.warnings)
    message = git(recording.source_dir, "log", "-1", "--format=%B")
    for text in (old_value, new_value, reason):
        assert text in message
    assert MarkdownRepository(recording).load().is_private(AGENCY_ID) is False


def test_REQ_499_a_change_between_public_values_does_not_report_it(recording) -> None:
    """公開不可でない値どうしの変更では、材料に新しく出る知らせを返さない。"""
    result = _disclose(recording, TERAMINA_ID, "公開可（社名は出さない）")

    assert result.accepted is True, result.rejection
    assert "材料に新しく出る" not in result.recorded


# ---------------------------------------------------------------- 構造の操作に共通


def test_REQ_478_a_duplicated_heading_under_one_parent_is_refused(recording) -> None:
    """見出しの変更・節の追加・節の移動で同じ親の下に同じ見出しが 2 つできるなら、書かずに道筋を返す。"""
    before = source_digest(recording.source_dir)

    renamed = _rename(recording, STUDY_PATH, "技術記事の執筆")
    added = _add(recording, OUTSIDE, "技術記事の執筆", "中身")

    for result in (renamed, added):
        assert result.accepted is False
        assert result.rejection.constraint == "同じ親の下の見出しの重なり"
        assert result.rejection.next_action.candidates == [WRITING_PATH]
    assert source_digest(recording.source_dir) == before

    assert _add(recording, BASIC_PATH, "技術記事の執筆", "中身").accepted is True
    moved = _move(recording, WRITING_PATH, BASIC_PATH)
    assert moved.accepted is False
    assert moved.rejection.next_action.candidates == [f"{BASIC_PATH} > 技術記事の執筆"]


def test_REQ_479_a_stale_fingerprint_stops_every_structure_operation(recording) -> None:
    """見出しの変更・節の削除・節の移動・公開可否の変更は、指紋が違えば書かずに、いまの指紋を返す。"""
    before = source_digest(recording.source_dir)
    current = _fingerprint(recording, WRITING_PATH)

    results = [
        _rename(recording, WRITING_PATH, "技術記事", fingerprint="00000000"),
        _remove(recording, WRITING_PATH, fingerprint="00000000"),
        _move(recording, WRITING_PATH, BASIC_PATH, fingerprint="00000000"),
        _disclose(recording, WRITING_PATH, "公開可", fingerprint="00000000"),
    ]

    for result in results:
        assert result.accepted is False
        assert result.rejection.constraint == "読んだときの指紋の一致"
        assert result.rejection.next_action.candidates == [current]
        assert "read_section" in result.rejection.reason
    assert source_digest(recording.source_dir) == before


def test_REQ_480_a_body_with_a_heading_line_is_refused_when_adding(recording) -> None:
    """足す節の本文が見出しの行を含むなら、書かずに、下位の節は操作を重ねて作ることを返す。"""
    before = source_digest(recording.source_dir)

    result = _add(recording, OUTSIDE, "登壇の記録", "中身\n\n#### 下位の節\n\n中身")

    assert result.accepted is False
    assert "add_section を重ねて" in result.rejection.reason
    assert source_digest(recording.source_dir) == before


def test_REQ_481_an_empty_reason_names_the_missing_field(recording) -> None:
    """5 つの操作は、理由が空なら、書かずに、欠けた欄の名前を返す。"""
    before = source_digest(recording.source_dir)

    results = [
        _rename(recording, WRITING_PATH, "技術記事", reason=" "),
        _add(recording, OUTSIDE, "登壇の記録", "中身", reason=""),
        _remove(recording, WRITING_PATH, reason=""),
        _move(recording, WRITING_PATH, BASIC_PATH, reason=""),
        _disclose(recording, WRITING_PATH, "公開可", reason=""),
    ]

    for result in results:
        assert result.accepted is False
        assert result.rejection.next_action.missing_fields == ["理由"]
    assert source_digest(recording.source_dir) == before


def test_REQ_482_a_structure_change_that_brings_a_new_violation_is_refused(recording) -> None:
    """書いた後に、書く前に無かった写しの鮮度以外の違反が出るなら、書かずにその違反を返す。"""
    before = source_digest(recording.source_dir)

    # 機能の裏づけと台帳の出典に使われている受託案件を消す。
    removed = _remove(recording, TERAMINA_ID)
    # 上位の見出しの名前を変え、受託案件を読み取り範囲の外に出す。
    renamed = _rename(recording, CAREER_ROOT, "職歴")

    for result in (removed, renamed):
        assert result.accepted is False
        assert result.rejection.constraint == "裏づけ節名の実在"
        assert "書く前に無かった整合の検査の違反" in result.rejection.reason
    assert "読み取り範囲の外" in renamed.rejection.reason
    assert source_digest(recording.source_dir) == before


def test_REQ_483_a_structure_change_names_the_copy_to_compare(recording) -> None:
    """通ったときに、書いたことで新しく出た写しの鮮度の違反を、読み比べる写しの名前を添えて返す。"""
    result = _disclose(recording, TERAMINA_ID, "公開可（社名は出さない）")

    assert result.accepted is True, result.rejection
    copies = result.recorded["読み比べる写し"]
    assert copies and all(item.startswith(LEDGER) for item in copies), copies
    assert any(note.startswith("写しの鮮度") for note in result.warnings)


def test_REQ_483_a_structure_change_without_a_copy_names_no_copy(recording) -> None:
    """どの写しも出典にしていない節では、読み比べる写しを返さない。"""
    result = _rename(recording, WRITING_PATH, "技術記事の連載")

    assert result.accepted is True, result.rejection
    assert result.recorded["読み比べる写し"] == []


# ---------------------------------------------------------------- 読めないブロックを作らない


def _assert_unreadable_block(result, constraint="必須の欄が欠けて読めないブロックを作らない") -> None:
    assert result.accepted is False
    assert result.rejection.constraint == constraint
    assert "読めないブロック" in result.rejection.reason
    assert result.rejection.next_action.missing_fields


def test_REQ_490_record_fact_that_makes_an_unreadable_block_is_refused(alt_settings) -> None:
    """事実の登記で、束ねるだけの見出しに欄が入り、必須の欄が欠けた受託案件になるなら書かない。"""
    before = source_digest(alt_settings.source_dir)

    result = _record(alt_settings, section=GROUP_PATH, fact="技術: SQL")

    _assert_unreadable_block(result)
    assert "2025 年から続いている案件" in result.rejection.reason
    assert "ID" in result.rejection.next_action.missing_fields
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_490_revise_section_that_drops_a_required_field_is_refused(alt_settings) -> None:
    """節の書き換えで、決めと公開記録の必須の欄を消す直しは書かない（整合の検査の違反にはならない欄）。"""
    before = source_digest(alt_settings.source_dir)
    decision = "売り方の決め > 2026-06-01 全体"
    # 機能の裏づけに指されていない公開記録を使う（指されている記録では、指す先の実在の違反が先に出る）。
    record = "外に出したもの > 分かれた数字を 1 か所に集める手順の寄稿"

    results = {}
    for path, label in ((decision, "- 根拠:"), (record, "- 種類:")):
        body = _service(alt_settings).read_section(path).body
        results[path] = _revise(
            alt_settings, path, "\n".join(line for line in body.splitlines() if not line.startswith(label))
        )

    _assert_unreadable_block(results[decision], "決めの必須欄")
    assert results[decision].rejection.next_action.missing_fields == ["根拠"]
    _assert_unreadable_block(results[record], "公開記録の必須欄")
    assert results[record].rejection.next_action.missing_fields == ["種類"]
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_490_rename_that_drops_the_entry_number_is_refused(recording) -> None:
    """見出しの変更で、台帳の案件番号（見出しの数字）が消えて読めなくなるなら書かない。"""
    before = source_digest(recording.source_dir)

    result = _rename(recording, LEDGER_ENTRY, "案件｜配送データの置き場づくり")

    _assert_unreadable_block(result)
    assert result.rejection.next_action.missing_fields == ["案件番号"]
    assert source_digest(recording.source_dir) == before


def test_REQ_490_add_that_makes_an_unreadable_block_is_refused(recording) -> None:
    """節の追加で、ID などの必須の欄を持たない受託案件ができるなら書かない。"""
    before = source_digest(recording.source_dir)

    result = _add(recording, FREELANCE_PATH, "新しい案件", "- 技術: SQL")

    _assert_unreadable_block(result)
    assert source_digest(recording.source_dir) == before


def test_REQ_490_move_that_makes_an_unreadable_block_is_refused(recording) -> None:
    """節の移動で、職歴の枠の必須の欄を持たない節が職歴の枠として読まれるなら書かない。"""
    before = source_digest(recording.source_dir)

    result = _move(recording, STUDY_PATH, CAREER_ROOT)

    _assert_unreadable_block(result)
    assert "社外の勉強会の運営" in result.rejection.reason
    assert source_digest(recording.source_dir) == before


@pytest.mark.parametrize("operation", ["remove", "disclose"])
def test_REQ_490_remove_and_disclosure_share_the_same_guard(recording, monkeypatch, operation) -> None:
    """節の削除と公開可否の変更も、書いた後の全文に読めないブロックが出るなら書かない。

    この 2 つは、正本の読み方では読めないブロックを作りえない（消すのは下位の節を持たない節だけで、
    公開可否は ID の欄を持つ節にしか書かない）。守りが同じ手順に通っていることを、書いた後の全文を
    決めの必須の欄が欠けた全文に差し替えて確かめる。
    """
    decision_file = "product/positioning.md"
    broken = (recording.source_dir / decision_file).read_text(encoding="utf-8").replace(
        "- 根拠: 2026 年前半", "- 備考: 2026 年前半", 1
    )
    target = WRITING_PATH
    if operation == "remove":
        target = "売り方の決め > 2026-09-10 見本の決め"
        monkeypatch.setattr(MarkdownRepository, "removed_text", lambda self, section: broken)
        before = source_digest(recording.source_dir)
        result = _remove(recording, target)
    else:
        target = "売り方の決め"
        monkeypatch.setattr(
            MarkdownRepository, "disclosure_text", lambda self, section, value, number=None: broken
        )
        monkeypatch.setattr(
            SectionService,
            "_find_one",
            lambda self, reference, op: (
                _service(recording)._resolve(target)[0][0].model_copy(update={"id": "decision-root"}),
                None,
            ),
        )
        before = source_digest(recording.source_dir)
        result = _disclose(recording, target, "公開可")

    _assert_unreadable_block(result, "決めの必須欄")
    assert result.rejection.next_action.missing_fields == ["根拠"]
    assert source_digest(recording.source_dir) == before


# ---------------------------------------------------------------- 書き換えの範囲を広げる


def test_REQ_485_every_source_file_can_be_revised(alt_settings) -> None:
    """機能の台帳・公開記録・パッケージ定義・売り方の決めの既にある行も、節の書き換えで直せる。"""
    edits = {
        "機能の台帳 > データの置き場をつくる": ("止まったときに気づける形", "止まったときにすぐ気づける形"),
        "外に出したもの > 刊行計画の進め方を話した勉強会の発表": ("2025-11-08", "2025-11-09"),
        "パッケージ定義 > 要件定義と進行管理": ("従業員 100 名前後", "従業員 80〜120 名"),
        "売り方の決め > 2026-06-01 全体": ("4 件のうち 3 件", "5 件のうち 3 件"),
    }
    for path, (old, new) in edits.items():
        body = _service(alt_settings).read_section(path).body
        assert old in body

        result = _revise(alt_settings, path, body.replace(old, new))

        assert result.accepted is True, (path, result.rejection)
        assert new in _service(alt_settings).read_section(path).body


def test_REQ_485_typed_rules_still_refuse_a_broken_row(alt_settings) -> None:
    """型の決まり（ID の形・語彙。仮説の状態と決めの適用範囲を含む）に反する直しは断られる。"""
    before = source_digest(alt_settings.source_dir)
    category = "機能の台帳 > 人と体制をつくる"
    record = "外に出したもの > 刊行計画の進め方を話した勉強会の発表"

    bad_id = _revise(
        alt_settings,
        category,
        _service(alt_settings).read_section(category).body.replace("| grow-inhouse-owner |", "| Grow Owner |"),
    )
    bad_kind = _revise(
        alt_settings,
        record,
        _service(alt_settings).read_section(record).body.replace("種類: 登壇", "種類: 無い種類"),
    )

    assert bad_id.accepted is False
    assert bad_id.rejection.constraint == "ID の形式"
    assert bad_kind.accepted is False
    assert bad_kind.rejection.constraint == "公開記録の種類の語彙"
    package = "パッケージ定義 > 要件定義と進行管理"
    # 適用される決め（最新の「全体」）ではなく、過去の決めの適用範囲を直す。
    decision = "売り方の決め > 2026-06-01 全体"
    bad_state = _revise(
        alt_settings,
        package,
        _service(alt_settings).read_section(package).body.replace("仮説の状態: 検証中", "仮説の状態: 無い状態"),
    )
    bad_scope = _revise(
        alt_settings,
        decision,
        _service(alt_settings).read_section(decision).body.replace("適用範囲: 全体", "適用範囲: 無い媒体"),
    )
    assert bad_state.accepted is False
    assert bad_state.rejection.constraint == "パッケージの仮説の状態の語彙"
    assert bad_scope.accepted is False
    assert bad_scope.rejection.constraint == "決めの適用範囲の語彙"
    assert source_digest(alt_settings.source_dir) == before


# ---------------------------------------------------------------- 断りと説明の文


# 正本のファイルを直接直す案内と、置き場で git を直接操作する案内に現れる言い回し。
DIRECT_EDIT_WORDS = (
    "人の手",
    "手で直",
    "直接直",
    "直接編集",
    "ファイルを開いて",
    "コミットしてから",
    "変更をコミット",
    "git commit",
    "git add",
    "git init",
    "git checkout",
    "git reset",
    "git stash",
)


def _texts_of(result) -> list[str]:
    rejection = result.rejection
    return [rejection.reason, rejection.next_action.example, *rejection.next_action.candidates]


def test_REQ_500_no_refusal_or_instruction_tells_to_edit_directly(recording) -> None:
    """断りの理由・次の一手・サーバーの説明に、直接直す案内も git を直接操作する案内も無い。"""
    import asyncio

    from accord.server.app import create_server

    server = create_server(recording)
    texts = [server.instructions or ""]
    texts += [tool.description or "" for tool in asyncio.run(server.list_tools())]

    body = _service(recording).read_section(TERAMINA_ID).body
    refusals = [
        _revise(recording, BASIC_PATH, NEW_BASIC + "\n\n## 新しい節"),
        _revise(recording, TERAMINA_ID, body.replace("- 公開可否: 公開可", "- 公開可否: 公開不可")),
        _revise(recording, BASIC_PATH, NEW_BASIC, fingerprint="00000000"),
        _revise(recording, BASIC_PATH, NEW_BASIC, reason=""),
        _record(recording, fact="公開可否: 公開不可"),
        _rename(recording, WRITING_PATH, ""),
        _add(recording, OUTSIDE, "登壇", "## 見出し"),
        _remove(recording, OUTSIDE),
        _move(recording, FREELANCE_PATH, TERAMINA_PATH),
        _disclose(recording, BASIC_PATH, "公開可"),
    ]
    # accord を通さない変更が残っているファイルへの書き込みの断り。
    career = recording.path_for("career")
    career.write_text(career.read_text(encoding="utf-8") + "\n書きかけ\n", encoding="utf-8")
    uncommitted = _record(recording)
    refusals.append(uncommitted)

    for result in refusals:
        assert result.accepted is False
        texts += _texts_of(result)
    assert "accord を通さない変更" in uncommitted.rejection.reason
    for text in texts:
        for word in DIRECT_EDIT_WORDS:
            assert word not in text, (word, text)


def test_REQ_513_each_structure_operation_makes_one_commit_of_the_file(recording) -> None:
    """5 つの操作は、変えたファイルだけを 1 件の git のコミットにし、説明に操作の名前の行を書く。"""
    steps = [
        lambda: _rename(recording, WRITING_PATH, "技術記事の連載"),
        lambda: _add(recording, OUTSIDE, "登壇の記録", "中身"),
        lambda: _remove(recording, f"{OUTSIDE} > 登壇の記録"),
        lambda: _move(recording, STUDY_PATH, BASIC_PATH),
        lambda: _disclose(recording, TERAMINA_ID, "公開可（社名は出さない）"),
    ]
    for step in steps:
        commits = _commits(recording)

        result = step()

        assert result.accepted is True, result.rejection
        assert _commits(recording) == commits + 1
        assert _last_commit_files(recording) == [CAREER]
        message = git(recording.source_dir, "log", "-1", "--format=%B")
        assert "Accord-Operation: " in message
    assert git(recording.source_dir, "status", "--porcelain").strip() == ""


# ---------------------------------------------------------------- 深さ 1 の節


def test_REQ_530_add_without_a_parent_puts_a_depth_one_section_at_the_end(recording) -> None:
    """親の節を渡さずにファイルを渡すと、そのファイルの末尾に深さ 1 の節を足す。"""
    commits = _commits(recording)

    result = _service(recording).add_section(None, "付録", "補足の資料を置く。", STRUCTURE_REASON, file=CAREER)

    assert result.accepted is True, result.rejection
    assert _career_text(recording).endswith("\n# 付録\n\n補足の資料を置く。\n")
    assert _paths(recording)[-1] == "付録"
    assert result.recorded["見出しの道筋"] == "付録"
    assert _commits(recording) == commits + 1


def test_REQ_530_add_without_a_parent_before_a_depth_one_section(recording) -> None:
    """前に置く深さ 1 の節を渡すと、その直前に深さ 1 の節を置く。深さ 1 でない節は断る。"""
    result = _service(recording).add_section(
        None, "まえがき", "この正本の読み方。", STRUCTURE_REASON, before=CAREER_TITLE, file=CAREER
    )

    assert result.accepted is True, result.rejection
    assert _paths(recording)[:2] == ["まえがき", CAREER_TITLE]
    before = source_digest(recording.source_dir)

    refused = _service(recording).add_section(
        None, "付録", "中身", STRUCTURE_REASON, before=BASIC_PATH, file=CAREER
    )
    missing = _service(recording).add_section(None, "付録", "中身", STRUCTURE_REASON)

    assert refused.accepted is False
    assert refused.rejection.next_action.candidates == ["まえがき", CAREER_TITLE]
    assert missing.accepted is False
    assert missing.rejection.next_action.missing_fields == ["parent", "file"]
    assert source_digest(recording.source_dir) == before


def test_REQ_531_move_without_a_parent_makes_a_depth_one_section(recording) -> None:
    """新しい親を渡さずに動かすと、下位の節ごと同じファイルの深さ 1 の節として末尾へ移し、下位の深さもずらす。"""
    bodies = {
        path: _service(recording).read_section(path).body for path in (OUTSIDE, STUDY_PATH, WRITING_PATH)
    }
    commits = _commits(recording)

    result = _move(recording, OUTSIDE, None)

    assert result.accepted is True, result.rejection
    text = _career_text(recording)
    assert "\n# 職歴の外の活動\n" in text
    assert "\n## 社外の勉強会の運営\n" in text
    assert "\n## 技術記事の執筆\n" in text
    for path, body in bodies.items():
        moved = path.replace(OUTSIDE, "職歴の外の活動", 1)
        assert _service(recording).read_section(moved).body == body
    assert _paths(recording)[-3:] == [
        "職歴の外の活動",
        "職歴の外の活動 > 社外の勉強会の運営",
        "職歴の外の活動 > 技術記事の執筆",
    ]
    assert _commits(recording) == commits + 1


def test_REQ_531_move_without_a_parent_before_a_depth_one_section_reorders(recording) -> None:
    """前に置く深さ 1 の節を渡すと、その直前へ動かす（深さ 1 の節どうしの並べ替え）。"""
    assert _service(recording).add_section(None, "付録", "中身", STRUCTURE_REASON, file=CAREER).accepted

    result = _move(recording, "付録", None, before=CAREER_TITLE)

    assert result.accepted is True, result.rejection
    assert _paths(recording)[:2] == ["付録", CAREER_TITLE]
    assert _service(recording).read_section("付録").body == "中身"


# ---------------------------------------------------------------- 正本に無いファイル


def test_REQ_533_an_unknown_file_is_refused_even_with_a_parent(recording) -> None:
    """節を足すか動かすときに渡されたファイルが正本のファイルでなければ、親があっても断り、正本のファイルの名前を返す。"""
    before = source_digest(recording.source_dir)

    added = _service(recording).add_section(OUTSIDE, "登壇の記録", "中身", STRUCTURE_REASON, file="missing.md")
    moved = _service(recording).move_section(
        WRITING_PATH, BASIC_PATH, _fingerprint(recording, WRITING_PATH), STRUCTURE_REASON, file="missing.md"
    )

    for result in (added, moved):
        assert result.accepted is False
        assert result.rejection.constraint == "正本のファイルの実在"
        assert result.rejection.next_action.candidates == recording.source_file_names()
    assert source_digest(recording.source_dir) == before


def test_REQ_533_a_known_file_scopes_the_parent(recording) -> None:
    """正本のファイルを渡せば、親の節と動かす節をそのファイルの中で探して書く。"""
    added = _service(recording).add_section(OUTSIDE, "登壇の記録", "中身", STRUCTURE_REASON, file=CAREER)
    moved = _service(recording).move_section(
        WRITING_PATH, BASIC_PATH, _fingerprint(recording, WRITING_PATH), STRUCTURE_REASON, file=CAREER
    )

    assert added.accepted is True, added.rejection
    assert moved.accepted is True, moved.rejection
    assert f"{BASIC_PATH} > 技術記事の執筆" in _paths(recording)


# ---------------------------------------------------------------- 公開可否の行が 2 行以上ある節


def _two_disclosure_lines(settings) -> str:
    """写しの受託案件 1 つに、値の違う公開可否の行をもう 1 行足してコミットし、足した後の全文を返す。"""
    career = settings.path_for("career")
    text = career.read_text(encoding="utf-8").replace(
        "- 公開可否: 公開可（業種と規模までにとどめ、製品名は出さない）\n",
        "- 公開可否: 公開可（業種と規模までにとどめ、製品名は出さない）\n- 公開可否: 公開不可（社内の報告書の数字）\n",
        1,
    )
    career.write_text(text, encoding="utf-8")
    git(settings.source_dir, "commit", "-q", "-am", "公開可否の行を 2 行にする")
    return text


def test_REQ_534_a_numbered_line_is_the_only_line_replaced(recording) -> None:
    """公開可否の行を 2 行以上持つ節で、番号を渡すとその行の値だけを置き換え、元に戻せる。"""
    text = _two_disclosure_lines(recording)

    changed = _service(recording).set_disclosure(
        "yukinoha-quality", "公開可（数字は丸める）", _fingerprint(recording, "yukinoha-quality"), "数字の扱いを決めた", 2
    )

    assert changed.accepted is True, changed.rejection
    assert changed.recorded["元の公開可否"] == "公開不可（社内の報告書の数字）"
    assert changed.recorded["行の番号"] == 2
    assert _career_text(recording) == text.replace(
        "- 公開可否: 公開不可（社内の報告書の数字）\n", "- 公開可否: 公開可（数字は丸める）\n", 1
    )

    restored = _service(recording).set_disclosure(
        "yukinoha-quality", "公開不可（社内の報告書の数字）", _fingerprint(recording, "yukinoha-quality"), "元に戻す", 2
    )

    assert restored.accepted is True, restored.rejection
    assert _career_text(recording) == text


@pytest.mark.parametrize("line", [None, 0, 3])
def test_REQ_535_a_missing_or_unknown_number_lists_the_lines(recording, line) -> None:
    """番号が渡されないか当たらなければ、書かずに、いまの公開可否の行を番号つきで候補に返す。"""
    _two_disclosure_lines(recording)
    before = source_digest(recording.source_dir)

    result = _service(recording).set_disclosure(
        "yukinoha-quality", "公開可", _fingerprint(recording, "yukinoha-quality"), STRUCTURE_REASON, line
    )

    assert result.accepted is False
    assert result.rejection.constraint == "公開可否の行の番号"
    assert result.rejection.next_action.candidates == [
        "1: - 公開可否: 公開可（業種と規模までにとどめ、製品名は出さない）",
        "2: - 公開可否: 公開不可（社内の報告書の数字）",
    ]
    assert source_digest(recording.source_dir) == before


# ---------------------------------------------------------------- 節の書き換えで公開可否の行を変える（申告）

YUKINOHA_DISCLOSURE = "公開可（業種と規模までにとどめ、製品名は出さない）"
MOVE_ITEM = "- 2 工場の記録の移し替え\n  - 公開可否: 公開可\n  - 移し替えの手順を工場ごとにそろえた。"
TALK_ITEM = "- 社内の勉強会での発表\n  - 公開可否: 公開不可（社内の話）\n  - 品質の見方を 2 回話した。"


def _itemized(settings) -> list[str]:
    """写しの受託案件 1 つの本文の末尾に、公開可否の行を持つ箇条書きの項目を 2 つ足してコミットし、値の並びを返す。"""
    body = _service(settings).read_section("yukinoha-quality").body
    career = settings.path_for("career")
    text = career.read_text(encoding="utf-8")
    career.write_text(text.replace(body, f"{body}\n{MOVE_ITEM}\n{TALK_ITEM}", 1), encoding="utf-8")
    git(settings.source_dir, "commit", "-q", "-am", "公開可否の行を持つ項目を足す")
    return [YUKINOHA_DISCLOSURE, "公開可", "公開不可（社内の話）"]


def _revise_yukinoha(settings, body, disclosures=None, reason="項目を直す"):
    current = _service(settings).read_section("yukinoha-quality")
    return _service(settings).revise_section("yukinoha-quality", body, current.fingerprint, reason, disclosures)


def test_REQ_536_items_with_disclosure_can_be_added_removed_and_reordered(recording) -> None:
    """申告が書いた後の並びと一致すれば、公開可否の行を持つ項目を足す・消す・並べ替えられ、前と後の行が残る。"""
    values = _itemized(recording)
    body = _service(recording).read_section("yukinoha-quality").body
    new_item = "- 品質の月報の引き継ぎ\n  - 公開可否: 公開可（月報の形だけ）"

    added = _revise_yukinoha(recording, f"{body}\n{new_item}", [*values, "公開可（月報の形だけ）"])
    assert added.accepted is True, added.rejection
    assert [entry["行"] for entry in added.recorded["変わる前の公開可否の行"]] == [
        f"- 公開可否: {value}" for value in values
    ]
    assert added.recorded["変わった後の公開可否の行"][-1]["行"] == "- 公開可否: 公開可（月報の形だけ）"
    message = git(recording.source_dir, "log", "-1", "--format=%B")
    assert "公開可否の行の変更" in message and "公開可（月報の形だけ）" in message

    removed = _revise_yukinoha(recording, body.replace(f"\n{TALK_ITEM}", ""), values[:2])
    assert removed.accepted is True, removed.rejection

    reordered_body = body.replace(f"{MOVE_ITEM}\n{TALK_ITEM}", f"{TALK_ITEM}\n{MOVE_ITEM}")
    restored_items = _revise_yukinoha(recording, reordered_body, [values[0], values[2], values[1]])
    assert restored_items.accepted is True, restored_items.rejection
    assert _service(recording).read_section("yukinoha-quality").body == reordered_body


def test_REQ_537_a_missing_or_wrong_declaration_is_refused(recording) -> None:
    """公開可否の行が変わるのに申告が無いか、申告が実際と違えば、書かずに、実際の並びと申告の欄の名前を返す。"""
    values = _itemized(recording)
    body = _service(recording).read_section("yukinoha-quality").body
    before = source_digest(recording.source_dir)
    changed = body.replace("公開不可（社内の話）", "公開可")

    missing = _revise_yukinoha(recording, changed)
    wrong = _revise_yukinoha(recording, changed, values)

    for result in (missing, wrong):
        assert result.accepted is False
        assert result.rejection.constraint == "公開可否の行の申告"
        assert result.rejection.next_action.missing_fields == ["disclosures"]
        assert result.rejection.next_action.candidates == [values[0], "公開可", "公開可"]
    assert source_digest(recording.source_dir) == before


def test_REQ_538_an_item_without_disclosure_is_not_added(recording) -> None:
    """公開可否の行を 2 行以上持つ節で、公開可否の行を持たない項目が増えるなら、書かずにその項目を返す。"""
    values = _itemized(recording)
    body = _service(recording).read_section("yukinoha-quality").body
    before = source_digest(recording.source_dir)

    result = _revise_yukinoha(recording, f"{body}\n- 公開可否を決めていない新しい項目", values)

    assert result.accepted is False
    assert result.rejection.constraint == "公開可否の行の無い項目を足さない"
    assert result.rejection.next_action.candidates == ["- 公開可否を決めていない新しい項目"]
    assert source_digest(recording.source_dir) == before


def test_REQ_538_a_single_disclosure_section_may_gain_plain_items(alt_settings) -> None:
    """公開可否の行が 1 行の節では、公開可否の行の無い項目を足しても断らない。"""
    body = _service(alt_settings).read_section(TERAMINA_ID).body

    result = _revise(alt_settings, TERAMINA_ID, f"{body}\n- 引き渡しの後の問い合わせ窓口をつくった")

    assert result.accepted is True, result.rejection


def test_REQ_539_lifting_a_private_section_by_revision_reports_it(alt_settings) -> None:
    """公開可否の行が変わる書き換えで節が「公開不可」から外れたら、材料に新しく出ることを返す。"""
    body = _service(alt_settings).read_section(AGENCY_ID).body
    old_line = next(line for line in body.splitlines() if line.startswith("- 公開可否:"))

    result = _revise(alt_settings, AGENCY_ID, body.replace(old_line, "- 公開可否: 公開可（社名は出さない）"))
    assert result.accepted is False
    result = _service(alt_settings).revise_section(
        AGENCY_ID,
        body.replace(old_line, "- 公開可否: 公開可（社名は出さない）"),
        _service(alt_settings).read_section(AGENCY_ID).fingerprint,
        "在籍先との約束の期限が過ぎた",
        ["公開可（社名は出さない）"],
    )

    assert result.accepted is True, result.rejection
    assert result.recorded["材料に新しく出る"] is True
    assert any("材料の取り出しに新しく出る" in note for note in result.warnings)
    assert MarkdownRepository(alt_settings).load().is_private(AGENCY_ID) is False


def test_REQ_536_each_disclosure_line_carries_its_item(recording) -> None:
    """変わる前と後の公開可否の行の 1 つずつに、属する項目の先頭の行（節の欄なら「節の欄」）を添え、コミットの説明にも載せる。"""
    values = _itemized(recording)
    body = _service(recording).read_section("yukinoha-quality").body

    result = _revise_yukinoha(recording, body.replace("公開不可（社内の話）", "公開可（社名は出さない）"), [
        values[0],
        values[1],
        "公開可（社名は出さない）",
    ])

    assert result.accepted is True, result.rejection
    assert result.recorded["変わる前の公開可否の行"] == [
        {"項目": "節の欄", "行": f"- 公開可否: {values[0]}"},
        {"項目": "- 2 工場の記録の移し替え", "行": "- 公開可否: 公開可"},
        {"項目": "- 社内の勉強会での発表", "行": "- 公開可否: 公開不可（社内の話）"},
    ]
    assert result.recorded["変わった後の公開可否の行"][2] == {
        "項目": "- 社内の勉強会での発表",
        "行": "- 公開可否: 公開可（社名は出さない）",
    }
    message = git(recording.source_dir, "log", "-1", "--format=%B")
    assert "［- 社内の勉強会での発表］- 公開可否: 公開不可（社内の話）" in message
    assert "［- 社内の勉強会での発表］- 公開可否: 公開可（社名は出さない）" in message
    assert f"［節の欄］- 公開可否: {values[0]}" in message


def test_REQ_537_moving_a_disclosure_line_to_the_next_item_needs_a_declaration(recording) -> None:
    """値の並びを変えずに公開可否の行を隣の項目へ移すと、申告なしでは断られ、申告つきなら通って前と後が記録に載る。"""
    body = _service(recording).read_section("yukinoha-quality").body
    first = "- 2 工場の記録の移し替え\n  - 公開可否: 公開可\n  - 公開可否: 公開可（工場の名前は出さない）\n  - 手順を工場ごとにそろえた。"
    second = "- 社内の勉強会での発表\n  - 公開可否: 公開不可（社内の話）\n  - 品質の見方を 2 回話した。"
    career = recording.path_for("career")
    career.write_text(
        career.read_text(encoding="utf-8").replace(body, f"{body}\n{first}\n{second}", 1), encoding="utf-8"
    )
    git(recording.source_dir, "commit", "-q", "-am", "公開可否の行を持つ項目を足す")
    values = [YUKINOHA_DISCLOSURE, "公開可", "公開可（工場の名前は出さない）", "公開不可（社内の話）"]
    current = _service(recording).read_section("yukinoha-quality").body
    moved = current.replace(
        "  - 公開可否: 公開可（工場の名前は出さない）\n  - 手順を工場ごとにそろえた。\n- 社内の勉強会での発表\n",
        "  - 手順を工場ごとにそろえた。\n- 社内の勉強会での発表\n  - 公開可否: 公開可（工場の名前は出さない）\n",
    )
    assert moved != current
    before = source_digest(recording.source_dir)

    refused = _revise_yukinoha(recording, moved)

    assert refused.accepted is False
    assert refused.rejection.constraint == "公開可否の行の申告"
    assert refused.rejection.next_action.candidates == values
    assert source_digest(recording.source_dir) == before

    accepted = _revise_yukinoha(recording, moved, values)

    assert accepted.accepted is True, accepted.rejection
    assert accepted.recorded["変わる前の公開可否の行"][2] == {
        "項目": "- 2 工場の記録の移し替え",
        "行": "- 公開可否: 公開可（工場の名前は出さない）",
    }
    assert accepted.recorded["変わった後の公開可否の行"][2] == {
        "項目": "- 社内の勉強会での発表",
        "行": "- 公開可否: 公開可（工場の名前は出さない）",
    }
    message = git(recording.source_dir, "log", "-1", "--format=%B")
    assert "［- 社内の勉強会での発表］- 公開可否: 公開可（工場の名前は出さない）" in message


# ---------------------------------------------------------------- 欄の値が型に合わないブロック

PACKAGE_PATH = "パッケージ定義 > 要件定義と進行管理"


def test_REQ_541_a_revision_with_an_unreadable_date_is_refused(alt_settings) -> None:
    """節の書き換えで、パッケージの「最終更新」を日付として読めない値にすると、例外で落ちずに書かずに断る。"""
    before = source_digest(alt_settings.source_dir)
    body = _service(alt_settings).read_section(PACKAGE_PATH).body
    line = next(item for item in body.splitlines() if item.startswith("- 最終更新:"))

    result = _revise(alt_settings, PACKAGE_PATH, body.replace(line, line + "（確かめ）"))

    assert result.accepted is False
    assert result.rejection.constraint == "欄の値を型に合わせる"
    assert result.rejection.next_action.missing_fields == ["最終更新"]
    assert "日付として読めない" in result.rejection.reason
    assert "product/packages.md" in result.rejection.reason
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_541_an_added_block_with_an_unreadable_date_is_refused(recording) -> None:
    """節を足す操作でも、足した節が欄の値の読めないブロックになるなら、書かずに断る（書き込みの操作に共通の守り）。"""
    before = source_digest(recording.source_dir)
    body = _service(recording).read_section(PACKAGE_PATH).body
    line = next(item for item in body.splitlines() if item.startswith("- 最終更新:"))
    new_body = body.replace("requirements-and-progress", "sample-new-package").replace(line, "- 最終更新: 来月")

    result = _service(recording).add_section("パッケージ定義", "新しいパッケージ", new_body, STRUCTURE_REASON)

    assert result.accepted is False
    assert result.rejection.constraint == "欄の値を型に合わせる"
    assert source_digest(recording.source_dir) == before
