# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_phantom_urghast_structures as route_builder
from tools import build_ruin_structures as ruin_builder
from tools import knight_stronghold_legacy_port as stronghold_port


def catalog_entries():
    document = json.loads(
        (
            BP
            / "structures"
            / "tf_slice"
            / "ruins"
            / "structure_catalog_v1.json"
        ).read_text(encoding="utf-8")
    )
    return {entry["id"]: entry for entry in document["structures"]}


class DarkForestLandmarkWorldgenContractTests(unittest.TestCase):
    def test_stronghold_gate_matches_the_magic_map_dark_forest_mapping(self):
        region_x = "region_x"
        region_z = "region_z"
        center_gate = ruin_builder._surface_mode_biome_expression(
            "dark_forest_center",
            region_x,
            region_z,
            (160,),
        )
        stronghold_gate = ruin_builder._surface_mode_biome_expression(
            "dark_forest",
            region_x,
            region_z,
            (157,),
        )

        self.assertEqual(1, center_gate.count("query.is_biome"))
        self.assertEqual(5, stronghold_gate.count("query.is_biome"))
        self.assertIn(
            "query.is_biome(region_x, region_z, 157)",
            stronghold_gate,
        )
        self.assertIn("160", stronghold_gate)
        self.assertIn("region_x - 256", stronghold_gate)
        self.assertIn("region_z - 256", stronghold_gate)
        self.assertIn("region_x + 256", stronghold_gate)
        self.assertIn("region_z + 256", stronghold_gate)

    def test_dark_forest_modes_have_bounded_native_surface_triggers(self):
        self.assertEqual(
            (157,), ruin_builder.SURFACE_LANDMARK_BIOME_TYPES["dark_forest"]
        )
        self.assertEqual(
            (160,),
            ruin_builder.SURFACE_LANDMARK_BIOME_TYPES["dark_forest_center"],
        )
        self.assertEqual(
            5,
            ruin_builder.SURFACE_LANDMARK_TILE_RADIUS_CHUNKS["dark_forest"],
        )
        self.assertEqual(
            3,
            ruin_builder.SURFACE_LANDMARK_TILE_RADIUS_CHUNKS[
                "dark_forest_center"
            ],
        )
        self.assertIn(
            "dark_forest",
            ruin_builder.ROUTE_COMPANION_MODE_CORE_TYPES,
        )

        stronghold_rule = json.loads(
            (
                BP
                / "netease_feature_rules"
                / "ruin_landmark_surface_dark_forest_feature_rule.json"
            ).read_text(encoding="utf-8")
        )["minecraft:feature_rules"]
        self.assertEqual(
            (
                "query.get_height_at("
                "math.floor((variable.originx + 128) / 256) * 256 + 8, "
                "math.floor((variable.originz + 128) / 256) * 256 + 8) - %d"
                % (route_builder.STRONGHOLD_ENTRY_Y + 1)
            ),
            stronghold_rule["distribution"]["y"],
        )
        tower_rule = json.loads(
            (
                BP
                / "netease_feature_rules"
                / "ruin_landmark_surface_dark_forest_center_feature_rule.json"
            ).read_text(encoding="utf-8")
        )["minecraft:feature_rules"]
        stronghold_iterations = stronghold_rule["distribution"][
            "iterations"
        ]
        self.assertEqual(5, stronghold_iterations.count("query.is_biome"))
        self.assertIn(", 160)", stronghold_iterations)
        self.assertEqual(
            1,
            tower_rule["distribution"]["iterations"].count(
                "query.is_biome"
            ),
        )
        tower_y = tower_rule["distribution"]["y"]
        self.assertTrue(
            tower_y.endswith(
                " - %d" % (route_builder.STRONGHOLD_ENTRY_Y + 1)
            ),
            tower_y,
        )
        self.assertFalse(
            tower_y.endswith(" - %d" % ruin_builder.SURFACE_NATIVE_GROUND_Y),
            tower_y,
        )

    def test_route_landmarks_are_compiled_as_surface_pass_tiles(self):
        entries = catalog_entries()
        expected_ground_y = {
            "knight_stronghold": route_builder.STRONGHOLD_ENTRY_Y,
            # Both routes are swapped into the same Dark Forest surface
            # trigger, which is emitted at local Y=-52.  The Dark Tower keeps
            # its authored marker coordinates through originOffset=-16.
            "dark_tower": route_builder.STRONGHOLD_ENTRY_Y,
        }
        for kind, ground_y in expected_ground_y.items():
            variants = entries[kind]["variants"]
            self.assertEqual(8 if kind == "knight_stronghold" else 2, len(variants), kind)
            for variant in variants:
                surface = variant["surfaceNative"]
                self.assertEqual("surface_pass", surface["placementPass"])
                self.assertEqual(ground_y, surface["groundY"])
                self.assertFalse(
                    surface["terrainAdaptation"]["runtimeWrites"]
                )
                self.assertFalse(
                    surface["environmentIntegration"]["runtimeWrites"]
                )
                self.assertTrue(surface["centerAlignments"])
                self.assertTrue(
                    surface["prefix"].startswith(
                        "tf_slice/ruins/surface_native/%s/" % kind
                    )
                )
                if kind == "knight_stronghold":
                    entrance = variant["markers"]["surfaceEntrance"][
                        "offset"
                    ]
                    self.assertEqual(
                        [0, 0],
                        [
                            int(surface["originOffset"][0])
                            + int(entrance[0]),
                            int(surface["originOffset"][2])
                            + int(entrance[2]),
                        ],
                        variant["id"],
                    )
            if kind == "knight_stronghold":
                sunken = [
                    variant
                    for variant in variants
                    if variant["sourcePort"]["surfaceAccessDepth"] == 2
                ]
                raised = [
                    variant
                    for variant in variants
                    if variant["sourcePort"]["surfaceAccessDepth"] == -2
                ]
                self.assertEqual(4, len(sunken))
                self.assertEqual(4, len(raised))
                self.assertEqual({2}, {variant["weight"] for variant in sunken})
                self.assertEqual({1}, {variant["weight"] for variant in raised})
                self.assertEqual(
                    {0, 1, 2, 3},
                    {variant["layoutSeed"] for variant in sunken},
                )
                self.assertEqual(
                    {0, 1, 2, 3},
                    {variant["layoutSeed"] for variant in raised},
                )

    def test_buried_stronghold_explicitly_carves_its_walkable_interior(self):
        api = {
            "SparseStructure": ruin_builder.SparseStructure,
            "set_loot_container": ruin_builder.set_loot_container,
            "set_spawner": ruin_builder.set_spawner,
            "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
        }
        structure, markers, validation, _graph = (
            route_builder._render_stronghold(0, api)
        )
        authored_air = sum(
            1 for value in structure.blocks.values()
            if value[0] == "minecraft:air"
        )
        self.assertGreater(authored_air, 10000)
        self.assertTrue(validation["entranceReachable"])
        self.assertTrue(validation["bossRoomReachable"])
        self.assertIn("bossGroupSpawner", markers)

    def test_buried_stronghold_only_authors_the_compact_surface_access(self):
        api = {
            "SparseStructure": ruin_builder.SparseStructure,
            "set_loot_container": ruin_builder.set_loot_container,
            "set_spawner": ruin_builder.set_spawner,
            "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
        }
        for seed_index in range(4):
            structure, markers, _validation, _graph = (
                route_builder._render_stronghold(seed_index, api)
            )
            entrance = markers["surfaceEntrance"]["offset"]
            entrance_column = (int(entrance[0]), int(entrance[2]))
            ground_y = int(route_builder.STRONGHOLD_ENTRY_Y)
            self.assertEqual(
                ground_y,
                structure.surface_columns[entrance_column],
                seed_index,
            )

            self.assertEqual([], structure.surface_burial_components)
            self.assertEqual(81, len(structure.surface_columns), seed_index)
            self.assertEqual(
                structure.surface_access_columns,
                structure.surface_columns,
                seed_index,
            )
            self.assertEqual(
                {ground_y},
                set(structure.surface_columns.values()),
                seed_index,
            )

    def test_buried_stronghold_serializes_only_authored_surface_air(self):
        api = {
            "SparseStructure": ruin_builder.SparseStructure,
            "set_loot_container": ruin_builder.set_loot_container,
            "set_spawner": ruin_builder.set_spawner,
            "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
        }
        for seed_index, seed in enumerate(stronghold_port.FIXED_SOURCE_SEEDS):
            structure, _markers, _validation, _graph = (
                route_builder._render_stronghold(seed_index, api)
            )
            graph = stronghold_port.StrongholdGraph(seed)
            surface_buffer = stronghold_port._compile_selected_buffer(
                graph,
                api,
                stronghold_port._is_surface_component,
                access_floor_depth=2,
            )
            ground_y = int(structure.surface_ground_y)
            entrance_columns = set(structure.surface_access_columns)
            authored_surface_air = {
                structure.source_local_positions[position]
                for position, block in surface_buffer.blocks.items()
                if block[0] == "minecraft:air"
                and position in structure.source_local_positions
                and structure.source_local_positions[position][1] >= ground_y
                and (
                    structure.source_local_positions[position][0],
                    structure.source_local_positions[position][2],
                )
                not in entrance_columns
            }
            actual_surface_air = {
                (x, y, z)
                for (x, y, z), block in structure.blocks.items()
                if block[0] == "minecraft:air"
                and y >= ground_y
                and (x, z) not in entrance_columns
            }
            self.assertGreater(len(authored_surface_air), 0, seed_index)
            self.assertEqual(
                authored_surface_air,
                actual_surface_air,
                seed_index,
            )
            self.assertTrue(
                any(
                    block[0] == "minecraft:air"
                    and y >= ground_y
                    and (x, z) in entrance_columns
                    for (x, y, z), block in structure.blocks.items()
                ),
                seed_index,
            )

    def test_stronghold_envelope_does_not_carve_a_surface_transition_moat(self):
        api = {
            "SparseStructure": ruin_builder.SparseStructure,
            "set_loot_container": ruin_builder.set_loot_container,
            "set_spawner": ruin_builder.set_spawner,
            "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
        }
        margin = ruin_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        for seed_index in range(4):
            structure, _markers, _validation, _graph = (
                route_builder._render_stronghold(seed_index, api)
            )
            envelope = ruin_builder._surface_native_envelope(
                structure,
                "knight_stronghold",
                environment_seed=271828,
            )
            ground_y = int(structure.surface_ground_y)
            authored_columns = {
                (x + margin, z + margin)
                for x, z in structure.surface_columns
            }
            source_positions = {
                (x + margin, y, z + margin)
                for x, y, z in structure.blocks
            }
            artificial_air = [
                (x, y, z)
                for (x, y, z), block in envelope.blocks.items()
                if block[0] == "minecraft:air"
                and y >= ground_y
                and (x, z) not in authored_columns
                and (x, y, z) not in source_positions
            ]
            self.assertEqual([], artificial_air[:16], seed_index)
            self.assertEqual(
                set(), envelope.surface_transition_columns, seed_index
            )

    def test_dark_tower_only_adapts_its_main_foundation(self):
        api = {
            "SparseStructure": ruin_builder.SparseStructure,
            "set_loot_container": ruin_builder.set_loot_container,
            "set_spawner": ruin_builder.set_spawner,
            "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
        }
        structure, _markers, _validation, _graph, _boss = (
            route_builder._render_dark_tower(0, api)
        )
        self.assertEqual(10, structure.surface_core_radius)
        center_x, center_z = structure.surface_core_center
        self.assertGreater(center_x, 0)
        self.assertGreater(center_z, 0)
        self.assertLess(center_x, structure.size[0])
        self.assertLess(center_z, structure.size[2])
        self.assertGreater(len(structure.surface_columns), 300)
        self.assertLess(len(structure.surface_columns), 350)
        self.assertEqual(
            {ruin_builder.SURFACE_NATIVE_GROUND_Y},
            set(structure.surface_columns.values()),
        )
        self.assertNotIn((0, 0), structure.surface_columns)
        self.assertNotIn((63, 63), structure.surface_columns)


if __name__ == "__main__":
    unittest.main()
