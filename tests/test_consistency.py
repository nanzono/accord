"""整合を検査する操作のテスト。

違反はすべて、同梱のサンプルの一時的な写しに仕込む。リポジトリのサンプルそのものは整ったままで、
その整った正本に検査を当てると違反が 0 件になることも、この文書で確かめる。
"""

from __future__ import annotations

from pathlib import Path

from accord.services.consistency import ConsistencyService
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
