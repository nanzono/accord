"""書き方の違う第 2 の正本の上で、第 1 版と同じ結果が出ることのテスト。

`samples/source_alt/` は、`samples/source/` と同じ人・同じ案件・同じ中身を、違う書き方で
書いた正本である。見出しの深さも、欄を箇条書きで書くか表で書くかも、欄のラベルの言い方も違う。
読み方の差は設定ファイル `samples/accord_alt.toml` の `[reading]` の節だけが吸収する。

ここで見るのは 2 つ。8 種と見せ方の正本が断り無しで読めることと、制約 7 つの判定が
第 1 版と同じ（受け付けない／検出する／飛ばす）になることである。
読み方の設定が書き方の違いを吸収することを、整合の検査の要件の番号で確かめる。
違反はすべて、写しに仕込む。同梱のサンプルそのものは整ったままにする。
"""

from __future__ import annotations

from pathlib import Path

from accord.models.results import (
    CapabilityDraft,
    MaterialRequest,
    PackageDraft,
    PositioningDraft,
)
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.consistency import ConsistencyService
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.services.positioning import PositioningService
from conftest import source_digest

# 決めも提示物もパッケージを ID で指すので、ID と見出し（表示名）の両方を持つ。
CHANNEL = "tsukikusa"
HEADLINE_PACKAGE = "requirements-and-progress"
HEADLINE_PACKAGE_NAME = "要件定義と進行管理"
OTHER_PACKAGE = "data-platform-setup"
KNOWN_CAPABILITY = "requirements-forum"
BUYER = "専任の進行役を置けない、従業員 100 名前後の会社の事業責任者"

# 第 2 の正本に仕込む違反。書き方が違うので、置き換える文字列も第 1 版とは違う。
STALE_UPDATED_ON = ("- 最終更新: 2026-09-12", "- 最終更新: 2026-08-01")
OUTDATED_CLAIM = (f"- 宣言する束: {HEADLINE_PACKAGE}", f"- 宣言する束: {OTHER_PACKAGE}")
EXCEPTION_ENTRY = (
    "- 例外: なし",
    "- 例外: tsukikusa/profile.md — 媒体側の審査待ちで、次の更新まで旧い束のまま残す",
)
DANGLING_NOTE = (
    "- 未反映の注記: なし",
    "- 未反映の注記: nagisa-publishng — 週 1 回の確認の場を隔週に変えた",
)
# 公開不可にする受託案件（深さ 5 の節）と、その節の本文にしか出てこない言い回し。
PRIVATE_SECTION_ID = "nagisa-publishing"
PRIVATE_SECTION = "ナギサ書房 刊行計画の進行管理"
PRIVATE_BODY_PHRASE = "刊行の予定が部署ごとに持たれていて"
MAKE_PRIVATE = (
    "- 公開可否: 公開可\n- 出所: 契約書と、月次の議事録（2025-04 以降）",
    "- 公開可否: 公開不可（先方の求めで、この案件は対外の文面に出さない）\n"
    "- 出所: 契約書と、月次の議事録（2025-04 以降）",
)

STALE_PACKAGE_FRESHNESS = "パッケージ定義の鮮度"
OUTDATED_OFFERING_CLAIM = "提示物の宣言と看板の一致"
NOTE_AND_SOURCE_SECTION = "注記と出典の節の実在・公開可否"

# 見せ方の正本から返る、媒体の規約と禁じた言い回しの実例。
CHANNEL_RULE_PHRASE = "400 字以内"
FORBIDDEN_PHRASE = "フルスタック"


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


def _presentation(settings, name: str) -> Path:
    """第 2 の正本の提示物の場所を返す。媒体ディレクトリの直下にある。"""
    return settings.source_dir / name


def test_REQ_082_alt_sample_loads_without_defects(alt_settings) -> None:
    """書き方が違っても、読めなかったブロックの断りが 1 件も出ない。"""
    snapshot = MarkdownRepository(alt_settings).load()

    assert [defect.model_dump() for defect in snapshot.defects] == []


