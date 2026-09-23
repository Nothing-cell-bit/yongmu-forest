# -*- coding: utf-8 -*-
import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
SCRIPT_ROOT = str(BP)
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)

EXPECTED = {
    "forest": ("dm33027004_plains", "plains", [0.025, 0.05], 14),
    "dense_forest": ("dm33027004_jungle", "jungle", [0.1, 0.2], 14),
    "oak_savannah": ("dm33027004_savanna", "savanna", [0.05, 0.1], 14),
    "mushroom_forest": (
        "dm33027004_mushroom_island_shore",
        "mushroom_island_shore",
        [0.025, 0.05],
        14,
    ),
    "firefly_forest": (
        "dm33027004_flower_forest",
        "flower_forest",
        [0.0625, 0.05],
        14,
    ),
    "stream": ("dm33027004_river", "river", [-0.1, 0.0], 3),
    "dense_mushroom_forest": (
        "dm33027004_mushroom_island",
        "mushroom_island",
        [0.05, 0.05],
        1,
    ),
    "lake": ("dm33027004_ocean", "ocean", [-1.97, 0.0], 1),
    "enchanted_forest": (
        "dm33027004_birch_forest_mutated",
        "birch_forest_mutated",
        [0.025, 0.05],
        1,
    ),
    "clearing": (
        "dm33027004_sunflower_plains",
        "sunflower_plains",
        [0.005, 0.005],
        1,
    ),
    "spooky_forest": (
        "dm33027004_roofed_forest",
        "roofed_forest",
        [0.025, 0.05],
        1,
    ),
    "swamp": (
        "dm33027004_swampland",
        "swampland",
        [-0.1, 0.15],
        1,
    ),
    "fire_swamp": (
        "dm33027004_swampland_mutated",
        "swampland_mutated",
        [-0.02, 0.05],
        1,
    ),
    "dark_forest": (
        "dm33027004_roofed_forest_mutated",
        "roofed_forest_mutated",
        [0.025, 0.005],
        1,
    ),
    "dark_forest_center": (
        "dm33027004_redwood_taiga_mutated",
        "redwood_taiga_mutated",
        [0.025, 0.005],
        1,
    ),
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class BiomeExpansionContractTests(unittest.TestCase):
    def test_catalog_is_the_single_complete_source_of_biome_metadata(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        actual = {
            entry["key"]: (
                entry["identifier"],
                entry["inherits"],
                entry["noise_params"],
                entry["weight"],
            )
            for entry in catalog.BIOMES
        }
        self.assertEqual(EXPECTED, actual)
        self.assertEqual(15, len(catalog.BIOMES))
        self.assertEqual(15, len(catalog.BIOMES_BY_IDENTIFIER))

    def test_all_server_and_client_biomes_are_registered_exactly_once(self):
        expected_ids = {spec[0] for spec in EXPECTED.values()}
        server_paths = list(
            (BP / "netease_biomes" / "dm33027004").glob("*.json")
        )
        client_paths = list((RP / "biomes").glob("*.client_biome.json"))

        server_ids = {
            read_json(path)["minecraft:biome"]["description"]["identifier"]
            for path in server_paths
        }
        client_ids = {
            read_json(path)["minecraft:client_biome"]["description"][
                "identifier"
            ]
            for path in client_paths
        }
        self.assertEqual(expected_ids, server_ids)
        self.assertEqual(expected_ids, client_ids)
        self.assertEqual(15, len(server_paths))
        self.assertEqual(15, len(client_paths))

    def test_server_biomes_match_upstream_profiles_and_have_unique_tags(self):
        for key, (identifier, inherits, noise_params, _weight) in (
            EXPECTED.items()
        ):
            biome = read_json(
                BP
                / "netease_biomes"
                / "dm33027004"
                / ("%s.json" % identifier)
            )["minecraft:biome"]
            self.assertEqual(inherits, biome["description"]["inherits"])
            components = biome["components"]
            self.assertEqual(
                noise_params,
                components["minecraft:overworld_height"]["noise_params"],
            )
            self.assertIn("dm33027004", components)
            self.assertIn("tf_slice_twilight_forest", components)
            self.assertIn("tf_slice_biome_%s" % key, components)

    def test_dimension_pool_and_spawn_list_are_catalog_driven(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        expected_weights = {
            entry["identifier"]: entry["weight"]
            for entry in catalog.RANDOM_SOURCE_BIOMES
        }
        components = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]
        pool = next(
            stage["pool"]
            for stage in components["netease:biome_source"]
            if stage["type"] == "random_with_weight"
        )
        actual_weights = {
            entry["biome_type"]: entry["weight"] for entry in pool
        }
        self.assertEqual(expected_weights, actual_weights)
        self.assertEqual(
            {
                catalog.BIOMES_BY_KEY[key]["identifier"]
                for key in (
                    "swamp",
                    "fire_swamp",
                    "dark_forest",
                    "dark_forest_center",
                )
            },
            {
                stage["pool"][0]
                for stage in components["netease:biome_source"]
                if stage["type"] == "condition"
            },
        )
        self.assertEqual(
            {
                entry["identifier"]
                for entry in catalog.BASE_SOURCE_BIOMES
            }
            | {catalog.BIOMES_BY_KEY["lake"]["identifier"]},
            set(components["netease:spawn_biomes"]),
        )

    def test_stream_is_only_injected_at_compatible_land_boundaries(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        aquatic_ids = {
            catalog.BIOMES_BY_KEY["lake"]["identifier"],
            catalog.BIOMES_BY_KEY["stream"]["identifier"],
        }
        base_ids = {
            entry["identifier"] for entry in catalog.BASE_SOURCE_BIOMES
        }
        dimension = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]
        pool = next(
            stage["pool"]
            for stage in dimension["netease:biome_source"]
            if stage["type"] == "random_with_weight"
        )

        self.assertTrue(aquatic_ids.isdisjoint(base_ids))
        self.assertTrue(
            aquatic_ids.isdisjoint(
                entry["biome_type"] for entry in pool
            )
        )
        self.assertTrue(
            aquatic_ids.isdisjoint(
                stage["pool"][0]
                for stage in dimension["netease:biome_source"]
                if stage["type"] == "condition"
            )
        )
        transitions = [
            stage
            for stage in dimension["netease:biome_source"]
            if stage["type"] == "transition"
        ]
        self.assertEqual(
            list(catalog.STREAM_TRANSITION_IDENTIFIER_PAIRS),
            [
                (stage["biome_a"], stage["biome_b"])
                for stage in transitions
            ],
        )
        self.assertEqual(
            {catalog.BIOMES_BY_KEY["stream"]["identifier"]},
            {stage["biome_transition"] for stage in transitions},
        )
        encoded_transitions = json.dumps(transitions)
        self.assertNotIn(
            catalog.BIOMES_BY_KEY["lake"]["identifier"],
            encoded_transitions,
        )
        swamp_id = catalog.BIOMES_BY_KEY["swamp"]["identifier"]
        for open_key in ("clearing", "oak_savannah"):
            open_id = catalog.BIOMES_BY_KEY[open_key]["identifier"]
            self.assertTrue(
                all(
                    open_id not in (stage["biome_a"], stage["biome_b"])
                    or swamp_id in (stage["biome_a"], stage["biome_b"])
                    for stage in transitions
                )
            )
        self.assertGreaterEqual(
            min(
                catalog.BIOMES_BY_IDENTIFIER[biome_id][
                    "noise_params"
                ][0]
                for biome_id in base_ids
            ),
            -0.25,
        )

    def test_stream_profile_cannot_form_cliff_trenches_at_land_seams(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        stream_depth = catalog.BIOMES_BY_KEY["stream"]["noise_params"][0]
        seam_depths = {
            key: catalog.BIOMES_BY_KEY[key]["noise_params"][0]
            for pair in catalog.STREAM_TRANSITION_KEY_PAIRS
            for key in pair
        }

        # NetEase inserts the stream after the final land zoom and applies the
        # biome height directly. Keep every last-stage seam within a shallow
        # land-profile delta; the former -0.5 value made a cliff-like trench.
        self.assertEqual(-0.1, stream_depth)
        for key, land_depth in seam_depths.items():
            self.assertLessEqual(
                abs(stream_depth - land_depth),
                0.2 + 1.0e-9,
                key,
            )

    def test_biome_source_builds_broad_regions_before_stream_seams(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        source = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]["netease:biome_source"]
        transition_start = next(
            index
            for index, stage in enumerate(source)
            if stage["type"] == "transition"
        )

        self.assertEqual("random_with_weight", source[0]["type"])
        self.assertEqual(
            ("vanilla_zoom_2x",),
            catalog.PRE_KEY_LAND_ZOOM_STAGES,
        )
        self.assertEqual(
            ("vanilla_zoom_2x",) * 4,
            catalog.FINAL_LAND_ZOOM_STAGES,
        )
        self.assertEqual(
            (
                list(catalog.PRE_KEY_LAND_ZOOM_STAGES)
                + ["condition"] * 4
                + list(catalog.ROUTE_PRE_STABILIZE_ZOOM_STAGES)
                + ["condition"] * 4
                + list(catalog.FINAL_LAND_ZOOM_STAGES)
            ),
            [stage["type"] for stage in source[1:transition_start]],
        )
        self.assertTrue(
            all(
                stage["type"] == "transition"
                for stage in source[transition_start:]
            )
        )
        self.assertEqual(
            7,
            sum(
                stage["type"] in (
                    "fuzzy_zoom_2x",
                    "vanilla_zoom_2x",
                )
                for stage in source
            ),
        )
        condition_indexes = [
            index
            for index, stage in enumerate(source)
            if stage["type"] == "condition"
        ]
        self.assertEqual(
            list(catalog.PRE_KEY_LAND_ZOOM_STAGES),
            [stage["type"] for stage in source[1:2]],
        )
        self.assertEqual(
            [2, 3, 4, 5, 8, 9, 10, 11],
            condition_indexes,
        )
        self.assertEqual(
            list(catalog.ROUTE_PRE_STABILIZE_ZOOM_STAGES),
            [stage["type"] for stage in source[6:8]],
        )
        self.assertEqual(
            list(catalog.FINAL_LAND_ZOOM_STAGES),
            [
                stage["type"]
                for stage in source[12:transition_start]
            ],
        )

    def test_key_biome_scale_preserves_the_accepted_landmark_envelope(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        key_zoom_scale = 1 << (
            len(catalog.ROUTE_PRE_STABILIZE_ZOOM_STAGES)
            + len(catalog.FINAL_LAND_ZOOM_STAGES)
        )
        ordinary_zoom_scale = 1 << (
            len(catalog.PRE_KEY_LAND_ZOOM_STAGES)
            + len(catalog.ROUTE_PRE_STABILIZE_ZOOM_STAGES)
            + len(catalog.FINAL_LAND_ZOOM_STAGES)
        )
        route_cell_width = catalog.ROUTE_BIOME_CELL_BLOCKS

        self.assertEqual(64, key_zoom_scale)
        self.assertEqual(128, ordinary_zoom_scale)
        self.assertEqual(
            {"len_x": 8, "len_z": 8, "border_x": 2, "border_z": 2},
            catalog.KEY_BIOME_GRID,
        )
        self.assertEqual(
            2048,
            catalog.ROUTE_BIOME_REGION_CELLS
            * catalog.ROUTE_BIOME_COORDINATE_BLOCKS,
        )
        self.assertEqual(256, catalog.ROUTE_BIOME_CELL_BLOCKS)
        self.assertEqual(64, catalog.ROUTE_BIOME_SEED_BLOCKS)
        self.assertEqual(
            256,
            catalog.ROUTE_BIOME_COMPANION_CELL_DISTANCE
            * route_cell_width,
        )
        self.assertEqual(128, catalog.ROUTE_STABLE_INTERIOR_BLOCKS)
        self.assertEqual(128, catalog.ROUTE_EFFECTIVE_TERRITORY_BLOCKS)
        route_outer_width = catalog.ROUTE_ROUNDED_MAX_ENVELOPE_BLOCKS
        self.assertEqual(592, route_outer_width)
        self.assertEqual(1456, 2048 - route_outer_width)

    def test_one_magic_map_deterministically_contains_both_route_types(self):
        """Do not let independent weighted draws erase a progression route."""
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        source = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]["netease:biome_source"]
        conditions = [stage for stage in source if stage["type"] == "condition"]
        map_width = 2048
        period_x = (
            catalog.ROUTE_BIOME_REGION_CELLS
            * catalog.ROUTE_BIOME_COORDINATE_BLOCKS
        )
        period_z = period_x
        macro_slots = (map_width // period_x) * (map_width // period_z)

        self.assertEqual((2048, 2048), (period_x, period_z))
        self.assertEqual(1, macro_slots)
        self.assertEqual(8, len(conditions))
        self.assertTrue(
            all("variable.worldx" in stage["condition"] for stage in conditions)
        )
        self.assertTrue(
            all("variable.worldz" in stage["condition"] for stage in conditions)
        )

        for routes in catalog.ROUTE_CORE_LOCALS_BY_VARIANT.values():
            self.assertEqual(
                {"fire_swamp", "dark_forest_center"},
                set(routes),
            )
            self.assertEqual(2, len(set(routes.values())))
        self.assertEqual(
            {
                catalog.BIOMES_BY_KEY[key]["identifier"]
                for key in (
                    "swamp",
                    "fire_swamp",
                    "dark_forest",
                    "dark_forest_center",
                )
            },
            {stage["pool"][0] for stage in conditions},
        )

    def test_dark_forest_builder_preserves_the_canonical_dimension_source(self):
        builder = importlib.import_module("tools.build_dark_forest_biomes")
        expected = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )

        self.assertEqual(expected, builder.dimension_document())

    def test_upstream_associated_performance_candidate_is_reproducible(self):
        candidate_builder = importlib.import_module(
            "tools.build_biome_performance_candidate"
        )
        source = candidate_builder.candidate_biome_source()
        types = [stage["type"] for stage in source]
        key_stage = next(
            stage for stage in source if stage["type"] == "gen_key_biomes"
        )
        associated = [
            stage for stage in source if stage["type"] == "associated"
        ]

        self.assertEqual(
            {"len_x": 8, "len_z": 8, "border_x": 2, "border_z": 2},
            {
                field: key_stage[field]
                for field in ("len_x", "len_z", "border_x", "border_z")
            },
        )
        self.assertEqual(1, types.count("condition"))
        self.assertEqual(2, len(associated))
        self.assertEqual(7, types.count("fuzzy_zoom_2x") + types.count("vanilla_zoom_2x"))
        self.assertEqual(
            1024,
            key_stage["len_x"] * (1 << 7),
        )
        self.assertTrue(
            all(
                len(stage["associated_biomes"])
                == len(candidate_builder.CARDINAL_OFFSETS)
                for stage in associated
            )
        )

    def test_canonical_route_stencil_uses_no_neighborhood_dilation(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        builder = importlib.import_module("tools.build_dark_forest_biomes")
        source = builder.dimension_document()["netease:dimension_info"][
            "components"
        ]["netease:biome_source"]
        transitions = [
            stage for stage in source if stage["type"] == "transition"
        ]
        land_stages = source[: len(source) - len(transitions)]
        conditions = [
            stage for stage in land_stages if stage["type"] == "condition"
        ]
        encoded = json.dumps(conditions)

        self.assertEqual(256, catalog.ROUTE_BIOME_CELL_BLOCKS)
        self.assertEqual((2, 2), catalog.ROUTE_BIOME_CORE_LOCAL)
        self.assertEqual(4, len(catalog.ROUTE_BIOME_COMPANION_LOCALS))
        self.assertEqual(128, catalog.ROUTE_STABLE_INTERIOR_BLOCKS)
        self.assertEqual(128, catalog.ROUTE_EFFECTIVE_TERRITORY_BLOCKS)
        self.assertEqual(8, len(conditions))
        self.assertNotIn("get_neighborhood_is_biome", encoded)
        self.assertIn("==", encoded)
        self.assertNotIn(">=", encoded)
        self.assertNotIn("gen_key_biomes", [stage["type"] for stage in land_stages])
        self.assertNotIn("associated", [stage["type"] for stage in land_stages])
        self.assertEqual(
            7,
            sum(
                stage["type"] in ("fuzzy_zoom_2x", "vanilla_zoom_2x")
                for stage in land_stages
            ),
        )
        self.assertEqual(
            2048,
            catalog.ROUTE_BIOME_REGION_CELLS
            * catalog.ROUTE_BIOME_COORDINATE_BLOCKS,
        )
        self.assertEqual(
            256,
            catalog.ROUTE_BIOME_COMPANION_CELL_DISTANCE
            * catalog.ROUTE_BIOME_CELL_BLOCKS,
        )

    def test_route_conditions_cache_repeated_molang_without_changing_stages(self):
        builder = importlib.import_module("tools.build_dark_forest_biomes")
        source = builder.dimension_document()["netease:dimension_info"][
            "components"
        ]["netease:biome_source"]
        conditions = [stage for stage in source if stage["type"] == "condition"]
        condition_text = "".join(stage["condition"] for stage in conditions)

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
        for stage in conditions:
            expression = stage["condition"]
            self.assertIn("temp.region_x =", expression)
            self.assertIn("temp.region_z =", expression)
            self.assertIn("temp.local_x =", expression)
            self.assertIn("temp.local_z =", expression)
            self.assertIn("temp.variant =", expression)
            self.assertEqual(1, expression.count("return "))
        self.assertLessEqual(condition_text.count("math.floor"), 48)
        self.assertLessEqual(condition_text.count("math.sin"), 16)
        self.assertLessEqual(len(condition_text), 30000)
        self.assertNotIn("get_neighborhood_is_biome", condition_text)

    def test_release_validator_accepts_the_decoupled_zoom_order(self):
        validator = importlib.import_module("tools.validate_slice")
        gate = validator.Gate()
        documents = validator.collect_json(gate)

        validator.validate_dimension_worldgen(gate, documents)

        self.assertFalse(
            any(
                "finish every land zoom before stream seams" in failure
                for failure in gate.failures
            ),
            gate.failures,
        )

    def test_rare_biomes_use_the_canonical_coordinate_stencil(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        source = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]["netease:biome_source"]
        conditions = [stage for stage in source if stage["type"] == "condition"]
        self.assertEqual(8, len(conditions))
        self.assertEqual(
            ["swamp", "fire_swamp", "dark_forest", "dark_forest_center"]
            * 2,
            [
                catalog.BIOMES_BY_IDENTIFIER[stage["pool"][0]]["key"]
                for stage in conditions
            ],
        )
        self.assertTrue(
            all(" / 32" in stage["condition"] for stage in conditions[:4])
        )
        self.assertTrue(
            all(" / 128" in stage["condition"] for stage in conditions[4:])
        )
        self.assertFalse(
            any(
                stage["type"] in ("gen_key_biomes", "associated")
                for stage in source
            )
        )

    def test_every_client_biome_has_the_complete_twilight_render_contract(self):
        for identifier, _inherits, _noise_params, _weight in EXPECTED.values():
            components = read_json(
                RP / "biomes" / ("%s.client_biome.json" % identifier)
            )["minecraft:client_biome"]["components"]
            expected_fog = {
                "dm33027004_roofed_forest": "tf_slice:fog_spooky_forest",
                "dm33027004_birch_forest_mutated": (
                    "tf_slice:fog_enchanted_forest"
                ),
                "dm33027004_swampland": "tf_slice:fog_swamp",
                "dm33027004_swampland_mutated": "tf_slice:fog_fire_swamp",
                "dm33027004_roofed_forest_mutated": "tf_slice:fog_dark_forest",
                "dm33027004_redwood_taiga_mutated": (
                    "tf_slice:fog_dark_forest_center"
                ),
            }.get(identifier, "tf_slice:fog_twilight_forest")
            self.assertEqual(
                expected_fog,
                components["minecraft:fog_appearance"]["fog_identifier"],
            )
            self.assertIn("minecraft:sky_color", components)
            self.assertIn("minecraft:water_appearance", components)
            self.assertIn("minecraft:foliage_appearance", components)
            self.assertIn("minecraft:grass_appearance", components)
            for deferred_component in (
                "minecraft:atmosphere_identifier",
                "minecraft:color_grading_identifier",
                "minecraft:lighting_identifier",
                "minecraft:water_identifier",
            ):
                self.assertNotIn(deferred_component, components)


if __name__ == "__main__":
    unittest.main()
