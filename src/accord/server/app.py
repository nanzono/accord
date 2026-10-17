"""MCP のツール 23 本と資源 1 本を開く、薄い皮。

この文書がするのは、引数の型を確かめてサービスに渡し、返ってきた型をそのまま返すことだけである。
制約の判断はサービスにあり、正本の在処はリポジトリにある。移行の前の置き場で移行のほかの操作を
断るかどうかも、書き込みの記録（WriteRecorder）が判断し、ここはその断りを各操作の返り値の型に詰めるだけである。ここに業務の判断を書かないのは、
同じサービスをコマンドの道具からも呼べる形に残すためである。
"""

from __future__ import annotations

from datetime import date

from mcp.server import MCPServer

from accord.models.ontology import Ontology, load_ontology
from accord.models.results import (
    CapabilityDraft,
    ConsistencyReport,
    ExportResult,
    FactSearch,
    Material,
    MaterialRequest,
    PackageDraft,
    PositioningDraft,
    PositioningException,
    PositioningView,
    PublicRecordDraft,
    SectionList,
    SectionText,
    WriteResult,
)
from accord.services.consistency import ConsistencyService
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.services.positioning import PositioningService
from accord.services.public_records import PublicRecordService
from accord.services.recording import (
    HistoryService,
    MigrationService,
    VocabularyService,
    WriteRecorder,
)
from accord.services.sections import SectionService
from accord.services.watch import SourceWatch
from accord.vocabulary.settings import Settings

# ツールと資源の名前。README の「動かす」の表と同じ綴りで、変えない。
# spec: REQ-526
TOOL_NAMES = (
    "get_positioning",
    "assemble_material",
    "record_positioning",
    "register_capability",
    "register_public_record",
    "revise_package",
    "check_consistency",
    "list_sections",
    "read_section",
    "search_facts",
    "record_fact",
    "revise_section",
    "rename_heading",
    "add_section",
    "remove_section",
    "move_section",
    "set_disclosure",
    "export_source",
    "add_term",
    "remove_term",
    "revert_commit",
    "discard_uncommitted",
    "migrate_data",
)
ONTOLOGY_URI = "accord://ontology"

# 材料の取り出しの返り値の文字数の上限として、MCP のクライアントに宣言する値と鍵。
# 経歴の正本の全節を 1 回で返すので、宣言の無い既定の上限（5 万字）を超えうる。
MAX_RESULT_SIZE_KEY = "anthropic/maxResultSizeChars"
MATERIAL_MAX_RESULT_SIZE = 500_000


def as_date(text: str) -> date | None:
    """日付の引数を date に直す。読めない形と空は None にして、欠けた欄としてサービスに渡す。

    ここで例外を投げると、呼んだ側に返るのは「次の一手」を持たない失敗になる。欠けた欄として
    渡せば、書き方の例つきの拒否が返り、呼んだ側は同じ口をもう一度呼ぶだけで直せる。
    """
    try:
        return date.fromisoformat(str(text).strip())
    except ValueError:
        return None


# spec: REQ-463
# spec: REQ-487
# spec: REQ-500
# spec: REQ-527
INSTRUCTIONS = """accord は、案件獲得の正本（何ができるか、何をしてきたか、どう売るか）と、
そこから派生する対外表現が食い違わないようにする道具である。
正本のファイルを直接開かず、accord の操作で読み書きする。正本の置き場は教えない。
セッションの初めに資源 accord://ontology を読み、いまの決めを get_positioning で読む。
応募文・プロフィール・職務経歴書を書く前に assemble_material を 1 回呼ぶ。経歴の節がすべてそろう。
事実を確かめるときは list_sections・read_section・search_facts で読む。
実績や経歴の事実を書き足すときは record_fact、節を直すときは read_section で読んでから revise_section を呼ぶ。
見出しの変更と節の追加と節の削除と節の移動と公開可否の変更も accord の操作で行う。
見出しは rename_heading、節を足すのは add_section、消すのは remove_section、動かすのは move_section、
公開可否は set_disclosure で変える。どれも read_section で読んだ指紋を渡す（節を足すときは要らない）。
語彙の変更と取り消しと未コミットの変更を捨てることと移行も accord の操作で行い、置き場のファイルを直接書かない。
語彙の語を足すのは add_term、消すのは remove_term、accord のコミット 1 件を打ち消すのは revert_commit、
accord を通さない未コミットの変更を捨てるのは discard_uncommitted、前の版の置き場を移すのは migrate_data。
書き込みが、未コミットの変更か accord 以外のコミットで断られたら、依頼した人に確かめてから、断りの次の一手を呼ぶ。
外に出す前に check_consistency を呼ぶ。
"""