def test_REQ_083_alt_sample_loads_every_type(alt_settings) -> None:
    """書き方が違っても、8 種の正本と見せ方の正本のすべてから 1 件以上が読める。"""
    repository = MarkdownRepository(alt_settings)
    snapshot = repository.load()

    assert len(snapshot.positionings) == 2
    assert [item.id for item in snapshot.packages] == [HEADLINE_PACKAGE, OTHER_PACKAGE]
    assert [item.name for item in snapshot.packages][0] == HEADLINE_PACKAGE_NAME
    assert len(snapshot.capabilities) == 7
    # 職歴の枠は深さ 3、受託案件は深さ 4 と 5。同じ 1 つのファイルから読み分ける。
    assert len(snapshot.career_frames) == 2
    assert len(snapshot.engagements) == 3
    # 提示物は、媒体ディレクトリの下で宣言の行を持つものだけ（控えのファイルは読まない）。
    assert [item.path for item in snapshot.presentations] == [
        "tsukikusa/profile.md",
        "nagiho/skill_sheet.md",
    ]
    # 台帳は 2 列の表を欄として読み、案件番号は見出しの数字から取る。
    assert [item.entry_number for item in snapshot.ledger_entries] == ["1", "2", "3"]
    assert snapshot.ledger_entries[0].fold_line
    # 公開記録は、束ねるための見出しの下の深さ 3 の節で 1 件ぶんになる。
    assert len(snapshot.public_records) == 2

    assert repository.channel_rules(CHANNEL)
    assert repository.forbidden_phrases()


