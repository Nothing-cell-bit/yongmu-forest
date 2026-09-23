#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the recipe atlas locally and expose its one-click rebuild endpoint."""

from __future__ import print_function

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

try:
    from build_recipe_atlas import DEFAULT_OUTPUT, build_catalog, build_html
except ImportError:  # pragma: no cover - package import in tests
    from tools.build_recipe_atlas import DEFAULT_OUTPUT, build_catalog, build_html


LOOPBACK_HOST = "127.0.0.1"
REBUILD_HEADER = "X-Recipe-Atlas-Request"
REBUILD_VALUE = "rebuild"


def rebuild(output):
    output = Path(output).resolve()
    catalog = build_catalog()
    html = build_html(catalog)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(html, encoding="utf-8", newline="\n")
    temporary.replace(output)
    return len(catalog)


class RecipeAtlasServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, output):
        self.output = Path(output).resolve()
        self.rebuild_lock = threading.Lock()
        super().__init__(address, handler)


class RecipeAtlasHandler(BaseHTTPRequestHandler):
    server_version = "RecipeAtlas/1.0"

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path not in ("/", "/index.html"):
            self.send_error(404)
            return
        try:
            body = self.server.output.read_bytes()
        except OSError as error:
            self._json(500, {"ok": False, "error": str(error)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' data: 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/rebuild":
            self.send_error(404)
            return
        if self.headers.get(REBUILD_HEADER) != REBUILD_VALUE:
            self._json(403, {"ok": False, "error": "rebuild header required"})
            return
        try:
            with self.server.rebuild_lock:
                recipe_count = rebuild(self.server.output)
        except Exception as error:  # keep the local UI responsive with details
            self._json(500, {"ok": False, "error": str(error)})
            return
        self._json(200, {"ok": True, "recipeCount": recipe_count})

    def log_message(self, message, *args):
        print("recipe-atlas: " + (message % args))


def create_server(port=8765, output=DEFAULT_OUTPUT):
    rebuild(output)
    return RecipeAtlasServer(
        (LOOPBACK_HOST, int(port)), RecipeAtlasHandler, output
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()
    server = create_server(args.port, args.output)
    url = "http://%s:%d/" % server.server_address
    print("配方图鉴：%s" % url, flush=True)
    print("关闭此窗口即可停止本机服务。", flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
