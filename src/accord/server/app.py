"""MCP のツール 6 本と資源 1 本を開く、薄い皮。

この文書がするのは、引数の型を確かめてサービスに渡し、返ってきた型をそのまま返すことだけである。
制約の判断はサービスにあり、正本の在処はリポジトリにある。ここに業務の判断を書かないのは、
同じサービスをコマンドの道具からも呼べる形に残すためである。
"""

from __future__ import annotations

from datetime import date

from mcp.server import MCPServer

from accord.models.ontology import Ontology, load_ontology
from accord.models.results import (
    CapabilityDraft,
    ConsistencyReport,
    Material,
    MaterialRequest,
    PackageDraft,
    PositioningDraft,
    PositioningException,
    PositioningView,
    WriteResult,
)
from accord.services.consistency import ConsistencyService
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.services.positioning import PositioningService
from accord.vocabulary.settings import Settings

# ツールと資源の名前。README の「動かす」の表と同じ綴りで、変えない。
TOOL_NAMES = (
    "get_positioning",
    "assemble_material",
    "record_positioning",
    "register_capability",
    "revise_package",
    "check_consistency",
)
ONTOLOGY_URI = "accord://ontology"

INSTRUCTIONS = """accord は、案件獲得の正本（何ができるか、何をしてきたか、どう売るか）と、
そこから派生する対外表現が食い違わないようにする道具である。
セッションの初めに資源 accord://ontology を読み、いまの決めを get_positioning で読む。
文面を書く前に assemble_material で材料を取り出し、外に出す前に check_consistency を呼ぶ。
"""


def create_server(settings: Settings) -> MCPServer:
    """設定を 1 つ受け取り、ツール 6 本と資源 1 本を登録したサーバーを返す。"""
    positioning_service = PositioningService(settings)
    offering_service = OfferingService(settings)
    material_service = MaterialService(settings)
    consistency_service = ConsistencyService(settings)

    mcp = MCPServer("accord", instructions=INSTRUCTIONS)

    @mcp.tool()
    def get_positioning(channel: str | None = None) -> PositioningView:
        """いまの決め（看板）を読む。媒体を省くと全体に適用される決めを返す。"""
        return positioning_service.current(channel)

    @mcp.tool()
    def assemble_material(
        channel: str,
        package: str | None = None,
        opportunity: str | None = None,
    ) -> Material:
        """媒体向けの文面を書くための材料を取り出す。公開不可の節は落として警告に書く。"""
        return material_service.assemble(
            MaterialRequest(channel=channel, package=package, opportunity=opportunity)
        )

    @mcp.tool()
    def record_positioning(
        decided_on: date,
        scope: str,
        headline_package: str,
        rationale: str,
        exceptions: list[PositioningException] | None = None,
    ) -> WriteResult:
        """売り方の決めを 1 ブロック登記する。必須の欄が欠けていれば書かずに拒否する。"""
        return positioning_service.record(
            PositioningDraft(
                decided_on=decided_on,
                scope=scope,
                headline_package=headline_package,
                rationale=rationale,
                exceptions=list(exceptions or []),
            )
        )

    @mcp.tool()
    def register_capability(
        name: str,
        description: str,
        category: str,
        evidence_sections: list[str],
    ) -> WriteResult:
        """機能の台帳に 1 行足す。分類か裏づけの節が通らなければ書かずに拒否し、候補を返す。"""
        return offering_service.register_capability(
            CapabilityDraft(
                name=name,
                description=description,
                category=category,
                evidence_sections=list(evidence_sections),
            )
        )

    @mcp.tool()
    def revise_package(
        name: str,
        capabilities: list[str],
        buyer: str,
        hypothesis_state: str,
        basis: str | None = None,
        source: str | None = None,
    ) -> WriteResult:
        """パッケージ定義を改訂する。台帳に無い機能名を束ねようとすれば書かずに拒否する。"""
        return offering_service.revise_package(
            PackageDraft(
                name=name,
                capabilities=list(capabilities),
                buyer=buyer,
                hypothesis_state=hypothesis_state,
                basis=basis,
                source=source,
            )
        )

    @mcp.tool()
    def check_consistency(scope: str | None = None) -> ConsistencyReport:
        """正本を制約に当て、違反の一覧を直し先つきで返す。正本は変えない。

        範囲は、省略か「全体」で正本全体、媒体の名前でその媒体、提示物のファイル名でその 1 件。
        実在しない名前を渡したときは、拒否ではなく実在する範囲の一覧が返る。
        """
        return consistency_service.inspect(scope)

    @mcp.resource(ONTOLOGY_URI)
    def ontology() -> Ontology:
        """型・関係・制約の定義を返す。セッションの初めに読む。"""
        return load_ontology()

    return mcp
