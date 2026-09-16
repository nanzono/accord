"""Markdown を見出しの階層と本文に切り分ける。

正本は Markdown のままで持つ、という決めなので、「節」が事実の単位になる。裏づけの節も
出典の節も、この文書が切り出した見出しの文字列で指す。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ATX 形式の見出し（# から ###### まで）。
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")

# 定義の行。「- ラベル: 値」の形で、正本の欄はこの書き方で持つ。
DEFINITION_RE = re.compile(r"^[-*][ \t]+([^:：]+)[:：][ \t]*(.*)$")


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


def parse_definition_list(body: str) -> dict[str, str]:
    """節の本文から「- ラベル: 値」の行を拾い、ラベルと値の対にする。

    同じラベルが複数回出たときは、値を改行でつないで 1 つにまとめる。
    """
    fields: dict[str, str] = {}
    for line in body.splitlines():
        match = DEFINITION_RE.match(line.strip())
        if match is None:
            continue
        label = match.group(1).strip()
        value = match.group(2).strip()
        if label in fields:
            fields[label] = f"{fields[label]}\n{value}"
        else:
            fields[label] = value
    return fields
