"""操作が受け取る入力と、返す値の型。手で書く（生成物ではない）。

拒否は例外ではなく返り値で表す。呼んだ側が、返ってきた「次の一手」を読んで自分で
呼び直せるようにするためである。だから書きの操作は、通っても通らなくても WriteResult を返す。

正本の 8 つの型は生成物の types.py にあり、この文書はそれを組み合わせた器だけを持つ。
"""

from __future__ import annotations

import difflib
import re
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
    PublicRecord,
    ResumeLedger,
)

# 公開可否の欄が、外に出せないことを表すときの書き出し。
# 欄には理由まで書けるので（「公開不可（在籍先の名前を出さない約束があるため）」）、
# 語の一致ではなく書き出しで見る。この 1 か所を、検査も材料の取り出しも読む。
PRIVATE_DISCLOSURE_PREFIX = "公開不可"

# 正本どうしの結びに使う ID の形。英小文字・数字・ハイフンで 3〜40 字、先頭と末尾は英数字。
# 形を決めるのはこの 1 か所で、検査も書きの操作も候補の出し方も、ここを読む。
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")

# ID の形を人に伝えるときの 1 行。違反の文にも拒否の文にも、同じ言い方で載せる。
ID_FORMAT_TEXT = "英小文字・数字・ハイフンで 3〜40 字、先頭と末尾は英数字"

# 候補の並びを文に載せるときの書き出し。この語で、文が候補を挙げ済みかどうかも見分ける。
CANDIDATE_PREFIX = "候補: "


def is_id(value: str) -> bool:
    """その文字列が ID の形に合っているか。"""
    return bool(ID_PATTERN.match(value.strip()))


def labelled(identifier: str, labels: dict[str, str] | None = None) -> str:
    """ID 1 つを「ID（表示名）」の 1 つの文字列にする。表示名が引けなければ ID だけを返す。

    人が読む文に ID だけを出すと、受け取った側は「どの節のことか」を正本を開いて確かめる
    羽目になる。だから文の中では表示名を添える。候補の欄そのものは ID だけで持つ（そのまま
    渡し直せば通る値に限る、という決めのため）ので、この関数を通すのは文を組むときだけである。
    """
    label = (labels or {}).get(identifier, "")
    if not label or label == identifier:
        return identifier
    return f"{identifier}（{label}）"


def candidate_text(candidates: list[str], labels: dict[str, str] | None = None) -> str:
    """候補の ID の並びを「候補: id（表示名） / …」の 1 つの文にする。候補が無ければ空文字。

    候補の欄は ID だけを持つので、そのままでは読む人にどの節のことか伝わらない。文の側で
    表示名を添える場所をここ 1 か所に集め、検査の違反も書きの操作の拒否も同じ文を使う。
    """
    if not candidates:
        return ""
    return CANDIDATE_PREFIX + " / ".join(labelled(item, labels) for item in candidates)


# 近い名前を探すときの緩さ。近いものが 1 つも出ないときは、実在する名前をそのまま並べる。
CLOSE_MATCH_CUTOFF = 0.3
CLOSE_MATCH_COUNT = 3
FALLBACK_COUNT = 5


def close_names(
    wanted: str, pool: list[str], labels: dict[str, str] | None = None
) -> list[str]:
    """実在する値のうち、渡された値に近いものを返す。近いものが無ければ先頭から並べる。

    探す先は必ず実在する値の一覧である。拒否も検査も同じ候補の出し方をするように、
    この 1 か所を全員が呼ぶ。

    labels を渡すと、pool は ID の一覧として扱う。返すのは ID だけで（そのまま渡し直せば
    通る値に限るため）、表示名は文の側に candidate_text が添える。
    近さの照合は、渡された値が ID の形なら ID どうしで、そうでなければ表示名どうしで行う。
    見出しを書いた人には ID の綴りの近さが効かず、ID を書き間違えた人には表示名の近さが
    効かないので、渡された値の形で照合の相手を選び分ける。
    """
    if labels is None:
        close = difflib.get_close_matches(
            wanted, pool, n=CLOSE_MATCH_COUNT, cutoff=CLOSE_MATCH_CUTOFF
        )
        return close or pool[:FALLBACK_COUNT]

    if is_id(wanted):
        found = difflib.get_close_matches(
            wanted, pool, n=CLOSE_MATCH_COUNT, cutoff=CLOSE_MATCH_CUTOFF
        )
    else:
        # 表示名で照合し、当たった表示名を ID に戻す。同じ表示名が 2 つの ID に付くことは
        # 無い前提を置かず、正本の並びの順で最初に見つかったものを返す。
        names = [labels.get(identifier, identifier) for identifier in pool]
        close = difflib.get_close_matches(
            wanted, names, n=CLOSE_MATCH_COUNT, cutoff=CLOSE_MATCH_CUTOFF
        )
        found = []
        for name in close:
            for identifier in pool:
                if labels.get(identifier, identifier) == name and identifier not in found:
                    found.append(identifier)
                    break

    return list(found or pool[:FALLBACK_COUNT])


