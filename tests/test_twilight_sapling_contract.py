# -*- coding: utf-8 -*-
"""Player-visible contracts for Twilight oak, canopy and rainbow saplings."""

import json
import sys
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
TOOLS = ROOT / "tools"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from TwilightBossSlice import leaf_decay_logic
from tools import (
    build_biome_features,
    build_dark_forest_content,
    build_hydra_route_content,
    build_public_block_shapes,
)


NEW_SAPLINGS = {
    "twilight_oak_sapling": "twilight_oak_tree_feature",
    "canopy_sapling": "canopy_tree_feature",
    "rainbow_oak_sapling": "rainbow_oak_tree_feature",
}
SAPLINGS = dict(NEW_SAPLINGS)
SAPLINGS.update(
    {
        "darkwood_sapling": "darkwood_tree_feature",
        "mangrove_sapling": "twilight_mangrove_tree_feature",
    }
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TwilightSaplingPackContractTests(unittest.TestCase):
    def test_behavior_blocks_are_growable_non_solid_saplings(self):
        for name in SAPLINGS:
            block = load(BP / "netease_blocks" / (name + ".json"))[
                "minecraft:block"
            ]
            self.assertEqual(
                "tf_slice:" + name,
                block["description"]["identifier"],
            )
            self.assertEqual(
                [0, 1],
                block["description"]["states"][
                    "tf_slice:growth_stage"
                ],
            )
            components = block["components"]
            self.assertEqual(
                "geometry.tf_slice.wood_sapling",
                components["minecraft:geometry"],
            )
            self.assertEqual(
                {"enable": True, "tick_to_script": True},
                components["netease:random_tick"],
            )
            self.assertFalse(components["netease:solid"]["value"])
            self.assertTrue(
                {
                    "minecraft:grass",
                    "minecraft:grass_block",
                    "minecraft:dirt",
                    "minecraft:podzol",
                }.issubset(set(components["netease:may_place_on"]["block"]))
            )

    def test_resource_entries_and_upstream_textures_are_closed(self):
        client_blocks = load(RP / "blocks.json")
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        for name in SAPLINGS:
            identifier = "tf_slice:" + name
            self.assertEqual(identifier, client_blocks[identifier]["textures"])
            texture_path = atlas[identifier]["textures"]
            image_path = RP / (texture_path + ".png")
            self.assertTrue(image_path.is_file(), name)
            image = Image.open(image_path).convert("RGBA")
            self.assertEqual((16, 16), image.size)
            self.assertGreater(sum(pixel[3] > 0 for pixel in image.getdata()), 8)

    def test_saplings_are_localized_and_visible_in_the_catalog(self):
        catalog = load(BP / "item_catalog" / "crafting_item_catalog.json")
        catalog_ids = {
            item
            for category in catalog["minecraft:crafting_items_catalog"][
                "categories"
            ]
            for group in category["groups"]
            for item in group["items"]
        }
        en = (RP / "texts" / "en_US.lang").read_text(encoding="utf-8")
        zh = (RP / "texts" / "zh_CN.lang").read_text(encoding="utf-8")
        for name in SAPLINGS:
            identifier = "tf_slice:" + name
            self.assertIn(identifier, catalog_ids)
            self.assertIn("tile.%s.name=" % identifier, en)
            self.assertIn("tile.%s.name=" % identifier, zh)

    def test_generator_declares_every_new_sapling(self):
        self.assertEqual(
            set(NEW_SAPLINGS),
            set(build_public_block_shapes.TREE_SAPLINGS),
        )
        self.assertEqual(
            set(SAPLINGS),
            set(build_public_block_shapes.GROWABLE_SAPLINGS),
        )
        builder_source = Path(build_public_block_shapes.__file__).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "grows=sapling_name in GROWABLE_SAPLINGS",
            builder_source,
        )
        generated = build_public_block_shapes.sapling_document(
            "twilight_oak_sapling",
            "tf_slice:twilight_oak_sapling",
            grows=True,
        )
        self.assertEqual(
            [0, 1],
            generated["minecraft:block"]["description"]["states"][
                "tf_slice:growth_stage"
            ],
        )

    def test_route_generators_preserve_growable_existing_saplings(self):
        dark = build_dark_forest_content.ordinary_block(
            "darkwood_sapling"
        )["minecraft:block"]["components"]
        mangrove = build_hydra_route_content.block_document(
            "mangrove_sapling", translucent=True, no_collision=True
        )["minecraft:block"]["components"]
        expected = {"enable": True, "tick_to_script": True}
        self.assertEqual(expected, dark["netease:random_tick"])
        self.assertEqual(expected, mangrove["netease:random_tick"])
        self.assertEqual(
            [0, 1],
            build_dark_forest_content.ordinary_block("darkwood_sapling")[
                "minecraft:block"
            ]["description"]["states"]["tf_slice:growth_stage"],
        )
        self.assertEqual(
            [0, 1],
            build_hydra_route_content.block_document(
                "mangrove_sapling", translucent=True, no_collision=True
            )["minecraft:block"]["description"]["states"][
                "tf_slice:growth_stage"
            ],
        )


