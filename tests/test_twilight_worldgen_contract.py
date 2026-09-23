# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path

from tools.native_structure_worldgen_safety import base_iterations


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog


DIMENSION_ID = 33027004
BIOME_SPECS = dict(
    (entry["key"], entry["identifier"])
    for entry in biome_catalog.BIOMES
)
BIOME_INHERITS = dict(
    (entry["identifier"], entry["inherits"])
    for entry in biome_catalog.BIOMES
)
BIOME_ID = BIOME_SPECS["forest"]
TWILIGHT_TERRAIN_PROFILES = dict(
    (entry["identifier"], entry["noise_params"])
    for entry in biome_catalog.BIOMES
)
BLOCK_IDS = {
    "tf_slice:twilight_oak_log",
    "tf_slice:twilight_oak_leaves",
    "tf_slice:canopy_log",
    "tf_slice:canopy_leaves",
    "tf_slice:mayapple",
}
FEATURES = {
    "twilight_oak_tree_feature": {
        "log": "tf_slice:twilight_oak_log",
        "leaves": "tf_slice:twilight_oak_leaves",
        "trunk": "trunk",
        "canopy": "canopy",
        "iterations": 1,
    },
    "large_twilight_oak_tree_feature": {
        "log": "tf_slice:twilight_oak_log",
        "leaves": "tf_slice:twilight_oak_leaves",
        "trunk": "fancy_trunk",
        "canopy": "fancy_canopy",
        "iterations": 1,
    },
    "canopy_tree_feature": {
        "log": "tf_slice:canopy_log",
        "leaves": "tf_slice:canopy_leaves",
        "trunk": "fancy_trunk",
        "canopy": "fancy_canopy",
        "iterations": 1,
        "placed_feature": "tf_slice:canopy_tree_selector_feature",
    },
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TwilightTerrainBlockContractTests(unittest.TestCase):
    def test_all_tree_blocks_have_server_and_client_definitions(self):
        server_ids = set()
        for path in (BP / "netease_blocks").glob("*.json"):
            block = read_json(path)["minecraft:block"]
            self.assertNotIn("base_block", block["description"])
            server_ids.add(block["description"]["identifier"])

        client_ids = set(read_json(RP / "blocks.json"))
        self.assertTrue(BLOCK_IDS.issubset(server_ids))
        self.assertTrue(BLOCK_IDS.issubset(client_ids))

    def test_leaves_use_mobile_safe_transparency_and_face_cropping(self):
        for name in ("twilight_oak_leaves", "canopy_leaves"):
            components = read_json(
                BP / "netease_blocks" / ("%s.json" % name)
            )["minecraft:block"]["components"]
            self.assertEqual(
                "optionalAlpha",
                components["netease:render_layer"]["value"],
            )
            self.assertIn("netease:no_crop_face_block", components)
            self.assertEqual(
                0,
                components["minecraft:block_light_absorption"]["value"],
            )

    def test_mayapple_uses_the_upstream_low_plant_silhouette(self):
        block = read_json(
            BP / "netease_blocks" / "mayapple.json"
        )["minecraft:block"]
        self.assertEqual(
            "geometry.tf_slice.mayapple",
            block["components"]["minecraft:geometry"],
        )
        self.assertFalse(block["components"]["minecraft:collision_box"])
        geometry = read_json(
            RP / "models" / "blocks" / "mayapple.geo.json"
        )["minecraft:geometry"][0]
        bones = {bone["name"]: bone for bone in geometry["bones"]}
        self.assertEqual([1, 6, 1], bones["stem"]["cubes"][0]["size"])
        self.assertEqual([16, 0.1, 16], bones["leaf"]["cubes"][0]["size"])

    def test_terrain_atlas_contains_every_block_texture_key(self):
        texture_data = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]
        for block_id in BLOCK_IDS:
            self.assertIn(block_id, texture_data)


