"""売り方の決めを読む操作と、登記する操作。

「その媒体に適用される決め」の選び方（媒体を名指しした決めの最新、無ければ「全体」の最新）と、
登記の操作の入力の型の組み立ては、この文書が持つ。整合検査と材料の取り出しは、同じ関数を呼ぶ。
同じ選び方を 2 か所に書くと、片方だけを直したときに、読んだ看板と検査した看板が食い違うからである。

登記は、制約を見てから 1 度だけ書き戻す。通らない入力は例外を投げずに拒否として返し、
そのときは決めの正本を 1 バイトも変えない。登記が通った後に走る 2 つの検査（定義の鮮度と、
旧い束を宣言する提示物）は整合検査の関数をそのまま呼ぶ。判定を 2 か所に書かないためである。
"""

from __future__ import annotations

from accord.models.constraints import CONSTRAINTS
from accord.models.ontology import (
    OntologyType,
    field_example,
    load_ontology,
    missing_required_fields,
)
from accord.models.results import (
    NextAction,
    PositioningDraft,
    PositioningView,
    Rejection,
    SourceDefect,
    SourceSnapshot,
    Violation,
    WriteResult,
    candidate_text,
    close_names,
    fold_names,
    labelled,
)
from accord.models.types import Positioning
from accord.repository.markdown_repository import (
    EXCEPTION_PRESENTATION_KEY,
    EXCEPTION_REASON_KEY,
    MarkdownRepository,
)
from accord.vocabulary.settings import Settings

# 適用範囲の「全体」。媒体の名前は設定から読むが、この語だけは型の欄の定義（適用範囲は
# 媒体の名前か「全体」）が持つ構造の語なので、設定ではなくここに置く。
WHOLE_SCOPE = "全体"

# 決めの入力の型を組み立てるときに引く、型の名前。
POSITIONING_TYPE_NAME = "Positioning"

# 操作の名前。次の一手にそのまま載せる。
READ_OPERATION = "get_positioning"
RECORD_OPERATION = "record_positioning"

# 制約は名前で参照する。名前を正本（ontology.yaml）で変えたら、ここで鍵が見つからず落ちる。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
POSITIONING_REQUIRED_FIELDS = CONSTRAINT_BY_NAME["決めの必須欄"].name
PACKAGE_FRESHNESS = CONSTRAINT_BY_NAME["パッケージ定義の鮮度"].name
OFFERING_CLAIM_MATCHES = CONSTRAINT_BY_NAME["提示物の宣言と看板の一致"].name

# 次の 2 つは制約 12 つではなく、型 Positioning の欄の定義である（適用範囲は媒体の名前か「全体」、
# 前面に出す束はパッケージ定義に実在する ID に限る）。選べる媒体の名前は設定が持つ。
POSITIONING_SCOPE_ENUM = "適用範囲の列挙"
HEADLINE_PACKAGE_EXISTS = "前面に出す束の実在"

# 束ねた断り 1 件に、代表として名前で並べる場所の数。残りは件数に畳む。
DEFECT_SAMPLE_COUNT = 3

# 束ねた断りそのものの上限。「どの正本の、どの欄が欠けたか」の組をこの数まで並べる。
DEFECT_GROUP_LIMIT = 12


def latest_positioning(positionings: list[Positioning], scope: str) -> Positioning | None:
    """適用範囲がその語に一致する決めのうち、いちばん新しい 1 件を返す。

    同じ日付が並んだときは、正本の後ろにあるブロックを新しいものとして扱う（決めは下に足すため）。
    """
    matching = [(index, item) for index, item in enumerate(positionings) if item.scope == scope]
    if not matching:
        return None
    return max(matching, key=lambda pair: (pair[1].decided_on, pair[0]))[1]


