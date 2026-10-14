"""Markdown を見出しの階層と本文に切り分け、設定の書き方どおりに節と欄を読む。

正本は Markdown のままで持つ、という決めなので、「節」が事実の単位になる。裏づけの節も
出典の節も、この文書が切り出した見出しの文字列で指す。

正本の書き方は人によって違う。見出しの深さも、欄を箇条書きで書くか表で書くかも、欄の
ラベルの言い方も違う。その違いは設定（`BlockRule`）が持ち、この文書はそれを当てる側に徹する。
どの節をブロックとして読むかは `select_blocks`、その節の欄をどう読むかは `read_fields` が
1 か所で決め、正本 8 種の読み込みはどちらも同じ関数を通る。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from accord.vocabulary.settings import DEFAULT_BLOCK_RULE, BlockRule

# ATX 形式の見出し（# から ###### まで）。
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")

# 定義の行。「- ラベル: 値」の形で、正本の欄はこの書き方で持つ。
DEFINITION_RE = re.compile(r"^[-*][ \t]+([^:：]+)[:：][ \t]*(.*)$")

# 公開可否の欄のラベル。この欄だけは、ほかの欄より広い書き方を欄として読む。
DISCLOSURE_FIELD = "公開可否"

# 公開可否の欄の広い書き方。箇条書き（「- 」「* 」）か番号つきの箇条書き（「1. 」）か、記号の無い行の頭に
# ラベルを置き、区切りに「:」「：」「＝」「=」のどれかを使う。ラベルは太字（「**公開可否**：」）でもよく、
# 区切りが太字の中にあってもよい（「**公開可否：**」）。行の頭の字下げは見ない（続きの行も読む）。
# 欄の名前の照らし合わせの前に当てる（区切りが「＝」の行は、ほかの欄の書き方では読めないため）。
DISCLOSURE_FORM_RE = re.compile(
    r"^((?:(?:[-*]|\d+\.)[ \t]+)?(?:\*\*)?"
    + DISCLOSURE_FIELD
    + r"(?:\*\*)?[ \t]*[:：＝=](?:\*\*)?[ \t]*)(.*)$"
)

# 箇条書きの行。「- 中身」の形で、ラベルを持たない並びはこの書き方で持つ。
BULLET_RE = re.compile(r"^[-*][ \t]+(.+?)[ \t]*$")

# 見出しやラベルの末尾の括弧書き。「成果（定量は聞き取りで足した）」の括弧の部分。
NOTE_RE = re.compile(r"[（(][^（）()]*[）)][ \t]*$")

# 見出しの前置きに続く数字。「案件12｜…」の前置きを外した残りから 12 を取る。
LEADING_NUMBER_RE = re.compile(r"^[ \t]*(\d+)")

# 本文に貼られた URL。http か https で始まり、空白・全角空白・改行・囲みの記号・句読点で終わる。
URL_RE = re.compile("https?://[^\\s　<>\"'`)）」、。]+")

# 取った URL の末尾に付いていたら落とす記号。文末の記号を URL に含めないため。
URL_TAIL_MARKS = ".,、。)）"

# 節の本文の指紋の桁数。SHA-256 の 16 進の先頭からこの桁数を使う。
FINGERPRINT_LENGTH = 8


@dataclass
class Section:
    """節 1 つ。見出しの深さ・見出しの文字列・本文と、元の文書での行の範囲を持つ。"""

    level: int
    heading: str
    body: str
    start: int = 0
    end: int = 0


@dataclass
class Document:
    """1 つの Markdown ファイルを切り分けた結果。frontmatter は節と混ぜずに別に持つ。"""

    frontmatter: str = ""
    sections: list[Section] = field(default_factory=list)


def split_document(text: str) -> Document:
    """frontmatter と節に切り分ける。

    frontmatter は、ファイルの 1 行目が `---` のときだけ、次の `---` までを指す。
    最初の見出しより前の本文は、深さ 0・見出し無しの節として先頭に置く。
    """
    lines = text.splitlines()
    frontmatter_lines: list[str] = []
    offset = 0

    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                frontmatter_lines = lines[1:index]
                offset = index + 1
                break

    sections: list[Section] = []
    current = Section(level=0, heading="", body="", start=offset, end=offset)
    body_lines: list[str] = []

    for index in range(offset, len(lines)):
        line = lines[index]
        match = HEADING_RE.match(line)
        if match is None:
            body_lines.append(line)
            continue
        current.body = "\n".join(body_lines).strip("\n")
        current.end = index
        sections.append(current)
        body_lines = []
        current = Section(
            level=len(match.group(1)),
            heading=match.group(2).strip(),
            body="",
            start=index,
            end=index,
        )

    current.body = "\n".join(body_lines).strip("\n")
    current.end = len(lines)
    sections.append(current)

    return Document(frontmatter="\n".join(frontmatter_lines), sections=sections)


def split_sections(text: str) -> list[Section]:
    """見出しの階層と本文に切り分けた節の一覧を返す。"""
    return split_document(text).sections


def section_fingerprint(body: str) -> str:
    """節の本文の指紋を返す。写しの鮮度の検査と、見本に書く指紋の算出の両方がこの 1 か所を使う。

    本文は見出しの行を含まない（split_document が切り出した body をそのまま渡す）。各行の末尾の
    空白と前後の空行を落とし、改行を LF にそろえた文字列の SHA-256 を取り、16 進の小文字の
    先頭 8 桁を返す。行末の空白や空行の足し引きのように、読んで分からない違いでは変わらない。
    """
    # spec: REQ-389
    lines = [line.rstrip() for line in body.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    text = "\n".join(lines)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]


def find_section(sections: list[Section], heading: str) -> Section | None:
    """見出しの文字列で節を探す。見つからなければ None。"""
    for section in sections:
        if section.heading == heading:
            return section
    return None


def bullet_items(body: str, first_block: bool = False) -> list[str]:
    """節の本文から「- 中身」の行だけを拾い、中身の一覧にする。

    ラベルを持たない並び（媒体の規約、禁じた言い回し）を読むために使う。
    箇条書きでない行は、その節に添えた説明なので落とす。
    first_block を立てると、最初にひと続きで並んだ箇条書きだけを読み、空行や地の文で
    切れた先は読まない。1 つの節に、別の話の箇条書きが続けて置かれていることがあるためである。
    """
    items: list[str] = []
    for line in body.splitlines():
        match = BULLET_RE.match(line.strip())
        if match is None:
            if first_block and items:
                break
            continue
        items.append(match.group(1).strip())
    return items


def find_urls(text: str) -> list[str]:
    """本文に書かれた URL を、書かれた順に拾う。

    Markdown のリンク記法 `[文字](URL)` と `<URL>` は、囲みの記号が上の 2 つの規則で落ちるので、
    別の処理は書かない。同じ URL が 2 度書かれていれば、2 件として返す（畳むのは読む側の仕事）。
    """
    return [match.group(0).rstrip(URL_TAIL_MARKS) for match in URL_RE.finditer(text)]


def strip_note(text: str) -> str:
    """末尾の括弧書きを 1 つ落とす。「成果（定量は聞き取りで足した）」は「成果」になる。

    見出しやラベルに、その場の但し書きを括弧で足す書き方があるので、名前で照らし合わせる
    前にこの形にそろえる。括弧の中に括弧があるときは落とさない（どこまでが但し書きかを
    決められないため、読まずに残す）。
    """
    return NOTE_RE.sub("", text.strip()).strip()


def leading_number(heading: str, prefix: str = "") -> str:
    """見出しの前置きに続く数字を返す。数字が無ければ空文字。

    「案件12｜配送の置き場づくり」の前置きが「案件」なら「12」を返す。
    """
    rest = heading[len(prefix) :] if prefix and heading.startswith(prefix) else heading
    match = LEADING_NUMBER_RE.match(rest)
    return match.group(1) if match is not None else ""


def table_blocks(body: str) -> list[list[list[str]]]:
    """節の本文の表を、表ごと・行ごと・セルごとに分けて返す。

    続けて並んだ `|` で始まる行を 1 つの表として数え、空行や表でない行で切れる。
    各表の見出しの行と区切りの行（`|---|---|`）は落とす。区切りの行を持たない表は、
    先頭の 1 行を見出しとして落とす。
    """
    tables: list[list[list[str]]] = []
    current: list[tuple[list[str], bool]] = []

    def close() -> None:
        if not current:
            return
        separators = [index for index, (_, is_separator) in enumerate(current) if is_separator]
        head = separators[0] if separators else 1
        tables.append(
            [
                cells
                for index, (cells, is_separator) in enumerate(current)
                if index >= head and not is_separator
            ]
        )
        current.clear()

    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            close()
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        is_separator = bool(cells) and all(set(cell) <= {"-", ":"} for cell in cells)
        current.append((cells, is_separator))
    close()

    return [rows for rows in tables if rows]


def table_rows(body: str) -> list[list[str]]:
    """節の本文の表の行を、表の別なく 1 つの並びで返す。"""
    return [cells for rows in table_blocks(body) for cells in rows]


def is_frame_heading(heading: str, rule: BlockRule = DEFAULT_BLOCK_RULE) -> bool:
    """その見出しが、在籍職歴の枠の前置き（frame_heading_prefix）で始まるか。前置きが空なら False。"""
    return bool(rule.frame_heading_prefix) and heading.startswith(rule.frame_heading_prefix)


def prefix_matches(heading: str, rule: BlockRule = DEFAULT_BLOCK_RULE) -> bool:
    """見出しが、読み方の前置きの絞りを通るか。

    heading_prefix が空なら絞らない。空でなければ、その前置きで始まる見出しを通す。
    台帳の在籍職歴の枠の前置き（frame_heading_prefix）で始まる見出しも通す。選ぶ側（select_blocks）と
    外れた理由を言う側が同じ判定を使うように、この 1 か所に置く。
    """
    if not rule.heading_prefix:
        return True
    # spec: REQ-375
    return heading.startswith(rule.heading_prefix) or is_frame_heading(heading, rule)


def select_blocks(sections: list[Section], rule: BlockRule = DEFAULT_BLOCK_RULE) -> list[Section]:
    """節の一覧から、その正本のブロックとして読む節だけを取り出す。

    絞り込みは 5 つで、どれも設定が決める。見出しの深さ、上位のどの節の下か、見出しの前置き、
    読まない見出し、欄を 1 つも持たない節（束ねるための見出し）を飛ばすかである。
    読まない見出しに挙げた節は、その下の節も読まない。
    """
    levels = set(rule.heading_levels)
    ancestors: list[tuple[int, str]] = []
    selected: list[Section] = []

    for section in sections:
        while ancestors and ancestors[-1][0] >= section.level:
            ancestors.pop()
        above = [heading for _, heading in ancestors]
        if section.heading:
            ancestors.append((section.level, section.heading))

        # spec: REQ-053
        if not section.heading or section.level not in levels:
            continue
        # spec: REQ-054
        if rule.under_headings and not any(name in rule.under_headings for name in above):
            continue
        if section.heading in rule.skip_headings:
            continue
        if any(name in rule.skip_headings for name in above):
            continue
        # spec: REQ-055
        if not prefix_matches(section.heading, rule):
            continue
        # spec: REQ-057
        if rule.skip_sections_without_fields and not read_fields(section, rule):
            continue
        selected.append(section)
    return selected


def read_fields(section: Section, rule: BlockRule = DEFAULT_BLOCK_RULE) -> dict[str, str]:
    """節の本文から、ラベルと値の欄を読む。

    欄の書き方は 3 つある。箇条書きの「- ラベル: 値」、2 列の表の 1 列目と 2 列目
    （`fields_from_table`）、箇条書きの記号が無い行頭の宣言「ラベル: 値」（`bare_labels`）である。
    読んだ後に、ラベルの末尾の括弧書きの除去（`strip_label_note`）と、ラベルの読み替え
    （`labels`）を当てる。1 つのラベルを複数の欄に読み替えると、同じ値がその欄すべてに入る。
    同じ欄が複数回出たときは、値を改行でつないで 1 つにまとめる。
    """
    entries = _definition_entries(section.body, rule.bare_labels)
    # spec: REQ-059
    if rule.fields_from_table:
        entries += [
            (cells[0], cells[1])
            for cells in table_rows(section.body)
            if len(cells) >= 2 and cells[0]
        ]

    fields: dict[str, str] = {}
    for label, value in entries:
        # spec: REQ-063
        name = strip_note(label) if rule.strip_label_note else label
        # spec: REQ-064
        for target in rule.labels.get(name, (name,)):
            if target in fields:
                fields[target] = f"{fields[target]}\n{value}"
            else:
                fields[target] = value
    return fields


def drop_field_lines(
    body: str, names: tuple[str, ...], rule: BlockRule = DEFAULT_BLOCK_RULE
) -> str:
    """節の本文から、指した欄の行だけを落とす。ほかの行は 1 文字も変えない。

    欄の行の見分け方は read_fields と同じ（「- ラベル: 値」・2 列の表の行・行頭の宣言に、
    ラベルの読み替えと末尾の括弧書きの除去を当てる）。読み方の違う正本でも同じ行が落ちるように、
    判定をこの 1 か所に置く。本文をそのまま渡す先（材料の取り出し）で、別の欄として返している
    値が本文にも二重に出るのを止めるために使う。
    """
    wanted = set(names)

    def is_wanted(label: str) -> bool:
        name = strip_note(label) if rule.strip_label_note else label
        return bool(wanted & set(rule.labels.get(name, (name,))))

    kept: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if DISCLOSURE_FORM_RE.match(line) is not None:
            if is_wanted(DISCLOSURE_FIELD):
                continue
            kept.append(raw)
            continue
        match = DEFINITION_RE.match(line)
        if match is not None:
            if is_wanted(match.group(1).strip()):
                continue
            kept.append(raw)
            continue
        if rule.fields_from_table and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] and is_wanted(cells[0]):
                continue
            kept.append(raw)
            continue
        if any(_bare_declaration(line, label) is not None for label in rule.bare_labels):
            label = next(
                label for label in rule.bare_labels if _bare_declaration(line, label) is not None
            )
            if is_wanted(label):
                continue
        kept.append(raw)
    return "\n".join(kept).strip("\n")


def _definition_entries(body: str, bare_labels: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """本文から「- ラベル: 値」の行と、行頭の宣言の行を、書かれた順に拾う。"""
    entries: list[tuple[str, str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        wide = DISCLOSURE_FORM_RE.match(line)
        if wide is not None:
            entries.append((DISCLOSURE_FIELD, wide.group(2).strip()))
            continue
        match = DEFINITION_RE.match(line)
        if match is not None:
            entries.append((match.group(1).strip(), match.group(2).strip()))
            continue
        # spec: REQ-061
        for label in bare_labels:
            value = _bare_declaration(line, label)
            if value is not None:
                entries.append((label, value))
                break
    return entries


def _bare_declaration(line: str, label: str) -> str | None:
    """箇条書きの記号が無い行頭の宣言「ラベル: 値」から、値を取り出す。宣言でなければ None。"""
    if not line.startswith(label):
        return None
    rest = line[len(label) :].lstrip()
    if not rest or rest[0] not in ":：":
        return None
    return rest[1:].strip()


# 見出しの道筋のつなぎ。最上位の見出しからその節の見出しまでを、この文字列でつなぐ。
PATH_SEPARATOR = " > "


@dataclass
class OutlinedSection:
    """見出しを持つ節 1 つと、その節の見出しの道筋。本文は下位の見出しの節を含まない。"""

    section: Section
    path: str


def outline_sections(text: str) -> list[OutlinedSection]:
    """見出しを持つ節を、ファイルの並びの順に、見出しの道筋つきで返す。

    最初の見出しより前の本文（見出しを持たない塊）は、道筋を付けようが無いので入れない。
    道筋は、その節より浅い見出しのうち直近のものを、浅い順につないで作る。
    """
    found: list[OutlinedSection] = []
    ancestors: list[tuple[int, str]] = []
    for section in split_sections(text):
        if not section.heading:
            continue
        while ancestors and ancestors[-1][0] >= section.level:
            ancestors.pop()
        ancestors.append((section.level, section.heading))
        found.append(
            OutlinedSection(
                section=section,
                path=PATH_SEPARATOR.join(heading for _, heading in ancestors),
            )
        )
    return found


def has_heading_line(body: str) -> bool:
    """本文に、見出しとして読まれる行が 1 行でもあるか。"""
    return any(HEADING_RE.match(line) for line in body.splitlines())


def _join(lines: list[str]) -> str:
    """行の並びを、末尾に改行 1 つを持つ文字列にする。"""
    return "\n".join(lines).rstrip("\n") + "\n"


def replace_section_body(text: str, section: Section, body: str) -> str:
    """節の本文だけを置き換えた全文を返す。見出しの行と、下位の見出しの節は 1 文字も変えない。

    section は、同じ text を split_sections で切った節である。本文の前に空行を 1 つ、後ろに
    （次の見出しがあれば）空行を 1 つ置く。指紋は前後の空行を見ないので、置き方で値は変わらない。
    """
    lines = text.splitlines()
    new_body = body.strip("\n").splitlines()
    block = [lines[section.start], ""]
    if new_body:
        block.extend(new_body)
        if section.end < len(lines):
            block.append("")
    lines[section.start : section.end] = block
    return _join(lines)


def append_section_line(text: str, section: Section, line: str) -> str:
    """節の本文の末尾（下位の見出しの節の前）に 1 行足した全文を返す。ほかの行は変えない。"""
    lines = text.splitlines()
    last = section.start
    for index in range(section.start + 1, section.end):
        if lines[index].strip():
            last = index
    insert_at = last + 1
    addition = [line] if last != section.start else ["", line]
    lines[insert_at:insert_at] = addition
    if insert_at + len(addition) < len(lines) and lines[insert_at + len(addition)].strip():
        lines.insert(insert_at + len(addition), "")
    return _join(lines)


# ------------------------------------------------------------ 節の構造と欄を書き換える

# 見出しの深さの上限。Markdown の ATX 形式の見出しは 6 段まで。
MAX_HEADING_LEVEL = 6

# 欄の行のうち、値の手前までを取る形。「- ラベル: 」と行頭の宣言「ラベル: 」の 2 つ。
DEFINITION_PREFIX_RE = re.compile(r"^([ \t]*[-*][ \t]+([^:：]+)[:：][ \t]*)(.*)$")


def heading_text_is_valid(heading: str) -> bool:
    """見出しの文字として書けるか。空・改行を含む・「#」で始まるものは書けない。"""
    text = (heading or "").strip()
    return bool(text) and "\n" not in heading and "\r" not in heading and not text.startswith("#")