class TwilightSaplingGrowthContractTests(unittest.TestCase):
    def test_growth_features_and_source_random_tick_rule_are_mapped(self):
        for name, feature in SAPLINGS.items():
            self.assertEqual(
                "tf_slice:" + feature,
                leaf_decay_logic.sapling_feature("tf_slice:" + name),
            )
        self.assertFalse(leaf_decay_logic.should_grow_sapling(8, 0))
        self.assertTrue(leaf_decay_logic.should_grow_sapling(9, 0))
        self.assertFalse(leaf_decay_logic.should_grow_sapling(15, 1))
        self.assertTrue(leaf_decay_logic.should_grow_sapling(15, 7))

    def test_bone_meal_and_growth_stage_follow_source_rules(self):
        self.assertTrue(leaf_decay_logic.bonemeal_growth_succeeds(0.449))
        self.assertFalse(leaf_decay_logic.bonemeal_growth_succeeds(0.45))
        self.assertFalse(leaf_decay_logic.bonemeal_growth_succeeds(0.99))
        self.assertEqual("advance", leaf_decay_logic.sapling_growth_action(0))
        self.assertEqual("advance", leaf_decay_logic.sapling_growth_action(-1))
        self.assertEqual("grow", leaf_decay_logic.sapling_growth_action(1))
        self.assertEqual("grow", leaf_decay_logic.sapling_growth_action(9))

    def test_rainbow_tree_has_valid_chance_data_and_same_leaf_fallback(self):
        primary = load(
            BP / "netease_features" / "rainbow_oak_tree_feature.json"
        )["minecraft:tree_feature"]
        fallback = load(
            BP
            / "netease_features"
            / "rainbow_oak_tree_fallback_feature.json"
        )["minecraft:tree_feature"]
        self.assertEqual(
            {"numerator": 1, "denominator": 3},
            primary["canopy"]["variation_chance"],
        )
        self.assertEqual(
            "tf_slice:rainbow_oak_leaves",
            fallback["canopy"]["leaf_block"]["name"],
        )
        self.assertEqual(
            (
                "tf_slice:rainbow_oak_tree_feature",
                "tf_slice:rainbow_oak_tree_fallback_feature",
            ),
            leaf_decay_logic.sapling_feature_attempts(
                "tf_slice:rainbow_oak_sapling"
            ),
        )
        generated = build_biome_features.tree_feature(
            "test_tree", "minecraft:oak_log", "minecraft:oak_leaves",
            (4, 7), 2,
        )
        self.assertEqual(
            {"numerator": 1, "denominator": 3},
            generated["minecraft:tree_feature"]["canopy"][
                "variation_chance"
            ],
        )

    def test_rainbow_sapling_uses_proven_regular_tree_structures(self):
        self.assertEqual(
            "tf_slice:enchanted/runtime/regular_rainbow/v00/x00_z00",
            leaf_decay_logic.rainbow_sapling_structure(0),
        )
        self.assertEqual(
            "tf_slice:enchanted/runtime/regular_rainbow/v15/x00_z00",
            leaf_decay_logic.rainbow_sapling_structure(15),
        )
        self.assertEqual(
            "tf_slice:enchanted/runtime/regular_rainbow/v00/x00_z00",
            leaf_decay_logic.rainbow_sapling_structure(16),
        )
        self.assertIsNone(
            leaf_decay_logic.rainbow_sapling_structure("invalid")
        )
        self.assertEqual(
            (93, 59, 193),
            leaf_decay_logic.rainbow_sapling_structure_origin(
                (100, 64, 200)
            ),
        )
        clearance = leaf_decay_logic.rainbow_sapling_clearance_positions(
            (100, 64, 200)
        )
        self.assertEqual(225, len(clearance))
        self.assertIn((98, 64, 198), clearance)
        self.assertIn((102, 72, 202), clearance)
        self.assertTrue(
            leaf_decay_logic.rainbow_sapling_can_replace("minecraft:air")
        )
        self.assertTrue(
            leaf_decay_logic.rainbow_sapling_can_replace(
                "tf_slice:rainbow_oak_leaves_07"
            )
        )
        self.assertFalse(
            leaf_decay_logic.rainbow_sapling_can_replace("minecraft:stone")
        )
        self.assertTrue(
            leaf_decay_logic.rainbow_sapling_has_grown(
                "tf_slice:twilight_oak_log"
            )
        )
        self.assertFalse(
            leaf_decay_logic.rainbow_sapling_has_grown(
                "tf_slice:rainbow_oak_sapling"
            )
        )

        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        start = source.index("    def _grow_twilight_sapling(")
        end = source.index("\n    def _advance_twilight_sapling", start)
        grow_handler = source[start:end]
        self.assertIn("_grow_rainbow_sapling_structure(", grow_handler)
        self.assertIn(".PlaceStructure(", source)
        self.assertIn("rainbow_sapling_has_grown(", source)

    def test_server_places_features_for_random_tick_and_bone_meal(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"BlockRandomTickServerEvent", self.OnBlockRandomTickServerEvent',
            source,
        )
        self.assertIn("def _grow_twilight_sapling(", source)
        self.assertIn("def _advance_twilight_sapling(", source)
        self.assertIn(".PlaceFeature(", source)
        self.assertIn("sapling_feature_attempts(", source)
        self.assertIn("_try_bonemeal_twilight_sapling", source)
        random_start = source.index("    def OnBlockRandomTickServerEvent")
        random_end = source.index("\n    def ", random_start + 5)
        random_handler = source[random_start:random_end]
        self.assertIn("_advance_twilight_sapling(", random_handler)
        self.assertNotIn("_grow_twilight_sapling(", random_handler)

    def test_bone_meal_resolves_the_clicked_block_from_the_world(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        start = source.index("    def _try_bonemeal_twilight_sapling")
        end = source.index("\n    def ", start + 5)
        handler = source[start:end]
        self.assertIn("self._get_block(position, dimensionId)", handler)
        self.assertNotIn(
            'blockName = str(args.get("blockName"',
            handler,
        )
        self.assertNotIn('args["cancel"]', handler)
        self.assertIn('args["ret"] = True', handler)
        self.assertIn("bonemeal_growth_succeeds(random.random())", handler)
        self.assertIn("_advance_twilight_sapling(", handler)
        self.assertNotIn("_grow_twilight_sapling(", handler)

    def test_bone_meal_always_broadcasts_vanilla_growth_particles(self):
        server_source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"SaplingGrowthEffect",',
            server_source,
        )
        start = server_source.index("    def _try_bonemeal_twilight_sapling")
        end = server_source.index("\n    def ", start + 5)
        handler = server_source[start:end]
        self.assertIn("_broadcast_sapling_growth_effect(", handler)
        self.assertIn(
            '"SaplingGrowthEffect",',
            client_source,
        )
        self.assertIn("def OnSaplingGrowthEffect(", client_source)
        self.assertIn("minecraft:crop_growth_emitter", client_source)


if __name__ == "__main__":
    unittest.main()
