# -*- coding: utf-8 -*-
"""Survival recipe completeness for the currently ported public content."""

from __future__ import unicode_literals

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RECIPES = BP / "recipes"


EXPECTED_ITEM_OUTPUTS = {
    "tf_slice:block_and_chain",
    "tf_slice:carminite",
    "tf_slice:ironwood_axe",
    "tf_slice:ironwood_boots",
    "tf_slice:ironwood_chestplate",
    "tf_slice:ironwood_helmet",
    "tf_slice:ironwood_hoe",
    "tf_slice:ironwood_ingot",
    "tf_slice:ironwood_leggings",
    "tf_slice:ironwood_pickaxe",
    "tf_slice:ironwood_shovel",
    "tf_slice:ironwood_sword",
    "tf_slice:knightmetal_axe",
    "tf_slice:knightmetal_boots",
    "tf_slice:knightmetal_chestplate",
    "tf_slice:knightmetal_helmet",
    "tf_slice:knightmetal_leggings",
    "tf_slice:knightmetal_pickaxe",
    "tf_slice:knightmetal_ring",
    "tf_slice:knightmetal_shield",
    "tf_slice:knightmetal_sword",
    "tf_slice:steeleaf_axe",
    "tf_slice:steeleaf_boots",
    "tf_slice:steeleaf_chestplate",
    "tf_slice:steeleaf_helmet",
    "tf_slice:steeleaf_hoe",
    "tf_slice:steeleaf_ingot",
    "tf_slice:steeleaf_leggings",
    "tf_slice:steeleaf_pickaxe",
    "tf_slice:steeleaf_shovel",
    "tf_slice:steeleaf_sword",
}

EXPECTED_BLOCK_OUTPUTS = {
    "tf_slice:canopy_fence",
    "tf_slice:carminite_block",
    "tf_slice:carminite_builder",
    "tf_slice:carminite_reactor",
    "tf_slice:cicada_jar",
    "tf_slice:cracked_etched_nagastone",
    "tf_slice:cracked_mazestone",
    "tf_slice:cracked_nagastone_pillar",
    "tf_slice:cracked_nagastone_stairs_left",
    "tf_slice:cracked_nagastone_stairs_right",
    "tf_slice:cracked_towerwood",
    "tf_slice:cracked_underbrick",
    "tf_slice:cut_mazestone",
    "tf_slice:dark_button",
    "tf_slice:dark_hanging_sign",
    "tf_slice:dark_pressure_plate",
    "tf_slice:dark_sign",
    "tf_slice:dark_wood",
    "tf_slice:decorative_mazestone",
    "tf_slice:firefly_jar",
    "tf_slice:huge_lily_pad",
    "tf_slice:knightmetal_block",
    "tf_slice:mangrove_button",
    "tf_slice:mangrove_hanging_sign",
    "tf_slice:mangrove_pressure_plate",
    "tf_slice:mangrove_sign",
    "tf_slice:mangrove_wood",
    "tf_slice:mazestone_border",
    "tf_slice:mazestone_brick",
    "tf_slice:mazestone_mosaic",
    "tf_slice:mossy_etched_nagastone",
    "tf_slice:mossy_mazestone",
    "tf_slice:mossy_nagastone_pillar",
    "tf_slice:mossy_nagastone_stairs_left",
    "tf_slice:mossy_nagastone_stairs_right",
    "tf_slice:mossy_towerwood",
    "tf_slice:mossy_underbrick",
    "tf_slice:nagastone_stairs_left",
    "tf_slice:nagastone_stairs_right",
    "tf_slice:reappearing_block",
    "tf_slice:spiral_bricks",
    "tf_slice:stripped_dark_wood",
    "tf_slice:stripped_mangrove_wood",
    "tf_slice:towerwood",
    "tf_slice:underbrick_floor",
    "tf_slice:vanishing_block",
}


def load_recipe_documents():
    documents = []
    for path in sorted(RECIPES.glob("*.recipe.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        recipe_type = next(
            key for key in document if key.startswith("minecraft:recipe_")
        )
        documents.append((path, recipe_type, document[recipe_type]))
    return documents


def recipe_output(recipe_type, recipe):
    if recipe_type == "minecraft:recipe_furnace":
        return recipe.get("output")
    result = recipe.get("result", {})
    return result.get("item") if isinstance(result, dict) else result


def custom_definitions():
    identifiers = set()
    for folder, root_key in (("items", "minecraft:item"), ("netease_blocks", "minecraft:block")):
        for path in (BP / folder).glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            identifiers.add(document[root_key]["description"]["identifier"])
    return identifiers


def test_every_current_upstream_craftable_output_has_a_local_recipe():
    """As a survival player, every ported craftable output remains obtainable."""
    documents = load_recipe_documents()
    outputs = {recipe_output(recipe_type, recipe) for _path, recipe_type, recipe in documents}
    recipe_ids = {
        recipe["description"]["identifier"]
        for _path, _recipe_type, recipe in documents
    }
    expected = EXPECTED_ITEM_OUTPUTS | EXPECTED_BLOCK_OUTPUTS
    covered = outputs | recipe_ids
    assert expected <= covered, "missing recipes: %s" % sorted(expected - covered)


def test_maze_map_cloning_covers_every_crafting_grid_capacity():
    """As a maze explorer, I can clone one filled map onto 1..8 blank maps."""
    for blank_count in range(1, 9):
        path = RECIPES / ("maze_map_cloning_%d.recipe.json" % blank_count)
        assert path.is_file(), path.name
        recipe = json.loads(path.read_text(encoding="utf-8"))[
            "minecraft:recipe_shapeless"
        ]
        items = [ingredient["item"] for ingredient in recipe["ingredients"]]
        assert items.count("tf_slice:filled_maze_map") == 1
        assert items.count("tf_slice:maze_map") == blank_count
        assert recipe["result"] == {
            "item": "tf_slice:filled_maze_map",
            "count": blank_count + 1,
        }


def test_completed_recipes_have_unique_ids_and_closed_custom_references():
    """As a pack maintainer, the completed recipe set has no dangling references."""
    definitions = custom_definitions()
    seen = set()
    for path, recipe_type, recipe in load_recipe_documents():
        identifier = recipe["description"]["identifier"]
        assert identifier not in seen, "duplicate recipe id: %s" % identifier
        seen.add(identifier)
        if recipe_type != "minecraft:recipe_furnace":
            assert recipe.get("unlock") == {"context": "AlwaysUnlocked"}, path.name

        references = []
        if recipe_type == "minecraft:recipe_furnace":
            references.append(recipe.get("input"))
        else:
            references.extend(
                ingredient.get("item") for ingredient in recipe.get("ingredients", [])
            )
            references.extend(
                ingredient.get("item") for ingredient in recipe.get("key", {}).values()
            )
        output = recipe_output(recipe_type, recipe)
        references.append(output)
        dangling = sorted(
            reference
            for reference in references
            if reference and reference.startswith("tf_slice:") and reference not in definitions
        )
        assert not dangling, "%s: %s" % (path.name, dangling)