def _rejoin(lines: list[str], original: str) -> str:
    """行の並びを、元の全文の末尾の改行の有無に合わせてつなぐ。"""
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + ("\n" if original.endswith("\n") or not original else "")


def _level_at(lines: list[str], index: int) -> int:
    match = HEADING_RE.match(lines[index])
    if match is None:
        raise ValueError(f"{index + 1} 行目は見出しの行ではない")
    return len(match.group(1))


def subtree_end(lines: list[str], start: int) -> int:
    """見出しの行 start の節を、下位の節ごと含めたときの終わり（次の同じか浅い見出しの行の位置）。"""
    level = _level_at(lines, start)
    for index in range(start + 1, len(lines)):
        match = HEADING_RE.match(lines[index])
        if match is not None and len(match.group(1)) <= level:
            return index
    return len(lines)


def _make_heading(level: int, heading: str) -> str:
    return f"{'#' * level} {heading.strip()}"


def _insert_block(lines: list[str], at: int, block: list[str]) -> None:
    """行の位置 at に、前後に空行を 1 つずつ置いて塊を差し込む。前後の行そのものは変えない。"""
    while block and not block[-1].strip():
        block = block[:-1]
    addition: list[str] = []
    if at > 0 and lines[at - 1].strip():
        addition.append("")
    addition.extend(block)
    if at < len(lines):
        addition.append("")
    lines[at:at] = addition


