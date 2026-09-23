# -*- coding: utf-8 -*-
"""Source-material parity for recipes that previously used placeholder inputs."""

from __future__ import unicode_literals

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def recipe(name, recipe_type):
    return load(BP / "recipes" / (name + ".recipe.json"))[recipe_type]


def catalog_ids():
    document = load(BP / "item_catalog" / "crafting_item_catalog.json")
    return {
        identifier
        for category in document["minecraft:crafting_items_catalog"]["categories"]
        for group in category.get("groups", [])
        for identifier in group.get("items", [])
    }


def test_canopy_fence_uses_the_ported_canopy_plank_chain():
    planks = load(BP / "netease_blocks" / "canopy_planks.json")["minecraft:block"]
    assert planks["description"]["identifier"] == "tf_slice:canopy_planks"
    assert (RP / "textures" / "blocks" / "canopy_planks.png").is_file()
    terrain = load(RP / "textures" / "terrain_texture.json")["texture_data"]
    assert terrain["tf_slice:canopy_planks"]["textures"] == "textures/blocks/canopy_planks"

    plank_recipe = recipe("canopy_planks", "minecraft:recipe_shapeless")
    assert plank_recipe["ingredients"] == [{"item": "tf_slice:canopy_log"}]
    assert plank_recipe["result"] == {"item": "tf_slice:canopy_planks", "count": 4}

    fence = recipe("canopy_fence", "minecraft:recipe_shaped")
    assert fence["key"]["#"] == {"item": "tf_slice:canopy_planks"}
    assert "tf_slice:canopy_planks" in catalog_ids()


def test_ironwood_restores_liveroot_raw_material_and_smelting_steps():
    for name in ("liveroot", "raw_ironwood"):
        item = load(BP / "items" / (name + ".item.json"))["minecraft:item"]
        assert item["description"]["identifier"] == "tf_slice:" + name
        assert (RP / "textures" / "items" / (name + ".png")).is_file()

    extraction = recipe("liveroot_from_block", "minecraft:recipe_shapeless")
    assert extraction["ingredients"] == [{"item": "tf_slice:liveroot_block"}]
    assert extraction["result"] == {"item": "tf_slice:liveroot", "count": 1}

    raw = recipe("raw_ironwood", "minecraft:recipe_shapeless")
    assert [entry["item"] for entry in raw["ingredients"]] == [
        "tf_slice:liveroot",
        "minecraft:raw_iron",
        "minecraft:gold_nugget",
    ]
    assert raw["result"] == {"item": "tf_slice:raw_ironwood", "count": 2}
    smelting = recipe("ironwood_ingot", "minecraft:recipe_furnace")
    assert smelting["input"] == "tf_slice:raw_ironwood"
    assert smelting["output"] == "tf_slice:ironwood_ingot"


def test_steeleaf_ingots_only_round_trip_through_the_storage_block():
    block = load(BP / "netease_blocks" / "steeleaf_block.json")["minecraft:block"]
    assert block["description"]["identifier"] == "tf_slice:steeleaf_block"
    assert (RP / "textures" / "blocks" / "steeleaf_block.png").is_file()

    packed = recipe("steeleaf_block", "minecraft:recipe_shaped")
    assert packed["key"]["#"] == {"item": "tf_slice:steeleaf_ingot"}
    unpacked = recipe("steeleaf_ingot", "minecraft:recipe_shapeless")
    assert unpacked["ingredients"] == [{"item": "tf_slice:steeleaf_block"}]
    assert unpacked["result"] == {"item": "tf_slice:steeleaf_ingot", "count": 9}
    assert "tf_slice:steeleaf_block" in catalog_ids()


def test_cicada_and_transformation_powder_replace_unrelated_substitutes():
    for name in ("cicada", "transformation_powder"):
        item = load(BP / "items" / (name + ".item.json"))["minecraft:item"]
        assert item["description"]["identifier"] == "tf_slice:" + name
        assert (RP / "textures" / "items" / (name + ".png")).is_file()
        assert "tf_slice:" + name in catalog_ids()

    cicada_jar = recipe("cicada_jar", "minecraft:recipe_shapeless")
    assert [entry["item"] for entry in cicada_jar["ingredients"]] == [
        "tf_slice:cicada",
        "minecraft:glass_bottle",
    ]
    lily = recipe("huge_lily_pad", "minecraft:recipe_shapeless")
    lily_inputs = [entry["item"] for entry in lily["ingredients"]]
    assert lily_inputs.count("minecraft:lily_pad") == 4
    assert lily_inputs.count("tf_slice:transformation_powder") == 1


def test_towerwood_stonecutter_route_no_longer_uses_dark_oak_planks():
    towerwood = recipe("towerwood", "minecraft:recipe_shapeless")
    assert towerwood["ingredients"] == [{"item": "tf_slice:dark_log"}]
    encased = recipe("encased_towerwood_stonecutting", "minecraft:recipe_shapeless")
    assert encased["ingredients"] == [{"item": "tf_slice:towerwood"}]
    metadata = load(ROOT / "docs" / "hydra_route_content.json")
    adaptation = metadata["platformAdaptations"]["encasedTowerwood"]
    assert adaptation["sourceInput"] == "twilightforest:towerwood"
    assert adaptation["implementedInput"] == "tf_slice:towerwood"


def test_restored_source_materials_are_obtainable_in_survival_loot():
    loot_names = set()
    for path in (BP / "loot_tables" / "chests" / "tf_slice").glob("*.json"):
        document = load(path)
        for pool in document.get("pools", []):
            for entry in pool.get("entries", []):
                loot_names.add(entry.get("name"))
    assert {
        "tf_slice:liveroot",
        "tf_slice:cicada",
        "tf_slice:transformation_powder",
    } <= loot_names
