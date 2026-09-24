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

import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHECK_SCRIPT = SCRIPT_DIR / "check_req_coverage.py"

FAIL_LINE_RE = re.compile(r"^FAIL ([^:]+):", re.MULTILINE)
SKIP_LINE_RE = re.compile(r"^SKIP ([^:]+):", re.MULTILINE)

# 木の中のファイルの置き場。
GUIDE_FILE = "docs/specs/README.md"
SPEC_FILE = "docs/specs/writing.md"
SECOND_SPEC_FILE = "docs/specs/reading.md"
TEST_FILE = "tests/test_writing.py"
SRC_FILE = "src/example/writing.py"

# 開発の仕様書の置き場（`--spec-dir` に渡す）と、その中のファイル。
DEV_SPEC_DIR = "dev_specs"
DEV_SPEC_FILE = DEV_SPEC_DIR + "/20260101_01_example_spec.md"
DEV_SPEC_NO_DECL_FILE = DEV_SPEC_DIR + "/20260103_03_no_declaration_spec.md"
DEV_SPEC_OFF_FILE = DEV_SPEC_DIR + "/20260104_04_declared_off_spec.md"

# 項目名（検査の出力に出るものと同じ文字列）。
ITEM_TESTS_EXIST = "要件にテストがある"
ITEM_TESTS_POINT = "テスト名の番号が要件にある"
ITEM_SUPERSEDED_TESTS = "取って代わられた番号のテストが残っていない"
ITEM_MARKERS = "実装の目印が有効な要件を指す"
ITEM_NUMBER_FORM = "番号の形と重なり"
ITEM_SUPERSEDE_TARGET = "取って代わった先が実在する"
ITEM_CONDITION_TARGET = "条件が指す要件が実在する"
ITEM_CONDITION_MARK = "条件に印がある"
ITEM_FORBIDDEN_WORDS = "要件に書かない語"

# 要件に書かない語の一覧が、案内のどの節の語と一致するべきか。
REAL_GUIDE = SCRIPT_DIR.parent / "docs" / "specs" / "README.md"
FORBIDDEN_SECTION_HEADING = "## 要件に書かないこと"


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

# 開発の仕様書の見本。宣言の行を持ち、条件の行それぞれの末尾に印がある。印は 3 つの形を
# 一通り使い、番号は並べた形と範囲の形の両方で書く。太字の段落の下の内訳は 2 文字字下げ
# してあるので、条件の行には数えない。コードの囲みの中と、「判定質問で見る条件」の節も数えない。
GOOD_DEV_SPEC = """\
# 見本の開発の仕様書（2026-01-01）

## 受け入れ条件

条件の印: あり

### 機械検査で見る条件

- 設定ファイルを渡して呼ぶと、正本の置き場を読むこと。 要件: REQ-001
- 置き場が見つからないときに、設定ファイルの場所を添えて断ること。 要件: REQ-002
- `pytest` の終了コードが 0 であること。 要件: 無し（テスト全体の合格）
- 書きの操作が、欠けた欄を挙げて断ること。 要件: これから（書きの操作）
- 材料の取り出しが、公開不可の節を落として断ること。 要件: REQ-002・これから（材料の取り出し）

| 条件 | 検証手順 | 要件 |
|---|---|---|
| 正本を 1 バイトも書き換えないこと | 呼び出しの前後で指紋を突き合わせる | 要件: REQ-001・REQ-002 |
| 公開境界の検査が通ること | 終了コードが 0 | 要件: 無し（公開境界） |

**2 つをまとめて見ること。** 次の内訳を 1 回の実行で確かめる。 要件: REQ-001〜REQ-002

  - 置き場を読むこと。
  - 読めないときに断ること。

```markdown
- 囲みの中のこの行は条件の行に数えない。
```

### 判定質問で見る条件

- この節の箇条書きは条件の行に数えない。
"""

