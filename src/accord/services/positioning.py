"""売り方の決めを読む操作と、登記する操作。

この段では骨だけを置く。中身は「材料の取り出し」と「書きの操作 3 つ」の段で埋める。
未実装の操作は例外を投げず、受け付けなかったことと次の一手を返り値で返す。
"""

from __future__ import annotations

from accord.models.results import (
    NextAction,
    PositioningDraft,
    PositioningView,
    Rejection,
    WriteResult,
)
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import Settings

# 後の段で実装する操作が返す断り。
LATER_STAGE = "この操作は後の段で実装する"


class PositioningService:
    """いまの決めを読む、決めを登記する。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def current(self, channel: str | None = None) -> PositioningView:
        """その媒体に適用される最新の決めを返す（材料の取り出しの段で実装する）。"""
        return PositioningView(warnings=[f"{LATER_STAGE}（材料の取り出しの段）。"])

    def record(self, draft: PositioningDraft) -> WriteResult:
        """決めを 1 ブロック登記する（書きの操作 3 つの段で実装する）。"""
        return WriteResult(
            accepted=False,
            rejection=Rejection(
                constraint="決めの必須欄",
                reason=f"{LATER_STAGE}。いまは決めの正本を 1 バイトも変えない。",
                next_action=NextAction(
                    operation="record_positioning",
                    example="書きの操作 3 つの段が済んでから、同じ入力でもう一度呼ぶ。",
                ),
            ),
        )
