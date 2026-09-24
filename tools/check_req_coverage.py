#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""要件・テスト・実装の目印を、要件の番号で突き合わせる検査。

見るのは、番号の文字列がそろっているかの項目と、要件文に要件に書かない語が無いかの
項目と、番号を名前に持たないテストが理由を書いているかの項目である。要件の文が正しいかどうか、テストの中身が要件を確かめているかどうかは
見ない。そこは人が読む。

読む範囲は 5 つ。

  要件        `docs/specs/` 配下の `*.md` の、`REQ-` に数字が続く見出し。
              案内の `README.md` と、コードの囲み（``` と ~~~ で囲んだ範囲）の中は
              読まない。案内や要件の中に書き方の例を置けるようにするため。
  テスト      `tests/` 配下の `test_*.py` の `def test_REQ_<数字>`。名前に番号を
              持たない `test_` の関数は、docstring の 1 行目も読む。
  実装の目印  `src/` 配下の `*.py` の `# spec: REQ-<数字>`。
  取って代わられた印
              要件の見出しから次の見出しまでの間にある
              `status: superseded by REQ-<数字>` の行。行頭の箇条書きの記号は許す。
  条件の行    `--spec-dir` で渡された置き場の `*.md` の、「機械検査で見る条件」の
              見出しから次の見出しまでの間にある条件の行と、宣言の行。渡されなければ
              読まない。名前が `_` で始まる雛形と、名前が `_intent.md` で終わる
              判定ファイルは、仕様書ではないので読まない。

要件が 0 件でも、実装の目印が 0 件でも合格する。番号の書き方と、要件の書き方は
`docs/specs/README.md` にある。

条件の行の見分け方と、その末尾に置く印の形は、下の「条件の行」の節に書いた。

標準ライブラリだけを使い、`accord` パッケージを import しない。このリポジトリを
外から見るための道具で、中で動くコードとは依存を分けるためである。

使い方:
  python3 tools/check_req_coverage.py [--root <リポジトリの直下>]
                                      [--spec-dir <開発の仕様書の置き場>]
                                      [--spec-table]

`--spec-table` は `--spec-dir` と一緒に渡す。項目の出力の後に、仕様書ごとの条件の行の
数と印の内訳を Markdown の表で出す。

終了コード: 0（全項目合格。省略は合格に数える）／1（不合格あり）／2（入力が読めない）
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path

CHECK_TITLE = "要件とテストの突合検査"

# 結果の語。この 3 つ以外は使わない。SKIP は「見る材料を渡されなかった」であって、
# 不合格ではない。終了コードには数えない。
RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"
RESULT_SKIP = "SKIP"

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

# 要件文に書かない語。案内の「要件に書かないこと」の節に挙げた語と同じ並びで、
# 一致は自己試験が見る。頭の「〜」は、前に何が来てもよいことを表し、探すときは外す。
FORBIDDEN_WORDS = (
    "適切に",
    "必要に応じて",
    "堅牢に",
    "最適化して",
    "〜が望ましい",
    "可能であれば",
)

# ---------------------------------------------------------------------------
# 条件の行
#
# 開発の仕様書の「機械検査で見る条件」の節には、条件を 1 件 1 行で書く。その行の
# 末尾に、その条件がどの要件を指すかの印を 1 つ置く。印の形は 3 つだけである。
#
#   要件: REQ-014          振る舞いを述べ、指せる要件がある条件。複数を指すなら
#                          `要件: REQ-011・REQ-012` や `要件: REQ-046〜REQ-052` と並べる。
#                          範囲で書いた場合は、間の番号もすべて実在するかを見る。
#   要件: 無し（理由）      振る舞いを述べていない条件。理由は「開発の手続き」
#                          「テスト全体の合格」「公開境界」のような短い語で書く。
#   要件: これから（機能名） 振る舞いを述べているのに、指せる要件がまだ書かれていない条件。
#                          要件を書いた単位で、番号の印へ置き換える。
#
# 1 つの条件が 2 つの振る舞いを述べ、片方だけ要件があるときは
# `要件: REQ-019・これから（機能名）` のように並べてよい。
#
# 条件の行は次の 3 つである。コードの囲みの中は読まない。
#
#   行頭が `- ` の行
#   行頭が `**` の行
#   表のデータ行（行頭が `| ` で、区切りの行でも見出しの行でもないもの）
#
# 太字の段落の下に内訳の箇条書きを置くときは 2 文字字下げする。字下げした行は行頭が
# `- ` ではなくなるので、条件の行から外れる。内訳が指す要件は、上の太字の行にまとめる。
#
# 条件の行を読むのは、宣言の行 `条件の印: あり` を持つ仕様書だけである。
# `条件の印: 対象外（理由）` の行を持つ仕様書は読み飛ばす。検査に対象の一覧を持たせると、
# 仕様書が増えるたびに一覧の更新を人が覚えておくことになるので、範囲は仕様書の側の宣言で
# 決める。そのかわり、宣言の無い仕様書と、理由の無い「対象外」は「仕様書に宣言がある」の
# 項目で落とす（黙って読み飛ばした仕様書の上に「全部覆った」が立たないようにするため）。
#
# 置き場のうち、名前が `_` で始まるもの（雛形）と、名前が `_intent.md` で終わるもの
# （判定ファイル）は仕様書ではないので、宣言も条件の行も読まない。
# ---------------------------------------------------------------------------

