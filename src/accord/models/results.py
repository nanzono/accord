"""操作が受け取る入力と、返す値の型。手で書く（生成物ではない）。

拒否は例外ではなく返り値で表す。呼んだ側が、返ってきた「次の一手」を読んで自分で
呼び直せるようにするためである。だから書きの操作は、通っても通らなくても WriteResult を返す。

正本の 7 つの型は生成物の types.py にあり、この文書はそれを組み合わせた器だけを持つ。
"""

from __future__ import annotations

import difflib
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from accord.models.types import (
    Capability,
    CareerFrame,
    Engagement,
    Package,
    Positioning,
    Presentation,
    ResumeLedger,
)

# 公開可否の欄が、外に出せないことを表すときの書き出し。
# 欄には理由まで書けるので（「公開不可（在籍先の名前を出さない約束があるため）」）、
# 語の一致ではなく書き出しで見る。この 1 か所を、検査も材料の取り出しも読む。
PRIVATE_DISCLOSURE_PREFIX = "公開不可"

# 近い名前を探すときの緩さ。近いものが 1 つも出ないときは、実在する名前をそのまま並べる。
CLOSE_MATCH_CUTOFF = 0.3
CLOSE_MATCH_COUNT = 3
FALLBACK_COUNT = 5


def close_names(wanted: str, pool: list[str]) -> list[str]:
    """実在する名前のうち、渡された名前に近いものを返す。近いものが無ければ先頭から並べる。

    候補は「そのまま渡し直せば通る名前」に限る、という決めなので、探す先は必ず実在する名前の
    一覧である。拒否も検査も同じ候補の出し方をするように、この 1 か所を全員が呼ぶ。
    """
    close = difflib.get_close_matches(wanted, pool, n=CLOSE_MATCH_COUNT, cutoff=CLOSE_MATCH_CUTOFF)
    return close or pool[:FALLBACK_COUNT]


class NextAction(BaseModel):
    """拒否のときに返す「次に何をすべきか」。何が悪いかだけで終わらせないための欄。"""

    operation: str = Field(description="次に呼ぶ操作の名前")
    missing_fields: list[str] = Field(default_factory=list, description="欠けていた欄の名前")
    candidates: list[str] = Field(
        default_factory=list, description="そのまま渡せば通る、実在する名前の候補"
    )
    example: str = Field(default="", description="書き方の例")


class Rejection(BaseModel):
    """受け付けなかったことの説明。どの制約に当たったかと、次の一手を持つ。"""

    constraint: str = Field(
        description="当たった制約の名前（ontology.yaml の制約の名前か、型の欄の定義の名前）"
    )
    reason: str = Field(description="何が通らなかったか")
    next_action: NextAction = Field(description="次に何をすべきか")


class WriteResult(BaseModel):
    """書きの操作の返り値。受け付けたときも拒否したときも、この型で返る。"""

    accepted: bool = Field(description="正本に書き込んだかどうか")
    recorded: dict[str, Any] = Field(
        default_factory=dict, description="登記した内容（拒否のときは空）"
    )
    warnings: list[str] = Field(
        default_factory=list, description="書き込みは通ったが、後で直したほうがよいこと"
    )
    rejection: Rejection | None = Field(
        default=None, description="受け付けなかった理由と次の一手（通ったときは None）"
    )


class Violation(BaseModel):
    """整合検査が挙げる違反 1 件。どのファイルのどこを、何に合わせるかを持つ。"""

    constraint: str = Field(description="破られた制約の名前")
    file: str = Field(description="違反のあるファイル")
    location: str = Field(description="ファイルの中のどこか（節の見出し、案件番号など）")
    expected: str = Field(description="何に合わせるべきか")
    candidates: list[str] = Field(default_factory=list, description="合わせ先の候補")

    def as_note(self) -> str:
        """違反 1 件を、警告の 1 行にする。

        違反を型のまま持たない返り値（材料の警告、登記のあとの報告）が、この 1 行を使う。
        候補まで載せるのは、文だけを読む側に「下の候補」の実体が届かないと、
        直し先を探しに正本を開く羽目になるからである。
        """
        text = f"{self.constraint}: {self.file} の{self.location} — {self.expected}"
        if self.candidates:
            text += "候補: " + " / ".join(self.candidates)
        return text


class PositioningException(BaseModel):
    """決めに反してよい提示物と、その理由の組。"""

    presentation: str = Field(description="例外にする提示物のファイル名")
    reason: str = Field(description="なぜこの提示物は決めに合わせなくてよいのか")


class PositioningDraft(BaseModel):
    """決めを登記する操作の入力。欠けた欄を見つけるため、どの欄も空を許して受ける。"""

    decided_on: date | None = None
    scope: str | None = None
    headline_package: str | None = None
    rationale: str | None = None
    exceptions: list[PositioningException] = Field(default_factory=list)


