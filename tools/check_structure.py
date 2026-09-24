#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""置き場と定義の検査。accord の中のファイルの置き場と、設計文書の表と実物の一致を見る。

見るのは 5 項目で、どれも「実物がそうなっているか」だけを見る。実装の中身が正しいか、
設計の判断が妥当かは見ない。そこは人が読む。

  直下の置き場            `src/accord/` の直下が、層の 5 つのディレクトリと
                          3 つのファイルだけでできていること。
  入れ子の置き場          層の 5 つのディレクトリの中に、さらにディレクトリが無いこと。
  生成器の独立            `scripts/` の Python が `accord` を読み込まないこと。
  設定のモジュールの依存  `src/accord/vocabulary/` の Python が読み込むのが、
                          標準ライブラリと同じ層の中のモジュールだけであること。
  実装層の表と実物の一致  設計文書の実装層の表と、`src/accord/` の実物が食い違わないこと。

最後の項目が見る設計文書は、このリポジトリの外に置くことがある。パスを `--arch` で
渡したときだけ見て、渡されなければ省略する。ほかの 4 項目は引数なしで走る。

機械が作る置き場（`__pycache__`）と、名前が `.` で始まる置き場は、どの項目でも見ない。
実物ではなく生成物や道具の置き場で、置き場の決まりの対象ではないからである。

標準ライブラリだけを使い、`accord` パッケージを import しない。このリポジトリを外から
見るための道具で、中で動くコードとは依存を分けるためである。

使い方:
  python3 tools/check_structure.py [--root <リポジトリの直下>] [--arch <設計文書のパス>]

終了コード: 0（全項目合格）／1（不合格あり）／2（入力が読めない）
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path

CHECK_TITLE = "置き場と定義の検査"

# 結果の語。この 3 つ以外は使わない。
RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"
RESULT_SKIP = "SKIP"

# 読む場所。リポジトリの直下からの相対。
PACKAGE_DIR = "src/accord"
GENERATOR_DIR = "scripts"

# パッケージの名前と、設定を読むモジュールの層。
PACKAGE_NAME = "accord"
VOCABULARY_LAYER = "vocabulary"
VOCABULARY_MODULE = "%s.%s" % (PACKAGE_NAME, VOCABULARY_LAYER)

# `src/accord/` の直下に置いてよいもの。この 2 つの並びが置き場の決まりそのもので、
# 足すときは決めの記録を書いてからここを直す。
LAYER_DIRS = ("server", "services", "repository", "models", VOCABULARY_LAYER)
PACKAGE_FILES = ("__init__.py", "__main__.py", "ontology.yaml")

# 設計文書の中で、実装層の表を探す見出しと、表の見出しの行の 3 列。
ARCH_HEADING = "## 実装層"
ARCH_COLUMNS = ("モジュール", "ファイル", "主要な関数・クラス")

# 機械が作る置き場。実物ではないので、どの項目でも見ない。
IGNORED_DIR_NAMES = ("__pycache__",)

# 表の行を列に割る。`str \| None` のように escape した縦棒は区切りにしない。
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")

# 表の「主要な関数・クラス」の欄から名前を拾う規則。バッククォートで囲まれた部分の中から、
# 直後に `(` が来る識別子と、`class ` の直後の識別子だけを拾う。
BACKTICK_RE = re.compile(r"`([^`]*)`")
CALLABLE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")


class InputError(Exception):
    """検査の入力が読めない（終了コード 2）。項目の不合格（終了コード 1）と区別する。"""


# ---------------------------------------------------------------------------
# 入力の読み込み
# ---------------------------------------------------------------------------


def is_ignored(parts):
    """置き場の並びに、機械が作る置き場か `.` で始まる置き場が混ざっているか。"""
    return any(part in IGNORED_DIR_NAMES or part.startswith(".") for part in parts)


def iter_python(directory):
    """そのディレクトリの下の `*.py` を、機械が作る置き場を除いて集める。"""
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.rglob("*.py")):
        if is_ignored(path.relative_to(directory).parts[:-1]):
            continue
        found.append(path)
    return found