class TwilightForestBiomeContractTests(unittest.TestCase):
    def test_server_biomes_keep_only_the_required_engine_registration_parents(self):
        biome_dir = BP / "netease_biomes" / ("dm%d" % DIMENSION_ID)
        definitions = [
            path
            for path in biome_dir.glob("*.json")
            if path.stem in BIOME_SPECS.values()
        ]
        self.assertEqual(len(BIOME_SPECS), len(definitions))

        for path in definitions:
            document = read_json(path)
            self.assertEqual("1.14.0", document["format_version"])
            description = document["minecraft:biome"]["description"]
            expected_id = path.stem
            self.assertEqual(
                BIOME_INHERITS[expected_id],
                description["inherits"],
            )
            self.assertEqual(expected_id, description["identifier"])

    def test_dimension_pool_only_references_registered_server_biomes(self):
        biome_dir = BP / "netease_biomes" / ("dm%d" % DIMENSION_ID)
        registered = {
            read_json(path)["minecraft:biome"]["description"]["identifier"]
            for path in biome_dir.glob("*.json")
            if path.stem in BIOME_SPECS.values()
        }
        dimension = read_json(
            BP / "netease_dimension" / ("dm%d.json" % DIMENSION_ID)
        )
        stages = dimension["netease:dimension_info"]["components"][
            "netease:biome_source"
        ]
        referenced = {
            entry["biome_type"] if isinstance(entry, dict) else entry
            for stage in stages
            for entry in stage.get("pool", [])
        }

        expected_active = {
            entry["identifier"]
            for entry in biome_catalog.ACTIVE_LAND_BIOMES
        }
        self.assertEqual(set(BIOME_SPECS.values()), registered)
        self.assertEqual(expected_active, referenced)

    def test_dimension_blocks_all_vanilla_features_and_structures(self):
        components = read_json(
            BP / "netease_dimension" / ("dm%d.json" % DIMENSION_ID)
        )["netease:dimension_info"]["components"]

        self.assertEqual({}, components["netease:ban_vanilla_feature"])
        self.assertEqual({}, components["netease:ban_vanilla_structure"])
        self.assertEqual(
            sorted(
                [
                    entry["identifier"]
                    for entry in biome_catalog.BASE_SOURCE_BIOMES
                ]
                + [biome_catalog.BIOMES_BY_KEY["lake"]["identifier"]]
            ),
            sorted(components["netease:spawn_biomes"]),
        )

    def test_biomes_use_the_upstream_twilight_landscape_profiles(self):
        biome_dir = BP / "netease_biomes" / ("dm%d" % DIMENSION_ID)
        for biome_id, expected_profile in TWILIGHT_TERRAIN_PROFILES.items():
            components = read_json(
                biome_dir / ("%s.json" % biome_id)
            )["minecraft:biome"]["components"]
            self.assertEqual(
                expected_profile,
                components["minecraft:overworld_height"]["noise_params"],
            )

    def test_custom_worldgen_never_calls_a_vanilla_feature_identifier(self):
        references = []
        for path in (BP / "netease_features").glob("*.json"):
            document = read_json(path)
            for feature in document.values():
                if not isinstance(feature, dict):
                    continue
                for entry in feature.get("features", []):
                    reference = entry[0] if isinstance(entry, list) else entry
                    if isinstance(reference, str):
                        references.append((path.name, reference))

        self.assertTrue(references)
        self.assertEqual(
            [],
            [
                (filename, reference)
                for filename, reference in references
                if reference.startswith("minecraft:")
            ],
        )

    def test_every_server_biome_has_an_exact_client_definition(self):
        registered = {
            read_json(path)["minecraft:biome"]["description"]["identifier"]
            for path in (BP / "netease_biomes").glob("dm*/*.json")
        }
        client_ids = {
            read_json(path)["minecraft:client_biome"]["description"][
                "identifier"
            ]
            for path in (RP / "biomes").glob("*.client_biome.json")
        }
        self.assertEqual(registered, client_ids)

    def test_basic_biome_keeps_netease_registration_and_twilight_surface(self):
        biome = read_json(
            BP
            / "netease_biomes"
            / "dm33027004"
            / ("%s.json" % BIOME_ID)
        )["minecraft:biome"]
        components = biome["components"]

        self.assertEqual("plains", biome["description"]["inherits"])
        self.assertIn("dm33027004", components)
        self.assertIn("tf_slice_twilight_forest", components)
        self.assertEqual(
            [0.025, 0.05],
            components["minecraft:overworld_height"]["noise_params"],
        )
        self.assertEqual(
            {
                "sea_floor_depth": 7,
                "sea_floor_material": "minecraft:gravel",
                "foundation_material": "minecraft:stone",
                "mid_material": "minecraft:dirt",
                "top_material": "minecraft:grass",
                "sea_material": "minecraft:water",
            },
            components["minecraft:surface_parameters"],
        )

    def test_twilight_visuals_match_upstream_palette(self):
        for biome_id in BIOME_SPECS.values():
            components = read_json(
                RP / "biomes" / ("%s.client_biome.json" % biome_id)
            )["minecraft:client_biome"]["components"]
            self.assertIn("#", components["minecraft:sky_color"]["sky_color"])
            self.assertIn("#", components["minecraft:water_appearance"]["surface_color"])
            self.assertIn("#", components["minecraft:foliage_appearance"]["color"])
            self.assertIn("#", components["minecraft:grass_appearance"]["color"])

        atlas = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]
        self.assertEqual(
            "#71A74D",
            atlas["tf_slice:twilight_oak_leaves"]["textures"][0][
                "tint_color"
            ],
        )
        self.assertEqual(
            "#5BA059",
            atlas["tf_slice:canopy_leaves"]["textures"][0]["tint_color"],
        )

        fog = read_json(
            RP / "fogs" / "twilight_forest.fog.json"
        )["minecraft:fog_settings"]["distance"]
        self.assertEqual("#20224A", fog["air"]["fog_color"])
        self.assertEqual("render", fog["air"]["render_distance_type"])
        self.assertEqual("#050533", fog["water"]["fog_color"])

    def test_custom_tree_scale_matches_twilight_forest_silhouette(self):
        twilight_oak = read_json(
            BP / "netease_features" / "twilight_oak_tree_feature.json"
        )["minecraft:tree_feature"]
        self.assertEqual(
            {
                "range_min": 4,
                "range_max": 7,
            },
            twilight_oak["trunk"]["trunk_height"],
        )
        self.assertEqual(
            {"min": -3, "max": 0},
            twilight_oak["canopy"]["canopy_offset"],
        )
        self.assertNotIn("acacia_trunk", twilight_oak)
        self.assertNotIn("fancy_canopy", twilight_oak)

        canopy = read_json(
            BP / "netease_features" / "canopy_tree_feature.json"
        )["minecraft:tree_feature"]
        self.assertEqual(
            {
                "base": 20,
                "variance": 10,
                "scale": 1.0,
            },
            canopy["fancy_trunk"]["trunk_height"],
        )
        self.assertEqual(
            {
                "slope": 0.2,
                "density": 0.35,
                "min_altitude_factor": 0.65,
            },
            canopy["fancy_trunk"]["branches"],
        )
        self.assertEqual(5, canopy["fancy_canopy"]["radius"])

        large_oak = read_json(
            BP
            / "netease_features"
            / "large_twilight_oak_tree_feature.json"
        )["minecraft:tree_feature"]
        self.assertEqual(
            {"base": 5, "variance": 12, "scale": 0.618},
            large_oak["fancy_trunk"]["trunk_height"],
        )
        self.assertEqual(3, large_oak["fancy_canopy"]["radius"])

    def test_tree_features_and_rules_are_closed_over_custom_blocks(self):
        for feature_name, spec in FEATURES.items():
            feature = read_json(
                BP / "netease_features" / ("%s.json" % feature_name)
            )["minecraft:tree_feature"]
            self.assertEqual(
                spec["log"],
                feature[spec["trunk"]]["trunk_block"]["name"],
            )
            self.assertEqual(
                spec["leaves"],
                feature[spec["canopy"]]["leaf_block"]["name"],
            )

            rule = read_json(
                BP
                / "netease_feature_rules"
                / ("%s_rule.json" % feature_name)
            )["minecraft:feature_rules"]
            projected_id = rule["description"]["places_feature"]
            projected = read_json(
                BP
                / "netease_features"
                / ("%s.json" % projected_id.split(":", 1)[1])
            )["minecraft:scatter_feature"]
            self.assertEqual(
                spec.get(
                    "placed_feature",
                    "tf_slice:%s" % feature_name,
                ),
                projected["places_feature"],
            )
            self.assertTrue(projected["project_input_to_floor"])
            self.assertEqual(1, projected["distribution"]["iterations"])
            self.assertEqual(
                spec["iterations"],
                base_iterations(rule["distribution"]["iterations"]),
            )
            self.assertIn("+ 64", rule["distribution"]["y"])
            self.assertIn(
                "tf_slice_biome_forest",
                json.dumps(rule["conditions"]),
            )

    def test_tree_selectors_match_upstream_probabilities(self):
        twilight_selector = read_json(
            BP
            / "netease_features"
            / "twilight_tree_mix_selector_feature.json"
        )["minecraft:weighted_random_feature"]
        self.assertEqual(
            [
                ["tf_slice:forest_vanilla_birch_tree_feature", 4],
                ["tf_slice:forest_vanilla_oak_tree_feature", 3],
                ["tf_slice:twilight_oak_tree_feature", 9],
            ],
            twilight_selector["features"],
        )

        canopy_selector = read_json(
            BP
            / "netease_features"
            / "canopy_tree_selector_feature.json"
        )["minecraft:weighted_random_feature"]
        self.assertEqual(
            [
                ["tf_slice:canopy_tree_source_shape_feature", 3],
                ["tf_slice:twilight_oak_tree_feature", 2],
            ],
            canopy_selector["features"],
        )

    def test_forest_groundcover_is_closed_over_mayapple_grass_flowers_and_mushrooms(self):
        flower = read_json(
            BP / "netease_features" / "twilight_flower_feature.json"
        )["minecraft:single_block_feature"]
        self.assertEqual(12, len(flower["places_block"]))

        patch_specs = {
            "twilight_flower_patch_feature": (32, 2, 75.0),
            "forest_groundcover_patch_feature": (64, 2, None),
            "forest_mushroom_patch_feature": (16, 1, 25.0),
            "mayapple_patch_feature": (96, 1, None),
        }
        for feature_name, (patch_iterations, rule_iterations, chance) in (
            patch_specs.items()
        ):
            feature = read_json(
                BP / "netease_features" / ("%s.json" % feature_name)
            )["minecraft:scatter_feature"]
            self.assertTrue(feature["project_input_to_floor"])
            self.assertEqual(
                patch_iterations,
                feature["distribution"]["iterations"],
            )
            rule = read_json(
                BP
                / "netease_feature_rules"
                / ("%s_rule.json" % feature_name)
            )["minecraft:feature_rules"]
            self.assertEqual(
                "tf_slice:%s" % feature_name,
                rule["description"]["places_feature"],
            )
            self.assertEqual(
                rule_iterations,
                rule["distribution"]["iterations"],
            )
            self.assertEqual(
                chance,
                rule["distribution"].get("scatter_chance"),
            )
            self.assertIn(
                "tf_slice_terrestrial_groundcover",
                json.dumps(rule["conditions"]),
            )


if __name__ == "__main__":
    unittest.main()
