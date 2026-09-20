#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""置き場と定義の検査の自己試験（審判が本当に落ちるかを試す）。

見るのは「検査が合格を出せるか」ではなく「わざと壊した木で本当に不合格を返すか」である。
落ちない審判は審判ではないので、壊し方を項目ごとに置く。

一時の置き場に小さな木（`src/accord/` の 5 層と `scripts/` と設計文書）を組み立て、
整った木では全項目が合格すること、壊し方 6 通りではそれぞれの項目が落ちることを確かめる。
見本は別ファイルにせず、この中に文字列で持つ（見本を別に置くと、検査の改訂と見本の同期が
切れる）。カレントディレクトリや外側の git の状態には依存しない。

標準ライブラリだけを使う（検査本体と同じ理由で、`accord` パッケージを import しない）。

使い方:
  python3 tools/check_structure_selftest.py

終了コード: 0（全ケースが期待どおり）／1（食い違いが 1 件以上）
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHECK_SCRIPT = SCRIPT_DIR / "check_structure.py"

# 見本の木の中の、設計文書の置き場。
ARCH_RELATIVE = "docs/design/architecture.md"


# ---------------------------------------------------------------------------
# 見本の木（整った状態）
#
# 中身は形を確かめるための最小のもので、accord の実物とは別である。人の名前や案件の名前は
# 一切置かない（この検査は公開リポジトリの中にある）。
# ---------------------------------------------------------------------------

ARCH_DOCUMENT = """\
# 見本のアーキテクチャ定義書

## 概念層

見本の木は 5 つの層でできている。

## 実装層

| モジュール | ファイル | 主要な関数・クラス |
|---|---|---|
| server | `src/accord/__init__.py` | （パッケージの宣言だけ） |
| server | `src/accord/__main__.py` | `main(argv: list[str]) -> int` |
| server | `src/accord/server/__init__.py` | （層の宣言だけ） |
| server | `src/accord/server/app.py` | `create_server(settings: Settings) -> MCPServer` |
| services | `src/accord/services/__init__.py` | （層の宣言だけ） |
| services | `src/accord/services/positioning.py` | `class PositioningService: def record(self, draft) -> WriteResult` |
| repository | `src/accord/repository/__init__.py` | （層の宣言だけ） |
| repository | `src/accord/repository/sections.py` | `split_sections(text: str) -> list[Section]` |
| models | `src/accord/models/__init__.py` | （層の宣言だけ） |
| models | `src/accord/models/types.py` | `Positioning`（生成物） |
| models | `src/accord/ontology.yaml` | 型 1 つの正本（Python ではないので名前は見ない） |
| vocabulary | `src/accord/vocabulary/__init__.py` | （層の宣言だけ） |
| vocabulary | `src/accord/vocabulary/settings.py` | `load_settings(path: Path \\| None) -> Settings` |

## 依存の向き

上から下へだけ読む。
"""

GOOD_TREE = {
    "src/accord/__init__.py": '"""見本のパッケージ。"""\n',
    "src/accord/__main__.py": "def main(argv):\n    return 0\n",
    "src/accord/ontology.yaml": "types: []\n",
    "src/accord/server/__init__.py": "",
    "src/accord/server/app.py": "def create_server(settings):\n    return settings\n",
    "src/accord/services/__init__.py": "",
    "src/accord/services/positioning.py": (
        "class PositioningService:\n"
        "    def record(self, draft):\n"
        "        return draft\n"
    ),
    "src/accord/repository/__init__.py": "",
    "src/accord/repository/sections.py": "def split_sections(text):\n    return []\n",
    "src/accord/models/__init__.py": "",
    "src/accord/models/types.py": "class Positioning:\n    pass\n",
    "src/accord/vocabulary/__init__.py": "",
    "src/accord/vocabulary/settings.py": (
        "import tomllib\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def load_settings(path):\n"
        "    return Path(path), tomllib\n"
    ),
    "scripts/generate_models.py": (
        "import argparse\n"
        "\n"
        "\n"
        "def main(argv):\n"
        "    return argparse.ArgumentParser().parse_args(argv)\n"
    ),
    ARCH_RELATIVE: ARCH_DOCUMENT,
}


# ---------------------------------------------------------------------------
# 補助（木を組み立てる・検査本体を別プロセスで起動する）
# ---------------------------------------------------------------------------


def build_tree(root):
    """見本の木を組み立てて、その直下のパスを返す。"""
    for relative, text in GOOD_TREE.items():
        path = Path(root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Path(root)


def snapshot(root):
    """木の中身を「相対のパス → 中身（ディレクトリは None）」で写し取る。"""
    taken = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            taken[relative] = None
        else:
            taken[relative] = path.read_text(encoding="utf-8")
    return taken


def run_check(root, extra_args=()):
    """検査本体を subprocess で起動し、(終了コード, 出力) を返す。

    import して関数を呼ぶのではなく別プロセスで起動するのは、終了コードと標準出力という
    「呼ぶ側が実際に見るもの」をそのまま突き合わせるためである。
    """
    completed = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(root), *extra_args],
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout + completed.stderr


def arch_args(root):
    """設計文書を渡す引数。"""
    return ["--arch", str(Path(root) / ARCH_RELATIVE)]