def as_written(target):
    """引数で渡された相対のパスを、書いたとおりの場所に着くパスにする。

    symlink をたどってこのリポジトリに入ったときは、`cd` した先で `../…` と書いても、
    `..` が実体の側から数えられて、書いた場所に着かない。そのまま開けないときだけ、
    シェルが持っている見かけ上の居場所（環境変数 PWD）から辿り直す。`..` は文字の上で
    たたんでから開く（実体の側へ抜けさせないため）。
    """
    path = Path(target)
    if path.is_absolute() or path.exists():
        return path
    logical = os.environ.get("PWD")
    if not logical:
        return path
    candidate = Path(os.path.normpath(os.path.join(logical, target)))
    return candidate if candidate.exists() else path


def shown(path, root):
    """出力に出す場所の文字列。リポジトリの直下からの相対のパス。"""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def read_imports(path):
    """Python のファイルの読み込みを (モジュール名, 相対の深さ, 行番号) の並びで返す。

    `import accord` と `from accord import …` のどちらの書き方も、同じ並びに入る。
    文として読めないファイルは SyntaxError をそのまま投げ、呼んだ側が不合格の行にする。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, 0, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level, node.lineno))
    return found


def collect_imports(paths, root):
    """並びの全ファイルの読み込みを集める。読めなかったファイルは直し方の行にして返す。"""
    imports = {}
    broken = []
    for path in paths:
        try:
            imports[path] = read_imports(path)
        except (OSError, SyntaxError, ValueError) as exc:
            broken.append(
                "`%s` が Python として読めない（%s）。文法の誤りを直す" % (shown(path, root), exc)
            )
    return imports, broken


def defined_names(path):
    """Python のファイルの中で宣言されている関数とクラスの名前を集める（入れ子も含む）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def table_cells(line):
    """表の 1 行を列に割る。行頭と行末の縦棒は落とす。"""
    parts = CELL_SPLIT_RE.split(line.strip())
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [part.strip() for part in parts]


def is_separator(cells):
    """表の見出しと中身を分ける区切りの行か。"""
    return bool(cells) and all(SEPARATOR_CELL_RE.match(cell) for cell in cells)


def cell_path(cell):
    """「ファイル」の欄から、リポジトリの直下からの相対のパスを取り出す。"""
    found = BACKTICK_RE.search(cell)
    return (found.group(1) if found else cell).strip()


def cell_names(cell):
    """「主要な関数・クラス」の欄から、確かめる名前を拾う。"""
    names = []
    for span in BACKTICK_RE.findall(cell):
        for name in CLASS_RE.findall(span):
            if name not in names:
                names.append(name)
        for name in CALLABLE_RE.findall(span):
            if name not in names:
                names.append(name)
    return names


def parse_arch_table(text):
    """設計文書から実装層の表を取り出して (見出しの列, 中身の行の並び) を返す。

    見出しが無ければ (None, []) を、表が無ければ ([], []) を返す。呼んだ側が不合格にする。
    """
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().startswith(ARCH_HEADING):
            start = index
            break
    if start is None:
        return None, []

    header = []
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("## ") or line.startswith("# "):
            break
        if not line.lstrip().startswith("|"):
            continue
        cells = table_cells(line)
        if is_separator(cells):
            continue
        if not header:
            header = cells
            continue
        rows.append(cells)
    return header, rows