# 条件の節を見分ける語。この語を含む見出しから、次の見出しまでが条件の節である。
CONDITION_SECTION_WORD = "機械検査で見る条件"

# 印の頭の語と、結ばないとき・要件がこれからのときの本文の形。
MARK_LABEL = "要件:"
MARK_NONE_RE = re.compile(r"^無し（.+）$")
MARK_PENDING_RE = re.compile(r"これから（.+?）")

# 仕様書の側の宣言。行の頭に置く。
DECLARATION_RE = re.compile(r"^条件の印:\s*(\S.*?)\s*$")
DECLARATION_ON = "あり"
DECLARATION_OFF = "対象外"
# 「対象外」の後ろに置く理由。括弧は全角で、中が空でないこと。
DECLARATION_OFF_RE = re.compile(r"^対象外\s*（(.*)）$")
DECLARATION_EXAMPLE = "「条件の印: あり」か「条件の印: 対象外（理由）」"

# 仕様書として読まないファイルの名前の形（雛形と判定ファイル）。
TEMPLATE_PREFIX = "_"
JUDGEMENT_SUFFIX = "_intent.md"

# 番号を名前に持たないテストの docstring の 1 行目の頭。この後ろに理由の文を書く。
PLAIN_TEST_PREFIX = "番号なし:"
PLAIN_TEST_EXAMPLE = "「番号なし: <何を試すテストか。なぜ要件に結ばないか>」"
NUMBERED_TEST_PREFIX = "test_REQ_"

FENCE_RE = re.compile(r"^\s*(```|~~~)")
# 表の区切りの行。行頭が `|` で、縦棒とハイフンとコロンと空白だけでできている。
TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+$")
HEADING_RE = re.compile(r"^#+\s*REQ-(\d+)")
SUPERSEDED_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?`?status:\s*superseded\s+by\s+REQ-(\d+)`?\s*$"
)
TEST_RE = re.compile(r"def\s+(test_REQ_(\d+)[A-Za-z0-9_]*)")
MARKER_RE = re.compile(r"#\s*spec:\s*REQ-(\d+)")
# 印の本文に並ぶ番号。`REQ-011・REQ-012` のように並べた形を拾う。
MARKER_NUMBER_RE = re.compile(r"REQ-(\d+)")
# 範囲で書いた形。`REQ-046〜REQ-052` は、間の番号も含めてすべてを指す。
MARKER_RANGE_RE = re.compile(r"REQ-(\d+)\s*〜\s*REQ-(\d+)")


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
                        "text": None,
                        "text_where": None,
                    }
                    requirements.append(current)
                continue
            if current is None:
                continue
            if current["text"] is None and line.strip() and not line.lstrip().startswith("- "):
                # 要件文。見出しの後で、箇条（添える 2 項目と取って代わられた印）でない最初の行。
                current["text"] = line.strip()
                current["text_where"] = where(path, root, line_number)
            if current["superseded_by"] is not None:
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


