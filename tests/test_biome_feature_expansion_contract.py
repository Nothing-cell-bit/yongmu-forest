# -*- coding: utf-8 -*-
import json
import math
import unittest
from pathlib import Path

from tools.native_structure_worldgen_safety import base_iterations


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"

FEATURE_BLOCKS = {
    "rainbow_oak_leaves",
    "fiddlehead",
    "mushgloom",
    "firefly",
    "firefly_jar",
    "cicada_jar",
    "canopy_fence",
    "fallen_leaves",
}
BIOME_FEATURE_PROFILES = {
    "dense_forest": ("dense_forest_tree_profile_feature_rule", 6),
    "oak_savannah": ("oak_savannah_tree_profile_feature_rule", 2),
    "firefly_forest": ("firefly_forest_tree_profile_feature_rule", 4),
    "enchanted_forest": (
        "enchanted_forest_tree_profile_feature_rule",
        "5 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
    ),
}
SPOOKY_TREE_RULES = {
    "spooky_dead_tree_feature_rule": (
        "tf_slice:spooky_dead_tree_selector_feature",
        "2 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
    ),
    "spooky_twilight_oak_tree_feature_rule": (
        "tf_slice:spooky_twilight_oak_tree_feature",
        "1 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
    ),
    "spooky_large_twilight_oak_tree_feature_rule": (
        "tf_slice:spooky_large_twilight_oak_tree_feature",
        "1 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
    ),
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class BiomeFeatureExpansionContractTests(unittest.TestCase):
    def test_feature_blocks_have_closed_server_client_and_texture_definitions(self):
        server_ids = {
            read_json(path)["minecraft:block"]["description"]["identifier"]
            for path in (BP / "netease_blocks").glob("*.json")
        }
        client_blocks = read_json(RP / "blocks.json")
        atlas = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]

        for name in FEATURE_BLOCKS:
            identifier = "tf_slice:%s" % name
            self.assertIn(identifier, server_ids)
            self.assertIn(identifier, client_blocks)
            self.assertIn(identifier, atlas)
            texture = atlas[identifier]["textures"]
            if isinstance(texture, list):
                texture = texture[0]["path"]
            elif isinstance(texture, dict):
                texture = next(iter(texture.values()))
            self.assertTrue((RP / ("%s.png" % texture)).is_file())

    def test_each_forest_variant_has_a_uniquely_tagged_tree_profile(self):
        for biome_key, (rule_name, iterations) in (
            BIOME_FEATURE_PROFILES.items()
        ):
            rule = read_json(
                BP / "netease_feature_rules" / ("%s.json" % rule_name)
            )["minecraft:feature_rules"]
            self.assertEqual(
                iterations,
                base_iterations(rule["distribution"]["iterations"]),
            )
            self.assertIn(
                "tf_slice_biome_%s" % biome_key,
                json.dumps(rule["conditions"]),
            )
            feature_id = rule["description"]["places_feature"]
            feature_path = (
                BP
                / "netease_features"
                / ("%s.json" % feature_id.split(":", 1)[1])
            )
            self.assertTrue(feature_path.is_file())

    def test_aquatic_biomes_have_seagrass_but_no_tree_profile(self):
        for biome_key in ("lake", "stream"):
            rule = read_json(
                BP
                / "netease_feature_rules"
                / ("%s_seagrass_feature_rule.json" % biome_key)
            )["minecraft:feature_rules"]
            self.assertIn(
                "tf_slice_biome_%s" % biome_key,
                json.dumps(rule["conditions"]),
            )
            self.assertIn("seagrass", rule["description"]["places_feature"])
            self.assertNotIn(biome_key, BIOME_FEATURE_PROFILES)

    def test_spooky_forest_uses_upstream_independent_tree_counts(self):
        for rule_name, (feature_id, iterations) in SPOOKY_TREE_RULES.items():
            rule = read_json(
                BP / "netease_feature_rules" / ("%s.json" % rule_name)
            )["minecraft:feature_rules"]
            projected_id = rule["description"]["places_feature"]
            projected = read_json(
                BP
                / "netease_features"
                / ("%s.json" % projected_id.split(":", 1)[1])
            )["minecraft:scatter_feature"]
            self.assertEqual(feature_id, projected["places_feature"])
            self.assertTrue(projected["project_input_to_floor"])
            self.assertEqual(
                {
                    "iterations": 1,
                    "coordinate_eval_order": "xzy",
                    "x": 0,
                    "y": 0,
                    "z": 0,
                },
                projected["distribution"],
            )
            self.assertEqual(
                iterations,
                base_iterations(rule["distribution"]["iterations"]),
            )
            self.assertIn("+ 64", rule["distribution"]["y"])
            self.assertIn(
                "tf_slice_biome_spooky_forest",
                json.dumps(rule["conditions"]),
            )

        self.assertFalse(
            (
                BP
                / "netease_features"
                / "spooky_forest_tree_profile_feature.json"
            ).exists()
        )
        self.assertFalse(
            (
                BP
                / "netease_feature_rules"
                / "spooky_forest_tree_profile_feature_rule.json"
            ).exists()
        )

    def test_structure_tree_probes_make_a_real_placement(self):
        """Bare soil must reach the template rather than fail an air-to-air write."""
        anchors = (
            "canopy_tree_anchor_feature",
            "spooky_dead_tree_anchor_feature",
        )
        for anchor_name in anchors:
            anchor = read_json(
                BP / "netease_features" / (anchor_name + ".json")
            )["minecraft:single_block_feature"]
            self.assertEqual(
                [{"block": "tf_slice:canopy_log", "weight": 1}],
                anchor["places_block"],
                anchor_name,
            )

    def test_spooky_dead_trees_validate_ground_before_placement(self):
        anchor_id = "tf_slice:spooky_dead_tree_anchor_feature"
        anchor = read_json(
            BP / "netease_features" / "spooky_dead_tree_anchor_feature.json"
        )["minecraft:single_block_feature"]
        self.assertEqual(
            [{"block": "tf_slice:canopy_log", "weight": 1}],
            anchor["places_block"],
        )
        self.assertEqual(
            {
                "minecraft:grass",
                "minecraft:grass_block",
                "minecraft:dirt",
                "minecraft:podzol",
            },
            set(anchor["may_attach_to"]["bottom"]),
        )
        self.assertNotIn(
            "tf_slice:canopy_leaves",
            anchor["may_attach_to"]["bottom"],
        )

        selector = read_json(
            BP / "netease_features" / "spooky_dead_tree_selector_feature.json"
        )["minecraft:weighted_random_feature"]
        self.assertEqual(16, len(selector["features"]))
        for index, (sequence_id, weight) in enumerate(selector["features"]):
            self.assertEqual(1, weight)
            local_id = "spooky_dead_tree_v%02d" % index
            self.assertEqual(
                "tf_slice:%s_sequence_feature" % local_id,
                sequence_id,
            )
            sequence = read_json(
                BP
                / "netease_features"
                / ("%s_sequence_feature.json" % local_id)
            )["minecraft:sequence_feature"]
            self.assertEqual(
                [anchor_id, "tf_slice:%s_placement_feature" % local_id],
                sequence["features"],
            )
            offset = read_json(
                BP
                / "netease_features"
                / ("%s_offset_feature.json" % local_id)
            )["minecraft:scatter_feature"]
            self.assertEqual(
                "tf_slice:%s_feature" % local_id,
                offset["places_feature"],
            )
            self.assertEqual(
                {
                    "iterations": 1,
                    "coordinate_eval_order": "xzy",
                    "x": -9,
                    "y": -5,
                    "z": -9,
                },
                offset["distribution"],
            )

    def test_signature_plants_are_biome_scoped(self):
        expected = {
            "mushgloom_patch_feature_rule": (
                "mushroom_forest",
                "dense_mushroom_forest",
                "firefly_forest",
            ),
            "fiddlehead_patch_feature_rule": ("enchanted_forest",),
            "fallen_leaves_patch_feature_rule": ("spooky_forest",),
            "firefly_lamppost_feature_rule": ("firefly_forest",),
        }
        for rule_name, biome_keys in expected.items():
            rule = read_json(
                BP / "netease_feature_rules" / ("%s.json" % rule_name)
            )
            encoded = json.dumps(rule)
            for biome_key in biome_keys:
                self.assertIn("tf_slice_biome_%s" % biome_key, encoded)

    def test_spooky_forest_has_upstream_tree_shapes_axes_and_decorations(self):
        block = read_json(
            BP / "netease_blocks" / "fallen_leaves.json"
        )["minecraft:block"]["components"]
        self.assertEqual(
            "geometry.tf_slice.fallen_leaves",
            block["minecraft:geometry"],
        )
        self.assertFalse(block["minecraft:collision_box"])
        self.assertEqual(
            [16, 1, 16],
            block["minecraft:selection_box"]["size"],
        )

        geometry = read_json(
            RP / "models" / "blocks" / "fallen_leaves.geo.json"
        )["minecraft:geometry"][0]
        cube = geometry["bones"][0]["cubes"][0]
        self.assertEqual([16, 1, 16], cube["size"])

        patch = read_json(
            BP / "netease_features" / "fallen_leaves_patch_feature.json"
        )["minecraft:scatter_feature"]
        distribution = patch["distribution"]
        self.assertEqual(16, distribution["iterations"])
        self.assertEqual([-3, 3], distribution["x"]["extent"])
        self.assertEqual([-3, 3], distribution["z"]["extent"])

        rule = read_json(
            BP
            / "netease_feature_rules"
            / "fallen_leaves_patch_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(1, rule["distribution"]["iterations"])

        self.assertFalse(
            (BP / "netease_features" / "spooky_dead_tree_feature.json").exists()
        )
        dead_tree_rule = read_json(
            BP
            / "netease_feature_rules"
            / "spooky_dead_tree_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "(query.get_height_at(variable.worldx, variable.worldz)) + 64",
            dead_tree_rule["distribution"]["y"],
        )
        manifest = read_json(
            BP / "metadata" / "spooky_forest_generation.json"
        )
        variants = manifest["dead_tree_variants"]
        self.assertGreaterEqual(len(variants), 16)
        self.assertTrue(all(20 <= item["height"] <= 30 for item in variants))
        self.assertTrue(
            all(3 <= item["branch_count"] <= 4 for item in variants)
        )
        self.assertTrue(all(item["branch_length"] in (10, 11) for item in variants))
        self.assertTrue(all(item["branch_pitch"] == 0.2 for item in variants))
        self.assertTrue(all(item["horizontal_reach"] <= 7 for item in variants))
        self.assertTrue(
            all(item["axis_counts"]["x"] > 0 for item in variants)
        )
        self.assertTrue(
            all(item["axis_counts"]["z"] > 0 for item in variants)
        )
        for axis in ("x", "z"):
            self.assertTrue(
                (BP / "netease_blocks" / ("canopy_log_%s.json" % axis)).is_file()
            )

        spooky_biome = read_json(
            BP
            / "netease_biomes"
            / "dm33027004"
            / "dm33027004_roofed_forest.json"
        )["minecraft:biome"]["components"]
        self.assertNotIn("tf_slice_terrestrial_groundcover", spooky_biome)
        self.assertIn("tf_slice_spooky_groundcover", spooky_biome)

        atlas = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]
        self.assertEqual(
            "#FF8501",
            atlas["tf_slice:spooky_twilight_oak_leaves"]["textures"][0][
                "tint_color"
            ],
        )

        web_rule = read_json(
            BP / "netease_feature_rules" / "spooky_web_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "tf_slice:spooky_web_search_feature",
            web_rule["description"]["places_feature"],
        )
        self.assertEqual(
            "query.get_height_at(variable.worldx, variable.worldz)",
            web_rule["distribution"]["y"],
        )
        self.assertEqual(60, web_rule["distribution"]["iterations"])

        web_search = read_json(
            BP / "netease_features" / "spooky_web_search_feature.json"
        )["minecraft:search_feature"]
        self.assertEqual(
            "tf_slice:spooky_web_feature",
            web_search["places_feature"],
        )
        self.assertEqual(
            {"min": [0, -31, 0], "max": [0, 0, 0]},
            web_search["search_volume"],
        )
        self.assertEqual("-y", web_search["search_axis"])
        self.assertEqual(1, web_search["required_successes"])

        web = read_json(
            BP / "netease_features" / "spooky_web_feature.json"
        )["minecraft:single_block_feature"]
        attachable_blocks = set(web["may_attach_to"]["top"])
        self.assertIn("tf_slice:twilight_oak_log", attachable_blocks)
        self.assertIn("tf_slice:spooky_twilight_oak_leaves", attachable_blocks)

        for rule_name in (
            "spooky_web_feature_rule",
            "spooky_pumpkin_lamppost_feature_rule",
            "spooky_canopy_fallen_log_feature_rule",
            "spooky_oak_fallen_log_feature_rule",
            "spooky_dead_bush_patch_feature_rule",
            "spooky_pumpkin_patch_feature_rule",
            "spooky_mayapple_patch_feature_rule",
        ):
            encoded = json.dumps(
                read_json(
                    BP / "netease_feature_rules" / ("%s.json" % rule_name)
                )
            )
            self.assertIn("tf_slice_biome_spooky_forest", encoded)

    def test_enchanted_forest_restores_rainbow_color_tree_and_ecology_contract(self):
        phase_count = 16
        atlas = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]
        client_blocks = read_json(RP / "blocks.json")
        base_tint = atlas["tf_slice:rainbow_oak_leaves"]["textures"][0][
            "tint_color"
        ]
        self.assertNotEqual("#FFFFFF", base_tint)

        phase_colors = []
        for index in range(phase_count):
            name = "rainbow_oak_leaves_%02d" % index
            identifier = "tf_slice:%s" % name
            self.assertTrue(
                (BP / "netease_blocks" / ("%s.json" % name)).is_file()
            )
            self.assertIn(identifier, client_blocks)
            self.assertIn(identifier, atlas)
            phase_colors.append(
                atlas[identifier]["textures"][0]["tint_color"]
            )
        self.assertEqual(phase_count, len(set(phase_colors)))
        self.assertNotIn("#FFFFFF", phase_colors)

        metadata = read_json(
            BP / "metadata" / "enchanted_forest_generation.json"
        )
        self.assertEqual("4.3.2508", metadata["source_version"])
        self.assertEqual(phase_colors, metadata["rainbow_leaf_colors"])
        self.assertEqual("#00FF80", metadata["grass_color_approximation"])
        self.assertEqual(
            "omit_static_roots",
            metadata["root_placement"]["implementation"],
        )
        self.assertEqual(
            "terrain_aware_underground_only",
            metadata["root_placement"]["upstream"],
        )
        for tree_kind, height_range in (
            ("regular", [4, 6]),
            ("large", [3, 14]),
        ):
            variants = metadata["tree_variants"][tree_kind]
            self.assertGreaterEqual(len(variants), phase_count)
            self.assertTrue(
                all(
                    height_range[0] <= item["height"] <= height_range[1]
                    for item in variants
                )
            )
            self.assertTrue(
                all(item["root_count"] == 0 for item in variants)
            )
            for index in range(phase_count):
                structure_path = (
                    BP
                    / "structures"
                    / "tf_slice"
                    / "enchanted"
                    / tree_kind
                    / ("v%02d.mcstructure" % index)
                )
                self.assertTrue(structure_path.is_file())
                structure_bytes = structure_path.read_bytes()
                self.assertNotIn(b"tf_slice:root_block", structure_bytes)
                self.assertNotIn(b"tf_slice:liveroot_block", structure_bytes)

        profile = read_json(
            BP
            / "netease_features"
            / "enchanted_forest_tree_profile_feature.json"
        )["minecraft:weighted_random_feature"]["features"]
        self.assertEqual(
            [
                ["tf_slice:enchanted_regular_rainbow_tree_trigger_feature", 650],
                ["tf_slice:enchanted_vanilla_oak_tree_trigger_feature", 150],
                ["tf_slice:enchanted_vanilla_birch_tree_trigger_feature", 128],
                ["tf_slice:enchanted_large_rainbow_tree_trigger_feature", 72],
            ],
            profile,
        )
        profile_rule = read_json(
            BP
            / "netease_feature_rules"
            / "enchanted_forest_tree_profile_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "(query.get_height_at(variable.worldx, variable.worldz)) + 64",
            profile_rule["distribution"]["y"],
        )
        for tree_kind in (
            "regular_rainbow",
            "vanilla_oak",
            "vanilla_birch",
            "large_rainbow",
        ):
            trigger = (
                BP
                / "structures"
                / "tf_slice"
                / "enchanted"
                / "tree_trigger"
                / ("%s.mcstructure" % tree_kind)
            )
            self.assertTrue(trigger.is_file())
            feature = read_json(
                BP
                / "netease_features"
                / ("enchanted_%s_tree_trigger_feature.json" % tree_kind)
            )
            self.assertIn("netease:structure_feature", feature)
        runtime_pieces = list(
            (
                BP / "structures" / "tf_slice" / "enchanted" / "runtime"
            ).rglob("*.mcstructure")
        )
        self.assertGreaterEqual(len(runtime_pieces), 34)
        self.assertEqual(
            "noop_1x1_trigger_deferred_root_anchor",
            metadata["placement"],
        )
        for stale in (
            "rainbow_oak_tree_selector_feature.json",
            "large_rainbow_oak_tree_selector_feature.json",
            "enchanted_vanilla_oak_tree_feature.json",
            "enchanted_vanilla_birch_tree_feature.json",
            "regular_rainbow_oak_tree_v00_feature.json",
            "large_rainbow_oak_tree_v00_feature.json",
        ):
            self.assertFalse((BP / "netease_features" / stale).exists())
        canopy_rule = read_json(
            BP
            / "netease_feature_rules"
            / "enchanted_canopy_tree_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(1, canopy_rule["distribution"]["iterations"])
        self.assertIn(
            "tf_slice_biome_enchanted_forest",
            json.dumps(canopy_rule["conditions"]),
        )

        client_biome = read_json(
            RP
            / "biomes"
            / "dm33027004_birch_forest_mutated.client_biome.json"
        )["minecraft:client_biome"]["components"]
        self.assertEqual(
            "tf_slice:fog_enchanted_forest",
            client_biome["minecraft:fog_appearance"]["fog_identifier"],
        )
        self.assertEqual(
            "#00FF80",
            client_biome["minecraft:grass_appearance"]["color"],
        )
        self.assertEqual(
            "#00FFFF",
            client_biome["minecraft:foliage_appearance"]["color"],
        )
        enchanted_fog = read_json(
            RP / "fogs" / "enchanted_forest.fog.json"
        )["minecraft:fog_settings"]
        self.assertEqual(
            "#C0FFD8",
            enchanted_fog["distance"]["air"]["fog_color"],
        )

        fiddlehead = read_json(
            BP / "netease_features" / "fiddlehead_patch_feature.json"
        )["minecraft:scatter_feature"]
        self.assertEqual(96, fiddlehead["distribution"]["iterations"])
        fiddlehead_rule = read_json(
            BP / "netease_feature_rules" / "fiddlehead_patch_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(1, fiddlehead_rule["distribution"]["iterations"])
        for rule_name in (
            "enchanted_vines_feature_rule",
            "enchanted_fallen_log_feature_rule",
        ):
            encoded = json.dumps(
                read_json(
                    BP / "netease_feature_rules" / ("%s.json" % rule_name)
                )
            )
            self.assertIn("tf_slice_biome_enchanted_forest", encoded)

        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn("CreateBiome(LEVEL_ID)", client_source)
        self.assertIn("GetBiomeName", client_source)
        self.assertIn(
            '"dm33027004_birch_forest_mutated"',
            client_source,
        )

    def test_bug_blocks_use_upstream_models_and_compatible_block_items(self):
        firefly = read_json(
            BP / "netease_blocks" / "firefly.json"
        )["minecraft:block"]
        firefly_components = firefly["components"]
        self.assertEqual("1.20.60", read_json(
            BP / "netease_blocks" / "firefly.json"
        )["format_version"])
        self.assertEqual(
            "geometry.tf_slice.firefly",
            firefly_components["minecraft:geometry"],
        )
        self.assertEqual(
            ["north", "south", "west", "east"],
            firefly["description"]["states"]["tf_slice:facing"],
        )
        firefly_permutations = firefly["permutations"]
        self.assertEqual(4, len(firefly_permutations))
        self.assertEqual(
            {
                # The facing state points from the supporting block to the
                # firefly block, so the model must sit on the opposite face.
                "north": [0, 180, 0],
                "south": [0, 0, 0],
                "west": [0, -90, 0],
                "east": [0, 90, 0],
            },
            {
                permutation["condition"].split("'")[-2]:
                permutation["components"]["minecraft:transformation"][
                    "rotation"
                ]
                for permutation in firefly_permutations
            },
        )
        self.assertNotIn("minecraft:item_visual", firefly_components)
        self.assertNotIn(
            "mayapple",
            json.dumps(firefly_components),
        )

        firefly_geometries = read_json(
            RP / "models" / "blocks" / "firefly.geo.json"
        )["minecraft:geometry"]
        self.assertEqual(
            ["geometry.tf_slice.firefly"],
            [
                geometry["description"]["identifier"]
                for geometry in firefly_geometries
            ],
        )
        firefly_geometry = firefly_geometries[0]
        self.assertEqual(
            (64, 32),
            (
                firefly_geometry["description"]["texture_width"],
                firefly_geometry["description"]["texture_height"],
            ),
        )
        cubes_by_bone = {
            bone["name"]: bone["cubes"][0]
            for bone in firefly_geometry["bones"]
            if bone.get("cubes")
        }
        bones_by_name = {
            bone["name"]: bone for bone in firefly_geometry["bones"]
        }
        self.assertEqual(
            {
                "legs": [8, 1, 10],
                "fat_body": [4, 2, 6],
                "skinny_body": [2, 1, 8],
                "glow": [10, 0.1, 10],
            },
            {
                name: cube["size"]
                for name, cube in cubes_by_bone.items()
            },
        )
        self.assertEqual(0, cubes_by_bone["legs"]["origin"][1])
        self.assertEqual(0, cubes_by_bone["glow"]["origin"][1])
        self.assertEqual(-8, cubes_by_bone["glow"]["origin"][2])
        wall_mount_rotation = bones_by_name["wall_mount"]["rotation"]
        self.assertEqual([90, 0, 0], wall_mount_rotation)
        # This geometry is rendered as a block, so its authored bone pitch is
        # used directly.  The unrotated bug lies on source y=0; after mounting,
        # that plane must be z=-8 so the default south-facing state renders on
        # the north face next to its supporting block.
        effective_pitch = math.radians(wall_mount_rotation[0])
        mounted_plane_z = (-8 * math.sin(effective_pitch))
        self.assertAlmostEqual(-8, mounted_plane_z)
        self.assertEqual([0, 8, 0], bones_by_name["wall_mount"]["pivot"])
        self.assertTrue(
            all(
                bones_by_name[name]["parent"] == "wall_mount"
                for name in (
                    "legs",
                    "fat_body",
                    "skinny_body",
                    "glow",
                )
            )
        )
        # The wall_mount bone rotates +90 degrees around X, so source y=0
        # becomes the north mount plane z=-8.  The abdomen
        # itself (not merely the antenna/legs) must share that plane.
        glow = cubes_by_bone["glow"]
        glow_source_y = glow["origin"][1]
        glow_source_z_min = glow["origin"][2]
        glow_source_z_max = glow_source_z_min + glow["size"][2]
        self.assertEqual(-8, glow_source_y - 8)
        self.assertGreaterEqual(8 - glow_source_z_max, 0)
        self.assertLessEqual(8 - glow_source_z_min, 16)
        self.assertEqual(
            {"origin": [-5, 0, -8], "size": [10, 16, 4]},
            firefly_components["minecraft:selection_box"],
        )

        fiddlehead = read_json(
            BP / "netease_blocks" / "fiddlehead.json"
        )["minecraft:block"]["components"]
        self.assertEqual(
            "geometry.tf_slice.fiddlehead",
            fiddlehead["minecraft:geometry"],
        )
        self.assertNotIn("mayapple", json.dumps(fiddlehead))
        self.assertEqual(
            {"origin": [-5, 0, -5], "size": [10, 14, 10]},
            fiddlehead["minecraft:selection_box"],
        )
        fiddlehead_geometry = read_json(
            RP / "models" / "blocks" / "fiddlehead.geo.json"
        )["minecraft:geometry"][0]
        fiddlehead_cubes = [
            bone["cubes"][0] for bone in fiddlehead_geometry["bones"]
        ]
        self.assertEqual([45, -45], [
            cube["rotation"][1] for cube in fiddlehead_cubes
        ])
        self.assertTrue(all(
            cube["origin"][1] == 0 and cube["size"][1] == 16
            for cube in fiddlehead_cubes
        ))

        mushgloom = read_json(
            BP / "netease_blocks" / "mushgloom.json"
        )["minecraft:block"]["components"]
        self.assertEqual(
            "geometry.tf_slice.mushgloom",
            mushgloom["minecraft:geometry"],
        )
        self.assertNotIn("mayapple", json.dumps(mushgloom))
        self.assertEqual(
            {"origin": [-6, 0, -6], "size": [12, 8, 12]},
            mushgloom["minecraft:selection_box"],
        )
        self.assertEqual(
            "tf_slice:mushgloom_head",
            mushgloom["minecraft:material_instances"]["head"]["texture"],
        )
        mushgloom_geometry = read_json(
            RP / "models" / "blocks" / "mushgloom.geo.json"
        )["minecraft:geometry"][0]
        mushgloom_cubes = [
            (bone["name"], bone["cubes"][0])
            for bone in mushgloom_geometry["bones"]
        ]
        self.assertEqual(
            ["stem_a", "stem_b", "head_a", "head_b"],
            [name for name, _ in mushgloom_cubes],
        )
        self.assertEqual(
            [45, -45, 45, -45],
            [cube["rotation"][1] for _, cube in mushgloom_cubes],
        )
        self.assertTrue(all(
            cube["origin"][1] == 0 and cube["size"][1] == 16
            for _, cube in mushgloom_cubes
        ))
        self.assertTrue(
            (RP / "textures" / "blocks" / "mushgloom_head.png").is_file()
        )

        jar_geometry = read_json(
            RP / "models" / "blocks" / "bug_jar.geo.json"
        )["minecraft:geometry"][0]
        jar_cubes = {
            bone["name"]: bone["cubes"][0]
            for bone in jar_geometry["bones"]
        }
        self.assertEqual([10, 14, 10], jar_cubes["glass"]["size"])
        self.assertEqual([8, 4, 8], jar_cubes["cork"]["size"])
        self.assertEqual(
            {"side", "top", "bottom"},
            {
                face["material_instance"]
                for face in jar_cubes["glass"]["uv"].values()
            },
        )
        self.assertEqual(
            {"cork"},
            {
                face["material_instance"]
                for face in jar_cubes["cork"]["uv"].values()
            },
        )

        for jar_name, cork_texture in (
            ("firefly_jar", "tf_slice:firefly_jar_cork"),
            ("cicada_jar", "tf_slice:cicada_jar_cork"),
        ):
            jar_document = read_json(
                BP / "netease_blocks" / ("%s.json" % jar_name)
            )
            self.assertEqual("1.20.60", jar_document["format_version"])
            components = jar_document["minecraft:block"]["components"]
            self.assertEqual(
                "geometry.tf_slice.bug_jar",
                components["minecraft:geometry"],
            )
            self.assertNotIn("minecraft:item_visual", components)
            self.assertEqual(
                cork_texture,
                components["minecraft:material_instances"]["cork"][
                    "texture"
                ],
            )
        block_items = read_json(RP / "blocks.json")
        for block_name in ("firefly", "firefly_jar", "cicada_jar"):
            block_id = "tf_slice:%s" % block_name
            texture_id = block_items[block_id]["textures"]
            self.assertEqual(block_id, texture_id)

        atlas = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]
        for texture_name in (
            "firefly_model",
            "jar_side",
            "jar_top",
            "jar_bottom",
            "firefly_jar_cork",
            "cicada_jar_cork",
        ):
            texture_id = "tf_slice:%s" % texture_name
            self.assertIn(texture_id, atlas)
            texture_path = atlas[texture_id]["textures"]
            self.assertTrue((RP / ("%s.png" % texture_path)).is_file())

    def test_original_base_tree_rules_do_not_leak_into_every_biome(self):
        for rule_name in (
            "canopy_tree_feature_rule",
            "large_twilight_oak_tree_feature_rule",
            "twilight_oak_tree_feature_rule",
            "twilight_tree_mix_selector_feature_rule",
        ):
            encoded = json.dumps(
                read_json(BP / "netease_feature_rules" / ("%s.json" % rule_name))
            )
            self.assertIn("tf_slice_biome_forest", encoded)
            self.assertNotIn('"value": "tf_slice_twilight_forest"', encoded)


if __name__ == "__main__":
    unittest.main()