def load_state(root, arch):
    """検査対象を読んで、項目の関数に渡す状態を作る。"""
    root_path = as_written(root)
    if not root_path.is_dir():
        raise InputError("リポジトリの直下が見つからない: %s" % root)

    package = root_path / PACKAGE_DIR
    if not package.is_dir():
        raise InputError("パッケージの置き場が見つからない: %s" % (root_path / PACKAGE_DIR))

    package_dirs = []
    package_files = []
    for entry in sorted(package.iterdir()):
        if entry.name in IGNORED_DIR_NAMES or entry.name.startswith("."):
            continue
        if entry.is_dir():
            package_dirs.append(entry.name)
        else:
            package_files.append(entry.name)

    nested = []
    for layer in package_dirs:
        layer_path = package / layer
        for entry in sorted(layer_path.rglob("*")):
            if not entry.is_dir():
                continue
            if is_ignored(entry.relative_to(layer_path).parts):
                continue
            nested.append(entry)

    generator_py = iter_python(root_path / GENERATOR_DIR)
    vocabulary_py = iter_python(package / VOCABULARY_LAYER)
    generator_imports, generator_broken = collect_imports(generator_py, root_path)
    vocabulary_imports, vocabulary_broken = collect_imports(vocabulary_py, root_path)

    arch_text = None
    arch_path = None
    if arch is not None:
        arch_path = as_written(arch)
        if not arch_path.is_file():
            raise InputError("設計文書が見つからない: %s" % arch)
        try:
            arch_text = arch_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise InputError("設計文書が読めない: %s（%s）" % (arch, exc))

    return {
        "root": root_path,
        "package": package,
        "package_dirs": package_dirs,
        "package_files": package_files,
        "nested": nested,
        "package_py": iter_python(package),
        "generator_imports": generator_imports,
        "generator_broken": generator_broken,
        "vocabulary_imports": vocabulary_imports,
        "vocabulary_broken": vocabulary_broken,
        "arch_path": arch_path,
        "arch_text": arch_text,
    }


# ---------------------------------------------------------------------------
# 項目の関数
#
# 引数は load_state が作った状態、返り値は (結果, 詳細, 直し方の行) の 3 つ組。
# 直し方の行は 1 件 1 行で、どのファイルを何に合わせるかを、この検査のコードを
# 開かずに読める文にする。
# ---------------------------------------------------------------------------


def check_package_layout(state):
    """`src/accord/` の直下が、層の 5 つと決まった 3 ファイルだけでできているか。"""
    lines = []
    for name in sorted(set(state["package_dirs"]) - set(LAYER_DIRS)):
        lines.append(
            "`%s/%s/` は層に無い置き場である。中身を層の 5 つ（%s）のどれかへ移すか、"
            "層を増やす決めの記録を書いてから tools/check_structure.py の LAYER_DIRS に足す"
            % (PACKAGE_DIR, name, "・".join(LAYER_DIRS))
        )
    for name in sorted(set(LAYER_DIRS) - set(state["package_dirs"])):
        lines.append(
            "層の置き場 `%s/%s/` が無い。作り直すか、層を減らす決めの記録を書いてから"
            " tools/check_structure.py の LAYER_DIRS から外す" % (PACKAGE_DIR, name)
        )
    for name in sorted(set(state["package_files"]) - set(PACKAGE_FILES)):
        lines.append(
            "`%s/%s` は直下に置けるファイルではない。層のどれかの中へ移すか、"
            "決めの記録を書いてから tools/check_structure.py の PACKAGE_FILES に足す"
            % (PACKAGE_DIR, name)
        )
    for name in sorted(set(PACKAGE_FILES) - set(state["package_files"])):
        lines.append("直下にあるはずの `%s/%s` が無い。戻す" % (PACKAGE_DIR, name))

    if lines:
        return RESULT_FAIL, "直下の食い違い %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "直下は層の %d 置き場とファイル %d 件だけ" % (len(LAYER_DIRS), len(PACKAGE_FILES)),
        [],
    )


def check_nested_layout(state):
    """層のディレクトリの中に、さらにディレクトリが無いか。"""
    lines = []
    for entry in state["nested"]:
        lines.append(
            "`%s/` は層のディレクトリの中の置き場である。中のファイルを層の直下へ移して"
            "この置き場を消す（層の中は 1 段だけにする）" % shown(entry, state["root"])
        )
    if lines:
        return RESULT_FAIL, "層の中の入れ子の置き場 %d 件" % len(lines), lines
    return RESULT_PASS, "層の %d 置き場は、どれも中に置き場を持たない" % len(state["package_dirs"]), []


