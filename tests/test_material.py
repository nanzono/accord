"""文面の材料を取り出す操作のテスト。

要件 REQ-084〜108 を、1 本につき 1 件ずつ確かめる。見るのは、材料に何が載るか、公開不可の節を
どう落とすか、正本に無いものをどう断るか、呼び方が通らないときに何を案内するかである。
執行する制約は「提出物に含まれる事実は公開可の節に限る」1 つで、公開不可の節が材料に出ないことと、
落としたことが警告に出ることを別々のテストで見る。すべて同梱のサンプルの一時的な写しの上で走らせる。
"""

from __future__ import annotations

from pathlib import Path

from accord.models.results import MaterialRequest
from accord.services.material import MaterialService
from accord.vocabulary.settings import PRESENTATION_RULES_KEY
from conftest import source_digest

# 決めも提示物もパッケージを ID で指すので、ID と見出し（表示名）の両方を持つ。
CHANNEL = "tsukikusa"
HEADLINE_PACKAGE = "requirements-and-progress"
HEADLINE_PACKAGE_NAME = "要件定義と進行管理"
OTHER_PACKAGE = "data-platform-setup"

# 公開不可にする受託案件と、その節の本文にしか出てこない言い回し。
PRIVATE_SECTION = "ナギサ書房 刊行計画の進行管理"
PRIVATE_BODY_PHRASE = "刊行の予定が部署ごとに持たれていて"
MAKE_PRIVATE = (
    "- 公開可否: 公開可\n- 出所: 契約書と、月次の議事録（2025-04 以降）",
    "- 公開可否: 公開不可（先方の求めで、この案件は対外の文面に出さない）\n"
    "- 出所: 契約書と、月次の議事録（2025-04 以降）",
)

# 見せ方の正本が持つ、媒体の規約と禁じた言い回しの実例。
CHANNEL_RULE_PHRASE = "400 字以内"
FORBIDDEN_PHRASE = "フルスタック"

# 提示物に旧い束を宣言させる書き換え。
OUTDATED_CLAIM = (
    f"- 宣言する束: {HEADLINE_PACKAGE}",
    f"- 宣言する束: {OTHER_PACKAGE}",
)

# 正本に無いものを材料に持ち込めなかったことは、どちらもこの言い回しで返る。
NOT_IN_MATERIAL = "材料に入っていない"

# パッケージ定義の束ねる機能を、機能の台帳に無い ID に差し替える書き換え。
UNKNOWN_CAPABILITY_ID = "handover-nowhere"
BREAK_PACKAGE_CAPABILITY = (
    "- 束ねる機能: requirements-forum / plan-from-decisions / handover-operations",
    f"- 束ねる機能: requirements-forum / plan-from-decisions / {UNKNOWN_CAPABILITY_ID}",
)

# 機能の台帳の裏づけの節を、正本のどこにも無い ID に差し替える書き換え。
CAPABILITY_WITH_BROKEN_EVIDENCE = "要件を決める場をつくる"
UNKNOWN_EVIDENCE_ID = "nagisa-nowhere"
_EVIDENCE_ROW = (
    "| requirements-forum | 要件を決める場をつくる "
    "| 決まっていないことを一覧にし、決める人と決める日を置く | "
)
BREAK_CAPABILITY_EVIDENCE = (
    _EVIDENCE_ROW + "nagisa-publishing |",
    _EVIDENCE_ROW + UNKNOWN_EVIDENCE_ID + " |",
)


