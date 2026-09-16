# 生成物。直すなら src/accord/ontology.yaml を直す
"""accord の型の定義。

型は 7 つで、正本 src/accord/ontology.yaml が
挙げる型に 1 対 1 で対応する。欄の名前と必須の別は src/accord/ontology.yaml が持つ。
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Positioning(BaseModel):
    """売り方の決め。どのパッケージを前面に出すかの判断。1 決め 1 ブロックで積み、過去のブロックは書き換えない。"""

    decided_on: date = Field(description="日付。この決めを決めた日。パッケージ定義の鮮度は、この日付と比べて判定する。")
    scope: str = Field(description="適用範囲。媒体の名前か「全体」。媒体の名前は設定ファイルの一覧から取る。")
    headline_package: str = Field(description="前面に出す束。看板にするパッケージの名前。パッケージ定義に実在する名前に限る。")
    rationale: str = Field(description="根拠。なぜこの束を前面に出すのかの説明。")
    exceptions: list[dict[str, str]] = Field(default_factory=list, description="例外。この決めに反してよい提示物の名前と、その理由の組。宣言の一致の検査はここに書いた提示物を飛ばす。")


class Package(BaseModel):
    """パッケージ。機能を束ねて誰に売るかを定めた売り物の単位。"""

    name: str = Field(description="パッケージ名。決めと提示物が名前で指す先。")
    buyer: str = Field(description="想定買い手。誰に売るか。")
    hypothesis_state: str = Field(description="仮説の状態。仮説のみ・検証中・実績あり。選べる語は設定ファイルから読む。")
    capabilities: list[str] = Field(description="束ねる機能。束ねる機能の名前。機能の台帳にある名前に限る。")
    updated_on: date = Field(description="最終更新。この定義を最後に直した日。決めの日付より古いと鮮度の違反になる。")
    basis: str | None = Field(default=None, description="判定根拠。仮説の状態をそう判定した理由。")
    source: str | None = Field(default=None, description="出典。判定の元にした正本の節。")
    breaks_when: str | None = Field(default=None, description="崩れる条件。この束が売り物として成り立たなくなる条件。")


class Capability(BaseModel):
    """機能。提供できる仕事 1 つ。裏づけの節を持つ。"""

    name: str = Field(description="機能名。パッケージが束ねるときに指す名前。")
    description: str = Field(description="説明。その仕事が何をするかの 1 行。")
    category: str = Field(description="分類。機能の台帳の節の名前。選べる語は設定ファイルから読む。")
    evidence_sections: list[str] = Field(description="裏づけの節。職歴の枠か受託案件の見出し。1 つ以上。実在する見出しに限る。")


class CareerFrame(BaseModel):
    """職歴の枠。会社 1 社ぶん、またはフリーランス 1 期ぶんの職歴。"""

    heading: str = Field(description="見出し。節の見出し。裏づけの節と出典の節はこの文字列で指す。")
    period: str = Field(description="期間")
    organization: str = Field(description="所属")
    position: str = Field(description="立場")
    summary: str | None = Field(default=None, description="やったこと")
    outcome: str | None = Field(default=None, description="成果")
    technologies: str | None = Field(default=None, description="技術")
    disclosure: str = Field(description="公開可否。外に出してよいかどうか。公開不可の節は材料の取り出しが落とす。")
    source: str = Field(description="出所。この記述の元にした素材。")


class Engagement(BaseModel):
    """受託案件。クライアント 1 社ぶんの仕事、または横断のトピック。"""

    heading: str = Field(description="見出し。節の見出し。裏づけの節と出典の節はこの文字列で指す。")
    industry: str | None = Field(default=None, description="業種")
    scale: str | None = Field(default=None, description="規模")
    problem: str | None = Field(default=None, description="課題")
    actions: str | None = Field(default=None, description="やったこと")
    outcome: str | None = Field(default=None, description="成果")
    technologies: str | None = Field(default=None, description="技術")
    disclosure: str = Field(description="公開可否。外に出してよいかどうか。公開不可の節は材料の取り出しが落とす。")
    source: str = Field(description="出所。この記述の元にした素材。")


class Presentation(BaseModel):
    """提示物。媒体の画面や添付に貼る文面。どのパッケージを名乗るかを宣言する。"""

    path: str = Field(description="ファイル。正本のディレクトリからの相対パス。違反の一覧はこの名前で場所を指す。")
    channel: str = Field(description="宛先の媒体。媒体の名前。設定ファイルの一覧から取る。")
    declared_package: str = Field(description="宣言する束。この文面が名乗っているパッケージの名前。")
    pending_notes: list[str] = Field(default_factory=list, description="未反映の注記。まだ正本に反映していない事実の覚え書き。「節の見出し — 覚え書き」の形で書き、区切りより前がその事実の入る先の節になる。指す節が実在することを検査する。")
    created_on: date | None = Field(default=None, description="作成日")


class ResumeLedger(BaseModel):
    """職務経歴書の台帳。職務経歴書の元になる正本の、案件 1 件ぶんのブロック。台帳全体はこのブロックの並びで持つ。"""

    entry_number: str = Field(description="案件番号。台帳の中での通し番号。違反の一覧はこの番号で場所を指す。")
    heading: str = Field(description="見出し")
    period: str = Field(description="期間")
    scale: str = Field(description="規模")
    process: str = Field(description="担当工程")
    role: str = Field(description="役割と任され方")
    decisions: str = Field(description="自分が決めたこと")
    closing: str = Field(description="終わりの状態")
    source_section: str = Field(description="出典の節。写し元の節の見出し（受託案件）。実在と公開可否を検査する。")
    fold_line: str | None = Field(default=None, description="畳み行")