class CapabilityDraft(BaseModel):
    """機能を登記する操作の入力。"""

    name: str
    description: str
    category: str
    evidence_sections: list[str] = Field(default_factory=list)


class PackageDraft(BaseModel):
    """パッケージを改訂する操作の入力。"""

    name: str
    capabilities: list[str] = Field(default_factory=list)
    buyer: str = ""
    hypothesis_state: str = ""
    basis: str | None = None
    source: str | None = None


class MaterialRequest(BaseModel):
    """文面の材料を取り出す操作の入力。"""

    channel: str
    package: str | None = None
    opportunity: str | None = None


class PositioningView(BaseModel):
    """いまの決めを読む操作の返り値。決めと、その束のパッケージを射影して返す。"""

    positioning: Positioning | None = Field(default=None, description="適用される最新の決め")
    package: Package | None = Field(default=None, description="前面に出す束のパッケージ")
    warnings: list[str] = Field(default_factory=list, description="決めが未登記などの断り")


class Material(BaseModel):
    """文面の材料。媒体向けの文面を書くために、正本から射影して渡す一式。"""

    channel: str = Field(description="宛先の媒体")
    positioning: Positioning | None = Field(default=None, description="適用される決め")
    package: Package | None = Field(default=None, description="看板のパッケージ")
    capabilities: list[Capability] = Field(default_factory=list, description="束ねる機能")
    evidence: list[dict[str, str]] = Field(
        default_factory=list, description="各機能の裏づけの節（公開可のものだけ。見出しと本文）"
    )
    channel_rules: list[str] = Field(default_factory=list, description="媒体の規約")
    forbidden_phrases: list[str] = Field(default_factory=list, description="禁じた言い回し")
    warnings: list[str] = Field(
        default_factory=list, description="旧い束の宣言、未反映の注記、落とした節の名前"
    )


class ConsistencyReport(BaseModel):
    """整合検査の返り値。違反の一覧と、違反ではない断りを持つ。"""

    scope: str = Field(default="全体", description="検査した範囲")
    violations: list[Violation] = Field(default_factory=list, description="違反の一覧")
    notes: list[str] = Field(default_factory=list, description="違反ではない断り")


class SourceDefect(BaseModel):
    """正本のブロックのうち、必須の欄が欠けていて型にできなかったもの 1 つ。

    型にできないブロックを黙って飛ばすと、1 つ前のブロックが「いまの正本」として通ってしまい、
    読んだ側は正しいはずの中身に対して逆向きの直し先を受け取る。だから、飛ばしたこと自体を
    この型で持ち帰り、検査の断りに載せる。読み込みそのものは止めない（他の中身は読めるため）。
    """

    file: str = Field(description="そのブロックがあるファイル")
    location: str = Field(description="ファイルの中のどこか（節の見出し）")
    missing_fields: list[str] = Field(description="欠けている欄の名前")

    def note(self) -> str:
        """断りの 1 行にする。どのファイルのどのブロックに、どの欄が無いかを書く。"""
        missing = "、".join(f"「{name}」" for name in self.missing_fields)
        return (
            f"{self.file} の{self.location}は、必須の欄{missing}が無いので型にできず、"
            "いまの正本として読んでいない。"
        )


class SourceSnapshot(BaseModel):
    """正本 7 種を読み込んだ結果。リポジトリが返し、サービスはこれだけを見て判断する。"""

    positionings: list[Positioning] = Field(default_factory=list)
    packages: list[Package] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    career_frames: list[CareerFrame] = Field(default_factory=list)
    engagements: list[Engagement] = Field(default_factory=list)
    presentations: list[Presentation] = Field(default_factory=list)
    ledger_entries: list[ResumeLedger] = Field(default_factory=list)
    defects: list[SourceDefect] = Field(
        default_factory=list, description="必須の欄が欠けていて型にできなかったブロック"
    )

    def section_headings(self) -> list[str]:
        """裏づけの節と出典の節が指せる見出しを、職歴の枠と受託案件から集める。"""
        return [frame.heading for frame in self.career_frames] + [
            engagement.heading for engagement in self.engagements
        ]

    def disclosure_of(self, heading: str) -> str | None:
        """見出しに対応する節の公開可否を返す。見出しが無ければ None。"""
        for frame in self.career_frames:
            if frame.heading == heading:
                return frame.disclosure
        for engagement in self.engagements:
            if engagement.heading == heading:
                return engagement.disclosure
        return None

    def is_private(self, heading: str) -> bool:
        """その見出しの節が公開不可か。

        見出しが実在しないときは False を返す。実在しないことは、公開可否とは別の制約で見るからである。
        """
        disclosure = self.disclosure_of(heading)
        return disclosure is not None and disclosure.startswith(PRIVATE_DISCLOSURE_PREFIX)