def _rewrite(path: Path, old: str, new: str) -> None:
    """写しの 1 か所を書き換える。狙った文字列が無ければ、テストの前提が崩れたとして落とす。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しに「{old}」が無い: {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _material(settings, **kwargs):
    """写しの正本から材料を取り出す。"""
    request = MaterialRequest(channel=kwargs.pop("channel", CHANNEL), **kwargs)
    return MaterialService(settings).assemble(request)


def _strip_presentation_rules(settings) -> str:
    """見せ方の正本を題だけに切り詰め、その正本のファイル名を返す。"""
    rules = settings.path_for(PRESENTATION_RULES_KEY)
    header, mark, _ = rules.read_text(encoding="utf-8").partition(f"## {CHANNEL}")
    assert mark, "写しの見せ方の正本に、媒体の節が無い"
    rules.write_text(header, encoding="utf-8")
    return settings.files[PRESENTATION_RULES_KEY]


# ---------------------------------------------------------------- 通る道に何が載るか


def test_REQ_084_material_headlines_the_bundle_the_positioning_names(settings) -> None:
    """媒体だけを渡すと、その媒体の決めが前面に出す束が、材料の看板になる。"""
    material = _material(settings)

    assert material.channel == CHANNEL
    assert material.positioning is not None
    assert material.package is not None
    assert material.package.id == HEADLINE_PACKAGE


def test_REQ_085_material_accepts_a_package_name_that_exists(settings) -> None:
    """実在するパッケージの ID をそのまま渡すと、その束が材料の看板になる。"""
    material = _material(settings, package=OTHER_PACKAGE)

    assert material.package is not None
    assert material.package.id == OTHER_PACKAGE
    assert [item.id for item in material.capabilities] == list(material.package.capabilities)


def test_REQ_086_capabilities_follow_the_order_in_the_package(settings) -> None:
    """束ねる機能は、パッケージ定義が並べた ID の並びのまま材料に載る。"""
    material = _material(settings)

    assert material.package is not None
    # 束ねる機能が、パッケージ定義の並び（ID の並び）で揃っている。
    assert [item.id for item in material.capabilities] == list(material.package.capabilities)


def test_REQ_087_evidence_carries_the_heading_the_id_and_the_body(settings) -> None:
    """裏づけの節は、表示名と ID と本文を添えて材料に載る。"""
    material = _material(settings)

    # 裏づけの節が、表示名と ID と本文で入っている。
    assert material.evidence
    for entry in material.evidence:
        assert entry["見出し"]
        assert entry["ID"]
        assert entry["本文"]
        # 見出しは人が読む表示名で、ID とは別物である。
        assert entry["見出し"] != entry["ID"]


def test_REQ_088_material_carries_the_public_records_behind_the_capabilities(settings) -> None:
    """束ねる機能の裏づけになっている公開記録が、材料の公開記録として返る。"""
    material = _material(settings)

    assert [record.name for record in material.public_records] == [CARRIED_RECORD]
    behind = {
        name for capability in material.capabilities for name in capability.evidence_sections
    }
    assert all(record.id in behind for record in material.public_records)
    # 媒体の規約も同じ返り値に載っているので、どの欄に入れるかをここだけで決められる。
    assert material.channel_rules


def test_REQ_089_public_records_are_not_listed_among_the_evidence_sections(settings) -> None:
    """公開記録は節ではないので、裏づけの節の一覧には混ざらない。"""
    material = _material(settings)

    assert material.public_records
    assert CARRIED_RECORD not in [entry["見出し"] for entry in material.evidence]


def test_REQ_090_material_carries_the_channel_rules(settings) -> None:
    """見せ方の正本にある、その媒体の規約が材料に載る。"""
    material = _material(settings)

    assert any(CHANNEL_RULE_PHRASE in rule for rule in material.channel_rules), (
        material.channel_rules
    )
    # 媒体の規約は、その媒体の節だけを返す（他の媒体の節は混ざらない）。
    other = _material(settings, channel="nagiho")
    assert other.channel_rules != material.channel_rules


def test_REQ_091_material_carries_the_forbidden_phrases(settings) -> None:
    """見せ方の正本にある禁じた言い回しが、媒体によらず同じ一覧として材料に載る。"""
    material = _material(settings)

    assert any(FORBIDDEN_PHRASE in phrase for phrase in material.forbidden_phrases), (
        material.forbidden_phrases
    )
    other = _material(settings, channel="nagiho")
    assert other.forbidden_phrases == material.forbidden_phrases


def test_REQ_092_assembling_material_leaves_the_source_untouched(settings) -> None:
    """読みの操作なので、材料を取り出しても正本は 1 バイトも変わらない。"""
    before = source_digest(settings.source_dir)

    material = _material(settings)

    assert material.package is not None
    # 読みの操作なので、正本は 1 バイトも変わらない。
    assert source_digest(settings.source_dir) == before


# ---------------------------------------------------------------- 公開不可で落とすもの


def test_REQ_093_private_section_is_dropped_from_the_evidence(settings) -> None:
    """公開不可の節は、見出しも本文も材料に出さない。"""
    _rewrite(settings.path_for("engagements"), *MAKE_PRIVATE)

    material = _material(settings)

    headings = [entry["見出し"] for entry in material.evidence]
    assert PRIVATE_SECTION not in headings, headings
    # 本文も出ていない（見出しだけ隠して中身が残る、という落ち方をしていない）。
    bodies = "\n".join(entry["本文"] for entry in material.evidence)
    assert PRIVATE_BODY_PHRASE not in bodies
    # 残りの裏づけは落ちていない。
    assert headings


def test_REQ_094_dropping_a_private_section_is_named_in_a_warning(settings) -> None:
    """公開不可の節を落としたことと、その節の名前を警告に書く。"""
    _rewrite(settings.path_for("engagements"), *MAKE_PRIVATE)

    material = _material(settings)

    # 落としたことと、落とした節の名前が警告に入っている。
    listed = "\n".join(material.warnings)
    assert PRIVATE_SECTION in listed, listed
    assert "落とした" in listed, listed


# ---------------------------------------------------------------- 材料に入らなかったものの断り


def test_REQ_095_capability_missing_from_the_ledger_is_named_in_a_warning(settings) -> None:
    """束ねる機能が台帳に無い ID のときは、束の名前とその ID を添えて警告に返す。"""
    before = len(_material(settings).capabilities)
    _rewrite(settings.path_for("packages"), *BREAK_PACKAGE_CAPABILITY)

    material = _material(settings)

    assert len(material.capabilities) == before - 1
    notes = [note for note in material.warnings if NOT_IN_MATERIAL in note]
    assert len(notes) == 1, material.warnings
    assert UNKNOWN_CAPABILITY_ID in notes[0]
    assert HEADLINE_PACKAGE_NAME in notes[0]


def test_REQ_096_evidence_section_missing_from_the_source_is_named_in_a_warning(
    settings,
) -> None:
    """裏づけの節が正本のどこにも無い ID のときは、機能の名前とその ID を添えて警告に返す。"""
    _rewrite(settings.path_for("capabilities"), *BREAK_CAPABILITY_EVIDENCE)

    material = _material(settings)

    assert UNKNOWN_EVIDENCE_ID not in [entry["ID"] for entry in material.evidence]
    notes = [note for note in material.warnings if NOT_IN_MATERIAL in note]
    assert len(notes) == 1, material.warnings
    assert UNKNOWN_EVIDENCE_ID in notes[0]
    assert CAPABILITY_WITH_BROKEN_EVIDENCE in notes[0]


def test_REQ_097_missing_channel_section_leaves_the_rules_empty_with_a_warning(
    settings,
) -> None:
    """見せ方の正本にその媒体の節が無いと、規約は空になり、正本のファイル名が警告に入る。"""
    file_name = _strip_presentation_rules(settings)

    material = _material(settings)

    assert material.channel_rules == []
    notes = [note for note in material.warnings if "媒体の規約は空" in note]
    assert len(notes) == 1, material.warnings
    assert file_name in notes[0]
    assert CHANNEL in notes[0]


def test_REQ_098_missing_forbidden_phrases_section_leaves_the_list_empty_with_a_warning(
    settings,
) -> None:
    """見せ方の正本に禁じた言い回しの節が無いと、一覧は空になり、正本のファイル名が警告に入る。"""
    file_name = _strip_presentation_rules(settings)

    material = _material(settings)

    assert material.forbidden_phrases == []
    notes = [note for note in material.warnings if "禁じた言い回しの節が無い" in note]
    assert len(notes) == 1, material.warnings
    assert file_name in notes[0]


# ---------------------------------------------------------------- 呼び方が通らないときの案内


def test_REQ_099_unknown_package_name_yields_no_bundle(settings) -> None:
    """パッケージの ID が実在しないときは、看板も束ねる機能も材料に載せない。"""
    material = _material(settings, package="要件定義と進こう管理")

    assert material.package is None
    assert material.capabilities == []


def test_REQ_100_unknown_package_name_lists_the_existing_packages(settings) -> None:
    """パッケージの ID が実在しないときは、実在する ID の一覧と次の一手を返す。"""
    material = _material(settings, package="要件定義と進こう管理")

    listed = "\n".join(material.warnings)
    assert HEADLINE_PACKAGE in listed, listed
    assert OTHER_PACKAGE in listed, listed
    assert "assemble_material" in listed, listed


def test_REQ_101_unknown_channel_yields_no_material(settings) -> None:
    """媒体の名前が実在しないときは、決めも看板のパッケージも材料に載せない。"""
    material = _material(settings, channel="shiokaze")

    assert material.positioning is None
    assert material.package is None


def test_REQ_102_unknown_channel_lists_the_existing_channels(settings) -> None:
    """媒体の名前が実在しないときは、拒否ではなく実在する媒体の一覧と次の一手を返す。"""
    material = _material(settings, channel="shiokaze")

    listed = "\n".join(material.warnings)
    for name in settings.channels:
        assert name in listed, listed
    assert "assemble_material" in listed, listed


def test_REQ_103_unrecorded_positioning_yields_no_material(settings) -> None:
    """決めが 1 件も登記されていないときは、決めも看板も裏づけも材料に載せない。"""
    positioning = settings.path_for("positioning")
    header, _, _ = positioning.read_text(encoding="utf-8").partition("## 2026-06-01 全体")
    positioning.write_text(header, encoding="utf-8")

    material = _material(settings)

    assert material.positioning is None
    assert material.package is None
    assert material.evidence == []


def test_REQ_104_unrecorded_positioning_says_to_record_it_first(settings) -> None:
    """決めが 1 件も登記されていないときは、先に決めを登記することと、その入力の型を返す。"""
    positioning = settings.path_for("positioning")
    header, _, _ = positioning.read_text(encoding="utf-8").partition("## 2026-06-01 全体")
    positioning.write_text(header, encoding="utf-8")

    material = _material(settings)

    listed = "\n".join(material.warnings)
    assert "先に決めを登記する" in listed, listed
    assert "record_positioning" in listed, listed
    for label in ["日付", "適用範囲", "前面に出す束", "根拠", "例外"]:
        assert label in listed, listed


# ---------------------------------------------------------------- 渡されたが使わないもの


def test_REQ_105_an_opportunity_does_not_change_the_material(settings) -> None:
    """案件を渡しても、看板のパッケージと裏づけは渡さないときと変わらない。"""
    plain = _material(settings)
    with_opportunity = _material(settings, opportunity="ある会社の進行役の募集")

    assert with_opportunity.package == plain.package
    assert with_opportunity.evidence == plain.evidence


def test_REQ_106_an_opportunity_is_named_as_unused_in_a_warning(settings) -> None:
    """案件を渡すと、第 1 版では材料に反映しないことを、その名前を添えて断る。"""
    with_opportunity = _material(settings, opportunity="ある会社の進行役の募集")

    listed = "\n".join(with_opportunity.warnings)
    assert "ある会社の進行役の募集" in listed, listed
    assert "反映しない" in listed, listed


# ---------------------------------------------------------------- 整合の検査との結びと公開記録


def test_REQ_107_material_carries_the_violations_of_the_consistency_check(settings) -> None:
    """旧い束を宣言する提示物は、整合の検査が挙げた文のまま材料の警告に入る。"""
    presentation = settings.path_for("presentations") / CHANNEL / "profile.md"
    _rewrite(presentation, *OUTDATED_CLAIM)

    material = _material(settings)

    listed = "\n".join(material.warnings)
    assert "提示物の宣言と看板の一致" in listed, listed
    assert "profile.md" in listed, listed
    assert HEADLINE_PACKAGE in listed, listed


# ---------------------------------------------------------------- 公開記録


# 同梱のサンプルの公開記録のうち、看板の束が束ねる機能の裏づけになっているもの。
CARRIED_RECORD = "刊行計画の進め方を話した勉強会の発表"

# 写しの公開記録を、裏づけに使われているブロック 1 つだけに切り詰めるときの目印。
SECOND_RECORD_HEADING = "## 品質記録の集約を取り上げた導入事例の記事"

# 裏づけに使われていない公開記録。写しに足して、警告に出ることを見る。
UNUSED_RECORD_NAME = "配送の置き場づくりを書いた個人の記事"
UNUSED_RECORD = f"""
## {UNUSED_RECORD_NAME}

