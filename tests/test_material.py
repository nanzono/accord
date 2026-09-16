"""文面の材料を取り出す操作のテスト。

執行する制約は「提出物に含まれる事実は公開可の節に限る」1 つで、公開不可の節が材料に出ないことと、
落としたことが警告に出ることを見る。あわせて、代わりの手（実在するパッケージの一覧、先に決めを登記する）と、
見せ方の正本から読む媒体の規約・禁じた言い回しを見る。すべて同梱のサンプルの一時的な写しの上で走らせる。
"""

from __future__ import annotations

from pathlib import Path

from accord.models.results import MaterialRequest
from accord.services.material import MaterialService
from conftest import source_digest

CHANNEL = "tsukikusa"
HEADLINE_PACKAGE = "要件定義と進行管理"
OTHER_PACKAGE = "データの置き場づくり"

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


def _rewrite(path: Path, old: str, new: str) -> None:
    """写しの 1 か所を書き換える。狙った文字列が無ければ、テストの前提が崩れたとして落とす。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しに「{old}」が無い: {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _material(settings, **kwargs):
    """写しの正本から材料を取り出す。"""
    request = MaterialRequest(channel=kwargs.pop("channel", CHANNEL), **kwargs)
    return MaterialService(settings).assemble(request)


def test_assemble_material_returns_the_headline_bundle_and_its_evidence(settings) -> None:
    """媒体だけを渡すと、その媒体の決めの束と、束ねる機能の裏づけが揃って返る。"""
    before = source_digest(settings.source_dir)

    material = _material(settings)

    assert material.channel == CHANNEL
    assert material.positioning is not None
    assert material.package is not None
    assert material.package.name == HEADLINE_PACKAGE
    # 束ねる機能が、パッケージ定義の並びで揃っている。
    assert [item.name for item in material.capabilities] == list(material.package.capabilities)
    # 裏づけの節が、見出しと本文で入っている。
    assert material.evidence
    for entry in material.evidence:
        assert entry["見出し"]
        assert entry["本文"]
    # 読みの操作なので、正本は 1 バイトも変わらない。
    assert source_digest(settings.source_dir) == before


def test_assemble_material_drops_private_section_and_warns(settings) -> None:
    """公開不可の節は材料に出さず、落としたことと節の名前を警告に書く。"""
    _rewrite(settings.path_for("engagements"), *MAKE_PRIVATE)

    material = _material(settings)

    headings = [entry["見出し"] for entry in material.evidence]
    assert PRIVATE_SECTION not in headings, headings
    # 本文も出ていない（見出しだけ隠して中身が残る、という落ち方をしていない）。
    bodies = "\n".join(entry["本文"] for entry in material.evidence)
    assert PRIVATE_BODY_PHRASE not in bodies
    # 落としたことと、落とした節の名前が警告に入っている。
    listed = "\n".join(material.warnings)
    assert PRIVATE_SECTION in listed, listed
    assert "落とした" in listed, listed
    # 残りの裏づけは落ちていない。
    assert headings


def test_assemble_material_lists_existing_packages_for_an_unknown_name(settings) -> None:
    """パッケージ名が実在しないときは、実在する名前の一覧と次の一手を返す。"""
    material = _material(settings, package="要件定義と進こう管理")

    assert material.package is None
    assert material.capabilities == []
    listed = "\n".join(material.warnings)
    assert HEADLINE_PACKAGE in listed, listed
    assert OTHER_PACKAGE in listed, listed
    assert "assemble_material" in listed, listed


def test_assemble_material_accepts_a_package_name_that_exists(settings) -> None:
    """実在するパッケージ名をそのまま渡すと、その束で材料が組み上がる。"""
    material = _material(settings, package=OTHER_PACKAGE)

    assert material.package is not None
    assert material.package.name == OTHER_PACKAGE
    assert [item.name for item in material.capabilities] == list(material.package.capabilities)


def test_assemble_material_says_to_record_the_positioning_first(settings) -> None:
    """決めが未登記のときは、先に決めを登記することと、その入力の型を返す。"""
    positioning = settings.path_for("positioning")
    header, _, _ = positioning.read_text(encoding="utf-8").partition("## 2026-06-01 全体")
    positioning.write_text(header, encoding="utf-8")

    material = _material(settings)

    assert material.positioning is None
    assert material.package is None
    assert material.evidence == []
    listed = "\n".join(material.warnings)
    assert "先に決めを登記する" in listed, listed
    assert "record_positioning" in listed, listed
    for label in ["日付", "適用範囲", "前面に出す束", "根拠", "例外"]:
        assert label in listed, listed


def test_assemble_material_returns_channel_rules_and_forbidden_phrases(settings) -> None:
    """見せ方の正本から、その媒体の節と、禁じた言い回しの節が返る。"""
    material = _material(settings)

    assert any(CHANNEL_RULE_PHRASE in rule for rule in material.channel_rules), (
        material.channel_rules
    )
    assert any(FORBIDDEN_PHRASE in phrase for phrase in material.forbidden_phrases), (
        material.forbidden_phrases
    )
    # 媒体の規約は、その媒体の節だけを返す（他の媒体の節は混ざらない）。
    other = _material(settings, channel="nagiho")
    assert other.channel_rules != material.channel_rules
    assert other.forbidden_phrases == material.forbidden_phrases


def test_assemble_material_warns_about_an_outdated_offering_claim(settings) -> None:
    """旧い束を宣言する提示物は、整合検査が挙げた文のまま警告に入る。"""
    presentation = settings.path_for("presentations") / CHANNEL / "profile.md"
    _rewrite(presentation, *OUTDATED_CLAIM)

    material = _material(settings)

    listed = "\n".join(material.warnings)
    assert "提示物の宣言と看板の一致" in listed, listed
    assert "profile.md" in listed, listed
    assert HEADLINE_PACKAGE in listed, listed


def test_assemble_material_accepts_an_opportunity_and_says_it_is_unused(settings) -> None:
    """案件を渡しても壊れず、第 1 版では材料に反映しないことを断る。"""
    plain = _material(settings)
    with_opportunity = _material(settings, opportunity="ある会社の進行役の募集")

    assert with_opportunity.package == plain.package
    assert with_opportunity.evidence == plain.evidence
    listed = "\n".join(with_opportunity.warnings)
    assert "ある会社の進行役の募集" in listed, listed
    assert "反映しない" in listed, listed


def test_assemble_material_lists_existing_channels_for_an_unknown_name(settings) -> None:
    """媒体の名前が実在しないときは、拒否ではなく実在する媒体の一覧を返す。"""
    material = _material(settings, channel="shiokaze")

    assert material.positioning is None
    listed = "\n".join(material.warnings)
    for name in settings.channels:
        assert name in listed, listed
    assert "assemble_material" in listed, listed