def check_generator_independence(state):
    """`scripts/` の Python が `accord` を読み込んでいないか。"""
    lines = list(state["generator_broken"])
    for path, imports in sorted(state["generator_imports"].items()):
        for module, level, lineno in imports:
            if level:
                continue
            if module != PACKAGE_NAME and not module.startswith(PACKAGE_NAME + "."):
                continue
            lines.append(
                "`%s` の %d 行目が `%s` を読み込んでいる。生成器は正本の YAML を読んで"
                "書き出すだけの道具なので、読み込みを消して同じ処理をその場に書く"
                % (shown(path, state["root"]), lineno, module)
            )
    if lines:
        return RESULT_FAIL, "生成器からの読み込み %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "`%s/` の Python %d 本は、どれも `%s` を読み込まない"
        % (GENERATOR_DIR, len(state["generator_imports"]), PACKAGE_NAME),
        [],
    )


def check_vocabulary_dependencies(state):
    """設定を読むモジュールが、標準ライブラリと同じ層の中だけを読んでいるか。"""
    layer_dir = "%s/%s/" % (PACKAGE_DIR, VOCABULARY_LAYER)
    advice = (
        "設定を読むモジュールが読んでよいのは、標準ライブラリと `%s` の中のモジュールだけ"
        "である（読み込みを消すか、その処理を上の層へ移す）" % layer_dir
    )
    lines = list(state["vocabulary_broken"])
    for path, imports in sorted(state["vocabulary_imports"].items()):
        for module, level, lineno in imports:
            where = "`%s` の %d 行目" % (shown(path, state["root"]), lineno)
            if level:
                if level == 1:
                    continue
                lines.append(
                    "%s が %d 段上の `%s` を読み込んでいる。%s"
                    % (where, level, module or "（同じ並びの全体）", advice)
                )
                continue
            if module == VOCABULARY_MODULE or module.startswith(VOCABULARY_MODULE + "."):
                continue
            if module.split(".")[0] in sys.stdlib_module_names:
                continue
            lines.append("%s が `%s` を読み込んでいる。%s" % (where, module, advice))

    if lines:
        return RESULT_FAIL, "層の外への読み込み %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "`%s` の Python %d 本は、標準ライブラリと同じ層の中だけを読む"
        % (layer_dir, len(state["vocabulary_imports"])),
        [],
    )


def check_arch_table(state):
    """設計文書の実装層の表と、`src/accord/` の実物が食い違っていないか。"""
    if state["arch_text"] is None:
        return (
            RESULT_SKIP,
            "設計文書を渡していないので見ない（`--arch <設計文書のパス>` を付けると見る）",
            [],
        )

    arch_shown = str(state["arch_path"])
    header, rows = parse_arch_table(state["arch_text"])
    if header is None:
        return (
            RESULT_FAIL,
            "実装層の見出しが無い",
            ["`%s` に「%s」の見出しを置き、その下に 3 列の表を書く" % (arch_shown, ARCH_HEADING)],
        )
    if tuple(header[:3]) != ARCH_COLUMNS:
        return (
            RESULT_FAIL,
            "表の見出しの行が違う",
            [
                "`%s` の実装層の表の見出しを「%s」の 3 列にする（いまは「%s」）"
                % (arch_shown, "｜".join(ARCH_COLUMNS), "｜".join(header) if header else "表そのものが無い")
            ],
        )

    lines = []
    listed = []
    name_count = 0
    for cells in rows:
        if len(cells) < 3:
            lines.append(
                "`%s` の実装層の表に、列の足りない行がある（%s）。3 列に直す"
                % (arch_shown, "｜".join(cells) or "空の行")
            )
            continue
        relative = cell_path(cells[1])
        listed.append(relative)
        target = state["root"] / relative
        if not target.is_file():
            lines.append(
                "`%s` の実装層の表が `%s` を挙げているが、実物が無い。表の行を消すか、"
                "そのファイルを作る" % (arch_shown, relative)
            )
            continue
        if not relative.endswith(".py"):
            continue
        try:
            have = defined_names(target)
        except (OSError, SyntaxError, ValueError) as exc:
            lines.append("`%s` が Python として読めない（%s）。文法の誤りを直す" % (relative, exc))
            continue
        for name in cell_names(cells[2]):
            name_count += 1
            if name not in have:
                lines.append(
                    "`%s` の実装層の表が `%s` に `%s` を挙げているが、そのファイルに無い。"
                    "表の名前を実物に合わせるか、その行から消す" % (arch_shown, relative, name)
                )

    listed_set = set(listed)
    for path in state["package_py"]:
        relative = shown(path, state["root"])
        if relative not in listed_set:
            lines.append(
                "`%s` が `%s` の実装層の表に無い。表に 1 行足す（モジュール名・このパス・"
                "主要な関数とクラス）" % (relative, arch_shown)
            )

    if lines:
        return RESULT_FAIL, "表と実物の食い違い %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "表の行 %d 件・`%s` の Python %d 本・名前 %d 件が実物と一致"
        % (len(rows), PACKAGE_DIR, len(state["package_py"]), name_count),
        [],
    )


