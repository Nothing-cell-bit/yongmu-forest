# -*- coding: utf-8 -*-
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import vanilla_block_adapter_logic


class VanillaBlockAdapterLogicTests(unittest.TestCase):
    def test_all_player_visible_wood_shapes_have_vanilla_templates(self):
        suffixes = (
            "stairs",
            "slab",
            "button",
            "fence",
            "fence_gate",
            "pressure_plate",
            "door",
            "trapdoor",
            "sign",
            "wall_sign",
            "hanging_sign",
            "wall_hanging_sign",
        )
        for family in ("dark", "mangrove"):
            vanilla_family = "dark_oak" if family == "dark" else family
            for suffix in suffixes:
                expected = (
                    "minecraft:%s_sign" % vanilla_family
                    if suffix == "wall_sign"
                    else "minecraft:%s_hanging_sign" % vanilla_family
                    if suffix == "wall_hanging_sign"
                    else "minecraft:%s_%s"
                    % (
                        vanilla_family,
                        suffix,
                    )
                )
                self.assertEqual(
                    expected,
                    vanilla_block_adapter_logic.VANILLA_BLOCK_ADAPTERS[
                        "tf_slice:%s_%s" % (family, suffix)
                    ],
                )

    def test_try_place_event_is_rewritten_before_vanilla_placement(self):
        args = {
            "fullName": "tf_slice:dark_door",
            "auxData": 0,
            "entityId": "player",
            "x": 3,
            "y": 64,
            "z": 5,
        }
        target = vanilla_block_adapter_logic.adapt_placement_event(args)
        self.assertEqual("minecraft:dark_oak_door", target)
        self.assertEqual("minecraft:dark_oak_door", args["fullName"])
        self.assertEqual("minecraft:dark_oak_door", args["blockName"])

    def test_unknown_block_event_is_unchanged(self):
        args = {"fullName": "tf_slice:hollow_dark_log_vertical"}
        before = copy.deepcopy(args)
        self.assertIsNone(
            vanilla_block_adapter_logic.adapt_placement_event(args)
        )
        self.assertEqual(before, args)

    def test_custom_stack_converts_to_vanilla_item_before_use(self):
        source = {
            "itemName": "tf_slice:dark_door",
            "newItemName": "tf_slice:dark_door",
            "count": 16,
            "auxValue": 0,
        }
        before = copy.deepcopy(source)
        converted = vanilla_block_adapter_logic.converted_vanilla_stack(
            source
        )
        self.assertEqual(before, source)
        self.assertEqual(
            {
                "itemName": "minecraft:dark_oak_door",
                "newItemName": "minecraft:dark_oak_door",
                "count": 16,
                "auxValue": 0,
            },
            converted,
        )

    def test_non_adapter_stack_does_not_convert(self):
        self.assertIsNone(
            vanilla_block_adapter_logic.converted_vanilla_stack(
                {"itemName": "tf_slice:hollow_dark_log_vertical", "count": 1}
            )
        )

    def test_server_keeps_inventory_ids_stable_until_placement(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"OnCarriedNewItemChangedServerEvent"', source)
        self.assertNotIn('"InventoryItemChangedServerEvent"', source)
        self.assertNotIn("def OnCarriedNewItemChangedServerEvent", source)
        self.assertNotIn("def OnInventoryItemChangedServerEvent", source)
        self.assertNotIn("_replace_inventory_adapter_item", source)
        self.assertNotIn("_normalize_player_adapter_inventory", source)
        client_ready = source[
            source.index("    def OnClientReady") :
            source.index("    def OnDimensionChangeServerEvent")
        ]
        self.assertNotIn("_normalize_player_adapter_inventory", client_ready)
        placement = source[
            source.index("    def OnServerEntityTryPlaceBlockEvent") :
            source.index("    def _orient_placed_trophy")
        ]
        self.assertIn(
            "vanilla_block_adapter_logic.adapt_placement_event(args)",
            placement,
        )

    def test_player_visible_native_templates_and_custom_exceptions_are_explicit(self):
        expected_native = {
            "minecraft:%s_%s" % (family, suffix)
            for family in ("dark_oak", "mangrove")
            for suffix in (
                "stairs",
                "slab",
                "button",
                "fence",
                "fence_gate",
                "pressure_plate",
                "door",
                "trapdoor",
                "sign",
                "hanging_sign",
            )
        } | {
            "minecraft:cherry_%s" % suffix
            for suffix in vanilla_block_adapter_logic.CANOPY_NATIVE_SUFFIXES
        }
        self.assertEqual(
            expected_native,
            set(vanilla_block_adapter_logic.PUBLIC_NATIVE_WOOD_ITEMS),
        )
        self.assertEqual(
            {
                "tf_slice:dark_banister",
                "tf_slice:mangrove_banister",
                "tf_slice:canopy_banister",
                "tf_slice:canopy_bookshelf",
                "tf_slice:canopy_chest",
            },
            set(vanilla_block_adapter_logic.PUBLIC_CUSTOM_WOOD_ITEMS),
        )

    def test_creative_catalog_keeps_only_real_custom_wood_blocks(self):
        catalog = json.loads(
            (
                BP / "item_catalog" / "crafting_item_catalog.json"
            ).read_text(encoding="utf-8")
        )
        items = {
            identifier
            for category in catalog["minecraft:crafting_items_catalog"][
                "categories"
            ]
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        for identifier in vanilla_block_adapter_logic.PUBLIC_NATIVE_WOOD_ITEMS:
            self.assertNotIn(identifier, items)
        for identifier in vanilla_block_adapter_logic.PUBLIC_CUSTOM_WOOD_ITEMS:
            self.assertIn(identifier, items)
        for identifier in vanilla_block_adapter_logic.MIGRATED_WOOD_ALIASES:
            self.assertNotIn(identifier, items)
            name = identifier.split(":", 1)[1]
            self.assertFalse(
                (BP / "netease_blocks" / (name + ".json")).exists()
            )

    def test_wood_shape_recipes_output_native_player_items(self):
        for recipe_path in (BP / "recipes").glob("*.recipe.json"):
            document = json.loads(recipe_path.read_text(encoding="utf-8"))
            recipe = document.get("minecraft:recipe_shaped", {})
            result = recipe.get("result", {})
            item = result.get("item")
            recipe_id = recipe.get("description", {}).get("identifier")
            if recipe_id not in vanilla_block_adapter_logic.MIGRATED_WOOD_ALIASES:
                continue
            self.assertEqual(
                vanilla_block_adapter_logic.player_visible_wood_item(
                    recipe_id
                ),
                item,
                recipe_path.name,
            )

    def test_public_shape_generator_keeps_only_stateful_banisters(self):
        from tools import build_public_block_shapes

        for family in ("dark", "mangrove"):
            block = build_public_block_shapes.banister_block_document(family)[
                "minecraft:block"
            ]
            self.assertEqual(24, len(block["permutations"]))
            for identifier in vanilla_block_adapter_logic.MIGRATED_WOOD_ALIASES:
                if identifier.startswith("tf_slice:%s_" % family):
                    name = identifier.split(":", 1)[1]
                    self.assertFalse(
                        (BP / "netease_blocks" / (name + ".json")).exists()
                    )
        canopy = build_public_block_shapes.banister_block_document(
            "canopy"
        )["minecraft:block"]
        self.assertEqual(24, len(canopy["permutations"]))
        for suffix in vanilla_block_adapter_logic.CANOPY_NATIVE_SUFFIXES:
            self.assertFalse(
                (
                    BP
                    / "netease_blocks"
                    / ("canopy_%s.json" % suffix)
                ).exists(),
                suffix,
            )

    def test_creative_generator_suppresses_automatic_registration(self):
        from tools import build_creative_catalog

        with tempfile.TemporaryDirectory() as directory:
            bp = Path(directory)
            blocks = bp / "netease_blocks"
            blocks.mkdir(parents=True)
            target = blocks / "mangrove_stairs.json"
            target.write_text(
                json.dumps(
                    {
                        "minecraft:block": {
                            "description": {
                                "identifier": "tf_slice:mangrove_stairs",
                                "register_to_creative_menu": True,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                0,
                build_creative_catalog.suppress_catalog_auto_registration(
                    bp, set()
                ),
            )
            self.assertEqual(
                1,
                build_creative_catalog.suppress_catalog_auto_registration(
                    bp, {"tf_slice:mangrove_stairs"}
                ),
            )
            hidden = json.loads(target.read_text(encoding="utf-8"))
            self.assertFalse(
                hidden["minecraft:block"]["description"][
                    "register_to_creative_menu"
                ]
            )

    def test_native_darkwood_templates_keep_twilight_display_names(self):
        english = (
            BP.parent / "TwilightBossSliceR" / "texts" / "en_US.lang"
        ).read_text(encoding="utf-8")
        chinese = (
            BP.parent / "TwilightBossSliceR" / "texts" / "zh_CN.lang"
        ).read_text(encoding="utf-8")
        expected = {
            "tile.dark_oak_stairs.name": ("Darkwood Stairs", "黑木楼梯"),
            "tile.wooden_slab.big_oak.name": ("Darkwood Slab", "黑木台阶"),
            "tile.darkOakFence.name": ("Darkwood Fence", "黑木栅栏"),
            "item.dark_oak_door.name": ("Darkwood Door", "黑木门"),
            "item.darkoak_sign.name": ("Darkwood Sign", "黑木告示牌"),
        }
        for key, (english_name, chinese_name) in expected.items():
            self.assertIn("%s=%s" % (key, english_name), english)
            self.assertIn("%s=%s" % (key, chinese_name), chinese)

    def test_targeted_recipe_migration_only_rewrites_native_equivalents(self):
        from tools import build_public_wood_native_items

        migrated = {
            "minecraft:recipe_shaped": {
                "result": {"item": "tf_slice:dark_stairs", "count": 4}
            }
        }
        self.assertTrue(
            build_public_wood_native_items.migrate_recipe_document(migrated)
        )
        self.assertEqual(
            "minecraft:dark_oak_stairs",
            migrated["minecraft:recipe_shaped"]["result"]["item"],
        )
        exception = {
            "minecraft:recipe_shaped": {
                "result": {"item": "tf_slice:dark_banister", "count": 1}
            }
        }
        self.assertFalse(
            build_public_wood_native_items.migrate_recipe_document(exception)
        )
        self.assertEqual(
            "tf_slice:dark_banister",
            exception["minecraft:recipe_shaped"]["result"]["item"],
        )

    def test_release_creative_gate_accepts_visible_custom_aliases(self):
        from tools import build_creative_catalog, validate_slice

        catalog = json.loads(
            (
                BP / "item_catalog" / "crafting_item_catalog.json"
            ).read_text(encoding="utf-8")
        )
        catalog_ids = {
            identifier
            for category in catalog["minecraft:crafting_items_catalog"][
                "categories"
            ]
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        self.assertTrue(build_creative_catalog.VANILLA_WOOD_TEMPLATE_IDS)
        self.assertTrue(
            set(build_creative_catalog.VANILLA_WOOD_TEMPLATE_IDS).isdisjoint(
                catalog_ids
            )
        )
        self.assertEqual(
            {"tf_slice:dark_banister", "tf_slice:mangrove_banister"},
            set(build_creative_catalog.PUBLIC_WOOD_SHAPE_IDS),
        )

        gate = validate_slice.Gate()
        documents = validate_slice.collect_json(gate)
        validate_slice.validate_creative_inventory(gate, documents)
        self.assertEqual([], gate.failures)


if __name__ == "__main__":
    unittest.main()
