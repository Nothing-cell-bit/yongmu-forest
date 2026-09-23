# -*- coding: utf-8 -*-
"""Offline recipe-atlas generation contract."""

from __future__ import unicode_literals

import json
import re
import subprocess
import sys
from pathlib import Path

from tools import build_recipe_atlas as recipe_atlas


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "build_recipe_atlas.py"
RECIPES = ROOT / "TwilightBossSliceB" / "recipes"
CHECKED_IN = ROOT / "artifacts" / "recipe-atlas" / "index.html"


def build_atlas(output):
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(output)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def build_atlas_in_process(output):
    catalog = recipe_atlas.build_catalog()
    output.write_text(
        recipe_atlas.build_html(catalog), encoding="utf-8", newline="\n"
    )


def embedded_recipes(html):
    match = re.search(
        r'<script id="recipe-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match, "missing embedded recipe data"
    return json.loads(match.group(1))


def test_generator_builds_complete_self_contained_atlas(tmp_path):
    """As a player, I can open one file and browse every current recipe."""
    output = tmp_path / "index.html"
    build_atlas_in_process(output)
    html = output.read_text(encoding="utf-8")
    recipes = embedded_recipes(html)
    assert len(recipes) == len(list(RECIPES.glob("*.recipe.json")))
    assert all(recipe["id"] and recipe["output"]["id"] for recipe in recipes)
    assert all(recipe["kind"] in {"shaped", "shapeless", "furnace", "stonecutter"} for recipe in recipes)
    assert "https://" not in html and "http://" not in html
    assert "data:image/png;base64," in html


def test_atlas_exposes_search_filters_and_accessible_recipe_details(tmp_path):
    """As a player, I can search, filter and inspect recipes by keyboard."""
    output = tmp_path / "index.html"
    build_atlas_in_process(output)
    html = output.read_text(encoding="utf-8")
    for marker in (
        'id="recipe-search"',
        'aria-label="搜索配方"',
        'data-filter="all"',
        'data-filter="shaped"',
        'data-filter="shapeless"',
        'data-filter="furnace"',
        'data-filter="stonecutter"',
        'id="recipe-dialog"',
        'aria-live="polite"',
        'id="empty-state"',
        'id="refresh-atlas"',
        'id="refresh-status"',
        'fetch("/api/rebuild"',
    ):
        assert marker in html


def test_checked_in_atlas_matches_the_generator(tmp_path):
    """As a maintainer, changing recipes cannot silently leave the atlas stale."""
    output = tmp_path / "index.html"
    result = build_atlas(output)
    assert result.returncode == 0, result.stdout + result.stderr
    assert CHECKED_IN.is_file()
    assert output.read_bytes() == CHECKED_IN.read_bytes()