def rename_heading(text: str, start: int, heading: str) -> str:
    """見出しの行 start の文字だけを置き換えた全文を返す。深さ・本文・下位の節は変えない。"""
    lines = text.splitlines()
    lines[start] = _make_heading(_level_at(lines, start), heading)
    return _rejoin(lines, text)


def _parent_level(lines: list[str], parent_start: int | None) -> int:
    """親の見出しの深さ。親が無い（ファイルの直下に置く）なら 0。"""
    return _level_at(lines, parent_start) if parent_start is not None else 0


def _parent_end(lines: list[str], parent_start: int | None) -> int:
    """親の下位の節の末尾の位置。親が無いならファイルの末尾。"""
    return subtree_end(lines, parent_start) if parent_start is not None else len(lines)


def insert_section(
    text: str, parent_start: int | None, heading: str, body: str, before_start: int | None = None
) -> str:
    """親の節より 1 段深い節を足した全文を返す。親が無ければ（None）、深さ 1 の節を足す。

    before_start が無ければ親の下位の節の末尾（親が無ければファイルの末尾）に、あればその見出しの
    行の直前に置く。
    """
    lines = text.splitlines()
    level = _parent_level(lines, parent_start) + 1
    at = before_start if before_start is not None else _parent_end(lines, parent_start)
    block = [_make_heading(level, heading)]
    body_lines = body.strip("\n").splitlines()
    if body_lines:
        block.extend(["", *body_lines])
    _insert_block(lines, at, block)
    return _rejoin(lines, text)


