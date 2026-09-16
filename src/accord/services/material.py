"""文面の材料を取り出す操作。

この段では骨だけを置く。中身は「材料の取り出し」の段で埋める。
公開不可の節を落とし、落としたことを警告に書く執行も、その段で入れる。
"""

from __future__ import annotations

from accord.models.results import Material, MaterialRequest
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import Settings

LATER_STAGE = "この操作は後の段で実装する"


class MaterialService:
    """媒体向けの文面を書くための材料を、正本から射影して返す。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def assemble(self, request: MaterialRequest) -> Material:
        """材料を組み立てる（材料の取り出しの段で実装する）。"""
        return Material(
            channel=request.channel,
            warnings=[f"{LATER_STAGE}（材料の取り出しの段）。"],
        )
