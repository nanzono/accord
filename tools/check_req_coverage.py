#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""要件・テスト・実装の目印を、要件の番号で突き合わせる検査。

見るのは 6 項目で、どれも「番号の文字列がそろっているか」だけを見る。要件の文が
正しいかどうか、テストの中身が要件を確かめているかどうかは見ない。そこは人が読む。

読む範囲は 4 つ。

  要件        `docs/specs/` 配下の `*.md` の、`REQ-` に数字が続く見出し。
              案内の `README.md` と、コードの囲み（``` と ~~~ で囲んだ範囲）の中は
              読まない。案内や要件の中に書き方の例を置けるようにするため。
  テスト      `tests/` 配下の `test_*.py` の `def test_REQ_<数字>`。
  実装の目印  `src/` 配下の `*.py` の `# spec: REQ-<数字>`。
  取って代わられた印
              要件の見出しから次の見出しまでの間にある
              `status: superseded by REQ-<数字>` の行。行頭の箇条書きの記号は許す。

要件が 0 件でも、実装の目印が 0 件でも合格する。番号の書き方と、要件の書き方は
`docs/specs/README.md` にある。

標準ライブラリだけを使い、`accord` パッケージを import しない。このリポジトリを
外から見るための道具で、中で動くコードとは依存を分けるためである。

使い方:
  python3 tools/check_req_coverage.py [--root <リポジトリの直下>]