def applicable_positioning(
    positionings: list[Positioning], channel: str
) -> Positioning | None:
    """その媒体に適用される決め。媒体を名指しした決めが無ければ「全体」の最新の 1 件。"""
    return latest_positioning(positionings, channel) or latest_positioning(
        positionings, WHOLE_SCOPE
    )


def positioning_type() -> OntologyType | None:
    """決めの型の定義を、型の正本から引く。欄の名前も必須の別もここが出どころである。"""
    return load_ontology().type_named(POSITIONING_TYPE_NAME)


def positioning_input_type() -> str:
    """決めを登記する操作の入力の型を、型の正本から 1 行にする。

    欄の名前と必須の別を手で書き写すと、正本を直したときに食い違う。だから正本から引く。
    """
    entry = positioning_type()
    if entry is None:
        return ""
    return "、".join(
        f"{field.label}（{field.type}・{'必須' if field.required else '任意'}）"
        for field in entry.fields
    )


def defect_notes(settings: Settings, snapshot: SourceSnapshot) -> list[str]:
    """型にできなかったブロックや節を、同じ型ごとに 1 件へ束ねた断りの文にする。

    決めとパッケージには、登記し直す書きの操作を添える（この 2 つだけ、正本を直す操作がある）。
    それ以外の正本（機能の台帳・職歴の枠・受託案件・職務経歴書の台帳・提示物）は、直す操作を
    持たないので、欄を書き足すことだけを案内する。読み込みで飛ばしたことを黙っていると、
    隣か 1 つ前のブロックが「いまの正本」として通り、正しい中身に逆向きの直し先が返る。

    1 件ずつ並べると、同じ欠け方が数百件並んで返り値そのものが受け取る側の口に載らなくなる。
    かといって件数だけにすると、直しに行く場所が消える。だから「どの正本の、どの欄が欠けたか」で
    束ね、代表をいくつか名前で見せて、残りは件数に畳む。
    """
    next_steps = {
        "positioning": f"欠けた欄を書き足すか、{RECORD_OPERATION} で登記し直す。",
        "packages": "欠けた欄を書き足すか、revise_package で登記し直す。",
    }

    groups: dict[tuple[str, tuple[str, ...]], list[SourceDefect]] = {}
    for defect in snapshot.defects:
        groups.setdefault((defect.source_key, tuple(defect.missing_fields)), []).append(defect)

    notes: list[str] = []
    for (source_key, missing_fields), defects in list(groups.items())[:DEFECT_GROUP_LIMIT]:
        files = {defect.file for defect in defects}
        places = [
            defect.location if len(files) == 1 else f"{defect.file} の{defect.location}"
            for defect in defects
        ]
        missing = "、".join(f"「{name}」" for name in missing_fields)
        where = settings.files.get(source_key, next(iter(files), ""))
        notes.append(
            f"必須の欄{missing}が無いので型にできず、いまの正本として読んでいないブロックが "
            f"{where} に {len(defects)} 件ある"
            f"（{fold_names(places, keep=DEFECT_SAMPLE_COUNT)}）。"
            + next_steps.get(source_key, "欠けた欄を書き足す。")
        )

    hidden = list(groups.values())[DEFECT_GROUP_LIMIT:]
    if hidden:
        notes.append(
            f"ほかに {len(hidden)} 通りの欠け方が、合わせて "
            f"{sum(len(defects) for defects in hidden)} 件ある。"
        )
    return notes


def unrecorded_positioning_next_step() -> str:
    """決めが 1 件も無いときに返す、次の一手の 1 行。読みの 2 つと検査が同じ文を返す。"""
    return f"先に決めを登記する（{RECORD_OPERATION}）。入力の型: {positioning_input_type()}"


def unknown_channel_notes(settings: Settings, channel: str, operation: str) -> list[str]:
    """媒体の名前が実在しないときの案内。拒否ではなく、実在する名前の一覧を返す。"""
    return [
        f"媒体「{channel}」は、設定ファイル {settings.config_path.name} の媒体の一覧に無い。",
        "実在する媒体: " + " / ".join(settings.channels),
        f"上の名前のどれかをそのまま渡して、もう一度 {operation} を呼ぶ。",
    ]