def collect_plain_tests(root):
    """番号を名前に持たないテスト関数と、その docstring の 1 行目を集める。

    文字列の一致ではなく構文木で読むのは、docstring の中身を確実に取るためである。
    構文として読めないテストのファイルは、入力の側の誤りとして投げる。
    """
    tests_dir = root / TESTS_DIR
    if not tests_dir.is_dir():
        raise InputError("テストの置き場が無い: %s" % TESTS_DIR)

    plain = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        source = "\n".join(read_lines(path))
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            raise InputError("テストのファイルを構文として読めない: %s（%s）" % (path, exc))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_") or node.name.startswith(NUMBERED_TEST_PREFIX):
                continue
            docstring = ast.get_docstring(node, clean=True)
            first = None
            if docstring is not None:
                lines = docstring.strip().splitlines()
                first = lines[0].strip() if lines else ""
            plain.append(
                {
                    "name": node.name,
                    "where": where(path, root, node.lineno),
                    "first_line": first,
                }
            )
    plain.sort(key=lambda item: item["where"])
    return plain


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


def numbers_in_mark(mark):
    """印の本文が指す番号を、範囲を広げて全部返す。

    返すのは (番号の一覧, 逆向きの範囲の一覧)。`REQ-046〜REQ-052` は 046 から 052 まで
    7 件に広げる。範囲で書いた以上、間が詰まっていることが前提なので、欠番があれば
    「実在しない番号」として落ちる。終わりが始まりより小さい範囲は、書き間違いとして返す。
    """
    numbers = []
    backwards = []
    rest = mark
    for found in MARKER_RANGE_RE.finditer(mark):
        start, end = found.group(1), found.group(2)
        if int(end) < int(start):
            backwards.append(found.group(0))
            continue
        width = max(len(start), len(end))
        numbers.extend("%0*d" % (width, n) for n in range(int(start), int(end) + 1))
    # 広げ終えた範囲は、両端を二重に数えないよう本文から抜く。
    rest = MARKER_RANGE_RE.sub(" ", rest)
    numbers.extend(MARKER_NUMBER_RE.findall(rest))
    return numbers, backwards


def mark_of(line):
    """条件の行から印の本文を取り出す。印が無ければ None を返す。

    表のデータ行は末尾の欄に印を書くので、その欄だけを見る。ほかの行は、行の末尾に
    ある最後の `要件:` から後ろを印の本文とする。
    """
    body = line.rstrip()
    if body.startswith("| "):
        cells = [cell.strip() for cell in body.strip().strip("|").split("|")]
        body = cells[-1] if cells else ""
    position = body.rfind(MARK_LABEL)
    if position < 0:
        return None
    return body[position + len(MARK_LABEL):].strip()


def resolve_given_dir(given):
    """渡された置き場を探す。

    相対の置き場が見つからないときは、symlink をたどる前の作業ディレクトリからも探す。
    symlink をたどってこのリポジトリに入ると、`cd` した後の `../…` が、たどる前の場所では
    なく実体の側から数えられて、書いた場所に着かないためである。
    `..` は symlink をたどった後で解かれるので、文字列のうちに約めてから見に行く。
    """
    path = Path(given)
    if path.is_dir() or path.is_absolute():
        return path
    logical = os.environ.get("PWD")
    if logical:
        candidate = Path(os.path.normpath(os.path.join(logical, given)))
        if candidate.is_dir():
            return candidate
    return path


def declaration_of(lines):
    """仕様書の宣言の行を読む。コードの囲みの中は見ない。

    返すのは `あり`・`対象外…`・None のどれか。同じ行が 2 つあれば、はじめの 1 つを採る。
    """
    fence = None
    for line in lines:
        found_fence = FENCE_RE.match(line)
        if fence is None and found_fence:
            fence = found_fence.group(1)
            continue
        if fence is not None:
            if found_fence and found_fence.group(1) == fence:
                fence = None
            continue
        found = DECLARATION_RE.match(line)
        if found:
            return found.group(1)
    return None


def is_spec_file(path):
    """仕様書として読むファイルか。雛形（`_` で始まる）と判定ファイル（`_intent.md` で終わる）は外す。"""
    return not (path.name.startswith(TEMPLATE_PREFIX) or path.name.endswith(JUDGEMENT_SUFFIX))


