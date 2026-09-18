"""売り物の層（機能とパッケージ）に書く操作。制約を執行し、拒否のときは次の一手を組み立てる。

この文書は保管の仕方も通信の仕方も知らない。正本の読み書きはリポジトリに頼み、
判断に使う語彙（機能の分類の節など）は設定から受け取る。
"""

from __future__ import annotations

from datetime import date

from accord.models.constraints import CONSTRAINTS
from accord.models.ontology import field_example, missing_required_fields
from accord.models.results import (
    CapabilityDraft,
    NextAction,
    PackageDraft,
    Rejection,
    SourceSnapshot,
    WriteResult,
    close_names,
)
from accord.models.types import Capability, Package
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import Settings

# 制約は名前で参照する。名前を正本（ontology.yaml）で変えたら、ここで鍵が見つからず落ちる。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
EVIDENCE_SECTION_EXISTS = CONSTRAINT_BY_NAME["裏づけ節名の実在"].name
PACKAGE_CAPABILITY_MATCHES = CONSTRAINT_BY_NAME["束ねる機能名の一致"].name

# 次の 4 つは制約 7 つではなく、型 Capability と型 Package の欄の定義である
# （選べる分類と、選べる仮説の状態の語は設定が持つ）。
CAPABILITY_CATEGORY_ENUM = "機能の分類の列挙"
CAPABILITY_REQUIRED_FIELDS = "機能の必須欄"
PACKAGE_HYPOTHESIS_STATE_ENUM = "仮説の状態の列挙"
PACKAGE_REQUIRED_FIELDS = "パッケージの必須欄"

# 入力の欄を引くときの、型の名前。
CAPABILITY_TYPE_NAME = "Capability"
PACKAGE_TYPE_NAME = "Package"

# 操作の名前。次の一手にそのまま載せる。
REGISTER_OPERATION = "register_capability"
REVISE_OPERATION = "revise_package"

# パッケージを改訂するときに、入力が持たない欄。前の定義の値をそのまま残し、残したことを断る。
CARRIED_OVER_LABEL = "崩れる条件"

# 裏づけが公開記録のときに、公開可否の欄の代わりに書く語。公開記録は公開されているものである。
PUBLIC_RECORD_DISCLOSURE = "公開記録（外から確かめられる）"