class PositioningService:
    """いまの決めを読む、決めを登記する。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def current(self, channel: str | None = None) -> PositioningView:
        """その媒体に適用される最新の決めと、前面に出す束のパッケージを返す。

        媒体を省くと「全体」の決めを返す。決めが 1 件も無いときと、媒体の名前が実在しないときは、
        拒否ではなく断りと次の一手を warnings に載せて返す。正本は 1 バイトも読み替えない。
        """
        if channel is not None and channel not in self.settings.channels:
            return PositioningView(
                warnings=unknown_channel_notes(self.settings, channel, READ_OPERATION)
                + [f"媒体を省いて呼ぶと、適用範囲「{WHOLE_SCOPE}」の決めが返る。"]
            )

        snapshot = self.repository.load()
        # 欄が欠けていて決めとして読めなかったブロックは、断りの先頭に出す。
        warnings: list[str] = defect_notes(self.settings, snapshot)

        if not snapshot.positionings:
            return PositioningView(
                warnings=warnings
                + [
                    "決めが未登記である。いま何を前面に出すかは、まだどこにも登記されていない。",
                    unrecorded_positioning_next_step(),
                ]
            )

        if channel is None:
            positioning = latest_positioning(snapshot.positionings, WHOLE_SCOPE)
        else:
            positioning = latest_positioning(snapshot.positionings, channel)
            if positioning is None:
                positioning = latest_positioning(snapshot.positionings, WHOLE_SCOPE)
                if positioning is not None:
                    warnings.append(
                        f"媒体「{channel}」を名指しした決めは無いので、"
                        f"適用範囲「{WHOLE_SCOPE}」の決めを返した。"
                    )

        if positioning is None:
            scopes = " / ".join(dict.fromkeys(item.scope for item in snapshot.positionings))
            return PositioningView(
                warnings=warnings
                + [
                    f"この呼び方に当たる決めが無い。登記されている決めの適用範囲は {scopes} である。",
                    unrecorded_positioning_next_step(),
                ]
            )

        package = next(
            (item for item in snapshot.packages if item.id == positioning.headline_package),
            None,
        )
        if package is None:
            listed = " / ".join(
                labelled(item.id, {item.id: item.name}) for item in snapshot.packages
            )
            warnings.append(
                f"決めが前面に出す束「{positioning.headline_package}」が、"
                f"パッケージ定義に無い ID である。実在する束: {listed}。"
                f"束の ID を直して {RECORD_OPERATION} で決めを登記し直す。"
            )

        return PositioningView(positioning=positioning, package=package, warnings=warnings)

    def record(self, draft: PositioningDraft) -> WriteResult:
        """決めを 1 ブロック登記し、その場で 2 つの検査の結果を返す。

        制約を先に全部見て、通ると決まってから 1 度だけ書き戻す。拒否のときは書き戻しに
        入らないので、決めの正本は 1 バイトも変わらない。
        登記が通った後の 2 つ（定義の鮮度、旧い束を宣言する提示物）は拒否ではなく報告である。
        決めそのものは正しく、直すのは決めの側ではなく定義と文面の側だからである。
        """
        snapshot = self.repository.load()

        rejection = self._rejection(snapshot, draft)
        if rejection is not None:
            return WriteResult(accepted=False, rejection=rejection)

        positioning = Positioning(
            decided_on=draft.decided_on,
            scope=draft.scope,
            headline_package=draft.headline_package,
            rationale=draft.rationale,
            exceptions=[
                {
                    EXCEPTION_PRESENTATION_KEY: entry.presentation,
                    EXCEPTION_REASON_KEY: entry.reason,
                }
                for entry in draft.exceptions
            ],
        )
        self.repository.append_positioning(positioning)

        stale, outdated = self._checks_after_record(positioning)
        return WriteResult(
            accepted=True,
            recorded={
                "登記した決め": positioning.model_dump(mode="json"),
                PACKAGE_FRESHNESS: [violation.as_note() for violation in stale]
                or [
                    f"「{positioning.headline_package}」の定義の最終更新は、"
                    f"この決めの日付 {positioning.decided_on} より古くない。"
                ],
                OFFERING_CLAIM_MATCHES: {
                    "件数": len(outdated),
                    "ファイル": [violation.file for violation in outdated],
                },
            },
            warnings=[violation.as_note() for violation in stale + outdated],
        )

    # ------------------------------------------------------------ 登記の部品

    def _rejection(self, snapshot: SourceSnapshot, draft: PositioningDraft) -> Rejection | None:
        """入力を制約に当てる。通れば None を返し、通らなければ次の一手つきの拒否を返す。"""
        missing = missing_required_fields(POSITIONING_TYPE_NAME, draft)
        if missing:
            return Rejection(
                constraint=POSITIONING_REQUIRED_FIELDS,
                reason=(
                    "決めの必須の欄"
                    + "、".join(f"「{field.label}」" for field in missing)
                    + "が無い。欄のそろわない決めは、いまの看板として読めない。"
                ),
                next_action=NextAction(
                    operation=RECORD_OPERATION,
                    missing_fields=[field.label for field in missing],
                    example="\n".join(field_example(field) for field in missing),
                ),
            )

        scopes = [WHOLE_SCOPE, *self.settings.channels]
        if draft.scope not in scopes:
            return Rejection(
                constraint=POSITIONING_SCOPE_ENUM,
                reason=(
                    f"適用範囲「{draft.scope}」は、媒体の名前でも「{WHOLE_SCOPE}」でもない。"
                    f"媒体の名前は設定ファイル {self.settings.config_path.name} の一覧に限る。"
                ),
                next_action=NextAction(
                    operation=RECORD_OPERATION,
                    candidates=scopes,
                    example=(
                        f"すべての媒体に効かせるなら「{WHOLE_SCOPE}」、"
                        "媒体 1 つに限るなら上の候補の媒体名をそのまま渡す。"
                    ),
                ),
            )

        names = [item.id for item in snapshot.packages]
        if draft.headline_package not in names:
            labels = snapshot.labels()
            candidates = close_names(str(draft.headline_package), names, labels)
            return Rejection(
                constraint=HEADLINE_PACKAGE_EXISTS,
                reason=(
                    f"前面に出す束「{draft.headline_package}」は、パッケージ定義に無い ID である。"
                    + candidate_text(candidates, labels)
                ),
                next_action=NextAction(
                    operation=RECORD_OPERATION,
                    candidates=candidates,
                    example=(
                        "上の候補をそのまま前面に出す束に渡して、"
                        f"もう一度 {RECORD_OPERATION} を呼ぶ。"
                        "まだ定義していない束を看板にするなら、先に revise_package で定義する。"
                    ),
                ),
            )

        return None

    def _checks_after_record(
        self, positioning: Positioning
    ) -> tuple[list[Violation], list[Violation]]:
        """登記のあとに走る 2 つの検査を、整合検査に頼んで結果だけ受け取る。

        鮮度も宣言の一致も判定は整合検査が持っている。ここで判定し直さない。
        読み込みを関数の中で行うのは、整合検査がこの文書を読み込んでいて輪になるためである。
        """
        from accord.services.consistency import ConsistencyService

        scope = None if positioning.scope == WHOLE_SCOPE else positioning.scope
        report = ConsistencyService(self.settings, self.repository).inspect(scope)
        stale = [item for item in report.violations if item.constraint == PACKAGE_FRESHNESS]
        outdated = [item for item in report.violations if item.constraint == OFFERING_CLAIM_MATCHES]
        return stale, outdated
