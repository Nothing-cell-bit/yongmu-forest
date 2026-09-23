# -*- coding: utf-8 -*-
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(BP))

import build_dark_forest_content as dark_forest_builder
from TwilightBossSlice import biome_catalog
from TwilightBossSlice import magic_map_bitmap_cache

DARK_BLOCKS = set(dark_forest_builder.DARK_BLOCKS)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class DarkForestContentContractTests(unittest.TestCase):
    def test_full_validation_enforces_center_tree_no_exclusion(self):
        validator = (ROOT / "tools" / "validate_slice.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "def validate_dark_forest_center_tree_invariant(",
            validator,
        )
        main = validator[validator.index("def main(") :]
        self.assertIn(
            "validate_dark_forest_center_tree_invariant(gate, documents)",
            main,
        )

    def test_project_policy_forbids_center_tree_spatial_exclusion(self):
        policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        normalized = " ".join(policy.split())
        self.assertIn("Dark Forest canopy invariant", policy)
        self.assertIn(
            "must not contain a square, circular, radial, or coordinate gate",
            normalized,
        )

    def test_release_gate_requires_bounded_center_tree_search(self):
        from tools import validate_slice

        center_path = (
            validate_slice.BP
            / "netease_feature_rules"
            / "dark_forest_center_tree_profile_feature_rule.json"
        )
        search_path = (
            validate_slice.BP
            / "netease_features"
            / "dark_forest_center_tree_ground_search_feature.json"
        )
        documents = {
            center_path: {
                "minecraft:feature_rules": {
                    "description": {
                        "places_feature": (
                            "tf_slice:dark_forest_center_"
                            "tree_ground_search_feature"
                        )
                    },
                    "conditions": {"placement_pass": "after_surface_pass"},
                    "distribution": {"iterations": 16},
                }
            },
            search_path: {
                "minecraft:search_feature": {
                    "description": {
                        "identifier": (
                            "tf_slice:dark_forest_center_"
                            "tree_ground_search_feature"
                        ),
                    },
                    "places_feature": (
                        "tf_slice:dark_forest_center_tree_profile_feature"
                    ),
                    "search_volume": {
                        "min": [0, -64, 0],
                        "max": [0, 0, 0],
                    },
                    "search_axis": "-y",
                    "required_successes": 1,
                }
            },
        }
        gate = validate_slice.Gate()
        validate_slice.validate_dark_forest_center_tree_invariant(
            gate,
            documents,
        )
        self.assertEqual([], gate.failures)

        stale_path = (
            validate_slice.BP
            / "netease_features"
            / (
                "dark_tower_canopy_cleanup_"
                "neighborhood_sequence_feature.json"
            )
        )
        stale_documents = dict(documents)
        stale_documents[stale_path] = {"minecraft:sequence_feature": {}}
        stale_gate = validate_slice.Gate()
        validate_slice.validate_dark_forest_center_tree_invariant(
            stale_gate,
            stale_documents,
        )
        self.assertTrue(
            any("retired" in failure.lower() for failure in stale_gate.failures),
            stale_gate.failures,
        )

        cleanup_path = (
            validate_slice.BP
            / "netease_feature_rules"
            / "dark_tower_canopy_cleanup_feature_rule.json"
        )
        stale_cleanup_documents = dict(documents)
        stale_cleanup_documents[cleanup_path] = {
            "minecraft:feature_rules": {}
        }
        stale_cleanup_gate = validate_slice.Gate()
        validate_slice.validate_dark_forest_center_tree_invariant(
            stale_cleanup_gate,
            stale_cleanup_documents,
        )
        self.assertTrue(
            any(
                "post-tree" in failure.lower()
                for failure in stale_cleanup_gate.failures
            ),
            stale_cleanup_gate.failures,
        )

        missing_center_gate = validate_slice.Gate()
        validate_slice.validate_dark_forest_center_tree_invariant(
            missing_center_gate,
            {search_path: documents[search_path]},
        )
        self.assertTrue(
            any(
                "center tree rule is missing" in failure.lower()
                for failure in missing_center_gate.failures
            ),
            missing_center_gate.failures,
        )

    def test_natural_darkwood_profiles_use_chunk_safe_native_trees(self):
        """Biome decoration must not reach cross-chunk structure templates."""
        expected = {
            "darkwood_tree_feature": "tf_slice:hardened_dark_leaves",
            "darkwood_tree_center_feature": (
                "tf_slice:hardened_dark_leaves_center"
            ),
        }
        for identifier, leaf_block in expected.items():
            document = load(
                BP / "netease_features" / (identifier + ".json")
            )
            self.assertEqual(
                {"format_version", "minecraft:tree_feature"},
                set(document),
            )
            feature = document["minecraft:tree_feature"]
            self.assertEqual(
                "tf_slice:dark_log_vertical",
                feature["fancy_trunk"]["trunk_block"]["name"],
            )
            self.assertEqual(
                {"base": 16, "variance": 8, "scale": 1.0},
                feature["fancy_trunk"]["trunk_height"],
            )
            self.assertEqual(
                leaf_block,
                feature["fancy_canopy"]["leaf_block"]["name"],
            )
            self.assertEqual(4, feature["fancy_canopy"]["height"])
            self.assertEqual(6, feature["fancy_canopy"]["radius"])

    def test_builder_retires_cross_chunk_darkwood_outputs(self):
        original_bp = dark_forest_builder.BP
        with tempfile.TemporaryDirectory() as directory:
            temporary_bp = Path(directory) / "TwilightBossSliceB"
            feature_root = temporary_bp / "netease_features"
            structure_root = (
                temporary_bp
                / "structures"
                / "tf_slice"
                / "dark_forest"
                / "trees"
                / "darkwood_tree_feature"
            )
            feature_root.mkdir(parents=True)
            structure_root.mkdir(parents=True)
            for suffix in ("structure", "offset", "sequence"):
                (
                    feature_root
                    / ("darkwood_tree_feature_v00_%s_feature.json" % suffix)
                ).write_text("{}", encoding="utf-8")
            for suffix in ("ground_anchor", "ground_search", "anchor"):
                (
                    feature_root
                    / ("darkwood_tree_feature_%s_feature.json" % suffix)
                ).write_text("{}", encoding="utf-8")
            (structure_root / "v00.mcstructure").write_bytes(b"unsafe")

            dark_forest_builder.BP = temporary_bp
            try:
                variants = dark_forest_builder.build_chunk_safe_darkwood_tree(
                    "darkwood_tree_feature",
                    "tf_slice:hardened_dark_leaves",
                )
            finally:
                dark_forest_builder.BP = original_bp

            self.assertEqual(16, len(variants))
            self.assertFalse(structure_root.exists())
            self.assertEqual(
                [],
                list(feature_root.glob("darkwood_tree_feature_v*_feature.json")),
            )
            for suffix in ("ground_anchor", "ground_search", "anchor"):
                self.assertFalse(
                    (
                        feature_root
                        / ("darkwood_tree_feature_%s_feature.json" % suffix)
                    ).exists()
                )
            generated = load(feature_root / "darkwood_tree_feature.json")
            self.assertIn("minecraft:tree_feature", generated)
            self.assertNotIn("netease:structure_feature", json.dumps(generated))
            tree = generated["minecraft:tree_feature"]
            self.assertEqual(
                {"base": 16, "variance": 8, "scale": 1.0},
                tree["fancy_trunk"]["trunk_height"],
            )
            self.assertEqual(4, tree["fancy_canopy"]["height"])
            self.assertEqual(6, tree["fancy_canopy"]["radius"])
            self.assertEqual(
                [
                    "minecraft:air",
                    "minecraft:tallgrass",
                    "minecraft:double_plant",
                    "tf_slice:fallen_leaves",
                    "tf_slice:dark_leaves",
                    "tf_slice:hardened_dark_leaves",
                    "tf_slice:hardened_dark_leaves_center",
                ],
                tree["may_replace"],
            )
            self.assertEqual(
                tree["may_replace"], tree["may_grow_through"]
            )

    def test_complete_darkwood_family_is_registered(self):
        for identifier in DARK_BLOCKS:
            self.assertTrue(
                (BP / "netease_blocks" / (identifier + ".json")).is_file(),
                identifier,
            )
        for identifier in ("dark_boat", "dark_chest_boat"):
            self.assertTrue(
                (BP / "items" / (identifier + ".item.json")).is_file(),
                identifier,
            )
        client_blocks = load(RP / "blocks.json")
        for identifier in DARK_BLOCKS:
            self.assertIn("tf_slice:" + identifier, client_blocks)

    def test_log_and_wood_blocks_expose_all_three_axes(self):
        for identifier in (
            "dark_log",
            "dark_wood",
            "stripped_dark_log",
            "stripped_dark_wood",
        ):
            block = load(BP / "netease_blocks" / (identifier + ".json"))[
                "minecraft:block"
            ]
            self.assertEqual(
                ["y", "x", "z"],
                block["description"]["states"]["tf_slice:axis"],
            )
            conditions = [
                permutation["condition"]
                for permutation in block["permutations"]
            ]
            self.assertTrue(any("== 'x'" in value for value in conditions))
            self.assertTrue(any("== 'z'" in value for value in conditions))

    def test_darkwood_trees_keep_source_shape_metadata_off_runtime_path(self):
        vertical_log = load(
            BP / "netease_blocks" / "dark_log_vertical.json"
        )["minecraft:block"]
        self.assertNotIn("states", vertical_log["description"])
        self.assertNotIn("permutations", vertical_log)
        self.assertFalse(
            vertical_log["description"]["register_to_creative_menu"]
        )

        metadata = load(BP / "metadata" / "dark_forest_tree_generation.json")
        self.assertEqual("4.3.2508", metadata["sourceVersion"])
        self.assertEqual(
            "bounded_ground_search_dense_fancy_tree_feature",
            metadata["generationMode"],
        )
        self.assertNotIn("centerPlacementMode", metadata)
        self.assertEqual(16, metadata["attemptsPerChunk"])
        self.assertEqual(64, metadata["groundSearchDepth"])
        self.assertEqual(4, metadata["runtimeCanopyHeight"])
        self.assertEqual(0, metadata["activeVariantCountPerProfile"])
        self.assertEqual(
            [37, 34, 37], metadata["retiredStructureTemplateBounds"]
        )
        self.assertEqual(16, metadata["variantCountPerProfile"])
        self.assertEqual("tf_slice:dark_log_vertical", metadata["logBlock"])
        self.assertEqual(4, metadata["branchCount"])
        self.assertEqual([8.0, 10.0], metadata["configuredBranchLengthRange"])
        self.assertEqual(8.0, metadata["effectiveBranchLength"])
        self.assertEqual(3, metadata["branchStartOffsetDown"])
        self.assertEqual(0.23, metadata["branchPitch"])
        self.assertEqual(0.23, metadata["branchYawSpacing"])
        self.assertEqual(4.5, metadata["foliage"]["horizontalRadius"])
        self.assertEqual(2.25, metadata["foliage"]["verticalRadius"])
        self.assertEqual(36, metadata["foliage"]["shagFactor"])
        self.assertEqual(
            "conditional_natural_block_cluster",
            metadata["roots"]["placementMode"],
        )
        self.assertEqual(-4, metadata["roots"]["clusterOffsetY"])
        self.assertEqual(12, metadata["roots"]["rootCount"])
        self.assertEqual(2, metadata["roots"]["liverootCount"])

        expected = {
            "darkwood_tree_feature": "tf_slice:hardened_dark_leaves",
            "darkwood_tree_center_feature": (
                "tf_slice:hardened_dark_leaves_center"
            ),
        }
        for identifier, leaf_block in expected.items():
            profile = metadata["profiles"][identifier]
            self.assertEqual(leaf_block, profile["leafBlock"])
            self.assertEqual(16, len(profile["variants"]))
            self.assertTrue(
                all(9 <= variant["configuredHeight"] <= 11 for variant in profile["variants"])
            )
            self.assertTrue(
                all(variant["branchCount"] == 4 for variant in profile["variants"])
            )
            for variant in range(16):
                structure, variant_metadata = dark_forest_builder.darkwood_tree_structure(
                    identifier,
                    leaf_block,
                    variant,
                )
                authored = {
                    block[0] for block in structure.blocks.values()
                }
                self.assertNotIn("tf_slice:root_block", authored)
                self.assertNotIn("tf_slice:liveroot_block", authored)
                self.assertEqual(0, variant_metadata["rootCount"])
                self.assertEqual([], variant_metadata["rootEnds"])

        root_feature = load(
            BP / "netease_features" / "darkwood_tree_root_ore_feature.json"
        )["minecraft:ore_feature"]
        liveroot_feature = load(
            BP / "netease_features" / "darkwood_tree_liveroot_ore_feature.json"
        )["minecraft:ore_feature"]
        self.assertEqual(12, root_feature["count"])
        self.assertEqual(2, liveroot_feature["count"])
        replaceable = {
            entry["name"]
            for rule in root_feature["replace_rules"]
            for entry in rule["may_replace"]
        }
        self.assertEqual(
            {
                "minecraft:dirt",
                "minecraft:grass_block",
                "minecraft:gravel",
                "minecraft:podzol",
                "minecraft:stone",
                "minecraft:deepslate",
            },
            replaceable,
        )
        self.assertTrue(
            all("underbrick" not in block for block in replaceable)
        )

    def test_native_darkwood_trees_use_the_known_good_fancy_tree_contract(self):
        replaceable = [
            "minecraft:air",
            "minecraft:tallgrass",
            "minecraft:double_plant",
            "tf_slice:fallen_leaves",
            "tf_slice:dark_leaves",
            "tf_slice:hardened_dark_leaves",
            "tf_slice:hardened_dark_leaves_center",
        ]
        grow_through = list(replaceable)
        for identifier in (
            "darkwood_tree_feature",
            "darkwood_tree_center_feature",
        ):
            document = load(
                BP / "netease_features" / (identifier + ".json")
            )
            self.assertNotIn("netease:structure_feature", json.dumps(document))
            tree = document["minecraft:tree_feature"]
            self.assertEqual(replaceable, tree["may_replace"])
            self.assertEqual(grow_through, tree["may_grow_through"])
            self.assertIn("fancy_trunk", tree)
            self.assertIn("fancy_canopy", tree)
            self.assertEqual(4, tree["fancy_canopy"]["height"])
            self.assertNotIn("trunk", tree)
            self.assertNotIn("canopy", tree)
            self.assertIn("minecraft:grass_block", tree["may_grow_on"])
            self.assertIn("minecraft:podzol", tree["may_grow_on"])

    def test_darkwood_canopy_density_closes_at_least_ninety_nine_percent(self):
        attempts = dark_forest_builder.SAFE_DARK_FOREST_TREE_ATTEMPTS
        radius = dark_forest_builder.SAFE_DARKWOOD_CANOPY_RADIUS
        darkwood_fraction = 0.93
        projected_area = math.pi * radius * radius
        expected_coverage = 1.0 - math.exp(
            -attempts * darkwood_fraction * projected_area / 256.0
        )
        self.assertGreaterEqual(expected_coverage, 0.995)

    def test_dark_forest_tree_rules_use_one_bounded_ground_search(self):
        original_bp = dark_forest_builder.BP
        with tempfile.TemporaryDirectory() as directory:
            temporary_bp = Path(directory) / "TwilightBossSliceB"
            feature_root = temporary_bp / "netease_features"
            feature_root.mkdir(parents=True)
            for stale_name in (
                "dark_forest_tree_batches_feature.json",
                "dark_forest_darkwood_batch_feature.json",
                (
                    "dark_forest_tree_profile_"
                    "landmark_surface_project_feature.json"
                ),
                "dark_forest_center_tree_mix_batch_feature.json",
                (
                    "dark_forest_center_tree_mix_"
                    "aerial_grounded_feature.json"
                ),
                (
                    "dark_forest_center_tree_profile_"
                    "landmark_surface_project_feature.json"
                ),
            ):
                (feature_root / stale_name).write_text(
                    "{}", encoding="utf-8"
                )
            dark_forest_builder.BP = temporary_bp
            try:
                dark_forest_builder.build_tree_profile(
                    "dark_forest",
                    "dark_forest_tree_profile_feature",
                    "darkwood_tree_feature",
                )
                dark_forest_builder.build_tree_profile(
                    "dark_forest_center",
                    "dark_forest_center_tree_profile_feature",
                    "darkwood_tree_center_feature",
                )
                dark_forest_builder.normalize_landmark_surface_decorations(
                    Path(directory)
                )
            finally:
                dark_forest_builder.BP = original_bp

            feature_root = temporary_bp / "netease_features"
            profiles = {
                "dark_forest": (
                    "dark_forest_tree_profile_feature",
                    "dark_forest_tree_ground_search_feature",
                ),
                "dark_forest_center": (
                    "dark_forest_center_tree_profile_feature",
                    "dark_forest_center_tree_ground_search_feature",
                ),
            }
            for biome_key, (profile_name, search_name) in profiles.items():
                rule = load(
                    Path(directory)
                    / "TwilightBossSliceB"
                    / "netease_feature_rules"
                    / (biome_key + "_tree_profile_feature_rule.json")
                )["minecraft:feature_rules"]
                self.assertEqual(
                    "tf_slice:" + search_name,
                    rule["description"]["places_feature"],
                )
                self.assertEqual(
                    "after_surface_pass",
                    rule["conditions"]["placement_pass"],
                )
                distribution = rule["distribution"]
                self.assertEqual(16, distribution["iterations"])
                self.assertNotIn("? 0", str(distribution))
                self.assertNotIn("6400", str(distribution))
                self.assertNotIn("math.abs", str(distribution))
                self.assertEqual(
                    {"distribution": "uniform", "extent": [0, 15]},
                    distribution["x"],
                )
                self.assertEqual(
                    {"distribution": "uniform", "extent": [0, 15]},
                    distribution["z"],
                )
                search = load(
                    feature_root / (search_name + ".json")
                )["minecraft:search_feature"]
                self.assertEqual(
                    "tf_slice:" + profile_name,
                    search["places_feature"],
                )
                profile = load(
                    feature_root / (profile_name + ".json")
                )["minecraft:weighted_random_feature"]
                expected_darkwood = (
                    "darkwood_tree_center_feature"
                    if biome_key == "dark_forest_center"
                    else "darkwood_tree_feature"
                )
                self.assertEqual(
                    [
                        ["tf_slice:forest_vanilla_birch_tree_feature", 4],
                        ["tf_slice:forest_vanilla_oak_tree_feature", 3],
                        ["tf_slice:" + expected_darkwood, 93],
                    ],
                    profile["features"],
                )
                self.assertEqual(
                    [0, -64, 0], search["search_volume"]["min"]
                )
                self.assertEqual(
                    [0, 0, 0], search["search_volume"]["max"]
                )
                self.assertEqual("-y", search["search_axis"])

            self.assertEqual(
                [],
                list(feature_root.glob("dark_forest*_batch*_feature.json")),
            )
            self.assertEqual(
                [],
                list(
                    feature_root.glob(
                        "dark_forest*_tree_batches_feature.json"
                    )
                ),
            )
            self.assertEqual(
                [],
                list(
                    feature_root.glob(
                        "dark_forest_center_*aerial*_feature.json"
                    )
                ),
            )

    def test_compiled_dark_forest_tree_rules_use_bounded_ground_search(self):
        profiles = {
            "dark_forest": "dark_forest_tree_ground_search_feature",
            "dark_forest_center": (
                "dark_forest_center_tree_ground_search_feature"
            ),
        }
        for biome_key, search_name in profiles.items():
            compiled_rule = load(
                BP
                / "netease_feature_rules"
                / (biome_key + "_tree_profile_feature_rule.json")
            )["minecraft:feature_rules"]
            self.assertEqual(
                "tf_slice:" + search_name,
                compiled_rule["description"]["places_feature"],
            )
            iterations = compiled_rule["distribution"]["iterations"]
            self.assertEqual(16, iterations)
            self.assertNotIn("? 0", str(compiled_rule["distribution"]))
            self.assertNotIn("6400", str(compiled_rule["distribution"]))
            self.assertNotIn(
                "math.abs",
                str(compiled_rule["distribution"]),
            )

    def test_darkwood_spheroid_uses_source_vertical_bias(self):
        class ConstantRandom(object):
            def random(self):
                return 0.5

        structure = dark_forest_builder.SparseStructure(
            (25, 25, 25), "source_spheroid_contract"
        )
        dark_forest_builder.place_source_spheroid(
            structure,
            (12, 12, 12),
            5.5,
            "tf_slice:hardened_dark_leaves",
            ConstantRandom(),
        )

        # The upstream positive bias fills the upper shoulder but narrows the
        # matching lower shoulder.  Treating negative dy as dy + bias makes
        # the lower half incorrectly full and symmetric.
        self.assertIn((13, 14, 12), structure.blocks)
        self.assertNotIn((13, 10, 12), structure.blocks)

    def test_dark_forest_tree_density_uses_one_bounded_search_profile(self):
        outer_rule = load(
            BP
            / "netease_feature_rules"
            / "dark_forest_tree_profile_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "after_surface_pass",
            outer_rule["conditions"]["placement_pass"],
        )
        self.assertEqual(
            "tf_slice:dark_forest_tree_ground_search_feature",
            outer_rule["description"]["places_feature"],
        )
        self.assertEqual(16, outer_rule["distribution"]["iterations"])

        center_rule = load(
            BP
            / "netease_feature_rules"
            / "dark_forest_center_tree_profile_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "after_surface_pass",
            center_rule["conditions"]["placement_pass"],
        )
        self.assertEqual(
            "tf_slice:dark_forest_center_tree_ground_search_feature",
            center_rule["description"]["places_feature"],
        )
        self.assertEqual(16, center_rule["distribution"]["iterations"])
        self.assertNotIn("? 0", str(center_rule["distribution"]))
        self.assertNotIn("6400", str(center_rule["distribution"]))

        center_search = load(
            BP
            / "netease_features"
            / "dark_forest_center_tree_ground_search_feature.json"
        )["minecraft:search_feature"]
        self.assertEqual(
            [0, -64, 0], center_search["search_volume"]["min"]
        )
        self.assertEqual(1, center_search["required_successes"])
        self.assertFalse(
            (
                BP
                / "netease_feature_rules"
                / "dark_tower_canopy_cleanup_feature_rule.json"
            ).exists()
        )
        self.assertFalse(
            (
                BP
                / "netease_features"
                / (
                    "dark_tower_canopy_cleanup_"
                    "neighborhood_sequence_feature.json"
                )
            ).exists()
        )
        self.assertEqual(
            [],
            list(
                (BP / "netease_features").glob(
                    "dark_tower_canopy_cleanup_offset_*_feature.json"
                )
            ),
        )

        for mix_name, darkwood_name in (
            ("dark_forest_tree_profile_feature", "darkwood_tree_feature"),
            (
                "dark_forest_center_tree_profile_feature",
                "darkwood_tree_center_feature",
            ),
        ):
            mix = load(BP / "netease_features" / (mix_name + ".json"))[
                "minecraft:weighted_random_feature"
            ]
            self.assertEqual(
                [
                    ["tf_slice:forest_vanilla_birch_tree_feature", 4],
                    ["tf_slice:forest_vanilla_oak_tree_feature", 3],
                    ["tf_slice:" + darkwood_name, 93],
                ],
                mix["features"],
            )

    def test_center_tree_ground_search_avoids_chunk_pp_floor_projection(self):
        """The NetEase center-biome worker must not floor-project trees."""
        feature_path = (
            BP
            / "netease_features"
            / "dark_forest_center_tree_ground_search_feature.json"
        )
        document = load(feature_path)
        self.assertNotIn("minecraft:scatter_feature", document)
        search = document["minecraft:search_feature"]
        self.assertEqual(
            "tf_slice:dark_forest_center_tree_profile_feature",
            search["places_feature"],
        )
        self.assertEqual(
            {"min": [0, -64, 0], "max": [0, 0, 0]},
            search["search_volume"],
        )
        self.assertEqual("-y", search["search_axis"])
        self.assertEqual(1, search["required_successes"])
        self.assertFalse(
            (
                BP
                / "netease_feature_rules"
                / "dark_tower_canopy_cleanup_feature_rule.json"
            ).exists(),
            "post-tree cleanup is unreliable; prevention must be authoritative",
        )

    def test_center_search_retires_the_post_tree_cleanup_rule(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            temporary_bp = Path(directory) / "TwilightBossSliceB"
            stale_feature_dir = temporary_bp / "netease_features"
            stale_feature_dir.mkdir(parents=True)
            for stale_name in (
                "dark_tower_canopy_cleanup_neighborhood_sequence_feature",
                "dark_tower_canopy_cleanup_offset_m1_m1_feature",
                "dark_tower_canopy_cleanup_offset_p1_p1_feature",
            ):
                (stale_feature_dir / (stale_name + ".json")).write_text(
                    "{}",
                    encoding="utf-8",
                )
            with mock.patch.object(
                dark_forest_builder,
                "BP",
                temporary_bp,
            ):
                dark_forest_builder.build_tree_profile(
                    "dark_forest_center",
                    "dark_forest_center_tree_profile_feature",
                    "darkwood_tree_center_feature",
                )

            tree_rule = load(
                temporary_bp
                / "netease_feature_rules"
                / "dark_forest_center_tree_profile_feature_rule.json"
            )["minecraft:feature_rules"]
            self.assertEqual(
                "tf_slice:dark_forest_center_tree_ground_search_feature",
                tree_rule["description"]["places_feature"],
            )
            self.assertEqual(16, tree_rule["distribution"]["iterations"])

            search = load(
                temporary_bp
                / "netease_features"
                / "dark_forest_center_tree_ground_search_feature.json"
            )["minecraft:search_feature"]
            self.assertEqual(
                "tf_slice:dark_forest_center_tree_profile_feature",
                search["places_feature"],
            )
            self.assertEqual(
                [0, -64, 0], search["search_volume"]["min"]
            )
            self.assertFalse(
                (
                    temporary_bp
                    / "netease_feature_rules"
                    / "dark_tower_canopy_cleanup_feature_rule.json"
                ).exists()
            )
            self.assertEqual(
                [],
                list(
                    (temporary_bp / "netease_features").glob(
                        "dark_tower_canopy_cleanup_offset_*_feature.json"
                    )
                ),
            )
            self.assertFalse(
                (
                    temporary_bp
                    / "netease_features"
                    / (
                        "dark_tower_canopy_cleanup_"
                        "neighborhood_sequence_feature.json"
                    )
                ).exists()
            )

    def test_dark_forest_canopy_is_formed_only_by_source_tree_batches(self):
        """The upstream biomes do not contain a biome-wide leaf-slab feature."""
        for biome_key in ("dark_forest", "dark_forest_center"):
            self.assertFalse(
                (
                    BP
                    / "netease_feature_rules"
                    / (biome_key + "_canopy_feature_rule.json")
                ).exists()
            )
            self.assertEqual(
                [],
                list(
                    (BP / "netease_features").glob(
                        biome_key + "_canopy_*_feature.json"
                    )
                ),
            )

            profile_rule = load(
                BP
                / "netease_feature_rules"
                / (biome_key + "_tree_profile_feature_rule.json")
            )["minecraft:feature_rules"]
            expected = "tf_slice:%s_tree_ground_search_feature" % biome_key
            self.assertEqual(
                expected,
                profile_rule["description"]["places_feature"],
            )

    def test_dark_leaf_textures_are_prebaked_for_netease_rendering(self):
        atlas = load(RP / "textures" / "terrain_texture.json")["texture_data"]
        expected = {
            "tf_slice:dark_leaves": (59, 94, 63),
            "tf_slice:hardened_dark_leaves": (59, 94, 63),
            "tf_slice:hardened_dark_leaves_center": (233, 78, 20),
        }
        source_path = (
            ROOT.parent
            / "twilightforest-1.20.1-4.3.2508-extracted"
            / "00_original_tree"
            / "assets"
            / "twilightforest"
            / "textures"
            / "block"
            / "darkwood_leaves.png"
        )
        with Image.open(source_path) as source_image:
            source = source_image.convert("RGBA")
            source_pixels = list(source.getdata())
        for identifier, tint in expected.items():
            texture_entry = atlas[identifier]["textures"]
            self.assertIsInstance(texture_entry, str)
            local_name = identifier.split(":", 1)[1]
            with Image.open(
                RP / "textures" / "blocks" / (local_name + ".png")
            ) as generated_image:
                generated = generated_image.convert("RGBA")
                generated_pixels = list(generated.getdata())
            self.assertEqual(source.size, generated.size)
            self.assertTrue(any(r != g or g != b for r, g, b, _a in generated_pixels))
            for original, rendered in zip(source_pixels, generated_pixels):
                self.assertEqual(
                    tuple(
                        (original[channel] * tint[channel] + 127) // 255
                        for channel in range(3)
                    )
                    + (original[3],),
                    rendered,
                )

    def test_dark_leaf_blocks_match_source_strength_and_occlusion_roles(self):
        ordinary = load(BP / "netease_blocks" / "dark_leaves.json")[
            "minecraft:block"
        ]["components"]
        hardened = load(BP / "netease_blocks" / "hardened_dark_leaves.json")[
            "minecraft:block"
        ]["components"]
        center = load(
            BP / "netease_blocks" / "hardened_dark_leaves_center.json"
        )["minecraft:block"]["components"]
        for components in (ordinary, hardened):
            self.assertEqual(
                2.0,
                components["minecraft:destructible_by_mining"][
                    "seconds_to_destroy"
                ],
            )
            self.assertEqual(
                10.0,
                components["minecraft:destructible_by_explosion"][
                    "explosion_resistance"
                ],
            )
        self.assertEqual(2.0, center["minecraft:destroy_time"]["value"])
        self.assertEqual(
            10.0, center["minecraft:explosion_resistance"]["value"]
        )
        self.assertEqual("optionalAlpha", ordinary["netease:render_layer"]["value"])
        self.assertEqual("opaque", hardened["netease:render_layer"]["value"])
        self.assertEqual("opaque", center["netease:render_layer"]["value"])

    def test_dark_forests_use_the_six_source_groundcover_profiles(self):
        biome_paths = {
            "dark_forest": "dm33027004_roofed_forest_mutated.json",
            "dark_forest_center": "dm33027004_redwood_taiga_mutated.json",
        }
        for biome_key, file_name in biome_paths.items():
            components = load(
                BP / "netease_biomes" / "dm33027004" / file_name
            )["minecraft:biome"]["components"]
            self.assertIn("tf_slice_dark_forest_groundcover", components)
            self.assertNotIn("tf_slice_terrestrial_groundcover", components)

        profiles = {
            "grass": (128, 25.0, "minecraft:short_grass"),
            "ferns": (128, 25.0, "minecraft:fern"),
            "mushglooms": (50, 100.0 / 30.0, "tf_slice:mushgloom"),
            "dead_bushes": (50, 100.0 / 15.0, "minecraft:deadbush"),
            "pumpkins": (50, 100.0 / 30.0, "minecraft:pumpkin"),
            "mushrooms": (50, None, "minecraft:brown_mushroom"),
        }
        for profile, (tries, chance, block_name) in profiles.items():
            feature = load(
                BP / "netease_features" / ("dark_%s_feature.json" % profile)
            )["minecraft:single_block_feature"]
            self.assertEqual(block_name, feature["places_block"][0]["block"])
            patch = load(
                BP
                / "netease_features"
                / ("dark_%s_patch_feature.json" % profile)
            )["minecraft:scatter_feature"]
            self.assertEqual(tries, patch["distribution"]["iterations"])
            rule = load(
                BP
                / "netease_feature_rules"
                / ("dark_%s_feature_rule.json" % profile)
            )["minecraft:feature_rules"]
            self.assertIn("tf_slice_dark_forest_groundcover", json.dumps(rule))
            if chance is None:
                self.assertNotIn("scatter_chance", rule["distribution"])
            else:
                self.assertAlmostEqual(
                    chance, rule["distribution"]["scatter_chance"], places=5
                )

        flower_rule = load(
            BP / "netease_feature_rules" / "dark_forest_flowers_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(3, flower_rule["distribution"]["iterations"])
        self.assertEqual(50.0, flower_rule["distribution"]["scatter_chance"])
        encoded_flower_rule = json.dumps(flower_rule)
        self.assertIn("tf_slice_biome_dark_forest", encoded_flower_rule)
        self.assertNotIn("dark_forest_center", encoded_flower_rule)

    def test_magic_map_has_dark_forest_palette_entries(self):
        expected = {
            "dark_forest": (0x35, 0x42, 0x1B, 0xFF),
            "dark_forest_center": (0x70, 0x42, 0x1B, 0xFF),
        }
        palette_root = RP / "textures" / "ui" / "tf_slice" / "magic_map_palette"
        for biome_key, color in expected.items():
            profile = next(
                entry
                for entry in biome_catalog.ACTIVE_TERRITORY_PROFILES
                if biome_key
                in (entry["companionBiome"], entry["coreBiome"])
            )
            color_field = (
                "coreMapColor"
                if biome_key == profile["coreBiome"]
                else "companionMapColor"
            )
            self.assertEqual(color, tuple(profile[color_field]))
            self.assertEqual(
                color,
                magic_map_bitmap_cache.MAGIC_MAP_BIOME_RGBA[biome_key],
            )
            with Image.open(palette_root / (biome_key + ".png")) as image:
                self.assertEqual({color}, set(image.convert("RGBA").getdata()))

    def test_center_uses_the_effective_runtime_autumn_colors(self):
        center = load(
            RP
            / "biomes"
            / "dm33027004_redwood_taiga_mutated.client_biome.json"
        )["minecraft:client_biome"]["components"]
        # The 4.3.2508 foliage handler normalizes noise to [0, 1] before
        # comparing it with -0.1, so the effective result is always E94E14.
        self.assertEqual(
            "#E94E14", center["minecraft:foliage_appearance"]["color"]
        )
        # NetEase exposes no equivalent custom grass-color modifier. Use the
        # common branch of the source's two-color noise rule, not its override.
        self.assertEqual(
            "#554114", center["minecraft:grass_appearance"]["color"]
        )

    def test_dark_forest_spawn_weights_match_locked_biome_json(self):
        expected = {
            "mist_wolf": (5, 1, 1),
            "skeleton_druid": (5, 1, 1),
            "king_spider": (1, 1, 1),
            "kobold": (10, 1, 3),
        }
        for identifier, (weight, minimum, maximum) in expected.items():
            rule = load(BP / "spawn_rules" / (identifier + "_dark_forest.json"))[
                "minecraft:spawn_rules"
            ]
            condition = rule["conditions"][0]
            self.assertEqual(weight, condition["minecraft:weight"]["default"])
            self.assertEqual(minimum, condition["minecraft:herd"]["min_size"])
            self.assertEqual(maximum, condition["minecraft:herd"]["max_size"])
            encoded = json.dumps(condition)
            self.assertIn("tf_slice_biome_dark_forest", encoded)
            self.assertNotIn("dark_forest_center", encoded)

    def test_center_is_explicitly_marked_as_no_natural_spawns(self):
        center = load(
            BP
            / "netease_biomes"
            / "dm33027004"
            / "dm33027004_redwood_taiga_mutated.json"
        )["minecraft:biome"]["components"]
        self.assertIn(
            "tf_slice_dark_forest_center_no_natural_spawns", center
        )

    def test_new_dark_forest_entities_use_source_shapes_and_stats(self):
        expected = {
            "mist_wolf": (30, 6, "geometry.tf_slice.hostile_wolf"),
            "king_spider": (30, 6, "geometry.spider.v1.8"),
        }
        for identifier, (health, damage, geometry) in expected.items():
            entity = load(BP / "entities" / (identifier + ".entity.json"))[
                "minecraft:entity"
            ]
            components = entity["components"]
            self.assertEqual(health, components["minecraft:health"]["value"])
            self.assertEqual(damage, components["minecraft:attack"]["damage"])
            client = load(RP / "entity" / (identifier + ".entity.json"))[
                "minecraft:client_entity"
            ]["description"]
            self.assertEqual(geometry, client["geometry"]["default"])

        king = load(BP / "entities" / "king_spider.entity.json")[
            "minecraft:entity"
        ]["components"]
        self.assertEqual(0.35, king["minecraft:movement"]["value"])
        self.assertEqual(
            {"width": 1.6, "height": 1.6},
            king["minecraft:collision_box"],
        )
        self.assertNotIn("minecraft:can_climb", king)
        self.assertEqual(
            1.0,
            king["minecraft:behavior.melee_attack"]["speed_multiplier"],
        )
        self.assertEqual(
            0.8,
            king["minecraft:behavior.random_stroll"]["speed_multiplier"],
        )
        self.assertEqual(
            0.4,
            king["minecraft:behavior.leap_at_target"]["yd"],
        )
        target = king["minecraft:behavior.nearest_attackable_target"]
        self.assertTrue(target["must_see"])
        self.assertEqual(16, target["entity_types"][0]["max_dist"])
        self.assertEqual(
            [0, 1.2, 0],
            king["minecraft:rideable"]["seats"]["position"],
        )

        king_client = load(RP / "entity" / "king_spider.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual("1.9", king_client["scripts"]["scale"])
        self.assertEqual(
            {
                "default_leg_pose": "animation.spider.default_leg_pose",
                "look_at_target": "animation.spider.look_at_target",
                "walk": "animation.spider.walk",
            },
            king_client["animations"],
        )
        self.assertEqual(
            [
                "default_leg_pose",
                {"walk": "query.modified_move_speed"},
                "look_at_target",
            ],
            king_client["scripts"]["animate"],
        )

    def test_king_spider_druid_uses_source_riding_pose(self):
        king = load(BP / "entities" / "king_spider.entity.json")[
            "minecraft:entity"
        ]["components"]
        # KingSpider.getPassengersRidingOffset() is height * 0.75.
        self.assertEqual(
            [0, 1.2, 0],
            king["minecraft:rideable"]["seats"]["position"],
        )

        animations = load(RP / "animations" / "ruin_mobs.animation.json")[
            "animations"
        ]
        bones = animations["animation.tf_slice.biped.move"]["bones"]
        self.assertEqual(
            [
                "query.is_riding ? -81 : (math.cos(query.modified_distance_moved * 38.17) * 35.0 * query.modified_move_speed)",
                "query.is_riding ? 18 : 0",
                "query.is_riding ? 4.5 : 0",
            ],
            bones["rightLeg"]["rotation"],
        )
        self.assertEqual(
            [
                "query.is_riding ? -81 : -(math.cos(query.modified_distance_moved * 38.17) * 35.0 * query.modified_move_speed)",
                "query.is_riding ? -18 : 0",
                "query.is_riding ? -4.5 : 0",
            ],
            bones["leftLeg"]["rotation"],
        )
        self.assertIn(
            "query.is_riding",
            bones["rightArm"]["rotation"][0],
        )
        self.assertIn(
            "query.is_riding",
            bones["leftArm"]["rotation"][0],
        )


if __name__ == "__main__":
    unittest.main()
