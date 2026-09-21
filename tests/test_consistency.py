"""整合を検査する操作のテスト。

違反はすべて、同梱のサンプルの一時的な写しに仕込む。リポジトリのサンプルそのものは整ったままで、
その整った正本に検査を当てると違反が 0 件になることも、この文書で確かめる。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import accord
from accord.models.ontology import load_ontology
from accord.services.consistency import NOTE_LIMIT, ConsistencyService, limit_notes
from conftest import source_digest

# 写しに仕込む違反。サンプルの正本にある文字列を、そのまま置き換える形で書く。
STALE_UPDATED_ON = ("- 最終更新: 2026-09-12", "- 最終更新: 2026-08-01")
OUTDATED_CLAIM = (
    "- 宣言する束: requirements-and-progress",
    "- 宣言する束: data-platform-setup",
)
DANGLING_NOTE = (
    "- 未反映の注記: なし",
    "- 未反映の注記: nagisa-publishng — 週 1 回の確認の場を隔週に変えた",
)
PRIVATE_DISCLOSURE = (
    "- 公開可否: 公開可\n- 出所: 契約書と、月次の議事録（2025-04 以降）",
    "- 公開可否: 公開不可（先方の求めで、この案件は対外の文面に出さない）\n"
    "- 出所: 契約書と、月次の議事録（2025-04 以降）",
)
EXCEPTION_ENTRY = (
    "- 例外: なし",
    "- 例外: presentations/tsukikusa/profile.md — 媒体側の審査待ちで、次の更新まで旧い束のまま残す",
)

# 第 2 のサンプルが持つ、正本に実在するが読み取り範囲の外にある節と、その居場所。
OUT_OF_RANGE_ID = "study-group-host"
OUT_OF_RANGE_SECTION = "社外の勉強会の運営"
OUT_OF_RANGE_PARENT = "職歴の外の活動"
OUT_OF_RANGE_LEVEL = 3
OUT_OF_RANGE_RULE_KEY = "under_headings"

# 第 2 のサンプルの受託案件のブロックと、そこから 1 行消す必須の欄。
UNREADABLE_SECTION = "ナギサ書房 刊行計画の進行管理"
UNREADABLE_FIELD = "公開可否"
DROP_DISCLOSURE = (
    "- 公開可否: 公開可\n- 出所: 契約書と、月次の議事録（2025-04 以降）",
    "- 出所: 契約書と、月次の議事録（2025-04 以降）",
)

# 裏づけの節と台帳の出典の節を、読み取り範囲の外の節に向け直すための置き換え。
POINT_EVIDENCE_AT = ("| nagisa-publishing |", f"| {OUT_OF_RANGE_ID} |")
POINT_LEDGER_AT = (
    "- 出典の節: teramina-delivery",
    f"- 出典の節: {OUT_OF_RANGE_ID}",
)

# 欄を 1 つも持たない提示物を写しに置くときの、件数と中身。
FIELDLESS_PRESENTATION_COUNT = 40
FIELDLESS_PRESENTATION_BODY = "# 下書き\n\n本文だけで、欄を 1 つも持たない。\n"

EVIDENCE_SECTION_EXISTS = "裏づけ節名の実在"
ID_FORMAT_AND_UNIQUENESS = "ID の形式と一意性"
# 決めと提示物はパッケージを ID で指すので、ID と見出し（表示名）の両方を持つ。
HEADLINE_PACKAGE = "requirements-and-progress"
HEADLINE_PACKAGE_NAME = "要件定義と進行管理"
STALE_PACKAGE_FRESHNESS = "パッケージ定義の鮮度"
OUTDATED_OFFERING_CLAIM = "提示物の宣言と看板の一致"
NOTE_AND_SOURCE_SECTION = "注記と出典の節の実在・公開可否"


def _rewrite(path: Path, old: str, new: str, *, last: bool = False) -> None:
    """写しの 1 か所を書き換える。狙った文字列が無ければ、テストの前提が崩れたとして落とす。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しに「{old}」が無い: {path}"
    if last:
        head, _, tail = text.rpartition(old)
        text = head + new + tail
    else:
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def _report(settings, scope: str | None = None):
    """写しの正本に検査を当てる。"""
    return ConsistencyService(settings).inspect(scope)


def _flood_with_fieldless_presentations(settings) -> None:
    """欄を 1 つも持たない Markdown を、写しの提示物の置き場に並べる。

    同じ型の断りをたくさん出す入力を、実データを指さずに作るための仕掛けである。
    """
    directory = settings.path_for("presentations") / "tsukikusa"
    for index in range(FIELDLESS_PRESENTATION_COUNT):
        (directory / f"draft_{index:02d}.md").write_text(
            FIELDLESS_PRESENTATION_BODY, encoding="utf-8"
        )


def test_REQ_001_scope_is_named_whole_when_no_scope_is_given(settings) -> None:
    """範囲を渡さずに呼ぶと、返り値の範囲の名前が「全体」になる。"""
    report = _report(settings)

    assert report.scope == "全体"


def test_REQ_002_check_consistency_finds_nothing_in_the_shipped_samples(settings) -> None:
    """手を入れていない同梱のサンプルは整っているので、違反は 1 件も出ない。"""
    report = _report(settings)

    assert [violation.model_dump() for violation in report.violations] == []


