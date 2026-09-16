"""README の節「## データの型とルール」が、定義の正本 ontology.yaml と一致しているかのテスト。

突き合わせの本体は、README の文面（str）と Ontology を受けて、違いの一覧（違いが無ければ
空リスト）を返す関数として書く。テスト関数はその関数を呼んで `assert not diffs` の形で見る。
こうしておくと、自己試験で「わざと壊した文面」を同じ関数にそのまま渡せる。
"""

from __future__ import annotations

import re
from pathlib import Path

from accord.models.ontology import Ontology, load_ontology

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
SVG_PATH = REPO_ROOT / "docs" / "ontology.svg"
SECTION_HEADING = "## データの型とルール"

# 冒頭の段落の数の書き方（仕様書のとおり。数字は半角、前後に半角スペース 1 つ）。
COUNT_PATTERNS = {
    "型": r"型 (\d+) つ",
    "関係": r"関係 (\d+) 種類",
    "矢印": r"矢印 (\d+) 本",
    "ルール": r"ルール (\d+) つ",
}

# Mermaid のノードの宣言 1 行。例: Positioning["売り方の決め"]
NODE_PATTERN = re.compile(r'^\s*(\w+)\["([^"]+)"\]\s*$', re.MULTILINE)

# Mermaid の矢印 1 行。例: Positioning -->|前面に出す| Package
EDGE_PATTERN = re.compile(r"^\s*(\w+)\s*-->\|([^|]+)\|\s*(\w+)\s*$", re.MULTILINE)


# ---------------------------------------------------------------- 節の切り出し


def extract_section(readme_text: str) -> str | None:
    """README の全文から、見出し「## データの型とルール」の節だけを切り出す。

    節は見出しの行の次から、次の「## 」見出しの手前まで（最後の節なら文末まで）。
    見出しが無ければ None を返す。
    """
    match = re.search(rf"^{re.escape(SECTION_HEADING)}\s*$", readme_text, re.MULTILINE)
    if match is None:
        return None
    start = match.end()
    rest = readme_text[start:]
    next_heading = re.search(r"^## ", rest, re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(readme_text)
    return readme_text[start:end]


def extract_mermaid_blocks(section_text: str) -> list[str]:
    """節の文面から、```mermaid のコードブロックの中身をすべて取り出す。"""
    return re.findall(r"```mermaid\n(.*?)```", section_text, re.DOTALL)


def extract_mermaid_block(section_text: str) -> str | None:
    """節の文面から、```mermaid のコードブロックの中身を 1 つ取り出す（無ければ None）。"""
    blocks = extract_mermaid_blocks(section_text)
    return blocks[0] if blocks else None


def _table_rows(section_text: str) -> list[list[str]]:
    """節の文面にある Markdown の表の行を、セルの一覧の一覧にして返す。

    区切り行（`---` や `:--:` だけで組み立てた行）は除く。表が型の表かルールの表かは
    区別せず、節全体から拾う（仕様書の突き合わせが「行がどこかにある」しか求めていないため）。
    """
    rows: list[list[str]] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _real_readme_text() -> str:
    """本物の README.md の全文を読む。"""
    return README_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 突き合わせ（違いの一覧を返す）


def diff_heading_and_counts(readme_text: str, ontology: Ontology) -> list[str]:
    """見出しの有無と、冒頭の段落の数（型・関係・矢印・ルール）が正本と一致するかを見る。

    数は決め打ちせず、load_ontology() の中身（型・関係・関係を to で展開した矢印・制約の
    それぞれの件数）から数える。
    """
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]

    expected = {
        "型": len(ontology.types),
        "関係": len(ontology.relations),
        "矢印": ontology.relation_edge_count,
        "ルール": len(ontology.constraints),
    }
    diffs: list[str] = []
    for key, pattern in COUNT_PATTERNS.items():
        match = re.search(pattern, section)
        if match is None:
            diffs.append(
                f"冒頭の段落に「{key} {expected[key]} ...」の書き方が見つからない"
                f"（正規表現 {pattern!r} に一致する箇所が無い）。"
            )
            continue
        found = int(match.group(1))
        if found != expected[key]:
            diffs.append(
                f"冒頭の段落の「{key}」の数が {found} と書かれているが、"
                f"正本から数えると {expected[key]}。"
            )
    return diffs


def diff_mermaid_nodes(readme_text: str, ontology: Ontology) -> list[str]:
    """図のノードの集合と各ノードの表示名が、型の name と label に過不足なく一致するかを見る。"""
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]
    blocks = extract_mermaid_blocks(section)
    if not blocks:
        return ["節に ```mermaid のコードブロックが無い。"]
    if len(blocks) != 1:
        return [f"節の ```mermaid のコードブロックは 1 つだけのはずが {len(blocks)} 個ある。"]
    mermaid = blocks[0]

    nodes = dict(NODE_PATTERN.findall(mermaid))
    expected_names = {entry.name for entry in ontology.types}
    found_names = set(nodes)

    diffs: list[str] = []
    missing = expected_names - found_names
    if missing:
        diffs.append(f"図に無いノード: {', '.join(sorted(missing))}")
    extra = found_names - expected_names
    if extra:
        diffs.append(f"正本に無いノードが図にある: {', '.join(sorted(extra))}")
    for entry in ontology.types:
        if entry.name in nodes and nodes[entry.name] != entry.label:
            diffs.append(
                f"ノード {entry.name} の表示名が「{nodes[entry.name]}」だが、"
                f"正本の label は「{entry.label}」。"
            )
    return diffs