def collect_conditions(spec_dir):
    """開発の仕様書の宣言と条件の行を集める。置き場が無ければ入力の側の誤り。

    条件の行を読むのは、宣言の行が `条件の印: あり` の仕様書だけである。返すのは
    (条件の一覧, 仕様書の一覧, 読まなかった雛形と判定ファイルの数)。仕様書の一覧の
    1 件は、名前・宣言の値（無ければ None）・その仕様書の条件の行を持つ。
    """
    spec_dir = resolve_given_dir(spec_dir)
    if not spec_dir.is_dir():
        raise InputError("仕様書の置き場が見つからない: %s" % spec_dir)

    conditions = []
    specs = []
    excluded = 0
    for path in sorted(spec_dir.rglob("*.md")):
        if not is_spec_file(path):
            excluded += 1
            continue
        lines = read_lines(path)
        declaration = declaration_of(lines)
        spec = {
            "name": path.relative_to(spec_dir).as_posix(),
            "declaration": declaration,
            "conditions": [],
        }
        specs.append(spec)
        if declaration != DECLARATION_ON:
            # `対象外` を宣言した仕様書と、宣言が無いか形の違う仕様書は、条件の行を読まない。
            # 後の 2 つは「仕様書に宣言がある」の項目が落とす。
            continue
        inside = False
        fence = None
        fence_line = 0
        for line_number, line in enumerate(lines, 1):
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
                inside = CONDITION_SECTION_WORD in line
                continue
            if not inside:
                continue
            if line.startswith("| "):
                if TABLE_SEPARATOR_RE.match(line.rstrip()):
                    continue
                # 見出しの行は「次の行が区切りの行」で見分ける。
                following = lines[line_number] if line_number < len(lines) else ""
                if TABLE_SEPARATOR_RE.match(following.rstrip()):
                    continue
            elif not (line.startswith("- ") or line.startswith("**")):
                continue
            condition = {
                "where": where(path, spec_dir, line_number),
                "text": line.strip(),
                "mark": mark_of(line),
            }
            conditions.append(condition)
            spec["conditions"].append(condition)
        if fence is not None:
            raise InputError(
                "コードの囲みが閉じていない: %s。囲みを閉じてから走らせ直す"
                % where(path, spec_dir, fence_line)
            )
    return conditions, specs, excluded


