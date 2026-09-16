"""機能を登記する操作と、パッケージを改訂する操作のテスト。

機能の登記は、分類の出どころと裏づけの節の実在を見る。パッケージの改訂は、束ねる機能名の
一致と仮説の状態の語、通ったときに節が差し替わって最終更新日が今日に進むことを見る。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from accord.models.results import CapabilityDraft, PackageDraft
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.offering import OfferingService
from accord.vocabulary.settings import load_settings
from conftest import source_digest

# 設定を書き換えたときに使う、別人の語彙。コードには 1 行も現れない語にしてある。
OTHER_CATEGORIES = [
    "土台をならす",
    "見えるようにする",
    "段取りをつくる",
    "渡せるようにする",
    "人を増やす",
]

# 同梱のサンプルにある名前。改訂のテストはこの節を土台にする。
PACKAGE_NAME = "要件定義と進行管理"
KNOWN_CAPABILITY = "要件を決める場をつくる"
BUYER = "専任の進行役を置けない、従業員 100 名前後の会社の事業責任者"

CONFIG_TEMPLATE = """[source]
directory = "source"

[source.files]
positioning = "positioning.md"
packages = "packages.md"
capabilities = "capabilities.md"
career = "career.md"
engagements = "engagements.md"
resume_ledger = "resume_ledger.md"
presentations = "presentations"
presentation_rules = "presentation_rules.md"

