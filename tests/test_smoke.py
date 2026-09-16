"""clone した人が最初に確かめること。口が揃っているかを見る。"""

from __future__ import annotations

import asyncio
import subprocess
import sys

from accord.server.app import ONTOLOGY_URI, TOOL_NAMES, create_server

EXPECTED_TOOLS = set(TOOL_NAMES)


def test_server_lists_six_tools_and_one_resource(settings) -> None:
    """サンプルだけで起動したサーバーが、ツール 6 本と資源 1 本を開く。"""
    server = create_server(settings)

    tools = asyncio.run(server.list_tools())
    resources = asyncio.run(server.list_resources())

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    assert len(tools) == 6
    assert [str(resource.uri) for resource in resources] == [ONTOLOGY_URI]


def test_command_line_lists_the_same_names(settings) -> None:
    """`accord --list` も、同じ 6 本と 1 本を 1 行ずつ出す。"""
    completed = subprocess.run(
        [sys.executable, "-m", "accord", "--config", str(settings.config_path), "--list"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.split()
    assert set(lines) == EXPECTED_TOOLS | {ONTOLOGY_URI}
    assert len(lines) == 7
