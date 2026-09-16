"""正本全体を制約に当て、違反の一覧を返す操作。

この段では骨だけを置く。中身は「整合検査」の段で埋める。
違反 1 件ごとに「どのファイルのどこを、何に合わせるか」を付けるのも、その段の仕事である。
"""

from __future__ import annotations

from accord.models.results import ConsistencyReport
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import Settings

LATER_STAGE = "この操作は後の段で実装する"


class ConsistencyService:
    """整合を検査する。正本は変えない。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def inspect(self, scope: str | None = None) -> ConsistencyReport:
        """範囲を受けて違反の一覧を返す（整合検査の段で実装する）。"""
        return ConsistencyReport(
            scope=scope or "全体",
            notes=[f"{LATER_STAGE}（整合検査の段）。"],
        )