[vocabulary]
channels = ["tsukikusa", "nagiho"]
capability_categories = [{categories}]
package_hypothesis_states = ["仮説のみ", "検証中", "実績あり"]
"""


def _rewrite_categories(config_path: Path, categories: list[str]) -> None:
    """設定ファイルの分類の 5 節を、別の語に差し替える。"""
    listed = ", ".join(f'"{name}"' for name in categories)
    config_path.write_text(CONFIG_TEMPLATE.format(categories=listed), encoding="utf-8")


def test_capability_categories_come_from_settings(sample_copy: Path) -> None:
    """分類の 5 節を設定で差し替えると、受け付ける分類もコードを直さずに変わる。"""
    config_path = sample_copy / "accord.toml"
    before = load_settings(config_path)
    old_category = before.capability_categories[0]
    assert old_category not in OTHER_CATEGORIES

    _rewrite_categories(config_path, OTHER_CATEGORIES)
    after = load_settings(config_path)
    assert after.capability_categories == OTHER_CATEGORIES

    service = OfferingService(after)
    heading = MarkdownRepository(after).load().section_headings()[-1]

    accepted = service.register_capability(
        CapabilityDraft(
            name="工程の期日を 1 枚に集める",
            description="部署ごとに持っている予定を 1 枚にまとめ、遅れを早く見つける",
            category=OTHER_CATEGORIES[2],
            evidence_sections=[heading],
        )
    )
    assert accepted.accepted is True, accepted.model_dump()
    assert OTHER_CATEGORIES[2] in after.path_for("capabilities").read_text(encoding="utf-8")

    rejected = service.register_capability(
        CapabilityDraft(
            name="置き場をそろえる",
            description="分かれている数字を 1 か所に集める",
            category=old_category,
            evidence_sections=[heading],
        )
    )
    assert rejected.accepted is False
    assert rejected.rejection is not None
    assert rejected.rejection.next_action.candidates == OTHER_CATEGORIES


def test_register_capability_rejects_missing_required_fields(settings) -> None:
    """機能名と説明を空にすると、書かずに拒否し、欠けた欄の名前と書き方の例を返す。"""
    before = source_digest(settings.source_dir)
    heading = MarkdownRepository(settings).load().section_headings()[0]

    result = OfferingService(settings).register_capability(
        CapabilityDraft(
            name="",
            description="",
            category=settings.capability_categories[0],
            evidence_sections=[heading],
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "機能の必須欄"

    next_action = result.rejection.next_action
    assert next_action.missing_fields == ["機能名", "説明"]
    assert next_action.operation == "register_capability"
    assert "機能名" in next_action.example
    assert "説明" in next_action.example

    # 拒否のときは正本のバイト列が 1 つも変わらない。
    assert source_digest(settings.source_dir) == before


def test_register_capability_rejects_unknown_evidence_section(settings) -> None:
    """実在しない節名を裏づけにすると、受け付けず、近い見出しの候補を返す。"""
    before = source_digest(settings.source_dir)
    service = OfferingService(settings)
    headings = MarkdownRepository(settings).load().section_headings()

    result = service.register_capability(
        CapabilityDraft(
            name="配送の実績を 1 か所に集める",
            description="拠点ごとに分かれた実績を 1 つの置き場に入れる",
            category=settings.capability_categories[0],
            evidence_sections=["テラミナ物流 配送データの置き揚づくり"],
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "裏づけ節名の実在"

    candidates = result.rejection.next_action.candidates
    assert candidates, "近い見出しの候補が 1 つ以上返ること"
    assert all(candidate in headings for candidate in candidates), "候補はそのまま渡せば通る名前"

    # 拒否のときは正本のバイト列が 1 つも変わらない。
    assert source_digest(settings.source_dir) == before


def test_rejected_candidate_is_accepted_when_passed_back(settings) -> None:
    """返ってきた候補をそのまま渡し直すと、今度は受け付けられる。"""
    service = OfferingService(settings)
    rejected = service.register_capability(
        CapabilityDraft(
            name="配送の実績を 1 か所に集める",
            description="拠点ごとに分かれた実績を 1 つの置き場に入れる",
            category=settings.capability_categories[0],
            evidence_sections=["テラミナ物流 配送データの置き揚づくり"],
        )
    )
    assert rejected.rejection is not None

    retried = service.register_capability(
        CapabilityDraft(
            name="配送の実績を 1 か所に集める",
            description="拠点ごとに分かれた実績を 1 つの置き場に入れる",
            category=settings.capability_categories[0],
            evidence_sections=[rejected.rejection.next_action.candidates[0]],
        )
    )
    assert retried.accepted is True, retried.model_dump()
    assert "裏づけの節の公開可否" in retried.recorded


def test_revise_package_rejects_unregistered_capability(settings) -> None:
    """機能の台帳に無い名前を束ねると、書かずに拒否し、候補と先に呼ぶ操作を返す。"""
    before = source_digest(settings.source_dir)
    service = OfferingService(settings)

    result = service.revise_package(
        PackageDraft(
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY, "決まったことを段取りに落とさない"],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[1],
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "束ねる機能名の一致"

    next_action = result.rejection.next_action
    assert "決まったことを段取りに落とす" in next_action.candidates, next_action.candidates
    assert "register_capability" in next_action.example, next_action.example

    # 拒否のときは正本のバイト列が 1 つも変わらない。
    assert source_digest(settings.source_dir) == before

    # 返ってきた候補をそのまま渡し直すと、今度は受け付けられる。
    retried = service.revise_package(
        PackageDraft(
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY, next_action.candidates[0]],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[1],
        )
    )
    assert retried.accepted is True, retried.model_dump()


def test_revise_package_rejects_a_hypothesis_state_outside_the_settings(settings) -> None:
    """仮説の状態が設定の語に無いときは、書かずに拒否し、設定の語を返す。"""
    before = source_digest(settings.source_dir)

    result = OfferingService(settings).revise_package(
        PackageDraft(
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY],
            buyer=BUYER,
            hypothesis_state="だいたい実績あり",
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.next_action.candidates == settings.package_hypothesis_states
    assert source_digest(settings.source_dir) == before


def test_revise_package_replaces_the_section_and_advances_the_update_date(settings) -> None:
    """通る改訂は、その節を書き換え、最終更新日を今日に進める。"""
    packages = settings.path_for("packages")
    before_sections = packages.read_text(encoding="utf-8").count("\n## ")

    result = OfferingService(settings).revise_package(
        PackageDraft(
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY, "決まったことを段取りに落とす"],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[2],
            basis="受注 2 件がどちらも継続している。",
        )
    )

    assert result.accepted is True, result.model_dump()
    assert result.recorded["最終更新"] == date.today().isoformat()
    assert result.recorded["新しい節か"] is False

    # 節は増えず、中身が差し替わる。
    text = packages.read_text(encoding="utf-8")
    assert text.count("\n## ") == before_sections
    assert text.count(f"\n## {PACKAGE_NAME}\n") == 1

    package = next(
        item
        for item in MarkdownRepository(settings).load().packages
        if item.name == PACKAGE_NAME
    )
    assert package.updated_on == date.today()
    assert package.hypothesis_state == settings.package_hypothesis_states[2]
    assert package.capabilities == [KNOWN_CAPABILITY, "決まったことを段取りに落とす"]
    # 入力が持たない欄（崩れる条件）は、前の定義の値をそのまま残し、残したことを断る。
    assert package.breaks_when
    assert any("崩れる条件" in warning for warning in result.warnings), result.warnings


def test_revise_package_adds_a_section_for_a_new_name(settings) -> None:
    """その名前の節が無いときは、新しい節を足す。"""
    packages = settings.path_for("packages")
    before_sections = packages.read_text(encoding="utf-8").count("\n## ")

    result = OfferingService(settings).revise_package(
        PackageDraft(
            name="引き継ぎまでを 1 本で受ける",
            capabilities=[KNOWN_CAPABILITY],
            buyer="担当者が 1 人で回している会社の事業責任者",
            hypothesis_state=settings.package_hypothesis_states[0],
        )
    )

    assert result.accepted is True, result.model_dump()
    assert result.recorded["新しい節か"] is True
    assert packages.read_text(encoding="utf-8").count("\n## ") == before_sections + 1
    names = [item.name for item in MarkdownRepository(settings).load().packages]
    assert "引き継ぎまでを 1 本で受ける" in names
