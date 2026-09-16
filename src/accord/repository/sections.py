"""Markdown を見出しの階層と本文に切り分け、設定の書き方どおりに節と欄を読む。

正本は Markdown のままで持つ、という決めなので、「節」が事実の単位になる。裏づけの節も
出典の節も、この文書が切り出した見出しの文字列で指す。

正本の書き方は人によって違う。見出しの深さも、欄を箇条書きで書くか表で書くかも、欄の
ラベルの言い方も違う。その違いは設定（`BlockRule`）が持ち、この文書はそれを当てる側に徹する。
どの節をブロックとして読むかは `select_blocks`、その節の欄をどう読むかは `read_fields` が
1 か所で決め、正本 7 種の読み込みはどちらも同じ関数を通る。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from accord.vocabulary.settings import DEFAULT_BLOCK_RULE, BlockRule

# ATX 形式の見出し（# から ###### まで）。
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")

# 定義の行。「- ラベル: 値」の形で、正本の欄はこの書き方で持つ。
DEFINITION_RE = re.compile(r"^[-*][ \t]+([^:：]+)[:：][ \t]*(.*)$")

# 箇条書きの行。「- 中身」の形で、ラベルを持たない並びはこの書き方で持つ。
BULLET_RE = re.compile(r"^[-*][ \t]+(.+?)[ \t]*$")

# 見出しやラベルの末尾の括弧書き。「成果（定量は聞き取りで足した）」の括弧の部分。
NOTE_RE = re.compile(r"[（(][^（）()]*[）)][ \t]*$")

# 見出しの前置きに続く数字。「案件12｜…」の前置きを外した残りから 12 を取る。
LEADING_NUMBER_RE = re.compile(r"^[ \t]*(\d+)")


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

        if not section.heading or section.level not in levels:
            continue
        if rule.under_headings and not any(name in rule.under_headings for name in above):
            continue
        if section.heading in rule.skip_headings:
            continue
        if any(name in rule.skip_headings for name in above):
            continue
        if rule.heading_prefix and not section.heading.startswith(rule.heading_prefix):
            continue
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
    if rule.fields_from_table:
        entries += [
            (cells[0], cells[1])
            for cells in table_rows(section.body)
            if len(cells) >= 2 and cells[0]
        ]

    fields: dict[str, str] = {}
    for label, value in entries:
        name = strip_note(label) if rule.strip_label_note else label
        for target in rule.labels.get(name, (name,)):
            if target in fields:
                fields[target] = f"{fields[target]}\n{value}"
            else:
                fields[target] = value
    return fields


def _definition_entries(body: str, bare_labels: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """本文から「- ラベル: 値」の行と、行頭の宣言の行を、書かれた順に拾う。"""
    entries: list[tuple[str, str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        match = DEFINITION_RE.match(line)
        if match is not None:
            entries.append((match.group(1).strip(), match.group(2).strip()))
            continue
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
