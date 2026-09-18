"""MCP のツール 7 本と資源 1 本を開く、薄い皮。

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
    PublicRecordDraft,
    WriteResult,
)
from accord.services.consistency import ConsistencyService
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.services.positioning import PositioningService
from accord.services.public_records import PublicRecordService
from accord.vocabulary.settings import Settings

# ツールと資源の名前。README の「動かす」の表と同じ綴りで、変えない。
TOOL_NAMES = (
    "get_positioning",
    "assemble_material",
    "record_positioning",
    "register_capability",
    "register_public_record",
    "revise_package",
    "check_consistency",
)
ONTOLOGY_URI = "accord://ontology"


def as_date(text: str) -> date | None:
    """日付の引数を date に直す。読めない形と空は None にして、欠けた欄としてサービスに渡す。

    ここで例外を投げると、呼んだ側に返るのは「次の一手」を持たない失敗になる。欠けた欄として
    渡せば、書き方の例つきの拒否が返り、呼んだ側は同じ口をもう一度呼ぶだけで直せる。
    """
    try:
        return date.fromisoformat(str(text).strip())
    except ValueError:
        return None


INSTRUCTIONS = """accord は、案件獲得の正本（何ができるか、何をしてきたか、どう売るか）と、
そこから派生する対外表現が食い違わないようにする道具である。
セッションの初めに資源 accord://ontology を読み、いまの決めを get_positioning で読む。
文面を書く前に assemble_material で材料を取り出し、外に出す前に check_consistency を呼ぶ。
"""


def create_server(settings: Settings) -> MCPServer:
    """設定を 1 つ受け取り、ツール 7 本と資源 1 本を登録したサーバーを返す。"""
    positioning_service = PositioningService(settings)
    offering_service = OfferingService(settings)
    material_service = MaterialService(settings)
    consistency_service = ConsistencyService(settings)
    public_record_service = PublicRecordService(settings)

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
        """媒体向けの文面を書くための材料を取り出す。公開不可の節は落として警告に書く。

        package を渡すときは、パッケージ定義に実在する ID（パッケージ名ではない）を渡す。
        返る裏づけには、人が読む見出しと ID の両方が入る。
        """
        return material_service.assemble(
            MaterialRequest(channel=channel, package=package, opportunity=opportunity)
        )

    @mcp.tool()
    def record_positioning(
        decided_on: str,
        scope: str,
        headline_package: str,
        rationale: str,
        exceptions: list[PositioningException] | None = None,
    ) -> WriteResult:
        """売り方の決めを 1 ブロック登記する。必須の欄が欠けていれば書かずに拒否する。

        日付は `2026-09-16` の形で渡す。headline_package は、パッケージ定義に実在する ID
        （英小文字・数字・ハイフン）で、パッケージ名ではない。登記が通ると、その場で
        パッケージ定義の鮮度と、旧い束を宣言する提示物の件数（ファイル名つき）が返る。
        """
        return positioning_service.record(
            PositioningDraft(
                decided_on=as_date(decided_on),
                scope=scope,
                headline_package=headline_package,
                rationale=rationale,
                exceptions=list(exceptions or []),
            )
        )

    @mcp.tool()
    def register_capability(
        id: str,
        name: str,
        description: str,
        category: str,
        evidence_sections: list[str],
    ) -> WriteResult:
        """機能の台帳に 1 行足す。必須欄・分類・ID・裏づけが通らなければ書かずに拒否し、次の一手を返す。

        id は人が振る短い識別子（英小文字・数字・ハイフンで 3〜40 字、正本全体で重ならない値）。
        evidence_sections には、職歴の枠・受託案件・公開記録の ID を渡す（見出しや名前ではない）。
        拒否のときに返る候補はそのまま渡し直せる ID で、どの節のことかは拒否の文が表示名で添える。
        """
        return offering_service.register_capability(
            CapabilityDraft(
                id=id,
                name=name,
                description=description,
                category=category,
                evidence_sections=list(evidence_sections),
            )
        )

    @mcp.tool()
    def register_public_record(
        id: str,
        name: str,
        kind: str,
        published_on: str,
        publisher: str,
        role: str,
        url: str | None = None,
        origin_section: str | None = None,
        source: str | None = None,
    ) -> WriteResult:
        """公開記録（登壇・記事・リポジトリなど）を 1 ブロック登記する。必須の欄が欠けていれば書かずに拒否する。

        id は人が振る短い識別子（英小文字・数字・ハイフンで 3〜40 字、正本全体で重ならない値）で、
        機能の裏づけはこの ID でこの 1 件を指す。origin_section には、職歴の枠か受託案件の ID を
        渡す（見出しではない）。日付は `2020-03-10` の形で渡す。月までしか分からないときは
        `2020-03`、年だけなら `2020`。URL を持たない紙媒体のものは、URL を省いて渡す。
        """
        return public_record_service.register(
            PublicRecordDraft(
                id=id,
                name=name,
                kind=kind,
                published_on=published_on,
                url=url,
                publisher=publisher,
                role=role,
                origin_section=origin_section,
                source=source,
            )
        )

    @mcp.tool()
    def revise_package(
        id: str,
        name: str,
        capabilities: list[str],
        buyer: str,
        hypothesis_state: str,
        basis: str | None = None,
        source: str | None = None,
    ) -> WriteResult:
        """パッケージ定義を改訂する。台帳に無い機能の ID を束ねようとすれば書かずに拒否する。

        id は人が振る短い識別子（英小文字・数字・ハイフンで 3〜40 字、正本全体で重ならない値）で、
        決めと提示物はこの ID でこの束を指す。capabilities には機能の ID を渡す（機能名ではない）。
        通ると、その節を書き換えて最終更新日を今日に進める。節が無ければ新しく足す。
        """
        return offering_service.revise_package(
            PackageDraft(
                id=id,
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
