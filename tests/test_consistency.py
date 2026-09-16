"""整合を検査する操作のテスト。

違反はすべて、同梱のサンプルの一時的な写しに仕込む。リポジトリのサンプルそのものは整ったままで、
その整った正本に検査を当てると違反が 0 件になることも、この文書で確かめる。
"""

from __future__ import annotations

from pathlib import Path

import accord
from accord.services.consistency import NOTE_LIMIT, ConsistencyService, limit_notes
from conftest import source_digest

# 写しに仕込む違反。サンプルの正本にある文字列を、そのまま置き換える形で書く。
STALE_UPDATED_ON = ("- 最終更新: 2026-09-12", "- 最終更新: 2026-08-01")
OUTDATED_CLAIM = ("- 宣言する束: 要件定義と進行管理", "- 宣言する束: データの置き場づくり")
DANGLING_NOTE = (
    "- 未反映の注記: なし",
    "- 未反映の注記: ナギサ書房 刊行計画のしんこう管理 — 週 1 回の確認の場を隔週に変えた",
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

# 第 2 のサンプルが持つ、正本に実在するが読み取り範囲の外にある見出しと、その居場所。
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

# 裏づけの節と台帳の出典の節を、別の見出しに向け直すための置き換え。
POINT_EVIDENCE_AT = ("| ナギサ書房 刊行計画の進行管理 |", f"| {OUT_OF_RANGE_SECTION} |")
POINT_LEDGER_AT = (
    "- 出典の節: テラミナ物流 配送データの置き場づくり",
    f"- 出典の節: {OUT_OF_RANGE_SECTION}",
)

# 欄を 1 つも持たない提示物を写しに置くときの、件数と中身。
FIELDLESS_PRESENTATION_COUNT = 40
FIELDLESS_PRESENTATION_BODY = "# 下書き\n\n本文だけで、欄を 1 つも持たない。\n"

EVIDENCE_SECTION_EXISTS = "裏づけ節名の実在"
HEADLINE_PACKAGE = "要件定義と進行管理"
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


def test_check_consistency_finds_nothing_in_the_shipped_samples(settings) -> None:
    """同梱のサンプルは整っているので、違反は 1 件も出ない。正本も 1 バイトも変わらない。"""
    before = source_digest(settings.source_dir)

    report = _report(settings)

    assert report.scope == "全体"
    assert [violation.model_dump() for violation in report.violations] == []
    assert source_digest(settings.source_dir) == before


def test_check_consistency_detects_stale_package_definition(settings) -> None:
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


def test_check_consistency_detects_outdated_offering_claim(settings) -> None:
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


def test_check_consistency_skips_claim_listed_as_exception(settings) -> None:
    """旧い束を宣言した提示物が 2 件でも、決めの例外欄に書いた 1 件は一覧に出ない。"""
    presentations = settings.path_for("presentations")
    _rewrite(presentations / "tsukikusa" / "profile.md", *OUTDATED_CLAIM)
    _rewrite(presentations / "nagiho" / "skill_sheet.md", *OUTDATED_CLAIM)
    # 例外は、いま効いている決め（正本の最後のブロック）の欄に書く。
    _rewrite(settings.path_for("positioning"), *EXCEPTION_ENTRY, last=True)

    report = _report(settings)

    outdated = [v for v in report.violations if v.constraint == OUTDATED_OFFERING_CLAIM]
    assert [v.file for v in outdated] == ["presentations/nagiho/skill_sheet.md"]


def test_check_consistency_detects_private_source_section_in_ledger(settings) -> None:
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
    # 差し替え先の候補は、公開可の節だけが並ぶ。
    assert violation.candidates == [
        "テラミナ物流 配送データの置き場づくり",
        "ユキノハ化成 品質記録の集約と見える化",
    ]


def test_check_consistency_detects_dangling_pending_note(settings) -> None:
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
    assert "ナギサ書房 刊行計画の進行管理" in dangling[0].candidates

    # 注記が残っていること自体は、違反ではなく断りとして報告に入る。
    assert any("未反映の注記が 1 件残っている" in note for note in report.notes), report.notes


def test_check_consistency_names_a_package_section_that_lost_a_field(settings) -> None:
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
    assert HEADLINE_PACKAGE in listed, listed
    assert "想定買い手" in listed, listed
    assert "revise_package" in listed, listed


def test_check_consistency_names_a_capability_row_that_lost_a_field(settings) -> None:
    """機能の台帳の表から裏づけの節の列を消しても黙って飛ばさず、どの分類の何行目かを断る。"""
    _rewrite(
        settings.path_for("capabilities"),
        "| 要件を決める場をつくる | 決まっていないことを一覧にし、決める人と決める日を置く | "
        "ナギサ書房 刊行計画の進行管理 |",
        "| 要件を決める場をつくる | 決まっていないことを一覧にし、決める人と決める日を置く |",
    )

    report = _report(settings)

    listed = "\n".join(report.notes)
    assert settings.files["capabilities"] in listed, listed
    assert "決めて、進める" in listed, listed
    assert "裏づけの節" in listed, listed


def test_check_consistency_lists_existing_scopes_for_an_unknown_name(settings) -> None:
    """範囲の名前が実在しないときは、違反ではなく実在する範囲の一覧を返す。"""
    report = _report(settings, "shiokaze")

    assert report.violations == []
    listed = "\n".join(report.notes)
    for name in ["全体", *settings.channels, "presentations/tsukikusa/profile.md"]:
        assert name in listed, listed


def test_check_consistency_narrows_to_one_channel(settings) -> None:
    """媒体を範囲に渡すと、その媒体の提示物だけを見て、見ていないものを断る。"""
    presentations = settings.path_for("presentations")
    _rewrite(presentations / "tsukikusa" / "profile.md", *OUTDATED_CLAIM)
    _rewrite(presentations / "nagiho" / "skill_sheet.md", *OUTDATED_CLAIM)

    report = _report(settings, "nagiho")

    assert report.scope == "nagiho"
    assert [v.file for v in report.violations] == ["presentations/nagiho/skill_sheet.md"]
    assert any("見ていない" in note for note in report.notes), report.notes


def test_check_consistency_holds_judgement_when_no_positioning_is_recorded(settings) -> None:
    """決めが 1 件も無いときは、鮮度と宣言の一致を保留し、先に決めを登記すると返す。"""
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
    assert [v.constraint for v in report.violations] == []


def test_check_consistency_cannot_judge_freshness_without_the_headline_package(settings) -> None:
    """看板の束がパッケージ定義に無いときは、鮮度を違反にせず、判定できない断りを返す。"""
    _rewrite(
        settings.path_for("positioning"),
        "- 前面に出す束: 要件定義と進行管理",
        "- 前面に出す束: 要件定義と進こう管理",
        last=True,
    )

    report = _report(settings)

    assert [v for v in report.violations if v.constraint == STALE_PACKAGE_FRESHNESS] == []
    listed = "\n".join(report.notes)
    assert "鮮度は判定できない" in listed, listed
    assert HEADLINE_PACKAGE in listed, listed


def test_check_consistency_names_a_positioning_block_that_lost_a_field(settings) -> None:
    """必須の欄を欠いた決めのブロックは、黙って捨てず、どのブロックのどの欄が無いかを断る。

    黙って捨てると、1 つ前の決めが「いまの看板」として通り、正しい提示物 2 件に対して
    逆向きの直し先（旧い束に書き換えよ）が返る。
    """
    positioning = settings.path_for("positioning")
    _rewrite(positioning, "- 日付: 2026-09-10\n", "", last=True)

    report = _report(settings)

    listed = "\n".join(report.notes)
    assert settings.files["positioning"] in listed, listed
    assert "2026-09-10 全体" in listed, listed
    assert "日付" in listed, listed
    assert "record_positioning" in listed, listed

    # 読めなかったぶん、看板は 1 つ前の決めになる。それ自体は検査に判断できないので、
    # 違反は 1 つ前の決めを基準に出る。断りが無いとこれが黙って起きる、というのが直した点である。
    outdated = [item for item in report.violations if item.constraint == OUTDATED_OFFERING_CLAIM]
    assert outdated, "1 つ前の決めを基準にした違反は出る（断りと組で読む）"
    assert all("2026-06-01" in item.expected for item in outdated)
    assert report.notes, "違反だけを返して、読めなかったブロックを黙っていない"


# ---------------------------------------------------------------- 足跡


def test_report_carries_the_config_path_and_version_and_source_location(settings) -> None:
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


def test_reading_keys_say_default_when_the_config_has_no_reading_section(settings) -> None:
    """読み方の節を持たない設定では、適用した読み方が「既定」の 1 件になる。"""
    report = _report(settings)

    assert report.provenance is not None
    assert report.provenance.reading == ["既定"]


def test_reading_keys_list_every_key_written_in_the_config(alt_settings) -> None:
    """読み方の節を持つ設定では、設定に実際に書かれた鍵が道の形で並ぶ。"""
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


def test_defects_of_the_same_kind_become_one_note_with_a_count(settings) -> None:
    """同じ正本の同じ欄が欠けた断りは、代表と件数を持つ 1 件の注記に束ねられる。"""
    _flood_with_fieldless_presentations(settings)

    report = _report(settings)

    bundled = [note for note in report.notes if "型にできず" in note]
    assert len(bundled) == 1, report.notes
    assert str(FIELDLESS_PRESENTATION_COUNT) in bundled[0], bundled[0]
    assert "ほかに 37 件" in bundled[0], bundled[0]


def test_notes_never_exceed_the_limit(settings) -> None:
    """断りの数は上限を超えず、打ち切った分は件数の 1 行に畳まれる。"""
    _flood_with_fieldless_presentations(settings)

    assert len(_report(settings).notes) <= NOTE_LIMIT

    # 打ち切りそのものは、上限より 1 件多い並びを渡して見る。
    folded = limit_notes([f"断り {index}" for index in range(NOTE_LIMIT + 1)])
    assert len(folded) == NOTE_LIMIT
    assert "ほかに 2 件" in folded[-1], folded[-1]


# ---------------------------------------------------------------- 範囲の外と、欠けた欄


def test_evidence_section_outside_the_reading_range_is_named_as_such(alt_settings) -> None:
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


def test_evidence_section_in_an_unreadable_block_points_at_the_missing_field(
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


def test_ledger_source_section_outside_the_reading_range_is_named_as_such(alt_settings) -> None:
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
