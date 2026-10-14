"""コマンドとして accord を起動する入口。

`--data`（経歴データの置き場）を渡して呼ぶと、標準入出力（stdio）で MCP サーバーを開く。
ネットワークの口は開かない。設定ファイルは読まない（正本の書き方は accord の形の 1 通りに固定）。
`--list` を付けると、開く口の名前だけを並べて終わる（人が目で確かめるための出口。`--data` なしで動く）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from accord.server.app import create_server
from accord.services.watch import SourceWatch
from accord.vocabulary.settings import (
    DATA_USAGE,
    SettingsError,
    load_settings,
    unbound_settings,
)


def main(argv: list[str] | None = None) -> int:
    """引数を読み、口を並べるか、stdio でサーバーを起動する。"""
    parser = argparse.ArgumentParser(
        prog="accord",
        description="正本と対外表現の一致を守る MCP サーバー",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="経歴データの置き場（git の作業ツリーの根）。--list のほかは必須",
    )
    parser.add_argument(
        "--presentations",
        type=Path,
        default=None,
        help="提示物と媒体ごとの規約の置き場（省くと提示物を 0 件として読む）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="開くツールと資源の名前を並べて終わる（--data なしで動く）",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.list and args.data is None:
        settings = unbound_settings()
    else:
        # spec: REQ-503
        if args.data is None:
            print(f"accord: --data が無い。{DATA_USAGE}", file=sys.stderr)
            return 2
        try:
            # spec: REQ-502
            # spec: REQ-504
            settings = load_settings(args.data, args.presentations)
        except (OSError, SettingsError) as error:
            # spec: REQ-545
            # spec: REQ-546
            print(f"accord: {error}", file=sys.stderr)
            return 2

    watch = SourceWatch(settings)
    server = create_server(settings, watch)

    if args.list:
        # spec: REQ-339
        for name in sorted(tool.name for tool in asyncio.run(server.list_tools())):
            print(name)
        for uri in sorted(str(resource.uri) for resource in asyncio.run(server.list_resources())):
            print(uri)
        # spec: REQ-338
        return 0

    # spec: REQ-456
    report_startup_check(watch)
    server.run("stdio")
    return 0


def report_startup_check(watch: SourceWatch) -> None:
    """起動時に正本全体の整合を検査し、違反と断りの件数を標準エラーに書く。違反があっても止めない。

    正本が食い違った状態でも読めるように、起動は続ける。違反の中身は、読みの操作の整合の知らせと
    check_consistency が返す。
    """
    try:
        violations, notes = watch.counts()
    except Exception as error:  # 検査が落ちても起動は続ける。落ちたことだけを書く。
        print(f"accord: 起動時の整合の検査が走らなかった（{type(error).__name__}）", file=sys.stderr)
        return
    # spec: REQ-457
    print(f"accord: 起動時の整合の検査 違反 {violations} 件・断り {notes} 件", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
