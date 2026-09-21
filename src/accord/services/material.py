"""文面の材料を取り出す操作。

媒体向けの文面を書く工程に入ったときに 1 回呼ばれ、正本の通読の代わりになる材料を返す。
返すのは、適用される決め、看板のパッケージ、束ねる機能、各機能の裏づけの節、裏づけになっている
公開記録、媒体の規約、禁じた言い回し、そして警告の一覧である。

この操作が執行する制約は 1 つ、「提出物に含まれる事実は公開可の節に限る」である。
公開不可の節は材料に載せず、落としたことと節の名前を警告に書く。落としたことを黙っていると、
受け取った側は「その節は無い」と読んで、別の裏づけを探しに正本を開く羽目になるからである。

決めの選び方と、決めが未登記のときの次の一手は、いまの決めを読む操作（positioning）が持つ。
旧い束を宣言する提示物と未反映の注記の判定は、整合検査（consistency）が持つ。どちらも
この文書には書き直さない。同じ判定が 2 か所にあると、片方だけ直したときに、材料の警告と
検査の一覧が食い違うからである。
"""

from __future__ import annotations

from accord.models.constraints import CONSTRAINTS
from accord.models.results import (
    Material,
    MaterialRequest,
    SourceSnapshot,
    fold_names,
    labelled,
)
from accord.models.types import Capability, Package, PublicRecord
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.positioning import PositioningService, unknown_channel_notes
from accord.vocabulary.settings import PRESENTATION_RULES_KEY, Settings

# 制約は名前で参照する。名前を正本（ontology.yaml）で変えたら、ここで鍵が見つからず落ちる。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
NOTE_AND_SOURCE_SECTION = CONSTRAINT_BY_NAME["注記と出典の節の実在・公開可否"].name

# 操作の名前。次の一手にそのまま載せる。
ASSEMBLE_OPERATION = "assemble_material"
INSPECT_OPERATION = "check_consistency"

# 裏づけの節を材料に載せるときの、欄の名前。
# 見出しには人が読む表示名を入れ、ID は隣の欄で添える。文面を書く側が読むのは表示名と本文で、
# ID だけを渡すとどの節のことか伝わらない。逆に ID を落とすと、正本に戻る道が消える。
EVIDENCE_HEADING_KEY = "見出し"
EVIDENCE_ID_KEY = "ID"
EVIDENCE_DISCLOSURE_KEY = "公開可否"
EVIDENCE_BODY_KEY = "本文"

# 警告に名前を並べるときに、名前で見せる数。残りは件数に畳む。
NAME_SAMPLE_COUNT = 5


