"""clone した人が最初に確かめること。口が揃っているかを見る。

要件 1 件につきテストを 1 本置く。もとは 2 本で見ていたものを、返り値に現れる 1 か所ごとに割った。
起動したサーバーが開く操作と資源で 2 本、`accord --list` の終了コードと出す名前と重なりで 3 本、
サーバーと操作の説明が依頼の言葉を持つかで 4 本である。
"""

from __future__ import annotations

import asyncio
import subprocess
import sys

from accord.server.app import ONTOLOGY_URI, TOOL_NAMES, create_server

EXPECTED_TOOLS = set(TOOL_NAMES)


def _listed_names(settings) -> list[str]:
    """`accord --list` を呼び、終了コードと出力の行を返す。"""
    completed = subprocess.run(
        [sys.executable, "-m", "accord", "--data", str(settings.source_dir), "--presentations", str(settings.presentations_dir), "--list"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.split()


# ---------------------------------------------------------------- 起動して開く口


def test_REQ_489_the_server_opens_eighteen_tools(settings) -> None:
    """サンプルだけで起動したサーバーが、決めを読むから書き出すまでのツール 18 本を開く。"""
    server = create_server(settings)

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    assert len(tools) == 18
    assert {
        "rename_heading",
        "add_section",
        "remove_section",
        "move_section",
        "set_disclosure",
    } <= EXPECTED_TOOLS


def test_REQ_337_the_server_opens_one_resource(settings) -> None:
    """サンプルだけで起動したサーバーが、型とルールの定義を返す資源を 1 本だけ開く。"""
    server = create_server(settings)

    resources = asyncio.run(server.list_resources())

    assert [str(resource.uri) for resource in resources] == [ONTOLOGY_URI]


# ---------------------------------------------------------------- 開く口の一覧


def test_REQ_338_listing_the_names_exits_zero(settings) -> None:
    """`accord --list` が終了コード 0 で終わる。"""
    completed = subprocess.run(
        [sys.executable, "-m", "accord", "--data", str(settings.source_dir), "--presentations", str(settings.presentations_dir), "--list"],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_REQ_339_listing_the_names_prints_every_name(settings) -> None:
    """`accord --list` が、サーバーが開くツール 18 本と資源 1 本の名前をすべて出す。"""
    lines = _listed_names(settings)

    assert set(lines) == EXPECTED_TOOLS | {ONTOLOGY_URI}


def test_REQ_340_listing_the_names_prints_no_duplicate(settings) -> None:
    """`accord --list` が、同じ名前を 2 度出さない（19 行で、重なりが無い）。"""
    lines = _listed_names(settings)

    assert len(lines) == 19
    assert len(lines) == len(set(lines))


# ---------------------------------------------------------------- 説明の言葉


def _description(settings, name: str) -> str:
    tools = asyncio.run(create_server(settings).list_tools())
    return next(tool.description for tool in tools if tool.name == name) or ""


def test_REQ_463_the_server_says_not_to_open_the_source_files(settings) -> None:
    """サーバーの説明に、正本のファイルを直接開かずに accord の操作で読み書きすることが書いてある。"""
    server = create_server(settings)

    assert "正本のファイルを直接開かず、accord の操作で読み書きする" in server.instructions


def test_REQ_464_the_material_description_says_when_to_call_it(settings) -> None:
    """材料の取り出しの説明が、応募文とプロフィールと職務経歴書を書く前に呼ぶ操作であることを書く。"""
    description = _description(settings, "assemble_material")

    assert description.startswith("応募文・プロフィール・職務経歴書を書く前に、これを 1 回呼ぶ")


def test_REQ_465_the_record_fact_description_says_when_to_call_it(settings) -> None:
    """事実の登記の説明が、実績と経歴の事実を書き足すときに呼ぶ操作であることを書く。"""
    description = _description(settings, "record_fact")

    assert description.startswith("実績や経歴の事実を書き足すときに呼ぶ")


def test_REQ_487_the_server_says_structure_changes_go_through_accord(settings) -> None:
    """サーバーの説明に、見出しの変更・節の追加・削除・移動・公開可否の変更も accord の操作で行うことが書いてある。"""
    server = create_server(settings)

    assert "見出しの変更と節の追加と節の削除と節の移動と公開可否の変更も accord の操作で行う" in server.instructions
    for name in ("rename_heading", "add_section", "remove_section", "move_section", "set_disclosure"):
        assert name in server.instructions
