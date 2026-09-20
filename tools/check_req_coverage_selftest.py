#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""突合検査そのものを試す（審判が本当に落ちるかを確かめる）。

見るのは「検査が合格を出せるか」ではなく「**わざと壊した入力で本当に不合格を返すか**」
である。落ちない審判は審判ではないので、壊した入力のケースを項目ごとに置く。

ケースは 1 件ずつ、一時ディレクトリに小さな木（`docs/specs/`・`tests/`・`src/` に
要件・テスト・実装のファイルを組んだもの）を作り、その木に検査を当てて、終了コードと
落ちるはずの項目名の `FAIL` 行を突き合わせる。木は毎回作って毎回捨てるので、
どこで実行しても、外側の git の状態に左右されない。

見本は別ファイルにせず、この中に文字列で持つ（見本を別に置くと、検査の改訂と見本の
同期が切れる）。標準ライブラリだけを使い、`accord` パッケージを import しない。

使い方:
  python3 tools/check_req_coverage_selftest.py

終了コード: 0（全ケースが期待どおり）／1（食い違いが 1 件以上）
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHECK_SCRIPT = SCRIPT_DIR / "check_req_coverage.py"

FAIL_LINE_RE = re.compile(r"^FAIL ([^:]+):", re.MULTILINE)

# 木の中のファイルの置き場。
GUIDE_FILE = "docs/specs/README.md"
SPEC_FILE = "docs/specs/writing.md"
SECOND_SPEC_FILE = "docs/specs/reading.md"
TEST_FILE = "tests/test_writing.py"
SRC_FILE = "src/example/writing.py"

# 項目名（検査の出力に出るものと同じ文字列）。
ITEM_TESTS_EXIST = "要件にテストがある"
ITEM_TESTS_POINT = "テスト名の番号が要件にある"
ITEM_SUPERSEDED_TESTS = "取って代わられた番号のテストが残っていない"
ITEM_MARKERS = "実装の目印が有効な要件を指す"
ITEM_NUMBER_FORM = "番号の形と重なり"
ITEM_SUPERSEDE_TARGET = "取って代わった先が実在する"


# ---------------------------------------------------------------------------
# 見本（木に置くファイルの中身）
# ---------------------------------------------------------------------------

GOOD_SPEC = """\
# 設定の読み込み

## REQ-001
常に、accord は正本の置き場を設定ファイルから読む。

- 関係するファイル: `src/example/writing.py`
- 検証手順: `pytest tests/test_writing.py -k REQ_001`

## REQ-002
もし正本の置き場が見つからないなら、accord は読んだ設定ファイルの場所を添えて断る。

- 関係するファイル: `src/example/writing.py`
- 検証手順: `pytest tests/test_writing.py -k REQ_002`

## REQ-003

- status: superseded by REQ-002

もし正本の置き場が見つからないなら、accord は断る。
"""

GOOD_TESTS = """\
def test_REQ_001_reads_the_source_location():
    assert True


def test_REQ_002_refuses_with_the_settings_path():
    assert True
"""

GOOD_SRC = """\
# spec: REQ-001
def read_source_location():
    return "source"
"""

# 番号を持たない、ただのテストだけがある木に置く。
PLAIN_TEST = """\
def test_it_runs():
    assert True
"""

# 案内。ここに書いた番号は数えない（`README.md` は読まないため）。
GUIDE_WITH_NUMBERS = """\
# 要件の案内

書き方の例です。

## REQ-014
常に、accord は例として書いたこの行を要件として数えない。
"""

# コードの囲みの中にだけ番号の見出しがある要件のファイル。ここも数えない。
SPEC_WITH_FENCED_EXAMPLE = """\
# 書き方の例

要件は次の形で書きます。

```markdown
## REQ-014
常に、accord はコードの囲みの中を要件として数えない。
```
"""


# ``` の囲みの中にチルダ 3 つの行がある要件のファイル。囲みは同じ記号でしか閉じない。
# 囲みの中の REQ-014 は数えず、囲みの後ろの REQ-001 は数える。
SPEC_WITH_MIXED_FENCES = """\
# 書き方の例と要件

```markdown
~~~
## REQ-014
常に、accord は囲みの中のこの行を要件として数えない。
```

## REQ-001
常に、accord は正本の置き場を設定ファイルから読む。
"""

# 囲みを閉じ忘れた要件のファイル。後ろを黙って読み飛ばさず、入力の誤りとして止まる。
SPEC_WITH_UNCLOSED_FENCE = """\
# 閉じ忘れ

```markdown
## REQ-014

## REQ-001
常に、accord は正本の置き場を設定ファイルから読む。
"""