def test_REQ_003_check_consistency_never_rewrites_the_source(settings) -> None:
    """検査を当てても、正本のファイルは 1 バイトも変わらない。"""
    before = source_digest(settings.source_dir)

    _report(settings)

    assert source_digest(settings.source_dir) == before


def test_REQ_011_check_consistency_detects_stale_package_definition(settings) -> None:
    """看板の束の定義が、その束を前面に出した決めより古いと検出する。"""
    _rewrite(settings.path_for("packages"), *STALE_UPDATED_ON)

    report = _report(settings)

    stale = [v for v in report.violations if v.constraint == STALE_PACKAGE_FRESHNESS]
    assert len(stale) == 1, [v.model_dump() for v in report.violations]
    violation = stale[0]
    assert violation.file == settings.files["packages"]
    assert HEADLINE_PACKAGE in violation.location
    # 決めの日付と定義の最終更新日の両方が、直し先として入っている。
    assert "2026-09-10" in violation.expected
    assert "2026-08-01" in violation.expected


def test_REQ_012_check_consistency_detects_outdated_offering_claim(settings) -> None:
    """旧い束を宣言した提示物を、ファイル名といまの看板つきで検出する。"""
    profile = settings.path_for("presentations") / "tsukikusa" / "profile.md"
    _rewrite(profile, *OUTDATED_CLAIM)

    report = _report(settings)

    outdated = [v for v in report.violations if v.constraint == OUTDATED_OFFERING_CLAIM]
    assert len(outdated) == 1, [v.model_dump() for v in report.violations]
    violation = outdated[0]
    assert violation.file == "presentations/tsukikusa/profile.md"
    assert violation.candidates == [HEADLINE_PACKAGE]
    assert HEADLINE_PACKAGE in violation.expected


def test_REQ_013_check_consistency_skips_claim_listed_as_exception(settings) -> None:
    """旧い束を宣言した提示物が 2 件でも、決めの例外欄に書いた 1 件は一覧に出ない。"""
    presentations = settings.path_for("presentations")
    _rewrite(presentations / "tsukikusa" / "profile.md", *OUTDATED_CLAIM)
    _rewrite(presentations / "nagiho" / "skill_sheet.md", *OUTDATED_CLAIM)
    # 例外は、いま効いている決め（正本の最後のブロック）の欄に書く。
    _rewrite(settings.path_for("positioning"), *EXCEPTION_ENTRY, last=True)

    report = _report(settings)

    outdated = [v for v in report.violations if v.constraint == OUTDATED_OFFERING_CLAIM]
    assert [v.file for v in outdated] == ["presentations/nagiho/skill_sheet.md"]


def test_REQ_019_check_consistency_detects_private_source_section_in_ledger(settings) -> None:
    """職務経歴書の台帳が公開不可の節を出典にしていると、案件の番号と節の名前つきで検出する。"""
    _rewrite(settings.path_for("engagements"), *PRIVATE_DISCLOSURE)

    report = _report(settings)

    ledger = [
        v
        for v in report.violations
        if v.constraint == NOTE_AND_SOURCE_SECTION and v.file == settings.files["resume_ledger"]
    ]
    assert len(ledger) == 1, [v.model_dump() for v in report.violations]
    violation = ledger[0]
    assert "案件番号 3" in violation.location
    assert "ナギサ書房 刊行計画の進行管理" in violation.expected
    assert "公開不可" in violation.expected
    # 差し替え先の候補は、公開可の節の ID だけが並ぶ。表示名は文の側に添えて出る。
    assert violation.candidates == ["teramina-delivery", "yukinoha-quality"]
    assert "テラミナ物流 配送データの置き場づくり" in violation.expected, violation.expected


def test_REQ_020_check_consistency_detects_dangling_pending_note(settings) -> None:
    """実在しない節を指す注記を、ファイル名と近い節の候補つきで検出する。"""
    skill_sheet = settings.path_for("presentations") / "nagiho" / "skill_sheet.md"
    _rewrite(skill_sheet, *DANGLING_NOTE)

    report = _report(settings)

    dangling = [
        v
        for v in report.violations
        if v.constraint == NOTE_AND_SOURCE_SECTION
        and v.file == "presentations/nagiho/skill_sheet.md"
    ]
    assert len(dangling) == 1, [v.model_dump() for v in report.violations]
    assert "nagisa-publishing" in dangling[0].candidates
    assert "ナギサ書房 刊行計画の進行管理" in dangling[0].expected, dangling[0].expected


def test_REQ_021_remaining_pending_notes_are_counted_in_a_note(settings) -> None:
    """注記が残っていること自体は、違反ではなく件数つきの断りとして報告に入る。"""
    skill_sheet = settings.path_for("presentations") / "nagiho" / "skill_sheet.md"
    _rewrite(skill_sheet, *DANGLING_NOTE)

    report = _report(settings)

    assert any("未反映の注記が 1 件残っている" in note for note in report.notes), report.notes


def test_REQ_024_check_consistency_names_a_package_section_that_lost_a_field(settings) -> None:
    """パッケージ定義の必須欄を 1 行消しても黙って飛ばさず、どの節のどの欄が無いかを断る。

    型にできなかった節そのもの（packages.md 側）を名指しする。決めの側にも「鮮度は判定できない」
    という別の断りが出るが、直すべきは packages.md の欠けた欄である。
    """
    _rewrite(
        settings.path_for("packages"),
        "- 想定買い手: 専任の進行役を置けない、従業員 100 名前後の会社の事業責任者\n",
        "",
    )

    report = _report(settings)

    listed = "\n".join(report.notes)
    assert settings.files["packages"] in listed, listed
    assert HEADLINE_PACKAGE_NAME in listed, listed
    assert "想定買い手" in listed, listed
    assert "revise_package" in listed, listed