def fold_names(names: list[str], keep: int = 5) -> str:
    """名前の並びを「A / B / C ほかに 12 件」の形の 1 つの文字列にする。

    数が増えるほど長くなる並びを本文に埋めると、返り値そのものが受け取る側の口に載らなくなる。
    先頭のいくつかだけを名前で見せ、残りは件数に畳む。畳む分が無ければ件数の断りは付けない。
    """
    head = " / ".join(names[:keep])
    rest = len(names) - keep
    if rest > 0:
        return f"{head} ほかに {rest} 件"
    return head


def normalize_url(url: str) -> str:
    """URL から、書き方の違い（scheme・www.・末尾のスラッシュ・クエリ）だけを落とす。

    比べ方をここ 1 か所に置く。提示物の本文から拾う側も、正本の公開記録と突き合わせる側も、
    この関数が返した形どうしを比べる。落とすのは、http と https の違い、ホストの大文字と小文字、
    ホストの先頭の `www.`、`?` から後ろと `#` から後ろ、末尾のスラッシュ 1 つである。
    パスの大文字と小文字は残す（同じ経路の別の綴りは、別の場所を指しうるため）。
    http でも https でも始まらない文字列は、URL として扱わずに空文字を返す。
    """
    text = url.strip()
    for scheme in ("https://", "http://"):
        if text[: len(scheme)].lower() == scheme:
            text = text[len(scheme) :]
            break
    else:
        return ""

    # クエリとフラグメントを先に落とす。どちらの記号もホストには現れないので、
    # ホストを切り出してから落とすのと結果は変わらず、パスを持たない URL も同じ形になる。
    for mark in ("?", "#"):
        text = text.split(mark, 1)[0]

    host, slash, path = text.partition("/")
    host = host.lower()
    if host.startswith("www."):
        host = host[len("www.") :]

    normalized = f"{host}{slash}{path}"
    if normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def url_host(normalized: str) -> str:
    """正規化した URL のホストを返す。照合の相手にするかどうかは、このホストで決める。"""
    return normalized.partition("/")[0]


def url_tail(normalized: str) -> str:
    """正規化した URL のパスを / で切り、空でない最後の要素を返す。無ければ空文字。

    同じものを指しているのに経路の書き方だけが違う URL は、この最後の要素が同じになる。
    """
    path = normalized.partition("/")[2]
    items = [item for item in path.split("/") if item]
    return items[-1] if items else ""


class PresentationUrl(BaseModel):
    """提示物の本文に書かれていた URL 1 つ。"""

    path: str = Field(description="その提示物の、正本のディレクトリからの相対パス")
    url: str = Field(description="本文に書かれていたそのままの文字列")
    normalized: str = Field(description="書き方の違いを落とした形")


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