# 条件の節を持たない開発の仕様書。宣言はあるので読むが、条件の行は 0 件になる。
DEV_SPEC_WITHOUT_CONDITIONS = """\
# 条件の節を持たない仕様書（2026-01-02）

## 受け入れ条件

条件の印: あり

## 目的

- ここは条件の節ではないので、条件の行に数えない。
"""

# 宣言の行を持たない開発の仕様書。印の無い条件があっても、検査は読み飛ばす。
DEV_SPEC_WITHOUT_DECLARATION = """\
# 宣言の行を持たない仕様書（2026-01-03）

## 受け入れ条件

### 機械検査で見る条件

- この行には印が無いが、宣言の行が無いので読み飛ばされる。
- この行にも印が無い。
"""

# 「対象外」を宣言した開発の仕様書。これも読み飛ばす。
DEV_SPEC_DECLARED_OFF = """\
# 対象外を宣言した仕様書（2026-01-04）

## 受け入れ条件

条件の印: 対象外（外から見える振る舞いを変えない単位なので、指せる要件を持たない）

### 機械検査で見る条件

- この行には印が無いが、対象外を宣言しているので読み飛ばされる。
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
    # 要件に書かない語。
    (
        "要件文に要件に書かない語がある",
        changed(
            {
                SPEC_FILE: GOOD_SPEC.replace(
                    "常に、accord は正本の置き場を設定ファイルから読む。",
                    "常に、accord は正本の置き場を必要に応じて設定ファイルから読む。",
                )
            }
        ),
        1,
        (ITEM_FORBIDDEN_WORDS,),
        (ITEM_TESTS_EXIST, ITEM_NUMBER_FORM),
        "REQ-001（docs/specs/writing.md:4 の要件文）: 「必要に応じて」を含む",
    ),
    (
        "取って代わられた要件の要件文も見る",
        changed(
            {
                SPEC_FILE: GOOD_SPEC.replace(
                    "もし正本の置き場が見つからないなら、accord は断る。",
                    "もし正本の置き場が見つからないなら、accord は断ることが望ましい。",
                )
            }
        ),
        1,
        (ITEM_FORBIDDEN_WORDS,),
        (ITEM_SUPERSEDED_TESTS, ITEM_SUPERSEDE_TARGET),
        "「〜が望ましい」を含む",
    ),
    (
        "要件文でない箇条の語は数えない",
        changed(
            {
                SPEC_FILE: GOOD_SPEC.replace(
                    "- 関係するファイル: `src/example/writing.py`\n- 検証手順: `pytest tests/test_writing.py -k REQ_001`",
                    "- 関係するファイル: `src/example/writing.py`（可能であれば分ける）\n"
                    "- 検証手順: `pytest tests/test_writing.py -k REQ_001`",
                )
            }
        ),
        0,
        (),
        (ITEM_FORBIDDEN_WORDS,),
        "要件文 3 件のどれにも",
    ),
    # 条件の行の印（`--spec-dir` を渡したときだけ走る 2 項目）。
    (
        "条件の行に印がそろった仕様書（3 つの印と、並べた番号と範囲）",
        changed({DEV_SPEC_FILE: GOOD_DEV_SPEC}),
        0,
        (),
        (),
        "条件の行 8 件すべてに印がある（要件に結んだ 5・無し 2・これから 2。"
        "うち 1 件は番号と「これから」を併記）",
        DEV_SPEC_DIR,
    ),
    (
        "範囲で書いた印は、間の番号まで広げて見る",
        changed({DEV_SPEC_FILE: GOOD_DEV_SPEC}),
        0,
        (),
        (),
        "範囲で書いた印 1 件は、間の番号まで広げて確かめた",
        DEV_SPEC_DIR,
    ),
    (
        "宣言の行が無い仕様書は読み飛ばす",
        changed(
            {
                DEV_SPEC_FILE: GOOD_DEV_SPEC,
                DEV_SPEC_NO_DECL_FILE: DEV_SPEC_WITHOUT_DECLARATION,
            }
        ),
        0,
        (),
        (ITEM_CONDITION_MARK,),
        "読んだ仕様書 1 本、宣言が無いか対象外で読まなかった仕様書 1 本",
        DEV_SPEC_DIR,
    ),
    (
        "「対象外」を宣言した仕様書も読み飛ばす",
        changed(
            {
                DEV_SPEC_FILE: GOOD_DEV_SPEC,
                DEV_SPEC_OFF_FILE: DEV_SPEC_DECLARED_OFF,
            }
        ),
        0,
        (),
        (ITEM_CONDITION_MARK,),
        "読んだ仕様書 1 本、宣言が無いか対象外で読まなかった仕様書 1 本",
        DEV_SPEC_DIR,
    ),
    (
        "範囲の真ん中の欠番で落ちる",
        {
            SPEC_FILE: GOOD_SPEC
            + "\n## REQ-005\n常に、accord は範囲を広げる試しのためにこの要件を持つ。\n",
            TEST_FILE: GOOD_TESTS
            + "\n\ndef test_REQ_005_for_range_expansion():\n    assert True\n",
            SRC_FILE: GOOD_SRC,
            DEV_SPEC_FILE: GOOD_DEV_SPEC.replace(
                "要件: REQ-001〜REQ-002", "要件: REQ-001〜REQ-005"
            ),
        },
        1,
        (ITEM_CONDITION_TARGET,),
        (ITEM_CONDITION_MARK,),
        "REQ-004",
        DEV_SPEC_DIR,
    ),
    (
        "範囲の終わりが始まりより小さい",
        changed(
            {
                DEV_SPEC_FILE: GOOD_DEV_SPEC.replace(
                    "要件: REQ-001〜REQ-002", "要件: REQ-002〜REQ-001"
                )
            }
        ),
        1,
        (ITEM_CONDITION_TARGET,),
        (ITEM_CONDITION_MARK,),
        "終わりが始まりより小さい",
        DEV_SPEC_DIR,
    ),
    (
        "条件の節を持たない仕様書だけ",
        changed({DEV_SPEC_FILE: DEV_SPEC_WITHOUT_CONDITIONS}),
        0,
        (),
        (),
        "条件の行 0 件すべてに印がある",
        DEV_SPEC_DIR,
    ),
    (
        "実在しない番号を印に書く",
        changed(
            {
                DEV_SPEC_FILE: GOOD_DEV_SPEC.replace(
                    "正本の置き場を読むこと。 要件: REQ-001",
                    "正本の置き場を読むこと。 要件: REQ-099",
                )
            }
        ),
        1,
        (ITEM_CONDITION_TARGET,),
        (ITEM_CONDITION_MARK,),
        "REQ-099",
        DEV_SPEC_DIR,
    ),
    (
        "条件の印を 1 つ消す",
        changed(
            {
                DEV_SPEC_FILE: GOOD_DEV_SPEC.replace(
                    "設定ファイルの場所を添えて断ること。 要件: REQ-002",
                    "設定ファイルの場所を添えて断ること。",
                )
            }
        ),
        1,
        (ITEM_CONDITION_MARK,),
        (ITEM_CONDITION_TARGET,),
        "条件の行に印が無い",
        DEV_SPEC_DIR,
    ),
    (
        "取って代わられた番号を印に書く",
        changed(
            {
                DEV_SPEC_FILE: GOOD_DEV_SPEC.replace(
                    "正本の置き場を読むこと。 要件: REQ-001",
                    "正本の置き場を読むこと。 要件: REQ-003",
                )
            }
        ),
        1,
        (ITEM_CONDITION_TARGET,),
        (ITEM_CONDITION_MARK,),
        "取って代わられている",
        DEV_SPEC_DIR,
    ),
    (
        "印の形が 3 つのどれでもない",
        changed(
            {
                DEV_SPEC_FILE: GOOD_DEV_SPEC.replace(
                    "要件: 無し（テスト全体の合格）", "要件: なし（テスト全体の合格）"
                )
            }
        ),
        1,
        (ITEM_CONDITION_MARK,),
        (ITEM_CONDITION_TARGET,),
        "印の形が違う",
        DEV_SPEC_DIR,
    ),
    (
        "仕様書の置き場を渡さないと 2 項目が省略になる",
        changed({DEV_SPEC_FILE: GOOD_DEV_SPEC}),
        0,
        (),
        (),
        "条件の行 読んでいない",
        None,
        (ITEM_CONDITION_TARGET, ITEM_CONDITION_MARK),
    ),
    # 入力が読めない木。
    (
        "仕様書の置き場が無い",
        good_tree(),
        2,
        (),
        (),
        "仕様書の置き場が見つからない",
        "dev_specs_typo",
    ),
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


def run_check(root, spec_dir=None):
    """検査本体を別プロセスで起動し、(終了コード, 出力) を返す。

    import して関数を呼ぶのではなく別プロセスで起動するのは、終了コードと標準出力という
    「呼ぶ側が実際に見るもの」をそのまま突き合わせるためである。

    `spec_dir` は木の中の相対の置き場。渡さなければ `--spec-dir` を付けずに起動し、
    条件を見る 2 項目が省略になることを確かめられる。
    """
    command = [sys.executable, str(CHECK_SCRIPT), "--root", str(root)]
    if spec_dir is not None:
        command += ["--spec-dir", str(Path(root) / spec_dir)]
    completed = subprocess.run(command, capture_output=True, text=True)
    return completed.returncode, completed.stdout + completed.stderr


def run_case(
    name,
    files,
    expected_code,
    must_fail,
    must_not_fail,
    expected_word,
    spec_dir=None,
    must_skip=(),
):
    """1 ケースを走らせて、期待どおりなら True を返す。"""
    with tempfile.TemporaryDirectory() as work:
        build_tree(work, files)
        code, output = run_check(work, spec_dir)

    failed_items = FAIL_LINE_RE.findall(output)
    skipped_items = SKIP_LINE_RE.findall(output)

    problems = []
    if code != expected_code:
        problems.append("終了コードが %d（期待 %d）" % (code, expected_code))
    for item in must_fail:
        if item not in failed_items:
            problems.append("「FAIL %s」の行が無い" % item)
    for item in must_not_fail:
        if item in failed_items:
            problems.append("落ちてはいけない項目が落ちた: %s" % item)
    for item in must_skip:
        if item not in skipped_items:
            problems.append("「SKIP %s」の行が無い" % item)
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


def guide_forbidden_words():
    """案内の「要件に書かないこと」の節から、「」で囲んだ語を並びどおりに拾う。"""
    words = []
    inside = False
    for line in REAL_GUIDE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            inside = line.strip() == FORBIDDEN_SECTION_HEADING
            continue
        if inside:
            words.extend(re.findall(r"「([^」]+)」", line))
    return words


def check_words_agree_with_guide():
    """検査の持つ語の一覧が、案内の「要件に書かないこと」の節の語と一致するか。"""
    spec = importlib.util.spec_from_file_location("check_req_coverage", CHECK_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    in_check = list(module.FORBIDDEN_WORDS)
    try:
        in_guide = guide_forbidden_words()
    except OSError as exc:
        print("NG 案内を読めない: %s（%s）" % (REAL_GUIDE, exc))
        return False
    if in_check == in_guide:
        print("OK 要件に書かない語 %d 語が、案内の「要件に書かないこと」の節と一致する" % len(in_check))
        return True
    print(
        "NG 要件に書かない語が案内と食い違う — 検査: %s、案内: %s" % (in_check, in_guide)
    )
    return False


def main():
    if not CHECK_SCRIPT.is_file():
        print("ERROR: 検査本体が見つからない: %s" % CHECK_SCRIPT, file=sys.stderr)
        return 1
    failures = 0
    for case in CASES:
        if not run_case(*case):
            failures += 1
    if not check_words_agree_with_guide():
        failures += 1
    print("ケース %d 件・食い違い %d 件" % (len(CASES) + 1, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
