"""clone した人が最初に確かめること。口が揃っているかを見る。

要件 1 件につきテストを 1 本置く。もとは 2 本で見ていたものを、返り値に現れる 1 か所ごとに割った。
起動したサーバーが開く操作と資源で 2 本、`accord --list` の終了コードと出す名前と重なりで 3 本である。
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
        [sys.executable, "-m", "accord", "--config", str(settings.config_path), "--list"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.split()


# ---------------------------------------------------------------- 起動して開く口


def test_REQ_336_the_server_opens_seven_tools(settings) -> None:
    """サンプルだけで起動したサーバーが、決めを読むから整合を検査するまでのツール 7 本を開く。"""
    server = create_server(settings)

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    assert len(tools) == 7


def test_REQ_337_the_server_opens_one_resource(settings) -> None:
    """サンプルだけで起動したサーバーが、型とルールの定義を返す資源を 1 本だけ開く。"""
    server = create_server(settings)

    resources = asyncio.run(server.list_resources())

    assert [str(resource.uri) for resource in resources] == [ONTOLOGY_URI]


# ---------------------------------------------------------------- 開く口の一覧


def test_REQ_338_listing_the_names_exits_zero(settings) -> None:
    """`accord --list` が終了コード 0 で終わる。"""
    completed = subprocess.run(
        [sys.executable, "-m", "accord", "--config", str(settings.config_path), "--list"],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_REQ_339_listing_the_names_prints_every_name(settings) -> None:
    """`accord --list` が、サーバーが開くツール 7 本と資源 1 本の名前をすべて出す。"""
    lines = _listed_names(settings)

    assert set(lines) == EXPECTED_TOOLS | {ONTOLOGY_URI}


def test_REQ_340_listing_the_names_prints_no_duplicate(settings) -> None:
    """`accord --list` が、同じ名前を 2 度出さない（8 行で、重なりが無い）。"""
    lines = _listed_names(settings)

    assert len(lines) == 8
    assert len(lines) == len(set(lines))