def test_REQ_024_check_consistency_names_a_capability_row_that_lost_a_field(settings) -> None:
    """機能の台帳の表から裏づけの節の列を消しても黙って飛ばさず、どの分類の何行目かを断る。"""
    _rewrite(
        settings.path_for("capabilities"),
        "| requirements-forum | 要件を決める場をつくる | "
        "決まっていないことを一覧にし、決める人と決める日を置く | nagisa-publishing |",
        "| requirements-forum | 要件を決める場をつくる | "
        "決まっていないことを一覧にし、決める人と決める日を置く |",
    )

    report = _report(settings)

    listed = "\n".join(report.notes)
    assert settings.files["capabilities"] in listed, listed
    assert "決めて、進める" in listed, listed
    assert "裏づけの節" in listed, listed


def test_REQ_009_unknown_scope_name_returns_no_violation(settings) -> None:
    """範囲の名前が実在しないときは、違反を 1 件も返さない（拒否もしない）。"""
    report = _report(settings, "shiokaze")

    assert report.violations == []


def test_REQ_010_check_consistency_lists_existing_scopes_for_an_unknown_name(settings) -> None:
    """範囲の名前が実在しないときは、そのまま渡せる範囲の名前の一覧を断りに並べる。"""
    report = _report(settings, "shiokaze")

    listed = "\n".join(report.notes)
    for name in ["全体", *settings.channels, "presentations/tsukikusa/profile.md"]:
        assert name in listed, listed


def test_REQ_007_check_consistency_narrows_to_one_channel(settings) -> None:
    """媒体を範囲に渡すと、その媒体の提示物だけを見る。"""
    presentations = settings.path_for("presentations")
    _rewrite(presentations / "tsukikusa" / "profile.md", *OUTDATED_CLAIM)
    _rewrite(presentations / "nagiho" / "skill_sheet.md", *OUTDATED_CLAIM)

    report = _report(settings, "nagiho")

    assert report.scope == "nagiho"
    assert [v.file for v in report.violations] == ["presentations/nagiho/skill_sheet.md"]


def test_REQ_008_narrowed_scope_says_what_was_not_looked_at(settings) -> None:
    """範囲を絞って呼ぶと、見ていないものがあることが断りに出る。"""
    presentations = settings.path_for("presentations")
    _rewrite(presentations / "tsukikusa" / "profile.md", *OUTDATED_CLAIM)
    _rewrite(presentations / "nagiho" / "skill_sheet.md", *OUTDATED_CLAIM)

    report = _report(settings, "nagiho")

    assert any("見ていない" in note for note in report.notes), report.notes


def test_REQ_014_no_positioning_means_no_headline_violation(settings) -> None:
    """決めが 1 件も無いときは、鮮度も宣言の一致も違反にしない。"""
    positioning = settings.path_for("positioning")
    header, _, _ = positioning.read_text(encoding="utf-8").partition("## 2026-06-01 全体")
    positioning.write_text(header, encoding="utf-8")

    report = _report(settings)

    assert [v.constraint for v in report.violations] == []


def test_REQ_015_check_consistency_holds_judgement_when_no_positioning_is_recorded(
    settings,
) -> None:
    """決めが 1 件も無いときは、判定を保留したことと、先に決めを登記することを断りに返す。"""
    positioning = settings.path_for("positioning")
    header, _, _ = positioning.read_text(encoding="utf-8").partition("## 2026-06-01 全体")
    positioning.write_text(header, encoding="utf-8")

    report = _report(settings)

    listed = "\n".join(report.notes)
    assert "判定を保留" in listed
    assert "record_positioning" in listed
    # 登記の操作の入力の型（欄の名前と必須の別）が添えられている。
    for label in ["日付", "適用範囲", "前面に出す束", "根拠", "例外"]:
        assert label in listed, listed


def test_REQ_016_missing_headline_package_is_not_a_freshness_violation(settings) -> None:
    """看板の束がパッケージ定義に無いときは、鮮度を違反にしない。"""
    _rewrite(
        settings.path_for("positioning"),
        "- 前面に出す束: requirements-and-progress",
        "- 前面に出す束: requirements-and-progres",
        last=True,
    )

    report = _report(settings)

    assert [v for v in report.violations if v.constraint == STALE_PACKAGE_FRESHNESS] == []


def test_REQ_017_check_consistency_cannot_judge_freshness_without_the_headline_package(
    settings,
) -> None:
    """看板の束がパッケージ定義に無いときは、判定できないことと実在する束を断りに返す。"""
    _rewrite(
        settings.path_for("positioning"),
        "- 前面に出す束: requirements-and-progress",
        "- 前面に出す束: requirements-and-progres",
        last=True,
    )

    report = _report(settings)

    listed = "\n".join(report.notes)
    assert "鮮度は判定できない" in listed, listed
    assert HEADLINE_PACKAGE in listed, listed