終了コード: 0（全項目合格）／1（不合格あり）／2（入力が読めない）
"""

import argparse
import re
import sys
from pathlib import Path

CHECK_TITLE = "要件とテストの突合検査"

# 結果の語。この 2 つ以外は使わない。
RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"

# 番号の桁数。この桁でないものは「番号の形と重なり」で落とす。
NUMBER_WIDTH = 3

# 読む場所。リポジトリの直下からの相対。末尾に `/` を付けた形は、直し方の文に出す。
SPECS_DIR = "docs/specs"
TESTS_DIR = "tests"
SRC_DIR = "src"
SPECS_DIR_SHOWN = SPECS_DIR + "/"
TESTS_DIR_SHOWN = TESTS_DIR + "/"

# 要件を置かない案内のファイル名（`docs/specs/` の中でこの名前だけは読まない）。
GUIDE_NAME = "README.md"

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^#+\s*REQ-(\d+)")
SUPERSEDED_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?`?status:\s*superseded\s+by\s+REQ-(\d+)`?\s*$"
)
TEST_RE = re.compile(r"def\s+(test_REQ_(\d+)[A-Za-z0-9_]*)")
MARKER_RE = re.compile(r"#\s*spec:\s*REQ-(\d+)")


class InputError(Exception):
    """検査の入力が読めない（終了コード 2）。項目の不合格（終了コード 1）と区別する。"""


# ---------------------------------------------------------------------------
# 入力の読み込み
# ---------------------------------------------------------------------------


def label(number):
    """数字の並びを、出力に出す `REQ-014` の形にする。"""
    return "REQ-%s" % number


def form_advice(number, shape):
    """桁の違う番号の直し方。shape は、3 桁にそろえた数字を差し込む書き方の形。

    桁が足りないときは 0 で埋めた形を見せる。桁が多いときは埋めようが無いので、振り直しを促す。
    """
    if len(number) < NUMBER_WIDTH:
        return "番号は %d 桁で書く（%s）" % (NUMBER_WIDTH, shape % number.zfill(NUMBER_WIDTH))
    return "番号は %d 桁で書く（%d 桁に収まる番号を振り直す）" % (NUMBER_WIDTH, NUMBER_WIDTH)


def where(path, root, line_number):
    """出力に出す場所の文字列。リポジトリの直下からの相対のパスと行番号。"""
    try:
        shown = path.relative_to(root)
    except ValueError:
        shown = path
    return "%s:%d" % (shown.as_posix(), line_number)


def shown_root(root):
    """見出しに出す対象の書き方。いま居る場所の中なら相対で出す。"""
    try:
        return str(Path(root).resolve().relative_to(Path.cwd()))
    except (ValueError, OSError):
        return str(root)


def read_lines(path):
    """1 ファイルを読んで行の一覧を返す。読めなければ入力の側の誤りとして投げる。"""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError("読めない: %s（%s）" % (path, exc))


def collect_requirements(root):
    """要件の見出しと、取って代わられた印を集める。

    `docs/specs/` が無いか空のときは 0 件を返す（入力が読めないことにはしない）。
    """
    specs_dir = root / SPECS_DIR
    requirements = []
    if not specs_dir.is_dir():
        return requirements

    guide = specs_dir / GUIDE_NAME
    for path in sorted(specs_dir.rglob("*.md")):
        if path == guide:
            continue
        current = None
        # 開いている囲みの記号（``` か ~~~）と、開いた行。閉じるのは同じ記号だけ。
        fence = None
        fence_line = 0
        for line_number, line in enumerate(read_lines(path), 1):
            found_fence = FENCE_RE.match(line)
            if fence is None and found_fence:
                fence = found_fence.group(1)
                fence_line = line_number
                continue
            if fence is not None:
                if found_fence and found_fence.group(1) == fence:
                    fence = None
                continue
            if line.startswith("#"):
                current = None
                heading = HEADING_RE.match(line)
                if heading:
                    current = {
                        "number": heading.group(1),
                        "where": where(path, root, line_number),
                        "superseded_by": None,
                        "superseded_where": None,
                    }
                    requirements.append(current)
                continue
            if current is None or current["superseded_by"] is not None:
                continue
            found = SUPERSEDED_RE.match(line)
            if found:
                current["superseded_by"] = found.group(1)
                current["superseded_where"] = where(path, root, line_number)
        if fence is not None:
            # 閉じ忘れの後ろを黙って読み飛ばすと、要件を数え落としたまま合格を返してしまう。
            raise InputError(
                "コードの囲みが閉じていない: %s。囲みを閉じてから走らせ直す"
                % where(path, root, fence_line)
            )
    return requirements


def collect_tests(root):
    """番号を名前に持つテストを集める。`tests/` が無ければ入力の側の誤り。"""
    tests_dir = root / TESTS_DIR
    if not tests_dir.is_dir():
        raise InputError("テストの置き場が無い: %s" % TESTS_DIR)

    tests = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        for line_number, line in enumerate(read_lines(path), 1):
            for name, number in TEST_RE.findall(line):
                tests.append(
                    {
                        "number": number,
                        "name": name,
                        "where": where(path, root, line_number),
                    }
                )
    return tests


def collect_markers(root):
    """実装の目印を集める。`src/` が無ければ 0 件（目印は無くてよい）。"""
    src_dir = root / SRC_DIR
    markers = []
    if not src_dir.is_dir():
        return markers

    for path in sorted(src_dir.rglob("*.py")):
        for line_number, line in enumerate(read_lines(path), 1):
            found = MARKER_RE.search(line)
            if found:
                markers.append(
                    {
                        "number": found.group(1),
                        "where": where(path, root, line_number),
                    }
                )
    return markers


def load_state(root):
    """検査対象を読んで、項目の関数に渡す状態を作る。"""
    root = Path(root)
    if not root.is_dir():
        raise InputError("リポジトリの直下が見つからない: %s" % root)

    requirements = collect_requirements(root)
    tests = collect_tests(root)
    markers = collect_markers(root)

    live = {r["number"] for r in requirements if r["superseded_by"] is None}
    superseded = {r["number"] for r in requirements if r["superseded_by"] is not None}
    return {
        "root": root,
        "requirements": requirements,
        "tests": tests,
        "markers": markers,
        "numbers": {r["number"] for r in requirements},
        "live": live,
        "superseded": superseded,
        "tested": {t["number"] for t in tests},
    }


# ---------------------------------------------------------------------------
# 項目の関数
#
# 引数は load_state が作った状態、返り値は (結果, 詳細, 直し方の行) の 3 つ組。
# 詳細は合格のときも書く（何を見て合格にしたのかが、後から出力だけで分かる）。
# 直し方の行は不合格のときだけ使い、1 件 1 行で「番号・場所・次にすること」を書く。
# ---------------------------------------------------------------------------


def check_tests_exist(state):
    """取って代わられていない要件のそれぞれに、その番号を名前に持つテストがあるか。"""
    missing = [
        r
        for r in state["requirements"]
        if r["superseded_by"] is None and r["number"] not in state["tested"]
    ]
    if missing:
        lines = [
            "%s（%s）: %s に def test_REQ_%s_<内容> を足す"
            % (label(r["number"]), r["where"], TESTS_DIR_SHOWN, r["number"])
            for r in missing
        ]
        return RESULT_FAIL, "テストの無い要件 %d 件" % len(missing), lines
    return RESULT_PASS, "現役の要件 %d 件すべてにテストがある" % len(state["live"]), []


def check_tests_point_to_requirements(state):
    """テスト名の番号が、要件のどれかに実在するか。"""
    orphans = [t for t in state["tests"] if t["number"] not in state["numbers"]]
    if orphans:
        lines = [
            "%s（%s の %s）: %s に「## %s」の要件を書くか、テスト名の番号を実在する要件に直す"
            % (
                label(t["number"]),
                t["where"],
                t["name"],
                SPECS_DIR_SHOWN,
                label(t["number"]),
            )
            for t in orphans
        ]
        return RESULT_FAIL, "要件に無い番号のテスト %d 件" % len(orphans), lines
    return RESULT_PASS, "番号つきのテスト %d 件はどれも要件を指している" % len(state["tests"]), []


def check_superseded_tests_gone(state):
    """取って代わられた要件の番号を名前に持つテストが残っていないか。"""
    replaced = {
        r["number"]: r["superseded_by"]
        for r in state["requirements"]
        if r["superseded_by"] is not None
    }
    left = [t for t in state["tests"] if t["number"] in replaced]
    if left:
        lines = [
            "%s（%s の %s）: この要件は %s に取って代わられている。"
            "振る舞いが変わった改訂ならこのテストを消し、文だけ直した改訂なら名前の番号を %s に付け替える"
            % (
                label(t["number"]),
                t["where"],
                t["name"],
                label(replaced[t["number"]]),
                label(replaced[t["number"]]),
            )
            for t in left
        ]
        return RESULT_FAIL, "取って代わられた番号のテスト %d 件" % len(left), lines
    return RESULT_PASS, "取って代わられた要件 %d 件にテストは残っていない" % len(state["superseded"]), []


def check_markers_point_to_live_requirements(state):
    """実装の目印の番号が要件に実在し、取って代わられていないか。目印 0 件なら合格。"""
    replaced = {
        r["number"]: r["superseded_by"]
        for r in state["requirements"]
        if r["superseded_by"] is not None
    }
    lines = []
    for marker in state["markers"]:
        number = marker["number"]
        if number in replaced:
            lines.append(
                "%s（%s の目印）: この要件は %s に取って代わられている。目印の番号を %s に付け替える"
                % (
                    label(number),
                    marker["where"],
                    label(replaced[number]),
                    label(replaced[number]),
                )
            )
        elif number not in state["numbers"]:
            lines.append(
                "%s（%s の目印）: %s にこの番号の要件が無い。実在する要件の番号に直すか、目印を消す"
                % (label(number), marker["where"], SPECS_DIR_SHOWN)
            )
    if lines:
        return RESULT_FAIL, "行き先の無い目印 %d 件" % len(lines), lines
    return RESULT_PASS, "実装の目印 %d 件はどれも現役の要件を指している" % len(state["markers"]), []


def check_number_form(state):
    """番号がすべて 3 桁で、同じ番号の見出しが 2 つ以上無いか。"""
    lines = []

    def wrong_width(number):
        return len(number) != NUMBER_WIDTH

    for requirement in state["requirements"]:
        if wrong_width(requirement["number"]):
            lines.append(
                "%s（%s の見出し）: %s"
                % (
                    label(requirement["number"]),
                    requirement["where"],
                    form_advice(requirement["number"], "REQ-%s"),
                )
            )
        if requirement["superseded_by"] is not None and wrong_width(requirement["superseded_by"]):
            lines.append(
                "%s（%s の取って代わられた印）: %s"
                % (
                    label(requirement["superseded_by"]),
                    requirement["superseded_where"],
                    form_advice(requirement["superseded_by"], "superseded by REQ-%s"),
                )
            )
    for test in state["tests"]:
        if wrong_width(test["number"]):
            lines.append(
                "%s（%s の %s）: %s"
                % (
                    label(test["number"]),
                    test["where"],
                    test["name"],
                    form_advice(test["number"], "test_REQ_%s_<内容>"),
                )
            )
    for marker in state["markers"]:
        if wrong_width(marker["number"]):
            lines.append(
                "%s（%s の目印）: %s"
                % (
                    label(marker["number"]),
                    marker["where"],
                    form_advice(marker["number"], "# spec: REQ-%s"),
                )
            )

    seen = {}
    for requirement in state["requirements"]:
        seen.setdefault(requirement["number"], []).append(requirement["where"])
    for number in sorted(seen):
        places = seen[number]
        if len(places) > 1:
            lines.append(
                "%s（%s の見出し）: 同じ番号の見出しが %d つある。片方に新しい番号を振る"
                % (label(number), "・".join(places), len(places))
            )

    if lines:
        return RESULT_FAIL, "形か重なりの誤り %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "見出し %d 件・テスト %d 件・目印 %d 件の番号がすべて %d 桁で、重なりも無い"
        % (len(state["requirements"]), len(state["tests"]), len(state["markers"]), NUMBER_WIDTH),
        [],
    )


def check_supersede_target_exists(state):
    """`superseded by` が指す番号が、要件に実在するか。"""
    lines = []
    for requirement in state["requirements"]:
        target = requirement["superseded_by"]
        if target is not None and target not in state["numbers"]:
            lines.append(
                "%s（%s の取って代わられた印）: 取って代わった先の %s が %s に無い。"
                "実在する番号に直すか、この印を消す"
                % (
                    label(requirement["number"]),
                    requirement["superseded_where"],
                    label(target),
                    SPECS_DIR_SHOWN,
                )
            )
    if lines:
        return RESULT_FAIL, "行き先の無い取って代わられた印 %d 件" % len(lines), lines
    return RESULT_PASS, "取って代わられた要件 %d 件の行き先はすべて実在する" % len(state["superseded"]), []


# 検査項目の表。読み手に向けて項目番号を使わず、この項目名で呼ぶ。
CHECKS = [
    ("要件にテストがある", check_tests_exist),
    ("テスト名の番号が要件にある", check_tests_point_to_requirements),
    ("取って代わられた番号のテストが残っていない", check_superseded_tests_gone),
    ("実装の目印が有効な要件を指す", check_markers_point_to_live_requirements),
    ("番号の形と重なり", check_number_form),
    ("取って代わった先が実在する", check_supersede_target_exists),
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
        except Exception as exc:  # noqa: BLE001 — 項目の不具合は不合格の側で扱う
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

    print("# %s（対象: %s）" % (CHECK_TITLE, shown_root(root)))
    failed = 0
    for name, result, detail, lines in evaluate(state):
        print("%s %s: %s" % (result, name, detail))
        if result == RESULT_FAIL:
            failed += 1
            for line in lines:
                print("    %s" % line)

    if failed:
        print("NG 不合格 %d 項目" % failed)
        return 1

    print(
        "OK 要件 %d 件（うち取って代わられた %d 件）、番号つきのテスト %d 件、実装の目印 %d 件"
        % (
            len(state["requirements"]),
            len(state["superseded"]),
            len(state["tests"]),
            len(state["markers"]),
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="%s。項目ごとに PASS か FAIL を 1 行ずつ出し、"
        "不合格の項目の下に直し方を 1 件 1 行で出す。" % CHECK_TITLE,
        epilog="終了コード: 0（全項目合格）／1（不合格あり）／2（入力が読めない）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="リポジトリの直下（既定: この検査の 1 つ上のディレクトリ）",
    )
    args = parser.parse_args(argv)
    return run(args.root)


if __name__ == "__main__":
    sys.exit(main())