def load_state(root, spec_dir=None):
    """検査対象を読んで、項目の関数に渡す状態を作る。

    `spec_dir` が None のときは仕様書を読まず、仕様書の宣言と条件の行を見る 3 項目は省略になる。
    """
    root = Path(root)
    if not root.is_dir():
        raise InputError("リポジトリの直下が見つからない: %s" % root)

    requirements = collect_requirements(root)
    tests = collect_tests(root)
    plain_tests = collect_plain_tests(root)
    markers = collect_markers(root)
    if spec_dir is None:
        conditions, specs, specs_excluded = None, None, 0
    else:
        conditions, specs, specs_excluded = collect_conditions(spec_dir)
    specs_read = 0 if specs is None else sum(
        1 for spec in specs if spec["declaration"] == DECLARATION_ON
    )
    specs_skipped = 0 if specs is None else len(specs) - specs_read

    live = {r["number"] for r in requirements if r["superseded_by"] is None}
    superseded = {r["number"] for r in requirements if r["superseded_by"] is not None}
    return {
        "root": root,
        "spec_dir": None if spec_dir is None else Path(spec_dir),
        "requirements": requirements,
        "tests": tests,
        "plain_tests": plain_tests,
        "markers": markers,
        "conditions": conditions,
        "specs": specs,
        "specs_excluded": specs_excluded,
        "specs_read": specs_read,
        "specs_skipped": specs_skipped,
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


def plain_test_problem(first_line):
    """番号なしのテストの docstring の 1 行目の不足を 1 語で返す。足りていれば None。"""
    if first_line is None:
        return "docstring が無い"
    if not first_line.startswith(PLAIN_TEST_PREFIX):
        return "docstring の 1 行目が「%s 」で始まらない" % PLAIN_TEST_PREFIX
    if not first_line[len(PLAIN_TEST_PREFIX):].strip():
        return "「%s」の後ろの理由が空" % PLAIN_TEST_PREFIX
    return None


def check_plain_tests_have_reasons(state):
    """番号を名前に持たないテストの docstring の 1 行目が、「番号なし: 」と理由の文か。

    `--spec-dir` を渡さなくても見る。
    """
    lines = []
    for test in state["plain_tests"]:
        problem = plain_test_problem(test["first_line"])
        if problem is None:
            continue
        lines.append(
            "%s の %s: %s。docstring の 1 行目を%sにする"
            "（要件を確かめるテストなら、名前を test_REQ_<番号>_<内容> にする）"
            % (test["where"], test["name"], problem, PLAIN_TEST_EXAMPLE)
        )
    if lines:
        return (
            RESULT_FAIL,
            "番号を名前に持たないテスト %d 本のうち、理由の無いもの %d 本"
            % (len(state["plain_tests"]), len(lines)),
            lines,
        )
    return (
        RESULT_PASS,
        "番号を名前に持たないテスト %d 本すべてに、docstring の 1 行目の理由がある"
        % len(state["plain_tests"]),
        [],
    )


def declaration_problem(declaration):
    """宣言の値の不足を 1 語で返す。足りていれば None。"""
    if declaration is None:
        return "宣言の行が無い"
    if declaration == DECLARATION_ON:
        return None
    found = DECLARATION_OFF_RE.match(declaration)
    if found:
        return None if found.group(1).strip() else "「%s」の括弧の中の理由が空" % DECLARATION_OFF
    if declaration.startswith(DECLARATION_OFF) and "（" not in declaration:
        return "「%s」の後ろに理由の括弧が無い" % DECLARATION_OFF
    return "宣言の形が違う（いまは「条件の印: %s」）" % declaration


def check_specs_declare(state):
    """雛形と判定ファイルを除いた仕様書のすべてが、宣言「あり」か「対象外（理由）」を持つか。

    `--spec-dir` を渡されなければ省略する。
    """
    if state["specs"] is None:
        return RESULT_SKIP, "--spec-dir を渡されていないので、仕様書を読んでいない", []

    lines = []
    for spec in state["specs"]:
        problem = declaration_problem(spec["declaration"])
        if problem is None:
            continue
        lines.append(
            "%s: %s。受け入れ条件の節に%sの行を置く" % (spec["name"], problem, DECLARATION_EXAMPLE)
        )
    if lines:
        return RESULT_FAIL, "宣言の足りない仕様書 %d 本" % len(lines), lines
    return (
        RESULT_PASS,
        "仕様書 %d 本すべてに宣言がある（あり %d・対象外 %d）。雛形と判定ファイル %d 本は読んでいない"
        % (
            len(state["specs"]),
            state["specs_read"],
            state["specs_skipped"],
            state["specs_excluded"],
        ),
        [],
    )


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


def check_conditions_point_to_requirements(state):
    """条件の行の印が指す番号が、要件に実在し、取って代わられていないか。

    `--spec-dir` を渡されなければ省略する。印の無い行は、ここでは数えない
    （印が無いことは「条件に印がある」の項目が見る）。
    """
    if state["conditions"] is None:
        return RESULT_SKIP, "--spec-dir を渡されていないので、条件の行を読んでいない", []

    replaced = {
        r["number"]: r["superseded_by"]
        for r in state["requirements"]
        if r["superseded_by"] is not None
    }
    lines = []
    linked = 0
    ranges = 0
    for condition in state["conditions"]:
        mark = condition["mark"]
        if mark is None or MARK_NONE_RE.match(mark):
            continue
        numbers, backwards = numbers_in_mark(mark)
        for written in backwards:
            lines.append(
                "%s の条件の印: 範囲「%s」の終わりが始まりより小さい。"
                "小さいほうを先に書く" % (condition["where"], written)
            )
        if not numbers:
            continue
        linked += 1
        ranges += len(MARKER_RANGE_RE.findall(mark))
        for number in numbers:
            if number in replaced:
                lines.append(
                    "%s（%s の条件の印）: この要件は %s に取って代わられている。"
                    "印の番号を %s に付け替える"
                    % (
                        label(number),
                        condition["where"],
                        label(replaced[number]),
                        label(replaced[number]),
                    )
                )
            elif number not in state["numbers"]:
                lines.append(
                    "%s（%s の条件の印）: %s にこの番号の要件が無い。"
                    "実在する要件の番号に直すか、先に要件を書く"
                    % (label(number), condition["where"], SPECS_DIR_SHOWN)
                )
    if lines:
        return RESULT_FAIL, "行き先の無い条件の印 %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "要件に結んだ条件 %d 件の行き先はすべて実在する（うち範囲で書いた印 %d 件は、"
        "間の番号まで広げて確かめた）" % (linked, ranges),
        [],
    )