def create_server(settings: Settings, watch: SourceWatch | None = None) -> MCPServer:
    """設定を 1 つ受け取り、ツール 23 本と資源 1 本を登録したサーバーを返す。

    読みの前の整合の検査（watch）は、読みの操作のすべてで 1 つを共有する。起動時の検査の結果も
    これに残るので、起動後の最初の読みは、正本が変わっていなければ検査を走らせ直さない。
    """
    watch = watch or SourceWatch(settings)
    recorder = WriteRecorder(settings)
    migration_service = MigrationService(settings, recorder=recorder)
    vocabulary_service = VocabularyService(settings, recorder=recorder)
    history_service = HistoryService(settings, recorder=recorder)
    positioning_service = PositioningService(settings, recorder=recorder, watch=watch)
    offering_service = OfferingService(settings, recorder=recorder)
    material_service = MaterialService(settings, watch=watch)
    consistency_service = ConsistencyService(settings)
    public_record_service = PublicRecordService(settings, recorder=recorder)
    section_service = SectionService(settings, recorder=recorder, watch=watch)

    mcp = MCPServer("accord", instructions=INSTRUCTIONS)

    @mcp.tool()
    def get_positioning(channel: str | None = None) -> PositioningView:
        """いまの決め（看板）を読む。媒体を省くと全体に適用される決めを返す。"""
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("get_positioning")) is not None:
            return PositioningView(rejection=blocked)
        return positioning_service.current(channel)

    # spec: REQ-424
    # spec: REQ-464
    @mcp.tool(meta={MAX_RESULT_SIZE_KEY: MATERIAL_MAX_RESULT_SIZE})
    def assemble_material(
        channel: str,
        package: str | None = None,
        opportunity: str | None = None,
    ) -> Material:
        """応募文・プロフィール・職務経歴書を書く前に、これを 1 回呼ぶ。文面の材料を 1 回でそろえて返す。

        channel には媒体の名前か、語彙の決めの適用先の語（媒体ではない書く先）を渡す。返るのは、いまの決め、
        看板のパッケージ、束ねる機能、裏づけの節、公開記録、媒体の規約、禁じた言い回し、そして
        経歴の正本の節のすべて（公開不可の節は下位の節ごと落とし、落としたことを警告に書く）である。
        package を渡すときは、パッケージ定義に実在する ID（パッケージ名ではない）を渡す。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("assemble_material")) is not None:
            return Material(channel=channel, rejection=blocked)
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
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("record_positioning")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
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
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("register_capability")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
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
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("register_public_record")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
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
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("revise_package")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
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
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("check_consistency")) is not None:
            return ConsistencyReport(rejection=blocked)
        return consistency_service.inspect(scope)

    @mcp.tool()
    def list_sections(file: str | None = None) -> SectionList:
        """正本の節を一覧にする（ファイルの名前・見出しの道筋・指紋・字数。ID の欄があれば ID と公開可否）。

        file を省くと正本のすべてのファイル、渡すとそのファイルだけ。ファイルの名前は accord の形の名前
        （例 career_master.md）で、知らない名前を渡すと正本のファイルの名前が候補に返る。正本は変えない。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("list_sections")) is not None:
            return SectionList(rejection=blocked)
        return section_service.list_sections(file)

    @mcp.tool()
    def read_section(section: str) -> SectionText:
        """節を 1 つ読み、本文と指紋を返す。正本は変えない。

        section には節の ID か見出しの道筋（最上位の見出しから「 > 」でつないだもの）を渡す。
        同じ道筋の節が 2 つ以上あるときは、候補の「ファイルの名前 :: 見出しの道筋」をそのまま渡す。
        本文に下位の見出しの節は含まない。節を書き換えるときは、ここで得た指紋を渡す。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("read_section")) is not None:
            return SectionText(rejection=blocked)
        return section_service.read_section(section)

    @mcp.tool()
    def search_facts(query: str) -> FactSearch:
        """語を含む行を、ファイルの名前と見出しの道筋と行の文で返す。正本は変えない。

        全角と半角、大文字と小文字の違いは同じ文字として扱う。当たりが 50 件を超えたら、
        先頭の 50 件と当たった総数を返す。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("search_facts")) is not None:
            return FactSearch(query=query, rejection=blocked)
        return section_service.search_facts(query)

    # spec: REQ-465
    @mcp.tool()
    def record_fact(section: str, fact: str, source: str, date: str) -> WriteResult:
        """実績や経歴の事実を書き足すときに呼ぶ。経歴の正本の節 1 つの末尾に、事実を 1 行足す。

        section は経歴の正本の節の ID か見出しの道筋、fact は事実の文（1 行）、source は出所
        （確かめた先）、date は `2026-10-13` の形の日付。書く行は「- 事実の文（日付、出所: 出所）」。
        通ると、足した行と節の新しい指紋と、読み比べるべき写し（職務経歴書の台帳など）が返る。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("record_fact")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        return section_service.record_fact(section, fact, source, date)

    @mcp.tool()
    def revise_section(
        section: str,
        body: str,
        fingerprint: str,
        reason: str,
        disclosures: list[str] | None = None,
    ) -> WriteResult:
        """節 1 つの本文を書き換える。read_section で読んでから、そのとき得た指紋を添えて呼ぶ。

        正本のどのファイルの節も書ける。見出しの行と下位の節は変わらない。本文に見出しの行を書くと断る
        （節を足すのは add_section、見出しを変えるのは rename_heading）。ID の欄は元の値のまま残す。
        公開可否の行を足す・消す・並べ替える・値を変えるときは、書いた後の公開可否の行の値を上から順に
        disclosures に並べて渡す（申告）。申告が無いか実際の並びと違えば書かない。通ると、変わる前と後の
        公開可否の行が返り、コミットの説明にも残る。公開可否の行を 2 行以上持つ節では、公開可否の行の無い
        箇条書きの項目を増やせない。読んだ後に誰かが直していれば（指紋が違えば）書かない。書いた後に
        整合の検査の違反か読めないブロックが新しく出るなら書かない。reason は何をなぜ直すかの 1 文。
        通ると、節の新しい指紋と、読み比べるべき写しが返る。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("revise_section")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        return section_service.revise_section(section, body, fingerprint, reason, disclosures)

    @mcp.tool()
    def rename_heading(section: str, heading: str, fingerprint: str, reason: str) -> WriteResult:
        """節の見出しの文字だけを変える。深さ・本文・下位の節は変わらない。

        section は節の ID か見出しの道筋、heading は「#」を付けない新しい見出しの文字（1 行）、
        fingerprint は read_section で得た指紋、reason は何をなぜ変えるかの 1 文。
        ファイルの 1 行目の見出しもこれで変える。通ると、変えたファイルを 1 件のコミットにする。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("rename_heading")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        return section_service.rename_heading(section, heading, fingerprint, reason)

    @mcp.tool()
    def add_section(
        heading: str,
        body: str,
        reason: str,
        parent: str | None = None,
        file: str | None = None,
        before: str | None = None,
    ) -> WriteResult:
        """節を 1 つ足す。parent を渡すと、その節より 1 段深い節を親の下位の節の末尾に置く。

        parent は親の節の ID か見出しの道筋。parent を渡さずに file（正本のファイルの名前）を渡すと、
        そのファイルの末尾に深さ 1 の節を足す（parent と file の両方を渡すと、親をそのファイルの中で探す。
        file が正本のファイルに無い名前なら、parent があっても断る）。heading は「#」を付けない見出しの文字、body は本文
        （見出しの行を含めない。下位の節は、足した節を親にしてもう一度呼んで作る）、reason は理由の 1 文。
        before に親の直下の節（parent が無ければ深さ 1 の節）を渡すと、その節の直前に置く
        （新しい順に並べる正本のため）。通ると、変えたファイルを 1 件のコミットにする。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("add_section")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        return section_service.add_section(parent, heading, body, reason, before, file)

    @mcp.tool()
    def remove_section(section: str, fingerprint: str, reason: str) -> WriteResult:
        """節の見出しの行と本文を消す。下位の節を持つ節は消さない（先に下位の節を消す）。

        fingerprint は read_section で得た指紋、reason は何をなぜ消すかの 1 文。ほかの項目がこの節の
        ID を指していれば、書いた後の検査が違反を出すので消さない。通ると、変えたファイルを 1 件のコミットにする。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("remove_section")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        return section_service.remove_section(section, fingerprint, reason)

    @mcp.tool()
    def move_section(
        section: str,
        fingerprint: str,
        reason: str,
        new_parent: str | None = None,
        before: str | None = None,
        file: str | None = None,
    ) -> WriteResult:
        """節を下位の節ごと、新しい親の節の下へ動かす。同じ親の中の並べ替えにも使う。

        深さは新しい親より 1 段深くそろえ、下位の節も同じ段数ずらす。既定では新しい親の下位の末尾、
        before に新しい親の直下の節を渡すとその直前に置く。new_parent を渡さなければ、同じファイルの
        深さ 1 の節として末尾へ動かす（before に深さ 1 の節を渡せばその直前。深さ 1 の節どうしの
        並べ替えもこれで行う）。ファイルをまたいでは動かせない。fingerprint は動かす節を read_section で
        読んだ指紋。file に正本のファイルの名前を渡すと、動かす節と新しい親をそのファイルの中で探す
        （正本のファイルに無い名前なら断る）。通ると、1 件のコミットにする。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("move_section")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        return section_service.move_section(section, new_parent, fingerprint, reason, before, file)

    @mcp.tool()
    def set_disclosure(
        section: str,
        disclosure: str,
        fingerprint: str,
        reason: str,
        line: int | None = None,
    ) -> WriteResult:
        """ID の欄を持つ節の公開可否を変える。欄が無ければ ID の欄の行の直後に足す。

        disclosure は新しい公開可否の 1 行（「公開不可」で始まる値は材料に載らない）。
        「公開不可」で始まる値から外すと、材料の取り出しに新しく出ることと、元の値・新しい値・理由が返る。
        fingerprint は read_section で得た指紋、reason は理由の 1 文。通ると、元の値と新しい値を書いた
        1 件のコミットにする。公開可否の行を 2 行以上持つ節では、line に何行目か（1 始まり）を渡し、
        その行だけを変える。line が無いか当たらなければ書かずに、いまの公開可否の行を番号つきで返す。
        """
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("set_disclosure")) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        return section_service.set_disclosure(section, disclosure, fingerprint, reason, line)

    @mcp.tool()
    def export_source(path: str) -> ExportResult:
        """正本の各ファイルを 1 つの Markdown につないで、path に書く。

        path は経歴データの置き場の外のファイルを指す（中を指すと書かずに断る）。返るのは書いたファイルの
        名前と字数だけ。正本は変えない。
        """
        # spec: REQ-525
        # spec: REQ-522
        if (blocked := recorder.migration_refusal("export_source")) is not None:
            return ExportResult(written=False, rejection=blocked)
        return section_service.export_source(path)

    @mcp.tool()
    def add_term(kind: str, term: str, reason: str) -> WriteResult:
        """語彙（vocabulary.md）の種類の節の末尾に、語を 1 行足す。

        kind は語彙の種類の名前（媒体・決めの適用先・機能の分類・パッケージの仮説の状態・公開記録の種類・
        公開記録の役割のどれか）、term は足す語（改行を含まない 1 行。その種類に既にある語は足さない）、
        reason は何をなぜ足すかの 1 文。通ると、その種類の語の一覧を返し、1 件のコミットにする。
        語を直すときは、新しい語を足し、使っている節を revise_section で直してから、古い語を remove_term で消す。
        """
        # spec: REQ-508
        return vocabulary_service.add_term(kind, term, reason)

    @mcp.tool()
    def remove_term(kind: str, term: str, reason: str) -> WriteResult:
        """語彙（vocabulary.md）の種類の節から、語の行を消す。正本の節が使っている語は消さない。

        kind は語彙の種類の名前、term は消す語、reason は何をなぜ消すかの 1 文。使っている節があれば、
        その節の見出しの道筋を返して消さない（先に revise_section で直す）。媒体の語は、提示物の置き場に
        同じ名前のディレクトリがあれば、そのディレクトリの名前を返して消さない。通ると 1 件のコミットにする。
        """
        # spec: REQ-510
        return vocabulary_service.remove_term(kind, term, reason)

    @mcp.tool()
    def revert_commit(commit: str, reason: str) -> WriteResult:
        """置き場の履歴のコミット 1 件の変更を打ち消すコミットを 1 件作る。

        commit はコミットの短い識別子か長い識別子（断りの候補に返るものをそのまま渡す）、reason は何をなぜ
        取り消すかの 1 文。移行のコミットとそれより前のコミット、合流のコミット、既に打ち消したコミットは
        取り消さない。後のコミットとぶつかるときと、打ち消した後に新しい整合の検査の違反が出るときは、
        置き場をそのままにして断る。accord 以外のコミットがあっても呼べる（それを打ち消すための操作）。
        """
        # spec: REQ-517
        return history_service.revert_commit(commit, reason)

    @mcp.tool()
    def discard_uncommitted(reason: str) -> WriteResult:
        """置き場の accord を通さない未コミットの変更を捨て、作業ツリーを最後のコミットの状態に戻す。

        reason は何をなぜ捨てるかの 1 文。捨てる前の差分（最後のコミットとの差分と、追跡していない
        ファイルの名前と中身）と、捨てたファイルの名前を返す。頼まれた直しが差分に入っていれば、
        捨てた後に accord の操作でやり直す。捨てる変更が無ければ、何もせずに空の差分を返す。
        """
        # spec: REQ-521
        return history_service.discard_uncommitted(reason)

    @mcp.tool()
    def migrate_data() -> WriteResult:
        """移行の前の置き場（設定ファイル accord.toml があり vocabulary.md が無い）を、accord の形の置き場にする。

        引数は無い。accord.toml の置き場の節と読み方の節が accord の形と同じことを確かめ、違えば違う鍵と
        accord の形の値を返して移行しない。同じなら、語彙の節から vocabulary.md を作り、accord.toml を消し、
        その 2 つを 1 件のコミットにする。返るのは、作ったファイル・消したファイル・種類ごとの語の数。
        移行の前の置き場では、ほかの操作はどれもこの操作を指して断る。移行済みの置き場では断る。
        """
        # spec: REQ-523
        return migration_service.migrate_data()

    # spec: REQ-337
    @mcp.resource(ONTOLOGY_URI)
    def ontology() -> Ontology:
        """型・関係・制約の定義を返す。セッションの初めに読む。"""
        return load_ontology()

    return mcp
