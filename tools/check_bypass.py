#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""検査を黙らせる印と、印を持たない迂回の一部を見る検査。

見るのは 4 項目で、どれも「実物がそうなっているか」だけを見る。印を置いた判断が
妥当かどうかは見ない。そこは決めの記録を読む人が判断する。

  迂回の印に決めの記録がある    lint の咎めを黙らせる注記、テストを飛ばす印、層の契約の
                                例外、CI の失敗を無かったことにする書き方などの印を持つ行が、
                                同じ行に「決め: NNNN」（4 桁）を持つこと。
  決めの記録が印を名指しする    その番号の記録が `docs/decisions/NNNN-*.md` に実在し、
                                本文の 1 つの行に、行のファイルのパス（リポジトリの直下からの
                                相対）と印の文字列を両方持つこと。別々の行にあるだけでは
                                通さない。
  層の契約が緩んでいない        `.importlinter` の契約の名前の顔ぶれが、この検査の持つ期待と
                                一致し、層の契約が網羅（exhaustive = true）を持つこと。
  再エクスポートが無い          `src/accord/` の下の `__init__.py` に、行頭が import か
                                from の行が無いこと。

印を探すのは、git が追跡するファイルのうち、`.py`・`.importlinter`・`pyproject.toml`・
`.github/workflows/*.yml` である。差分ではなく木全体を見る。差分の起点は CI とコミット前で
ぶれるうえ、差分では前からある印を見られないためである。

印の一覧と契約の期待は、下の MARKERS と EXPECTED_CONTRACTS に持つ。同じものを決めの記録
`docs/decisions/0010-record-every-check-bypass.md` に書き、両者の一致は自己試験が見る。
印を足すか外すときは、先に決めの記録を直してからここを直す。

この検査自身と自己試験も、印を探す対象に入る（ファイルの単位の例外は置かない）。
そのため印の文字列は、ソースの上で印に当たらないよう分割して組み立てる。

標準ライブラリだけを使い、`accord` パッケージを import しない。

使い方:
  python3 tools/check_bypass.py [--root <リポジトリの直下>]