def test_REQ_024_check_consistency_names_a_positioning_block_that_lost_a_field(settings) -> None:
    """必須の欄を欠いた決めのブロックは、黙って捨てず、どのブロックのどの欄が無いかを断る。"""
    positioning = settings.path_for("positioning")
    _rewrite(positioning, "- 日付: 2026-09-10\n", "", last=True)

    report = _report(settings)

    listed = "\n".join(report.notes)
    assert settings.files["positioning"] in listed, listed
    assert "2026-09-10 全体" in listed, listed
    assert "日付" in listed, listed
    assert "record_positioning" in listed, listed


def test_REQ_018_previous_positioning_is_the_headline_when_the_latest_block_lost_a_field(
    settings,
) -> None:
    """いまの決めが読めないと、1 つ前の決めを看板にして提示物の宣言を判定する。

    黙って捨てると、1 つ前の決めが「いまの看板」として通り、正しい提示物 2 件に対して
    逆向きの直し先（旧い束に書き換えよ）が返る。それ自体は検査に判断できないので、
    違反は 1 つ前の決めを基準に出て、読めなかったことは断りで組にして読む。
    """
    positioning = settings.path_for("positioning")
    _rewrite(positioning, "- 日付: 2026-09-10\n", "", last=True)

    report = _report(settings)

    outdated = [item for item in report.violations if item.constraint == OUTDATED_OFFERING_CLAIM]
    assert outdated, "1 つ前の決めを基準にした違反は出る（断りと組で読む）"
    assert all("2026-06-01" in item.expected for item in outdated)
    assert report.notes, "違反だけを返して、読めなかったブロックを黙っていない"


# ---------------------------------------------------------------- 足跡


def test_REQ_004_report_carries_the_config_path_and_version_and_source_location(settings) -> None:
    """検査の戻り値が、読んだ設定ファイルと、動いているソースの置き場と版を持ち帰る。

    版番号だけでは、入れ直していない古い環境と直したばかりのソースを見分けられない。
    どちらのコードが動いたかは、ソースの置き場で見分ける。
    """
    report = _report(settings)

    provenance = report.provenance
    assert provenance is not None, report.model_dump()
    assert provenance.config_path == str(settings.config_path.resolve())
    assert provenance.module_path == str(Path(accord.__file__).resolve().parent)
    assert provenance.version != ""

    # JSON にしたときも、設定の場所とソースの置き場が文字として読める。
    as_json = report.model_dump_json()
    assert as_json.count(provenance.config_path) >= 1
    assert as_json.count(provenance.module_path) >= 1


def test_REQ_005_reading_keys_say_default_when_the_config_has_no_reading_section(
    settings,
) -> None:
    """読み方の節を持たない設定では、適用した読み方が「既定」の 1 件になる。"""
    report = _report(settings)

    assert report.provenance is not None
    assert report.provenance.reading == ["既定"]


def test_REQ_006_reading_keys_list_every_key_written_in_the_config(alt_settings) -> None:
    """読み方の節を持つ設定では、設定に実際に書かれた鍵が、節と欄をつないだ形で並ぶ。"""
    report = _report(alt_settings)

    assert report.provenance is not None
    applied = report.provenance.reading
    assert len(applied) >= 10, applied
    for key in (
        "reading.career.heading_levels",
        "reading.presentations.directories",
        "reading.labels",
    ):
        assert key in applied, applied


# ---------------------------------------------------------------- 注記の束ね


def test_REQ_025_defects_of_the_same_kind_become_one_note_with_a_count(settings) -> None:
    """同じ正本の同じ欄が欠けた断りは、代表と件数を持つ 1 件の注記に束ねられる。"""
    _flood_with_fieldless_presentations(settings)

    report = _report(settings)

    bundled = [note for note in report.notes if "型にできず" in note]
    assert len(bundled) == 1, report.notes
    assert str(FIELDLESS_PRESENTATION_COUNT) in bundled[0], bundled[0]
    assert "ほかに 37 件" in bundled[0], bundled[0]


def test_REQ_026_notes_never_exceed_the_limit(settings) -> None:
    """束ねた後の断りの数は、上限を超えない。"""
    _flood_with_fieldless_presentations(settings)

    assert len(_report(settings).notes) <= NOTE_LIMIT


def test_REQ_027_notes_over_the_limit_end_with_the_cut_count() -> None:
    """上限より多い断りを渡すと、打ち切った件数が末尾の 1 行に畳まれる。"""
    folded = limit_notes([f"断り {index}" for index in range(NOTE_LIMIT + 1)])

    assert len(folded) == NOTE_LIMIT
    assert "ほかに 2 件" in folded[-1], folded[-1]


# ---------------------------------------------------------------- 範囲の外と、欠けた欄


def test_REQ_028_evidence_section_outside_the_reading_range_is_named_as_such(
    alt_settings,
) -> None:
    """正本に実在するが読み取り範囲の外にある節を裏づけに指すと、そう言い分けて直し方を出す。

    「無い」とだけ返すと、名前の合っている側を書き換える誘導になる。だから候補は出さず、
    深さと上位の見出しと、外れた絞りの鍵の名前を expected に書く。
    """
    _rewrite(alt_settings.path_for("capabilities"), *POINT_EVIDENCE_AT)

    report = _report(alt_settings)

    outside = [v for v in report.violations if v.constraint == EVIDENCE_SECTION_EXISTS]
    assert len(outside) == 1, [v.model_dump() for v in report.violations]
    violation = outside[0]
    assert "読み取り範囲の外" in violation.expected, violation.expected
    assert str(OUT_OF_RANGE_LEVEL) in violation.expected, violation.expected
    assert OUT_OF_RANGE_PARENT in violation.expected, violation.expected
    assert OUT_OF_RANGE_RULE_KEY in violation.expected, violation.expected
    assert violation.candidates == []