def test_alt_record_positioning_rejects_missing_date(alt_settings) -> None:
    """日付の欄を欠いた決めは、第 2 の正本でも受け付けず、正本を 1 バイトも変えない。"""
    before = source_digest(alt_settings.source_dir)

    result = PositioningService(alt_settings).record(
        PositioningDraft(
            scope="全体",
            headline_package=HEADLINE_PACKAGE,
            rationale="直近の引き合いが、作る前の整理に集中していたため。",
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "決めの必須欄"
    assert result.rejection.next_action.missing_fields == ["日付"]
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_011_alt_check_consistency_detects_stale_package_definition(alt_settings) -> None:
    """看板の束の定義が決めより古いことを、第 2 の正本でも検出する。"""
    _rewrite(alt_settings.path_for("packages"), *STALE_UPDATED_ON)

    report = ConsistencyService(alt_settings).inspect()

    stale = [v for v in report.violations if v.constraint == STALE_PACKAGE_FRESHNESS]
    assert len(stale) == 1, [v.model_dump() for v in report.violations]
    assert stale[0].file == alt_settings.files["packages"]
    assert HEADLINE_PACKAGE in stale[0].location


def test_REQ_012_alt_check_consistency_detects_outdated_offering_claim(alt_settings) -> None:
    """旧い束を宣言した提示物を、媒体ディレクトリ直下のファイル名つきで検出する。"""
    _rewrite(_presentation(alt_settings, "tsukikusa/profile.md"), *OUTDATED_CLAIM)

    report = ConsistencyService(alt_settings).inspect()

    outdated = [v for v in report.violations if v.constraint == OUTDATED_OFFERING_CLAIM]
    assert [v.file for v in outdated] == ["tsukikusa/profile.md"]
    assert outdated[0].candidates == [HEADLINE_PACKAGE]


def test_REQ_013_alt_check_consistency_skips_claim_listed_as_exception(alt_settings) -> None:
    """旧い束を宣言した提示物が 2 件でも、決めの例外欄に書いた 1 件は一覧に出ない。"""
    _rewrite(_presentation(alt_settings, "tsukikusa/profile.md"), *OUTDATED_CLAIM)
    _rewrite(_presentation(alt_settings, "nagiho/skill_sheet.md"), *OUTDATED_CLAIM)
    _rewrite(alt_settings.path_for("positioning"), *EXCEPTION_ENTRY, last=True)

    report = ConsistencyService(alt_settings).inspect()

    outdated = [v for v in report.violations if v.constraint == OUTDATED_OFFERING_CLAIM]
    assert [v.file for v in outdated] == ["nagiho/skill_sheet.md"]


def test_alt_register_capability_rejects_unknown_evidence_section(alt_settings) -> None:
    """実在しない節名を裏づけにすると、第 2 の正本でも受け付けず、近い見出しを返す。"""
    before = source_digest(alt_settings.source_dir)
    headings = MarkdownRepository(alt_settings).load().section_headings()

    result = OfferingService(alt_settings).register_capability(
        CapabilityDraft(
            id="collect-delivery-records",
            name="配送の実績を 1 か所に集める",
            description="拠点ごとに分かれた実績を 1 つの置き場に入れる",
            category=alt_settings.capability_categories[0],
            evidence_sections=["teramina-deliver"],
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "裏づけ節名の実在"
    candidates = result.rejection.next_action.candidates
    assert candidates
    assert all(candidate in headings for candidate in candidates)
    assert source_digest(alt_settings.source_dir) == before


def test_alt_revise_package_rejects_unregistered_capability(alt_settings) -> None:
    """機能の台帳に無い名前を束ねると、第 2 の正本でも書かずに拒否する。"""
    before = source_digest(alt_settings.source_dir)

    result = OfferingService(alt_settings).revise_package(
        PackageDraft(
            id=HEADLINE_PACKAGE,
            name=HEADLINE_PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY, "plan-from-decision"],
            buyer=BUYER,
            hypothesis_state=alt_settings.package_hypothesis_states[1],
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "束ねる機能名の一致"
    assert "plan-from-decisions" in result.rejection.next_action.candidates
    assert source_digest(alt_settings.source_dir) == before


def test_REQ_019_alt_check_consistency_detects_private_source_section_in_ledger(alt_settings) -> None:
    """台帳が公開不可の節を出典にしていることを、表で書かれた台帳でも検出する。"""
    _rewrite(alt_settings.path_for("engagements"), *MAKE_PRIVATE)

    report = ConsistencyService(alt_settings).inspect()

    ledger = [
        v
        for v in report.violations
        if v.constraint == NOTE_AND_SOURCE_SECTION
        and v.file == alt_settings.files["resume_ledger"]
    ]
    assert len(ledger) == 1, [v.model_dump() for v in report.violations]
    # 案件番号は見出しの数字から読むので、場所の指し方も第 1 版と同じになる。
    assert "案件番号 3" in ledger[0].location
    assert PRIVATE_SECTION in ledger[0].expected
    assert ledger[0].candidates == ["teramina-delivery", "yukinoha-quality"]
    # 表示名は違反の文の側に添えて出る。
    assert "テラミナ物流 配送データの置き場づくり" in ledger[0].expected, ledger[0].expected


def test_alt_assemble_material_drops_private_section_and_warns(alt_settings) -> None:
    """公開不可の節は材料に出さず、落としたことと節の名前を警告に書く。"""
    _rewrite(alt_settings.path_for("engagements"), *MAKE_PRIVATE)

    material = MaterialService(alt_settings).assemble(MaterialRequest(channel=CHANNEL))

    headings = [entry["見出し"] for entry in material.evidence]
    assert PRIVATE_SECTION not in headings, headings
    bodies = "\n".join(entry["本文"] for entry in material.evidence)
    assert PRIVATE_BODY_PHRASE not in bodies
    listed = "\n".join(material.warnings)
    assert PRIVATE_SECTION in listed, listed
    assert "落とした" in listed, listed
    assert headings


def test_REQ_020_alt_check_consistency_detects_dangling_pending_note(alt_settings) -> None:
    """実在しない節を指す注記を、ファイル名と近い節の候補つきで検出する。"""
    _rewrite(_presentation(alt_settings, "nagiho/skill_sheet.md"), *DANGLING_NOTE)

    report = ConsistencyService(alt_settings).inspect()

    dangling = [
        v
        for v in report.violations
        if v.constraint == NOTE_AND_SOURCE_SECTION and v.file == "nagiho/skill_sheet.md"
    ]
    assert len(dangling) == 1, [v.model_dump() for v in report.violations]
    assert PRIVATE_SECTION_ID in dangling[0].candidates
    assert PRIVATE_SECTION in dangling[0].expected, dangling[0].expected


def test_REQ_021_alt_remaining_pending_notes_are_counted_in_a_note(alt_settings) -> None:
    """残っている未反映の注記の件数を、第 2 の正本でも断りに書く。"""
    _rewrite(_presentation(alt_settings, "nagiho/skill_sheet.md"), *DANGLING_NOTE)

    report = ConsistencyService(alt_settings).inspect()

    assert any("未反映の注記が 1 件残っている" in note for note in report.notes), report.notes


def test_alt_assemble_material_returns_channel_rules_and_forbidden_phrases(alt_settings) -> None:
    """媒体ごとのファイルの規約と、表で書かれた禁じた言い回しが、材料に載って返る。"""
    material = MaterialService(alt_settings).assemble(MaterialRequest(channel=CHANNEL))

    assert any(CHANNEL_RULE_PHRASE in rule for rule in material.channel_rules), (
        material.channel_rules
    )
    assert any(FORBIDDEN_PHRASE in phrase for phrase in material.forbidden_phrases), (
        material.forbidden_phrases
    )
    # 媒体の規約は、その媒体のファイルだけを返す。禁じた言い回しはどの媒体でも同じ。
    other = MaterialService(alt_settings).assemble(MaterialRequest(channel="nagiho"))
    assert other.channel_rules != material.channel_rules
    assert other.forbidden_phrases == material.forbidden_phrases
    # 禁じた言い回しの節にある 2 つ目の表（決めの出典）は混ざらない。
    assert len(material.forbidden_phrases) == 3, material.forbidden_phrases
