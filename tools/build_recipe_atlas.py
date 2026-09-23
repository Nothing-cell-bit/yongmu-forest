#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a searchable, self-contained HTML atlas for every behavior-pack recipe."""

from __future__ import print_function

import argparse
import base64
import json
import mimetypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
RECIPES = BP / "recipes"
DEFAULT_OUTPUT = ROOT / "artifacts" / "recipe-atlas" / "index.html"

VANILLA_NAMES = {
    "minecraft:blaze_rod": "烈焰棒",
    "minecraft:bone_meal": "骨粉",
    "minecraft:chain": "锁链",
    "minecraft:chest": "箱子",
    "minecraft:dark_oak_button": "深色橡木按钮",
    "minecraft:dark_oak_door": "深色橡木门",
    "minecraft:dark_oak_fence": "深色橡木栅栏",
    "minecraft:dark_oak_fence_gate": "深色橡木栅栏门",
    "minecraft:dark_oak_hanging_sign": "悬挂式深色橡木告示牌",
    "minecraft:dark_oak_planks": "深色橡木木板",
    "minecraft:dark_oak_pressure_plate": "深色橡木压力板",
    "minecraft:dark_oak_sign": "深色橡木告示牌",
    "minecraft:dark_oak_slab": "深色橡木台阶",
    "minecraft:dark_oak_stairs": "深色橡木楼梯",
    "minecraft:dark_oak_trapdoor": "深色橡木活板门",
    "minecraft:dispenser": "发射器",
    "minecraft:ender_pearl": "末影珍珠",
    "minecraft:fermented_spider_eye": "发酵蛛眼",
    "minecraft:glass_bottle": "玻璃瓶",
    "minecraft:glowstone_dust": "荧石粉",
    "minecraft:gold_nugget": "金粒",
    "minecraft:golden_apple": "金苹果",
    "minecraft:honeycomb": "蜜脾",
    "minecraft:iron_ingot": "铁锭",
    "minecraft:lava_bucket": "熔岩桶",
    "minecraft:lily_pad": "睡莲",
    "minecraft:mangrove_button": "红树木按钮",
    "minecraft:mangrove_door": "红树木门",
    "minecraft:mangrove_fence": "红树木栅栏",
    "minecraft:mangrove_fence_gate": "红树木栅栏门",
    "minecraft:mangrove_hanging_sign": "悬挂式红树木告示牌",
    "minecraft:mangrove_pressure_plate": "红树木压力板",
    "minecraft:mangrove_sign": "红树木告示牌",
    "minecraft:mangrove_slab": "红树木台阶",
    "minecraft:mangrove_stairs": "红树木楼梯",
    "minecraft:mangrove_trapdoor": "红树木活板门",
    "minecraft:oak_planks": "橡木木板",
    "minecraft:paper": "纸",
    "minecraft:potion": "药水",
    "minecraft:raw_iron": "粗铁",
    "minecraft:redstone": "红石粉",
    "minecraft:redstone_ore": "红石矿石",
    "minecraft:rotten_flesh": "腐肉",
    "minecraft:stick": "木棍",
    "minecraft:stone_brick_slab": "石砖台阶",
    "minecraft:stone_bricks": "石砖",
    "minecraft:vine": "藤蔓",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_language(path):
    entries = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        entries[key.strip()] = value.strip()
    return entries


def localized_name(identifier, language):
    if identifier in VANILLA_NAMES:
        return VANILLA_NAMES[identifier]
    candidates = (
        "item.%s.name" % identifier,
        "tile.%s.name" % identifier,
        "entity.%s.name" % identifier,
    )
    for key in candidates:
        if language.get(key):
            return language[key]
    plain = identifier.split(":", 1)[-1].replace("_", " ")
    return plain.title()


def first_texture_path(value):
    if isinstance(value, str):
        return value if value.startswith("textures/") else None
    if isinstance(value, list):
        for child in value:
            found = first_texture_path(child)
            if found:
                return found
    if isinstance(value, dict):
        for preferred in ("default", "path", "textures"):
            if preferred in value:
                found = first_texture_path(value[preferred])
                if found:
                    return found
        for child in value.values():
            found = first_texture_path(child)
            if found:
                return found
    return None


def atlas_entries():
    result = {}
    for atlas_name in ("item_texture.json", "terrain_texture.json"):
        document = load_json(RP / "textures" / atlas_name)
        for identifier, entry in document.get("texture_data", {}).items():
            path = first_texture_path(entry)
            if path:
                result[identifier] = path
    return result


def texture_file(identifier, atlas):
    name = identifier.split(":", 1)[-1]
    aliases = (
        identifier,
        identifier + "_item",
        name,
        name + "_item",
    )
    for alias in aliases:
        relative = atlas.get(alias)
        if not relative:
            continue
        for extension in (".png", ".tga", ".jpg", ".jpeg"):
            candidate = RP / (relative + extension)
            if candidate.is_file():
                return candidate
    fallback_dirs = (
        RP / "textures" / "items",
        RP / "textures" / "blocks",
    )
    for directory in fallback_dirs:
        for extension in (".png", ".tga"):
            candidate = directory / (name + extension)
            if candidate.is_file():
                return candidate
    return None


def data_uri(path):
    if path is None:
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:%s;base64,%s" % (mime, encoded)


def recipe_kind(root_key, recipe):
    if root_key == "minecraft:recipe_furnace":
        return "furnace"
    if root_key == "minecraft:recipe_shaped":
        return "shaped"
    if "stonecutter" in recipe.get("tags", []):
        return "stonecutter"
    return "shapeless"


def result_stack(root_key, recipe):
    if root_key == "minecraft:recipe_furnace":
        return recipe["output"], 1
    result = recipe.get("result", {})
    if isinstance(result, str):
        return result, 1
    return result["item"], int(result.get("count", 1))


def centered_shaped_slots(pattern, key):
    rows = list(pattern)
    width = max(len(row) for row in rows)
    vertical_offset = (3 - len(rows)) // 2
    horizontal_offset = (3 - width) // 2
    slots = [""] * 9
    for row_index, row in enumerate(rows):
        for column_index, token in enumerate(row):
            if token == " ":
                continue
            entry = key.get(token, {})
            slots[(row_index + vertical_offset) * 3 + column_index + horizontal_offset] = (
                entry.get("item", "")
            )
    return slots


def shapeless_slots(ingredients):
    items = [entry.get("item", "") for entry in ingredients]
    return (items + [""] * 9)[:9]


def build_catalog():
    language = load_language(RP / "texts" / "zh_CN.lang")
    atlas = atlas_entries()
    icons = {}

    def item(identifier):
        if not identifier:
            return {"id": "", "name": "", "icon": ""}
        if identifier not in icons:
            icons[identifier] = data_uri(texture_file(identifier, atlas))
        return {
            "id": identifier,
            "name": localized_name(identifier, language),
            "icon": icons[identifier],
        }

    catalog = []
    for path in sorted(RECIPES.glob("*.recipe.json")):
        document = load_json(path)
        root_key = next(
            key for key in document if key.startswith("minecraft:recipe_")
        )
        recipe = document[root_key]
        kind = recipe_kind(root_key, recipe)
        output_id, output_count = result_stack(root_key, recipe)
        if kind == "shaped":
            slot_ids = centered_shaped_slots(
                recipe.get("pattern", []), recipe.get("key", {})
            )
        elif kind == "furnace":
            slot_ids = [recipe.get("input", "")]
        else:
            slot_ids = shapeless_slots(recipe.get("ingredients", []))
        inputs = [item(identifier) for identifier in slot_ids if identifier]
        output = item(output_id)
        output["count"] = output_count
        search_text = " ".join(
            [recipe["description"]["identifier"], output["id"], output["name"]]
            + [entry["id"] for entry in inputs]
            + [entry["name"] for entry in inputs]
        ).lower()
        catalog.append(
            {
                "source": path.name,
                "id": recipe["description"]["identifier"],
                "kind": kind,
                "tags": recipe.get("tags", []),
                "slots": [item(identifier) for identifier in slot_ids],
                "inputs": inputs,
                "output": output,
                "search": search_text,
            }
        )
    return catalog


STYLE = r"""
:root {
  color-scheme: dark;
  --ink: #eaf6ef;
  --muted: #9cb2a7;
  --night: #08110e;
  --forest: #10251c;
  --panel: rgba(15, 34, 27, .92);
  --panel-strong: #173d2d;
  --line: rgba(140, 204, 166, .2);
  --green: #73d695;
  --gold: #f2c86b;
  --red: #ff8c7c;
  --shadow: 0 18px 50px rgba(0, 0, 0, .34);
}
* { box-sizing: border-box; }
html { min-width: 320px; background: var(--night); }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  font: 16px/1.5 "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif;
  background:
    radial-gradient(circle at 12% 0%, rgba(69, 139, 99, .2), transparent 32rem),
    radial-gradient(circle at 90% 16%, rgba(71, 91, 154, .18), transparent 28rem),
    linear-gradient(145deg, #07110d 0%, #0c1814 52%, #09100f 100%);
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: .22;
  background-image:
    linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px);
  background-size: 24px 24px;
}
button, input, select { font: inherit; }
button { color: inherit; }
.shell { width: min(1460px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 64px; }
.masthead {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 24px;
  align-items: end;
  margin-bottom: 24px;
}
.eyebrow {
  margin: 0 0 5px;
  color: var(--green);
  font-size: .82rem;
  font-weight: 800;
  letter-spacing: .14em;
  text-transform: uppercase;
}
h1 { margin: 0; font-size: clamp(2rem, 5vw, 4.4rem); line-height: .98; letter-spacing: -.055em; }
.summary { margin: 12px 0 0; color: var(--muted); font-size: 1rem; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.stat {
  min-width: 94px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  background: rgba(16, 37, 28, .72);
  box-shadow: inset 0 1px rgba(255,255,255,.04);
}
.stat strong { display: block; color: var(--gold); font-size: 1.35rem; line-height: 1; }
.stat span { color: var(--muted); font-size: .76rem; }
.toolbar {
  position: sticky;
  top: 12px;
  z-index: 10;
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto auto auto;
  gap: 12px;
  padding: 12px;
  margin-bottom: 22px;
  border: 1px solid var(--line);
  background: rgba(7, 17, 13, .9);
  box-shadow: var(--shadow);
  backdrop-filter: blur(14px);
}
.search-wrap { position: relative; }
.search-wrap::before {
  content: "⌕";
  position: absolute;
  left: 15px;
  top: 50%;
  transform: translateY(-53%);
  color: var(--green);
  font-size: 1.45rem;
}
#recipe-search, #sort-order {
  width: 100%;
  height: 46px;
  border: 1px solid var(--line);
  border-radius: 0;
  color: var(--ink);
  background: #0d2118;
}
#recipe-search { padding: 0 14px 0 44px; }
#sort-order { padding: 0 34px 0 12px; }
#recipe-search:focus, #sort-order:focus, button:focus-visible {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}
.filters { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.filter {
  height: 46px;
  padding: 0 14px;
  border: 1px solid var(--line);
  background: #10251c;
  cursor: pointer;
}
.filter:hover { border-color: rgba(115,214,149,.65); }
.filter.active { color: #06110c; background: var(--green); border-color: var(--green); font-weight: 800; }
.refresh {
  height: 46px;
  padding: 0 16px;
  border: 1px solid var(--gold);
  color: #171006;
  background: var(--gold);
  font-weight: 900;
  cursor: pointer;
}
.refresh:hover { filter: brightness(1.08); }
.refresh:disabled { cursor: wait; opacity: .62; }
.refresh-status { align-self: center; min-width: 7em; color: var(--muted); font-size: .82rem; }
.result-row { display: flex; align-items: center; justify-content: space-between; margin: 0 2px 14px; color: var(--muted); }
.key-hint { font-size: .82rem; }
kbd { padding: 2px 7px; border: 1px solid var(--line); background: #10251c; color: var(--ink); }
.recipe-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 14px;
}
.recipe-card {
  position: relative;
  display: grid;
  grid-template-columns: 78px 1fr;
  gap: 16px;
  width: 100%;
  min-height: 130px;
  padding: 16px;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 0;
  background: linear-gradient(145deg, rgba(24, 58, 43, .92), rgba(13, 31, 24, .94));
  box-shadow: 0 8px 24px rgba(0,0,0,.18);
  cursor: pointer;
  overflow: hidden;
}
.recipe-card::after {
  content: "";
  position: absolute;
  inset: auto 0 0;
  height: 2px;
  transform: scaleX(0);
  transform-origin: left;
  background: linear-gradient(90deg, var(--green), var(--gold));
  transition: transform .18s ease;
}
.recipe-card:hover { border-color: rgba(115,214,149,.5); transform: translateY(-1px); }
.recipe-card:hover::after { transform: scaleX(1); }
.result-icon, .slot {
  position: relative;
  display: grid;
  place-items: center;
  background:
    linear-gradient(135deg, rgba(255,255,255,.05), transparent),
    #0a1812;
  border: 1px solid rgba(155, 213, 177, .28);
  box-shadow: inset 0 0 0 3px rgba(0,0,0,.18);
}
.result-icon { width: 78px; height: 78px; }
.result-icon img, .slot img { max-width: 72%; max-height: 72%; image-rendering: pixelated; filter: drop-shadow(0 5px 4px rgba(0,0,0,.45)); }
.fallback {
  display: grid;
  place-items: center;
  width: 62%;
  height: 62%;
  color: var(--gold);
  border: 1px dashed rgba(242,200,107,.45);
  font-size: .72rem;
  font-weight: 900;
  letter-spacing: .04em;
}
.count {
  position: absolute;
  right: 5px;
  bottom: 2px;
  color: white;
  font-size: .78rem;
  font-weight: 900;
  text-shadow: 0 1px 3px black;
}
.card-copy { min-width: 0; }
.kind {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--green);
  font-size: .75rem;
  font-weight: 800;
}
.kind::before { content: ""; width: 6px; height: 6px; background: currentColor; }
.card-copy h2 { margin: 8px 0 4px; font-size: 1.1rem; line-height: 1.2; }
.identifier { margin: 0; color: var(--muted); font: .73rem/1.4 ui-monospace, Consolas, monospace; overflow-wrap: anywhere; }
.ingredient-preview { display: flex; gap: 4px; margin-top: 12px; }
.ingredient-dot {
  width: 22px;
  height: 5px;
  background: rgba(156,178,167,.24);
}
.ingredient-dot.filled { background: var(--gold); }
#empty-state {
  padding: 64px 20px;
  text-align: center;
  border: 1px dashed var(--line);
  color: var(--muted);
}
#recipe-dialog {
  width: min(760px, calc(100% - 28px));
  max-height: calc(100vh - 28px);
  padding: 0;
  color: var(--ink);
  border: 1px solid rgba(115,214,149,.45);
  border-radius: 0;
  background: #0b1d15;
  box-shadow: 0 28px 90px rgba(0,0,0,.68);
}
#recipe-dialog::backdrop { background: rgba(1,7,4,.78); backdrop-filter: blur(6px); }
.dialog-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 22px; border-bottom: 1px solid var(--line); }
.dialog-head h2 { margin: 3px 0 0; font-size: 1.65rem; }
.close {
  min-width: 42px;
  height: 42px;
  border: 1px solid var(--line);
  background: #10251c;
  cursor: pointer;
}
.dialog-body { display: grid; grid-template-columns: minmax(270px, .9fr) 1fr; gap: 30px; padding: 26px 22px 28px; }
.craft-flow { display: flex; align-items: center; justify-content: center; gap: 17px; min-height: 260px; padding: 18px; background: rgba(255,255,255,.025); border: 1px solid var(--line); }
.crafting-grid { display: grid; grid-template-columns: repeat(3, 58px); gap: 5px; }
.crafting-grid.single { grid-template-columns: 74px; }
.slot { width: 58px; height: 58px; }
.single .slot { width: 74px; height: 74px; }
.flow-arrow { color: var(--gold); font-size: 2rem; }
.dialog-output { width: 82px; height: 82px; }
.ingredient-list { display: grid; gap: 8px; align-content: start; }
.ingredient-row { display: grid; grid-template-columns: 36px 1fr; gap: 10px; align-items: center; padding: 8px; background: rgba(255,255,255,.025); border: 1px solid var(--line); }
.ingredient-row .slot { width: 36px; height: 36px; }
.ingredient-row strong { display: block; font-size: .9rem; }
.ingredient-row small { display: block; color: var(--muted); overflow-wrap: anywhere; }
.source-line { margin-top: 16px; color: var(--muted); font: .75rem/1.5 ui-monospace, Consolas, monospace; overflow-wrap: anywhere; }
.noscript { margin: 24px; padding: 16px; color: var(--red); border: 1px solid var(--red); }
@media (max-width: 900px) {
  .masthead { grid-template-columns: 1fr; }
  .stats { justify-content: flex-start; }
  .toolbar { position: static; grid-template-columns: 1fr; }
  .filters { order: 2; }
}
@media (max-width: 640px) {
  .shell { width: min(100% - 20px, 1460px); padding-top: 22px; }
  .masthead { gap: 16px; }
  .stat { min-width: 82px; }
  .recipe-grid { grid-template-columns: 1fr; }
  .dialog-body { grid-template-columns: 1fr; }
  .craft-flow { min-height: 220px; }
  .crafting-grid { grid-template-columns: repeat(3, 48px); }
  .slot { width: 48px; height: 48px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}
"""


SCRIPT = r"""
(function () {
  "use strict";
  var recipes = JSON.parse(document.getElementById("recipe-data").textContent);
  var state = { query: "", filter: "all", sort: "name" };
  var labels = {
    shaped: "有序合成",
    shapeless: "无序合成",
    furnace: "熔炉",
    stonecutter: "切石机"
  };
  var grid = document.getElementById("recipe-grid");
  var count = document.getElementById("result-count");
  var empty = document.getElementById("empty-state");
  var dialog = document.getElementById("recipe-dialog");
  var dialogContent = document.getElementById("dialog-content");
  var refreshButton = document.getElementById("refresh-atlas");
  var refreshStatus = document.getElementById("refresh-status");

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (token) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[token];
    });
  }

  function initials(item) {
    var words = item.name.replace(/[^\w\u4e00-\u9fff]+/g, " ").trim().split(/\s+/);
    if (/[\u4e00-\u9fff]/.test(item.name)) return item.name.slice(0, 2);
    return words.slice(0, 2).map(function (word) { return word.charAt(0); }).join("").toUpperCase();
  }

  function itemVisual(item, extraClass, itemCount) {
    if (!item || !item.id) return '<span class="slot ' + (extraClass || "") + '" aria-hidden="true"></span>';
    var visual = item.icon
      ? '<img src="' + item.icon + '" alt="" loading="lazy">'
      : '<span class="fallback">' + escapeHtml(initials(item)) + '</span>';
    var number = itemCount && itemCount > 1 ? '<span class="count">' + itemCount + '</span>' : "";
    return '<span class="slot ' + (extraClass || "") + '" title="' +
      escapeHtml(item.name + " · " + item.id) + '">' + visual + number + '</span>';
  }

  function resultVisual(item, extraClass) {
    var visual = item.icon
      ? '<img src="' + item.icon + '" alt="" loading="lazy">'
      : '<span class="fallback">' + escapeHtml(initials(item)) + '</span>';
    var number = item.count > 1 ? '<span class="count">' + item.count + '</span>' : "";
    return '<span class="result-icon ' + (extraClass || "") + '">' + visual + number + '</span>';
  }

  function card(recipe, index) {
    var dots = recipe.slots.map(function (slot) {
      return '<span class="ingredient-dot ' + (slot.id ? "filled" : "") + '"></span>';
    }).join("");
    return '<button class="recipe-card" type="button" data-index="' + index +
      '" aria-label="查看 ' + escapeHtml(recipe.output.name) + ' 的配方">' +
      resultVisual(recipe.output, "") +
      '<span class="card-copy"><span class="kind">' + labels[recipe.kind] +
      '</span><h2>' + escapeHtml(recipe.output.name) + '</h2><p class="identifier">' +
      escapeHtml(recipe.id) + '</p><span class="ingredient-preview" aria-hidden="true">' +
      dots + '</span></span></button>';
  }

  function visibleRecipes() {
    var query = state.query.trim().toLowerCase();
    var filtered = recipes.filter(function (recipe) {
      return (state.filter === "all" || recipe.kind === state.filter) &&
        (!query || recipe.search.indexOf(query) !== -1);
    });
    filtered.sort(function (a, b) {
      if (state.sort === "type") {
        return labels[a.kind].localeCompare(labels[b.kind], "zh-CN") ||
          a.output.name.localeCompare(b.output.name, "zh-CN");
      }
      if (state.sort === "id") return a.id.localeCompare(b.id);
      return a.output.name.localeCompare(b.output.name, "zh-CN");
    });
    return filtered;
  }

  function render() {
    var visible = visibleRecipes();
    grid.innerHTML = visible.map(function (recipe) {
      return card(recipe, recipes.indexOf(recipe));
    }).join("");
    count.textContent = "显示 " + visible.length + " / " + recipes.length + " 份配方";
    empty.hidden = visible.length !== 0;
  }

  function ingredientRows(recipe) {
    var totals = {};
    recipe.inputs.forEach(function (item) {
      if (!totals[item.id]) totals[item.id] = {item: item, count: 0};
      totals[item.id].count += 1;
    });
    return Object.keys(totals).map(function (id) {
      var entry = totals[id];
      return '<div class="ingredient-row">' + itemVisual(entry.item, "", 0) +
        '<span><strong>' + escapeHtml(entry.item.name) +
        (entry.count > 1 ? " × " + entry.count : "") +
        '</strong><small>' + escapeHtml(entry.item.id) + '</small></span></div>';
    }).join("");
  }

  function openRecipe(recipe) {
    var slots;
    if (recipe.kind === "furnace" || recipe.kind === "stonecutter") {
      slots = '<div class="crafting-grid single">' + itemVisual(recipe.slots[0], "", 0) + '</div>';
    } else {
      slots = '<div class="crafting-grid">' +
        recipe.slots.map(function (item) { return itemVisual(item, "", 0); }).join("") +
        '</div>';
    }
    dialogContent.innerHTML =
      '<div class="dialog-head"><div><span class="kind">' + labels[recipe.kind] +
      '</span><h2 id="dialog-title">' + escapeHtml(recipe.output.name) +
      '</h2><p class="identifier">' + escapeHtml(recipe.id) +
      '</p></div><button class="close" type="button" aria-label="关闭">✕</button></div>' +
      '<div class="dialog-body"><div><div class="craft-flow">' + slots +
      '<span class="flow-arrow" aria-hidden="true">➜</span>' +
      resultVisual(recipe.output, "dialog-output") +
      '</div><p class="source-line">来源：' + escapeHtml(recipe.source) +
      '</p></div><div class="ingredient-list"><span class="eyebrow">所需材料</span>' +
      ingredientRows(recipe) + '</div></div>';
    dialogContent.querySelector(".close").addEventListener("click", function () { dialog.close(); });
    dialog.showModal();
  }

  document.getElementById("recipe-search").addEventListener("input", function (event) {
    state.query = event.target.value;
    render();
  });
  document.getElementById("sort-order").addEventListener("change", function (event) {
    state.sort = event.target.value;
    render();
  });
  document.querySelectorAll(".filter").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".filter").forEach(function (item) {
        item.classList.remove("active");
        item.setAttribute("aria-pressed", "false");
      });
      button.classList.add("active");
      button.setAttribute("aria-pressed", "true");
      state.filter = button.getAttribute("data-filter");
      render();
    });
  });
  grid.addEventListener("click", function (event) {
    var cardButton = event.target.closest(".recipe-card");
    if (cardButton) openRecipe(recipes[Number(cardButton.getAttribute("data-index"))]);
  });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) dialog.close();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "/" && document.activeElement !== document.getElementById("recipe-search")) {
      event.preventDefault();
      document.getElementById("recipe-search").focus();
    }
  });
  refreshButton.addEventListener("click", function () {
    refreshButton.disabled = true;
    refreshStatus.textContent = "正在更新…";
    fetch("/api/rebuild", {
      method: "POST",
      headers: {"X-Recipe-Atlas-Request": "rebuild"}
    }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }).then(function (payload) {
      refreshStatus.textContent = "已更新 " + payload.recipeCount + " 份配方";
      window.setTimeout(function () { window.location.reload(); }, 350);
    }).catch(function () {
      refreshStatus.textContent = window.location.protocol === "file:"
        ? "请双击“打开配方图鉴.cmd”后使用"
        : "更新失败，请重新启动图鉴";
      refreshButton.disabled = false;
    });
  });
  render();
}());
"""


def build_html(catalog):
    totals = {
        "all": len(catalog),
        "shaped": sum(recipe["kind"] == "shaped" for recipe in catalog),
        "shapeless": sum(recipe["kind"] == "shapeless" for recipe in catalog),
        "furnace": sum(recipe["kind"] == "furnace" for recipe in catalog),
        "stonecutter": sum(
            recipe["kind"] == "stonecutter" for recipe in catalog
        ),
    }
    embedded = json.dumps(
        catalog, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="暮色森林网易版离线配方图鉴">
  <title>暮色配方档案馆</title>
  <style>%s</style>
</head>
<body>
  <main class="shell">
    <header class="masthead">
      <div>
        <p class="eyebrow">Twilight Forest · Recipe Atlas</p>
        <h1>暮色配方<br>档案馆</h1>
        <p class="summary">搜索产物或材料，点击卡片查看完整合成格。</p>
      </div>
      <div class="stats" aria-label="配方统计">
        <div class="stat"><strong>%d</strong><span>全部配方</span></div>
        <div class="stat"><strong>%d</strong><span>有序合成</span></div>
        <div class="stat"><strong>%d</strong><span>无序合成</span></div>
        <div class="stat"><strong>%d</strong><span>熔炉 / 切石</span></div>
      </div>
    </header>
    <section class="toolbar" aria-label="配方筛选工具">
      <div class="search-wrap">
        <label for="recipe-search" hidden>搜索配方</label>
        <input id="recipe-search" type="search" aria-label="搜索配方"
          placeholder="搜索中文名、物品 ID 或材料…" autocomplete="off">
      </div>
      <div class="filters" role="group" aria-label="配方类型">
        <button class="filter active" type="button" data-filter="all" aria-pressed="true">全部</button>
        <button class="filter" type="button" data-filter="shaped" aria-pressed="false">有序</button>
        <button class="filter" type="button" data-filter="shapeless" aria-pressed="false">无序</button>
        <button class="filter" type="button" data-filter="furnace" aria-pressed="false">熔炉</button>
        <button class="filter" type="button" data-filter="stonecutter" aria-pressed="false">切石</button>
      </div>
      <button id="refresh-atlas" class="refresh" type="button">↻ 更新配方</button>
      <label>
        <span hidden>排序方式</span>
        <select id="sort-order" aria-label="排序方式">
          <option value="name">按中文名</option>
          <option value="type">按配方类型</option>
          <option value="id">按物品 ID</option>
        </select>
      </label>
    </section>
    <div id="refresh-status" class="refresh-status" aria-live="polite"></div>
    <div class="result-row">
      <span id="result-count" aria-live="polite"></span>
      <span class="key-hint"><kbd>/</kbd> 快速搜索</span>
    </div>
    <section id="recipe-grid" class="recipe-grid" aria-label="配方列表"></section>
    <div id="empty-state" hidden>没有找到匹配的配方，试试搜索材料名称。</div>
  </main>
  <dialog id="recipe-dialog" aria-labelledby="dialog-title">
    <div id="dialog-content"></div>
  </dialog>
  <noscript><p class="noscript">需要启用 JavaScript 才能搜索和查看配方。</p></noscript>
  <script id="recipe-data" type="application/json">%s</script>
  <script>%s</script>
</body>
</html>
""" % (
        STYLE,
        totals["all"],
        totals["shaped"],
        totals["shapeless"],
        totals["furnace"] + totals["stonecutter"],
        embedded,
        SCRIPT,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    catalog = build_catalog()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(catalog), encoding="utf-8", newline="\n")
    print(
        "wrote %s (%d recipes, %d bytes)"
        % (output, len(catalog), output.stat().st_size)
    )


if __name__ == "__main__":
    main()