def test_REQ_029_evidence_section_in_an_unreadable_block_points_at_the_missing_field(
    alt_settings,
) -> None:
    """欄が欠けて読めていないブロックを裏づけに指すと、欠けた欄そのものを直し先に出す。"""
    _rewrite(alt_settings.path_for("career"), *DROP_DISCLOSURE)

    report = _report(alt_settings)

    evidence = [v for v in report.violations if v.constraint == EVIDENCE_SECTION_EXISTS]
    assert evidence, [v.model_dump() for v in report.violations]
    for violation in evidence:
        assert UNREADABLE_SECTION in violation.expected, violation.expected
        assert UNREADABLE_FIELD in violation.expected, violation.expected
        assert violation.candidates == []

    # 同じ検査の断りにも、そのブロックが欄の欠けで読めていないことが出ている。
    listed = "\n".join(report.notes)
    assert UNREADABLE_SECTION in listed, listed
    assert UNREADABLE_FIELD in listed, listed


def test_REQ_028_ledger_source_section_outside_the_reading_range_is_named_as_such(
    alt_settings,
) -> None:
    """台帳の出典の節でも、読み取り範囲の外にある見出しを同じ形で言い分ける。"""
    _rewrite(alt_settings.path_for("resume_ledger"), *POINT_LEDGER_AT)

    report = _report(alt_settings)

    ledger = [
        v
        for v in report.violations
        if v.constraint == NOTE_AND_SOURCE_SECTION
        and v.file == alt_settings.files["resume_ledger"]
    ]
    assert len(ledger) == 1, [v.model_dump() for v in report.violations]
    violation = ledger[0]
    assert "読み取り範囲の外" in violation.expected, violation.expected
    assert str(OUT_OF_RANGE_LEVEL) in violation.expected, violation.expected
    assert OUT_OF_RANGE_PARENT in violation.expected, violation.expected
    assert OUT_OF_RANGE_RULE_KEY in violation.expected, violation.expected
    assert violation.candidates == []


# ---------------------------------------------------------------- 公開記録と、提示物の URL


# 同梱のサンプルの公開記録と、その URL を載せている提示物の本文の書き方。
RECORD_ID = "meetup-talk-publishing"
RECORD_NAME = "刊行計画の進め方を話した勉強会の発表"
RECORD_URL = "https://example.com/events/report/spring-meetup/"
PROFILE_URL_LINE = f"進め方は勉強会でも話しています: {RECORD_URL}"

# 同じ場所を指しているが、書き方だけが違う 5 通り。どれも違反にならない。
SAME_PLACE_URLS = {
    "末尾にスラッシュを足す": "https://example.com/events/report/spring-meetup/",
    "https を http にする": "http://example.com/events/report/spring-meetup",
    "ホストを大文字にする": "https://EXAMPLE.COM/events/report/spring-meetup",
    "ホストの頭に www. を足す": "https://www.example.com/events/report/spring-meetup",
    "末尾にクエリを足す": "https://example.com/events/report/spring-meetup?utm_source=test",
}

# 経路の書き方だけが違う URL と、正本のどれとも合わない URL。
DIFFERENT_PATH_URL = "https://example.com/topic/spring-meetup"
UNKNOWN_URL = "https://example.com/notes/unknown-page"

# 公開記録を 1 件も持たないホスト。テストの中で、このホストの公開記録を足して振る舞いを変える。
OTHER_HOST_URL = "https://docs.example.com/handbook/progress"
OTHER_HOST_RECORD = """
## 進行管理の手引きの公開ページ

- ID: handbook-progress-page
- 種類: 記事
- 日付: 2026-02
- URL: https://docs.example.com/handbook/index
- 発行元か主催: 架空の手引きの置き場
- 役割: 著者
- 由来の節: なし
- 出所: 公開したときの控え
"""

ORIGIN_SECTION_EXISTS = "由来の節の実在"
PRESENTATION_URL_MATCHES = "提示物の URL と公開記録の一致"

# 設定から抜くと、公開記録を使わない正本（この段より前の設定と同じ形）になる 3 行の書き出し。
PUBLIC_RECORD_SETTING_LINES = (
    "public_records = ",
    "public_record_kinds = ",
    "public_record_roles = ",
)


def _profile(settings) -> Path:
    """写しの、URL を本文に載せている提示物の場所を返す。"""
    return settings.path_for("presentations") / "tsukikusa" / "profile.md"


def _url_violations(report) -> list:
    """提示物の URL の違反だけを取り出す。"""
    return [v for v in report.violations if v.constraint == PRESENTATION_URL_MATCHES]


def _without_public_records(settings):
    """写しの設定から、公開記録の置き場と語彙の 3 行を抜いて読み直す。"""
    from accord.vocabulary.settings import load_settings

    path: Path = settings.config_path
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.startswith(PUBLIC_RECORD_SETTING_LINES)]
    assert len(kept) == len(lines) - 3, "写しの設定から抜く 3 行が見つからない"
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return load_settings(path)


