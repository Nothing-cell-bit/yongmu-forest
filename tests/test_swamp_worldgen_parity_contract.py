# -*- coding: utf-8 -*-
import importlib
import json
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops

from tools.native_structure_worldgen_safety import base_iterations

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
TOOLS_ROOT = str(ROOT / "tools")
if TOOLS_ROOT not in sys.path:
    sys.path.insert(0, TOOLS_ROOT)
SCRIPT_ROOT = str(BP)
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)

import build_swamp_features as swamp_builder


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def feature_rule(name):
    return read_json(BP / "netease_feature_rules" / (name + ".json"))[
        "minecraft:feature_rules"
    ]


class SwampBiomeEnvelopeContractTests(unittest.TestCase):
    def test_route_stencil_writes_companions_before_each_inner_core(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        source = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]["netease:biome_source"]
        conditions = [stage for stage in source if stage["type"] == "condition"]

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
        self.assertNotIn(
            "get_neighborhood_is_biome",
            json.dumps(conditions),
        )

    def test_cardinal_route_domain_fits_one_main_and_four_companions(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        cell_width = catalog.ROUTE_BIOME_CELL_BLOCKS
        companion_distance = (
            catalog.ROUTE_BIOME_COMPANION_CELL_DISTANCE * cell_width
        )
        landmark_width = catalog.ROUTE_STABLE_INTERIOR_BLOCKS
        outer_width = catalog.ROUTE_ROUNDED_MAX_ENVELOPE_BLOCKS
        period = (
            catalog.ROUTE_BIOME_REGION_CELLS
            * catalog.ROUTE_BIOME_COORDINATE_BLOCKS
        )

        self.assertEqual(256, cell_width)
        self.assertEqual(656, outer_width)
        self.assertEqual(256, companion_distance)
        self.assertEqual(2048, period)
        self.assertEqual(
            {"len_x": 8, "len_z": 8, "border_x": 2, "border_z": 2},
            catalog.KEY_BIOME_GRID,
        )

        # The route structures are surface-pass tiles selected from the shared
        # center plus four cardinal 256-block offsets.  The arms must contain
        # each complete 112-block companion footprint while remaining inside
        # one key-biome repetition period.
        self.assertGreaterEqual(landmark_width, 112)
        self.assertGreaterEqual(period - outer_width, 64)

    def test_route_feature_rules_use_bounded_center_samples(self):
        for mode in ("fire_swamp", "dark_forest_center"):
            iterations = str(
                feature_rule(
                    "ruin_landmark_surface_%s_feature_rule" % mode
                )["distribution"]["iterations"]
            )
            self.assertEqual(1, iterations.count("query.is_biome"))

        for mode in ("swamp", "dark_forest"):
            iterations = str(
                feature_rule(
                    "ruin_landmark_surface_%s_feature_rule" % mode
                )["distribution"]["iterations"]
            )
            self.assertEqual(5, iterations.count("query.is_biome"))
            self.assertIn("256", iterations)

    def test_condition_stages_are_coordinate_only_route_stencils(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        builder = importlib.import_module("tools.build_dark_forest_biomes")
        source = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]["netease:biome_source"]
        conditions = [stage for stage in source if stage["type"] == "condition"]
        seed_specs = builder.route_seed_stage_specs()
        stabilize_specs = builder.route_stabilize_stage_specs()

        self.assertEqual(8, len(conditions))
        self.assertEqual([], [stage for stage in source if stage["type"] == "associated"])
        self.assertFalse(any(stage["type"] == "gen_key_biomes" for stage in source))
        self.assertNotIn("get_neighborhood_is_biome", json.dumps(conditions))
        self.assertEqual(
            catalog.route_biome_seed_condition(
                seed_specs[0]["geometryByVariant"],
            ),
            conditions[0]["condition"],
        )
        self.assertEqual(
            catalog.route_biome_core_stabilize_condition(
                stabilize_specs[-1]["geometryByVariant"],
                stabilize_specs[-1]["routeKey"],
            ),
            conditions[-1]["condition"],
        )

    def test_fire_core_and_swamp_envelope_fit_route_landmarks(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")

        source = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]["netease:biome_source"]
        companion_cell_width = catalog.ROUTE_BIOME_CELL_BLOCKS
        companion_distance = (
            catalog.ROUTE_BIOME_COMPANION_CELL_DISTANCE
            * companion_cell_width
        )
        total_zoom_count = sum(
            stage["type"] in ("fuzzy_zoom_2x", "vanilla_zoom_2x")
            for stage in source
        )
        ordinary_land_seed_width = 4 * (2 ** total_zoom_count)
        fire_core_width = catalog.ROUTE_EFFECTIVE_TERRITORY_BLOCKS
        hydra_footprint = 80
        labyrinth_footprint = 112
        envelope_width = 2 * (
            companion_distance + fire_core_width // 2
        )

        # NetEase condition coordinates use one block per source unit. Keep
        # the 256-block center spacing, but narrow each visible territory to
        # 128 blocks so jittered centers stay inside without swallowing the
        # diagonal landmark cells.
        self.assertEqual(512, ordinary_land_seed_width)
        self.assertEqual(256, companion_cell_width)
        self.assertEqual(128, fire_core_width)
        self.assertEqual(256, companion_distance)
        self.assertGreaterEqual(fire_core_width, hydra_footprint)
        self.assertGreaterEqual(fire_core_width, labyrinth_footprint)
        self.assertEqual(
            2048,
            catalog.ROUTE_BIOME_REGION_CELLS
            * catalog.ROUTE_BIOME_COORDINATE_BLOCKS,
        )
        self.assertEqual(640, envelope_width)
        self.assertLess(
            envelope_width,
            catalog.ROUTE_BIOME_REGION_CELLS
            * catalog.ROUTE_BIOME_COORDINATE_BLOCKS,
        )

    def test_swamp_route_landmarks_follow_generated_terrain_height(self):
        for mode in ("swamp", "fire_swamp"):
            rule = feature_rule(
                "ruin_landmark_surface_%s_feature_rule" % mode
            )
            y_expression = str(rule["distribution"]["y"])
            self.assertIn("query.get_height_at", y_expression)
            expected_samples = 1
            self.assertEqual(
                expected_samples,
                y_expression.count("query.get_height_at"),
            )
            self.assertIn(
                "- 42" if mode == "swamp" else "- 17",
                y_expression,
            )
            self.assertNotIn("math.min", y_expression)
            self.assertNotIn("math.max", y_expression)

    def test_swamp_restores_surface_ruins_and_groundcover(self):
        components = read_json(
            BP
            / "netease_biomes"
            / "dm33027004"
            / "dm33027004_swampland.json"
        )["minecraft:biome"]["components"]
        self.assertIn("tf_slice_small_ruins", components)
        self.assertIn("tf_slice_terrestrial_groundcover", components)


class SwampTreeContractTests(unittest.TestCase):
    def test_tree_vines_form_supported_attachment_chains(self):
        attachment_offsets = {
            1: (0, 0, 1),
            2: (-1, 0, 0),
            4: (0, 0, -1),
            8: (1, 0, 0),
        }
        support_blocks = {
            "tf_slice:mangrove_log",
            "tf_slice:mangrove_log_x",
            "tf_slice:mangrove_log_z",
            "tf_slice:mangrove_leaves",
            "tf_slice:twilight_oak_log",
            "tf_slice:twilight_oak_leaves",
        }
        unsupported = []

        for tree_kind, factory, expected_strands in (
            ("mangrove", swamp_builder.mangrove_tree_structure, 8),
            ("swampy_oak", swamp_builder.swampy_oak_tree_structure, 6),
        ):
            for variant in range(4):
                structure, _center, _base_y = factory(variant)
                strand_count = 0
                for (x, y, z), block in structure.blocks.items():
                    if block[0] != "minecraft:vine":
                        continue
                    bits = int(block[1].get("vine_direction_bits", 0))
                    side_supported = any(
                        bits & bit
                        and structure.blocks.get(
                            (x + dx, y + dy, z + dz), (None,)
                        )[0]
                        in support_blocks
                        for bit, (dx, dy, dz) in attachment_offsets.items()
                    )
                    above = structure.blocks.get((x, y + 1, z))
                    chain_supported = (
                        above is not None
                        and above[0] == "minecraft:vine"
                        and int(above[1].get("vine_direction_bits", 0)) & bits
                        == bits
                    )
                    if not chain_supported:
                        strand_count += 1
                    if not side_supported and not chain_supported:
                        unsupported.append(
                            (tree_kind, variant, (x, y, z), bits)
                        )
                self.assertEqual(
                    expected_strands,
                    strand_count,
                    "%s variant %d lost source-visible vine strands"
                    % (tree_kind, variant),
                )

        self.assertEqual([], unsupported)

    def test_mangrove_projects_once_then_places_source_tree_selector(self):
        rule = feature_rule("mangrove_tree_feature_rule")
        self.assertEqual(
            "tf_slice:mangrove_tree_landmark_surface_project_feature",
            rule["description"]["places_feature"],
        )
        self.assertEqual(
            "3 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
            base_iterations(rule["distribution"]["iterations"]),
        )
        self.assertEqual(
            "(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64",
            rule["distribution"]["y"],
        )

        projection = read_json(
            BP
            / "netease_features"
            / "mangrove_tree_landmark_surface_project_feature.json"
        )["minecraft:scatter_feature"]
        self.assertTrue(projection["project_input_to_floor"])
        self.assertEqual(1, projection["distribution"]["iterations"])
        self.assertEqual(
            "tf_slice:twilight_mangrove_tree_feature",
            projection["places_feature"],
        )

        selector = read_json(
            BP / "netease_features" / "twilight_mangrove_tree_feature.json"
        )["minecraft:weighted_random_feature"]
        self.assertGreaterEqual(len(selector["features"]), 4)

        structures = sorted(
            (
                BP
                / "structures"
                / "tf_slice"
                / "swamp"
                / "trees"
                / "mangrove"
            ).glob("*.mcstructure")
        )
        self.assertGreaterEqual(len(structures), 4)
        encoded = b"".join(path.read_bytes() for path in structures)
        for block_id in (
            b"tf_slice:mangrove_log",
            b"tf_slice:mangrove_log_x",
            b"tf_slice:mangrove_log_z",
            b"tf_slice:mangrove_leaves",
            b"tf_slice:firefly",
            b"minecraft:vine",
        ):
            self.assertIn(block_id, encoded)

    def test_both_swamps_use_source_swampy_oaks(self):
        for biome_key in ("swamp", "fire_swamp"):
            rule = feature_rule("%s_swampy_oak_tree_feature_rule" % biome_key)
            landmark_projection = read_json(
                BP
                / "netease_features"
                / (
                    "%s.json"
                    % rule["description"]["places_feature"].split(":", 1)[1]
                )
            )["minecraft:scatter_feature"]
            self.assertEqual(
                "tf_slice:swampy_oak_tree_feature",
                landmark_projection["places_feature"],
            )
            self.assertTrue(
                landmark_projection["project_input_to_floor"]
            )
            self.assertEqual(1, landmark_projection["distribution"]["iterations"])
            self.assertEqual(
                "4 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
                base_iterations(rule["distribution"]["iterations"]),
            )

        self.assertFalse(
            (BP / "netease_feature_rules" / "fire_swamp_tree_feature_rule.json").exists()
        )

        selector = read_json(
            BP / "netease_features" / "swampy_oak_tree_feature.json"
        )["minecraft:weighted_random_feature"]
        self.assertGreaterEqual(len(selector["features"]), 4)

        structures = sorted(
            (
                BP
                / "structures"
                / "tf_slice"
                / "swamp"
                / "trees"
                / "swampy_oak"
            ).glob("*.mcstructure")
        )
        self.assertGreaterEqual(len(structures), 4)
        encoded = b"".join(path.read_bytes() for path in structures)
        for block_id in (
            b"tf_slice:twilight_oak_log",
            b"tf_slice:twilight_oak_leaves",
            b"minecraft:vine",
        ):
            self.assertIn(block_id, encoded)

    def test_canopy_tree_uses_source_branches_and_fireflies(self):
        selector = read_json(
            BP
            / "netease_features"
            / "canopy_tree_source_shape_feature.json"
        )["minecraft:weighted_random_feature"]
        self.assertGreaterEqual(len(selector["features"]), 4)
        structures = sorted(
            (
                BP
                / "structures"
                / "tf_slice"
                / "swamp"
                / "trees"
                / "canopy"
            ).glob("*.mcstructure")
        )
        self.assertGreaterEqual(len(structures), 4)
        encoded = b"".join(path.read_bytes() for path in structures)
        for block_id in (
            b"tf_slice:canopy_log",
            b"tf_slice:canopy_log_x",
            b"tf_slice:canopy_log_z",
            b"tf_slice:canopy_leaves",
            b"tf_slice:firefly",
        ):
            self.assertIn(block_id, encoded)

    def test_static_tree_templates_omit_terrain_sensitive_roots(self):
        metadata = read_json(BP / "metadata" / "swamp_generation.json")
        self.assertEqual(
            "terrain_aware_trace_exposed_root",
            metadata["tree_root_placement"]["upstream"],
        )
        self.assertEqual(
            "omit_static_roots",
            metadata["tree_root_placement"]["implementation"],
        )
        root_blocks = {
            "tf_slice:mangrove_root",
            "tf_slice:root_block",
            "tf_slice:liveroot_block",
        }
        factories = (
            swamp_builder.mangrove_tree_structure,
            swamp_builder.swampy_oak_tree_structure,
            swamp_builder.canopy_tree_structure,
        )

        for factory in factories:
            for variant in range(4):
                structure, unused_center, unused_base_y = factory(variant)
                static_roots = {
                    block_name
                    for block_name, unused_states, unused_layer in (
                        block_data for block_data in structure.blocks.values()
                    )
                    if block_name in root_blocks
                }
                self.assertEqual(
                    set(),
                    static_roots,
                    "%s variant %d bakes roots without terrain checks"
                    % (factory.__name__, variant),
                )

    def test_mangrove_horizontal_logs_have_source_end_texture(self):
        for axis in ("x", "z"):
            block = read_json(
                BP / "netease_blocks" / ("mangrove_log_%s.json" % axis)
            )["minecraft:block"]
            materials = block["components"]["minecraft:material_instances"]
            self.assertEqual("tf_slice:mangrove_log", materials["side"]["texture"])
            self.assertEqual(
                "tf_slice:mangrove_log_top", materials["end"]["texture"]
            )
        self.assertTrue(
            (RP / "textures" / "blocks" / "mangrove_log_top.png").exists()
        )

    def test_mangrove_fallen_logs_keep_one_in_forty_rarity(self):
        rule = feature_rule("mangrove_fallen_log_feature_rule")
        self.assertEqual(
            "tf_slice:mangrove_fallen_log_selector_feature",
            rule["description"]["places_feature"],
        )
        self.assertEqual(2.5, rule["distribution"]["scatter_chance"])


class SwampAquaticPlantContractTests(unittest.TestCase):
    def test_huge_lily_pad_natural_generation_uses_only_north_template(self):
        self.assertEqual(
            (("huge_lily_pad_2x2_feature", 1),),
            swamp_builder.huge_lily_pad_natural_sequences(),
        )

    def test_huge_lily_pad_uses_one_runtime_safe_thirty_pixel_plane(self):
        geometries = swamp_builder.swamp_plant_geometry()["minecraft:geometry"]
        geometry = next(
            item for item in geometries
            if item["description"]["identifier"]
            == "geometry.tf_slice.huge_lily_pad_item"
        )
        self.assertEqual(2, geometry["description"]["visible_bounds_width"])
        cube = geometry["bones"][0]["cubes"][0]
        self.assertEqual([-8, 0, -8], cube["origin"])
        self.assertEqual([30, 1, 30], cube["size"])
        self.assertEqual({"up"}, set(cube["uv"]))
        self.assertEqual([32, 32], cube["uv"]["up"]["uv_size"])

        components = swamp_builder.huge_lily_pad_block()["minecraft:block"][
            "components"
        ]
        expected_bounds = {
            "min": [0.0, 0.0, 0.0],
            "max": [1.875, 0.0625, 1.875],
        }
        self.assertEqual(
            {"collision": expected_bounds, "clip": expected_bounds},
            components["netease:aabb"],
        )

    def test_huge_lily_pad_texture_entries_restore_upstream_tints(self):
        self.assertEqual(
            {
                "textures": [
                    {
                        "path": "textures/blocks/huge_lily_pad",
                        "tint_color": "#71C35C",
                    }
                ]
            },
            swamp_builder.huge_lily_pad_texture_entry(
                "huge_lily_pad",
                swamp_builder.HUGE_LILY_PAD_ITEM_TINT,
            ),
        )
        for quadrant in ("nw", "ne", "se", "sw"):
            texture_name = "huge_lily_pad_%s" % quadrant
            self.assertEqual(
                {
                    "textures": [
                        {
                            "path": "textures/blocks/%s" % texture_name,
                            "tint_color": "#208030",
                        }
                    ]
                },
                swamp_builder.huge_lily_pad_texture_entry(
                    texture_name,
                    swamp_builder.HUGE_LILY_PAD_WORLD_TINT,
                ),
            )

    def test_huge_lily_pad_texture_assets_use_fresh_cache_busting_stems(self):
        expected = {
            "huge_lily_pad": "huge_lily_pad_clean_v2",
            "huge_lily_pad_ne": "huge_lily_pad_ne_clean_v2",
            "huge_lily_pad_nw": "huge_lily_pad_nw_clean_v2",
            "huge_lily_pad_se": "huge_lily_pad_se_clean_v2",
            "huge_lily_pad_sw": "huge_lily_pad_sw_clean_v2",
        }

        self.assertEqual(
            expected,
            {
                block_id: swamp_builder.huge_lily_pad_texture_stem(block_id)
                for block_id in expected
            },
        )

    def test_huge_lily_pad_public_texture_rotates_upstream_notch_to_right(self):
        upstream = (
            ROOT.parent
            / "twilightforest-1.20.1-4.3.2508-extracted"
            / "00_original_tree"
            / "assets"
            / "twilightforest"
            / "textures"
            / "block"
            / "huge_lily_pad.png"
        )
        with Image.open(upstream) as source:
            source_rgba = source.convert("RGBA")

        rotated = swamp_builder.huge_lily_pad_public_image(source_rgba)
        expected = source_rgba.transpose(Image.Transpose.ROTATE_270)

        self.assertIsNone(ImageChops.difference(rotated, expected).getbbox())
        self.assertEqual(0, rotated.getpixel((31, 15))[3])
        self.assertGreater(rotated.getpixel((24, 8))[3], 0)
        self.assertGreater(rotated.getpixel((28, 20))[3], 0)

    def test_huge_lily_pad_preflights_all_nine_cells_before_placing(self):
        documents, clearances = swamp_builder.huge_lily_pad_clearance_documents(
            ["minecraft:water", "minecraft:flowing_water"])
        self.assertEqual(10, len(documents))
        self.assertEqual(9, len(clearances))
        clearance = documents[
            "huge_lily_pad_clearance_block_feature.json"
        ]["minecraft:single_block_feature"]
        self.assertEqual(
            [{"block": "minecraft:air", "weight": 1}],
            clearance["places_block"],
        )
        self.assertEqual(
            ["minecraft:water", "minecraft:flowing_water"],
            clearance["may_attach_to"]["bottom"],
        )
        sequence = swamp_builder.huge_lily_pad_single_sequence_document(
            "huge_lily_pad_2x2_feature", clearances
        )["minecraft:sequence_feature"]
        self.assertEqual(
            ["tf_slice:%s" % name for name in clearances]
            + ["tf_slice:huge_lily_pad_feature"],
            sequence["features"],
        )

    def test_huge_lily_pad_places_each_facing_as_one_atomic_structure(self):
        expected_layouts = {
            "north": {
                (0, 0): "nw",
                (1, 0): "ne",
                (1, 1): "se",
                (0, 1): "sw",
            },
            "east": {
                (1, 0): "nw",
                (1, 1): "ne",
                (0, 1): "se",
                (0, 0): "sw",
            },
            "south": {
                (1, 1): "nw",
                (0, 1): "ne",
                (0, 0): "se",
                (1, 0): "sw",
            },
            "west": {
                (0, 1): "nw",
                (0, 0): "ne",
                (1, 0): "se",
                (1, 1): "sw",
            },
        }
        clearance = [
            "huge_lily_pad_clearance_%s_position_feature" % quadrant
            for quadrant in ("nw", "ne", "se", "sw")
        ]
        for facing, expected_layout in expected_layouts.items():
            structure = swamp_builder.huge_lily_pad_structure(facing)
            self.assertEqual((2, 1, 2), structure.size)
            self.assertEqual(4, len(structure.blocks))
            for (x, z), quadrant in expected_layout.items():
                block = structure.blocks[(x, 0, z)]
                self.assertEqual(
                    "tf_slice:huge_lily_pad_%s" % quadrant,
                    block[0],
                )
                self.assertEqual(
                    {"tf_slice:facing": facing},
                    block[1],
                )

            feature_id = "huge_lily_pad_%s_structure_feature" % facing
            structure_name = "tf_slice:swamp/huge_lily_pad/%s" % facing
            feature = swamp_builder.huge_lily_pad_structure_feature_document(
                feature_id,
                structure_name,
            )["minecraft:structure_template_feature"]
            self.assertEqual(structure_name, feature["structure_name"])
            self.assertEqual(0, feature["adjustment_radius"])
            self.assertEqual("north", feature["facing_direction"])
            self.assertEqual(
                {"block_allowlist": ["minecraft:air"]},
                feature["constraints"]["block_intersection"],
            )

            sequence_id = (
                "huge_lily_pad_2x2_feature"
                if facing == "north"
                else "huge_lily_pad_2x2_%s_feature" % facing
            )
            sequence = swamp_builder.huge_lily_pad_atomic_sequence_document(
                sequence_id,
                clearance,
                feature_id,
            )["minecraft:sequence_feature"]
            self.assertEqual(
                ["tf_slice:%s" % item for item in clearance]
                + ["tf_slice:%s" % feature_id],
                sequence["features"],
            )

    def test_huge_lily_pad_geometry_meets_netease_runtime_bounds(self):
        geometries = read_json(
            RP / "models" / "blocks" / "swamp_plants.geo.json"
        )["minecraft:geometry"]
        pad_geometries = [
            geometry for geometry in geometries
            if geometry["description"]["identifier"] in {
                "geometry.tf_slice.huge_lily_pad_item",
                "geometry.tf_slice.huge_lily_pad_quadrant",
            }
        ]
        self.assertEqual(2, len(pad_geometries))
        cubes = [
            cube for geometry in pad_geometries
            for bone in geometry["bones"]
            for cube in bone.get("cubes", [])
        ]

        self.assertTrue(cubes)
        for cube in cubes:
            self.assertGreaterEqual(
                float(cube["size"][1]),
                1.0,
                "NetEase rejects horizontal block geometry thinner than 1/16 block",
            )
            minimum = [
                (float(origin) + 8.0) / 16.0
                for origin in cube["origin"]
            ]
            maximum = [
                minimum[index] + float(cube["size"][index]) / 16.0
                for index in range(3)
            ]
            self.assertTrue(
                all(value >= -0.875 for value in minimum),
                "NetEase rejects custom block geometry below its error bounds",
            )
            self.assertTrue(
                all(value <= 1.875 for value in maximum),
                "NetEase rejects custom block geometry above its error bounds",
            )

    def test_huge_lily_pad_quadrants_reassemble_for_every_facing(self):
        geometries = swamp_builder.swamp_plant_geometry()["minecraft:geometry"]
        quadrant = next(
            geometry for geometry in geometries
            if geometry["description"]["identifier"]
            == "geometry.tf_slice.huge_lily_pad_quadrant"
        )
        up_face = quadrant["bones"][0]["cubes"][0]["uv"]["up"]

        self.assertEqual([0, 0], up_face["uv"])
        self.assertEqual([16, 16], up_face["uv_size"])
        self.assertNotIn("down", quadrant["bones"][0]["cubes"][0]["uv"])

        positions = {
            "nw": (0, 0),
            "ne": (16, 0),
            "sw": (0, 16),
            "se": (16, 16),
        }
        upstream = (
            ROOT.parent
            / "twilightforest-1.20.1-4.3.2508-extracted"
            / "00_original_tree"
            / "assets"
            / "twilightforest"
            / "textures"
            / "block"
        )
        with Image.open(upstream / "huge_lily_pad.png") as source:
            north_leaf = source.convert("RGBA")
        quadrant_images = swamp_builder.huge_lily_pad_quadrant_images(
            north_leaf
        )
        self.assertEqual(
            {"nw", "ne", "se", "sw"},
            set(quadrant_images),
        )

        block = swamp_builder.lily_quadrant_block("huge_lily_pad_nw")
        permutations = block["minecraft:block"]["permutations"]
        facings = ("north", "east", "south", "west")
        for turns, (facing, permutation) in enumerate(
            zip(facings, permutations)
        ):
            rotation = permutation["components"]["minecraft:transformation"][
                "rotation"
            ][1]
            assembled = Image.new("RGBA", (32, 32))
            for quadrant_name, source_position in positions.items():
                rendered = quadrant_images[quadrant_name].transpose(
                    Image.Transpose.FLIP_LEFT_RIGHT
                )
                rendered = rendered.rotate(rotation)

                x, z = (value // 16 for value in source_position)
                for unused in range(turns):
                    x, z = 1 - z, x
                assembled.paste(rendered, (x * 16, z * 16))

            expected = north_leaf.rotate(-90 * turns)
            self.assertIsNone(
                ImageChops.difference(assembled, expected).getbbox(),
                facing,
            )

    def test_huge_lily_pad_uses_runtime_safe_rotated_quadrants(self):
        cluster = read_json(
            BP / "netease_features" / "huge_lily_pad_cluster_feature.json"
        )["minecraft:scatter_feature"]
        self.assertEqual(1, cluster["distribution"]["iterations"])
        self.assertTrue(cluster["project_input_to_floor"])
        self.assertEqual(
            "tf_slice:huge_lily_pad_water_search_feature",
            cluster["places_feature"],
        )
        search = read_json(
            BP
            / "netease_features"
            / "huge_lily_pad_water_search_feature.json"
        )["minecraft:search_feature"]
        self.assertEqual([0, -2, 0], search["search_volume"]["min"])
        self.assertEqual([0, 8, 0], search["search_volume"]["max"])
        self.assertEqual("-y", search["search_axis"])
        self.assertEqual(
            "tf_slice:huge_lily_pad_rotation_selector_feature",
            search["places_feature"],
        )
        selector = read_json(
            BP
            / "netease_features"
            / "huge_lily_pad_rotation_selector_feature.json"
        )["minecraft:weighted_random_feature"]
        self.assertEqual(
            {"tf_slice:huge_lily_pad_2x2_feature"},
            {entry[0] for entry in selector["features"]},
        )
        rule = feature_rule("huge_lily_pad_feature_rule")
        self.assertEqual(
            "math.random(0, 1) < 0.5 ? 1 : 0",
            rule["distribution"]["iterations"],
        )
        self.assertEqual(
            "(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64",
            rule["distribution"]["y"],
        )

        block_document = read_json(
            BP / "netease_blocks" / "huge_lily_pad.json"
        )
        self.assertEqual("1.20.60", block_document["format_version"])
        components = block_document["minecraft:block"]["components"]
        self.assertEqual(
            "geometry.tf_slice.huge_lily_pad_item",
            components["minecraft:geometry"],
        )
        self.assertIn("*", components["minecraft:material_instances"])
        self.assertTrue(components["netease:pathable"]["value"])
        pad_bounds = {
            "min": [0.0, 0.0, 0.0],
            "max": [1.875, 0.0625, 1.875],
        }
        self.assertEqual(
            {"collision": pad_bounds, "clip": pad_bounds},
            components["netease:aabb"],
        )

        geometries = read_json(
            RP / "models" / "blocks" / "swamp_plants.geo.json"
        )["minecraft:geometry"]
        geometry = next(
            item
            for item in geometries
            if item["description"]["identifier"]
            == "geometry.tf_slice.huge_lily_pad_item"
        )
        self.assertEqual(32, geometry["description"]["texture_width"])
        self.assertEqual(32, geometry["description"]["texture_height"])
        self.assertEqual(
            [30, 1, 30],
            geometry["bones"][0]["cubes"][0]["size"],
        )
        self.assertEqual(
            [-8, 0, -8],
            geometry["bones"][0]["cubes"][0]["origin"],
        )

    def test_huge_water_lily_has_a_complete_natural_generation_path(self):
        patch = read_json(
            BP / "netease_features" / "huge_water_lily_patch_feature.json"
        )["minecraft:scatter_feature"]
        self.assertEqual(5, patch["distribution"]["iterations"])
        self.assertTrue(patch["project_input_to_floor"])
        self.assertEqual(
            "tf_slice:huge_water_lily_water_search_feature",
            patch["places_feature"],
        )
        search = read_json(
            BP
            / "netease_features"
            / "huge_water_lily_water_search_feature.json"
        )["minecraft:search_feature"]
        self.assertEqual([0, -2, 0], search["search_volume"]["min"])
        self.assertEqual([0, 8, 0], search["search_volume"]["max"])
        self.assertEqual(
            "tf_slice:huge_water_lily_feature", search["places_feature"]
        )
        rule = feature_rule("huge_water_lily_feature_rule")
        self.assertEqual(
            "math.random(0, 1) < 0.04 ? 1 : 0",
            rule["distribution"]["iterations"],
        )
        self.assertEqual(
            "(query.get_height_at(variable.worldx, variable.worldz) + 1) + 64",
            rule["distribution"]["y"],
        )

    def test_swamp_restores_vanilla_water_and_bank_plants(self):
        for name in (
            "swamp_waterlily_feature_rule",
            "swamp_sugar_cane_feature_rule",
            "swamp_vines_feature_rule",
            "swamp_dead_bush_feature_rule",
        ):
            rule = feature_rule(name)
            encoded = json.dumps(rule)
            self.assertIn("tf_slice_biome_swamp", encoded)
            self.assertIn("dm33027004", encoded)

        waterlily_patch = read_json(
            BP / "netease_features" / "swamp_waterlily_patch_feature.json"
        )["minecraft:scatter_feature"]
        self.assertTrue(waterlily_patch["project_input_to_floor"])
        self.assertEqual(
            "tf_slice:swamp_waterlily_water_search_feature",
            waterlily_patch["places_feature"],
        )
        waterlily_search = read_json(
            BP
            / "netease_features"
            / "swamp_waterlily_water_search_feature.json"
        )["minecraft:search_feature"]
        self.assertEqual([0, -2, 0], waterlily_search["search_volume"]["min"])
        self.assertEqual([0, 8, 0], waterlily_search["search_volume"]["max"])

        sugar_cane = read_json(
            BP / "netease_features" / "swamp_sugar_cane_feature.json"
        )["minecraft:single_block_feature"]
        self.assertEqual(
            [{"block": "minecraft:reeds", "weight": 1}],
            sugar_cane["places_block"],
        )

    def test_release_validator_rejects_item_only_sugar_cane_block_id(self):
        from tools import validate_slice

        gate = validate_slice.Gate()
        documents = validate_slice.collect_json(gate)
        feature_path = (
            BP / "netease_features" / "swamp_sugar_cane_feature.json"
        )
        broken_feature = json.loads(json.dumps(documents[feature_path]))
        broken_feature["minecraft:single_block_feature"]["places_block"] = [
            {"block": "minecraft:sugar_cane", "weight": 1}
        ]
        documents[feature_path] = broken_feature

        validate_slice.validate_runtime_log_compatibility(gate, documents)

        self.assertTrue(
            any(
                "minecraft:sugar_cane" in failure
                for failure in gate.failures
            ),
            gate.failures,
        )


class FireSwampDensityContractTests(unittest.TestCase):
    def test_fire_jets_and_smokers_restore_four_source_candidates_per_chunk(self):
        for kind in ("jet", "smoker"):
            rule = feature_rule("fire_swamp_%s_feature_rule" % kind)
            self.assertEqual(
                4,
                base_iterations(rule["distribution"]["iterations"]),
            )


if __name__ == "__main__":
    unittest.main()