class MaterialService:
    """媒体向けの文面を書くための材料を、正本から射影して返す。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def assemble(self, request: MaterialRequest) -> Material:
        """材料を組み立てる。正本は 1 バイトも書き換えない。"""
        channel = request.channel
        # spec: REQ-101
        if channel not in self.settings.channels:
            return Material(
                channel=channel,
                warnings=unknown_channel_notes(self.settings, channel, ASSEMBLE_OPERATION),
            )

        snapshot = self.repository.load()
        # spec: REQ-084
        view = PositioningService(self.settings, self.repository).current(channel)
        warnings = list(view.warnings)

        # spec: REQ-103
        if view.positioning is None:
            # 決めが未登記（または当たる決めが無い）。読む側の次の一手は view が持っている。
            return Material(channel=channel, warnings=warnings)

        package, package_notes = self._package(snapshot, request, view.package)
        if package is None:
            # 名前が実在しないか、看板の束がパッケージ定義に無い。どちらも直し方を断りに載せて返す。
            return Material(
                channel=channel,
                positioning=view.positioning,
                warnings=warnings + package_notes,
            )

        capabilities, unknown_capabilities = self._capabilities(snapshot, package)
        warnings.extend(unknown_capabilities)

        evidence, public_records, evidence_warnings = self._evidence(snapshot, capabilities)
        warnings.extend(evidence_warnings)
        warnings.extend(self._unused_public_record_warnings(snapshot))

        # spec: REQ-090
        channel_rules = self.repository.channel_rules(channel)
        # spec: REQ-091
        forbidden_phrases = self.repository.forbidden_phrases()
        warnings.extend(
            self._presentation_rule_warnings(channel, channel_rules, forbidden_phrases)
        )

        warnings.extend(self._inspection_warnings(channel))

        if request.opportunity is not None:
            # spec: REQ-106
            warnings.append(
                f"案件「{request.opportunity}」は受け取ったが、第 1 版の材料には反映しない。"
                "求人票の必須条件とこの材料の突き合わせは、材料を読む側が行う。"
            )

        return Material(
            channel=channel,
            positioning=view.positioning,
            package=package,
            capabilities=capabilities,
            evidence=evidence,
            public_records=public_records,
            channel_rules=channel_rules,
            forbidden_phrases=forbidden_phrases,
            warnings=warnings,
        )

    # ------------------------------------------------------------ 組み立ての部品

    def _package(
        self, snapshot: SourceSnapshot, request: MaterialRequest, headline: Package | None
    ) -> tuple[Package | None, list[str]]:
        """材料の土台にするパッケージと、選べなかったときの断りを返す。

        ID を渡されたときはその ID で引き、省かれたときはその媒体の決めが前面に出す束を使う。
        渡された ID が実在しないときは、パッケージを返さず、実在する ID の一覧と次の一手を返す。
        """
        if request.package is None:
            return headline, []

        # spec: REQ-085
        found = next((item for item in snapshot.packages if item.id == request.package), None)
        if found is not None:
            return found, []

        fallback = ""
        if headline is not None:
            fallback = (
                f"package を省くと、この媒体の決めが前面に出す束"
                f"「{headline.name}」（{headline.id}）で組み立てる。"
            )
        # spec: REQ-099
        return None, [
            f"パッケージ「{request.package}」は、パッケージ定義に無い ID である。",
            # spec: REQ-100
            "実在するパッケージ: "
            + " / ".join(labelled(item.id, {item.id: item.name}) for item in snapshot.packages),
            f"上の ID のどれかを package に渡して、もう一度 {ASSEMBLE_OPERATION} を呼ぶ。"
            + fallback,
        ]

    def _capabilities(
        self, snapshot: SourceSnapshot, package: Package
    ) -> tuple[list[Capability], list[str]]:
        """パッケージが束ねる機能を、機能の台帳から ID で引く。台帳に無い ID は断りにする。"""
        by_id = {item.id: item for item in snapshot.capabilities}
        found: list[Capability] = []
        warnings: list[str] = []

        # spec: REQ-086
        for name in package.capabilities:
            capability = by_id.get(name)
            if capability is None:
                # spec: REQ-095
                warnings.append(
                    f"束「{package.name}」が束ねる機能「{name}」が機能の台帳に無いので、"
                    f"この機能の裏づけは材料に入っていない。直し先は {INSPECT_OPERATION} が返す。"
                )
                continue
            found.append(capability)
        return found, warnings

    def _evidence(
        self, snapshot: SourceSnapshot, capabilities: list[Capability]
    ) -> tuple[list[dict[str, str]], list[PublicRecord], list[str]]:
        """各機能の裏づけの節を、表示名・ID・本文で集める。公開不可の節は落として警告に書く。

        裏づけは ID で書かれていて、職歴の枠か受託案件の節を指すこともあれば、公開記録を指す
        こともある。公開記録は節ではなく 1 件ぶんの型なので、先に取り分けて別の欄で返す。
        取り分けないと「職歴の枠にも受託案件にも無い」として警告に落ちてしまう。
        同じ節を複数の機能が指すことがあるので、ID で重複を落とす。
        ここが、ID を人が読む表示名に戻す唯一の場所である。
        """
        bodies = self.repository.evidence_bodies()
        records = {record.id: record for record in snapshot.public_records}
        labels = snapshot.labels()
        evidence: list[dict[str, str]] = []
        public_records: list[PublicRecord] = []
        warnings: list[str] = []
        seen: set[str] = set()

        for capability in capabilities:
            for section_id in capability.evidence_sections:
                if section_id in seen:
                    continue
                seen.add(section_id)

                # spec: REQ-088
                if section_id in records:
                    public_records.append(records[section_id])
                    # spec: REQ-089
                    continue

                disclosure = snapshot.disclosure_of(section_id)
                if disclosure is None:
                    # spec: REQ-096
                    warnings.append(
                        f"機能「{capability.name}」の裏づけの節「{section_id}」は、"
                        "職歴の枠にも受託案件にも公開記録にも無い ID なので、材料に入っていない。"
                        f"実在する ID の候補は {INSPECT_OPERATION} が返す。"
                    )
                    continue

                heading = labels.get(section_id, section_id)
                # spec: REQ-093
                if snapshot.is_private(section_id):
                    # spec: REQ-094
                    warnings.append(
                        f"{NOTE_AND_SOURCE_SECTION}: 裏づけの節「{heading}」（{section_id}）は"
                        f"公開可否が「{disclosure}」なので、材料から落とした。"
                        "この節の中身は文面に書かない。"
                        "別の公開可の節で裏づけるか、公開可否そのものを先に直す。"
                    )
                    continue

                # spec: REQ-087
                evidence.append(
                    {
                        # spec: REQ-300
                        EVIDENCE_HEADING_KEY: heading,
                        EVIDENCE_ID_KEY: section_id,
                        EVIDENCE_DISCLOSURE_KEY: disclosure,
                        EVIDENCE_BODY_KEY: bodies.get(section_id, ""),
                    }
                )
        return evidence, public_records, warnings

    @staticmethod
    def _unused_public_record_warnings(snapshot: SourceSnapshot) -> list[str]:
        """どの機能の裏づけにもなっていない公開記録を、名前つきで断る。

        登記しただけで裏づけに使っていない公開記録は、材料に載らない。載らないことを黙っていると、
        書く側は「登記したのに使われない」理由を探しに正本を開く羽目になる。
        """
        used = {
            name
            for capability in snapshot.capabilities
            for name in capability.evidence_sections
        }
        labels = snapshot.labels()
        unused = [
            labelled(record.id, labels)
            for record in snapshot.public_records
            if record.id not in used
        ]
        if not unused:
            return []
        # spec: REQ-108
        return [
            f"裏づけに使われていない公開記録が {len(unused)} 件ある"
            f"（{fold_names(unused, keep=NAME_SAMPLE_COUNT)}）。"
            "いま売る機能の担保に使うなら、機能の裏づけの節にその ID を足す。"
        ]

    def _presentation_rule_warnings(
        self, channel: str, channel_rules: list[str], forbidden_phrases: list[str]
    ) -> list[str]:
        """見せ方の正本に、その媒体の節と禁じた言い回しの節があるかを断る。"""
        file_name = self.settings.files[PRESENTATION_RULES_KEY]
        warnings: list[str] = []
        # spec: REQ-097
        if not channel_rules:
            warnings.append(
                f"見せ方の正本 {file_name} に媒体「{channel}」の節が無いので、媒体の規約は空である。"
                f"文字数の上限や書き出しの決まりがあるなら、この媒体の名前の節を作って箇条書きで書く。"
            )
        # spec: REQ-098
        if not forbidden_phrases:
            warnings.append(
                f"見せ方の正本 {file_name} に禁じた言い回しの節が無いので、その一覧は空である。"
            )
        return warnings

    def _inspection_warnings(self, channel: str) -> list[str]:
        """整合検査をこの媒体の範囲で呼び、返った違反と断りを警告の文にする。

        旧い束を宣言する提示物と、未反映の注記の判定は整合検査が持っている。ここで判定し直さない。
        読み込みを関数の中で行うのは、整合検査の側が制約と実装の対応表でこの文書を指していて、
        文書どうしが互いを指すためである（頭で読み込むと輪になり、どちらも読み込めない）。
        """
        from accord.services.consistency import ConsistencyService

        report = ConsistencyService(self.settings, self.repository).inspect(channel)
        # 違反を 1 行に均すときに候補を落とすと、「下の候補」の実体が材料に届かない。
        # 1 行にする書き方は違反の型が持っているので、ここでは組み立て直さない。
        # spec: REQ-107
        warnings = [violation.as_note() for violation in report.violations]
        warnings.extend(report.notes)
        return warnings