def delete_section(text: str, start: int) -> str:
    """見出しの行 start の節（見出しの行と本文）を消した全文を返す。下位の節を持たない節に使う。"""
    lines = text.splitlines()
    end = subtree_end(lines, start)
    del lines[start:end]
    return _rejoin(lines, text)


def shifted_levels(text: str, start: int, new_parent_start: int | None) -> list[int]:
    """節を新しい親の下（親が None なら深さ 1）へ動かしたときの、その節と下位の節の深さを並びの順に返す。"""
    lines = text.splitlines()
    delta = _parent_level(lines, new_parent_start) + 1 - _level_at(lines, start)
    end = subtree_end(lines, start)
    return [
        len(match.group(1)) + delta
        for match in (HEADING_RE.match(line) for line in lines[start:end])
        if match is not None
    ]


def move_section(
    text: str, start: int, new_parent_start: int | None, before_start: int | None = None
) -> str:
    """節を下位の節ごと、新しい親の下位の末尾（before_start があればその直前）へ移した全文を返す。

    新しい親が None なら、深さ 1 の節としてファイルの末尾（before_start があればその直前）へ移す。
    見出しの深さは新しい親より 1 段深くそろえ、下位の節も同じ段数ずらす。見出しの行の深さの
    ほかは、移す節の本文も下位の節の本文も 1 文字も変えない。
    """
    lines = text.splitlines()
    end = subtree_end(lines, start)
    delta = _parent_level(lines, new_parent_start) + 1 - _level_at(lines, start)
    block: list[str] = []
    for line in lines[start:end]:
        match = HEADING_RE.match(line)
        if match is not None and delta:
            block.append(_make_heading(len(match.group(1)) + delta, match.group(2)))
        else:
            block.append(line)
    target = before_start if before_start is not None else _parent_end(lines, new_parent_start)
    if start <= target <= end:
        target = start
    elif target > end:
        target -= end - start
    remaining = lines[:start] + lines[end:]
    # 抜いた跡に空行が 2 つ並んだら 1 つにする（抜いた節の前の空行と、次の見出しの前の空行）。
    if 0 < start < len(remaining) and not remaining[start - 1].strip() and not remaining[start].strip():
        del remaining[start]
        if target > start:
            target -= 1
    _insert_block(remaining, target, block)
    return _rejoin(remaining, text)