def diff_mermaid_edges(readme_text: str, ontology: Ontology) -> list[str]:
    """図の矢印の集合（from・関係名・to の 3 つ組）が、関係を to ごとに展開した集合と一致するかを見る。

    裏づけの関係は to を 2 つ持つので、矢印としては 2 本に展開して比べる。
    """
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]
    mermaid = extract_mermaid_block(section)
    if mermaid is None:
        return ["節に ```mermaid のコードブロックが無い。"]

    found_edges = {(f, r, t) for f, r, t in EDGE_PATTERN.findall(mermaid)}
    expected_edges = {
        (relation.from_type, relation.name, to)
        for relation in ontology.relations
        for to in relation.to_types
    }

    diffs: list[str] = []
    missing = expected_edges - found_edges
    if missing:
        diffs.append(
            "図に無い矢印: " + "; ".join(f"{f} -->|{r}| {t}" for f, r, t in sorted(missing))
        )
    extra = found_edges - expected_edges
    if extra:
        diffs.append(
            "正本に無い矢印が図にある: "
            + "; ".join(f"{f} -->|{r}| {t}" for f, r, t in sorted(extra))
        )
    return diffs


def diff_type_table(readme_text: str, ontology: Ontology) -> list[str]:
    """型の表に、型ごとの label を 1 列目に持つ行がそれぞれあるかを見る（余分な行は見ない）。"""
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]

    first_cells = {row[0] for row in _table_rows(section) if row}
    diffs: list[str] = []
    for entry in ontology.types:
        if entry.label not in first_cells:
            diffs.append(f"型の表に label「{entry.label}」を 1 列目に持つ行が無い。")
    return diffs


def diff_rule_table(readme_text: str, ontology: Ontology) -> list[str]:
    """ルールの表に、制約ごとの name を 1 列目に持つ行があり、appears_as の語を含むかを見る。"""
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]

    rows = _table_rows(section)
    diffs: list[str] = []
    for constraint in ontology.constraints:
        matching_rows = [row for row in rows if row and row[0] == constraint.name]
        if not matching_rows:
            diffs.append(f"ルールの表に制約名「{constraint.name}」を 1 列目に持つ行が無い。")
            continue
        if not any(constraint.appears_as in "|".join(row) for row in matching_rows):
            diffs.append(
                f"ルールの表の「{constraint.name}」の行に、"
                f"現れ方「{constraint.appears_as}」の語が含まれない。"
            )
    return diffs


# ---------------------------------------------------------------- テスト（受け入れ条件 1〜5）


def test_heading_and_counts_match_ontology() -> None:
    """節の見出しがあり、冒頭の段落の型・関係・矢印・ルールの数が正本の件数と一致する。"""
    ontology = load_ontology()
    diffs = diff_heading_and_counts(_real_readme_text(), ontology)
    assert not diffs, "\n".join(diffs)


def test_mermaid_nodes_match_types() -> None:
    """図のノードの集合と各ノードの表示名が、型の name と label に過不足なく一致する。"""
    ontology = load_ontology()
    diffs = diff_mermaid_nodes(_real_readme_text(), ontology)
    assert not diffs, "\n".join(diffs)


def test_mermaid_edges_match_relations() -> None:
    """図の矢印の集合が、関係を相手ごとに展開した 7 本と過不足なく一致する。"""
    ontology = load_ontology()
    diffs = diff_mermaid_edges(_real_readme_text(), ontology)
    assert not diffs, "\n".join(diffs)


def test_type_table_lists_every_label() -> None:
    """型の表に、7 つの label それぞれを 1 列目に持つ行がある。"""
    ontology = load_ontology()
    diffs = diff_type_table(_real_readme_text(), ontology)
    assert not diffs, "\n".join(diffs)


def test_rule_table_lists_every_constraint_with_appears_as() -> None:
    """ルールの表に、7 つの制約名それぞれを 1 列目に持つ行があり、その行に appears_as の語が含まれる。"""
    ontology = load_ontology()
    diffs = diff_rule_table(_real_readme_text(), ontology)
    assert not diffs, "\n".join(diffs)


# ---------------------------------------------------------------- テスト（受け入れ条件 6・自己試験）