class OfferingService:
    """機能を登記する、パッケージを改訂する。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def register_capability(self, draft: CapabilityDraft) -> WriteResult:
        """機能の台帳に 1 行足す。必須欄・分類・裏づけの節を確かめ、通らなければ書かずに拒否する。"""
        snapshot = self.repository.load()

        missing = missing_required_fields(CAPABILITY_TYPE_NAME, draft)
        if missing:
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=CAPABILITY_REQUIRED_FIELDS,
                    reason=(
                        "機能の必須の欄"
                        + "、".join(f"「{field.label}」" for field in missing)
                        + "が無い。名前と説明と裏づけがそろって初めて、仕事をしたと言える機能になる。"
                    ),
                    next_action=NextAction(
                        operation=REGISTER_OPERATION,
                        missing_fields=[field.label for field in missing],
                        example="\n".join(field_example(field) for field in missing),
                    ),
                ),
            )

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
                        operation=REGISTER_OPERATION,
                        candidates=list(categories),
                        example=f"分類には「{categories[0]}」のように、上の候補のどれかをそのまま渡す。",
                    ),
                ),
            )

        headings = snapshot.evidence_targets()
        unknown = [name for name in draft.evidence_sections if name not in headings]
        if unknown:
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=EVIDENCE_SECTION_EXISTS,
                    reason=(
                        f"裏づけの節「{unknown[0]}」は、"
                        "職歴の枠にも受託案件にも公開記録にも無い名前である。"
                    ),
                    next_action=NextAction(
                        operation=REGISTER_OPERATION,
                        candidates=close_names(unknown[0], headings),
                        example=f"上の候補をそのまま裏づけの節に渡して、もう一度 {REGISTER_OPERATION} を呼ぶ。",
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

        # 公開記録は定義により公開されているものなので、公開可否の欄を持たない。
        # 「不明」と並べると外に出せないものと読めるので、公開記録であることをそのまま書く。
        record_names = {record.name for record in snapshot.public_records}
        disclosure = {
            heading: (
                PUBLIC_RECORD_DISCLOSURE
                if heading in record_names
                else snapshot.disclosure_of(heading) or "不明"
            )
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
        """パッケージ定義の 1 節を改訂し、最終更新日を今日に進める。

        制約を先に全部見て、通ると決まってから 1 度だけ書き戻す。拒否のときは書き戻しに
        入らないので、パッケージ定義は 1 バイトも変わらない。
        最終更新日をこの操作が進めるのは、鮮度の制約（定義が決めより古くないこと）を
        満たす側がここだからである。
        """
        snapshot = self.repository.load()

        rejection = self._package_rejection(snapshot, draft)
        if rejection is not None:
            return WriteResult(accepted=False, rejection=rejection)

        previous = next((item for item in snapshot.packages if item.name == draft.name), None)
        carried, warnings = self._carried_over(previous, draft)

        package = Package(
            name=draft.name,
            buyer=draft.buyer,
            hypothesis_state=draft.hypothesis_state,
            capabilities=list(draft.capabilities),
            updated_on=date.today(),
            basis=carried["basis"],
            source=carried["source"],
            breaks_when=carried["breaks_when"],
        )
        self.repository.write_package(package)

        return WriteResult(
            accepted=True,
            recorded={
                "改訂したパッケージ": package.model_dump(mode="json"),
                "最終更新": package.updated_on.isoformat(),
                "新しい節か": previous is None,
            },
            warnings=warnings,
        )

    # ------------------------------------------------------------ 改訂の部品

    def _package_rejection(
        self, snapshot: SourceSnapshot, draft: PackageDraft
    ) -> Rejection | None:
        """改訂の入力を制約に当てる。通れば None を返し、通らなければ次の一手つきの拒否を返す。"""
        missing = missing_required_fields(PACKAGE_TYPE_NAME, draft)
        if missing:
            return Rejection(
                constraint=PACKAGE_REQUIRED_FIELDS,
                reason=(
                    "パッケージの必須の欄"
                    + "、".join(f"「{field.label}」" for field in missing)
                    + "が無い。売り物の定義は、誰に何を売るかがそろって初めて書ける。"
                ),
                next_action=NextAction(
                    operation=REVISE_OPERATION,
                    missing_fields=[field.label for field in missing],
                    example="\n".join(field_example(field) for field in missing),
                ),
            )

        states = self.settings.package_hypothesis_states
        if draft.hypothesis_state not in states:
            return Rejection(
                constraint=PACKAGE_HYPOTHESIS_STATE_ENUM,
                reason=(
                    f"仮説の状態「{draft.hypothesis_state}」は、"
                    f"設定ファイル {self.settings.config_path.name} が持つ語の一覧に無い。"
                ),
                next_action=NextAction(
                    operation=REVISE_OPERATION,
                    candidates=list(states),
                    example=f"仮説の状態には「{states[0]}」のように、上の候補のどれかをそのまま渡す。",
                ),
            )

        names = [item.name for item in snapshot.capabilities]
        unknown = [name for name in draft.capabilities if name not in names]
        if unknown:
            return Rejection(
                constraint=PACKAGE_CAPABILITY_MATCHES,
                reason=f"束ねる機能「{unknown[0]}」は、機能の台帳に無い名前である。",
                next_action=NextAction(
                    operation=REVISE_OPERATION,
                    candidates=close_names(unknown[0], names),
                    example=(
                        f"上の候補をそのまま束ねる機能に渡して、もう一度 {REVISE_OPERATION} を呼ぶ。"
                        f"まだ台帳に無い仕事を束ねるなら、先に機能を登記する（{REGISTER_OPERATION}）。"
                    ),
                ),
            )

        return None

    @staticmethod
    def _carried_over(
        previous: Package | None, draft: PackageDraft
    ) -> tuple[dict[str, str | None], list[str]]:
        """入力が持たない任意の欄を、前の定義から引き継ぐ。引き継いだ欄は断りに書く。

        改訂の入力は「崩れる条件」の欄を持たず、判定根拠と出典も省ける。省かれた欄を空にすると、
        前に書いた中身が改訂のたびに黙って消える。だから残し、残したことを言う。
        """
        carried: dict[str, str | None] = {
            "basis": draft.basis,
            "source": draft.source,
            "breaks_when": None,
        }
        if previous is None:
            return carried, []

        warnings: list[str] = []
        for name, label in (("basis", "判定根拠"), ("source", "出典")):
            if carried[name] is None and getattr(previous, name) is not None:
                carried[name] = getattr(previous, name)
                warnings.append(
                    f"「{label}」は入力に無かったので、前の定義の値をそのまま残した。"
                    f"変えるなら、{REVISE_OPERATION} にこの欄を入れてもう一度呼ぶ。"
                )
        if previous.breaks_when is not None:
            carried["breaks_when"] = previous.breaks_when
            warnings.append(
                f"「{CARRIED_OVER_LABEL}」はこの操作の入力に無い欄なので、"
                "前の定義の値をそのまま残した。変えるなら正本を直す。"
            )
        return carried, warnings
