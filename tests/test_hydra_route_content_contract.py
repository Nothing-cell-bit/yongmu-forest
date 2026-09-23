# -*- coding: utf-8 -*-
import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))


class HydraRouteSourceLockTests(unittest.TestCase):
    def test_route_source_lock_is_bound_to_exact_jar_and_six_textures(self):
        lock = json.loads((ROOT / "source_locks" / "hydra_route.json").read_text("utf-8"))
        self.assertEqual(
            "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778",
            lock["upstream"]["jarSha256"],
        )
        self.assertEqual(
            {"minotaur.png", "minoshroomtaur.png", "mazeslime.png", "mosquitoswarm.png", "hydra4.png", "hydramortar.png"},
            {Path(entry["source"]).name for entry in lock["textures"]},
        )
        self.assertGreaterEqual(len(lock["classes"]), 20)


class HydraRouteBiomeTests(unittest.TestCase):
    def test_custom_mangrove_tree_feature_avoids_vanilla_registry_collision(self):
        feature_name = "twilight_mangrove_tree_feature"
        feature_path = BP / "netease_features" / (feature_name + ".json")
        self.assertTrue(feature_path.is_file())
        self.assertFalse(
            (BP / "netease_features" / "mangrove_tree_feature.json").exists()
        )

        feature = json.loads(feature_path.read_text("utf-8"))[
            "minecraft:weighted_random_feature"
        ]
        feature_id = "tf_slice:" + feature_name
        self.assertEqual(feature_id, feature["description"]["identifier"])
        self.assertGreaterEqual(len(feature["features"]), 4)

        rule = json.loads(
            (
                BP
                / "netease_feature_rules"
                / "mangrove_tree_feature_rule.json"
            ).read_text("utf-8")
        )["minecraft:feature_rules"]
        projected_id = rule["description"]["places_feature"]
        self.assertEqual(
            "tf_slice:mangrove_tree_landmark_surface_project_feature",
            projected_id,
        )
        projection = json.loads(
            (
                BP
                / "netease_features"
                / (projected_id.split(":", 1)[1] + ".json")
            ).read_text("utf-8")
        )["minecraft:scatter_feature"]
        self.assertTrue(projection["project_input_to_floor"])
        self.assertEqual(feature_id, projection["places_feature"])

    def test_tree_root_support_lists_do_not_mix_namespaces(self):
        for path in (BP / "netease_features").glob("*_tree_feature.json"):
            payload = json.loads(path.read_text("utf-8"))
            tree = payload.get("minecraft:tree_feature")
            if tree is None:
                continue
            for field in ("base_block", "may_grow_on"):
                identifiers = tree.get(field, [])
                namespaces = {identifier.split(":", 1)[0] for identifier in identifiers}
                self.assertLessEqual(
                    len(namespaces),
                    1,
                    "%s mixes namespaces in %s: %s" % (path.name, field, sorted(namespaces)),
                )

    def test_dimension_uses_stable_fire_seed_and_immediate_swamp_companions(self):
        dimension = json.loads((BP / "netease_dimension" / "dm33027004.json").read_text("utf-8"))
        stages = dimension["netease:dimension_info"]["components"]["netease:biome_source"]
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        builder = importlib.import_module("tools.build_dark_forest_biomes")
        conditions = [stage for stage in stages if stage["type"] == "condition"]
        seed_specs = builder.route_seed_stage_specs()

        self.assertEqual(8, len(conditions))
        self.assertEqual(
            [
                "dm33027004_swampland",
                "dm33027004_swampland_mutated",
                "dm33027004_roofed_forest_mutated",
                "dm33027004_redwood_taiga_mutated",
            ]
            * 2,
            [stage["pool"][0] for stage in conditions],
        )
        self.assertEqual(
            catalog.route_biome_seed_condition(
                seed_specs[0]["geometryByVariant"],
            ),
            conditions[0]["condition"],
        )
        self.assertTrue(
            all("temp.variant =" in stage["condition"] for stage in conditions)
        )
        self.assertFalse(any(stage["type"] == "gen_key_biomes" for stage in stages))
        self.assertFalse(any(stage["type"] == "associated" for stage in stages))
        self.assertFalse(
            any(
                "get_neighborhood_is_biome" in stage["condition"]
                for stage in conditions
            )
        )

    def test_swamp_and_fire_swamp_files_exist_on_both_sides(self):
        for identifier in ("dm33027004_swampland", "dm33027004_swampland_mutated"):
            self.assertTrue((BP / "netease_biomes" / "dm33027004" / (identifier + ".json")).is_file())
            self.assertTrue((RP / "biomes" / (identifier + ".client_biome.json")).is_file())

    def test_internal_swamp_boundary_has_no_stream_transition(self):
        dimension = json.loads((BP / "netease_dimension" / "dm33027004.json").read_text("utf-8"))
        stages = dimension["netease:dimension_info"]["components"]["netease:biome_source"]
        pairs = {
            frozenset((stage["biome_a"], stage["biome_b"]))
            for stage in stages if stage.get("type") == "transition"
        }
        self.assertNotIn(
            frozenset(("dm33027004_swampland", "dm33027004_swampland_mutated")),
            pairs,
        )

    def test_release_validator_covers_both_route_landmark_trigger_modes(self):
        from tools import validate_slice

        self.assertIn("swamp", validate_slice.SURFACE_LANDMARK_MODES)
        self.assertIn("fire_swamp", validate_slice.SURFACE_LANDMARK_MODES)


class HydraRouteResourceTests(unittest.TestCase):
    def test_all_new_entities_are_registered_on_both_sides(self):
        identifiers = (
            "minotaur", "minoshroom", "maze_slime", "mosquito_swarm",
            "hydra", "hydra_head", "hydra_mortar",
        )
        for identifier in identifiers:
            self.assertTrue((BP / "entities" / (identifier + ".entity.json")).is_file(), identifier)
            self.assertTrue((RP / "entity" / (identifier + ".entity.json")).is_file(), identifier)

    def test_route_declares_complete_block_and_item_catalogs(self):
        catalog = json.loads((ROOT / "docs" / "hydra_route_content.json").read_text("utf-8"))
        self.assertEqual(8, len(catalog["mazestoneBlocks"]))
        self.assertEqual(12, len(catalog["mangroveBlocks"]))
        self.assertIn("mangrove_banister", catalog["mangroveBlocks"])
        self.assertNotIn("mangrove_stairs", catalog["mangroveBlocks"])
        self.assertNotIn("mangrove_chest", catalog["mangroveBlocks"])
        self.assertGreaterEqual(len(catalog["items"]), 45)
        for identifier in catalog["items"]:
            self.assertTrue((BP / "items" / (identifier + ".item.json")).is_file(), identifier)

    def test_boss_huds_are_registered(self):
        defs = json.loads((RP / "ui" / "_ui_defs.json").read_text("utf-8"))
        payload = json.dumps(defs)
        self.assertIn("minoshroom_boss_hud.json", payload)
        self.assertIn("hydra_boss_hud.json", payload)


if __name__ == "__main__":
    unittest.main()
