# -*- coding: utf-8 -*-
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog
from TwilightBossSlice import ruin_worldgen_logic as ruin_logic
from tools import build_ruin_structures as ruin_builder
from tests.test_structure_worldgen_handoff import FakeFactory, SERVICE


CARDINAL_CELL_OFFSETS = ((-1, 0), (0, -1), (0, 1), (1, 0))
CARDINAL_BLOCK_OFFSETS = (
    (-256, 0),
    (0, -256),
    (0, 256),
    (256, 0),
)
OUTER_MASK_SAMPLE_REGIONS = tuple(
    (region_x, region_z)
    for region_x in range(-4, 4)
    for region_z in range(-4, 4)
)


def feature_rule(mode):
    path = (
        BP
        / "netease_feature_rules"
        / ("ruin_landmark_surface_%s_feature_rule.json" % mode)
    )
    return json.loads(path.read_text(encoding="utf-8"))[
        "minecraft:feature_rules"
    ]


def cells_in_boxes(boxes):
    cells = set()
    for min_x, min_z, max_x, max_z in boxes:
        cells.update(
            (x, z)
            for x in range(int(min_x), int(max_x))
            for z in range(int(min_z), int(max_z))
        )
    return cells


def connected_component_count(cells):
    remaining = set(cells)
    components = 0
    while remaining:
        components += 1
        pending = [remaining.pop()]
        while pending:
            x, z = pending.pop()
            for neighbor in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
    return components


def enclosed_hole_count(cells):
    min_x = min(x for x, _ in cells) - 1
    max_x = max(x for x, _ in cells) + 1
    min_z = min(z for _, z in cells) - 1
    max_z = max(z for _, z in cells) + 1
    outside = {(min_x, min_z)}
    pending = [(min_x, min_z)]
    while pending:
        x, z = pending.pop()
        for neighbor in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
            if (
                min_x <= neighbor[0] <= max_x
                and min_z <= neighbor[1] <= max_z
                and neighbor not in cells
                and neighbor not in outside
            ):
                outside.add(neighbor)
                pending.append(neighbor)
    return sum(
        (x, z) not in cells and (x, z) not in outside
        for x in range(min_x, max_x + 1)
        for z in range(min_z, max_z + 1)
    )


def radial_sector_radii(cells, origin, sector_count=16):
    sectors = [[] for _ in range(sector_count)]
    sector_width = math.tau / float(sector_count)
    for x, z in cells:
        delta_x = x - origin[0]
        delta_z = z - origin[1]
        angle = (math.atan2(delta_z, delta_x) + math.tau) % math.tau
        sector = int((angle + sector_width / 2.0) / sector_width) % sector_count
        sectors[sector].append(math.hypot(delta_x, delta_z))
    return [max(sector) for sector in sectors]