def _label_is(label: str, names: set[str], rule: BlockRule) -> bool:
    """欄のラベルが、読み替えと括弧書きの除去の後に names のどれかに当たるか。"""
    name = strip_note(label) if rule.strip_label_note else label
    return bool(names & set(rule.labels.get(name, (name,))))


def _field_label(line: str, rule: BlockRule) -> str | None:
    """行が欄の行なら、そのラベル（読み替えの前）を返す。欄の行でなければ None。"""
    stripped = line.strip()
    if DISCLOSURE_FORM_RE.match(stripped) is not None:
        return DISCLOSURE_FIELD
    match = DEFINITION_RE.match(stripped)
    if match is not None:
        return match.group(1).strip()
    if rule.fields_from_table and stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and cells[0]:
            return cells[0]
    for label in rule.bare_labels:
        if _bare_declaration(stripped, label) is not None:
            return label
    return None


def _with_value(line: str, value: str, rule: BlockRule) -> str:
    """欄の行の値だけを置き換えた行を返す。ラベルと書き方（箇条書き・表・行頭の宣言）はそのまま。"""
    indent = line[: len(line) - len(line.lstrip())]
    wide = DISCLOSURE_FORM_RE.match(line.strip())
    if wide is not None:
        return f"{indent}{wide.group(1)}{value}"
    match = DEFINITION_PREFIX_RE.match(line)
    if match is not None:
        return f"{match.group(1)}{value}"
    stripped = line.strip()
    if rule.fields_from_table and stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        cells[1] = value
        indent = line[: len(line) - len(line.lstrip())]
        return f"{indent}| " + " | ".join(cells) + " |"
    for label in rule.bare_labels:
        if _bare_declaration(stripped, label) is not None:
            indent = line[: len(line) - len(line.lstrip())]
            separator = stripped[len(label) :].lstrip()[0]
            return f"{indent}{label}{separator} {value}"
    return line


