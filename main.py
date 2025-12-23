#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from core import InternalError, generate_from_url_to_path
from server import serve_subscription
from ui import run_gui


def main() -> int:
    default_output = str(Path.home() / f"{date.today().strftime('%Y-%m-%d')}.yaml")
    ap = argparse.ArgumentParser(
        description="从订阅 URL 生成 Clash YAML（ss/vmess 的 base64 列表）")
    ap.add_argument(
        "url", nargs="?", help="订阅 URL（你已有的 SUBSCRIPTION_URL）")
    ap.add_argument("-o", "--output", default=default_output,
                    help=f"输出 YAML 路径（默认: {default_output}）")
    ap.add_argument("--serve", action="store_true",
                    help="通过本地 HTTP 提供生成的 YAML")
    ap.add_argument("--listen", default="127.0.0.1",
                    help="监听地址（默认: 127.0.0.1）")
    ap.add_argument("--port", type=int, default=9095,
                    help="监听端口（默认: 9095）")
    ap.add_argument("--interval", type=int, default=300,
                    help="刷新间隔秒数（默认: 300）")
    args = ap.parse_args()

    if args.serve:
        if not args.url:
            print("错误：--serve 需要提供 URL", file=sys.stderr)
            return 2
        return serve_subscription(args.url, args.listen, args.port, args.interval)

    if not args.url:
        return run_gui(default_output)

    generate_from_url_to_path(args.url, Path(args.output))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InternalError as e:
        print(f"错误：{e.message}", file=sys.stderr)
        raise SystemExit(2)
