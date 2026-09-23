# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path

from tools import build_mushroom_forest as mushroom_builder
from tools.native_structure_worldgen_safety import base_iterations


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
FEATURES = BP / "netease_features"
RULES = BP / "netease_feature_rules"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def feature_weights(identifier):
    document = read_json(FEATURES / ("%s.json" % identifier))
    return document["minecraft:weighted_random_feature"]["features"]


class MushroomForestGenerationContractTests(unittest.TestCase):
    def test_firefly_quota_and_red_cap_roll_match_upstream_boundaries(self):
        self.assertEqual(
            [0, 0, 0, 0, 0, 0, 1, 1, 2, 2],
            [mushroom_builder.firefly_quota(roll) for roll in range(10)],
        )
        self.assertEqual(
            ["vanilla"] * 33 + ["smooth"] * 33 + ["spheroid"] * 34,
            [mushroom_builder.red_cap_style(roll) for roll in range(1, 101)],
        )

    def test_canopy_cap_profiles_use_upstream_branch_head_radius_and_shells(self):
        brown = mushroom_builder.cap_offsets("flat")
        vanilla = mushroom_builder.cap_offsets("vanilla")
        smooth = mushroom_builder.cap_offsets("smooth")
        spheroid = mushroom_builder.cap_offsets("spheroid")

        self.assertEqual(21, len(brown))
        self.assertEqual({0}, {point[1] for point in brown})
        self.assertEqual(2, max(max(abs(x), abs(z)) for x, _, z in brown))

        self.assertEqual(set(range(-2, 2)), {point[1] for point in vanilla})
        for y in (-2, -1, 0):
            layer = {(x, z) for x, py, z in vanilla if py == y}
            self.assertNotIn((0, 0), layer)
            self.assertEqual(12, len(layer))
        self.assertEqual(
            {(x, z) for x in range(-1, 2) for z in range(-1, 2)},
            {(x, z) for x, y, z in vanilla if y == 1},
        )

        self.assertEqual(set(range(-1, 3)), {point[1] for point in smooth})
        self.assertNotIn((0, 0, 0), smooth)
        self.assertIn((0, 1, 0), smooth)
        self.assertEqual(3, max(max(abs(x), abs(z)) for x, _, z in smooth))

        self.assertEqual({-1, 0, 1}, {point[1] for point in spheroid})
        self.assertEqual(4, max(max(abs(x), abs(z)) for x, _, z in spheroid))
        self.assertEqual(
            4,
            max(max(abs(x), abs(z)) for x, y, z in spheroid if y == 0),
        )
        self.assertEqual(
            3,
            max(max(abs(x), abs(z)) for x, y, z in spheroid if y != 0),
        )

    def test_canopy_branches_run_horizontal_then_rise_vertically(self):
        points = mushroom_builder.branch_points((0, 4, 0), (5, 12, 3))
        horizontal = {point for point in points if point[1] == 4}
        vertical = {point for point in points if point[1] != 4}
        self.assertIn((0, 4, 0), horizontal)
        self.assertIn((5, 4, 3), horizontal)
        self.assertEqual(
            {(5, y, 3) for y in range(5, 13)},
            vertical,
        )

    def test_canopy_mushrooms_follow_upstream_shape_ranges_and_block_states(self):
        brown_metadata = []
        red_metadata = []
        cap_states = set()
        firefly_facings = set()
        facing_offsets = {
            "north": (0, 0, -1),
            "south": (0, 0, 1),
            "west": (-1, 0, 0),
            "east": (1, 0, 0),
        }

        for index in range(32):
            brown, brown_info = mushroom_builder.build_canopy_mushroom(
                "brown", 0xB001 + index * 977, "brown_%02d" % index
            )
            red, red_info = mushroom_builder.build_canopy_mushroom(
                "red", 0xD001 + index * 977, "red_%02d" % index
            )
            brown_metadata.append(brown_info)
            red_metadata.append(red_info)

            for structure in (brown, red):
                for position, (block_name, states, _) in structure.blocks.items():
                    if block_name == "minecraft:mushroom_stem":
                        self.assertEqual(10, states.get("huge_mushroom_bits"))
                    elif block_name in (
                        "minecraft:brown_mushroom_block",
                        "minecraft:red_mushroom_block",
                    ):
                        state = states.get("huge_mushroom_bits")
                        self.assertIn(state, range(1, 10))
                        cap_states.add(state)
                    elif block_name == "tf_slice:firefly":
                        facing = states["tf_slice:facing"]
                        firefly_facings.add(facing)
                        offset = facing_offsets[facing]
                        support = (
                            position[0] - offset[0],
                            position[1] - offset[1],
                            position[2] - offset[2],
                        )
                        self.assertEqual(
                            "minecraft:mushroom_stem",
                            structure.blocks[support][0],
                        )

        self.assertTrue(
            all(9 <= item["height"] <= 13 for item in brown_metadata)
        )
        self.assertEqual({3, 4}, {item["branch_count"] for item in brown_metadata})
        self.assertEqual({8, 9}, {item["branch_length"] for item in brown_metadata})
        self.assertTrue(
            all(12 <= item["height"] <= 16 for item in red_metadata)
        )
        self.assertEqual({3}, {item["branch_count"] for item in red_metadata})
        self.assertEqual({10, 11}, {item["branch_length"] for item in red_metadata})
        self.assertTrue(
            {"vanilla", "smooth", "spheroid"}.issubset(
                {item["cap_style"] for item in red_metadata}
            )
        )
        self.assertTrue(
            all(item["horizontal_reach"] >= 4 for item in brown_metadata + red_metadata)
        )
        self.assertTrue(
            all(item["cap_radius"] == 2 for item in brown_metadata)
        )
        self.assertTrue(
            all(item["cap_radius"] <= 4 for item in red_metadata)
        )
        self.assertTrue(
            all(
                len(item["branch_lengths"]) == item["branch_count"]
                for item in brown_metadata + red_metadata
            )
        )
        self.assertTrue(
            all(
                set(item["branch_lengths"]).issubset({8, 9})
                for item in brown_metadata
            )
        )
        self.assertTrue(
            all(
                set(item["branch_lengths"]).issubset({10, 11})
                for item in red_metadata
            )
        )
        self.assertNotIn("flat", {item["cap_style"] for item in red_metadata})
        self.assertGreaterEqual(len(firefly_facings), 3)
        self.assertEqual(set(range(1, 10)), cap_states)

    def test_generated_selectors_and_counts_match_upstream_registration(self):
        self.assertEqual(
            [
                ["tf_slice:brown_canopy_mushroom_trigger_feature", 60],
                ["tf_slice:red_canopy_mushroom_trigger_feature", 17],
                ["tf_slice:mushroom_canopy_dummy_feature", 323],
            ],
            feature_weights("mushroom_canopy_sparse_selector_feature"),
        )
        self.assertEqual(
            [
                ["tf_slice:brown_canopy_mushroom_trigger_feature", 1080],
                ["tf_slice:red_canopy_mushroom_trigger_feature", 117],
                ["tf_slice:mushroom_canopy_dummy_feature", 403],
            ],
            feature_weights("mushroom_canopy_dense_selector_feature"),
        )
        expected_rules = {
            "mushroom_canopy_sparse_feature_rule": (
                "tf_slice:mushroom_canopy_sparse_selector_feature",
                "3 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
                "tf_slice_biome_mushroom_forest",
            ),
            "mushroom_canopy_dense_feature_rule": (
                "tf_slice:mushroom_canopy_dense_selector_feature",
                "5 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
                "tf_slice_biome_dense_mushroom_forest",
            ),
        }
        for filename, (feature, iterations, biome_tag) in expected_rules.items():
            rule = read_json(RULES / ("%s.json" % filename))[
                "minecraft:feature_rules"
            ]
            self.assertEqual(feature, rule["description"]["places_feature"])
            self.assertEqual(
                iterations,
                base_iterations(rule["distribution"]["iterations"]),
            )
            self.assertEqual(
                "query.get_height_at(variable.worldx, variable.worldz)",
                rule["distribution"]["y"],
            )
            self.assertIn(biome_tag, json.dumps(rule["conditions"]))
        self.assertFalse(
            (RULES / "mushroom_vanilla_huge_feature_rule.json").exists()
        )
        for identifier in (
            "vanilla_mushroom_selector_feature",
            "vanilla_brown_mushroom_selector_feature",
            "vanilla_red_mushroom_selector_feature",
        ):
            self.assertFalse((FEATURES / ("%s.json" % identifier)).exists())
        self.assertFalse(
            (BP / "structures" / "tf_slice" / "mushroom" / "vanilla_brown").exists()
        )
        self.assertFalse(
            (BP / "structures" / "tf_slice" / "mushroom" / "vanilla_red").exists()
        )

        self.assertEqual(
            [
                ["tf_slice:mushroom_vanilla_oak_tree_feature", 3],
                ["tf_slice:mushroom_vanilla_birch_tree_feature", 4],
                ["tf_slice:mushroom_twilight_oak_tree_feature", 9],
            ],
            feature_weights("mushroom_vanilla_trees_selector_feature"),
        )
        for identifier in (
            "mushroom_vanilla_oak_tree_feature",
            "mushroom_vanilla_birch_tree_feature",
            "mushroom_twilight_oak_tree_feature",
        ):
            self.assertIn(
                "minecraft:tree_feature",
                read_json(FEATURES / ("%s.json" % identifier)),
                identifier,
            )
        tree_rule = read_json(
            RULES / "mushroom_biomes_vanilla_tree_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "(query.get_height_at(variable.worldx, variable.worldz)) + 64",
            tree_rule["distribution"]["y"],
        )

    def test_canopy_worldgen_uses_small_cancelled_triggers_and_chunk_pieces(self):
        from TwilightBossSlice import mushroom_worldgen_logic

        expected_triggers = {
            "brown": "tf_slice:mushroom/canopy_trigger/brown",
            "red": "tf_slice:mushroom/canopy_trigger/red",
        }
        self.assertEqual(
            expected_triggers,
            mushroom_worldgen_logic.TRIGGER_STRUCTURES,
        )
        for kind, structure_name in expected_triggers.items():
            trigger_path = (
                BP
                / "structures"
                / ("%s.mcstructure" % structure_name.replace(":", "/"))
            )
            parsed = mushroom_builder.read_structure_summary(trigger_path)
            self.assertEqual([1, 1, 1], parsed["size"])
            feature = read_json(
                FEATURES / ("%s_canopy_mushroom_trigger_feature.json" % kind)
            )["netease:structure_feature"]
            self.assertEqual(structure_name, feature["places_structure"])

        for kind, count in (("brown", 16), ("red", 24)):
            for index in range(count):
                pieces = list(
                    (
                        BP
                        / "structures"
                        / "tf_slice"
                        / "mushroom"
                        / "runtime"
                        / kind
                        / ("v%02d" % index)
                    ).glob("*.mcstructure")
                )
                self.assertGreater(len(pieces), 1)
                for piece in pieces:
                    parsed = mushroom_builder.read_structure_summary(piece)
                    self.assertLessEqual(parsed["size"][0], 16)
                    self.assertLessEqual(parsed["size"][2], 16)

        for stale_pattern in (
            "brown_canopy_mushroom_v*_feature.json",
            "red_canopy_mushroom_v*_feature.json",
        ):
            self.assertEqual([], list(FEATURES.glob(stale_pattern)))

    def test_canopy_runtime_logic_anchors_at_the_real_stem_and_filters_sites(self):
        from TwilightBossSlice import mushroom_worldgen_logic as logic

        self.assertEqual(
            (-311, 61, 183),
            logic.template_origin((-291, 66, 203)),
        )
        self.assertEqual(
            {
                (-20, 11), (-20, 12), (-20, 13),
                (-19, 11), (-19, 12), (-19, 13),
                (-18, 11), (-18, 12), (-18, 13),
            },
            set(logic.required_chunks((-311, 61, 183), [0, 0, 0, 31, 20, 31])),
        )
        for block_name in (
            "minecraft:grass_block",
            "minecraft:dirt",
            "minecraft:podzol",
            "minecraft:mycelium",
        ):
            self.assertTrue(logic.is_ground_support(block_name), block_name)
        for block_name in (
            "minecraft:water",
            "minecraft:flowing_water",
            "minecraft:oak_log",
            "tf_slice:twilight_oak_log",
            "minecraft:red_mushroom_block",
        ):
            self.assertFalse(logic.is_ground_support(block_name), block_name)

        for block_name in (
            "minecraft:air",
            "minecraft:tallgrass",
            "minecraft:oak_leaves",
            "tf_slice:twilight_oak_leaves",
        ):
            self.assertTrue(logic.is_canopy_replaceable(block_name), block_name)
        for block_name in (
            "minecraft:water",
            "minecraft:oak_log",
            "tf_slice:twilight_oak_log",
            "minecraft:red_mushroom_block",
            "minecraft:stone",
        ):
            self.assertFalse(logic.is_canopy_replaceable(block_name), block_name)

    def test_structures_replace_old_straight_tree_features(self):
        self.assertGreaterEqual(
            len(list((BP / "structures" / "tf_slice" / "mushroom").rglob("*.mcstructure"))),
            41,
        )
        for stale in (
            FEATURES / "brown_canopy_mushroom_tree_feature.json",
            FEATURES / "red_canopy_mushroom_tree_feature.json",
            FEATURES / "mushroom_forest_tree_profile_feature.json",
            FEATURES / "dense_mushroom_forest_tree_profile_feature.json",
            RULES / "mushroom_forest_tree_profile_feature_rule.json",
            RULES / "dense_mushroom_forest_tree_profile_feature_rule.json",
        ):
            self.assertFalse(stale.exists(), str(stale))

        metadata = read_json(BP / "metadata" / "mushroom_forest_generation.json")
        self.assertEqual("4.3.2508", metadata["source_version"])
        self.assertEqual(16, len(metadata["brown_canopy_variants"]))
        self.assertEqual(24, len(metadata["red_canopy_variants"]))
        self.assertEqual(
            {"brown": 60, "red": 17, "dummy": 323},
            metadata["selector_weights"]["sparse"],
        )
        self.assertEqual(
            {"brown": 1080, "red": 117, "dummy": 403},
            metadata["selector_weights"]["dense"],
        )
        self.assertEqual(
            "noop 1x1 trigger plus deferred chunk-piece placement",
            metadata["placement"],
        )
        self.assertEqual([4, 5, 6], metadata["mycelium_blob"]["radius"])
        self.assertNotIn("vanilla_huge_mushroom", metadata["attempts"])

    def test_mycelium_is_patchy_and_groundcover_can_attach_to_it(self):
        dense_biome = read_json(
            BP
            / "netease_biomes"
            / "dm33027004"
            / "dm33027004_mushroom_island.json"
        )["minecraft:biome"]
        self.assertEqual(
            "minecraft:grass",
            dense_biome["components"]["minecraft:surface_parameters"][
                "top_material"
            ],
        )
        patch_rule = read_json(
            RULES / "mushroom_mycelium_blob_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertAlmostEqual(
            100.0 / 3.0, patch_rule["distribution"]["scatter_chance"]
        )
        self.assertIn(
            "tf_slice_biome_mushroom_forest",
            json.dumps(patch_rule["conditions"]),
        )
        self.assertIn(
            "tf_slice_biome_dense_mushroom_forest",
            json.dumps(patch_rule["conditions"]),
        )

        for filename in (
            "forest_mushroom_feature.json",
            "forest_groundcover_feature.json",
            "mayapple_feature.json",
        ):
            feature = read_json(FEATURES / filename)
            single = feature["minecraft:single_block_feature"]
            self.assertIn(
                "minecraft:mycelium",
                single["may_attach_to"]["bottom"],
                filename,
            )
        mushgloom_patch = read_json(FEATURES / "mushgloom_patch_feature.json")
        self.assertEqual(
            96,
            mushgloom_patch["minecraft:scatter_feature"]["distribution"][
                "iterations"
            ],
        )

    def test_dense_mushroom_atmosphere_matches_regular_mushroom_forest(self):
        dense = read_json(
            RP / "biomes" / "dm33027004_mushroom_island.client_biome.json"
        )["minecraft:client_biome"]["components"]
        regular = read_json(
            RP / "biomes" / "dm33027004_mushroom_island_shore.client_biome.json"
        )["minecraft:client_biome"]["components"]
        self.assertEqual(
            regular["minecraft:sky_color"],
            dense["minecraft:sky_color"],
        )
        self.assertEqual(
            regular["minecraft:water_appearance"],
            dense["minecraft:water_appearance"],
        )

    def test_mushroom_tower_and_vanilla_creature_policy_remain_present(self):
        catalog = read_json(
            BP / "structures" / "tf_slice" / "ruins" / "structure_catalog_v1.json"
        )
        self.assertIn("mushroom_tower", json.dumps(catalog))
        from TwilightBossSlice import biome_catalog, spawn_policy

        dense_id = biome_catalog.BIOMES_BY_KEY["dense_mushroom_forest"]["identifier"]
        self.assertEqual(
            "mushroom_tower",
            biome_catalog.UNPORTED_LANDMARK_FALLBACK_BY_BIOME[dense_id],
        )
        for entity in ("minecraft:chicken", "minecraft:wolf"):
            self.assertFalse(
                spawn_policy.should_cancel_twilight_spawn(
                    {"dimensionId": 7, "identifier": entity},
                    7,
                    biome_identifier=dense_id,
                )
            )


if __name__ == "__main__":
    unittest.main()
