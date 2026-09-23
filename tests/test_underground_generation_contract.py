# -*- coding: utf-8 -*-
import json
import runpy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
TOOLS = ROOT / "tools"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog


ORE_SPECS = {
    "coal": ("minecraft:coal_ore", 16, 20, [-32, 127]),
    "iron": ("minecraft:iron_ore", 9, 20, [-32, 63]),
    "gold": ("minecraft:gold_ore", 9, 2, [-32, 31]),
    "redstone": ("minecraft:redstone_ore", 8, 8, [-32, 15]),
    "diamond": ("minecraft:diamond_ore", 8, 1, [-32, 15]),
    "lapis": ("minecraft:lapis_ore", 7, 2, [-32, 30]),
    "copper": ("minecraft:copper_ore", 10, 6, [-32, 96]),
}
ROCK_CLUSTER_SPECS = {
    "andesite": "minecraft:andesite",
    "diorite": "minecraft:diorite",
    "granite": "minecraft:granite",
}
STONE_REPLACEABLES = [
    {"name": "minecraft:stone"},
    {"name": "minecraft:deepslate"},
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class UndergroundOreGenerationContractTests(unittest.TestCase):
    def test_generator_keeps_one_canonical_upstream_parameter_table(self):
        script = TOOLS / "build_underground_features.py"
        self.assertTrue(script.is_file(), "underground feature builder is missing")
        module = runpy.run_path(str(script), run_name="underground_feature_contract")
        actual_ores = {
            key: (
                spec["block"],
                spec["vein_size"],
                spec["attempts"],
                spec["y_extent"],
            )
            for key, spec in module["ORE_SPECS"].items()
        }
        self.assertEqual(ORE_SPECS, actual_ores)
        self.assertEqual(ROCK_CLUSTER_SPECS, module["ROCK_CLUSTER_BLOCKS"])

    def test_all_seven_upstream_ores_have_exact_vein_and_height_rules(self):
        for key, (block, vein_size, attempts, y_extent) in ORE_SPECS.items():
            with self.subTest(ore=key):
                feature_name = "twilight_%s_ore_feature" % key
                feature_path = BP / "netease_features" / (feature_name + ".json")
                rule_path = (
                    BP
                    / "netease_feature_rules"
                    / (feature_name + "_rule.json")
                )
                self.assertTrue(feature_path.is_file())
                self.assertTrue(rule_path.is_file())

                feature = read_json(feature_path)["minecraft:ore_feature"]
                self.assertEqual("tf_slice:" + feature_name, feature["description"]["identifier"])
                self.assertEqual(vein_size, feature["count"])
                self.assertEqual(block, feature["replace_rules"][0]["places_block"])
                self.assertEqual(STONE_REPLACEABLES, feature["replace_rules"][0]["may_replace"])

                rule = read_json(rule_path)["minecraft:feature_rules"]
                self.assertEqual("underground_pass", rule["conditions"]["placement_pass"])
                self.assertEqual("tf_slice:" + feature_name, rule["description"]["places_feature"])
                self.assertEqual(attempts, rule["distribution"]["iterations"])
                self.assertEqual(
                    {"distribution": "uniform", "extent": y_extent},
                    rule["distribution"]["y"],
                )
                conditions = json.dumps(rule["conditions"])
                self.assertIn("dm33027004", conditions)
                self.assertNotIn("tf_slice_has_underground_roots", conditions)

    def test_small_stone_clusters_keep_burst_rarity_count_and_triangle_height(self):
        for key, block in ROCK_CLUSTER_SPECS.items():
            with self.subTest(cluster=key):
                ore_name = "twilight_%s_cluster_ore_feature" % key
                scatter_name = "twilight_%s_cluster_feature" % key
                ore = read_json(
                    BP / "netease_features" / (ore_name + ".json")
                )["minecraft:ore_feature"]
                scatter = read_json(
                    BP / "netease_features" / (scatter_name + ".json")
                )["minecraft:scatter_feature"]
                rule = read_json(
                    BP
                    / "netease_feature_rules"
                    / (scatter_name + "_rule.json")
                )["minecraft:feature_rules"]

                self.assertEqual(16, ore["count"])
                self.assertEqual(block, ore["replace_rules"][0]["places_block"])
                self.assertEqual(STONE_REPLACEABLES, ore["replace_rules"][0]["may_replace"])
                self.assertEqual("tf_slice:" + ore_name, scatter["places_feature"])
                self.assertEqual(5, scatter["distribution"]["iterations"])
                self.assertEqual(
                    {"distribution": "triangle", "extent": [-64, 64]},
                    scatter["distribution"]["y"],
                )
                self.assertEqual(1, rule["distribution"]["iterations"])
                self.assertEqual(10.0, rule["distribution"]["scatter_chance"])
                self.assertEqual("tf_slice:" + scatter_name, rule["description"]["places_feature"])


class UndergroundRootBiomeContractTests(unittest.TestCase):
    def test_roots_cover_every_land_biome_but_no_stream_or_lake(self):
        expected = {
            entry["identifier"] for entry in biome_catalog.BASE_SOURCE_BIOMES
        }
        self.assertEqual(expected, set(biome_catalog.UNDERGROUND_ROOT_BIOMES))

        tagged = set()
        for entry in biome_catalog.BIOMES:
            components = read_json(
                BP
                / "netease_biomes"
                / "dm33027004"
                / (entry["identifier"] + ".json")
            )["minecraft:biome"]["components"]
            if "tf_slice_has_underground_roots" in components:
                tagged.add(entry["identifier"])
        self.assertEqual(expected, tagged)
        self.assertIn(
            biome_catalog.BIOMES_BY_KEY["spooky_forest"]["identifier"],
            tagged,
        )
        self.assertTrue(biome_catalog.AQUATIC_BIOMES.isdisjoint(tagged))

    def test_root_rule_uses_the_dedicated_underground_biome_tag(self):
        rule = read_json(
            BP
            / "netease_feature_rules"
            / "wood_root_vein_feature_rule.json"
        )["minecraft:feature_rules"]
        encoded = json.dumps(rule["conditions"])
        self.assertIn("dm33027004", encoded)
        self.assertIn("tf_slice_has_underground_roots", encoded)
        self.assertNotIn("tf_slice_terrestrial_groundcover", encoded)


if __name__ == "__main__":
    unittest.main()