def check_conditions_have_marks(state):
    """条件の行すべてに印があるか。

    `--spec-dir` を渡されなければ省略する。印の形が 2 つのどちらでもない行も、
    ここで落とす（`要件:` と書いてあるのに中身が読めない状態を見逃さないため）。
    """
    if state["conditions"] is None:
        return RESULT_SKIP, "--spec-dir を渡されていないので、条件の行を読んでいない", []

    lines = []
    linked = 0
    none = 0
    pending = 0
    both = 0
    for condition in state["conditions"]:
        mark = condition["mark"]
        shown = condition["text"]
        if len(shown) > 40:
            shown = shown[:40] + "…"
        if mark is None:
            lines.append(
                "%s: 条件の行に印が無い。行の末尾に「%s REQ-014」か"
                "「%s 無し（理由）」か「%s これから（機能名）」を足す（%s）"
                % (condition["where"], MARK_LABEL, MARK_LABEL, MARK_LABEL, shown)
            )
            continue
        if MARK_NONE_RE.match(mark):
            none += 1
            continue
        has_number = bool(MARKER_NUMBER_RE.search(mark))
        has_pending = bool(MARK_PENDING_RE.search(mark))
        if has_number:
            linked += 1
        if has_pending:
            pending += 1
        if has_number and has_pending:
            both += 1
        if not has_number and not has_pending:
            lines.append(
                "%s: 印の形が違う（いまは「%s %s」）。「%s REQ-014」か"
                "「%s 無し（理由）」か「%s これから（機能名）」の形にする"
                % (
                    condition["where"],
                    MARK_LABEL,
                    mark,
                    MARK_LABEL,
                    MARK_LABEL,
                    MARK_LABEL,
                )
            )
    if lines:
        return RESULT_FAIL, "印の無い条件の行 %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "条件の行 %d 件すべてに印がある（要件に結んだ %d・無し %d・これから %d。"
        "うち %d 件は番号と「これから」を併記）。読んだ仕様書 %d 本、"
        "宣言が「あり」でないので読まなかった仕様書 %d 本"
        % (
            len(state["conditions"]),
            linked,
            none,
            pending,
            both,
            state["specs_read"],
            state["specs_skipped"],
        ),
        [],
    )


def check_forbidden_words(state):
    """要件文（見出しの直下の文）に、要件に書かない語が無いか。取って代わられた要件も見る。"""
    lines = []
    looked = 0
    for requirement in state["requirements"]:
        text = requirement["text"]
        if text is None:
            continue
        looked += 1
        for word in FORBIDDEN_WORDS:
            if word.lstrip("〜") in text:
                lines.append(
                    "%s（%s の要件文）: 「%s」を含む。機械で確かめられる振る舞いの文に書き直す"
                    "（守らなくてよいことなら要件から外す）"
                    % (label(requirement["number"]), requirement["text_where"], word)
                )
    if lines:
        return RESULT_FAIL, "要件に書かない語 %d 件" % len(lines), lines
    return (
        RESULT_PASS,
        "要件文 %d 件のどれにも、要件に書かない語 %d 語が無い" % (looked, len(FORBIDDEN_WORDS)),
        [],
    )