# 下の階層に置いた README.md。読まないのは docs/specs/ 直下の案内だけなので、これは読む。
NESTED_README_FILE = "docs/specs/sub/README.md"
NESTED_README_WITH_REQUIREMENT = """\
# 下の階層の要件

## REQ-050
常に、accord は下の階層に置いたファイルも要件として読む。
"""


def good_tree():
    """要件 2 件・取って代わられた要件 1 件に、テストと目印がそろった木。"""
    return {
        SPEC_FILE: GOOD_SPEC,
        TEST_FILE: GOOD_TESTS,
        SRC_FILE: GOOD_SRC,
    }


def changed(updates):
    """そろった木の一部を差し替えた（または 1 ファイル足した）木を作る。"""
    tree = good_tree()
    tree.update(updates)
    return tree


def without(name):
    """そろった木から 1 ファイルを抜いた木を作る。"""
    tree = good_tree()
    tree.pop(name)
    return tree


# ---------------------------------------------------------------------------
# ケースの表
#
# (ケース名, 木, 期待の終了コード, 落ちるはずの項目, 落ちてはいけない項目, 含まれる語)
# ---------------------------------------------------------------------------

CASES = [
    # 通るはずの木。
    (
        "要件 0 件",
        {TEST_FILE: PLAIN_TEST},
        0,
        (),
        (),
        "OK 要件 0 件",
    ),
    (
        "要件とテストと目印がそろった木",
        good_tree(),
        0,
        (),
        (),
        "OK 要件 3 件（うち取って代わられた 1 件）",
    ),
    (
        "目印が 0 件の木",
        without(SRC_FILE),
        0,
        (),
        (),
        "実装の目印 0 件",
    ),
    (
        "案内とコードの囲みの中の番号は数えない",
        {
            GUIDE_FILE: GUIDE_WITH_NUMBERS,
            SPEC_FILE: SPEC_WITH_FENCED_EXAMPLE,
            TEST_FILE: PLAIN_TEST,
        },
        0,
        (),
        (),
        "OK 要件 0 件",
    ),
    (
        "種類の違う囲みの記号では閉じない",
        {
            SPEC_FILE: SPEC_WITH_MIXED_FENCES,
            TEST_FILE: "def test_REQ_001_reads_the_source_location():\n    assert True\n",
        },
        0,
        (),
        (),
        "OK 要件 1 件",
    ),
    # 落ちるはずの木（1 点だけ壊す）。
    (
        "テストの無い要件を足す",
        changed({SPEC_FILE: GOOD_SPEC + "\n## REQ-004\n常に、accord はこの要件のテストを持たない。\n"}),
        1,
        (ITEM_TESTS_EXIST,),
        (ITEM_TESTS_POINT, ITEM_NUMBER_FORM),
        "REQ-004",
    ),
    (
        "要件に無い番号のテスト名",
        changed({TEST_FILE: GOOD_TESTS + "\n\ndef test_REQ_009_not_in_the_specs():\n    assert True\n"}),
        1,
        (ITEM_TESTS_POINT,),
        (ITEM_TESTS_EXIST, ITEM_NUMBER_FORM),
        "REQ-009",
    ),
    (
        "取って代わられた番号のテストを残す",
        changed({TEST_FILE: GOOD_TESTS + "\n\ndef test_REQ_003_old_behaviour():\n    assert True\n"}),
        1,
        (ITEM_SUPERSEDED_TESTS,),
        (ITEM_TESTS_EXIST, ITEM_TESTS_POINT),
        "REQ-003",
    ),
    (
        "要件に無い番号の目印",
        changed({SRC_FILE: '# spec: REQ-009\ndef read_source_location():\n    return "source"\n'}),
        1,
        (ITEM_MARKERS,),
        (ITEM_NUMBER_FORM,),
        "REQ-009",
    ),
    (
        "取って代わられた番号の目印",
        changed({SRC_FILE: '# spec: REQ-003\ndef read_source_location():\n    return "source"\n'}),
        1,
        (ITEM_MARKERS,),
        (ITEM_NUMBER_FORM,),
        "REQ-003",
    ),
    (
        "2 桁の見出し",
        changed(
            {
                SPEC_FILE: GOOD_SPEC + "\n## REQ-04\n常に、accord は 2 桁の番号を許さない。\n",
                TEST_FILE: GOOD_TESTS + "\n\ndef test_REQ_04_two_digits():\n    assert True\n",
            }
        ),
        1,
        (ITEM_NUMBER_FORM,),
        (ITEM_TESTS_EXIST, ITEM_TESTS_POINT),
        "3 桁で書く",
    ),
    (
        "2 桁のテスト名",
        changed({TEST_FILE: GOOD_TESTS + "\n\ndef test_REQ_01_two_digits():\n    assert True\n"}),
        1,
        (ITEM_NUMBER_FORM,),
        (ITEM_TESTS_EXIST,),
        "3 桁で書く",
    ),
    (
        "同じ番号の見出し 2 つ",
        changed(
            {SECOND_SPEC_FILE: "# 重なり\n\n## REQ-002\n常に、accord は同じ番号の見出しを許さない。\n"}
        ),
        1,
        (ITEM_NUMBER_FORM,),
        (ITEM_TESTS_EXIST, ITEM_TESTS_POINT),
        "同じ番号の見出し",
    ),
    (
        "指す先の無い取って代わられた印",
        changed({SPEC_FILE: GOOD_SPEC.replace("superseded by REQ-002", "superseded by REQ-099")}),
        1,
        (ITEM_SUPERSEDE_TARGET,),
        (ITEM_TESTS_EXIST, ITEM_NUMBER_FORM),
        "REQ-099",
    ),
    (
        "4 桁の見出し",
        changed({SPEC_FILE: GOOD_SPEC + "\n## REQ-1006\n常に、accord は例を示す。\n",
                 TEST_FILE: GOOD_TESTS + "\n\ndef test_REQ_1006_example():\n    assert True\n"}),
        1,
        (ITEM_NUMBER_FORM,),
        (ITEM_TESTS_EXIST,),
        "桁に収まる番号を振り直す",
    ),
    (
        "下の階層の README.md は要件として読む",
        changed({NESTED_README_FILE: NESTED_README_WITH_REQUIREMENT}),
        1,
        (ITEM_TESTS_EXIST,),
        (ITEM_NUMBER_FORM,),
        "REQ-050",
    ),
    # 入力が読めない木。
    (
        "テストの置き場が無い",
        {SPEC_FILE: GOOD_SPEC},
        2,
        (),
        (),
        "テストの置き場が無い",
    ),
    (
        "コードの囲みを閉じ忘れている",
        {SPEC_FILE: SPEC_WITH_UNCLOSED_FENCE, TEST_FILE: PLAIN_TEST},
        2,
        (),
        (),
        "コードの囲みが閉じていない",
    ),
]