def id_rejection(
    constraint: str, operation: str, identifier: str, taken: dict[str, str]
) -> Rejection | None:
    """書きの操作が受け取った ID を、形式と一意性に当てる。通れば None を返す。

    ID を持つ項目を書く操作は 3 つあり、どれも同じ形と同じ一意性を見る。判定を 3 か所に書くと、
    片方だけを直したときに、書きで通った ID が検査で違反になる。だからこの 1 か所に集める。
    taken は、すでに使われている ID と、その ID を持つ項目の表示名の対応である。
    """
    value = (identifier or "").strip()
    if not is_id(value):
        examples = list(taken)[:FALLBACK_COUNT]
        return Rejection(
            constraint=constraint,
            reason=(
                f"ID「{value}」は形に合わない（{ID_FORMAT_TEXT}）。"
                "正本にすでにある ID を例にすると "
                + " / ".join(labelled(name, taken) for name in examples)
                + "。"
            ),
            next_action=NextAction(
                operation=operation,
                candidates=examples,
                example="ID は「teramina-delivery」のように、意味の分かる短い語をハイフンでつなぐ。",
            ),
        )

    if value in taken:
        return Rejection(
            constraint=constraint,
            reason=(
                f"ID「{value}」は、すでに「{taken[value]}」が使っている。"
                "ID は正本全体で 1 つの項目にしか付けられない。"
            ),
            next_action=NextAction(
                operation=operation,
                candidates=[],
                example="まだどの項目も使っていない ID を渡して呼び直す。",
            ),
        )
    return None


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
        文がもう候補を挙げているとき（ID で結ぶ検査は、表示名を添えた候補の文を expected に
        持つ）は重ねない。同じ並びが 2 度出ると、どちらが正しいのか読む側が決められなくなる。
        """
        text = f"{self.constraint}: {self.file} の{self.location} — {self.expected}"
        if self.candidates and CANDIDATE_PREFIX not in self.expected:
            text += candidate_text(self.candidates)
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

    id: str = ""
    name: str
    description: str
    category: str
    evidence_sections: list[str] = Field(default_factory=list)


class PublicRecordDraft(BaseModel):
    """公開記録を登記する操作の入力。欠けた欄を見つけるため、どの欄も空を許して受ける。"""

    id: str | None = None
    name: str | None = None
    kind: str | None = None
    published_on: str | None = None
    url: str | None = None
    publisher: str | None = None
    role: str | None = None
    origin_section: str | None = None
    source: str | None = None


class PackageDraft(BaseModel):
    """パッケージを改訂する操作の入力。"""

    id: str = ""
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
        default_factory=list,
        description="各機能の裏づけの節（公開可のものだけ。表示名・ID・公開可否・本文）",
    )
    public_records: list[PublicRecord] = Field(
        default_factory=list, description="束ねる機能の裏づけになっている公開記録"
    )
    channel_rules: list[str] = Field(default_factory=list, description="媒体の規約")
    forbidden_phrases: list[str] = Field(default_factory=list, description="禁じた言い回し")
    warnings: list[str] = Field(
        default_factory=list, description="旧い束の宣言、未反映の注記、落とした節の名前"
    )


class Provenance(BaseModel):
    """この検査が、どの設定を、どの読み方で、どの版の accord で走ったか。

    版番号だけでは足りない。入れ直していない古い環境と、直したばかりのソースが、同じ版番号を
    名乗ることがあるからである。見分けがつくのは、実際に動いているソースの置き場である。
    """

    config_path: str = Field(description="読んだ設定ファイルの絶対パス")
    reading: list[str] = Field(
        default_factory=list, description="適用した [reading] の鍵。1 つも無ければ「既定」"
    )
    version: str = Field(default="", description="accord の版")
    module_path: str = Field(description="実際に動いている accord のソースの置き場（絶対パス）")


class ConsistencyReport(BaseModel):
    """整合検査の返り値。違反の一覧と、違反ではない断りを持つ。

    足跡（provenance）を欄の宣言の先頭に置くのは、JSON にしたときに先頭に出るのが宣言の順
    だからである。読んだ側が、まず「どの設定を、どのソースが読んだか」を目にする形にする。
    """

    provenance: Provenance | None = Field(
        default=None, description="どの設定を、どの読み方で、どの版の accord が読んだか"
    )
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
    source_key: str = Field(default="", description="どの正本のブロックか（正本の役割の名前）")
    heading: str = Field(
        default="", description="そのブロックの見出し。ファイル 1 枚を丸ごと読む提示物では空"
    )
    id: str = Field(
        default="",
        description="そのブロックの ID。ID の行そのものが欠けているブロックと、提示物では空",
    )


class SkippedHeading(BaseModel):
    """正本のファイルにあるが、その正本の読み方では読んでいない見出し 1 つ。

    指された見出しが読めていないとき、それが「どこにも無い」のか「実在するが読み取り範囲の
    外にある」のかで、直し先が正反対になる。前者は指す側の名前を直し、後者は設定の絞りを
    広げるか正本の節を動かす。その言い分けをするために、外れた見出しを居場所つきで持ち帰る。
    """

    source_key: str = Field(description="どの正本の読み方で外れたか（career / engagements）")
    heading: str = Field(description="外れた見出しの文字列")
    id: str = Field(
        default="", description="外れた節の ID。ID の行を持たない節では空"
    )
    level: int = Field(description="見出しの深さ")
    parents: list[str] = Field(default_factory=list, description="その見出しの上にある見出し（浅い順）")
    reason: str = Field(description="どの絞りに当たって外れたか")


class SourceSnapshot(BaseModel):
    """正本 8 種を読み込んだ結果。リポジトリが返し、サービスはこれだけを見て判断する。"""

    positionings: list[Positioning] = Field(default_factory=list)
    packages: list[Package] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    career_frames: list[CareerFrame] = Field(default_factory=list)
    engagements: list[Engagement] = Field(default_factory=list)
    public_records: list[PublicRecord] = Field(default_factory=list)
    presentations: list[Presentation] = Field(default_factory=list)
    ledger_entries: list[ResumeLedger] = Field(default_factory=list)
    presentation_urls: list[PresentationUrl] = Field(
        default_factory=list, description="提示物の本文に書かれていた URL"
    )
    defects: list[SourceDefect] = Field(
        default_factory=list, description="必須の欄が欠けていて型にできなかったブロック"
    )
    skipped_headings: list[SkippedHeading] = Field(
        default_factory=list, description="正本にあるが、その正本の読み方では読んでいない見出し"
    )

    def section_headings(self) -> list[str]:
        """由来の節と出典の節が指せる ID を、職歴の枠と受託案件から集める。"""
        return [frame.id for frame in self.career_frames] + [
            engagement.id for engagement in self.engagements
        ]

    def evidence_targets(self) -> list[str]:
        """裏づけが指せる ID。職歴の枠・受託案件の ID に、公開記録の ID を足したもの。

        並びは職歴の枠・受託案件・公開記録の順にする。ID は正本全体で一意なので、この並びで
        勝ち負けが決まることは無く、並びは候補を出すときの見え方だけを決める。
        """
        return self.section_headings() + [record.id for record in self.public_records]

    def labels(self) -> dict[str, str]:
        """ID から人が読む表示名を引く対応表。指される側の 5 つの型を全部入れる。

        違反の文も候補も、ID だけでは読んだ人にどの節のことか伝わらない。ID を表示名に
        戻す場所をこの 1 か所に集める。
        """
        found: dict[str, str] = {}
        for frame in self.career_frames:
            found.setdefault(frame.id, frame.heading)
        for engagement in self.engagements:
            found.setdefault(engagement.id, engagement.heading)
        for record in self.public_records:
            found.setdefault(record.id, record.name)
        for capability in self.capabilities:
            found.setdefault(capability.id, capability.name)
        for package in self.packages:
            found.setdefault(package.id, package.name)
        return found

    def label_of(self, identifier: str) -> str:
        """ID 1 つの表示名を返す。引けなければ ID をそのまま返す。"""
        return self.labels().get(identifier, identifier)

    def disclosure_of(self, section_id: str) -> str | None:
        """ID に対応する節の公開可否を返す。ID が無ければ None。"""
        for frame in self.career_frames:
            if frame.id == section_id:
                return frame.disclosure
        for engagement in self.engagements:
            if engagement.id == section_id:
                return engagement.disclosure
        return None

    def is_private(self, section_id: str) -> bool:
        """その ID の節が公開不可か。

        ID が実在しないときは False を返す。実在しないことは、公開可否とは別の制約で見るからである。
        """
        disclosure = self.disclosure_of(section_id)
        return disclosure is not None and disclosure.startswith(PRIVATE_DISCLOSURE_PREFIX)
