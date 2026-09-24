#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迂回の検査そのものを試す（審判が本当に落ちるかを確かめる）。

見るのは「わざと壊した入力で本当に不合格を返すか」である。ケースは 1 件ずつ、一時
ディレクトリに小さな木（層の契約・`src/accord/`・決めの記録・印を置くファイル）を作り、
git に登録してから検査を別プロセスで当て、終了コードと落ちるはずの項目名の `FAIL` 行を
突き合わせる。

あわせて、検査の持つ印の一覧と契約の期待が、決めの記録 0010 の一覧と一致すること、
検査をこのリポジトリの実物の木に当てて合格することを見る。

見本の中の印の文字列は、検査の持つ一覧から組み立てる。この自己試験のソースも迂回の検査が
読む対象なので、印をソースにそのまま書かない。標準ライブラリだけを使う。

使い方:
  python3 tools/check_bypass_selftest.py

終了コード: 0（全ケースが期待どおり）／1（食い違いが 1 件以上）
"""

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CHECK_SCRIPT = SCRIPT_DIR / "check_bypass.py"
DECISION_RECORD = REPO_ROOT / "docs" / "decisions" / "0010-record-every-check-bypass.md"

FAIL_LINE_RE = re.compile(r"^FAIL ([^:]+):", re.MULTILINE)

# 項目名（検査の出力に出るものと同じ文字列）。
ITEM_HAS_DECISION = "迂回の印に決めの記録がある"
ITEM_NAMES_MARKER = "決めの記録が印を名指しする"
ITEM_CONTRACTS = "層の契約が緩んでいない"
ITEM_REEXPORT = "再エクスポートが無い"
ALL_ITEMS = (ITEM_HAS_DECISION, ITEM_NAMES_MARKER, ITEM_CONTRACTS, ITEM_REEXPORT)

# 決めの記録の中で、一覧を探す小見出し。
MARKER_LIST_HEADING = "### 迂回の印の一覧"
CONTRACT_LIST_HEADING = "### 層の契約の期待の顔ぶれ"

# 見本の木で決めの記録に使う番号とファイル。
SAMPLE_NUMBER = "0010"
SAMPLE_RECORD = "docs/decisions/0010-sample.md"


def load_check():
    """検査のモジュールを読み込んで、印の一覧と契約の期待を取り出せるようにする。"""
    spec = importlib.util.spec_from_file_location("check_bypass", CHECK_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = load_check()
MARKER_NAMES = [name for name, _ in CHECK.MARKERS]

# 層の契約の見本。期待の 2 本を、実物と同じ形で持つ。
CONTRACT_LAYERS = """\
[importlinter:contract:layers]
name = %s
type = layers
containers =
    accord
layers =
    server
    models
exhaustive = true
""" % CHECK.EXPECTED_CONTRACTS[0]

CONTRACT_FORBIDDEN = """\
[importlinter:contract:vocabulary-external]
name = %s
type = forbidden
source_modules =
    accord.vocabulary
forbidden_modules =
    yaml
