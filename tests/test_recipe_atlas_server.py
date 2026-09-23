# -*- coding: utf-8 -*-
"""Loopback-only recipe-atlas rebuild service contract."""

from __future__ import unicode_literals

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools import serve_recipe_atlas


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "打开配方图鉴.cmd"


def request(url, method="GET", headers=None):
    return urlopen(
        Request(url, method=method, headers=headers or {}), timeout=5
    )


def test_loopback_server_rebuilds_the_atlas_from_the_button_endpoint(tmp_path):
    """As a maintainer, one button rebuilds the atlas from current pack files."""
    output = tmp_path / "index.html"
    server = serve_recipe_atlas.create_server(port=0, output=output)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    try:
        host, port = server.server_address
        assert host == "127.0.0.1"
        base = "http://127.0.0.1:%d" % port
        with request(base + "/") as response:
            assert response.status == 200
            assert b'id="refresh-atlas"' in response.read()
        with request(
            base + "/api/rebuild",
            method="POST",
            headers={"X-Recipe-Atlas-Request": "rebuild"},
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["recipeCount"] > 0
        assert output.is_file()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_rebuild_endpoint_rejects_cross_site_simple_posts(tmp_path):
    """As a user, another website cannot silently trigger local file writes."""
    server = serve_recipe_atlas.create_server(
        port=0, output=tmp_path / "index.html"
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    try:
        port = server.server_address[1]
        try:
            request(
                "http://127.0.0.1:%d/api/rebuild" % port,
                method="POST",
            )
        except HTTPError as error:
            assert error.code == 403
        else:
            raise AssertionError("rebuild endpoint accepted an unsigned POST")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_contains_missing_paths_and_rebuild_failures(tmp_path, monkeypatch):
    output = tmp_path / "index.html"
    server = serve_recipe_atlas.create_server(port=0, output=output)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    try:
        base = "http://127.0.0.1:%d" % server.server_address[1]
        for path, method in (("/missing", "GET"), ("/missing", "POST")):
            try:
                request(base + path, method=method)
            except HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError("unknown path was not rejected")

        output.unlink()
        try:
            request(base + "/")
        except HTTPError as error:
            assert error.code == 500
        else:
            raise AssertionError("missing atlas did not return an error")

        def fail_rebuild(_output):
            raise RuntimeError("test rebuild failure")

        monkeypatch.setattr(serve_recipe_atlas, "rebuild", fail_rebuild)
        try:
            request(
                base + "/api/rebuild",
                method="POST",
                headers={"X-Recipe-Atlas-Request": "rebuild"},
            )
        except HTTPError as error:
            assert error.code == 500
            assert b"test rebuild failure" in error.read()
        else:
            raise AssertionError("rebuild failure was not contained")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_windows_launcher_starts_the_local_atlas_service():
    assert LAUNCHER.is_file()
    source = LAUNCHER.read_text(encoding="utf-8-sig")
    assert "serve_recipe_atlas.py" in source
    assert "--open" in source