# ケースの表。(ケース名, 木を組み立てるか, 引数を作る関数, 期待の終了コード, 出力に必ず含まれる語)
CASES = [
    ("整った木は表の項目まで合格する", True, arch_args, 0, "PASS 実装層の表と実物の一致"),
    ("整った木は不合格を 1 件も出さない", True, arch_args, 0, "不合格 0 件"),
    ("設計文書を渡さなければ表の項目を省略する", True, lambda root: [], 0, "SKIP 実装層の表と実物の一致"),
    (
        "設計文書を渡さなくてもほかの項目は合格する",
        True,
        lambda root: [],
        0,
        "PASS 直下の置き場",
    ),
    (
        "リポジトリの直下が無ければ終了コード 2",
        False,
        lambda root: [],
        2,
        "リポジトリの直下が見つからない",
    ),
    (
        "設計文書のパスが指す先が無ければ終了コード 2",
        True,
        lambda root: ["--arch", str(Path(root) / "docs/design/no_such_file.md")],
        2,
        "設計文書が見つからない",
    ),
]


# ---------------------------------------------------------------------------
# 壊し方の一覧（1 ケースにつき 1 箇所だけ壊す）
# ---------------------------------------------------------------------------


def mutate_nested_directory(root):
    """層のディレクトリの中に、さらにディレクトリを作る。"""
    (root / "src/accord/services/nested").mkdir()


def mutate_extra_directory(root):
    """`src/accord/` の直下に、層でないディレクトリを作る。"""
    (root / "src/accord/helpers").mkdir()


def mutate_unlisted_python(root):
    """設計文書の表に無い Python を足す。"""
    (root / "src/accord/services/extra.py").write_text(
        "def extra():\n    return None\n", encoding="utf-8"
    )


def mutate_vocabulary_external(root):
    """設定を読むモジュールに、外部のパッケージの読み込みを足す。"""
    path = root / "src/accord/vocabulary/settings.py"
    path.write_text("import yaml\n" + path.read_text(encoding="utf-8"), encoding="utf-8")


def mutate_generator_import(root):
    """生成器に、accord の読み込みを足す。"""
    path = root / "scripts/generate_models.py"
    path.write_text(
        "from accord.models import types\n" + path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def mutate_drop_table_row(root):
    """設計文書の実装層の表から、実在するファイルの行を 1 つ消す。"""
    path = root / ARCH_RELATIVE
    kept = [
        line
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
        if "sections.py" not in line
    ]
    path.write_text("".join(kept), encoding="utf-8")


# (壊し方の名前, 木を壊す関数, 落ちるはずの項目名)
MUTATIONS = [
    ("層の中に入れ子のディレクトリを作る", mutate_nested_directory, "入れ子の置き場"),
    ("直下に層でないディレクトリを作る", mutate_extra_directory, "直下の置き場"),
    ("表に無い Python を足す", mutate_unlisted_python, "実装層の表と実物の一致"),
    ("設定のモジュールに外部のパッケージの読み込みを足す", mutate_vocabulary_external, "設定のモジュールの依存"),
    ("生成器に accord の読み込みを足す", mutate_generator_import, "生成器の独立"),
    ("表から 1 行消す", mutate_drop_table_row, "実装層の表と実物の一致"),
]


# ---------------------------------------------------------------------------
# 骨組み
# ---------------------------------------------------------------------------


def report(name, problems, output):
    """食い違いを 1 件出す。"""
    print("NG %s — %s" % (name, "、".join(problems)))
    print("--- 実際の出力 ---")
    print(output.rstrip())
    print("------------------")


def run_case(name, build, make_args, expected_code, expected_word):
    """1 ケースを走らせて、期待どおりなら True を返す。"""
    with tempfile.TemporaryDirectory() as work:
        if build:
            root = build_tree(work)
        else:
            root = Path(work) / "no_such_root"
        code, output = run_check(root, make_args(root))

    problems = []
    if code != expected_code:
        problems.append("終了コードが %d（期待 %d）" % (code, expected_code))
    if expected_word not in output:
        problems.append("出力に「%s」が無い" % expected_word)
    if problems:
        report(name, problems, output)
        return False
    print("OK %s" % name)
    return True


def run_mutation(name, mutate, expected_item):
    """1 つの壊し方を整った木に当てて、終了コード 1 と、期待した項目名の不合格の行が出ることを
    確かめる。壊し方が木を変えなければ「効いていない」として食い違いに数える。"""
    with tempfile.TemporaryDirectory() as work:
        root = build_tree(work)
        before = snapshot(root)
        mutate(root)
        after = snapshot(root)
        if before == after:
            print("NG 壊し方「%s」— 壊し方が効いていない（木が変わらない）" % name)
            return False
        code, output = run_check(root, arch_args(root))

    problems = []
    if code != 1:
        problems.append("終了コードが %d（期待 1）" % code)
    fail_line = "FAIL %s" % expected_item
    if fail_line not in output:
        problems.append("出力に「%s」が無い" % fail_line)
    if problems:
        report("壊し方「%s」" % name, problems, output)
        return False
    print("OK 壊し方「%s」（%s が不合格）" % (name, expected_item))
    return True


def main():
    if not CHECK_SCRIPT.is_file():
        print("ERROR: 検査本体が見つからない: %s" % CHECK_SCRIPT, file=sys.stderr)
        return 1
    failures = 0
    for case in CASES:
        if not run_case(*case):
            failures += 1
    for name, mutate, expected_item in MUTATIONS:
        if not run_mutation(name, mutate, expected_item):
            failures += 1
    print("ケース %d 件・壊し方 %d 件・食い違い %d 件" % (len(CASES), len(MUTATIONS), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
