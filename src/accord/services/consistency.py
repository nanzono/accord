"""正本全体を制約に当て、違反の一覧を返す操作。

この操作は正本を読むだけで、1 バイトも書き換えない。
違反 1 件ごとに「どのファイルのどこを、何に合わせるか」を持たせる。何が悪いかだけを返すと、
受け取った側が正本を読み直して直し先を自分で探す羽目になり、規則が行動の瞬間に効かないからである。

範囲は 3 通り取れる。正本全体（省略か「全体」）、媒体の名前、提示物のファイル名である。
範囲の名前が実在しないときは、違反ではなく実在する範囲の一覧を返す。拒否は無い。

書きの操作が書き込みの瞬間に拒否する制約（ID の形式・ID の一意性・裏づけ節名の実在・
束ねる機能名の一致・由来の節の実在・公開記録の種類の語彙・公開記録の役割の語彙・機能の分類の語彙）にも
後から食い違う経路があるので当て直し、書きでは拒否できず後から食い違う制約（パッケージ定義の鮮度・
提示物の宣言と看板の一致・注記と出典の節の実在・出典と裏づけの節の公開可否・提示物の URL と公開記録の一致）
を加えて、正本全体に当てる。
決めの必須欄と公開記録の必須欄は、それぞれを登記する操作だけが見る
（正本の ontology.yaml の enforced_by のとおり）。
どの制約をどの関数が受け持つかは、この文書の末尾の対応表にある。
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accord.models.constraints import CONSTRAINTS
from accord.models.results import (
    ID_FORMAT_TEXT,
    PRIVATE_DISCLOSURE_PREFIX,
    ConsistencyReport,
    PresentationUrl,
    Provenance,
    SourceSnapshot,
    Violation,
    candidate_text,
    close_names,
    fold_names,
    is_id,
    labelled,
    normalize_url,
    url_host,
    url_tail,
)
from accord.models.types import (
    Capability,
    Package,
    Positioning,
    Presentation,
    PublicRecord,
    ResumeLedger,
)
from accord.repository.markdown_repository import (
    EXCEPTION_PRESENTATION_KEY,
    ID_LABEL,
    MarkdownRepository,
)
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.services.positioning import (
    WHOLE_SCOPE,
    PositioningService,
    applicable_positioning,
    defect_notes,
    latest_positioning,
    unrecorded_positioning_next_step,
)
from accord.services.public_records import REGISTER_OPERATION, PublicRecordService
from accord.vocabulary.settings import (
    PUBLIC_RECORD_KINDS_KEY,
    PUBLIC_RECORD_ROLES_KEY,
    PUBLIC_RECORDS_KEY,
    READING_KEY,
    Settings,
)

# 制約は名前で参照する。名前を正本（ontology.yaml）で変えたら、ここで鍵が見つからず落ちる。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
POSITIONING_REQUIRED_FIELDS = CONSTRAINT_BY_NAME["決めの必須欄"].name
PACKAGE_FRESHNESS = CONSTRAINT_BY_NAME["パッケージ定義の鮮度"].name
OFFERING_CLAIM_MATCHES = CONSTRAINT_BY_NAME["提示物の宣言と看板の一致"].name
EVIDENCE_SECTION_EXISTS = CONSTRAINT_BY_NAME["裏づけ節名の実在"].name
PACKAGE_CAPABILITY_MATCHES = CONSTRAINT_BY_NAME["束ねる機能名の一致"].name
ID_FORMAT = CONSTRAINT_BY_NAME["ID の形式"].name
ID_UNIQUENESS = CONSTRAINT_BY_NAME["ID の一意性"].name
NOTE_AND_SOURCE_SECTION_EXISTS = CONSTRAINT_BY_NAME["注記と出典の節の実在"].name
SOURCE_AND_EVIDENCE_DISCLOSURE = CONSTRAINT_BY_NAME["出典と裏づけの節の公開可否"].name
PUBLIC_RECORD_REQUIRED_FIELDS = CONSTRAINT_BY_NAME["公開記録の必須欄"].name
PUBLIC_RECORD_KIND_VOCABULARY = CONSTRAINT_BY_NAME["公開記録の種類の語彙"].name
PUBLIC_RECORD_ROLE_VOCABULARY = CONSTRAINT_BY_NAME["公開記録の役割の語彙"].name
CAPABILITY_CATEGORY_VOCABULARY = CONSTRAINT_BY_NAME["機能の分類の語彙"].name
ORIGIN_SECTION_EXISTS = CONSTRAINT_BY_NAME["由来の節の実在"].name
PRESENTATION_URL_MATCHES = CONSTRAINT_BY_NAME["提示物の URL と公開記録の一致"].name

# 未反映の注記の書き方。「節の見出し — 覚え書き」で、区切りより前がその注記の入る先の節になる。
# 区切りが無ければ、注記の全文を節の見出しとして読む。
NOTE_SEPARATOR = "—"

# 返り値に載せる断りの数の上限。違反には上限を置かない（1 件ずつ直す対象なので、減らすと直し漏れる）。
NOTE_LIMIT = 30

# 名前の並びを本文に埋めるときに、名前で見せる数。残りは件数に畳む。
NAME_SAMPLE_COUNT = 5

# 見出しが読めていないことを言う 3 か所の、文の頭に置く語。
EVIDENCE_LABEL = "裏づけの節"
LEDGER_SOURCE_LABEL = "出典の節"
PENDING_NOTE_LABEL = "注記が指す節"
ORIGIN_SECTION_LABEL = "由来の節"

# 設定の語の一覧に照らす 3 つの欄の、正本での欄の名前。違反の文はこの語のまま欄を指す。
PUBLIC_RECORD_KIND_LABEL = "種類"
PUBLIC_RECORD_ROLE_LABEL = "役割"
CAPABILITY_CATEGORY_LABEL = "分類"

# 機能の分類の語を書く、[vocabulary] の鍵。公開記録の 2 つと同じく、設定の側の名前を文に出す。
CAPABILITY_CATEGORIES_KEY = "capability_categories"

# 「どこにも無い」ときの文の後半。照らす相手も次の一手も呼ぶ場所ごとに違うので、語で引く。
MISSING_HEADING_TEXT = {
    EVIDENCE_LABEL: (
        "は、職歴の枠にも受託案件にも公開記録にも無い ID である。"
        "実在する ID に書き換える。"
    ),
    ORIGIN_SECTION_LABEL: (
        "は、職歴の枠にも受託案件にも無い ID である。実在する ID に書き換える。"
    ),
    LEDGER_SOURCE_LABEL: "は、受託案件の ID に無い。実在する ID に書き換える。",
    PENDING_NOTE_LABEL: (
        "は、受託案件の ID に無い。実在する ID に書き換える。"
        "この事実をもう正本に書いたのなら、注記の行ごと消す。"
    ),
}


# 値が ID の形に合っていないときの文。区切りの取り違えを、推測ではなく形式の検査で断定する。
def id_format_text(label: str, wanted: str) -> str:
    """ID の形に合わない値を指されたときの、直し方の文を組み立てる。"""
    return (
        f"{label}「{wanted}」は ID の形に合わない（{ID_FORMAT_TEXT}）。"
        "見出しや名前をそのまま書いているなら、その節の ID に置き換える。"
        "2 つ以上を書くなら、半角のスラッシュ「/」で区切る"
        "（「・」や全角の「／」や読点は区切りとして読まない）。"
    )


# 候補の母集団が空のときの文。書き間違いと、そもそも 1 件も読めていないことを言い分ける。
NO_CANDIDATE_MATERIAL_TEXT = (
    "候補を出せる材料が無い（照らす相手が 1 件も読めていない）。"
    "設定の読み方の絞りか、正本の節の位置を確かめる。"
)


# 公開記録の置き場が設定に無いときの断り。照合していないことと、照合させるための鍵 3 つを言う。
# spec: REQ-036
NO_PUBLIC_RECORDS_FILE_NOTE = (
    "公開記録の置き場が設定に無いので、提示物の URL は照合していない。照合させるには、"
    f"設定の [source.files] に {PUBLIC_RECORDS_KEY} を、"
    f"[vocabulary] に {PUBLIC_RECORD_KINDS_KEY} と {PUBLIC_RECORD_ROLES_KEY} を足す。"
)


def records_behind(
    capabilities: tuple[Capability, ...] | list[Capability], records: list[PublicRecord]
) -> tuple[PublicRecord, ...]:
    """その機能たちの裏づけに ID が書かれている公開記録を、正本の並びで返す。"""
    wanted = {name for capability in capabilities for name in capability.evidence_sections}
    return tuple(record for record in records if record.id in wanted)


def provenance_of(settings: Settings) -> Provenance:
    """この検査が、どの設定を、どの読み方で、どの版とどの置き場の accord で走ったかを作る。

    設定を読む層は型を知らない状態に保たれ、型の器の層は設定を知らない状態に保たれている。
    両方を見てよいのはサービス層だけなので、足跡の組み立てはここに置く。
    """
    try:
        version = importlib.metadata.version("accord")
    except importlib.metadata.PackageNotFoundError:
        version = "不明（未導入）"
    # spec: REQ-004
    return Provenance(
        config_path=str(settings.config_path.resolve()),
        # spec: REQ-005
        # spec: REQ-006
        reading=list(settings.reading.applied_keys) or ["既定"],
        version=version,
        # 動いている accord のパッケージの置き場。ここでパッケージを import しないのは、
        # パッケージ単位の読み込みを禁じる構造の検査に当たるからである。
        module_path=str(Path(__file__).resolve().parents[1]),
    )


def limit_notes(notes: list[str]) -> list[str]:
    """断りの数を上限で打ち切る。打ち切った分は、件数と次の一手の 1 行に畳む。

    束ねても、束の種類そのものは入力次第で増える。最後に 1 か所で止めることで、
    返り値の大きさが入力の大きさに引きずられないようにする。
    """
    # spec: REQ-026
    if len(notes) <= NOTE_LIMIT:
        return notes
    rest = len(notes) - (NOTE_LIMIT - 1)
    # spec: REQ-027
    return notes[: NOTE_LIMIT - 1] + [
        f"ほかに {rest} 件の断りを省いた。範囲を絞って check_consistency を呼ぶと、"
        "その範囲の断りを全部見られる。"
    ]


def explain_heading(
    settings: Settings,
    snapshot: SourceSnapshot,
    label: str,
    wanted: str,
    pool: list[str],
) -> tuple[bool, str, list[str]]:
    """指された ID が読めているかと、読めていないときの直し方の文と候補を返す。

    「無い」の一言で片づけると、正本に実在する節を指したときに、合っている側を書き換える
    誘導になる。だから 6 通りに分ける——読めた、ID の形に合わない、欄が欠けて読めていない、
    読み取り範囲の外に実在する、候補を出せる材料が無い、どこにも無い。
    値が合っている 2 つでは候補を出さない。候補は「そのまま渡し直せば通る値」に限る決めなので、
    値が合っているところに候補を並べると、直し先を取り違えさせる。返す候補は ID だけで、
    どの節のことかが読んで分かるように、表示名を添えた候補の文を直し方の文の末尾に置く。

    形の検査を「どこにも無い」より先に置くのは、区切りを取り違えた値（「見出し A・見出し B」の
    ように半角のスラッシュ以外でつないだもの）を、推測ではなく形式で断定するためである。
    """
    labels = snapshot.labels()
    if wanted in pool:
        return True, "", []

    if not is_id(wanted):
        candidates = close_names(wanted, pool, labels)
        return False, id_format_text(label, wanted) + candidate_text(candidates, labels), candidates

    # spec: REQ-029
    for defect in snapshot.defects:
        if not defect.id or defect.id != wanted:
            continue
        missing = "、".join(f"「{name}」" for name in defect.missing_fields)
        where = defect.heading or defect.location
        return (
            False,
            f"{label}「{wanted}」は {defect.file} の「{where}」に実在するが、"
            f"必須の欄{missing}が無いので型にできず、いまの正本として読んでいない。"
            f"直すのはこのファイルではなく、{defect.file} の「{where}」に"
            f"{missing}の行を足すことである。",
            [],
        )

    # spec: REQ-028
    for skipped in snapshot.skipped_headings:
        if not skipped.id or skipped.id != wanted:
            continue
        where = settings.files.get(skipped.source_key, skipped.source_key)
        if skipped.parents:
            parents = "、".join(f"「{name}」" for name in skipped.parents)
            place = f"深さ {skipped.level} の見出しで、{parents}の下にある"
        else:
            place = f"深さ {skipped.level} の見出しである"
        return (
            False,
            f"{label}「{wanted}」は {where} の「{skipped.heading}」に実在する（{place}）が、"
            f"いまの読み取り範囲の外にある——{skipped.reason}。直し方は 2 つで、"
            f"設定の [{READING_KEY}.{skipped.source_key}] の絞りを広げてこの節を読めるようにするか、"
            "正本のこの節を読み取り範囲の中へ移す。",
            [],
        )

    if not pool:
        return False, f"{label}「{wanted}」を照らそうにも、{NO_CANDIDATE_MATERIAL_TEXT}", []

    tail = MISSING_HEADING_TEXT.get(
        label, "は、いまの正本に読めている ID に無い。実在する ID に書き換える。"
    )
    candidates = close_names(wanted, pool, labels)
    return (
        False,
        f"{label}「{wanted}」{tail}" + candidate_text(candidates, labels),
        candidates,
    )


def _is_listed_as_exception(positioning: Positioning, presentation: Presentation) -> bool:
    """この提示物が、決めの例外の欄に書かれているか。"""
    path = presentation.path
    name = path.rsplit("/", 1)[-1]
    for entry in positioning.exceptions:
        listed = str(entry.get(EXCEPTION_PRESENTATION_KEY, "")).strip()
        if not listed:
            continue
        if listed == path or listed == name or path.endswith(f"/{listed}"):
            return True
    return False


def _note_target(note: str) -> str:
    """未反映の注記から、その注記が指す節の見出しを取り出す。"""
    head = note.split(NOTE_SEPARATOR, 1)[0]
    return head.strip()


@dataclass(frozen=True)
class InspectionScope:
    """今回の検査が見る範囲。範囲を絞ったときに、見ていないものを断るためにも使う。"""

    label: str
    positionings: tuple[Positioning, ...]
    packages: tuple[Package, ...]
    capabilities: tuple[Capability, ...]
    presentations: tuple[Presentation, ...]
    ledger_entries: tuple[ResumeLedger, ...]
    public_records: tuple[PublicRecord, ...] = ()
    skipped: tuple[str, ...] = ()


class ConsistencyService:
    """整合を検査する。正本は変えない。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    # ------------------------------------------------------------ 入口

    def inspect(self, scope: str | None = None) -> ConsistencyReport:
        """範囲を受けて違反の一覧を返す。正本は 1 バイトも書き換えない。"""
        snapshot = self.repository.load()
        target = self._resolve_scope(snapshot, scope)

        if target is None:
            # spec: REQ-009
            return ConsistencyReport(
                provenance=provenance_of(self.settings),
                scope=scope or WHOLE_SCOPE,
                notes=limit_notes(self._unknown_scope_notes(snapshot, str(scope))),
            )

        violations: list[Violation] = []
        notes: list[str] = list(target.skipped)

        # 型にできなかったブロックは、検査の対象に入っていない。入っていないことを先に断る。
        # 黙って飛ばすと、1 つ前のブロックを看板として、正しい提示物に逆向きの直し先が返る。
        notes.extend(defect_notes(self.settings, snapshot))

        if snapshot.positionings:
            stale, missing_package = self._check_package_freshness(snapshot, target)
            violations.extend(stale)
            notes.extend(missing_package)
            violations.extend(self._check_offering_claims(snapshot, target))
        # spec: REQ-014
        else:
            notes.extend(self._unrecorded_positioning_notes())

        violations.extend(self._check_evidence_sections(snapshot, target))
        violations.extend(self._check_bundled_capabilities(snapshot, target))
        violations.extend(self._check_public_record_origins(snapshot, target))
        violations.extend(self._check_vocabulary(snapshot, target))

        url_violations, url_notes = self._check_presentation_urls(snapshot, target)
        violations.extend(url_violations)
        notes.extend(url_notes)

        note_violations, note_remarks = self._check_pending_notes(snapshot, target)
        violations.extend(note_violations)
        notes.extend(note_remarks)

        violations.extend(self._check_ledger_source_sections(snapshot, target))
        # ID の形式と ID の一意性は、範囲を絞っても正本全体で見る。一意性は 1 つのブロックだけを
        # 見ても言えず、絞った範囲の外にある項目と重なっていても違反だからである。
        # spec: REQ-362
        violations.extend(self._check_id_format_and_uniqueness(snapshot))

        return ConsistencyReport(
            provenance=provenance_of(self.settings),
            scope=target.label,
            violations=violations,
            notes=limit_notes(notes),
        )

    # ------------------------------------------------------------ 範囲

    def _resolve_scope(self, snapshot: SourceSnapshot, scope: str | None) -> InspectionScope | None:
        """範囲の名前を、今回見る型の集合に翻訳する。名前が実在しなければ None。"""
        if scope is None or scope == WHOLE_SCOPE:
            return InspectionScope(
                # spec: REQ-001
                label=WHOLE_SCOPE,
                positionings=self._applicable_positionings(snapshot),
                packages=tuple(snapshot.packages),
                capabilities=tuple(snapshot.capabilities),
                presentations=tuple(snapshot.presentations),
                ledger_entries=tuple(snapshot.ledger_entries),
                public_records=tuple(snapshot.public_records),
            )

        if scope in self.settings.channels:
            return self._channel_scope(snapshot, scope)

        # spec: REQ-042
        presentations = self._presentations_named(snapshot, scope)
        if presentations:
            return InspectionScope(
                label=scope,
                positionings=(),
                packages=(),
                capabilities=(),
                presentations=presentations,
                ledger_entries=(),
                # spec: REQ-008
                skipped=(
                    f"範囲を提示物「{scope}」に絞ったので、"
                    "パッケージ定義・機能の台帳・職務経歴書の台帳・他の提示物は見ていない。"
                    "全部を見るには範囲を省いて呼ぶ。",
                ),
            )

        return None

    def _channel_scope(self, snapshot: SourceSnapshot, channel: str) -> InspectionScope:
        """媒体 1 つを範囲にとる。その媒体に適用される決めから、束と機能までを辿る。"""
        positioning = applicable_positioning(snapshot.positionings, channel)
        positionings = (positioning,) if positioning is not None else ()

        headline = {item.headline_package for item in positionings}
        packages = tuple(item for item in snapshot.packages if item.id in headline)
        bundled = {name for package in packages for name in package.capabilities}
        capabilities = tuple(item for item in snapshot.capabilities if item.id in bundled)

        return InspectionScope(
            label=channel,
            positionings=positionings,
            packages=packages,
            capabilities=capabilities,
            # spec: REQ-007
            presentations=tuple(
                item for item in snapshot.presentations if item.channel == channel
            ),
            ledger_entries=(),
            # spec: REQ-043
            public_records=records_behind(capabilities, snapshot.public_records),
            # spec: REQ-008
            skipped=(
                f"範囲を媒体「{channel}」に絞ったので、他の媒体の提示物と、"
                "職務経歴書の台帳と、この媒体の看板が束ねていない機能は見ていない。"
                "全部を見るには範囲を省いて呼ぶ。",
            ),
        )

    def _applicable_positionings(self, snapshot: SourceSnapshot) -> tuple[Positioning, ...]:
        """いま効いている決めを集める。「全体」の最新と、媒体ごとの最新である。"""
        found: list[Positioning] = []
        candidates = [latest_positioning(snapshot.positionings, WHOLE_SCOPE)]
        candidates += [
            applicable_positioning(snapshot.positionings, name)
            for name in self.settings.channels
        ]
        for item in candidates:
            if item is not None and item not in found:
                found.append(item)
        return tuple(found)

    def _presentations_named(
        self, snapshot: SourceSnapshot, scope: str
    ) -> tuple[Presentation, ...]:
        """提示物のファイル名で範囲を指されたときに、その提示物を探す。

        正本のディレクトリからの相対パスでも、末尾のファイル名だけでも指せるようにする。
        """
        return tuple(
            item
            for item in snapshot.presentations
            if item.path == scope
            or item.path.endswith(f"/{scope}")
            or item.path.rsplit("/", 1)[-1] == scope
        )

    def _existing_scopes(self, snapshot: SourceSnapshot) -> list[str]:
        """範囲として渡せる名前を、そのまま渡せる形で並べる。"""
        return (
            [WHOLE_SCOPE]
            + list(self.settings.channels)
            + [item.path for item in snapshot.presentations]
        )

    def _unknown_scope_notes(self, snapshot: SourceSnapshot, scope: str) -> list[str]:
        """範囲の名前が実在しないときの断り。拒否ではなく、実在する範囲の一覧を返す。"""
        # spec: REQ-010
        return [
            f"範囲「{scope}」は、媒体の名前にも提示物のファイル名にも無い。",
            "実在する範囲: "
            + fold_names(self._existing_scopes(snapshot), keep=NAME_SAMPLE_COUNT),
            "上の名前のどれかをそのまま範囲に渡して、もう一度 check_consistency を呼ぶ。",
        ]

    def _unrecorded_positioning_notes(self) -> list[str]:
        """決めが 1 件も無いときの断り。2 つの制約は判定を保留し、次の一手を添える。"""
        # spec: REQ-015
        return [
            f"決めが未登記なので、「{PACKAGE_FRESHNESS}」と「{OFFERING_CLAIM_MATCHES}」は"
            "判定を保留した。比べる相手（いまの看板と、その決めの日付）が無いためである。",
            unrecorded_positioning_next_step(),
        ]

    # ------------------------------------------------------------ 制約ごとの執行

    def _check_package_freshness(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> tuple[list[Violation], list[str]]:
        """パッケージ定義の最終更新が、それを前面に出した決めの日付より古くないかを見る。

        看板の束がパッケージ定義に無いときは、比べる相手が無いので判定できない。
        束の実在は決めを登記する操作が書き込みの瞬間に見るので、ここでは断りとして返す。
        """
        packages = {item.id: item for item in snapshot.packages}
        listed = [labelled(item.id, {item.id: item.name}) for item in snapshot.packages]
        violations: list[Violation] = []
        notes: list[str] = []
        seen: set[str] = set()

        for positioning in target.positionings:
            package = packages.get(positioning.headline_package)
            # spec: REQ-016
            if package is None:
                # spec: REQ-017
                notes.append(
                    f"{positioning.decided_on} の決め（適用範囲 {positioning.scope}）が前面に出す束"
                    f"「{positioning.headline_package}」がパッケージ定義に無いので、鮮度は判定できない。"
                    f"実在する束: {fold_names(listed, keep=NAME_SAMPLE_COUNT)}。"
                    "束の ID を直して record_positioning で決めを登記し直す。"
                )
                continue
            if package.id in seen:
                continue
            seen.add(package.id)
            # spec: REQ-011
            if package.updated_on >= positioning.decided_on:
                continue
            violations.append(
                Violation(
                    constraint=PACKAGE_FRESHNESS,
                    file=self.settings.files["packages"],
                    location=f"「{package.name}」（{package.id}）の節の「最終更新」の行",
                    expected=(
                        f"この束を前面に出した決めの日付は {positioning.decided_on}"
                        f"（適用範囲 {positioning.scope}）で、定義の最終更新は {package.updated_on} と"
                        "それより古い。定義の中身を決めに合わせて直し、revise_package を呼んで"
                        "最終更新を決めの日付以降に進める。"
                    ),
                )
            )
        return violations, notes

    def _check_offering_claims(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """提示物が宣言する束の ID が、その媒体に適用される決めの看板と一致するかを見る。"""
        violations: list[Violation] = []
        labels = snapshot.labels()

        for presentation in target.presentations:
            # spec: REQ-018
            positioning = applicable_positioning(snapshot.positionings, presentation.channel)
            if positioning is None:
                continue
            # spec: REQ-013
            if _is_listed_as_exception(positioning, presentation):
                continue
            # spec: REQ-012
            if presentation.declared_package == positioning.headline_package:
                continue
            violations.append(
                Violation(
                    constraint=OFFERING_CLAIM_MATCHES,
                    file=presentation.path,
                    location="「宣言する束」の行",
                    expected=(
                        f"いまの看板は「{labelled(positioning.headline_package, labels)}」"
                        f"（{positioning.decided_on} の決め・適用範囲 {positioning.scope}）で、"
                        f"この文面は「{labelled(presentation.declared_package, labels)}」を"
                        "名乗っている。宣言する束を看板の ID に書き換える。"
                        "この文面だけ合わせない理由があるなら、"
                        "決めの「例外」欄にこのファイル名と理由を書く。"
                    ),
                    candidates=[positioning.headline_package],
                )
            )
        return violations

    def _check_evidence_sections(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """機能の裏づけに書いた ID が、職歴の枠・受託案件・公開記録の ID として実在するかを見る。"""
        # spec: REQ-022
        headings = snapshot.evidence_targets()
        violations: list[Violation] = []

        for capability in target.capabilities:
            for section in capability.evidence_sections:
                readable, expected, candidates = explain_heading(
                    self.settings, snapshot, EVIDENCE_LABEL, section, headings
                )
                if readable:
                    continue
                violations.append(
                    Violation(
                        constraint=EVIDENCE_SECTION_EXISTS,
                        file=self.settings.files["capabilities"],
                        location=(
                            f"分類「{capability.category}」の機能"
                            f"「{capability.name}」（{capability.id}）の裏づけの節"
                        ),
                        expected=expected,
                        candidates=candidates,
                    )
                )
        return violations

    def _check_bundled_capabilities(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """パッケージが束ねる機能の ID が、機能の台帳にあるかを見る。"""
        names = [item.id for item in snapshot.capabilities]
        labels = snapshot.labels()
        violations: list[Violation] = []

        for package in target.packages:
            for wanted in package.capabilities:
                # spec: REQ-041
                if wanted in names:
                    continue
                trouble = (
                    f"束ねる機能「{wanted}」は ID の形に合わない（{ID_FORMAT_TEXT}）。"
                    "機能名をそのまま書いているなら ID に置き換え、2 つ以上は半角のスラッシュ"
                    "「/」で区切る。"
                    if not is_id(wanted)
                    else f"束ねる機能「{wanted}」は機能の台帳に無い ID である。"
                )
                candidates = close_names(wanted, names, labels)
                violations.append(
                    Violation(
                        constraint=PACKAGE_CAPABILITY_MATCHES,
                        file=self.settings.files["packages"],
                        location=f"「{package.name}」（{package.id}）の節の「束ねる機能」の行",
                        expected=(
                            trouble
                            + "実在する ID に書き換えるか、"
                            "先に register_capability でこの機能を台帳に登記する。"
                            + candidate_text(candidates, labels)
                        ),
                        candidates=candidates,
                    )
                )
        return violations

    def _check_public_record_origins(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """公開記録の由来の節に書いた ID が、職歴の枠か受託案件の ID として実在するかを見る。

        登記の操作も書き込みの瞬間に同じことを見るが、書いたあとで正本の節の側が動けば食い違う。
        だから、裏づけ節名の実在と同じく、検査でも当て直す。
        """
        if not self.settings.has_file(PUBLIC_RECORDS_KEY):
            return []

        headings = snapshot.section_headings()
        violations: list[Violation] = []

        for record in target.public_records:
            if not record.origin_section:
                continue
            readable, expected, candidates = explain_heading(
                self.settings, snapshot, ORIGIN_SECTION_LABEL, record.origin_section, headings
            )
            if readable:
                continue
            # spec: REQ-023
            violations.append(
                Violation(
                    constraint=ORIGIN_SECTION_EXISTS,
                    file=self.settings.files[PUBLIC_RECORDS_KEY],
                    location=f"「{record.name}」（{record.id}）のブロックの「由来の節」の行",
                    expected=expected,
                    candidates=candidates,
                )
            )
        return violations

    def _check_vocabulary(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """公開記録の種類と役割、機能の分類が、設定が持つ語の一覧にあるかを見る。

        登記の操作も書き込みの瞬間に同じことを見るが、正本は accord を通さずに手で直すことがある。
        設定の外の語でも型にはできるので読み込みは通り、必須の欄の欠けだけを見る検査は黙って通る。
        だから、裏づけ節名の実在と同じく、読み込んだ正本に対しても当て直す。
        語の外れたブロックを読み飛ばさず違反 1 件として挙げるので、材料の取り出しからは消えない。
        """
        violations: list[Violation] = []
        config_name = self.settings.config_path.name

        # 公開記録の置き場を書いていない設定は、公開記録を 0 件として読む。照らす相手も語彙も無い。
        if self.settings.has_file(PUBLIC_RECORDS_KEY):
            records_file = self.settings.files[PUBLIC_RECORDS_KEY]
            # 種類と役割は別のルールなので、外れた側のルールの名前で違反を挙げる。
            fields = (
                # spec: REQ-368
                (
                    PUBLIC_RECORD_KIND_VOCABULARY,
                    PUBLIC_RECORD_KIND_LABEL,
                    self.settings.public_record_kinds,
                    PUBLIC_RECORD_KINDS_KEY,
                ),
                # spec: REQ-369
                (
                    PUBLIC_RECORD_ROLE_VOCABULARY,
                    PUBLIC_RECORD_ROLE_LABEL,
                    self.settings.public_record_roles,
                    PUBLIC_RECORD_ROLES_KEY,
                ),
            )
            for record in target.public_records:
                written = {
                    PUBLIC_RECORD_KIND_LABEL: record.kind,
                    PUBLIC_RECORD_ROLE_LABEL: record.role,
                }
                for constraint, label, allowed, key in fields:
                    value = written[label]
                    if not value or value in allowed:
                        continue
                    violations.append(
                        Violation(
                            constraint=constraint,
                            file=records_file,
                            location=f"「{record.name}」のブロックの「{label}」の行",
                            expected=(
                                f"{label}「{value}」は、設定が持つ語の一覧に無い。"
                                f"この行を下の候補のどれかに書き換えるか、設定 {config_name} の"
                                f" [vocabulary] の {key} に「{value}」を足す。"
                            ),
                            candidates=list(allowed),
                        )
                    )

        categories = self.settings.capability_categories
        for capability in target.capabilities:
            # spec: REQ-040
            if capability.category in categories:
                continue
            violations.append(
                Violation(
                    constraint=CAPABILITY_CATEGORY_VOCABULARY,
                    file=self.settings.files["capabilities"],
                    location=(
                        f"節「{capability.category}」の機能「{capability.name}」の行"
                        f"（この節の見出しが{CAPABILITY_CATEGORY_LABEL}になる）"
                    ),
                    expected=(
                        f"{CAPABILITY_CATEGORY_LABEL}「{capability.category}」は、"
                        "設定が持つ機能の台帳の節の名前に無い。この行を下の候補のどれかの節へ移すか、"
                        f"設定 {config_name} の [vocabulary] の {CAPABILITY_CATEGORIES_KEY} に"
                        f"「{capability.category}」を足す。"
                    ),
                    candidates=list(categories),
                )
            )
        return violations

    def _check_presentation_urls(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> tuple[list[Violation], list[str]]:
        """提示物の本文の URL が、正本の公開記録の URL にあるかを見る。

        見るのは、正本の公開記録と同じホストの URL だけである。ほかのホストの URL は、媒体の
        設定画面の場所の覚え書きのように公開記録ではありえないものなので、照合の相手にしない。
        URL を持たない公開記録（紙媒体）も、照らす相手には入れない。
        """
        if not self.settings.has_file(PUBLIC_RECORDS_KEY):
            # spec: REQ-035
            return [], [NO_PUBLIC_RECORDS_FILE_NOTE]

        # spec: REQ-033
        known = [
            (record, normalize_url(record.url))
            for record in snapshot.public_records
            if record.url
        ]
        known = [(record, normalized) for record, normalized in known if normalized]
        hosts = {url_host(normalized) for _, normalized in known}

        violations: list[Violation] = []
        for entry in self._urls_in_scope(snapshot, target):
            # spec: REQ-034
            if url_host(entry.normalized) not in hosts:
                continue
            if any(entry.normalized == normalized for _, normalized in known):
                continue
            violations.append(self._url_violation(entry, known))

        # spec: REQ-037
        return violations, self._uncarried_public_record_notes(snapshot, target)

    @staticmethod
    def _urls_in_scope(
        snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[PresentationUrl]:
        """今回の範囲に入っている提示物の URL だけを取り出す。"""
        paths = {item.path for item in target.presentations}
        return [entry for entry in snapshot.presentation_urls if entry.path in paths]

    @staticmethod
    def _url_violation(
        entry: PresentationUrl, known: list[tuple[PublicRecord, str]]
    ) -> Violation:
        """正本に無い URL 1 つを、違反 1 件にする。経路の書き方だけが違うものは言い分ける。

        同じ場所を指しているのに経路の書き方だけが違う形は、正規化した後のパスの最後の要素が
        同じになる。相手が複数あるときは、正本に書かれた順で最初の 1 件を相手にする。
        """
        host = url_host(entry.normalized)
        tail = url_tail(entry.normalized)
        # spec: REQ-031
        same_place = next(
            (
                record
                for record, normalized in known
                if url_host(normalized) == host and tail and url_tail(normalized) == tail
            ),
            None,
        )
        if same_place is not None:
            return Violation(
                constraint=PRESENTATION_URL_MATCHES,
                file=entry.path,
                location=f"本文の URL「{entry.url}」",
                expected=(
                    f"この URL は、正本の公開記録「{same_place.name}」の URL"
                    f"「{same_place.url}」と同じ場所を指しているが、経路の書き方が違う。"
                    "文面を正本の書き方にそろえるか、正本の URL を今の経路に直して登記し直す。"
                ),
                candidates=[str(same_place.url)],
            )

        # spec: REQ-030
        return Violation(
            constraint=PRESENTATION_URL_MATCHES,
            file=entry.path,
            location=f"本文の URL「{entry.url}」",
            expected=(
                "この URL は、正本の公開記録のどの URL にも無い。"
                f"公開記録として登記する（{REGISTER_OPERATION} に、ID・名前・種類・日付・"
                "発行元か主催・役割とこの URL を渡す。由来の節と出所は任意）か、この行を文面から外す。"
            ),
            candidates=close_names(entry.url, [str(record.url) for record, _ in known]),
        )

    def _uncarried_public_record_notes(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[str]:
        """看板の裏づけの公開記録のうち、この範囲のどの提示物にも載っていないものを断る。

        載せるかどうかは見せ方の判断なので、違反にはしない。
        """
        if not target.presentations:
            return []

        headline = self._records_behind_headline(snapshot, target)
        behind = [record for record in headline if record.url]
        if not behind:
            return []

        carried = {entry.normalized for entry in self._urls_in_scope(snapshot, target)}
        missing = [record for record in behind if normalize_url(str(record.url)) not in carried]
        if not missing:
            return []

        names = [record.name for record in missing]
        # spec: REQ-038
        return [
            f"看板の裏づけになっている公開記録 {len(behind)} 件のうち、"
            f"この範囲の提示物にどれも載っていないものが {len(missing)} 件ある"
            f"（{fold_names(names, keep=NAME_SAMPLE_COUNT)}）。"
            "載せるかどうかは見せ方の判断なので、違反にはしない。"
        ]

    @staticmethod
    def _records_behind_headline(
        snapshot: SourceSnapshot, target: InspectionScope
    ) -> tuple[PublicRecord, ...]:
        """看板の束が束ねる機能の、裏づけになっている公開記録を集める。"""
        headline = {item.headline_package for item in target.positionings}
        bundled = {
            name for package in snapshot.packages if package.id in headline
            for name in package.capabilities
        }
        capabilities = [item for item in snapshot.capabilities if item.id in bundled]
        return records_behind(capabilities, snapshot.public_records)

    # spec: REQ-364
    def _check_id_format_and_uniqueness(self, snapshot: SourceSnapshot) -> list[Violation]:
        """指される側の 5 つの型の ID が、形に合うか（ID の形式）と、正本全体で重ならないか（ID の一意性）を見る。

        形に合わない ID は、形を直すまで重なりを見ない。

        形が外れた ID と重なった ID は、ブロックとしては読んだうえでここが違反として挙げる。
        読み込みの層で落とさないのは、落とすと「その節は無い」と読めてしまい、正しい側を
        書き換える誘導になるからである。重なりは、同じ ID を持つ場所を両方挙げる。
        片方だけを挙げると、どちらを直すかを決めるのに正本を開き直すことになる。
        """
        # ID を持つ項目を、正本の並びのまま「ID・置き場・場所の言い方」の組にする。
        entries: list[tuple[str, str, str]] = []
        for frame in snapshot.career_frames:
            entries.append((frame.id, self.settings.files["career"], f"「{frame.heading}」の節"))
        for engagement in snapshot.engagements:
            entries.append(
                (engagement.id, self.settings.files["engagements"], f"「{engagement.heading}」の節")
            )
        # spec: REQ-366
        if self.settings.has_file(PUBLIC_RECORDS_KEY):
            for record in snapshot.public_records:
                entries.append(
                    (
                        record.id,
                        self.settings.files[PUBLIC_RECORDS_KEY],
                        f"「{record.name}」のブロック",
                    )
                )
        for capability in snapshot.capabilities:
            entries.append(
                (
                    capability.id,
                    self.settings.files["capabilities"],
                    f"分類「{capability.category}」の機能「{capability.name}」の行",
                )
            )
        for package in snapshot.packages:
            entries.append((package.id, self.settings.files["packages"], f"「{package.name}」の節"))

        places: dict[str, list[str]] = {}
        for identifier, file_name, location in entries:
            # spec: REQ-365
            places.setdefault(identifier, []).append(f"{file_name} の{location}")

        violations: list[Violation] = []
        for identifier, file_name, location in entries:
            # spec: REQ-292
            if not is_id(identifier):
                violations.append(
                    Violation(
                        constraint=ID_FORMAT,
                        file=file_name,
                        # spec: REQ-293
                        location=f"{location}の「{ID_LABEL}」",
                        expected=(
                            f"ID「{identifier}」は形に合わない（{ID_FORMAT_TEXT}）。"
                            # spec: REQ-294
                            "この行を形に合う値に直し、この ID を指している側も同じ値に直す。"
                        ),
                    )
                )
                continue
            same = places[identifier]
            # spec: REQ-295
            if len(same) > 1:
                violations.append(
                    Violation(
                        constraint=ID_UNIQUENESS,
                        file=file_name,
                        location=f"{location}の「{ID_LABEL}」",
                        expected=(
                            # spec: REQ-296
                            f"ID「{identifier}」が {len(same)} か所で使われている"
                            f"（{fold_names(same, keep=NAME_SAMPLE_COUNT)}）。"
                            "ID は正本全体で 1 つの項目にしか付けられないので、"
                            # spec: REQ-297
                            "どちらか一方を別の値に直し、その ID を指している側も同じ値に直す。"
                        ),
                    )
                )
        return violations

    def _check_pending_notes(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> tuple[list[Violation], list[str]]:
        """未反映の注記が指す ID の実在と、注記が残っていること自体を見る。

        指す先が無い注記は違反として挙げ、注記が残っていること自体は違反ではなく断りとして返す。
        注記は、正本に反映すれば消える覚え書きだからである。
        """
        headings = [item.id for item in snapshot.engagements]
        violations: list[Violation] = []
        remaining: list[str] = []

        for presentation in target.presentations:
            for note in presentation.pending_notes:
                remaining.append(presentation.path)
                section = _note_target(note)
                readable, expected, candidates = explain_heading(
                    self.settings, snapshot, PENDING_NOTE_LABEL, section, headings
                )
                if readable:
                    continue
                # spec: REQ-020
                violations.append(
                    Violation(
                        constraint=NOTE_AND_SOURCE_SECTION_EXISTS,
                        file=presentation.path,
                        location=f"「未反映の注記」の行「{note}」",
                        expected=expected,
                        candidates=candidates,
                    )
                )

        notes: list[str] = []
        if remaining:
            where = fold_names(list(dict.fromkeys(remaining)), keep=NAME_SAMPLE_COUNT)
            # spec: REQ-021
            notes.append(
                f"未反映の注記が {len(remaining)} 件残っている（{where}）。"
                "注記の中身を正本に書き、書いたら提示物の注記の行を消す。"
            )
        return violations, notes

    def _check_ledger_source_sections(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """職務経歴書の台帳の出典の節の ID が、受託案件として実在するか（注記と出典の節の実在）と、
        実在した節が公開可であるか（出典と裏づけの節の公開可否）を見る。実在しない節は公開可否を見ない。
        """
        engagements = {item.id: item for item in snapshot.engagements}
        labels = snapshot.labels()
        public = [
            identifier
            for identifier, item in engagements.items()
            if not item.disclosure.startswith(PRIVATE_DISCLOSURE_PREFIX)
        ]
        violations: list[Violation] = []

        for entry in target.ledger_entries:
            section = entry.source_section
            location = f"案件番号 {entry.entry_number}（{entry.heading}）の「出典の節」の行"

            readable, expected, candidates = explain_heading(
                self.settings, snapshot, LEDGER_SOURCE_LABEL, section, list(engagements)
            )
            if not readable:
                violations.append(
                    Violation(
                        constraint=NOTE_AND_SOURCE_SECTION_EXISTS,
                        file=self.settings.files["resume_ledger"],
                        location=location,
                        expected=expected,
                        candidates=candidates,
                    )
                )
                continue

            engagement = engagements[section]
            # spec: REQ-019
            if engagement.disclosure.startswith(PRIVATE_DISCLOSURE_PREFIX):
                violations.append(
                    Violation(
                        constraint=SOURCE_AND_EVIDENCE_DISCLOSURE,
                        file=self.settings.files["resume_ledger"],
                        location=location,
                        expected=(
                            f"出典の節「{labelled(section, labels)}」の公開可否は"
                            f"「{engagement.disclosure}」なので、そこから写した中身は外に出せない。"
                            "公開可の節の ID に差し替えるか、この案件を台帳から外す。"
                            + candidate_text(public, labels)
                        ),
                        candidates=public,
                    )
                )
        return violations


# ---------------------------------------------------------------- 制約と実装の対応表
#
# 制約の名前（正本は ontology.yaml）を鍵に、それを執行する操作と関数を引く。
# 同じ制約が、書きの操作では拒否、読みの操作では警告、検査の操作では一覧として現れるので、
# 操作の名前ごとに関数を持つ。1 つの操作が 2 か所で執行する制約（注記と出典の節の実在）は 2 つ並ぶ。
# 書きの操作が持つ拒否と、検査が持つ検出は、同じ制約の違う顔である。

# spec: REQ-334
ENFORCEMENT: dict[str, dict[str, tuple[Callable[..., Any], ...]]] = {
    POSITIONING_REQUIRED_FIELDS: {
        "record_positioning": (PositioningService.record,),
    },
    PACKAGE_FRESHNESS: {
        "record_positioning": (PositioningService.record,),
        "check_consistency": (ConsistencyService._check_package_freshness,),
    },
    OFFERING_CLAIM_MATCHES: {
        "record_positioning": (PositioningService.record,),
        "check_consistency": (ConsistencyService._check_offering_claims,),
    },
    EVIDENCE_SECTION_EXISTS: {
        "register_capability": (OfferingService.register_capability,),
        "check_consistency": (ConsistencyService._check_evidence_sections,),
    },
    PACKAGE_CAPABILITY_MATCHES: {
        "revise_package": (OfferingService.revise_package,),
        "check_consistency": (ConsistencyService._check_bundled_capabilities,),
    },
    ID_FORMAT: {
        "check_consistency": (ConsistencyService._check_id_format_and_uniqueness,),
        "register_capability": (OfferingService.register_capability,),
        "revise_package": (OfferingService.revise_package,),
        "register_public_record": (PublicRecordService.register,),
    },
    ID_UNIQUENESS: {
        "check_consistency": (ConsistencyService._check_id_format_and_uniqueness,),
        "register_capability": (OfferingService.register_capability,),
        "revise_package": (OfferingService.revise_package,),
        "register_public_record": (PublicRecordService.register,),
    },
    NOTE_AND_SOURCE_SECTION_EXISTS: {
        "check_consistency": (
            ConsistencyService._check_pending_notes,
            ConsistencyService._check_ledger_source_sections,
        ),
    },
    SOURCE_AND_EVIDENCE_DISCLOSURE: {
        "check_consistency": (ConsistencyService._check_ledger_source_sections,),
        "assemble_material": (MaterialService.assemble,),
        "register_capability": (OfferingService.register_capability,),
    },
    PUBLIC_RECORD_REQUIRED_FIELDS: {
        "register_public_record": (PublicRecordService.register,),
    },
    PUBLIC_RECORD_KIND_VOCABULARY: {
        "register_public_record": (PublicRecordService.register,),
        "check_consistency": (ConsistencyService._check_vocabulary,),
    },
    PUBLIC_RECORD_ROLE_VOCABULARY: {
        "register_public_record": (PublicRecordService.register,),
        "check_consistency": (ConsistencyService._check_vocabulary,),
    },
    CAPABILITY_CATEGORY_VOCABULARY: {
        "register_capability": (OfferingService.register_capability,),
        "check_consistency": (ConsistencyService._check_vocabulary,),
    },
    ORIGIN_SECTION_EXISTS: {
        "register_public_record": (PublicRecordService.register,),
        "check_consistency": (ConsistencyService._check_public_record_origins,),
    },
    PRESENTATION_URL_MATCHES: {
        "check_consistency": (ConsistencyService._check_presentation_urls,),
    },
}


def enforcement_for(constraint_name: str) -> dict[str, tuple[Callable[..., Any], ...]]:
    """制約の名前から、それを執行する操作と関数を引く。結び付きが無ければ空の表。"""
    return ENFORCEMENT.get(constraint_name, {})