終了コード: 0（全項目合格）／1（不合格あり）／2（入力が読めない）
"""

import argparse
import configparser
import os
import re
import subprocess
import sys
from pathlib import Path

CHECK_TITLE = "迂回の検査"

# 結果の語。この 3 つ以外は使わない。
RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"
RESULT_SKIP = "SKIP"

# 読む場所。リポジトリの直下からの相対。
DECISIONS_DIR = "docs/decisions"
CONTRACT_FILE = ".importlinter"
PYPROJECT_FILE = "pyproject.toml"
WORKFLOWS_DIR = ".github/workflows"
PACKAGE_DIR = "src/accord"
IGNORED_DIR_NAMES = ("__pycache__",)

# 行に書く決めの記録の番号。桁は 4 で、決めの記録のファイル名の頭と同じ。
DECISION_RE = re.compile(r"決め:\s*(\d+)")
DECISION_WIDTH = 4

# ---------------------------------------------------------------------------
# 迂回の印
#
# (印の名前, 見つける正規表現) の並び。印の名前は決めの記録の一覧に書く形で、出力にも出る。
# どれも、ソースの上で自分に当たらないよう、文字列を 2 つ以上に割って組み立てる。
# 決めの記録が持つべき「印の文字列」は、行の中で正規表現が当たった部分そのもの
# （lint の注記なら、後ろに付けた規則の名前まで含む）。
# ---------------------------------------------------------------------------

_PY = "py" + "test"
_LINT_CODES = r"(?::\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)?"
_TYPE_CODES = r"(?:\[[^\]]*\])?"

MARKERS = [
    ("# " + "no" + "qa", re.compile(r"#\s*" + "no" + "qa" + _LINT_CODES, re.IGNORECASE)),
    (
        "# type" + ": ignore",
        re.compile(r"#\s*type:\s*" + "ign" + "ore" + _TYPE_CODES, re.IGNORECASE),
    ),
    (
        "# pragma" + ": no cover",
        re.compile(r"#\s*pragma:\s*no\s*" + "co" + "ver", re.IGNORECASE),
    ),
    # 「skip」は「skipif」の頭でもあるので、後ろに if が続かないときだけ当てる。
    (_PY + ".mark." + "skip", re.compile(re.escape(_PY + ".mark." + "skip") + "(?!if)")),
    (_PY + ".mark." + "skipif", re.compile(re.escape(_PY + ".mark." + "skipif"))),
    (_PY + ".mark." + "xfail", re.compile(re.escape(_PY + ".mark." + "xfail"))),
    (_PY + "." + "skip(", re.compile(re.escape(_PY + "." + "skip("))),
    (_PY + "." + "xfail(", re.compile(re.escape(_PY + "." + "xfail("))),
    (_PY + "." + "importorskip(", re.compile(re.escape(_PY + "." + "importorskip("))),
    ("ignore" + "_imports", re.compile(re.escape("ignore" + "_imports"))),
    ("allow_indirect" + "_imports", re.compile(re.escape("allow_indirect" + "_imports"))),
    ("continue-on" + "-error", re.compile(re.escape("continue-on" + "-error"))),
    ("||" + " true", re.compile(r"\|\|\s*" + "tr" + r"ue\b")),
    ("--" + "deselect", re.compile(re.escape("--" + "deselect"))),
    ("--" + "ignore", re.compile(re.escape("--" + "ignore"))),
    ("-p" + " no:", re.compile(r"-p\s+" + "no:")),
]

# ---------------------------------------------------------------------------
# 層の契約の期待
#
# `.importlinter` の契約の名前の顔ぶれ。契約を消す・名前を変える・足すと、ここと食い違う。
# 網羅（exhaustive）を持つべき契約は、並びの先頭の 1 本。
# ---------------------------------------------------------------------------

EXPECTED_CONTRACTS = (
    "層は上から下へだけ読む",
    "設定を読むモジュールは外部のパッケージを読まない",
)
EXHAUSTIVE_CONTRACT = EXPECTED_CONTRACTS[0]
CONTRACT_SECTION_PREFIX = "importlinter:contract:"

# 再エクスポートの見分け方。行頭（字下げは許す）が import か from の行。
REEXPORT_RE = re.compile(r"^\s*(import|from)\s+\S")


class InputError(Exception):
    """検査の入力が読めない（終了コード 2）。項目の不合格（終了コード 1）と区別する。"""


# ---------------------------------------------------------------------------
# 入力の読み込み
# ---------------------------------------------------------------------------


def read_lines(path):
    """1 ファイルを読んで行の一覧を返す。読めなければ入力の側の誤りとして投げる。"""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError("読めない: %s（%s）" % (path, exc))


def is_scanned(relative):
    """印を探す対象のファイルか。relative はリポジトリの直下からの相対（`/` 区切り）。"""
    if relative.endswith(".py"):
        return True
    if relative in (CONTRACT_FILE, PYPROJECT_FILE):
        return True
    parent, _, name = relative.rpartition("/")
    return parent == WORKFLOWS_DIR and name.endswith(".yml")


def tracked_files(root):
    """git が追跡するファイルの一覧（直下からの相対）を返す。

    呼んだ側が git の hook の中にいると、git の置き場を指す環境変数が別のリポジトリを
    指していることがある。`-C` で渡した直下の git だけを読むよう、その 3 つを外して呼ぶ。
    """
    env = dict(os.environ)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(name, None)
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            env=env,
        )
    except OSError as exc:
        raise InputError("git を起動できない（%s）" % exc)
    if completed.returncode != 0:
        raise InputError(
            "git が追跡するファイルを読めない: %s（%s）"
            % (root, completed.stderr.decode("utf-8", "replace").strip())
        )
    names = completed.stdout.decode("utf-8", "replace").split("\0")
    return sorted(name for name in names if name)


def find_markers(line):
    """1 行から印を探して [(印の名前, 当たった文字列), …] を返す。

    ほかの印の当たりにすっぽり含まれる当たりは数えない（同じ場所を 2 度数えないため）。
    """
    hits = []
    for name, pattern in MARKERS:
        for found in pattern.finditer(line):
            hits.append((found.start(), found.end(), name, found.group(0)))
    kept = []
    for start, end, name, text in hits:
        covered = any(
            (s <= start and end <= e) and (s, e) != (start, end)
            for s, e, _, _ in hits
        )
        if not covered:
            kept.append((start, name, text))
    kept.sort()
    return [(name, text) for _, name, text in kept]


def collect_hits(root, files):
    """追跡するファイルの中の、印を持つ行を集める。"""
    hits = []
    for relative in files:
        if not is_scanned(relative):
            continue
        path = root / relative
        if not path.is_file():
            # 追跡しているが作業ツリーから消したファイル。読む中身が無い。
            continue
        for line_number, line in enumerate(read_lines(path), 1):
            for name, text in find_markers(line):
                found = DECISION_RE.search(line)
                hits.append(
                    {
                        "path": relative,
                        "line": line_number,
                        "marker": name,
                        "text": text,
                        "decision": found.group(1) if found else None,
                    }
                )
    return hits


def read_contracts(root):
    """`.importlinter` の契約を並びどおりに読む。ファイルが無ければ None を返す。"""
    path = root / CONTRACT_FILE
    if not path.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string("\n".join(read_lines(path)) + "\n", source=str(path))
    except configparser.Error as exc:
        raise InputError("契約のファイルを読めない: %s（%s）" % (CONTRACT_FILE, exc))
    contracts = []
    for section in parser.sections():
        if not section.startswith(CONTRACT_SECTION_PREFIX):
            continue
        body = parser[section]
        contracts.append(
            {
                "section": section,
                "name": body.get("name"),
                "exhaustive": (body.get("exhaustive") or "").strip().lower(),
            }
        )
    return contracts


def collect_init_files(root):
    """`src/accord/` の下の `__init__.py` を集める。置き場が無ければ None を返す。"""
    package = root / PACKAGE_DIR
    if not package.is_dir():
        return None
    found = []
    for path in sorted(package.rglob("__init__.py")):
        if any(part in IGNORED_DIR_NAMES for part in path.relative_to(package).parts):
            continue
        found.append(path)
    return found


def load_state(root):
    """検査対象を読んで、項目の関数に渡す状態を作る。"""
    root = Path(root)
    if not root.is_dir():
        raise InputError("リポジトリの直下が見つからない: %s" % root)
    files = tracked_files(root)
    return {
        "root": root,
        "files": files,
        "scanned": [f for f in files if is_scanned(f)],
        "hits": collect_hits(root, files),
        "contracts": read_contracts(root),
        "inits": collect_init_files(root),
    }


def decision_files(root, number):
    """番号の決めの記録のファイルを返す。無ければ空の一覧。"""
    directory = root / DECISIONS_DIR
    if not directory.is_dir():
        return []
    return sorted(directory.glob("%s-*.md" % number))


# 記録の行の中で、印の文字列の直後に来てはいけない文字。規則の名前の続き（`:`・英数字・
# `_`）、型の注記の規則の括弧（`[`）、オプションの名前の続き（`-`）である。
_CONTINUES_RE = re.compile(r"[:\[\-A-Za-z0-9_]")


def names_text(line, text):
    """記録の 1 行が、印の文字列をそこで切れる形で持つか。

    規則の名前を持たない lint の注記は、行の咎めを全部黙らせる。記録が規則の名前つきの
    注記だけを書いているのに、その頭の文字列として一致を取ると、全部を黙らせる注記まで
    許してしまう。そのため、文字列の直後が行末か、続きにならない文字のときだけ一致とする。
    """
    start = line.find(text)
    while start >= 0:
        after = line[start + len(text):start + len(text) + 1]
        if not after or not _CONTINUES_RE.match(after):
            return True
        start = line.find(text, start + 1)
    return False


def shown_marker(hit):
    return "%s:%d 印「%s」" % (hit["path"], hit["line"], hit["text"])


# ---------------------------------------------------------------------------
# 項目の関数
#
# 引数は load_state が作った状態、返り値は (結果, 詳細, 直し方の行) の 3 つ組。
# 直し方の行は不合格のときだけ使い、1 件 1 行で「場所・印・次にすること」を書く。
# ---------------------------------------------------------------------------


def check_markers_have_decisions(state):
    """印を持つ行が、同じ行に 4 桁の決めの記録の番号を持つか。"""
    lines = []
    for hit in state["hits"]:
        number = hit["decision"]
        if number is None:
            lines.append(
                "%s: 同じ行に番号が無い。印を外して本来の直し方をとるか、"
                "%s/ に決めの記録を書いて、この行に「決め: NNNN」を足す" % (shown_marker(hit), DECISIONS_DIR)
            )
        elif len(number) != DECISION_WIDTH:
            lines.append(
                "%s: 番号「%s」は %d 桁ではない。決めの記録のファイル名の頭と同じ %d 桁で書く"
                % (shown_marker(hit), number, DECISION_WIDTH, DECISION_WIDTH)
            )
    if lines:
        return RESULT_FAIL, "番号の無い印 %d 件（印のある行 %d 件のうち）" % (len(lines), len(state["hits"])), lines
    return (
        RESULT_PASS,
        "追跡するファイル %d 件のうち対象 %d 件を読み、印のある %d 件すべてが決めの記録の番号を持つ"
        % (len(state["files"]), len(state["scanned"]), len(state["hits"])),
        [],
    )


def check_decisions_name_markers(state):
    """番号の決めの記録が実在し、行のファイルのパスと印の文字列を両方持つか。"""
    lines = []
    looked = 0
    for hit in state["hits"]:
        number = hit["decision"]
        if number is None or len(number) != DECISION_WIDTH:
            continue
        looked += 1
        records = decision_files(state["root"], number)
        if not records:
            lines.append(
                "%s: 決めの記録 %s/%s-*.md が無い。記録を書くか、実在する番号に直す"
                % (shown_marker(hit), DECISIONS_DIR, number)
            )
            continue
        # パスと印の文字列は、記録の同じ 1 行に両方そろっていなければならない。別々の行に
        # あるだけで通すと、印の一覧やパスの説明を持つ記録が、そのファイルのほかの印まで
        # 許してしまうためである。
        record_lines = [line for record in records for line in read_lines(record)]
        if any(hit["path"] in line and names_text(line, hit["text"]) for line in record_lines):
            continue
        has_path = any(hit["path"] in line for line in record_lines)
        has_text = any(names_text(line, hit["text"]) for line in record_lines)
        missing = []
        if not has_path:
            missing.append("ファイルのパス「%s」" % hit["path"])
        if not has_text:
            missing.append("印の文字列「%s」" % hit["text"])
        if missing:
            what = "%s を書いていない" % "と".join(missing)
        else:
            what = (
                "ファイルのパス「%s」と印の文字列「%s」を別々の行にしか書いていない"
                % (hit["path"], hit["text"])
            )
        lines.append(
            "%s: 決めの記録 %s が %s。記録の本文の 1 つの行に、"
            "このパスと印の文字列を並べて書き、同じ行に印が黙らせているものと許す理由を書く"
            % (
                shown_marker(hit),
                records[0].relative_to(state["root"]).as_posix(),
                what,
            )
        )
    if lines:
        return RESULT_FAIL, "記録が名指ししていない印 %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "番号を持つ印 %d 件すべてを、記録が 1 つの行でパスと印の文字列を並べて名指ししている" % looked,
        [],
    )


def check_contracts_intact(state):
    """層の契約の名前の顔ぶれが期待と一致し、層の契約が網羅を持つか。"""
    contracts = state["contracts"]
    if contracts is None:
        return (
            RESULT_FAIL,
            "契約のファイルが無い",
            ["%s: ファイルが無い。層の依存の契約を消さずに戻す" % CONTRACT_FILE],
        )
    names = [c["name"] for c in contracts]
    lines = []
    for expected in EXPECTED_CONTRACTS:
        if expected not in names:
            lines.append(
                "%s: 契約「%s」が無い。契約を消したか名前を変えたなら戻す"
                "（契約を変えるなら、先に決めの記録を書いてからこの検査の期待を直す）"
                % (CONTRACT_FILE, expected)
            )
    for contract in contracts:
        if contract["name"] not in EXPECTED_CONTRACTS:
            lines.append(
                "%s の [%s]: 期待に無い契約「%s」。名前を戻すか、先に決めの記録を書いてから"
                "この検査の期待に足す" % (CONTRACT_FILE, contract["section"], contract["name"])
            )
    for contract in contracts:
        if contract["name"] == EXHAUSTIVE_CONTRACT and contract["exhaustive"] != "true":
            lines.append(
                "%s の [%s]: 契約「%s」に exhaustive = true が無い。網羅を戻す"
                % (CONTRACT_FILE, contract["section"], EXHAUSTIVE_CONTRACT)
            )
    if lines:
        return RESULT_FAIL, "契約の食い違い %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "契約 %d 本の名前が期待どおりで、「%s」が網羅を持つ" % (len(contracts), EXHAUSTIVE_CONTRACT),
        [],
    )


def check_no_reexports(state):
    """`src/accord/` の下の `__init__.py` に、読み込みの行が無いか。"""
    inits = state["inits"]
    if inits is None:
        return RESULT_SKIP, "%s/ が無いので、読む __init__.py が無い" % PACKAGE_DIR, []
    lines = []
    for path in inits:
        for line_number, line in enumerate(read_lines(path), 1):
            if REEXPORT_RE.match(line):
                lines.append(
                    "%s:%d: __init__.py に読み込みの行がある（%s）。消して、使う側が"
                    "定義のあるモジュールを直接読むようにする"
                    % (path.relative_to(state["root"]).as_posix(), line_number, line.strip())
                )
    if lines:
        return RESULT_FAIL, "読み込みの行 %d 件" % len(lines), lines
    return RESULT_PASS, "__init__.py %d 件のどれにも読み込みの行が無い" % len(inits), []


# 検査項目の表。読み手に向けて項目番号を使わず、この項目名で呼ぶ。
CHECKS = [
    ("迂回の印に決めの記録がある", check_markers_have_decisions),
    ("決めの記録が印を名指しする", check_decisions_name_markers),
    ("層の契約が緩んでいない", check_contracts_intact),
    ("再エクスポートが無い", check_no_reexports),
]


# ---------------------------------------------------------------------------
# 骨組み
# ---------------------------------------------------------------------------


def evaluate(state):
    """全項目を走らせて [(項目名, 結果, 詳細, 直し方の行), …] を返す。

    項目の関数が例外を投げたときは、その項目だけ不合格にして詳細を
    「項目の実行中に例外:」で始める（検査全体は落とさない）。広い受け止めは lint の咎めを
    黙らせる注記を要するので、ここでは項目の側の読み込みの誤りだけを受け止める。
    """
    results = []
    for name, check in CHECKS:
        try:
            result, detail, lines = check(state)
        except (InputError, OSError, ValueError, KeyError, TypeError) as exc:
            result, detail, lines = RESULT_FAIL, "項目の実行中に例外: %r" % (exc,), []
        results.append((name, result, detail, lines))
    return results


def run(root):
    """検査を 1 回走らせて終了コードを返す。"""
    try:
        state = load_state(root)
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
        default=".",
        help="リポジトリの直下（既定: カレントディレクトリ）",
    )
    args = parser.parse_args(argv)
    return run(args.root)


if __name__ == "__main__":
    sys.exit(main())