- ID: warehouse-note-article
- 種類: 記事
- 日付: 2023-06
- URL: https://example.com/notes/warehouse
- 発行元か主催: 架空の個人の記事の置き場
- 役割: 著者
- 由来の節: なし
- 出所: 公開したときの控え
"""

UNUSED_RECORD_PHRASE = "裏づけに使われていない公開記録"


def _keep_only_the_carried_record(settings) -> None:
    """写しの公開記録を、裏づけに使われているブロック 1 つだけに切り詰める。"""
    records = settings.path_for("public_records")
    head, mark, _ = records.read_text(encoding="utf-8").partition(SECOND_RECORD_HEADING)
    assert mark, "写しの公開記録に、2 つ目のブロックが無い"
    records.write_text(head.rstrip("\n") + "\n", encoding="utf-8")


def test_REQ_108_public_record_not_used_as_evidence_is_named_in_a_warning(settings) -> None:
    """どの機能の裏づけにもなっていない公開記録を足すと、件数と名前を添えた警告が 1 件増える。"""
    _keep_only_the_carried_record(settings)
    before = [note for note in _material(settings).warnings if UNUSED_RECORD_PHRASE in note]
    assert before == []

    records = settings.path_for("public_records")
    records.write_text(records.read_text(encoding="utf-8") + UNUSED_RECORD, encoding="utf-8")

    after = [note for note in _material(settings).warnings if UNUSED_RECORD_PHRASE in note]
    assert len(after) == 1, after
    assert UNUSED_RECORD_NAME in after[0]
