"""README の節「## 自分のデータで使う」が、2 通りの起動を取り違えない形で書けているかのテスト。

`uvx` は指したパスから組み立てた環境を版番号で覚えるので、版を上げないままソースを直しても、
前の版が動き続ける。README がその起動だけを案内していると、読んだ人は古いコードが返した結果を
正本の不備と読み、正しい正本を直しにかかる。だから、手元の木をそのまま動かす起動が書かれていること、
版を固定する起動には注意書きが付いていること、`.mcp.json` の例が手元の木を動かす形であることを、
文面から機械で見る。

突き合わせの本体は、README の文面（str）を受けて違いの一覧（違いが無ければ空リスト）を返す
関数として書く。テスト関数はその関数を呼んで `assert not diffs` の形で見る。こうしておくと、
自己試験で「わざと壊した文面」を同じ関数にそのまま渡せる。

要件 1 件につきテストを 1 本置くので、突き合わせの関数は「どの観点を見るか」を引数で絞れる。
絞らずに呼ぶと、もとの 1 本が見ていた観点をすべて見る（自己試験はこの形で呼ぶ）。観点ごとに
絞った呼び出しをすべて足すと、絞らない呼び出しと同じ違いの一覧になる。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
SECTION_HEADING = "## 自分のデータで使う"

# 手元の木をそのまま動かす起動の書き出し。
IN_PLACE_COMMAND = "uv run --project"

# 版を固定して入れて使う起動のコマンド名。
PINNED_COMMAND = "uvx"

# 版を上げないと古い版が動き続ける、という注意書きに必ず入る 2 つの語。
VERSION_WARNING_WORDS = ("version", "上げ")

# 突き合わせの観点。要件 1 件につき 1 つを選んで渡す。既定は「全部」で、もとの 1 本と同じ。
MCP_ASPECTS = ("example_present", "in_place")
BOTH_WAYS_ASPECTS = ("in_place", "pinned")


# ---------------------------------------------------------------- 節の切り出し


def extract_section(readme_text: str) -> str | None:
    """README の全文から、見出し「## 自分のデータで使う」の節だけを切り出す。

    節は見出しの行の次から、次の「## 」見出しの手前まで（最後の節なら文末まで）。
    コードブロック（``` で囲まれた中）の行は見出しとして数えない。節の中の Markdown の例に
    「## 2026-09-10 全体」の行があり、そこで節が切れてしまうからである。
    見出しが無ければ None を返す。
    """
    lines = readme_text.splitlines()
    start = None
    fenced = False
    for index, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if start is None:
            if line.strip() == SECTION_HEADING:
                start = index + 1
            continue
        if line.startswith("## "):
            return "\n".join(lines[start:index])
    if start is None:
        return None
    return "\n".join(lines[start:])


def extract_json_blocks(section_text: str) -> list[str]:
    """節の文面から、```json のコードブロックの中身をすべて取り出す。"""
    return re.findall(r"```json\n(.*?)```", section_text, re.DOTALL)


def _real_readme_text() -> str:
    """本物の README.md の全文を読む。"""
    return README_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 突き合わせ（違いの一覧を返す）


def diff_mcp_example(readme_text: str, aspects: tuple[str, ...] = MCP_ASPECTS) -> list[str]:
    """AI から呼ぶときの設定の例があり、手元の木をその場で動かす起動になっているかを見る。

    aspects を絞ると、例が置かれているかと、その起動の形かの片方だけを見る。例が読めない
    （節が無い・ブロックが無い・JSON として読めない）ときは、どの観点でも同じ 1 件を返す。
    """
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]

    blocks = extract_json_blocks(section)
    if not blocks:
        return ["節に ```json のコードブロックが無い。"]

    diffs: list[str] = []
    try:
        document = json.loads(blocks[0])
    except json.JSONDecodeError as error:
        return [f"節の ```json のコードブロックが JSON として読めない: {error}"]

    servers = document.get("mcpServers", {})
    if "example_present" in aspects and "accord" not in servers:
        diffs.append("節の ```json のコードブロックに mcpServers.accord の項目が無い。")
    if "in_place" not in aspects:
        return diffs

    entry = servers.get("accord", {})
    command = entry.get("command")
    if command != "uv":
        diffs.append(f"mcpServers.accord.command が「{command}」で、「uv」ではない。")
    args = entry.get("args", [])
    if list(args[:2]) != ["run", "--project"]:
        diffs.append(
            f"mcpServers.accord.args の先頭 2 つが {list(args[:2])} で、"
            "「run」「--project」ではない。"
        )
    return diffs


def diff_both_ways(readme_text: str, aspects: tuple[str, ...] = BOTH_WAYS_ASPECTS) -> list[str]:
    """2 通りの起動が、どちらも節に書かれているかを見る。aspects を絞ると片方だけを見る。"""
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]

    diffs: list[str] = []
    if "in_place" in aspects and not any(
        IN_PLACE_COMMAND in line for line in section.splitlines()
    ):
        diffs.append(f"節に「{IN_PLACE_COMMAND}」を含む行が無い（手元の木を動かす起動の案内）。")
    if "pinned" in aspects and not any(PINNED_COMMAND in line for line in section.splitlines()):
        diffs.append(f"節に「{PINNED_COMMAND}」を含む行が無い（版を固定する起動の案内）。")
    return diffs


def diff_uvx_warning(readme_text: str) -> list[str]:
    """版を固定する起動を書いているなら、版を上げないと古い版が動く注意書きがあるかを見る。"""
    section = extract_section(readme_text)
    if section is None:
        return [f"README に見出し「{SECTION_HEADING}」が無い。"]

    lines = section.splitlines()
    if not any(PINNED_COMMAND in line for line in lines):
        return []
    if any(all(word in line for word in VERSION_WARNING_WORDS) for line in lines):
        return []
    return [
        f"節に「{PINNED_COMMAND}」の起動があるのに、"
        f"{'」と「'.join(VERSION_WARNING_WORDS)}」をどちらも含む行が無い（罠の注意書きが無い）。"
    ]


# ---------------------------------------------------------------- テスト


def test_REQ_357_the_startup_section_shows_a_client_config() -> None:
    """節に、AI から呼ぶときの設定の例（`.mcp.json` の書き方）が置かれている。"""
    diffs = diff_mcp_example(_real_readme_text(), aspects=("example_present",))
    assert not diffs, "\n".join(diffs)


def test_REQ_358_the_client_config_runs_the_checkout_in_place() -> None:
    """設定の例の起動が、手元の木をその場で動かす `uv run --project` の形になっている。"""
    diffs = diff_mcp_example(_real_readme_text(), aspects=("in_place",))
    assert not diffs, "\n".join(diffs)


def test_REQ_359_the_startup_section_shows_the_in_place_way() -> None:
    """節に、指した場所のソースをそのまま動かす起動の書き方が置かれている。"""
    diffs = diff_both_ways(_real_readme_text(), aspects=("in_place",))
    assert not diffs, "\n".join(diffs)


def test_REQ_360_the_startup_section_shows_the_pinned_way() -> None:
    """節に、版を固定して入れて使う起動の書き方が置かれている。"""
    diffs = diff_both_ways(_real_readme_text(), aspects=("pinned",))
    assert not diffs, "\n".join(diffs)


def test_REQ_361_the_pinned_way_carries_the_version_warning() -> None:
    """版を固定する起動には、版を上げないと古い版が動き続けるという注意書きが付いている。"""
    diffs = diff_uvx_warning(_real_readme_text())
    assert not diffs, "\n".join(diffs)


def test_the_checker_catches_a_broken_section() -> None:
    """例の起動コマンドを `uvx` に戻した文面を渡すと、違いが 1 件以上返る。

    審判（diff_mcp_example）自体が壊れていないかを見る自己試験。壊し方が対象を見つけられず
    文面が変わらなかった場合は、審判の合否と切り分けるため、その時点でテストを落とす。
    """
    readme_text = _real_readme_text()
    target = '"command": "uv",'
    assert target in readme_text, "README に起動コマンドの行が無く、自己試験の対象を壊せない。"

    broken_text = readme_text.replace(target, '"command": "uvx",', 1)
    assert broken_text != readme_text, "起動コマンドの置き換えが効かず、文面が変わらなかった。"

    diffs = diff_mcp_example(broken_text)
    assert diffs, "起動コマンドを壊しても、例の差分検査が違いを返さなかった（審判が効いていない）。"