# ---------------------------------------------------------------------------
# 骨組み
# ---------------------------------------------------------------------------


def build_tree(base, files):
    """一時ディレクトリに木を組む。"""
    for relative_path, text in files.items():
        path = Path(base) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def run_check(root):
    """検査本体を別プロセスで起動し、(終了コード, 出力) を返す。

    import して関数を呼ぶのではなく別プロセスで起動するのは、終了コードと標準出力という
    「呼ぶ側が実際に見るもの」をそのまま突き合わせるためである。
    """
    completed = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout + completed.stderr


def run_case(name, files, expected_code, must_fail, must_not_fail, expected_word):
    """1 ケースを走らせて、期待どおりなら True を返す。"""
    with tempfile.TemporaryDirectory() as work:
        build_tree(work, files)
        code, output = run_check(work)

    failed_items = FAIL_LINE_RE.findall(output)

    problems = []
    if code != expected_code:
        problems.append("終了コードが %d（期待 %d）" % (code, expected_code))
    for item in must_fail:
        if item not in failed_items:
            problems.append("「FAIL %s」の行が無い" % item)
    for item in must_not_fail:
        if item in failed_items:
            problems.append("落ちてはいけない項目が落ちた: %s" % item)
    if expected_word and expected_word not in output:
        problems.append("出力に「%s」が無い" % expected_word)

    if problems:
        print("NG %s — %s" % (name, "、".join(problems)))
        print("--- 実際の出力 ---")
        print(output.rstrip())
        print("------------------")
        return False

    if failed_items:
        print("OK %s — 終了コード %d、FAIL: %s" % (name, code, " / ".join(failed_items)))
    else:
        print("OK %s — 終了コード %d、FAIL の行なし" % (name, code))
    return True


def main():
    if not CHECK_SCRIPT.is_file():
        print("ERROR: 検査本体が見つからない: %s" % CHECK_SCRIPT, file=sys.stderr)
        return 1
    failures = 0
    for case in CASES:
        if not run_case(*case):
            failures += 1
    print("ケース %d 件・食い違い %d 件" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
