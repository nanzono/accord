"""README の節「## データの型とルール」が、定義の正本 ontology.yaml と一致しているかのテスト。

突き合わせの本体は、README の文面（str）と Ontology を受けて、違いの一覧（違いが無ければ
空リスト）を返す関数として書く。テスト関数はその関数を呼んで `assert not diffs` の形で見る。
こうしておくと、自己試験で「わざと壊した文面」を同じ関数にそのまま渡せる。

要件 1 件につきテストを 1 本置くので、突き合わせの関数は「どの観点を見るか」を引数で絞れる。
絞らずに呼ぶと、もとの 1 本が見ていた観点をすべて見る（自己試験はこの形で呼ぶ）。観点ごとに
絞った呼び出しをすべて足すと、絞らない呼び出しと同じ違いの一覧になる。だから 1 本を数本に
割っても、見ているものは減らない。
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

# 節の中に 2 か所以上書くことがあり、すべてを拾って正本の数と比べる数の書き方。
# 冒頭の段落の「ルール N つ」と、ルールの表の前の「ルール N つは次のとおり」の 2 か所がある。
# 最初の 1 か所だけを見ると、2 か所目が古い数のまま残っても気づけない。
EVERY_OCCURRENCE_KEYS = ("ルール",)

# ルールの表の見出しの行の 1 列目の書き出し。型の表と見分けるのに使う。
RULE_TABLE_HEADER_PREFIX = "ルール"

# Mermaid のノードの宣言 1 行。例: Positioning["売り方の決め"]
NODE_PATTERN = re.compile(r'^\s*(\w+)\["([^"]+)"\]\s*$', re.MULTILINE)

# Mermaid の矢印 1 行。例: Positioning -->|前面に出す| Package
EDGE_PATTERN = re.compile(r"^\s*(\w+)\s*-->\|([^|]+)\|\s*(\w+)\s*$", re.MULTILINE)

# 突き合わせの観点。要件 1 件につき 1 つを選んで渡す。既定は「全部」で、もとの 1 本と同じ。
ALL_COUNT_KEYS = tuple(COUNT_PATTERNS)
NODE_ASPECTS = ("one_diagram", "missing_nodes", "unknown_nodes", "labels")
EDGE_ASPECTS = ("missing_edges", "unknown_edges")
RULE_TABLE_ASPECTS = ("rows", "appears_as", "unknown_rows")
SVG_ASPECTS = ("type_labels", "relation_names")


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


def _rule_table_rows(section_text: str) -> list[list[str]] | None:
    """節の文面から、ルールの表のデータ行（見出しの行と区切り行を除く）を返す。

    ルールの表は、見出しの行の 1 列目が「ルール」で始まる表である。見つからなければ None を返す。
    型の表の行を混ぜないので、1 列目が制約の名前でない行を「正本に無い名前の行」として拾える。
    """
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            current.append([cell.strip() for cell in stripped.strip("|").split("|")])
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)

    for table in tables:
        if table and table[0] and table[0][0].startswith(RULE_TABLE_HEADER_PREFIX):
            return [
                row
                for row in table[1:]
                if row and not all(re.fullmatch(r":?-+:?", cell) for cell in row)
            ]
    return None


def _real_readme_text() -> str:
    """本物の README.md の全文を読む。"""
    return README_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 突き合わせ（違いの一覧を返す）


def diff_heading_and_counts(
    readme_text: str, ontology: Ontology, keys: tuple[str, ...] = ALL_COUNT_KEYS
) -> list[str]:
    """見出しの有無と、冒頭の段落の数（型・関係・矢印・ルール）が正本と一致するかを見る。

    数は決め打ちせず、load_ontology() の中身（型・関係・関係を to で展開した矢印・制約の
    それぞれの件数）から数える。keys を絞ると、その数だけを見る。
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
        if key not in keys:
            continue
        matches = list(re.finditer(pattern, section))
        if not matches:
            diffs.append(
                f"冒頭の段落に「{key} {expected[key]} ...」の書き方が見つからない"
                f"（正規表現 {pattern!r} に一致する箇所が無い）。"
            )
            continue
        # 節の中のすべての書き方を見る数と、最初の 1 か所だけを見る数がある。
        if key not in EVERY_OCCURRENCE_KEYS:
            matches = matches[:1]
        for match in matches:
            found = int(match.group(1))
            if found != expected[key]:
                diffs.append(
                    f"節の「{match.group(0)}」の「{key}」の数が {found} と書かれているが、"
                    f"正本から数えると {expected[key]}。"
                )
    return diffs


