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

from accord.repository.sections import section_fingerprint
from accord.services.sections import SectionService
from accord.vocabulary.settings import load_settings
from conftest import add_config_lines, source_digest

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
    engagements = settings.path_for("engagements")
    with engagements.open("a", encoding="utf-8") as handle:
        handle.write("\n# 稼働条件\n\n受託案件のファイルに置いた、同じ見出しの節。\n")

    result = _service(settings).read_section("稼働条件")

    assert result.body is None
    assert result.candidates == ["career.md :: 稼働条件", "engagements.md :: 稼働条件"]
    again = _service(settings).read_section(result.candidates[1])
    assert again.body == "受託案件のファイルに置いた、同じ見出しの節。"


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

    removed = _revise(alt_settings, TERAMINA_ID, body.replace(f"- 識別子: {TERAMINA_ID}\n", ""))
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


def test_REQ_451_a_section_of_a_typed_source_is_refused_with_its_operation(alt_settings) -> None:
    """経歴の正本・台帳・見せ方の正本のどれにも無い節は、書かずに、その正本を書く操作を候補に返す。"""
    before = source_digest(alt_settings.source_dir)
    package = _service(alt_settings).list_sections("product/packages.md").sections[1]
    positioning = _service(alt_settings).list_sections("positioning.md").sections[1]

    on_package = _revise(alt_settings, package.heading_path, "中身")
    on_positioning = _revise(alt_settings, positioning.heading_path, "中身")

    assert on_package.accepted is False
    assert on_package.rejection.next_action.candidates == ["revise_package"]
    assert on_positioning.rejection.next_action.candidates == ["record_positioning"]
    assert source_digest(alt_settings.source_dir) == before


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


def _with_export(settings, value: str):
    return add_config_lines(settings.config_path, "source", [f'export_path = "{value}"'])


def test_REQ_452_export_writes_every_source_file_under_its_name(alt_settings, tmp_path) -> None:
    """正本の各ファイルの中身を、ファイルの名前の見出しを付けて、書き出し先の 1 つのファイルに書く。"""
    settings = _with_export(alt_settings, "../exported/all.md")

    result = _service(settings).export_source()

    assert result.written is True
    text = settings.export_path.read_text(encoding="utf-8")
    for name in settings.source_file_names():
        assert f"# {name}\n" in text
        first = (settings.source_dir / name).read_text(encoding="utf-8").strip().splitlines()[-1]
        assert first in text


def test_REQ_453_an_export_path_inside_the_source_stops_the_start(alt_settings) -> None:
    """書き出し先が正本の置き場の中なら、書き出し先の鍵の名前を添えて起動をやめる。"""
    config = alt_settings.config_path
    text = config.read_text(encoding="utf-8").replace(
        "[source]\n", '[source]\nexport_path = "source_alt/export.md"\n', 1
    )
    config.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="export_path"):
        load_settings(config)


def test_REQ_454_without_an_export_path_the_export_is_refused(alt_settings) -> None:
    """設定に書き出し先が無ければ、書かずに、設定に足す鍵の名前を断りに返す。"""
    result = _service(alt_settings).export_source()

    assert result.written is False
    assert "export_path" in result.rejection.reason
    assert result.rejection.next_action.missing_fields == ["export_path"]


def test_REQ_455_export_returns_the_name_and_size_without_the_path(alt_settings) -> None:
    """書き出しが通ると、書いたファイルの名前と字数を返し、書き出し先の絶対パスを返さない。"""
    settings = _with_export(alt_settings, "../exported/all.md")

    result = _service(settings).export_source()

    assert result.file_name == "all.md"
    assert result.chars == len(settings.export_path.read_text(encoding="utf-8"))
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert str(settings.export_path.parent) not in dumped
    assert str(Path(settings.export_path).parent.parent) not in dumped


def test_REQ_468_removing_or_changing_the_disclosure_field_is_refused(alt_settings) -> None:
    """新しい本文で公開可否の欄が消えるか値が変わるなら、書かずに、元の値のまま残すことを返す。"""
    before = source_digest(alt_settings.source_dir)
    body = _service(alt_settings).read_section(TERAMINA_ID).body

    removed = _revise(alt_settings, TERAMINA_ID, body.replace("- 公開可否: 公開可\n", ""))
    changed = _revise(alt_settings, TERAMINA_ID, body.replace("- 公開可否: 公開可", "- 公開可否: 公開不可"))

    for result in (removed, changed):
        assert result.accepted is False
        assert result.rejection.constraint == "公開可否の欄を元の値のまま残す"
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_469_a_fact_written_as_a_field_is_refused(alt_settings) -> None:
    """足す行が ID か公開可否の欄として読まれて値が変わるなら、書かずに、欄の書き方で書かないことを返す。"""
    before = source_digest(alt_settings.source_dir)

    disclosure = _record(alt_settings, fact="公開可否: 公開不可")
    identifier = _record(alt_settings, fact="識別子: teramina-routes")

    for result in (disclosure, identifier):
        assert result.accepted is False
        assert result.rejection.constraint == "事実の文を欄の書き方で書かない"
    assert source_digest(alt_settings.source_dir) == before
