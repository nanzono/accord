"""機能を登記する操作のテスト。分類の出どころと、裏づけの節の実在を見る。"""

from __future__ import annotations

from pathlib import Path

from accord.models.results import CapabilityDraft
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