def diff_mermaid_nodes(
    readme_text: str, ontology: Ontology, aspects: tuple[str, ...] = NODE_ASPECTS
) -> list[str]:
    """節の図が 1 つであることと、ノードの集合・表示名が型の name と label に一致するかを見る。

    aspects を絞ると、その観点だけを見る。図が無い・2 つ以上あるときは、どの観点でも同じ
    1 件を返す（ノードを数える相手が定まらないため）。
    """
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
    if "missing_nodes" in aspects and missing:
        diffs.append(f"図に無いノード: {', '.join(sorted(missing))}")
    extra = found_names - expected_names
    if "unknown_nodes" in aspects and extra:
        diffs.append(f"正本に無いノードが図にある: {', '.join(sorted(extra))}")
    if "labels" in aspects:
        for entry in ontology.types:
            if entry.name in nodes and nodes[entry.name] != entry.label:
                diffs.append(
                    f"ノード {entry.name} の表示名が「{nodes[entry.name]}」だが、"
                    f"正本の label は「{entry.label}」。"
                )
    return diffs


def diff_mermaid_edges(
    readme_text: str, ontology: Ontology, aspects: tuple[str, ...] = EDGE_ASPECTS
) -> list[str]:
    """図の矢印の集合（from・関係名・to の 3 つ組）が、関係を to ごとに展開した集合と一致するかを見る。

    裏づけの関係は to を 3 つ、由来は 2 つ持つので、矢印としてはその本数に展開して比べる。
    aspects を絞ると、足りない矢印か、正本に無い矢印かの片方だけを見る。
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
    if "missing_edges" in aspects and missing:
        diffs.append(
            "図に無い矢印: " + "; ".join(f"{f} -->|{r}| {t}" for f, r, t in sorted(missing))
        )
    extra = found_edges - expected_edges
    if "unknown_edges" in aspects and extra:
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


def diff_rule_table(
    readme_text: str, ontology: Ontology, aspects: tuple[str, ...] = RULE_TABLE_ASPECTS
) -> list[str]:
    """ルールの表に、制約ごとの name を 1 列目に持つ行があり、appears_as の語を含むかを見る。

    あわせて、ルールの表に正本に無い名前を 1 列目に持つ行が無いかを見る（名前を変えたあとの
    古い名前の行の消し忘れを拾う）。aspects を絞ると、そのうちの 1 つの観点だけを見る。
    """
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]

    rows = _table_rows(section)
    diffs: list[str] = []
    if "unknown_rows" in aspects:
        rule_rows = _rule_table_rows(section)
        if rule_rows is None:
            diffs.append(
                f"見出しの行の 1 列目が「{RULE_TABLE_HEADER_PREFIX}」で始まるルールの表が無い。"
            )
        else:
            names = {constraint.name for constraint in ontology.constraints}
            for row in rule_rows:
                if row[0] not in names:
                    diffs.append(f"ルールの表に、正本に無い制約名「{row[0]}」の行がある。")
    for constraint in ontology.constraints:
        matching_rows = [row for row in rows if row and row[0] == constraint.name]
        if not matching_rows:
            if "rows" in aspects:
                diffs.append(f"ルールの表に制約名「{constraint.name}」を 1 列目に持つ行が無い。")
            continue
        if "appears_as" not in aspects:
            continue
        if not any(constraint.appears_as in "|".join(row) for row in matching_rows):
            diffs.append(
                f"ルールの表の「{constraint.name}」の行に、"
                f"現れ方「{constraint.appears_as}」の語が含まれない。"
            )
    return diffs


# ---------------------------------------------------------------- テスト（冒頭の段落の数）


def test_REQ_341_the_readme_states_the_type_count() -> None:
    """冒頭の段落の「型 N つ」が、正本から数えた型の件数と一致する。"""
    ontology = load_ontology()
    diffs = diff_heading_and_counts(_real_readme_text(), ontology, keys=("型",))
    assert not diffs, "\n".join(diffs)


def test_REQ_342_the_readme_states_the_relation_count() -> None:
    """冒頭の段落の「関係 N 種類」が、正本から数えた関係の件数と一致する。"""
    ontology = load_ontology()
    diffs = diff_heading_and_counts(_real_readme_text(), ontology, keys=("関係",))
    assert not diffs, "\n".join(diffs)


def test_REQ_343_the_readme_states_the_edge_count() -> None:
    """冒頭の段落の「矢印 N 本」が、関係を相手の型ごとに展開した本数と一致する。"""
    ontology = load_ontology()
    diffs = diff_heading_and_counts(_real_readme_text(), ontology, keys=("矢印",))
    assert not diffs, "\n".join(diffs)


def test_REQ_344_the_readme_states_the_rule_count() -> None:
    """節の中の「ルール N つ」のすべてが、正本から数えた制約の件数と一致する。

    冒頭の段落と、ルールの表の前の 2 か所がある。どちらか 1 か所でも古い数なら落ちる。
    """
    ontology = load_ontology()
    diffs = diff_heading_and_counts(_real_readme_text(), ontology, keys=("ルール",))
    assert not diffs, "\n".join(diffs)


# ---------------------------------------------------------------- テスト（節の中の図）


def test_REQ_345_the_readme_has_exactly_one_diagram() -> None:
    """節に ```mermaid のコードブロックが 1 つだけある。"""
    ontology = load_ontology()
    diffs = diff_mermaid_nodes(_real_readme_text(), ontology, aspects=("one_diagram",))
    assert not diffs, "\n".join(diffs)


def test_REQ_346_the_diagram_has_every_type_as_a_node() -> None:
    """図に、正本が挙げる型がすべてノードとして置かれている。"""
    ontology = load_ontology()
    diffs = diff_mermaid_nodes(_real_readme_text(), ontology, aspects=("missing_nodes",))
    assert not diffs, "\n".join(diffs)


def test_REQ_347_the_diagram_has_no_unknown_node() -> None:
    """図に、正本に無いノードが置かれていない。"""
    ontology = load_ontology()
    diffs = diff_mermaid_nodes(_real_readme_text(), ontology, aspects=("unknown_nodes",))
    assert not diffs, "\n".join(diffs)


def test_REQ_348_the_diagram_node_labels_match_the_ontology() -> None:
    """図のノードの表示名が、正本のその型の label と同じである。"""
    ontology = load_ontology()
    diffs = diff_mermaid_nodes(_real_readme_text(), ontology, aspects=("labels",))
    assert not diffs, "\n".join(diffs)


def test_REQ_349_the_diagram_has_every_edge() -> None:
    """図に、関係を相手の型ごとに展開した矢印がすべて置かれている。"""
    ontology = load_ontology()
    diffs = diff_mermaid_edges(_real_readme_text(), ontology, aspects=("missing_edges",))
    assert not diffs, "\n".join(diffs)


def test_REQ_350_the_diagram_has_no_unknown_edge() -> None:
    """図に、正本に無い矢印が置かれていない。"""
    ontology = load_ontology()
    diffs = diff_mermaid_edges(_real_readme_text(), ontology, aspects=("unknown_edges",))
    assert not diffs, "\n".join(diffs)


# ---------------------------------------------------------------- テスト（節の中の表）


def test_REQ_351_the_type_table_lists_every_type_label() -> None:
    """型の表に、正本の型の label それぞれを 1 列目に持つ行がある。"""
    ontology = load_ontology()
    diffs = diff_type_table(_real_readme_text(), ontology)
    assert not diffs, "\n".join(diffs)


def test_REQ_352_the_rule_table_lists_every_rule_name() -> None:
    """ルールの表に、正本の制約の name それぞれを 1 列目に持つ行がある。"""
    ontology = load_ontology()
    diffs = diff_rule_table(_real_readme_text(), ontology, aspects=("rows",))
    assert not diffs, "\n".join(diffs)


def test_REQ_372_the_rule_table_has_no_unknown_rule_name() -> None:
    """ルールの表に、正本に無い制約の名前を 1 列目に持つ行が無い。"""
    ontology = load_ontology()
    diffs = diff_rule_table(_real_readme_text(), ontology, aspects=("unknown_rows",))
    assert not diffs, "\n".join(diffs)


def test_REQ_353_the_rule_table_shows_how_each_rule_appears() -> None:
    """ルールの表の制約の行に、正本のその制約の appears_as の語が含まれる。"""
    ontology = load_ontology()
    diffs = diff_rule_table(_real_readme_text(), ontology, aspects=("appears_as",))
    assert not diffs, "\n".join(diffs)


# ---------------------------------------------------------------- テスト（受け入れ条件 6・自己試験）


def test_self_check_removing_one_arrow_line_is_caught() -> None:
    """番号なし: 説明書の図から矢印の行を 1 本消した文面で、矢印を突き合わせる関数が違いを返すかを試す自己試験。accord の振る舞いではなくテストの中の道具を確かめるので、要件に結ばない。

    本物の節から矢印の行を 1 本消した文面を渡すと、矢印の差分検査が違いを 1 件以上返す。

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
    """番号なし: 説明書の型の表から行を 1 つ消した文面で、型の表を突き合わせる関数が違いを返すかを試す自己試験。accord の振る舞いではなくテストの中の道具を確かめるので、要件に結ばない。

    本物の型の表から行を 1 つ消した文面を渡すと、型の表の差分検査が違いを 1 件以上返す。

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
    """番号なし: 説明書のルールの表の現れ方の語を替えた文面で、ルールの表を突き合わせる関数が違いを返すかを試す自己試験。accord の振る舞いではなくテストの中の道具を確かめるので、要件に結ばない。

    ルールの表のある行の appears_as の語を別の語に替えた文面を渡すと、違いが 1 件以上返る。

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


def diff_svg_labels(
    svg_text: str, ontology: Ontology, aspects: tuple[str, ...] = SVG_ASPECTS
) -> list[str]:
    """画像にした図に、型の表示名と関係の名前がすべて文字として入っているかを見る。

    画像は Mermaid の原稿から描いたもので、原稿を直したら描き直す。描き直し忘れをここで拾う。
    aspects を絞ると、型の表示名か関係の名前かの片方だけを見る。
    """
    diffs: list[str] = []
    if "type_labels" in aspects:
        for entry in ontology.types:
            if entry.label not in svg_text:
                diffs.append(f"画像の図に型の表示名「{entry.label}」が無い。")
    if "relation_names" in aspects:
        for relation in ontology.relations:
            if relation.name not in svg_text:
                diffs.append(f"画像の図に関係の名前「{relation.name}」が無い。")
    return diffs


def test_REQ_354_the_repository_ships_the_diagram_image() -> None:
    """節の図を画像にしたもの（docs/ontology.svg）が同梱されている。"""
    assert SVG_PATH.exists(), f"画像にした図 {SVG_PATH} が無い。"


def test_REQ_355_the_image_carries_every_type_label() -> None:
    """画像にした図に、正本が挙げる型の表示名がすべて入っている。"""
    assert SVG_PATH.exists(), f"画像にした図 {SVG_PATH} が無い。"
    ontology = load_ontology()
    diffs = diff_svg_labels(SVG_PATH.read_text(encoding="utf-8"), ontology, aspects=("type_labels",))
    assert not diffs, "\n".join(diffs)


def test_REQ_356_the_image_carries_every_relation_name() -> None:
    """画像にした図に、正本が挙げる関係の名前がすべて入っている。"""
    assert SVG_PATH.exists(), f"画像にした図 {SVG_PATH} が無い。"
    ontology = load_ontology()
    diffs = diff_svg_labels(
        SVG_PATH.read_text(encoding="utf-8"), ontology, aspects=("relation_names",)
    )
    assert not diffs, "\n".join(diffs)
