# 生成物。直すなら src/accord/ontology.yaml を直す
"""accord の型の定義。

型は 8 つで、正本 src/accord/ontology.yaml が
挙げる型に 1 対 1 で対応する。欄の名前と必須の別は src/accord/ontology.yaml が持つ。
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Positioning(BaseModel):
    """売り方の決め。どのパッケージを前面に出すかの判断。1 決め 1 ブロックで積み、過去のブロックは書き換えない。"""

    decided_on: date = Field(description="日付。この決めを決めた日。パッケージ定義の鮮度は、この日付と比べて判定する。")
    scope: str = Field(description="適用範囲。媒体の名前か「全体」。媒体の名前は設定ファイルの一覧から取る。")
    headline_package: str = Field(description="前面に出す束。看板にするパッケージの ID。パッケージ定義に実在する ID に限る。")
    rationale: str = Field(description="根拠。なぜこの束を前面に出すのかの説明。")
    exceptions: list[dict[str, str]] = Field(default_factory=list, description="例外。この決めに反してよい提示物の名前と、その理由の組。宣言の一致の検査はここに書いた提示物を飛ばす。")


class Package(BaseModel):
    """パッケージ。機能を束ねて誰に売るかを定めた売り物の単位。"""

    id: str = Field(description="ID。このパッケージを指すときに使う識別子。英小文字・数字・ハイフンで 3〜40 字、先頭と末尾は英数字、正本全体で重ならない値にする。")
    name: str = Field(description="パッケージ名。人が読む表示名。決めと提示物が指すときは名前ではなく ID を使う。")
    buyer: str = Field(description="想定買い手。誰に売るか。")
    hypothesis_state: str = Field(description="仮説の状態。選べる語は設定ファイルの package_hypothesis_states が持つ一覧に限る。")
    capabilities: list[str] = Field(description="束ねる機能。束ねる機能の ID。機能の台帳にある ID に限る。複数あるときは半角のスラッシュ「/」で区切る（例「id-a / id-b」）。ID にスラッシュは入らないので、区切りと値を取り違えない。")
    updated_on: date = Field(description="最終更新。この定義を最後に直した日。決めの日付より古いと鮮度の違反になる。")
    basis: str | None = Field(default=None, description="判定根拠。仮説の状態をそう判定した理由。")
    source: str | None = Field(default=None, description="出典。判定の元にした正本の節。")
    breaks_when: str | None = Field(default=None, description="崩れる条件。この束が売り物として成り立たなくなる条件。")


class Capability(BaseModel):
    """機能。提供できる仕事 1 つ。裏づけの節を持つ。"""

    id: str = Field(description="ID。この機能を指すときに使う識別子。英小文字・数字・ハイフンで 3〜40 字、先頭と末尾は英数字、正本全体で重ならない値にする。台帳の表では 1 列目に置く。")
    name: str = Field(description="機能名。人が読む表示名。パッケージが束ねるときは名前ではなく ID を使う。")
    description: str = Field(description="説明。その仕事が何をするかの 1 行。")
    category: str = Field(description="分類。機能の台帳の節の名前。選べる語は設定ファイルから読む。")
    evidence_sections: list[str] = Field(description="裏づけの節。職歴の枠か受託案件か公開記録の ID。1 つ以上。複数あるときは半角のスラッシュ「/」で区切る（例「id-a / id-b」）。ほかの記号でつなぐと、つないだ全体が 1 つの値として読まれ、ID の形式に合わないと判定される。実在する ID に限る。")


class CareerFrame(BaseModel):
    """職歴の枠。会社 1 社ぶん、またはフリーランス 1 期ぶんの職歴。"""

    id: str = Field(description="ID。この枠を指すときに使う識別子。英小文字・数字・ハイフンで 3〜40 字、先頭と末尾は英数字、正本全体で重ならない値にする。")
    heading: str = Field(description="見出し。節の見出し。人が読む表示名で、指すときは見出しではなく ID を使う（見出しは自由に書き換えてよい）。")
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

    id: str = Field(description="ID。この案件を指すときに使う識別子。英小文字・数字・ハイフンで 3〜40 字、先頭と末尾は英数字、正本全体で重ならない値にする。")
    heading: str = Field(description="見出し。節の見出し。人が読む表示名で、指すときは見出しではなく ID を使う（見出しは自由に書き換えてよい）。")
    industry: str | None = Field(default=None, description="業種")
    scale: str | None = Field(default=None, description="規模")
    problem: str | None = Field(default=None, description="課題")
    actions: str | None = Field(default=None, description="やったこと")
    outcome: str | None = Field(default=None, description="成果")
    technologies: str | None = Field(default=None, description="技術")
    disclosure: str = Field(description="公開可否。外に出してよいかどうか。公開不可の節は材料の取り出しが落とす。")
    source: str = Field(description="出所。この記述の元にした素材。")


class PublicRecord(BaseModel):
    """公開記録。外から確かめられる公開の成果物 1 件。リポジトリ・登壇・記事・書籍・第三者の掲載など。1 件 1 ブロックで積む。"""

    id: str = Field(description="ID。この 1 件を指すときに使う識別子。英小文字・数字・ハイフンで 3〜40 字、先頭と末尾は英数字、正本全体で重ならない値にする。")
    name: str = Field(description="名前。この 1 件を言い表す、人が読む表示名。機能の裏づけが指すときは名前ではなく ID を使う。")
    kind: str = Field(description="種類。選べる語は設定ファイルの public_record_kinds が持つ一覧に限る。")
    published_on: str = Field(description="日付。2020-03-10 の形。月までしか分からないときは 2020-03、年だけなら 2020 と書く。")
    url: str | None = Field(default=None, description="URL。外から確かめられる場所。紙媒体など URL が無いものは「なし」と書く。")
    publisher: str = Field(description="発行元か主催。記事なら載せた媒体、登壇なら催しの主催、リポジトリなら置いた場所。")
    role: str = Field(description="役割。選べる語は設定ファイルの public_record_roles が持つ一覧に限る。")
    origin_section: str | None = Field(default=None, description="由来の節。職歴の枠か受託案件の ID。無ければ空でよい。")
    source: str | None = Field(default=None, description="出所。この記述の元にした素材。URL があれば、その URL 自身が外から確かめられる出所になる。")


class Presentation(BaseModel):
    """提示物。媒体の画面や添付に貼る文面。どのパッケージを名乗るかを宣言する。"""

    path: str = Field(description="ファイル。正本のディレクトリからの相対パス。違反の一覧はこの名前で場所を指す。")
    channel: str = Field(description="宛先の媒体。媒体の名前。設定ファイルの一覧から取る。")
    declared_package: str = Field(description="宣言する束。この文面が名乗っているパッケージの ID。")
    pending_notes: list[str] = Field(default_factory=list, description="未反映の注記。まだ正本に反映していない事実の覚え書き。「受託案件の ID — 覚え書き」の形で書き、区切りより前がその事実の入る先の節の ID になる。指す ID が実在することを検査する。")
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
    source_section: str = Field(description="出典の節。写し元の節の ID（受託案件）。実在と公開可否を検査する。")
    fold_line: str | None = Field(default=None, description="畳み行")
