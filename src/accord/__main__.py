"""コマンドとして accord を起動する入口。

引数なしで呼ぶと、標準入出力（stdio）で MCP サーバーを開く。ネットワークの口は開かない。
`--list` を付けると、開く口の名前だけを並べて終わる（人が目で確かめるための出口）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from accord.server.app import create_server
from accord.vocabulary.settings import load_settings


def main(argv: list[str] | None = None) -> int:
    """引数を読み、口を並べるか、stdio でサーバーを起動する。"""
    parser = argparse.ArgumentParser(
        prog="accord",
        description="正本と対外表現の一致を守る MCP サーバー",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="設定ファイルの場所（省くと同梱の samples/accord.toml を読む）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="開くツールと資源の名前を並べて終わる",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        settings = load_settings(args.config)
    except (OSError, ValueError) as error:
        print(f"設定が読めない: {error}", file=sys.stderr)
        return 2

    server = create_server(settings)

    if args.list:
        # spec: REQ-339
        for name in sorted(tool.name for tool in asyncio.run(server.list_tools())):
            print(name)
        for uri in sorted(str(resource.uri) for resource in asyncio.run(server.list_resources())):
            print(uri)
        # spec: REQ-338
        return 0

    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
