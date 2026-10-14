"""正本全体を制約に当て、違反の一覧を返す操作。

この操作は正本を読むだけで、1 バイトも書き換えない。
違反 1 件ごとに「どのファイルのどこを、何に合わせるか」を持たせる。何が悪いかだけを返すと、
受け取った側が正本を読み直して直し先を自分で探す羽目になり、規則が行動の瞬間に効かないからである。

範囲は 3 通り取れる。正本全体（省略か「全体」）、媒体の名前、提示物のファイル名である。
範囲の名前が実在しないときは、違反ではなく実在する範囲の一覧を返す。拒否は無い。

書きの操作が書き込みの瞬間に拒否する制約（ID の形式・ID の一意性・裏づけ節名の実在・
束ねる機能名の一致・由来の節の実在・公開記録の種類の語彙・公開記録の役割の語彙・機能の分類の語彙）にも
後から食い違う経路があるので当て直し、パッケージの仮説の状態と決めの適用範囲の語彙も当て、書きでは拒否できず後から食い違う制約（パッケージ定義の鮮度・
提示物の宣言と看板の一致・注記と出典の節の実在・出典と裏づけの節の公開可否・提示物の URL と公開記録の一致・
写しの鮮度）を加えて、正本全体に当てる。
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
    FINGERPRINT_ID_KEY,
    FINGERPRINT_VALUE_KEY,
    ID_LABEL,
    LEDGER_KEY,
    LEDGER_KIND_FRAME,
    PRESENTATION_FINGERPRINT_LABEL,
    PRESENTATION_SOURCE_LABEL,
    MarkdownRepository,
    format_fingerprints,
    split_ids,
)
from accord.repository.sections import strip_note
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.services.positioning import (
    WHOLE_SCOPE,
    PositioningService,
    accepted_scopes,
    applicable_positioning,
    defect_notes,
    latest_positioning,
    unrecorded_positioning_next_step,
)
from accord.services.public_records import REGISTER_OPERATION, PublicRecordService
from accord.vocabulary.settings import (
    CAPABILITY_CATEGORIES_KIND,
    CHANNELS_KIND,
    LEDGER_ENTRY_PREFIX,
    LEDGER_FRAME_PREFIX,
    PACKAGE_HYPOTHESIS_STATES_KIND,
    POSITIONING_TARGETS_KIND,
    PUBLIC_RECORD_KINDS_KIND,
    PUBLIC_RECORD_ROLES_KIND,
    PUBLIC_RECORDS_KEY,
    VOCABULARY_FILE,
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
PACKAGE_HYPOTHESIS_STATE_VOCABULARY = CONSTRAINT_BY_NAME["パッケージの仮説の状態の語彙"].name
POSITIONING_SCOPE_VOCABULARY = CONSTRAINT_BY_NAME["決めの適用範囲の語彙"].name

ORIGIN_SECTION_EXISTS = CONSTRAINT_BY_NAME["由来の節の実在"].name
PRESENTATION_URL_MATCHES = CONSTRAINT_BY_NAME["提示物の URL と公開記録の一致"].name
COPY_FRESHNESS = CONSTRAINT_BY_NAME["写しの鮮度"].name

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
FRAME_SOURCE_LABEL = "在籍職歴の枠の出典の節"
PRESENTATION_SOURCE_TEXT_LABEL = "提示物の出典の節"
PENDING_NOTE_LABEL = "注記が指す節"
ORIGIN_SECTION_LABEL = "由来の節"

# 指す先の型ごとの、読み方の絞りで外れた節を探す正本の役割の名前。外れた節の言い分けは、
# 指す先の型の読み方で外れた節だけを使う。別の型の読み方で外れた節を使うと、合っていない
# 読み方を広げよという直し方を返してしまう。
CAREER_KEYS = ("career",)
ENGAGEMENT_KEYS = ("engagements",)

# 写しの鮮度の違反の文で、出典の指紋の欄を指す語。台帳と提示物で同じ語を使う。
FINGERPRINT_FIELD_LABEL = PRESENTATION_FINGERPRINT_LABEL

# 語彙に照らす 3 つの欄の、正本での欄の名前。違反の文はこの語のまま欄を指す。
PUBLIC_RECORD_KIND_LABEL = "種類"
PUBLIC_RECORD_ROLE_LABEL = "役割"
CAPABILITY_CATEGORY_LABEL = "分類"


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
    FRAME_SOURCE_LABEL: "は、職歴の枠の ID に無い。実在する ID に書き換える。",
    PRESENTATION_SOURCE_TEXT_LABEL: (
        "は、職歴の枠にも受託案件にも無い ID である。実在する ID に書き換える。"
    ),
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
    "accord の形の読み方の絞り（見出しの深さと束ねる見出し）に、正本の節の位置が合っているかを確かめる。"
)


def records_behind(
    capabilities: tuple[Capability, ...] | list[Capability], records: list[PublicRecord]
) -> tuple[PublicRecord, ...]:
    """その機能たちの裏づけに ID が書かれている公開記録を、正本の並びで返す。"""
    wanted = {name for capability in capabilities for name in capability.evidence_sections}
    return tuple(record for record in records if record.id in wanted)


def provenance_of(settings: Settings) -> Provenance:
    """この検査が、どの置き場の語彙を、どの読み方で、どの版とどの置き場の accord で走ったかを作る。

    設定を読む層は型を知らない状態に保たれ、型の器の層は設定を知らない状態に保たれている。
    両方を見てよいのはサービス層だけなので、足跡の組み立てはここに置く。
    """
    try:
        version = importlib.metadata.version("accord")
    except importlib.metadata.PackageNotFoundError:
        version = "不明（未導入）"
    data = settings.source_dir.resolve()
    # spec: REQ-460
    return Provenance(
        # 設定ファイルは無いので、置き場の中で正本のほかに読む唯一のファイル（語彙）の名前を書く。
        # spec: REQ-461
        config_name=f"{data.name}/{VOCABULARY_FILE}",
        # 読み方は accord の形の 1 通りで、変える鍵を持たない。
        # spec: REQ-005
        reading=["既定"],
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
    source_keys: tuple[str, ...] | None = None,
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

    読み取り範囲の外の言い分けには、指す先の型の読み方（source_keys）で外れた節だけを使う。
    別の型として読めている ID も使わない。たとえば職歴の枠の ID は、受託案件の読み方では
    外れた節に入るが、職歴の枠としては読めているので、受託案件を指す欄に書かれたなら
    「範囲の外」ではなく「受託案件の ID に無い」と言う。
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
        if defect.invalid_fields and not defect.missing_fields:
            return (
                False,
                f"{label}「{wanted}」は {defect.file} の「{where}」に実在するが、"
                f"{defect.reason}ので型にできず、いまの正本として読んでいない。"
                f"直すのはこのファイルではなく、{defect.file} の「{where}」の値である。",
                [],
            )
        return (
            False,
            f"{label}「{wanted}」は {defect.file} の「{where}」に実在するが、"
            f"必須の欄{missing}が無いので型にできず、いまの正本として読んでいない。"
            f"直すのはこのファイルではなく、{defect.file} の「{where}」に"
            f"{missing}の行を足すことである。",
            [],
        )

    # spec: REQ-028
    read_elsewhere = set(snapshot.section_headings())
    for skipped in snapshot.skipped_headings:
        if not skipped.id or skipped.id != wanted:
            continue
        # spec: REQ-383
        if source_keys is not None and skipped.source_key not in source_keys:
            continue
        # spec: REQ-397
        if skipped.id in read_elsewhere:
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
            f"いまの読み取り範囲の外にある——{skipped.reason}。直し方は、"
            "正本のこの節を accord の形の読み取り範囲の中へ動かす（move_section・rename_heading）。",
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

    def inspect(self, scope: str | None = None, allow_targets: bool = False) -> ConsistencyReport:
        """範囲を受けて違反の一覧を返す。正本は 1 バイトも書き換えない。

        allow_targets は、決めの適用先の語（媒体ではない適用範囲）を範囲として受けるかどうか。
        整合の検査の操作そのものは受けず、決めの登記と材料の取り出しの中から呼ぶときだけ立てる。
        """
        snapshot = self.repository.load()
        target = self._resolve_scope(snapshot, scope, allow_targets)

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
        violations.extend(self._check_presentation_sources(snapshot, target))
        copy_violations, copy_notes = self._check_copy_freshness(snapshot, target)
        violations.extend(copy_violations)
        notes.extend(copy_notes)
        # ID の形式と ID の一意性は、範囲を絞っても正本全体で見る。一意性は 1 つのブロックだけを
        # 見ても言えず、絞った範囲の外にある項目と重なっていても違反だからである。
        # spec: REQ-362
        violations.extend(self._check_id_format_and_uniqueness(snapshot))

        # 台帳の読まなかった節の断りは先頭に積む。断りの上限は末尾から打ち切るので、
        # 先頭に置けば、ほかの断りが何件あっても落ちない。台帳を見ない範囲では書かない。
        if target.label == WHOLE_SCOPE:
            unread = unread_ledger_note(self.settings, snapshot)
            # spec: REQ-396
            if unread is not None:
                notes.insert(0, unread)

        return ConsistencyReport(
            provenance=provenance_of(self.settings),
            scope=target.label,
            violations=violations,
            notes=limit_notes(notes),
        )

    # ------------------------------------------------------------ 範囲

    def _resolve_scope(
        self, snapshot: SourceSnapshot, scope: str | None, allow_targets: bool = False
    ) -> InspectionScope | None:
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

        if allow_targets and scope in self.settings.positioning_targets:
            # 適用先の語には提示物も媒体の規約も無いので、媒体と同じ絞り方で、その語の決めから
            # 束と機能までを辿る（提示物は宛先が一致するものが無いので 0 件になる）。
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
        """公開記録の種類と役割、機能の分類、パッケージの仮説の状態、決めの適用範囲が、語彙にあるかを見る。

        登記の操作も書き込みの瞬間に同じことを見るが、正本には accord を通さずに入った行が残っていることがある。
        語彙の外の語でも型にはできるので読み込みは通り、必須の欄の欠けだけを見る検査は黙って通る。
        だから、裏づけ節名の実在と同じく、読み込んだ正本に対しても当て直す。
        語の外れたブロックを読み飛ばさず違反 1 件として挙げるので、材料の取り出しからは消えない。
        """
        violations: list[Violation] = []
        if self.settings.has_file(PUBLIC_RECORDS_KEY):
            records_file = self.settings.files[PUBLIC_RECORDS_KEY]
            # 種類と役割は別のルールなので、外れた側のルールの名前で違反を挙げる。
            fields = (
                # spec: REQ-368
                (
                    PUBLIC_RECORD_KIND_VOCABULARY,
                    PUBLIC_RECORD_KIND_LABEL,
                    self.settings.public_record_kinds,
                    PUBLIC_RECORD_KINDS_KIND,
                ),
                # spec: REQ-369
                (
                    PUBLIC_RECORD_ROLE_VOCABULARY,
                    PUBLIC_RECORD_ROLE_LABEL,
                    self.settings.public_record_roles,
                    PUBLIC_RECORD_ROLES_KIND,
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
                                f"{label}「{value}」は、語彙の「{key}」に無い。"
                                f"この行を下の候補のどれかに書き換えるか、語彙（{VOCABULARY_FILE}）の"
                                f"「{key}」に「{value}」を足す。"
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
                        f"語彙の「{CAPABILITY_CATEGORIES_KIND}」に無い。この行を下の候補のどれかの節へ移すか、"
                        f"語彙（{VOCABULARY_FILE}）の「{CAPABILITY_CATEGORIES_KIND}」に"
                        f"「{capability.category}」を足す。"
                    ),
                    candidates=list(categories),
                )
            )

        states = self.settings.package_hypothesis_states
        for package in target.packages:
            # spec: REQ-528
            # 値の末尾の括弧書きの注（「検証中（引き合い 2 件）」の括弧の部分）は落としてから照らす。
            if strip_note(package.hypothesis_state) in states:
                continue
            violations.append(
                Violation(
                    constraint=PACKAGE_HYPOTHESIS_STATE_VOCABULARY,
                    file=self.settings.files["packages"],
                    location=f"「{package.name}」（{package.id}）の節の「仮説の状態」の行",
                    expected=(
                        f"仮説の状態「{package.hypothesis_state}」は、語彙の「{PACKAGE_HYPOTHESIS_STATES_KIND}」に無い。"
                        f"この行を下の候補のどれかに書き換えるか、語彙（{VOCABULARY_FILE}）の"
                        f"「{PACKAGE_HYPOTHESIS_STATES_KIND}」に「{package.hypothesis_state}」を足す。"
                    ),
                    candidates=list(states),
                )
            )

        scopes = accepted_scopes(self.settings)
        # 全体の検査では、適用される決めだけでなく、積んだ決めのすべてを見る（過去の決めの直しも断るため）。
        # 媒体（か適用先の語）で絞った検査では、その語を適用範囲に持つ決めにだけ当てる。
        positionings = (
            snapshot.positionings
            if target.label == WHOLE_SCOPE
            else [item for item in snapshot.positionings if strip_note(item.scope) == target.label]
        )
        for positioning in positionings:
            # spec: REQ-529
            # 値の末尾の括弧書きの注は落としてから照らす。
            if strip_note(positioning.scope) in scopes:
                continue
            violations.append(
                Violation(
                    constraint=POSITIONING_SCOPE_VOCABULARY,
                    file=self.settings.files["positioning"],
                    location=f"{positioning.decided_on} の決めの「適用範囲」の行",
                    expected=(
                        f"適用範囲「{positioning.scope}」は、「{WHOLE_SCOPE}」でも、語彙の媒体の名前"
                        "でも決めの適用先の語でもない。この行を下の候補のどれかに書き換えるか、"
                        f"語彙（{VOCABULARY_FILE}）の「{CHANNELS_KIND}」か「{POSITIONING_TARGETS_KIND}」"
                        f"に「{positioning.scope}」を足す。"
                    ),
                    candidates=list(scopes),
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
        """職務経歴書の台帳の出典の節の ID が実在するか（注記と出典の節の実在）と、実在した節が
        公開可であるか（出典と裏づけの節の公開可否）を見る。実在しない節は公開可否を見ない。

        案件のブロックは受託案件の ID を 1 つ、在籍職歴の枠のブロックは職歴の枠の ID を 1 つ以上
        （半角のスラッシュで区切る）指す。照らす相手も、公開可の候補も、指す先の型から取る。
        """
        engagements = {item.id: item.disclosure for item in snapshot.engagements}
        frames = {item.id: item.disclosure for item in snapshot.career_frames}
        labels = snapshot.labels()
        violations: list[Violation] = []

        for entry in target.ledger_entries:
            location = f"{_ledger_place(entry)}の「出典の節」の行"
            if entry.kind == LEDGER_KIND_FRAME:
                # spec: REQ-379
                pool, label, keys = frames, FRAME_SOURCE_LABEL, CAREER_KEYS
                # spec: REQ-381
                wanted_ids = split_ids(entry.source_section)
            else:
                pool, label, keys = engagements, LEDGER_SOURCE_LABEL, ENGAGEMENT_KEYS
                wanted_ids = [entry.source_section]
            public = [
                identifier
                for identifier, disclosure in pool.items()
                if not disclosure.startswith(PRIVATE_DISCLOSURE_PREFIX)
            ]

            for section in wanted_ids:
                # spec: REQ-380
                # spec: REQ-383
                readable, expected, candidates = explain_heading(
                    self.settings, snapshot, label, section, list(pool), keys
                )
                if not readable:
                    violations.append(
                        Violation(
                            constraint=NOTE_AND_SOURCE_SECTION_EXISTS,
                            file=self.settings.files[LEDGER_KEY],
                            location=location,
                            expected=expected,
                            candidates=candidates,
                        )
                    )
                    continue

                disclosure = pool[section]
                # spec: REQ-019
                # spec: REQ-382
                if disclosure.startswith(PRIVATE_DISCLOSURE_PREFIX):
                    violations.append(
                        Violation(
                            constraint=SOURCE_AND_EVIDENCE_DISCLOSURE,
                            file=self.settings.files[LEDGER_KEY],
                            location=location,
                            expected=(
                                f"出典の節「{labelled(section, labels)}」の公開可否は"
                                f"「{disclosure}」なので、そこから写した中身は外に出せない。"
                                "公開可の節の ID に差し替えるか、このブロックを台帳から外す。"
                                + candidate_text(public, labels)
                            ),
                            candidates=public,
                        )
                    )
        return violations

    def _check_presentation_sources(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> list[Violation]:
        """提示物が宣言した出典の節の ID が、職歴の枠か受託案件の ID として実在するかを見る。"""
        pool = snapshot.section_headings()
        violations: list[Violation] = []
        for presentation in target.presentations:
            for section in presentation.source_sections:
                # spec: REQ-393
                readable, expected, candidates = explain_heading(
                    self.settings, snapshot, PRESENTATION_SOURCE_TEXT_LABEL, section, pool
                )
                if readable:
                    continue
                violations.append(
                    Violation(
                        constraint=NOTE_AND_SOURCE_SECTION_EXISTS,
                        file=presentation.path,
                        location=f"「{PRESENTATION_SOURCE_LABEL}」の行",
                        expected=expected,
                        candidates=candidates,
                    )
                )
        return violations

    def _check_copy_freshness(
        self, snapshot: SourceSnapshot, target: InspectionScope
    ) -> tuple[list[Violation], list[str]]:
        """写しの鮮度を見る。写しが控えた出典の指紋と、出典の節のいまの本文の指紋を比べる。

        写しは、職務経歴書の台帳のブロックと、出典の節を宣言した提示物である。控えた指紋が
        いまの指紋と違う出典と、指紋の控えが無い出典（未確認の写し）があれば、その写しを名指しした
        違反を 1 件挙げる。見るのは「写した後に正本の節が変わったか」だけで、写しの文言が正本と
        合っているかは見ない。出典の節に書いていない ID の組は見ず、実在しない出典や読めていない
        出典は、実在の違反が別に挙がるのでここでは判定しない。
        出典の節を宣言していない提示物は判定の外にあるので、その件数を断りに書く。
        """
        engagement_ids = {item.id for item in snapshot.engagements}
        frame_ids = {item.id for item in snapshot.career_frames}
        violations: list[Violation] = []

        for entry in target.ledger_entries:
            if entry.kind == LEDGER_KIND_FRAME:
                sources, readable = split_ids(entry.source_section), frame_ids
            else:
                sources, readable = [entry.source_section], engagement_ids
            violation = self._freshness_violation(
                snapshot,
                sources=sources,
                readable=readable,
                recorded=entry.source_fingerprints,
                file=self.settings.files[LEDGER_KEY],
                # spec: REQ-384
                location=f"{_ledger_place(entry)}の「{FINGERPRINT_FIELD_LABEL}」の行",
            )
            if violation is not None:
                violations.append(violation)

        undeclared: list[str] = []
        for presentation in target.presentations:
            if not presentation.source_sections:
                undeclared.append(presentation.path)
                continue
            # spec: REQ-391
            violation = self._freshness_violation(
                snapshot,
                sources=presentation.source_sections,
                readable=engagement_ids | frame_ids,
                recorded=presentation.source_fingerprints,
                file=presentation.path,
                location=f"「{FINGERPRINT_FIELD_LABEL}」の行",
            )
            if violation is not None:
                violations.append(violation)

        notes: list[str] = []
        if undeclared:
            # spec: REQ-392
            notes.append(
                f"出典の節を宣言していない提示物が {len(undeclared)} 件ある"
                f"（{fold_names(undeclared, keep=NAME_SAMPLE_COUNT)}）。"
                "この提示物は、写した後に正本の節が変わったかを見ていない。"
                f"見させるには、先頭の欄に「- {PRESENTATION_SOURCE_LABEL}: 写し元の節の ID」の行を足す。"
                f"足した後の検査が、書くべき「{FINGERPRINT_FIELD_LABEL}」の行を返す。"
            )
        return violations, notes

    def _freshness_violation(
        self,
        snapshot: SourceSnapshot,
        *,
        sources: list[str],
        readable: set[str],
        recorded: list[dict[str, str]],
        file: str,
        location: str,
    ) -> Violation | None:
        """写し 1 つの出典を、控えた指紋といまの指紋で比べる。食い違いか控えの無い出典があれば違反 1 件。"""
        labels = snapshot.labels()
        kept = {
            pair.get(FINGERPRINT_ID_KEY, ""): pair.get(FINGERPRINT_VALUE_KEY, "")
            for pair in recorded
        }
        current: list[tuple[str, str]] = []
        changed: list[str] = []
        unconfirmed: list[str] = []
        for identifier in dict.fromkeys(sources):
            fingerprint = snapshot.section_fingerprints.get(identifier)
            # spec: REQ-390
            if identifier not in readable or fingerprint is None:
                continue
            current.append((identifier, fingerprint))
            written = kept.get(identifier, "")
            # spec: REQ-387
            if not written:
                unconfirmed.append(identifier)
            # spec: REQ-388
            elif written != fingerprint:
                changed.append(identifier)

        if not changed and not unconfirmed:
            return None

        reasons: list[str] = []
        for identifier in changed:
            # spec: REQ-385
            reasons.append(
                f"出典の節「{labelled(identifier, labels)}」の本文が、写しに控えた指紋"
                f"「{kept[identifier]}」の後に変わった（いまの本文の指紋は"
                f"「{snapshot.section_fingerprints[identifier]}」）。"
            )
        if unconfirmed:
            names = "、".join(f"「{labelled(item, labels)}」" for item in unconfirmed)
            reasons.append(
                f"出典の節{names}は指紋の控えが無いので、写した後に本文が変わったかを"
                "確かめられない（未確認の写し）。"
            )
        # spec: REQ-386
        # 示す行は、正本にそのまま書き足せば読まれる箇条書きの形「- 出典の指紋: …」にする。
        line = f"- {FINGERPRINT_FIELD_LABEL}: {format_fingerprints(current)}"
        return Violation(
            constraint=COPY_FRESHNESS,
            file=file,
            location=location,
            expected=(
                "".join(reasons)
                + "この写しを、いまの出典の節の本文と読み比べて、食い違う記述を直す。"
                f"読み比べ終えたら、「{FINGERPRINT_FIELD_LABEL}」の行を次の 1 行に書き換える"
                f"（行が無ければ足す）: {line}"
            ),
            candidates=[],
        )


def _ledger_place(entry: ResumeLedger) -> str:
    """台帳のブロック 1 つを、違反の文で名指しする言い方にする。番号の無い在籍職歴の枠は見出しだけで指す。"""
    if entry.kind == LEDGER_KIND_FRAME:
        if entry.entry_number:
            return f"在籍職歴の枠 {entry.entry_number}（{entry.heading}）"
        return f"在籍職歴の枠（{entry.heading}）"
    return f"案件番号 {entry.entry_number}（{entry.heading}）"


def unread_ledger_note(settings: Settings, snapshot: SourceSnapshot) -> str | None:
    """台帳の読まなかった節を、件数と見出しを持つ 1 件の断りにする。すべて読んだなら None。"""
    unread = snapshot.unread_ledger_sections
    # spec: REQ-395
    if not unread:
        return None
    headings = "、".join(f"「{item.heading}」" for item in unread)
    reasons = " / ".join(dict.fromkeys(item.reason for item in unread))
    # spec: REQ-394
    return (
        f"職務経歴書の台帳 {settings.files.get(LEDGER_KEY, LEDGER_KEY)} の節のうち "
        f"{len(unread)} 件は、読み方の絞りで外れたので読んでいない（{headings}。外れた理由: {reasons}）。"
        "この節は、出典の節の実在も写しの鮮度も見ていない。案件か在籍職歴の枠として見させるなら、"
        f"見出しを「{LEDGER_ENTRY_PREFIX}」か「{LEDGER_FRAME_PREFIX}」で始める（rename_heading）。"
    )


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
            ConsistencyService._check_presentation_sources,
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
    PACKAGE_HYPOTHESIS_STATE_VOCABULARY: {
        "check_consistency": (ConsistencyService._check_vocabulary,),
    },
    POSITIONING_SCOPE_VOCABULARY: {
        "check_consistency": (ConsistencyService._check_vocabulary,),
    },
    ORIGIN_SECTION_EXISTS: {
        "register_public_record": (PublicRecordService.register,),
        "check_consistency": (ConsistencyService._check_public_record_origins,),
    },
    PRESENTATION_URL_MATCHES: {
        "check_consistency": (ConsistencyService._check_presentation_urls,),
    },
    COPY_FRESHNESS: {
        "check_consistency": (ConsistencyService._check_copy_freshness,),
    },
}


def enforcement_for(constraint_name: str) -> dict[str, tuple[Callable[..., Any], ...]]:
    """制約の名前から、それを執行する操作と関数を引く。結び付きが無ければ空の表。"""
    return ENFORCEMENT.get(constraint_name, {})