def test_REQ_023_origin_section_that_does_not_exist_is_listed_as_a_violation(settings) -> None:
    """公開記録の由来の節が実在しないと、公開記録の正本のどのブロックかを名指しで挙げる。"""
    before = len(_report(settings).violations)
    _rewrite(
        settings.path_for("public_records"),
        "- 由来の節: nagisa-publishing",
        "- 由来の節: nagisa-publishng",
    )

    report = _report(settings)

    assert len(report.violations) == before + 1, [v.model_dump() for v in report.violations]
    origin = [v for v in report.violations if v.constraint == ORIGIN_SECTION_EXISTS]
    assert len(origin) == 1, [v.model_dump() for v in report.violations]
    assert origin[0].file == settings.files["public_records"]
    assert RECORD_NAME in origin[0].location
    assert origin[0].candidates


def test_REQ_030_presentation_url_missing_from_the_source_is_a_violation_with_close_urls(
    settings,
) -> None:
    """正本のどの公開記録の URL にも無い URL は、登記する操作の名前と近い URL つきで挙げる。"""
    _rewrite(_profile(settings), RECORD_URL, UNKNOWN_URL)

    report = _report(settings)

    urls = _url_violations(report)
    assert len(urls) == 1, [v.model_dump() for v in report.violations]
    violation = urls[0]
    assert violation.file == "presentations/tsukikusa/profile.md"
    assert UNKNOWN_URL in violation.location
    assert "register_public_record" in violation.expected
    # 違反の文だけで登記に行けるよう、必ず渡す欄の名前を正本の必須の別から引いて確かめる
    public_record = next(t for t in load_ontology().types if t.name == "PublicRecord")
    required_labels = [field.label for field in public_record.fields if field.required]
    assert all(label in violation.expected for label in required_labels), violation.expected
    assert violation.candidates


def test_REQ_031_presentation_url_with_a_different_path_is_named_as_a_notation_difference(
    settings,
) -> None:
    """同じ場所を指すのに経路の書き方だけが違う URL は、相手の URL 1 件を添えてそう言い分ける。"""
    _rewrite(_profile(settings), RECORD_URL, DIFFERENT_PATH_URL)

    report = _report(settings)

    urls = _url_violations(report)
    assert len(urls) == 1, [v.model_dump() for v in report.violations]
    violation = urls[0]
    assert "経路の書き方が違う" in violation.expected
    assert RECORD_URL in violation.expected
    assert violation.candidates == [RECORD_URL]


@pytest.mark.parametrize("writing", sorted(SAME_PLACE_URLS))
def test_REQ_032_urls_that_differ_only_in_writing_are_treated_as_the_same(
    settings, writing
) -> None:
    """書き方だけが違う 5 通りは、どれも正本の URL と同じものとして扱う。"""
    _rewrite(_profile(settings), RECORD_URL, SAME_PLACE_URLS[writing])

    report = _report(settings)

    assert _url_violations(report) == [], writing


def test_REQ_033_public_record_without_url_is_never_compared(settings) -> None:
    """URL を持たない公開記録だけの正本では、提示物に URL を書いても照らす相手が 0 件になる。"""
    records = settings.path_for("public_records")
    text = records.read_text(encoding="utf-8")
    head, mark, tail = text.partition("## 分かれた数字を 1 か所に集める手順の寄稿")
    assert mark, "写しの公開記録に、URL を持たないブロックが無い"
    records.write_text(head.split("## ", 1)[0] + mark + tail, encoding="utf-8")
    _rewrite(_profile(settings), RECORD_URL, UNKNOWN_URL)

    report = _report(settings)

    # 照らす相手が 0 件なので、違反も、近い URL の候補も返らない。
    assert [violation.candidates for violation in _url_violations(report)] == []


def test_REQ_034_url_on_a_host_without_any_public_record_is_not_compared(settings) -> None:
    """正本のどの公開記録とも違うホストの URL は見ない。同じホストの公開記録を足すと見るようになる。"""
    _rewrite(_profile(settings), RECORD_URL, OTHER_HOST_URL)
    before = len(_url_violations(_report(settings)))
    assert before == 0

    records = settings.path_for("public_records")
    records.write_text(
        records.read_text(encoding="utf-8") + OTHER_HOST_RECORD, encoding="utf-8"
    )

    urls = _url_violations(_report(settings))
    assert len(urls) == 1, [violation.model_dump() for violation in urls]
    assert OTHER_HOST_URL in urls[0].location


def test_REQ_035_without_the_public_record_file_urls_are_not_compared(settings) -> None:
    """公開記録の置き場を書いていない設定では、正本に無い URL を書いても違反にしない。"""
    _rewrite(_profile(settings), RECORD_URL, UNKNOWN_URL)
    plain = _without_public_records(settings)

    report = _report(plain)

    assert _url_violations(report) == []


def test_REQ_036_without_the_public_record_file_a_note_names_the_keys_to_add(settings) -> None:
    """公開記録の置き場を書いていない設定では、照合させるために足す鍵の名前を断りに返す。"""
    _rewrite(_profile(settings), RECORD_URL, UNKNOWN_URL)
    plain = _without_public_records(settings)

    report = _report(plain)

    listed = "\n".join(report.notes)
    assert "公開記録の置き場が設定に無い" in listed, listed
    for key in ("public_records", "public_record_kinds", "public_record_roles"):
        assert key in listed, listed


def test_REQ_037_public_record_not_carried_by_any_presentation_is_not_a_violation(
    settings,
) -> None:
    """看板の裏づけの公開記録がどの提示物にも載っていないことは、違反にしない。"""
    _rewrite(_profile(settings), PROFILE_URL_LINE, "")

    report = _report(settings)

    assert _url_violations(report) == []
    assert [v.model_dump() for v in report.violations] == []