def _body_end(lines: list[str], start: int) -> int:
    """見出しの行 start の節の本文の終わり（次の見出しの行の位置）。"""
    for index in range(start + 1, len(lines)):
        if HEADING_RE.match(lines[index]):
            return index
    return len(lines)


def _value_of(line: str, rule: BlockRule) -> str:
    """欄の行の値を返す。"""
    wide = DISCLOSURE_FORM_RE.match(line.strip())
    if wide is not None:
        return wide.group(2).strip()
    match = DEFINITION_PREFIX_RE.match(line)
    if match is not None:
        return match.group(3).strip()
    stripped = line.strip()
    if rule.fields_from_table and stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        return cells[1] if len(cells) > 1 else ""
    for label in rule.bare_labels:
        value = _bare_declaration(stripped, label)
        if value is not None:
            return value
    return ""


def field_lines(
    text: str, start: int, name: str, rule: BlockRule = DEFAULT_BLOCK_RULE
) -> list[tuple[str, str]]:
    """見出しの行 start の節の本文にある欄 name の行を、（行そのもの、値）の組で、書かれた順に返す。"""
    lines = text.splitlines()
    found: list[tuple[str, str]] = []
    for index in range(start + 1, _body_end(lines, start)):
        label = _field_label(lines[index], rule)
        if label is not None and _label_is(label, {name}, rule):
            found.append((lines[index].strip(), _value_of(lines[index], rule)))
    return found


