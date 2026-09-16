"""売り物の層（機能とパッケージ）に書く操作。制約を執行し、拒否のときは次の一手を組み立てる。

この文書は保管の仕方も通信の仕方も知らない。正本の読み書きはリポジトリに頼み、
判断に使う語彙（機能の分類の節など）は設定から受け取る。
"""

from __future__ import annotations

import difflib

from accord.models.constraints import CONSTRAINTS
from accord.models.results import (
    CapabilityDraft,
    NextAction,
    PackageDraft,
    Rejection,
    WriteResult,
)
from accord.models.types import Capability
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import Settings

# 制約は名前で参照する。名前を正本（ontology.yaml）で変えたら、ここで鍵が見つからず落ちる。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
EVIDENCE_SECTION_EXISTS = CONSTRAINT_BY_NAME["裏づけ節名の実在"].name
PACKAGE_CAPABILITY_MATCHES = CONSTRAINT_BY_NAME["束ねる機能名の一致"].name

# 分類の列挙は制約 7 つではなく、型 Capability の欄の定義である（選べる語は設定が持つ）。
CAPABILITY_CATEGORY_ENUM = "機能の分類の列挙"

# 候補を探すときの緩さ。近い名前が 1 つも出ないときは、実在する名前をそのまま並べる。
CLOSE_MATCH_CUTOFF = 0.3
CLOSE_MATCH_COUNT = 3
FALLBACK_COUNT = 5


def _candidates(wanted: str, pool: list[str]) -> list[str]:
    """実在する名前のうち、渡された名前に近いものを返す。近いものが無ければ先頭から並べる。"""
    close = difflib.get_close_matches(wanted, pool, n=CLOSE_MATCH_COUNT, cutoff=CLOSE_MATCH_CUTOFF)
    return close or pool[:FALLBACK_COUNT]


class OfferingService:
    """機能を登記する、パッケージを改訂する。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def register_capability(self, draft: CapabilityDraft) -> WriteResult:
        """機能の台帳に 1 行足す。分類と裏づけの節を確かめ、通らなければ書かずに拒否する。"""
        snapshot = self.repository.load()

        categories = self.settings.capability_categories
        if draft.category not in categories:
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=CAPABILITY_CATEGORY_ENUM,
                    reason=(
                        f"分類「{draft.category}」は機能の台帳の節に無い。"
                        f"分類は設定ファイル {self.settings.config_path.name} が持つ節の名前に限る。"
                    ),
                    next_action=NextAction(
                        operation="register_capability",
                        candidates=list(categories),
                        example=f"分類には「{categories[0]}」のように、上の候補のどれかをそのまま渡す。",
                    ),
                ),
            )

        headings = snapshot.section_headings()
        if not draft.evidence_sections:
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=EVIDENCE_SECTION_EXISTS,
                    reason="裏づけの節が 1 つも無い。機能は、その仕事をしたと言える節を 1 つ以上指す。",
                    next_action=NextAction(
                        operation="register_capability",
                        missing_fields=["裏づけの節"],
                        candidates=headings[:FALLBACK_COUNT],
                        example="裏づけの節には、職歴の枠か受託案件の見出しをそのまま渡す。",
                    ),
                ),
            )

        unknown = [name for name in draft.evidence_sections if name not in headings]
        if unknown:
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=EVIDENCE_SECTION_EXISTS,
                    reason=(
                        f"裏づけの節「{unknown[0]}」は、職歴の枠にも受託案件にも無い見出しである。"
                    ),
                    next_action=NextAction(
                        operation="register_capability",
                        candidates=_candidates(unknown[0], headings),
                        example="上の候補をそのまま裏づけの節に渡して、もう一度 register_capability を呼ぶ。",
                    ),
                ),
            )

        capability = Capability(
            name=draft.name,
            description=draft.description,
            category=draft.category,
            evidence_sections=list(draft.evidence_sections),
        )
        self.repository.append_capability(capability)

        disclosure = {
            heading: snapshot.disclosure_of(heading) or "不明"
            for heading in capability.evidence_sections
        }
        warnings = [
            f"裏づけの節「{heading}」は {state} なので、対外の文面には出せない。"
            for heading, state in disclosure.items()
            if state.startswith("公開不可")
        ]

        return WriteResult(
            accepted=True,
            recorded={
                "機能": capability.model_dump(mode="json"),
                "裏づけの節の公開可否": disclosure,
            },
            warnings=warnings,
        )

    def revise_package(self, draft: PackageDraft) -> WriteResult:
        """パッケージ定義を改訂する（書きの操作 3 つの段で実装する）。"""
        return WriteResult(
            accepted=False,
            rejection=Rejection(
                constraint=PACKAGE_CAPABILITY_MATCHES,
                reason=(
                    "この操作は後の段で実装する。いまはパッケージ定義を 1 バイトも変えない。"
                ),
                next_action=NextAction(
                    operation="revise_package",
                    example="書きの操作 3 つの段が済んでから、同じ入力でもう一度呼ぶ。",
                ),
            ),
        )