""" % CHECK.EXPECTED_CONTRACTS[1]

CONTRACT_HEAD = "[importlinter]\nroot_package = accord\n\n"
GOOD_CONTRACTS = CONTRACT_HEAD + CONTRACT_LAYERS + "\n" + CONTRACT_FORBIDDEN

GOOD_INIT = '"""見本のパッケージ。"""\n'


def marker_file(name):
    """印の種類ごとに、置くファイルを決める（4 種のファイルをそれぞれ読むことも試す）。"""
    if name in (MARKER_NAMES[9], MARKER_NAMES[10]):
        return ".importlinter"
    if name in (MARKER_NAMES[11], MARKER_NAMES[12]):
        return ".github/workflows/ci.yml"
    if name in (MARKER_NAMES[13], MARKER_NAMES[14], MARKER_NAMES[15]):
        return "pyproject.toml"
    return "tests/test_sample.py"


def marker_line(name, with_number):
    """印を 1 つ持つ行。with_number なら同じ行に決めの記録の番号を書く。"""
    tail = "  決め: %s" % SAMPLE_NUMBER if with_number else ""
    path = marker_file(name)
    if path == ".importlinter":
        return "%s = accord.server -> accord.models%s" % (name, tail)
    if path.endswith(".yml"):
        return "        run: uv run check %s%s" % (name, tail)
    if path == "pyproject.toml":
        return 'addopts = "%s tests/x"%s' % (name, tail)
    return "x = 1  %s%s" % (name, tail)


def base_tree():
    """印を持たない、合格する木。"""
    return {
        ".importlinter": GOOD_CONTRACTS,
        "src/accord/__init__.py": GOOD_INIT,
        "src/accord/server/__init__.py": "",
        "tests/test_sample.py": "def test_it_runs():\n    assert True\n",
        "pyproject.toml": '[project]\nname = "sample"\n',
        ".github/workflows/ci.yml": "name: CI\njobs:\n  check:\n    steps:\n",
        "docs/decisions/0001-sample.md": "# 見本の記録\n",
    }


def tree_with_marker(
    name, number=True, record=True, record_path=True, record_marker=True, same_line=True
):
    """印を 1 つ置いた木。引数で 1 点ずつ欠けさせる。

    same_line が偽なら、記録はパスと印の文字列を別々の行にだけ持つ（印の一覧とパスの
    説明を別々に書いた記録の形）。
    """
    tree = base_tree()
    path = marker_file(name)
    line = marker_line(name, number)
    if path == ".importlinter":
        # 層の契約の節の中に、例外の行として置く（契約そのものは壊さない）。
        tree[path] = CONTRACT_HEAD + CONTRACT_LAYERS + line + "\n\n" + CONTRACT_FORBIDDEN
    else:
        tree[path] = tree[path] + line + "\n"
    if record:
        body = ["# 見本の決め", ""]
        if record_path and record_marker and same_line:
            body.append("- `%s` の `%s` を許す" % (path, name))
        else:
            if record_path:
                body.append("- 場所: `%s`" % path)
            if record_marker:
                body.append("- 印: `%s`" % name)
        tree[SAMPLE_RECORD] = "\n".join(body) + "\n"
    return tree


def git_env():
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    return env


def build_tree(base, files, register=True):
    """一時ディレクトリに木を組み、git に登録する（迂回の検査は追跡するファイルを読む）。"""
    for relative_path, text in files.items():
        path = Path(base) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if register:
        subprocess.run(["git", "init", "-q", str(base)], check=True, env=git_env())
        subprocess.run(["git", "-C", str(base), "add", "-A"], check=True, env=git_env())


def run_check(root):
    completed = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout + completed.stderr


def judge(name, code, output, expected_code, must_fail, expected_word):
    """1 ケースの結果を突き合わせて、期待どおりなら True を返す。"""
    failed_items = FAIL_LINE_RE.findall(output)
    problems = []
    if code != expected_code:
        problems.append("終了コードが %d（期待 %d）" % (code, expected_code))
    for item in must_fail:
        if item not in failed_items:
            problems.append("「FAIL %s」の行が無い" % item)
    for item in ALL_ITEMS:
        if item in failed_items and item not in must_fail:
            problems.append("落ちてはいけない項目が落ちた: %s" % item)
    if expected_word and expected_word not in output:
        problems.append("出力に「%s」が無い" % expected_word)
    if problems:
        print("NG %s — %s" % (name, "、".join(problems)))
        print("--- 実際の出力 ---")
        print(output.rstrip())
        print("------------------")
        return False
    shown = " / ".join(failed_items) if failed_items else "FAIL の行なし"
    print("OK %s — 終了コード %d、%s" % (name, code, shown))
    return True


def run_case(name, files, expected_code, must_fail, expected_word=None, register=True):
    with tempfile.TemporaryDirectory() as work:
        build_tree(work, files, register)
        code, output = run_check(work)
    return judge(name, code, output, expected_code, must_fail, expected_word)


def cases():
    """(ケース名, 木, 期待の終了コード, 落ちるはずの項目, 含まれる語[, git に登録するか])"""
    found = [
        ("印の無い木", base_tree(), 0, (), "印のある 0 件"),
    ]
    for name in MARKER_NAMES:
        found += [
            ("%s: 番号と記録がそろう" % name, tree_with_marker(name), 0, (), "印のある 1 件"),
            (
                "%s: 番号が無い" % name,
                tree_with_marker(name, number=False),
                1,
                (ITEM_HAS_DECISION,),
                "同じ行に番号が無い",
            ),
            (
                "%s: 記録が無い" % name,
                tree_with_marker(name, record=False),
                1,
                (ITEM_NAMES_MARKER,),
                "が無い。記録を書くか",
            ),
            (
                "%s: 記録がパスを持たない" % name,
                tree_with_marker(name, record_path=False),
                1,
                (ITEM_NAMES_MARKER,),
                "ファイルのパス「%s」" % marker_file(name),
            ),
            (
                "%s: 記録が印を持たない" % name,
                tree_with_marker(name, record_marker=False),
                1,
                (ITEM_NAMES_MARKER,),
                "印の文字列「%s」" % name,
            ),
            (
                "%s: 記録がパスと印を別々の行にだけ持つ" % name,
                tree_with_marker(name, same_line=False),
                1,
                (ITEM_NAMES_MARKER,),
                "別々の行にしか書いていない",
            ),
        ]

    lint_note = MARKER_NAMES[0]
    with_code = base_tree()
    with_code["tests/test_sample.py"] += "x = 1  %s: E501  決め: %s\n" % (lint_note, SAMPLE_NUMBER)
    with_code[SAMPLE_RECORD] = "- `tests/test_sample.py` の `%s` を許す\n" % lint_note
    found.append(
        (
            "lint の注記は規則の名前まで記録に要る",
            with_code,
            1,
            (ITEM_NAMES_MARKER,),
            "印の文字列「%s: E501」" % lint_note,
        )
    )
    three_digits = tree_with_marker(lint_note)
    three_digits["tests/test_sample.py"] = three_digits["tests/test_sample.py"].replace(
        "決め: %s" % SAMPLE_NUMBER, "決め: 010"
    )
    found.append(
        ("番号が 4 桁でない", three_digits, 1, (ITEM_HAS_DECISION,), "4 桁ではない")
    )

    # 免罪符になりやすい 2 通り。印の一覧とパスの説明を別々の行に持つ記録が、そのファイルの
    # 別の印まで許してしまわないこと（pytest の設定の印と、検査のソースの型の注記）。
    for label_text, path, name, line in (
        (
            "pytest の設定",
            "pyproject.toml",
            MARKER_NAMES[13],
            'addopts = "%s tests/x"  決め: %s' % (MARKER_NAMES[13], SAMPLE_NUMBER),
        ),
        (
            "検査のソースの型の注記",
            "tools/check_bypass.py",
            MARKER_NAMES[1],
            "x = 1  %s  決め: %s" % (MARKER_NAMES[1], SAMPLE_NUMBER),
        ),
    ):
        loose_record = base_tree()
        loose_record[path] = loose_record.get(path, "") + line + "\n"
        loose_record[SAMPLE_RECORD] = (
            "# 見本の決め\n\n"
            "- 印の一覧: " + "・".join("`%s`" % m for m in MARKER_NAMES) + "\n"
            "- 見るファイル: `pyproject.toml`・`.importlinter`・`tools/check_bypass.py`\n"
        )
        found.append(
            (
                "%s: 一覧とパスの説明だけの記録では通らない" % label_text,
                loose_record,
                1,
                (ITEM_NAMES_MARKER,),
                "別々の行にしか書いていない",
            )
        )

    # 規則の名前を持たない注記は、規則の名前つきの注記を許す記録の行では通らない
    # （記録の行に文字として含まれるだけでは一致としない）。
    for label_text, bare, named in (
        ("lint の注記", MARKER_NAMES[0], MARKER_NAMES[0] + ": BLE001"),
        ("型の注記", MARKER_NAMES[1], MARKER_NAMES[1] + "[x]"),
    ):
        prefix_only = base_tree()
        prefix_only["tests/test_sample.py"] += "x = 1  %s  決め: %s\n" % (bare, SAMPLE_NUMBER)
        prefix_only[SAMPLE_RECORD] = "- `tests/test_sample.py` の `%s` を許す\n" % named
        found.append(
            (
                "%s: 規則の名前なしの印は、名前つきを許す記録の行では通らない" % label_text,
                prefix_only,
                1,
                (ITEM_NAMES_MARKER,),
                "印の文字列「%s」" % bare,
            )
        )
        exact = base_tree()
        exact["tests/test_sample.py"] += "x = 1  %s  決め: %s\n" % (named, SAMPLE_NUMBER)
        exact[SAMPLE_RECORD] = "- `tests/test_sample.py` の `%s` を許す\n" % named
        found.append(
            ("%s: 規則の名前まで同じなら通る" % label_text, exact, 0, (), "印のある 1 件")
        )

    # 層の契約と再エクスポート。
    dropped = base_tree()
    dropped[".importlinter"] = CONTRACT_HEAD + CONTRACT_LAYERS
    found.append(
        ("契約を 1 本消す", dropped, 1, (ITEM_CONTRACTS,), CHECK.EXPECTED_CONTRACTS[1])
    )
    renamed = base_tree()
    renamed[".importlinter"] = GOOD_CONTRACTS.replace(
        CHECK.EXPECTED_CONTRACTS[0], "層はおおむね上から下へ読む"
    )
    found.append(("契約の名前を変える", renamed, 1, (ITEM_CONTRACTS,), "期待に無い契約"))
    loose = base_tree()
    loose[".importlinter"] = GOOD_CONTRACTS.replace("exhaustive = true\n", "")
    found.append(("網羅を外す", loose, 1, (ITEM_CONTRACTS,), "exhaustive = true が無い"))
    no_file = base_tree()
    no_file.pop(".importlinter")
    found.append(("契約のファイルを消す", no_file, 1, (ITEM_CONTRACTS,), "契約のファイルが無い"))
    reexport = base_tree()
    reexport["src/accord/server/__init__.py"] = "from accord.server.app import run\n"
    found.append(("__init__.py に読み込みを足す", reexport, 1, (ITEM_REEXPORT,), "読み込みの行がある"))

    # 入力が読めない木。
    found.append(("git に登録していない木", base_tree(), 2, (), "git が追跡するファイルを読めない", False))
    return found


def bullets_under(heading, lines):
    """小見出しから次の見出しまでの、行頭が `- ` の行を返す。"""
    inside = False
    found = []
    for line in lines:
        if line.startswith("#"):
            inside = line.strip() == heading
            continue
        if inside and line.startswith("- "):
            found.append(line)
    return found


def check_record_agrees():
    """検査の持つ一覧と、決めの記録 0010 の一覧が一致するか。"""
    ok = True
    try:
        lines = DECISION_RECORD.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print("NG 決めの記録を読めない: %s（%s）" % (DECISION_RECORD, exc))
        return False

    recorded = []
    for line in bullets_under(MARKER_LIST_HEADING, lines):
        found = re.match(r"^- `([^`]+)`", line)
        if found:
            recorded.append(found.group(1))
    if recorded == MARKER_NAMES:
        print("OK 印の一覧 %d 種が決めの記録の一覧と一致する" % len(MARKER_NAMES))
    else:
        ok = False
        print(
            "NG 印の一覧が決めの記録と食い違う — 検査だけ: %s、記録だけ: %s、並びの一致: %s"
            % (
                [m for m in MARKER_NAMES if m not in recorded],
                [m for m in recorded if m not in MARKER_NAMES],
                recorded == MARKER_NAMES,
            )
        )

    contracts = []
    for line in bullets_under(CONTRACT_LIST_HEADING, lines):
        found = re.match(r"^- 「([^」]+)」", line)
        if found:
            contracts.append(found.group(1))
    if tuple(contracts) == tuple(CHECK.EXPECTED_CONTRACTS):
        print("OK 契約の期待 %d 本が決めの記録の顔ぶれと一致する" % len(contracts))
    else:
        ok = False
        print(
            "NG 契約の期待が決めの記録と食い違う — 検査: %s、記録: %s"
            % (list(CHECK.EXPECTED_CONTRACTS), contracts)
        )
    return ok


def main():
    if not CHECK_SCRIPT.is_file():
        print("ERROR: 検査本体が見つからない: %s" % CHECK_SCRIPT, file=sys.stderr)
        return 1
    failures = 0
    all_cases = cases()
    for case in all_cases:
        if not run_case(*case):
            failures += 1

    if not check_record_agrees():
        failures += 1

    code, output = run_check(REPO_ROOT)
    if not judge("このリポジトリの実物の木", code, output, 0, (), "不合格 0 件"):
        failures += 1

    print("ケース %d 件・食い違い %d 件" % (len(all_cases) + 2, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
