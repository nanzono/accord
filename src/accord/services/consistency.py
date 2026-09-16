"""正本全体を制約に当て、違反の一覧を返す操作。

この操作は正本を読むだけで、1 バイトも書き換えない。
違反 1 件ごとに「どのファイルのどこを、何に合わせるか」を持たせる。何が悪いかだけを返すと、
受け取った側が正本を読み直して直し先を自分で探す羽目になり、規則が行動の瞬間に効かないからである。

範囲は 3 通り取れる。正本全体（省略か「全体」）、媒体の名前、提示物のファイル名である。
範囲の名前が実在しないときは、違反ではなく実在する範囲の一覧を返す。拒否は無い。

執行するのは制約 6 件。書きの操作が書き込みの瞬間に拒否する 2 件（裏づけ節名の実在・束ねる機能名の一致）にも
後から食い違う経路があるので当て直し、書きでは拒否できず後から食い違う 4 件（パッケージ定義の鮮度・提示物の宣言と
看板の一致・未反映の注記の実在・台帳の出典の節の実在と公開可否）を加えて、正本全体に当てる。決めの必須欄は
決めを登記する操作だけが見る（正本の ontology.yaml の enforced_by のとおり）。
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
    PRIVATE_DISCLOSURE_PREFIX,
    ConsistencyReport,
    Provenance,
    SourceSnapshot,
    Violation,
    close_names,
    fold_names,
)
from accord.models.types import Capability, Package, Positioning, Presentation, ResumeLedger
from accord.repository.markdown_repository import (
    EXCEPTION_PRESENTATION_KEY,
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
from accord.vocabulary.settings import READING_KEY, Settings

# 制約は名前で参照する。名前を正本（ontology.yaml）で変えたら、ここで鍵が見つからず落ちる。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
POSITIONING_REQUIRED_FIELDS = CONSTRAINT_BY_NAME["決めの必須欄"].name
PACKAGE_FRESHNESS = CONSTRAINT_BY_NAME["パッケージ定義の鮮度"].name
OFFERING_CLAIM_MATCHES = CONSTRAINT_BY_NAME["提示物の宣言と看板の一致"].name
EVIDENCE_SECTION_EXISTS = CONSTRAINT_BY_NAME["裏づけ節名の実在"].name
PACKAGE_CAPABILITY_MATCHES = CONSTRAINT_BY_NAME["束ねる機能名の一致"].name
NOTE_AND_SOURCE_SECTION = CONSTRAINT_BY_NAME["注記と出典の節の実在・公開可否"].name

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

# 「どこにも無い」ときの文の後半。照らす相手も次の一手も呼ぶ場所ごとに違うので、語で引く。
MISSING_HEADING_TEXT = {
    EVIDENCE_LABEL: (
        "は、職歴の枠にも受託案件にも無い見出しである。下の候補のうち実在する見出しに書き換える。"
    ),
    LEDGER_SOURCE_LABEL: (
        "は、受託案件の見出しに無い。下の候補のうち実在する見出しに書き換える。"
    ),
    PENDING_NOTE_LABEL: (
        "は、受託案件の見出しに無い。下の候補のうち実在する見出しに書き換える。"
        "この事実をもう正本に書いたのなら、注記の行ごと消す。"
    ),
}


def provenance_of(settings: Settings) -> Provenance:
    """この検査が、どの設定を、どの読み方で、どの版とどの置き場の accord で走ったかを作る。

    設定を読む層は型を知らない状態に保たれ、型の器の層は設定を知らない状態に保たれている。
    両方を見てよいのはサービス層だけなので、足跡の組み立てはここに置く。
    """
    try:
        version = importlib.metadata.version("accord")
    except importlib.metadata.PackageNotFoundError:
        version = "不明（未導入）"
    return Provenance(
        config_path=str(settings.config_path.resolve()),
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
    if len(notes) <= NOTE_LIMIT:
        return notes
    rest = len(notes) - (NOTE_LIMIT - 1)
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
    """指された見出しが読めているかと、読めていないときの直し方の文と候補を返す。

    「無い」の一言で片づけると、正本に実在する見出しを指したときに、合っている側を書き換える
    誘導になる。だから 4 通りに分ける——読めた、欄が欠けて読めていない、読み取り範囲の外に実在する、
    どこにも無い。名前が合っている 2 つでは候補を出さない。候補は「そのまま渡し直せば通る名前」に
    限る決めなので、名前が合っているところに候補を並べると、直し先を取り違えさせる。
    """
    if wanted in pool:
        return True, "", []

    for defect in snapshot.defects:
        if defect.heading != wanted:
            continue
        missing = "、".join(f"「{name}」" for name in defect.missing_fields)
        return (
            False,
            f"{label}「{wanted}」は {defect.file} に実在するが、必須の欄{missing}が無いので"
            "型にできず、いまの正本として読んでいない。直すのはこのファイルではなく、"
            f"{defect.file} の「{wanted}」に{missing}の行を足すことである。",
            [],
        )

    for skipped in snapshot.skipped_headings:
        if skipped.heading != wanted:
            continue
        where = settings.files.get(skipped.source_key, skipped.source_key)
        if skipped.parents:
            parents = "、".join(f"「{name}」" for name in skipped.parents)
            place = f"深さ {skipped.level} の見出しで、{parents}の下にある"
        else:
            place = f"深さ {skipped.level} の見出しである"
        return (
            False,
            f"{label}「{wanted}」は {where} に実在する（{place}）が、"
            f"いまの読み取り範囲の外にある——{skipped.reason}。直し方は 2 つで、"
            f"設定の [{READING_KEY}.{skipped.source_key}] の絞りを広げてこの節を読めるようにするか、"
            "正本のこの節を読み取り範囲の中へ移す。",
            [],
        )

    tail = MISSING_HEADING_TEXT.get(
        label, "は、いまの正本に読めている見出しに無い。下の候補のうち実在する見出しに書き換える。"
    )
    return False, f"{label}「{wanted}」{tail}", close_names(wanted, pool)


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
        else:
            notes.extend(self._unrecorded_positioning_notes())

        violations.extend(self._check_evidence_sections(snapshot, target))
        violations.extend(self._check_bundled_capabilities(snapshot, target))

        note_violations, note_remarks = self._check_pending_notes(snapshot, target)
        violations.extend(note_violations)
        notes.extend(note_remarks)

        violations.extend(self._check_ledger_source_sections(snapshot, target))

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
                label=WHOLE_SCOPE,
                positionings=self._applicable_positionings(snapshot),
                packages=tuple(snapshot.packages),
                capabilities=tuple(snapshot.capabilities),
                presentations=tuple(snapshot.presentations),
                ledger_entries=tuple(snapshot.ledger_entries),
            )

        if scope in self.settings.channels:
            return self._channel_scope(snapshot, scope)

        presentations = self._presentations_named(snapshot, scope)
        if presentations:
            return InspectionScope(
                label=scope,
                positionings=(),
                packages=(),
                capabilities=(),
                presentations=presentations,
                ledger_entries=(),
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
        packages = tuple(item for item in snapshot.packages if item.name in headline)
        bundled = {name for package in packages for name in package.capabilities}
        capabilities = tuple(item for item in snapshot.capabilities if item.name in bundled)

        return InspectionScope(
            label=channel,
            positionings=positionings,
            packages=packages,
            capabilities=capabilities,
            presentations=tuple(
                item for item in snapshot.presentations if item.channel == channel
            ),
            ledger_entries=(),
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
        return [
            f"範囲「{scope}」は、媒体の名前にも提示物のファイル名にも無い。",
            "実在する範囲: "
            + fold_names(self._existing_scopes(snapshot), keep=NAME_SAMPLE_COUNT),
            "上の名前のどれかをそのまま範囲に渡して、もう一度 check_consistency を呼ぶ。",
        ]

    def _unrecorded_positioning_notes(self) -> list[str]:
        """決めが 1 件も無いときの断り。2 つの制約は判定を保留し、次の一手を添える。"""
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
        packages = {item.name: item for item in snapshot.packages}
        violations: list[Violation] = []
        notes: list[str] = []
        seen: set[str] = set()

        for positioning in target.positionings:
            package = packages.get(positioning.headline_package)
            if package is None:
                notes.append(
                    f"{positioning.decided_on} の決め（適用範囲 {positioning.scope}）が前面に出す束"
                    f"「{positioning.headline_package}」がパッケージ定義に無いので、鮮度は判定できない。"
                    f"実在する束: {fold_names(list(packages), keep=NAME_SAMPLE_COUNT)}。"
                    "束の名前を直して record_positioning で決めを登記し直す。"
                )
                continue
            if package.name in seen:
                continue
            seen.add(package.name)
            if package.updated_on >= positioning.decided_on:
                continue
            violations.append(
                Violation(
                    constraint=PACKAGE_FRESHNESS,
                    file=self.settings.files["packages"],
                    location=f"「{package.name}」の節の「最終更新」の行",
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
        """提示物が宣言する束が、その媒体に適用される決めの看板と一致するかを見る。"""
        violations: list[Violation] = []

        for presentation in target.presentations:
            positioning = applicable_positioning(snapshot.positionings, presentation.channel)
            if positioning is None:
                continue
            if _is_listed_as_exception(positioning, presentation):
                continue
            if presentation.declared_package == positioning.headline_package:
                continue
            violations.append(
                Violation(
                    constraint=OFFERING_CLAIM_MATCHES,
                    file=presentation.path,
                    location="「宣言する束」の行",
                    expected=(
                        f"いまの看板は「{positioning.headline_package}」"
                        f"（{positioning.decided_on} の決め・適用範囲 {positioning.scope}）で、"
                        f"この文面は「{presentation.declared_package}」を名乗っている。"
                        "宣言する束を看板の名前に書き換える。この文面だけ合わせない理由があるなら、"
                        "決めの「例外」欄にこのファイル名と理由を書く。"
                    ),
                    candidates=[positioning.headline_package],
                )
            )
        return violations

    def _check_evidence_sections(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """機能の裏づけの節名が、職歴の枠か受託案件の見出しとして実在するかを見る。"""
        headings = snapshot.section_headings()
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
                        location=f"分類「{capability.category}」の機能「{capability.name}」の裏づけの節",
                        expected=expected,
                        candidates=candidates,
                    )
                )
        return violations

    def _check_bundled_capabilities(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """パッケージが束ねる機能名が、機能の台帳にあるかを見る。"""
        names = [item.name for item in snapshot.capabilities]
        violations: list[Violation] = []

        for package in target.packages:
            for wanted in package.capabilities:
                if wanted in names:
                    continue
                violations.append(
                    Violation(
                        constraint=PACKAGE_CAPABILITY_MATCHES,
                        file=self.settings.files["packages"],
                        location=f"「{package.name}」の節の「束ねる機能」の行",
                        expected=(
                            f"束ねる機能「{wanted}」は機能の台帳に無い。"
                            "下の候補のどれかに書き換えるか、先に register_capability で"
                            "この機能を台帳に登記する。"
                        ),
                        candidates=close_names(wanted, names),
                    )
                )
        return violations

    def _check_pending_notes(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> tuple[list[Violation], list[str]]:
        """未反映の注記が指す節の実在と、注記が残っていること自体を見る。

        指す先が無い注記は違反として挙げ、注記が残っていること自体は違反ではなく断りとして返す。
        注記は、正本に反映すれば消える覚え書きだからである。
        """
        headings = [item.heading for item in snapshot.engagements]
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
                violations.append(
                    Violation(
                        constraint=NOTE_AND_SOURCE_SECTION,
                        file=presentation.path,
                        location=f"「未反映の注記」の行「{note}」",
                        expected=expected,
                        candidates=candidates,
                    )
                )

        notes: list[str] = []
        if remaining:
            where = fold_names(list(dict.fromkeys(remaining)), keep=NAME_SAMPLE_COUNT)
            notes.append(
                f"未反映の注記が {len(remaining)} 件残っている（{where}）。"
                "注記の中身を正本に書き、書いたら提示物の注記の行を消す。"
            )
        return violations, notes

    def _check_ledger_source_sections(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """職務経歴書の台帳の出典の節が、受託案件として実在し、公開可であるかを見る。"""
        engagements = {item.heading: item for item in snapshot.engagements}
        public = [
            heading
            for heading, item in engagements.items()
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
                        constraint=NOTE_AND_SOURCE_SECTION,
                        file=self.settings.files["resume_ledger"],
                        location=location,
                        expected=expected,
                        candidates=candidates,
                    )
                )
                continue

            engagement = engagements[section]
            if engagement.disclosure.startswith(PRIVATE_DISCLOSURE_PREFIX):
                violations.append(
                    Violation(
                        constraint=NOTE_AND_SOURCE_SECTION,
                        file=self.settings.files["resume_ledger"],
                        location=location,
                        expected=(
                            f"出典の節「{section}」の公開可否は「{engagement.disclosure}」なので、"
                            "そこから写した中身は外に出せない。下の候補のような公開可の節に"
                            "差し替えるか、この案件を台帳から外す。"
                        ),
                        candidates=public,
                    )
                )
        return violations


# ---------------------------------------------------------------- 制約と実装の対応表
#
# 制約の名前（正本は ontology.yaml）を鍵に、それを執行する操作と関数を引く。
# 同じ制約が、書きの操作では拒否、読みの操作では警告、検査の操作では一覧として現れるので、
# 操作の名前ごとに関数を持つ。1 つの操作が 2 か所で執行する制約（注記と出典の節）は 2 つ並ぶ。
# 書きの操作が持つ拒否と、検査が持つ検出は、同じ制約の違う顔である。

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
    NOTE_AND_SOURCE_SECTION: {
        "check_consistency": (
            ConsistencyService._check_pending_notes,
            ConsistencyService._check_ledger_source_sections,
        ),
        "assemble_material": (MaterialService.assemble,),
    },
}


def enforcement_for(constraint_name: str) -> dict[str, tuple[Callable[..., Any], ...]]:
    """制約の名前から、それを執行する操作と関数を引く。結び付きが無ければ空の表。"""
    return ENFORCEMENT.get(constraint_name, {})
