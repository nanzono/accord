"""売り方の決めを読む操作と、登記する操作。

いまの決めを読む操作はこの文書で実装する。登記する操作は「書きの操作 3 つ」の段で埋める。
未実装の操作は例外を投げず、受け付けなかったことと次の一手を返り値で返す。

「その媒体に適用される決め」の選び方（媒体を名指しした決めの最新、無ければ「全体」の最新）と、
登記の操作の入力の型の組み立ては、この文書が持つ。整合検査と材料の取り出しは、同じ関数を呼ぶ。
同じ選び方を 2 か所に書くと、片方だけを直したときに、読んだ看板と検査した看板が食い違うからである。
"""

from __future__ import annotations

from accord.models.ontology import load_ontology
from accord.models.results import (
    NextAction,
    PositioningDraft,
    PositioningView,
    Rejection,
    WriteResult,
)
from accord.models.types import Positioning
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import Settings

# 後の段で実装する操作が返す断り。
LATER_STAGE = "この操作は後の段で実装する"

# 適用範囲の「全体」。媒体の名前は設定から読むが、この語だけは型の欄の定義（適用範囲は
# 媒体の名前か「全体」）が持つ構造の語なので、設定ではなくここに置く。
WHOLE_SCOPE = "全体"

# 決めの入力の型を組み立てるときに引く、型の名前。
POSITIONING_TYPE_NAME = "Positioning"

# 操作の名前。次の一手にそのまま載せる。
READ_OPERATION = "get_positioning"
RECORD_OPERATION = "record_positioning"


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


def positioning_input_type() -> str:
    """決めを登記する操作の入力の型を、型の正本から 1 行にする。

    欄の名前と必須の別を手で書き写すと、正本を直したときに食い違う。だから正本から引く。
    """
    for entry in load_ontology().types:
        if entry.name != POSITIONING_TYPE_NAME:
            continue
        return "、".join(
            f"{field.label}（{field.type}・{'必須' if field.required else '任意'}）"
            for field in entry.fields
        )
    return ""


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
        if not snapshot.positionings:
            return PositioningView(
                warnings=[
                    "決めが未登記である。いま何を前面に出すかは、まだどこにも登記されていない。",
                    unrecorded_positioning_next_step(),
                ]
            )

        warnings: list[str] = []
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
                warnings=[
                    f"この呼び方に当たる決めが無い。登記されている決めの適用範囲は {scopes} である。",
                    unrecorded_positioning_next_step(),
                ]
            )

        package = next(
            (item for item in snapshot.packages if item.name == positioning.headline_package),
            None,
        )
        if package is None:
            warnings.append(
                f"決めが前面に出す束「{positioning.headline_package}」が、パッケージ定義に無い。"
                f"実在する束: {' / '.join(item.name for item in snapshot.packages)}。"
                f"束の名前を直して {RECORD_OPERATION} で決めを登記し直す。"
            )

        return PositioningView(positioning=positioning, package=package, warnings=warnings)

    def record(self, draft: PositioningDraft) -> WriteResult:
        """決めを 1 ブロック登記する（書きの操作 3 つの段で実装する）。"""
        return WriteResult(
            accepted=False,
            rejection=Rejection(
                constraint="決めの必須欄",
                reason=f"{LATER_STAGE}。いまは決めの正本を 1 バイトも変えない。",
                next_action=NextAction(
                    operation=RECORD_OPERATION,
                    example="書きの操作 3 つの段が済んでから、同じ入力でもう一度呼ぶ。",
                ),
            ),
        )