def test_REQ_038_public_record_not_carried_by_any_presentation_is_named_in_a_note(
    settings,
) -> None:
    """看板の裏づけの公開記録がどの提示物にも載っていないと、その名前が断りに出る。"""
    _rewrite(_profile(settings), PROFILE_URL_LINE, "")

    report = _report(settings)

    carried = [note for note in report.notes if "載っていない" in note]
    assert len(carried) == 1, report.notes
    assert RECORD_NAME in carried[0]
    assert "違反にはしない" in carried[0]


def test_REQ_022_evidence_section_can_point_at_a_public_record(settings) -> None:
    """機能の裏づけの節が公開記録の ID を指しているとき、実在する裏づけとして扱う。"""
    snapshot = ConsistencyService(settings).repository.load()
    pointing = [
        item for item in snapshot.capabilities if RECORD_ID in item.evidence_sections
    ]
    assert pointing, "写しの機能の台帳に、公開記録を裏づけにした行が無い"

    report = _report(settings)

    assert [v for v in report.violations if v.constraint == EVIDENCE_SECTION_EXISTS] == []


# ---------------------------------------------------------------- 設定の語の一覧との照合


PUBLIC_RECORD_VOCABULARY = "公開記録の種類と役割の語彙"
CAPABILITY_CATEGORY_ENUM = "機能の分類の列挙"

# 設定の語の一覧に無い語。どれも架空の語で、写しの正本に手で書いたことにする。
OUTSIDE_KIND = "ポッドキャスト"
OUTSIDE_ROLE = "司会"
OUTSIDE_CATEGORY = "話して伝える"

# 語の一覧の外の語を、正本に手で書いた状態にする置き換え。1 件目の公開記録の 2 つの欄を使う。
WRITE_OUTSIDE_KIND = ("- 種類: 登壇", f"- 種類: {OUTSIDE_KIND}")
WRITE_OUTSIDE_ROLE = ("- 役割: 登壇者", f"- 役割: {OUTSIDE_ROLE}")

# 語の一覧に無い見出しの節を、機能の台帳の末尾に足す。裏づけの節は正本に実在するものを書く。
OUTSIDE_CATEGORY_SECTION = f"""
## {OUTSIDE_CATEGORY}

| ID | 機能名 | 説明 | 裏づけの節 |
|---|---|---|---|
| talk-in-public | 進め方を人前で話す | 決め方と段取りを、催しの場で話して伝える | nagisa-publishing |
"""
OUTSIDE_CATEGORY_CAPABILITY = "進め方を人前で話す"


@pytest.mark.parametrize(
    ("label", "rewrite", "vocabulary_attribute", "written"),
    [
        ("種類", WRITE_OUTSIDE_KIND, "public_record_kinds", OUTSIDE_KIND),
        ("役割", WRITE_OUTSIDE_ROLE, "public_record_roles", OUTSIDE_ROLE),
    ],
)
def test_REQ_039_public_record_word_outside_the_vocabulary_is_listed_as_a_violation(
    settings, label: str, rewrite: tuple[str, str], vocabulary_attribute: str, written: str
) -> None:
    """公開記録の種類と役割に設定の語の一覧に無い語が書かれていると、違反 1 件として挙げる。"""
    before = len(_report(settings).violations)
    _rewrite(settings.path_for("public_records"), *rewrite)

    report = _report(settings)

    assert len(report.violations) == before + 1, [v.model_dump() for v in report.violations]
    listed = [v for v in report.violations if v.constraint == PUBLIC_RECORD_VOCABULARY]
    assert len(listed) == 1, [v.model_dump() for v in report.violations]
    violation = listed[0]
    assert violation.file == settings.files["public_records"]
    assert RECORD_NAME in violation.location, violation.location
    assert label in violation.location, violation.location
    assert violation.candidates == getattr(settings, vocabulary_attribute)
    assert written in violation.expected, violation.expected
    assert vocabulary_attribute in violation.expected, violation.expected


def test_REQ_040_capability_category_outside_the_vocabulary_is_listed_as_a_violation(
    settings,
) -> None:
    """機能の台帳に設定の語の一覧に無い見出しの節があると、その節の機能を違反 1 件として挙げる。"""
    before = len(_report(settings).violations)
    path = settings.path_for("capabilities")
    path.write_text(path.read_text(encoding="utf-8") + OUTSIDE_CATEGORY_SECTION, encoding="utf-8")

    report = _report(settings)

    assert len(report.violations) == before + 1, [v.model_dump() for v in report.violations]
    listed = [v for v in report.violations if v.constraint == CAPABILITY_CATEGORY_ENUM]
    assert len(listed) == 1, [v.model_dump() for v in report.violations]
    violation = listed[0]
    assert violation.file == settings.files["capabilities"]
    assert OUTSIDE_CATEGORY in violation.location, violation.location
    assert OUTSIDE_CATEGORY_CAPABILITY in violation.location, violation.location
    assert violation.candidates == settings.capability_categories
    assert OUTSIDE_CATEGORY in violation.expected, violation.expected
    assert "capability_categories" in violation.expected, violation.expected


def test_REQ_002_untouched_samples_have_no_vocabulary_violation(settings, alt_settings) -> None:
    """書き方の違う 2 つの同梱サンプルは、どちらも語彙の照合で違反が出ない（0 件のまま）。"""
    for target in (settings, alt_settings):
        report = _report(target)
        assert [v.model_dump() for v in report.violations] == [], target.config_path.name