def set_field(
    text: str,
    start: int,
    name: str,
    value: str,
    anchor: str,
    rule: BlockRule = DEFAULT_BLOCK_RULE,
    number: int | None = None,
) -> str:
    """見出しの行 start の節の本文で、欄 name の値だけを置き換えた全文を返す。

    number（1 始まり）を渡すと、欄 name の行のうちその番号の行だけを置き換える。渡さなければ
    欄 name の行をすべて置き換える。欄が無ければ、欄 anchor の行の直後に、anchor の行と同じ書き方で
    欄の行を足す。下位の節の本文と、ほかの行は 1 文字も変えない。
    """
    lines = text.splitlines()
    end = _body_end(lines, start)
    replaced = False
    seen = 0
    anchor_at: int | None = None
    for index in range(start + 1, end):
        label = _field_label(lines[index], rule)
        if label is None:
            continue
        if _label_is(label, {name}, rule):
            seen += 1
            if number is None or seen == number:
                lines[index] = _with_value(lines[index], value, rule)
            replaced = True
        elif anchor_at is None and _label_is(label, {anchor}, rule):
            anchor_at = index
    if not replaced:
        if anchor_at is None:
            raise ValueError(f"欄「{anchor}」の行が無い")
        source = lines[anchor_at]
        stripped = source.strip()
        indent = source[: len(source) - len(source.lstrip())]
        if rule.fields_from_table and stripped.startswith("|"):
            new_line = f"{indent}| {name} | {value} |"
        else:
            bullet = DEFINITION_PREFIX_RE.match(source)
            mark = bullet.group(1).lstrip()[0] if bullet is not None else "-"
            new_line = f"{indent}{mark} {name}: {value}"
        lines.insert(anchor_at + 1, new_line)
    return _rejoin(lines, text)