def test_self_check_removing_one_arrow_line_is_caught() -> None:
    """本物の節から矢印の行を 1 本消した文面を渡すと、矢印の差分検査が違いを 1 件以上返す。

    審判（diff_mermaid_edges）自体が壊れていないかを見る自己試験。壊し方が対象を見つけら
    れず文面が変わらなかった場合は、審判の合否と切り分けるためにその時点でテストを落とす。
    """
    ontology = load_ontology()
    readme_text = _real_readme_text()
    section = extract_section(readme_text)
    assert section is not None, "README に節が無く、矢印を消す自己試験の対象を壊せない。"
    mermaid = extract_mermaid_block(section)
    assert mermaid is not None, "節に mermaid ブロックが無く、自己試験の対象を壊せない。"
    edge_lines = [line for line in mermaid.splitlines() if EDGE_PATTERN.match(line)]
    assert edge_lines, "mermaid に矢印の行が無く、自己試験の対象を壊せない。"

    broken_text = readme_text.replace(edge_lines[0] + "\n", "", 1)
    assert broken_text != readme_text, "矢印の行を消す置き換えが効かず、文面が変わらなかった。"

    diffs = diff_mermaid_edges(broken_text, ontology)
    assert diffs, "矢印を 1 本消しても、矢印の差分検査が違いを返さなかった（審判が効いていない）。"


def test_self_check_removing_one_type_table_row_is_caught() -> None:
    """本物の型の表から行を 1 つ消した文面を渡すと、型の表の差分検査が違いを 1 件以上返す。

    審判（diff_type_table）自体が壊れていないかを見る自己試験。
    """
    ontology = load_ontology()
    readme_text = _real_readme_text()
    section = extract_section(readme_text)
    assert section is not None, "README に節が無く、型の表の行を消す自己試験の対象を壊せない。"

    label_set = {entry.label for entry in ontology.types}
    target_line = None
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] in label_set:
            target_line = line
            break
    assert target_line is not None, "型の表に label と一致する行が見つからず、自己試験の対象を壊せない。"

    broken_text = readme_text.replace(target_line + "\n", "", 1)
    assert broken_text != readme_text, "型の表の行を消す置き換えが効かず、文面が変わらなかった。"

    diffs = diff_type_table(broken_text, ontology)
    assert diffs, "型の表の行を 1 つ消しても、型の表の差分検査が違いを返さなかった（審判が効いていない）。"


def test_self_check_swapping_appears_as_word_is_caught() -> None:
    """ルールの表のある行の appears_as の語を別の語に替えた文面を渡すと、違いが 1 件以上返る。

    審判（diff_rule_table）自体が壊れていないかを見る自己試験。appears_as が「拒否」の制約を
    1 つ選び、その行の「拒否」を「検出」に書き換える。
    """
    ontology = load_ontology()
    readme_text = _real_readme_text()
    section = extract_section(readme_text)
    assert section is not None, "README に節が無く、appears_as を替える自己試験の対象を壊せない。"

    target_constraint = next((c for c in ontology.constraints if c.appears_as == "拒否"), None)
    assert target_constraint is not None, "正本に appears_as が「拒否」の制約が無い。"

    target_line = None
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] == target_constraint.name and "拒否" in line:
            target_line = line
            break
    assert (
        target_line is not None
    ), f"ルールの表に「{target_constraint.name}」の行が見つからず、自己試験の対象を壊せない。"

    broken_line = target_line.replace("拒否", "検出")
    assert broken_line != target_line, "「拒否」の置き換えが効かず、行が変わらなかった。"
    broken_text = readme_text.replace(target_line, broken_line, 1)
    assert broken_text != readme_text, "行の置き換えが README 全文に反映されなかった。"

    diffs = diff_rule_table(broken_text, ontology)
    assert diffs, "appears_as の語を替えても、ルールの表の差分検査が違いを返さなかった（審判が効いていない）。"


# ---------------------------------------------------------------- 画像にした図（docs/ontology.svg）


def diff_svg_labels(svg_text: str, ontology: Ontology) -> list[str]:
    """画像にした図に、型の表示名 7 つと関係の名前 6 つがすべて文字として入っているかを見る。

    画像は Mermaid の原稿から描いたもので、原稿を直したら描き直す。描き直し忘れをここで拾う。
    """
    diffs: list[str] = []
    for entry in ontology.types:
        if entry.label not in svg_text:
            diffs.append(f"画像の図に型の表示名「{entry.label}」が無い。")
    for relation in ontology.relations:
        if relation.name not in svg_text:
            diffs.append(f"画像の図に関係の名前「{relation.name}」が無い。")
    return diffs


def test_svg_figure_lists_every_type_and_relation() -> None:
    """docs/ontology.svg があり、型の表示名 7 つと関係の名前 6 つをすべて含む。"""
    assert SVG_PATH.exists(), f"画像にした図 {SVG_PATH} が無い。"
    ontology = load_ontology()
    diffs = diff_svg_labels(SVG_PATH.read_text(encoding="utf-8"), ontology)
    assert not diffs, "\n".join(diffs)