# ---------------------------------------------------------------- 範囲の絞りと、束ねる機能


PACKAGE_CAPABILITY_MATCHES = "束ねる機能名の一致"

# 束ねる機能の 1 つを、機能の台帳に無い ID（末尾の 1 字を落とした綴り）に書き換える。
BUNDLED_CAPABILITY_MISSING = (
    "- 束ねる機能: requirements-forum / plan-from-decisions / handover-operations",
    "- 束ねる機能: requirements-foru / plan-from-decisions / handover-operations",
)
BUNDLED_CAPABILITY_ID = "requirements-forum"

# 看板の束が束ねる機能の裏づけになっていない公開記録の、種類の欄。
OFF_HEADLINE_RECORD_KIND = ("- 種類: 第三者の掲載", f"- 種類: {OUTSIDE_KIND}")

# 看板の裏づけになっていない公開記録 2 件に、同じ ID を付ける。
OFF_HEADLINE_DUPLICATE_ID = ("- ID: magazine-column-data", "- ID: case-article-quality")
OFF_HEADLINE_DUPLICATE_TARGET = "case-article-quality"

# 同じ提示物の本文に、正本に無い同じ URL を 2 行書く。
UNKNOWN_URL_TWICE = (
    PROFILE_URL_LINE,
    f"進め方は勉強会でも話しています: {UNKNOWN_URL}\n同じ場所をもう一度: {UNKNOWN_URL}",
)

# 提示物 1 件を範囲に渡すときの、ファイル名とその相対パス。
ONE_PRESENTATION_NAME = "skill_sheet.md"
ONE_PRESENTATION_PATH = "presentations/nagiho/skill_sheet.md"


def test_REQ_041_bundled_capability_missing_from_the_ledger_is_a_violation(settings) -> None:
    """束ねる機能の ID が台帳に無いと、パッケージ定義のその節を名指しし、近い ID を候補に出す。"""
    _rewrite(settings.path_for("packages"), *BUNDLED_CAPABILITY_MISSING)

    report = _report(settings)

    bundled = [v for v in report.violations if v.constraint == PACKAGE_CAPABILITY_MATCHES]
    assert len(bundled) == 1, [v.model_dump() for v in report.violations]
    violation = bundled[0]
    assert violation.file == settings.files["packages"]
    assert HEADLINE_PACKAGE in violation.location, violation.location
    assert BUNDLED_CAPABILITY_ID in violation.candidates, violation.candidates


def test_REQ_042_check_consistency_narrows_to_one_presentation(settings) -> None:
    """提示物のファイル名を範囲に渡すと、その提示物だけを見る。

    ほかの提示物にも旧い束の宣言を置き、それが違反の一覧に出ないことで確かめる。
    """
    presentations = settings.path_for("presentations")
    _rewrite(presentations / "tsukikusa" / "profile.md", *OUTDATED_CLAIM)
    _rewrite(presentations / "nagiho" / ONE_PRESENTATION_NAME, *OUTDATED_CLAIM)

    report = _report(settings, ONE_PRESENTATION_NAME)

    assert report.scope == ONE_PRESENTATION_NAME
    assert [v.file for v in report.violations] == [ONE_PRESENTATION_PATH]


def test_REQ_043_channel_scope_checks_only_the_public_records_behind_the_headline(
    settings,
) -> None:
    """媒体を範囲に渡すと、その媒体の看板が束ねる機能の裏づけの公開記録だけを見る。

    看板の裏づけになっていない公開記録に語の一覧の外の語を置き、全体では違反に出て、
    媒体の範囲では出ないことで確かめる。
    """
    _rewrite(settings.path_for("public_records"), *OFF_HEADLINE_RECORD_KIND)

    whole = _report(settings)
    narrowed = _report(settings, "tsukikusa")

    outside = [v for v in whole.violations if v.constraint == PUBLIC_RECORD_VOCABULARY]
    assert len(outside) == 1, [v.model_dump() for v in whole.violations]
    assert [v.model_dump() for v in narrowed.violations] == []


def test_REQ_044_narrowed_scope_still_checks_ids_across_the_whole_source(settings) -> None:
    """範囲を絞っても、ID の形式と一意性は正本全体で見る。

    範囲の外にある公開記録 2 件に同じ ID を付け、媒体の範囲でも違反に出ることで確かめる。
    """
    _rewrite(settings.path_for("public_records"), *OFF_HEADLINE_DUPLICATE_ID)

    report = _report(settings, "tsukikusa")

    overlapping = [v for v in report.violations if v.constraint == ID_FORMAT_AND_UNIQUENESS]
    assert len(overlapping) == 2, [v.model_dump() for v in report.violations]
    for violation in overlapping:
        assert OFF_HEADLINE_DUPLICATE_TARGET in violation.expected, violation.expected


def test_REQ_045_same_unknown_url_written_twice_is_one_violation(settings) -> None:
    """同じ提示物が正本に無い同じ URL を 2 回載せても、その URL の違反は 1 件だけになる。"""
    _rewrite(_profile(settings), *UNKNOWN_URL_TWICE)

    report = _report(settings)

    urls = _url_violations(report)
    assert len(urls) == 1, [violation.model_dump() for violation in urls]
    assert UNKNOWN_URL in urls[0].location