# 検査項目の表。読み手に向けて項目番号を使わず、この項目名で呼ぶ。
CHECKS = [
    ("直下の置き場", check_package_layout),
    ("入れ子の置き場", check_nested_layout),
    ("生成器の独立", check_generator_independence),
    ("設定のモジュールの依存", check_vocabulary_dependencies),
    ("実装層の表と実物の一致", check_arch_table),
]


# ---------------------------------------------------------------------------
# 骨組み
# ---------------------------------------------------------------------------


def evaluate(state):
    """全項目を走らせて [(項目名, 結果, 詳細, 直し方の行), …] を返す。

    出力と分けてあるので、ほかのスクリプトから import して判定だけを使える。
    項目の関数が例外を投げたときは、その項目だけ不合格にして詳細を
    「項目の実行中に例外:」で始める（検査全体は落とさない）。入力そのものが読めない
    終了コード 2 とは別の経路である。
    """
    results = []
    for name, check in CHECKS:
        try:
            result, detail, lines = check(state)
        except Exception as exc:  # noqa: BLE001 — 項目の不具合は不合格の側で扱う（決め: 0010）
            result, detail, lines = RESULT_FAIL, "項目の実行中に例外: %r" % (exc,), []
        results.append((name, result, detail, lines))
    return results


def run(root, arch):
    """検査を 1 回走らせて終了コードを返す。"""
    try:
        state = load_state(root, arch)
    except InputError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    print("# %s（対象: %s）" % (CHECK_TITLE, root))
    counts = {RESULT_PASS: 0, RESULT_FAIL: 0, RESULT_SKIP: 0}
    for name, result, detail, lines in evaluate(state):
        print("%s %s: %s" % (result, name, detail))
        counts[result] = counts.get(result, 0) + 1
        if result == RESULT_FAIL:
            for line in lines:
                print("    %s" % line)

    print(
        "合格 %d 件・不合格 %d 件・省略 %d 件"
        % (counts[RESULT_PASS], counts[RESULT_FAIL], counts[RESULT_SKIP])
    )
    return 1 if counts[RESULT_FAIL] else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="%s。項目ごとに PASS・FAIL・SKIP を 1 行ずつ出し、"
        "不合格の項目の下に直し方を 1 件 1 行で出す。" % CHECK_TITLE,
        epilog="終了コード: 0（全項目合格）／1（不合格あり）／2（入力が読めない）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="リポジトリの直下（既定: この検査の 1 つ上のディレクトリ）",
    )
    parser.add_argument(
        "--arch",
        default=None,
        help="実装層の表を持つ設計文書のパス（渡さなければ、表を見る項目を省略する）",
    )
    args = parser.parse_args(argv)
    return run(args.root, args.arch)


if __name__ == "__main__":
    sys.exit(main())