# 箇条書きの行頭の印。「- 」「* 」と「1. 」の形。
LIST_ITEM_RE = re.compile(r"^([ \t]*)(?:[-*]|\d+\.)[ \t]+")


def list_items(
    text: str,
    start: int,
    name: str,
    known_labels: set[str],
    rule: BlockRule = DEFAULT_BLOCK_RULE,
) -> list[tuple[str, bool]]:
    """見出しの行 start の節の本文の、いちばん浅い箇条書きの項目を、（項目の先頭の行、欄 name の行を持つか）で返す。

    項目は、いちばん浅い字下げの箇条書きの行から、次に同じか浅い字下げの空でない行が来る手前までとする
    （下の字下げの行と入れ子の箇条書きを含む）。先頭の行が型の欄の行（ラベルが known_labels のどれかに
    読める「- ラベル: 値」）の項目は、節の欄なので数えない。欄 name の行を持つかは、項目の中の欄の行
    （入れ子の箇条書きの「- name: 値」を含む）で見る。
    """
    lines = text.splitlines()
    end = _body_end(lines, start)
    body = list(range(start + 1, end))
    depths = [len(LIST_ITEM_RE.match(lines[i]).group(1)) for i in body if LIST_ITEM_RE.match(lines[i])]
    if not depths:
        return []
    top = min(depths)
    heads = [
        i
        for i in body
        if LIST_ITEM_RE.match(lines[i]) and len(LIST_ITEM_RE.match(lines[i]).group(1)) == top
    ]
    found: list[tuple[str, bool]] = []
    for head in heads:
        stop = end
        for index in range(head + 1, end):
            line = lines[index]
            if line.strip() and len(line) - len(line.lstrip()) <= top:
                stop = index
                break
        label = _field_label(lines[head], rule)
        if label is not None and _label_is(label, known_labels, rule):
            continue
        has = any(
            (found_label := _field_label(lines[index], rule)) is not None
            and _label_is(found_label, {name}, rule)
            for index in range(head, stop)
        )
        found.append((lines[head].strip(), has))
    return found


def field_lines_with_items(
    text: str, start: int, name: str, rule: BlockRule = DEFAULT_BLOCK_RULE
) -> list[tuple[str, str, str | None]]:
    """見出しの行 start の節の欄 name の行を、（行そのもの、値、その行が属する項目の先頭の行）で返す。

    項目は list_items と同じく、いちばん浅い字下げの箇条書きの行から始まる塊とする。欄の行そのものが
    いちばん浅い字下げにある（節の欄として書かれた）ときは、項目の先頭の行を None にする。
    """
    lines = text.splitlines()
    end = _body_end(lines, start)
    body = list(range(start + 1, end))
    depths = [len(LIST_ITEM_RE.match(lines[i]).group(1)) for i in body if LIST_ITEM_RE.match(lines[i])]
    top = min(depths) if depths else 0
    found: list[tuple[str, str, str | None]] = []
    head: str | None = None
    for index in body:
        line = lines[index]
        match = LIST_ITEM_RE.match(line)
        if line.strip() and len(line) - len(line.lstrip()) <= top:
            head = line.strip() if match is not None and len(match.group(1)) == top else None
            at_top = True
        else:
            at_top = False
        label = _field_label(line, rule)
        if label is None or not _label_is(label, {name}, rule):
            continue
        found.append((line.strip(), _value_of(line, rule), None if at_top else head))
    return found
