#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from core import generate_from_url


def serve_subscription(url: str, listen: str, port: int, interval: int) -> int:
    latest: Dict[str, Any] = {"text": "", "error": "", "nodes": 0, "updated": 0.0}
    lock = threading.Lock()
    stop_event = threading.Event()

    def refresh_once() -> None:
        try:
            nodes, _cfg, yaml_text = generate_from_url(url)
        except Exception as e:
            with lock:
                latest["error"] = str(e)
            return
        with lock:
            latest["text"] = yaml_text
            latest["error"] = ""
            latest["nodes"] = nodes
            latest["updated"] = time.time()

    def refresh_loop() -> None:
        refresh_once()
        while not stop_event.wait(max(10, interval)):
            refresh_once()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in ("/", "/clash.yaml", "/config.yaml", "/config"):
                self.send_response(404)
                self.end_headers()
                return
            with lock:
                text = latest["text"]
                err = latest["error"]
            if err or not text.strip():
                self.send_response(503)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write((err or "未就绪").encode("utf-8"))
                return
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/yaml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    thread = threading.Thread(target=refresh_loop, daemon=True)
    thread.start()

    print(f"JMS 订阅管家本地订阅服务：http://{listen}:{port}/clash.yaml")
    try:
        httpd = ThreadingHTTPServer((listen, port), Handler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
    return 0