# 検査項目の表。読み手に向けて項目番号を使わず、この項目名で呼ぶ。
CHECKS = [
    ("要件にテストがある", check_tests_exist),
    ("テスト名の番号が要件にある", check_tests_point_to_requirements),
    ("番号なしのテストに理由がある", check_plain_tests_have_reasons),
    ("取って代わられた番号のテストが残っていない", check_superseded_tests_gone),
    ("実装の目印が有効な要件を指す", check_markers_point_to_live_requirements),
    ("番号の形と重なり", check_number_form),
    ("取って代わった先が実在する", check_supersede_target_exists),
    ("仕様書に宣言がある", check_specs_declare),
    ("条件が指す要件が実在する", check_conditions_point_to_requirements),
    ("条件に印がある", check_conditions_have_marks),
    ("要件に書かない語", check_forbidden_words),
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


def count_marks(conditions):
    """条件の行の一覧から、表の 1 行ぶんの数を数える。

    返すのは (条件の行, 要件に結んだ行, 無しの行, これからの行, 指す番号の集合)。
    番号と「これから」を併記した行は、結んだ行とこれからの行の両方に数える
    （「条件に印がある」の項目の数え方と同じ）。
    """
    linked = none = pending = 0
    numbers = set()
    for condition in conditions:
        mark = condition["mark"]
        if mark is None:
            continue
        if MARK_NONE_RE.match(mark):
            none += 1
            continue
        found, _ = numbers_in_mark(mark)
        if found:
            linked += 1
            numbers.update(found)
        if MARK_PENDING_RE.search(mark):
            pending += 1
    return len(conditions), linked, none, pending, numbers


def spec_table_lines(state):
    """仕様書ごとの条件の行と印の内訳を、Markdown の表の行で返す。"""
    header = "| 仕様書 | 条件の行 | 要件に結んだ行 | 無しの行 | これからの行 | 指す要件の番号の種類 |"
    lines = [
        "## 条件の印の対応表",
        "",
        "宣言が「あり」の仕様書（%d 本）" % state["specs_read"],
        "",
        header,
        "|---|---|---|---|---|---|",
    ]
    totals = [0, 0, 0, 0]
    all_numbers = set()
    off = []
    missing = []
    for spec in state["specs"]:
        declaration = spec["declaration"]
        if declaration != DECLARATION_ON:
            if declaration_problem(declaration) is None:
                off.append((spec["name"], DECLARATION_OFF_RE.match(declaration).group(1).strip()))
            else:
                missing.append((spec["name"], declaration_problem(declaration)))
            continue
        rows, linked, none, pending, numbers = count_marks(spec["conditions"])
        for index, value in enumerate((rows, linked, none, pending)):
            totals[index] += value
        all_numbers |= numbers
        lines.append(
            "| %s | %d | %d | %d | %d | %d |"
            % (spec["name"], rows, linked, none, pending, len(numbers))
        )
    lines.append(
        "| 合計 | %d | %d | %d | %d | %d |"
        % (totals[0], totals[1], totals[2], totals[3], len(all_numbers))
    )
    lines += ["", "宣言が「対象外」の仕様書（%d 本）" % len(off), ""]
    if off:
        lines += ["| 仕様書 | 対象外の理由 |", "|---|---|"]
        lines += ["| %s | %s |" % (name, reason) for name, reason in off]
    else:
        lines.append("無し")
    if missing:
        lines += ["", "宣言の足りない仕様書（%d 本）" % len(missing), ""]
        lines += ["| 仕様書 | 足りないもの |", "|---|---|"]
        lines += ["| %s | %s |" % (name, problem) for name, problem in missing]
    reasoned = sum(1 for t in state["plain_tests"] if plain_test_problem(t["first_line"]) is None)
    lines += [
        "",
        "番号を名前に持たないテスト: %d 本（うち docstring の 1 行目に理由があるもの %d 本）"
        % (len(state["plain_tests"]), reasoned),
    ]
    return lines


def run(root, spec_dir=None, spec_table=False):
    """検査を 1 回走らせて終了コードを返す。"""
    if spec_table and spec_dir is None:
        print("ERROR: --spec-table は --spec-dir と一緒に渡す", file=sys.stderr)
        return 2
    try:
        state = load_state(root, spec_dir)
    except InputError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    print("# %s（対象: %s）" % (CHECK_TITLE, shown_root(root)))
    failed = 0
    skipped = 0
    for name, result, detail, lines in evaluate(state):
        print("%s %s: %s" % (result, name, detail))
        if result == RESULT_SKIP:
            skipped += 1
        if result == RESULT_FAIL:
            failed += 1
            for line in lines:
                print("    %s" % line)

    if spec_table:
        # 表は合否にかかわらず出す。落ちたときこそ、どこの数が合わないかを見たいため。
        print()
        for line in spec_table_lines(state):
            print(line)
        print()

    if failed:
        print("NG 不合格 %d 項目（省略 %d 項目）" % (failed, skipped))
        return 1

    conditions = state["conditions"]
    print(
        "OK 要件 %d 件（うち取って代わられた %d 件）、番号つきのテスト %d 件、"
        "番号なしのテスト %d 本、実装の目印 %d 件、条件の行 %s（省略 %d 項目）"
        % (
            len(state["requirements"]),
            len(state["superseded"]),
            len(state["tests"]),
            len(state["plain_tests"]),
            len(state["markers"]),
            "読んでいない" if conditions is None else "%d 件" % len(conditions),
            skipped,
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
    parser.add_argument(
        "--spec-dir",
        default=None,
        help="開発の仕様書の置き場。渡すと、仕様書の宣言と条件の行を見る 3 項目が走る。"
        "渡さなければその 3 項目は省略になる（既定: 渡さない）",
    )
    parser.add_argument(
        "--spec-table",
        action="store_true",
        help="--spec-dir と一緒に渡す。項目の出力の後に、仕様書ごとの条件の行の数と"
        "印の内訳を Markdown の表で出す",
    )
    args = parser.parse_args(argv)
    return run(args.root, args.spec_dir, args.spec_table)


if __name__ == "__main__":
    sys.exit(main())