class OriginalRouteTerritoryContractTests(unittest.TestCase):
    def test_shared_route_layout_has_one_main_and_four_cardinal_companions(self):
        self.assertEqual(
            CARDINAL_BLOCK_OFFSETS,
            ruin_logic.ROUTE_LANDMARK_CARDINAL_OFFSETS,
        )
        self.assertEqual(
            (
                (8, 8),
                (-248, 8),
                (8, -248),
                (8, 264),
                (264, 8),
            ),
            ruin_logic.route_landmark_centers(8, 8),
        )

    def test_upstream_macro_has_one_fire_and_one_dark_route_per_map(self):
        self.assertEqual(1, biome_catalog.ROUTE_BIOME_SOURCE_CELL_BLOCKS)
        self.assertEqual(4, biome_catalog.ROUTE_BIOME_COORDINATE_SCALE)
        self.assertEqual(1, biome_catalog.ROUTE_BIOME_SEED_CELL_SPAN)
        self.assertEqual(64, biome_catalog.ROUTE_BIOME_COORDINATE_BLOCKS)
        self.assertEqual(64, biome_catalog.ROUTE_BIOME_SEED_BLOCKS)
        self.assertEqual(256, biome_catalog.ROUTE_BIOME_CELL_BLOCKS)
        self.assertEqual(32, biome_catalog.ROUTE_BIOME_REGION_CELLS)
        self.assertEqual(
            2048,
            biome_catalog.ROUTE_BIOME_REGION_CELLS
            * biome_catalog.ROUTE_BIOME_COORDINATE_BLOCKS,
        )
        expected = {
            0: {
                "fire_swamp": (2, 2),
                "dark_forest_center": (6, 2),
            },
            1: {
                "fire_swamp": (6, 2),
                "dark_forest_center": (6, 6),
            },
            2: {
                "fire_swamp": (6, 6),
                "dark_forest_center": (2, 6),
            },
            3: {
                "fire_swamp": (2, 6),
                "dark_forest_center": (2, 2),
            },
        }
        self.assertEqual(expected, biome_catalog.ROUTE_CORE_LOCALS_BY_VARIANT)
        self.assertEqual(
            {
                0: {
                    "fire_swamp": (8, 8, 9, 9),
                    "dark_forest_center": (24, 8, 25, 9),
                },
                1: {
                    "fire_swamp": (24, 8, 25, 9),
                    "dark_forest_center": (24, 24, 25, 25),
                },
                2: {
                    "fire_swamp": (24, 24, 25, 25),
                    "dark_forest_center": (8, 24, 9, 25),
                },
                3: {
                    "fire_swamp": (8, 24, 9, 25),
                    "dark_forest_center": (8, 8, 9, 9),
                },
            },
            biome_catalog.ROUTE_CORE_SEED_BOXES_BY_VARIANT,
        )
        route_distances = []
        for variant, routes in expected.items():
            self.assertEqual(2, len(set(routes.values())))
            delta_x = (
                routes["fire_swamp"][0]
                - routes["dark_forest_center"][0]
            ) * biome_catalog.ROUTE_BIOME_CELL_BLOCKS
            delta_z = (
                routes["fire_swamp"][1]
                - routes["dark_forest_center"][1]
            ) * biome_catalog.ROUTE_BIOME_CELL_BLOCKS
            route_distances.append(int(round(math.hypot(delta_x, delta_z))))
            self.assertEqual(1024, route_distances[-1])
        self.assertEqual([1024, 1024, 1024, 1024], route_distances)

    def test_macro_layout_hash_is_balanced_and_not_a_fixed_checkerboard(self):
        counts = {variant: 0 for variant in (0, 1, 2, 3)}
        rows = []
        for region_z in range(-24, 24):
            row = []
            for region_x in range(-24, 24):
                variant = biome_catalog.route_layout_variant(region_x, region_z)
                self.assertIn(variant, counts)
                counts[variant] += 1
                row.append(variant)
            rows.append(row)

        total = float(sum(counts.values()))
        for variant in counts:
            self.assertGreaterEqual(counts[variant] / total, 0.24)
            self.assertLessEqual(counts[variant] / total, 0.26)
        self.assertEqual(4, len(set(tuple(row) for row in rows)))
        self.assertTrue(
            any(row[index] != row[index + 1] for row in rows for index in range(47))
        )

    def test_global_route_spacing_removes_the_2048_block_same_route_gap(self):
        period = (
            biome_catalog.ROUTE_BIOME_REGION_CELLS
            * biome_catalog.ROUTE_BIOME_COORDINATE_BLOCKS
        )
        local_scale = biome_catalog.ROUTE_BIOME_CELL_BLOCKS
        points = []
        for region_z in range(-8, 9):
            for region_x in range(-8, 9):
                variant = biome_catalog.route_layout_variant(region_x, region_z)
                for profile_id, (local_x, local_z) in (
                    biome_catalog.ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT[
                        variant
                    ].items()
                ):
                    route_key = biome_catalog.ACTIVE_TERRITORY_PROFILE_BY_ID[
                        profile_id
                    ]["coreBiome"]
                    points.append(
                        (
                            region_x * period + local_x * local_scale,
                            region_z * period + local_z * local_scale,
                            route_key,
                            region_x,
                            region_z,
                        )
                    )

        interior = [
            point
            for point in points
            if -5 <= point[3] <= 5 and -5 <= point[4] <= 5
        ]
        nearest_any = []
        nearest_same = []
        for point in interior:
            nearest_any.append(
                min(
                    math.hypot(point[0] - other[0], point[1] - other[1])
                    for other in points
                    if other != point
                )
            )
            nearest_same.append(
                min(
                    math.hypot(point[0] - other[0], point[1] - other[1])
                    for other in points
                    if other != point and other[2] == point[2]
                )
            )

        self.assertEqual({1024.0}, set(nearest_any))
        self.assertEqual({1024.0}, set(nearest_same))
        self.assertNotIn(2048.0, nearest_same)
        self.assertEqual(
            432,
            1024 - biome_catalog.ROUTE_OUTER_MAX_ENVELOPE_BLOCKS,
        )
        self.assertLessEqual(
            max(nearest_same) - biome_catalog.ROUTE_OUTER_MAX_ENVELOPE_BLOCKS,
            432,
        )

    def test_upstream_route_stabilize_runs_between_two_zoom_groups(self):
        self.assertEqual(
            ("vanilla_zoom_2x",),
            biome_catalog.PRE_KEY_LAND_ZOOM_STAGES,
        )
        self.assertEqual(
            ("vanilla_zoom_2x",) * 2,
            biome_catalog.ROUTE_PRE_STABILIZE_ZOOM_STAGES,
        )
        self.assertEqual(
            ("vanilla_zoom_2x",) * 4,
            biome_catalog.FINAL_LAND_ZOOM_STAGES,
        )
        document = __import__(
            "tools.build_dark_forest_biomes",
            fromlist=["dimension_document"],
        ).dimension_document()
        source = document["netease:dimension_info"]["components"][
            "netease:biome_source"
        ]
        zoom_indexes = [
            index
            for index, stage in enumerate(source)
            if stage["type"] in ("fuzzy_zoom_2x", "vanilla_zoom_2x")
        ]
        condition_indexes = [
            index
            for index, stage in enumerate(source)
            if stage["type"] == "condition"
        ]
        self.assertEqual(7, len(zoom_indexes))
        self.assertEqual(8, len(condition_indexes))
        self.assertEqual([1], zoom_indexes[:1])
        self.assertEqual([2, 3, 4, 5], condition_indexes[:4])
        self.assertEqual([6, 7], zoom_indexes[1:3])
        self.assertEqual([8, 9, 10, 11], condition_indexes[4:])
        self.assertEqual([12, 13, 14, 15], zoom_indexes[3:])

        condition_text = "".join(
            stage["condition"]
            for stage in source
            if stage["type"] == "condition"
        )
        self.assertNotIn("get_neighborhood_is_biome", condition_text)
        self.assertEqual(
            4,
            sum(
                "math.sin" in source[index]["condition"]
                for index in (8, 9, 10, 11)
            ),
        )
        self.assertFalse(
            any("math.sin" in source[index]["condition"] for index in range(2, 6))
        )
        self.assertLess(len(condition_text), 90000)

    def test_route_stabilize_gives_every_center_a_128_block_territory(self):
        self.assertEqual(128, biome_catalog.ROUTE_STABILIZE_REGION_CELLS)
        self.assertEqual(16, biome_catalog.ROUTE_STABILIZE_CELL_BLOCKS)
        self.assertEqual(128, biome_catalog.ROUTE_STABLE_INTERIOR_BLOCKS)
        self.assertEqual(128, biome_catalog.ROUTE_EFFECTIVE_TERRITORY_BLOCKS)
        for variant, routes in biome_catalog.ROUTE_CORE_LOCALS_BY_VARIANT.items():
            for route_key, core_local in routes.items():
                core_mask = biome_catalog.ROUTE_STABLE_CORE_MASKS_BY_VARIANT[
                    variant
                ][route_key]
                companion_mask = (
                    biome_catalog.ROUTE_STABLE_COMPANION_MASKS_BY_VARIANT[
                        variant
                    ][route_key]
                )
                expected_origin = (
                    core_local[0]
                    * biome_catalog.ROUTE_BIOME_COORDINATE_SCALE
                    * biome_catalog.ROUTE_STABILIZE_SCALE,
                    core_local[1]
                    * biome_catalog.ROUTE_BIOME_COORDINATE_SCALE
                    * biome_catalog.ROUTE_STABILIZE_SCALE,
                )
                self.assertEqual(expected_origin, core_mask)
                self.assertEqual(expected_origin, companion_mask)
                self.assertEqual(
                    {
                        (
                            core_local[0] + offset_x,
                            core_local[1] + offset_z,
                        )
                        for offset_x, offset_z in CARDINAL_CELL_OFFSETS
                    },
                    set(
                        biome_catalog.ROUTE_COMPANION_LOCALS_BY_VARIANT[
                            variant
                        ][route_key]
                    ),
                )

    def test_outer_companion_mask_is_compact_irregular_and_not_a_cross(self):
        self.assertEqual(
            285.0,
            biome_catalog.ROUTE_OUTER_RADIUS_SQUARED_BASE,
        )
        self.assertEqual(
            291.5,
            biome_catalog.ROUTE_OUTER_RADIUS_SQUARED_FLOOR,
        )
        self.assertAlmostEqual(
            80.0,
            sum(
                abs(value[0])
                for value in biome_catalog.ROUTE_OUTER_RADIUS_WAVES
            ),
        )
        self.assertEqual(19, biome_catalog.ROUTE_OUTER_COARSE_RADIUS_CELLS)
        self.assertEqual(1, biome_catalog.ROUTE_ANCHOR_SAFE_MARGIN_CELLS)
        self.assertEqual(592, biome_catalog.ROUTE_OUTER_MAX_ENVELOPE_BLOCKS)
        self.assertEqual(
            {"fire_swamp": 0, "dark_forest_center": 180},
            biome_catalog.ROUTE_OUTER_PHASE_OFFSET_BY_KEY,
        )
        center_scale = (
            biome_catalog.ROUTE_BIOME_COORDINATE_SCALE
            * biome_catalog.ROUTE_STABILIZE_SCALE
        )
        for region_x, region_z in OUTER_MASK_SAMPLE_REGIONS:
            variant = biome_catalog.route_layout_variant(region_x, region_z)
            relative_by_route = {}
            for route_key, core_local in (
                biome_catalog.ROUTE_CORE_LOCALS_BY_VARIANT[variant].items()
            ):
                companion_mask = (
                    biome_catalog.ROUTE_STABLE_COMPANION_MASKS_BY_VARIANT[
                        variant
                    ][route_key]
                )
                outer_cells = {
                    (x, z)
                    for x in range(biome_catalog.ROUTE_STABILIZE_REGION_CELLS)
                    for z in range(biome_catalog.ROUTE_STABILIZE_REGION_CELLS)
                    if biome_catalog.route_companion_mask_contains(
                        region_x * biome_catalog.ROUTE_STABILIZE_REGION_CELLS + x,
                        region_z * biome_catalog.ROUTE_STABILIZE_REGION_CELLS + z,
                        companion_mask,
                        route_key,
                    )
                }
                self.assertEqual(1, connected_component_count(outer_cells))
                self.assertEqual(0, enclosed_hole_count(outer_cells))
                self.assertGreaterEqual(len(outer_cells), 880)
                self.assertLessEqual(len(outer_cells), 1000)

                core_origin = (
                    core_local[0] * center_scale,
                    core_local[1] * center_scale,
                )
                for offset_x, offset_z in ((0, 0),) + CARDINAL_CELL_OFFSETS:
                    anchor = (
                        core_origin[0] + offset_x * center_scale,
                        core_origin[1] + offset_z * center_scale,
                    )
                    self.assertIn(anchor, outer_cells)
                    if (offset_x, offset_z) != (0, 0):
                        for pad_x in range(-1, 2):
                            for pad_z in range(-1, 2):
                                self.assertIn(
                                    (anchor[0] + pad_x, anchor[1] + pad_z),
                                    outer_cells,
                                )
                for offset_x in (-1, 1):
                    for offset_z in (-1, 1):
                        self.assertNotIn(
                            (
                                core_origin[0] + offset_x * center_scale,
                                core_origin[1] + offset_z * center_scale,
                            ),
                            outer_cells,
                        )

                relative = {
                    (x - core_origin[0], z - core_origin[1])
                    for x, z in outer_cells
                }
                relative_by_route[route_key] = relative
                width = max(x for x, _ in relative) - min(x for x, _ in relative) + 1
                depth = max(z for _, z in relative) - min(z for _, z in relative) + 1
                self.assertIn(width, (35, 36, 37))
                self.assertIn(depth, (35, 36, 37))
                transforms = (
                    {(-x, z) for x, z in relative},
                    {(x, -z) for x, z in relative},
                    {(z, -x) for x, z in relative},
                )
                self.assertTrue(
                    all(len(relative.symmetric_difference(value)) >= 8 for value in transforms)
                )

                row_widths = {}
                for x, z in relative:
                    row_widths[z] = row_widths.get(z, 0) + 1
                self.assertGreaterEqual(len(set(row_widths.values())), 8)

                radial_radii = radial_sector_radii(outer_cells, core_origin)
                radial_mean = sum(radial_radii) / float(len(radial_radii))
                radial_stddev = math.sqrt(
                    sum((radius - radial_mean) ** 2 for radius in radial_radii)
                    / float(len(radial_radii))
                )
                radial_span = max(radial_radii) - min(radial_radii)
                cardinal_mean = sum(
                    radial_radii[index] for index in (0, 4, 8, 12)
                ) / 4.0
                diagonal_mean = sum(
                    radial_radii[index] for index in (2, 6, 10, 14)
                ) / 4.0
                self.assertGreaterEqual(radial_span, 0.2)
                self.assertLessEqual(radial_span, 4.0)
                self.assertGreaterEqual(radial_stddev, 0.05)
                self.assertLessEqual(radial_stddev, 1.25)
                self.assertLessEqual(abs(cardinal_mean - diagonal_mean), 2.0)

                eroded = {
                    (x, z)
                    for x, z in outer_cells
                    if all(
                        neighbor in outer_cells
                        for neighbor in (
                            (x - 1, z),
                            (x + 1, z),
                            (x, z - 1),
                            (x, z + 1),
                        )
                    )
                }
                self.assertEqual(1, connected_component_count(eroded))

                core_mask = biome_catalog.ROUTE_STABLE_CORE_MASKS_BY_VARIANT[
                    variant
                ][route_key]
                core_cells = {
                    (x, z)
                    for x in range(biome_catalog.ROUTE_STABILIZE_REGION_CELLS)
                    for z in range(biome_catalog.ROUTE_STABILIZE_REGION_CELLS)
                    if biome_catalog.route_core_mask_contains(
                        region_x * biome_catalog.ROUTE_STABILIZE_REGION_CELLS + x,
                        region_z * biome_catalog.ROUTE_STABILIZE_REGION_CELLS + z,
                        core_mask,
                        route_key,
                    )
                }
                self.assertGreaterEqual(len(core_cells), 145)
                self.assertLessEqual(len(core_cells), 165)
                self.assertGreaterEqual(len(core_cells) / float(len(outer_cells)), 0.145)
                self.assertLessEqual(len(core_cells) / float(len(outer_cells)), 0.18)

            self.assertGreaterEqual(
                len(
                    relative_by_route["fire_swamp"].symmetric_difference(
                        relative_by_route["dark_forest_center"]
                    )
                ),
                30,
            )

    def test_core_mask_is_connected_irregular_and_contains_the_zoomed_seed(self):
        self.assertEqual(48.5, biome_catalog.ROUTE_CORE_RADIUS_SQUARED_BASE)
        self.assertEqual(8, biome_catalog.ROUTE_CORE_COARSE_RADIUS_CELLS)
        self.assertEqual(1.25, biome_catalog.ROUTE_CORE_X_BIAS)
        self.assertEqual(-0.75, biome_catalog.ROUTE_CORE_Z_BIAS)
        self.assertAlmostEqual(
            8.4,
            sum(abs(value[0]) for value in biome_catalog.ROUTE_CORE_RADIUS_WAVES),
        )
        self.assertEqual(
            {"fire_swamp": 0, "dark_forest_center": 53},
            biome_catalog.ROUTE_CORE_PHASE_OFFSET_BY_KEY,
        )
        scale = biome_catalog.ROUTE_STABILIZE_SCALE
        for region_x, region_z in (
            (-4, -3),
            (-4, -2),
            (-3, 2),
            (-2, -4),
            (-2, -1),
            (-1, 1),
            (0, 0),
            (1, 0),
            (1, 2),
            (2, -2),
            (3, 3),
            (3, 1),
            (4, -1),
        ):
            variant = biome_catalog.route_layout_variant(region_x, region_z)
            for route_key, core_origin in (
                biome_catalog.ROUTE_STABLE_CORE_MASKS_BY_VARIANT[variant].items()
            ):
                core_cells = {
                    (x, z)
                    for x in range(biome_catalog.ROUTE_STABILIZE_REGION_CELLS)
                    for z in range(biome_catalog.ROUTE_STABILIZE_REGION_CELLS)
                    if biome_catalog.route_core_mask_contains(
                        region_x * biome_catalog.ROUTE_STABILIZE_REGION_CELLS + x,
                        region_z * biome_catalog.ROUTE_STABILIZE_REGION_CELLS + z,
                        core_origin,
                        route_key,
                    )
                }
                seed_box = biome_catalog.ROUTE_CORE_SEED_BOXES_BY_VARIANT[
                    variant
                ][route_key]
                seed_cells = {
                    (x, z)
                    for x in range(seed_box[0] * scale, seed_box[2] * scale)
                    for z in range(seed_box[1] * scale, seed_box[3] * scale)
                }
                final_core = core_cells | seed_cells
                self.assertEqual(1, connected_component_count(final_core))
                self.assertTrue(seed_cells.issubset(core_cells))
                self.assertGreaterEqual(len(final_core), 145)
                self.assertLessEqual(len(final_core), 165)
                min_x = min(x for x, _ in final_core)
                max_x = max(x for x, _ in final_core) + 1
                min_z = min(z for _, z in final_core)
                max_z = max(z for _, z in final_core) + 1
                self.assertGreaterEqual(max_x - min_x, 13)
                self.assertLessEqual(max_x - min_x, 15)
                self.assertGreaterEqual(max_z - min_z, 13)
                self.assertLessEqual(max_z - min_z, 15)
                self.assertLess(len(final_core), (max_x - min_x) * (max_z - min_z) - 4)

                relative = {
                    (x - core_origin[0], z - core_origin[1])
                    for x, z in final_core
                }
                self.assertGreaterEqual(
                    len(relative.symmetric_difference({(-x, z) for x, z in relative})),
                    15,
                )

    def test_each_route_seed_is_one_connected_core_plus_four_companions(self):
        for variant, routes in biome_catalog.ROUTE_CORE_LOCALS_BY_VARIANT.items():
            for route_key, core in routes.items():
                companions = set(
                    biome_catalog.ROUTE_COMPANION_LOCALS_BY_VARIANT[
                        variant
                    ][route_key]
                )
                territory = companions | {core}
                self.assertEqual(5, len(territory))
                self.assertEqual(
                    {
                        (core[0] + offset_x, core[1] + offset_z)
                        for offset_x, offset_z in CARDINAL_CELL_OFFSETS
                    },
                    companions,
                )

    def test_companion_domain_fits_all_four_source_scale_structures(self):
        coordinate_width = biome_catalog.ROUTE_BIOME_COORDINATE_BLOCKS
        companion_offsets = tuple(
            (
                (local_x - biome_catalog.ROUTE_BIOME_CORE_LOCAL[0])
                * biome_catalog.ROUTE_BIOME_COORDINATE_SCALE
                * coordinate_width,
                (local_z - biome_catalog.ROUTE_BIOME_CORE_LOCAL[1])
                * biome_catalog.ROUTE_BIOME_COORDINATE_SCALE
                * coordinate_width,
            )
            for local_x, local_z in (
                biome_catalog.ROUTE_BIOME_COMPANION_ANCHOR_LOCALS
            )
        )
        period = (
            biome_catalog.ROUTE_BIOME_REGION_CELLS * coordinate_width
        )
        landmark_width = biome_catalog.ROUTE_STABLE_INTERIOR_BLOCKS
        outer_width = biome_catalog.ROUTE_OUTER_MAX_ENVELOPE_BLOCKS

        self.assertEqual(
            CARDINAL_BLOCK_OFFSETS,
            companion_offsets,
        )
        self.assertGreaterEqual(landmark_width, 112)
        self.assertEqual(592, outer_width)
        self.assertGreaterEqual(period - outer_width, 64)

    def test_both_companion_modes_gate_on_the_same_four_core_offsets(self):
        expected_core_types = {
            "swamp": (134,),
            "dark_forest": (160,),
        }
        self.assertEqual(
            expected_core_types,
            ruin_builder.ROUTE_COMPANION_MODE_CORE_TYPES,
        )

        for mode, core_types in expected_core_types.items():
            expression = ruin_builder._surface_mode_biome_expression(
                mode,
                "region_x",
                "region_z",
                ruin_builder.SURFACE_LANDMARK_BIOME_TYPES[mode],
            )
            self.assertEqual(5, expression.count("query.is_biome"), expression)
            self.assertIn(
                ruin_builder._biome_sample_expression(
                    "region_x",
                    "region_z",
                    ruin_builder.SURFACE_LANDMARK_BIOME_TYPES[mode],
                ),
                expression,
            )
            for offset_x, offset_z in CARDINAL_BLOCK_OFFSETS:
                self.assertIn(
                    ruin_builder._biome_sample_expression(
                        ruin_builder._molang_offset("region_x", offset_x),
                        ruin_builder._molang_offset("region_z", offset_z),
                        core_types,
                    ),
                    expression,
                )

    def test_generated_companion_rules_preserve_all_four_core_samples(self):
        for mode in ("swamp", "dark_forest"):
            iterations = str(feature_rule(mode)["distribution"]["iterations"])
            self.assertEqual(5, iterations.count("query.is_biome"), iterations)
            self.assertIn("- 256", iterations)
            self.assertIn("+ 256", iterations)

    def test_magic_map_uses_the_same_main_and_cardinal_centers(self):
        cases = (
            (
                "dm33027004_swampland_mutated",
                "dm33027004_swampland",
                "hydra_lair",
                "labyrinth",
            ),
            (
                "dm33027004_redwood_taiga_mutated",
                "dm33027004_roofed_forest_mutated",
                "dark_tower",
                "knight_stronghold",
            ),
        )
        core_center = ruin_logic.nearest_route_landmark_center(0, 0)
        self.assertEqual((8, 8), core_center)
        cardinal_centers = ruin_logic.route_landmark_centers(*core_center)[1:]
        diagonal_center = (core_center[0] + 256, core_center[1] - 256)

        for core_biome, companion_biome, main_kind, companion_kind in cases:
            factory = FakeFactory()

            core_positions = {core_center}
            companion_positions = set(cardinal_centers)
            disconnected_positions = {diagonal_center}

            def biome_name(position, _dimension_id):
                sample = (int(position[0]), int(position[2]))
                if sample in core_positions:
                    return core_biome
                if sample in companion_positions or sample in disconnected_positions:
                    return companion_biome
                return "dm33027004_plains"

            factory.biome.GetBiomeName = biome_name
            service = SERVICE.StructureWorldgenService(
                factory,
                "level",
                33027004,
            )

            self.assertEqual(
                main_kind,
                service._magic_map_kind_at_center(*core_center),
            )
            self.assertEqual(
                [companion_kind] * 4,
                [
                    service._magic_map_kind_at_center(*center)
                    for center in cardinal_centers
                ],
            )
            self.assertIsNone(
                service._magic_map_kind_at_center(*diagonal_center)
            )

    def test_magic_map_emits_exactly_one_plus_four_at_nominal_centers(self):
        core = ruin_logic.nearest_route_landmark_center(0, 0)
        territory = set(ruin_logic.route_landmark_centers(*core))
        companions = territory - {core}
        diagonal = (core[0] + 256, core[1] + 256)
        factory = FakeFactory()

        def biome_name(position, _dimension_id):
            sample = (int(position[0]), int(position[2]))
            if sample == core:
                return "dm33027004_swampland_mutated"
            if sample in companions or sample == diagonal:
                return "dm33027004_swampland"
            return "dm33027004_plains"

        factory.biome.GetBiomeName = biome_name
        service = SERVICE.StructureWorldgenService(
            factory,
            "level",
            33027004,
        )
        landmarks = service.magic_map_landmarks_near(
            [core[0], 64, core[1]],
            core[0],
            core[1],
            400,
        )
        route_markers = [
            marker
            for marker in landmarks
            if marker["kind"] in ("hydra_lair", "labyrinth")
        ]

        self.assertEqual(5, len(route_markers))
        self.assertEqual(
            territory,
            {tuple(marker["position"]) for marker in route_markers},
        )
        self.assertEqual(
            {"hydra_lair": 1, "labyrinth": 4},
            {
                kind: sum(marker["kind"] == kind for marker in route_markers)
                for kind in ("hydra_lair", "labyrinth")
            },
        )
        self.assertNotIn(diagonal, territory)


if __name__ == "__main__":
    unittest.main()
