# -*- coding: utf-8 -*-
import io
import json
import pathlib
import struct
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
MODULE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(MODULE_ROOT))

import build_ruin_structures as builder
import lich_tower_legacy_port as legacy_port
import ruin_worldgen_logic as worldgen


def read_mcstructure(path):
    stream = io.BytesIO(path.read_bytes())
    root_type = struct.unpack("B", stream.read(1))[0]
    if root_type != builder.TAG_COMPOUND:
        raise ValueError("mcstructure root is not a compound")
    builder._read_string(stream, "<")
    return builder._read_payload(stream, root_type, "<")


class LichTowerBuilderTests(unittest.TestCase):
    LOCKED_SOURCE_COMMIT = "a7dd8f13c653e137f977f5ffaa870fcb20fc1625"

    @staticmethod
    def _main_position(structure, x, y, z):
        """Translate a locked-source main-tower local coordinate."""
        minimum_x, minimum_y, minimum_z = (
            structure.lich_tower_metadata["sourceBounds"][:3]
        )
        # The main component's source bounding box starts at world Y=1.
        return (
            int(x) - minimum_x,
            int(y) + 1 - minimum_y,
            int(z) - minimum_z,
        )

    def test_eight_deterministic_source_layouts_have_expected_shape_and_rooms(self):
        fingerprints = []
        for seed in range(8):
            first = builder.lich_tower(seed)
            second = builder.lich_tower(seed)
            self.assertEqual(first.size, second.size)
            self.assertEqual(first.blocks, second.blocks)
            self.assertGreaterEqual(first.size[0], 47)
            self.assertGreaterEqual(first.size[2], 47)
            self.assertGreaterEqual(first.size[1], 64)
            self.assertLessEqual(first.size[1], 104)
            names = [block[0] for block in first.blocks.values()]
            self.assertEqual(1, names.count("tf_slice:lich_boss_spawner"))
            self.assertIn("minecraft:bookshelf", names)
            # Bedrock/NetEase names the Java cobweb block `minecraft:web`.
            self.assertIn("minecraft:web", names)
            self.assertIn("minecraft:tnt", names)
            fingerprints.append(
                hash(
                    tuple(
                        (position, repr(block))
                        for position, block in sorted(first.blocks.items())
                    )
                )
            )
        self.assertGreaterEqual(len(set(fingerprints)), 6)

    def test_layout_uses_locked_component_graph_instead_of_fixed_mock_towers(self):
        for seed in range(8):
            structure = builder.lich_tower(seed)
            metadata = structure.lich_tower_metadata
            self.assertEqual(self.LOCKED_SOURCE_COMMIT, metadata["sourceCommit"])
            self.assertEqual(15, metadata["mainSize"])
            self.assertGreaterEqual(metadata["mainHeight"], 55)
            self.assertLessEqual(metadata["mainHeight"], 86)
            self.assertGreaterEqual(metadata["towerCount"], 9)
            self.assertEqual(metadata["towerCount"], metadata["roofCount"])
            self.assertIn("bridge", metadata["componentKinds"])
            self.assertIn("outbuilding", metadata["componentKinds"])

            marker_positions = [
                position
                for position, block in structure.blocks.items()
                if block[0] == "tf_slice:lich_boss_spawner"
            ]
            self.assertEqual([tuple(metadata["bossSpawnerOffset"])], marker_positions)

    def test_controlled_spawn_offsets_are_real_interior_floor_positions(self):
        for seed in range(8):
            structure = builder.lich_tower(seed)
            offsets = structure.lich_tower_metadata["controlledSpawnOffsets"]
            self.assertGreaterEqual(len(offsets), 64, seed)
            self.assertLessEqual(len(offsets), 256, seed)

            horizontal_positions = set()
            for offset in offsets:
                position = tuple(offset)
                horizontal_positions.add((position[0], position[2]))
                feet = structure.blocks.get(position)
                head = structure.blocks.get(
                    (position[0], position[1] + 1, position[2])
                )
                floor = structure.blocks.get(
                    (position[0], position[1] - 1, position[2])
                )
                self.assertIsNotNone(feet, (seed, position, "feet"))
                self.assertIsNotNone(head, (seed, position, "head"))
                self.assertIsNotNone(floor, (seed, position, "floor"))
                self.assertEqual("minecraft:air", feet[0], (seed, position))
                self.assertEqual("minecraft:air", head[0], (seed, position))
                self.assertNotEqual("minecraft:air", floor[0], (seed, position))

            xs = [position[0] for position in horizontal_positions]
            zs = [position[1] for position in horizontal_positions]
            self.assertTrue(max(xs) - min(xs) > 12 or max(zs) - min(zs) > 12)

    def test_source_roofs_and_interior_vertical_circulation_are_present(self):
        for seed in range(8):
            structure = builder.lich_tower(seed)
            names = [block[0] for block in structure.blocks.values()]
            # 4.3.2508 roofs are birch component roofs, not weathered-stone
            # pyramids extruded from a fixed square tower.
            self.assertIn("minecraft:birch_slab", names)
            self.assertIn("minecraft:birch_stairs", names)
            # The main tower uses paired slab stair flights, crossings and a
            # glass lich-room floor. Side towers carry ladders and room pools.
            self.assertGreater(names.count("minecraft:birch_slab"), 80)
            self.assertGreater(names.count("minecraft:oak_fence"), 80)
            self.assertIn("minecraft:glass", names)
            self.assertIn("minecraft:mob_spawner", names)

            highest_y = max(position[1] for position in structure.blocks)
            roof_names = {
                block[0]
                for position, block in structure.blocks.items()
                if position[1] >= highest_y - 2
            }
            self.assertTrue(
                roof_names
                & {
                    "minecraft:birch_planks",
                    "minecraft:birch_slab",
                    "minecraft:birch_stairs",
                }
            )

            roof_stairs = [
                block
                for block in structure.blocks.values()
                if block[0] == "minecraft:birch_stairs"
            ]
            self.assertEqual(
                {0, 1, 2, 3},
                {
                    block[1].get("weirdo_direction")
                    for block in roof_stairs
                },
                seed,
            )
            self.assertTrue(
                all(block[1].get("upside_down_bit") is False for block in roof_stairs),
                seed,
            )

    def test_stronghold_stone_palette_matches_locked_source_families(self):
        palette = legacy_port.BlockBuffer(legacy_port.FIXED_SOURCE_SEEDS[0])
        names = {
            palette.palette(x, y, z, 15)
            for x in range(20)
            for y in range(20)
            for z in range(20)
        }
        self.assertEqual(
            {
                "minecraft:stone_bricks",
                "minecraft:cracked_stone_bricks",
                "minecraft:mossy_stone_bricks",
                "minecraft:infested_stone_bricks",
            },
            names,
        )

    def test_small_side_towers_have_real_windows(self):
        for seed in range(8):
            names = [block[0] for block in builder.lich_tower(seed).blocks.values()]
            self.assertIn("minecraft:glass_pane", names, seed)

    def test_main_tower_first_double_spiral_flight_matches_locked_source(self):
        structure = builder.lich_tower(0)

        def block_at(x, y, z):
            return structure.blocks[
                self._main_position(structure, x, y, z)
            ]

        # TowerWingComponent.makeStairs15flight: the first birch flight uses
        # paired bottom/top slabs, a full-block inner spine and two-high rails.
        self.assertEqual(
            ("minecraft:birch_slab", {"top_slot_bit": False}, {}),
            block_at(3, 3, 13),
        )
        self.assertEqual(
            ("minecraft:birch_slab", {"top_slot_bit": False}, {}),
            block_at(5, 4, 13),
        )
        self.assertEqual(
            ("minecraft:birch_slab", {"top_slot_bit": True}, {}),
            block_at(6, 4, 13),
        )
        self.assertEqual(
            ("minecraft:birch_planks", {}, {}),
            block_at(4, 3, 11),
        )
        self.assertEqual(
            ("minecraft:oak_fence", {}, {}),
            block_at(4, 4, 11),
        )
        self.assertEqual(
            ("minecraft:oak_fence", {}, {}),
            block_at(4, 5, 11),
        )

        # The second foot is the same source flight rotated 180 degrees and
        # built from stone, which is what makes this a true double spiral.
        self.assertEqual(
            ("minecraft:stone_slab", {"top_slot_bit": False}, {}),
            block_at(11, 3, 1),
        )

    def test_lich_room_keeps_only_the_birch_spiral_entrance_open(self):
        """The second spiral terminates below instead of piercing the arena."""
        for seed in range(8):
            structure = builder.lich_tower(seed)
            graph = legacy_port.ComponentGraph(
                structure.lich_tower_metadata["layoutSeed"]
            )
            main = graph.main
            highest_opening = int(main.highest_opening)
            if main.height - highest_opening > 15:
                highest_opening = main.height - 15
            floor = 2 + (highest_opening // 5) * 5
            rotation = 0 if (highest_opening // 5) % 2 == 0 else 1

            def block_name(x, z):
                rotated_x, rotated_z = legacy_port._rotated_local(
                    15, x, z, rotation
                )
                position = self._main_position(
                    structure, rotated_x, floor, rotated_z
                )
                return structure.blocks[position][0]

            birch_entrance = [
                block_name(x, z)
                for x in (1, 2)
                for z in range(7, 13)
            ]
            terminated_stone_entrance = [
                block_name(x, z)
                for x in (12, 13)
                for z in range(3, 8)
            ]
            self.assertTrue(
                all(name == "minecraft:air" for name in birch_entrance),
                seed,
            )
            self.assertTrue(
                all(
                    name == "minecraft:birch_planks"
                    for name in terminated_stone_entrance
                ),
                seed,
            )

    def test_lich_room_keeps_every_recorded_side_tower_doorway_open(self):
        """The locked source cuts every recorded opening, including arena-height wings."""
        checked_openings = 0
        for seed in range(8):
            structure = builder.lich_tower(seed)
            graph = legacy_port.ComponentGraph(
                structure.lich_tower_metadata["layoutSeed"]
            )
            main = graph.main
            highest_opening = int(main.highest_opening)
            if main.height - highest_opening > 15:
                highest_opening = main.height - 15
            floor = 2 + (highest_opening // 5) * 5

            for x, y, z in main.openings:
                if y + 1 < floor:
                    continue
                checked_openings += 1
                for doorway_y in (y, y + 1):
                    position = self._main_position(
                        structure, x, doorway_y, z
                    )
                    self.assertEqual(
                        "minecraft:air",
                        structure.blocks[position][0],
                        (seed, (x, y, z), doorway_y),
                    )

        self.assertGreater(checked_openings, 0)

    def test_lich_chandelier_hangs_in_the_upper_arena(self):
        """Keep the light ring clear of the boss and players below it."""
        for seed in range(8):
            structure = builder.lich_tower(seed)
            graph = legacy_port.ComponentGraph(
                structure.lich_tower_metadata["layoutSeed"]
            )
            main = graph.main
            highest_opening = int(main.highest_opening)
            if main.height - highest_opening > 15:
                highest_opening = main.height - 15
            floor = 2 + (highest_opening // 5) * 5
            chandelier_y = max(floor + 7, main.height - 6)

            self.assertGreaterEqual(chandelier_y - floor, 7, seed)
            for x, z in ((9, 7), (7, 9), (5, 7), (7, 5)):
                position = self._main_position(
                    structure, x, chandelier_y, z
                )
                self.assertEqual(
                    "minecraft:oak_fence",
                    structure.blocks[position][0],
                    (seed, position),
                )

    def test_every_ladder_has_a_facing_state_and_solid_backing(self):
        support_offset = {
            2: (0, 0, 1),   # north-facing ladder is backed to its south
            3: (0, 0, -1),  # south-facing ladder is backed to its north
            4: (1, 0, 0),   # west-facing ladder is backed to its east
            5: (-1, 0, 0),  # east-facing ladder is backed to its west
        }
        for seed in range(8):
            structure = builder.lich_tower(seed)
            ladders = [
                (position, block)
                for position, block in structure.blocks.items()
                if block[0] == "minecraft:ladder"
            ]
            self.assertTrue(ladders)
            for position, block in ladders:
                facing = block[1].get("facing_direction")
                self.assertIn(facing, support_offset, (seed, position, block))
                dx, dy, dz = support_offset[facing]
                support = structure.blocks.get(
                    (position[0] + dx, position[1] + dy, position[2] + dz)
                )
                self.assertIsNotNone(support, (seed, position, facing))
                self.assertNotEqual(
                    "minecraft:air",
                    support[0],
                    (seed, position, facing, support),
                )
                # A supported ladder still breaks if its backing wall lives
                # in the next 16x16 structure tile and has not been placed
                # yet.  Check both manual catalog tiling and the independently
                # aligned surface-native chunk templates.
                self.assertEqual(
                    (position[0] // 16, position[2] // 16),
                    (
                        (position[0] + dx) // 16,
                        (position[2] + dz) // 16,
                    ),
                    (seed, "manual", position, facing),
                )
                native_x = 8 - structure.size[0] // 2 + position[0]
                native_z = 8 - structure.size[2] // 2 + position[2]
                self.assertEqual(
                    (native_x // 16, native_z // 16),
                    ((native_x + dx) // 16, (native_z + dz) // 16),
                    (seed, "surface_native", position, facing),
                )

    def test_rooms_use_the_netease_registered_wooden_pressure_plate(self):
        for seed in range(8):
            names = [
                block[0] for block in builder.lich_tower(seed).blocks.values()
            ]
            self.assertNotIn("minecraft:oak_pressure_plate", names)
            self.assertIn("minecraft:wooden_pressure_plate", names)


class LichTowerWorldgenTests(unittest.TestCase):
    def test_variant_boss_spawner_offset_overrides_entry_default(self):
        entry = {
            "bossSpawner": {
                "kind": "lich",
                "entity": "tf_slice:lich",
                "offset": [10, 20, 30],
                "activationRadius": 9,
            }
        }
        variant = {"bossSpawnerOffset": [40, 50, 60]}
        resolved = worldgen.boss_spawner_for_variant(entry, variant)
        self.assertEqual([40, 50, 60], resolved["offset"])
        self.assertEqual("lich", resolved["kind"])
        self.assertEqual(9, resolved["activationRadius"])
        self.assertEqual([10, 20, 30], entry["bossSpawner"]["offset"])

    def test_dense_mushroom_override_wins_even_after_lich_is_supported(self):
        for region_x, region_z in ((0, -16), (0, 16)):
            self.assertEqual(
                "lich_tower",
                worldgen.pick_variety_landmark(region_x, region_z, 0),
            )
            self.assertEqual(
                "mushroom_tower",
                worldgen.resolve_variety_landmark(
                    region_x,
                    region_z,
                    0,
                    {"lich_tower", "naga_courtyard", "large_hill"},
                    "mushroom_tower",
                ),
            )

    def test_lich_activation_honors_y_floor_without_progress_gate(self):
        job = worldgen.create_landmark_job(
            "lich_tower", (100, 64, 200), 0, []
        )
        job["state"] = "complete"
        job["bossSpawnerReady"] = True
        job["bossSpawner"] = {
            "offset": [24, 70, 24],
            "activationRadius": 9,
            "minPlayerYOffset": -4,
            "progressObjective": "tf_naga_defeated",
        }
        nearby = [
            {
                "dimensionId": 33027004,
                "position": (124.5, 134.0, 128.5 + 100.0),
                "progress": {},
            }
        ]
        self.assertEqual(
            (124.5, 134.5, 224.5),
            worldgen.boss_activation_position(job, nearby, 33027004),
        )

    def test_controlled_spawn_pool_locks_upstream_weights(self):
        weights = worldgen.LICH_TOWER_SPAWN_WEIGHTS
        self.assertEqual(33, sum(weight for _entity, weight, _group in weights))
        self.assertEqual(
            {
                "minecraft:zombie": 10,
                "minecraft:skeleton": 10,
                "tf_slice:death_tome": 10,
                "minecraft:creeper": 1,
                "minecraft:enderman": 1,
                "minecraft:witch": 1,
            },
            dict((entity, weight) for entity, weight, _group in weights),
        )
        first = worldgen.lich_tower_spawn_choice(7301)
        second = worldgen.lich_tower_spawn_choice(7301)
        self.assertEqual(first, second)
        self.assertIn(first[0], dict((row[0], row) for row in weights))
        self.assertGreaterEqual(first[1], 1)

    def test_controlled_spawn_candidates_use_only_compiled_interior_offsets(self):
        job = {
            "anchor": [100, 64, 200],
            "controlledSpawns": {
                "interiorOffsets": [[2, 3, 4], [8, 9, 10]],
            },
        }
        candidates = worldgen.lich_tower_spawn_candidates(job, 7301, 8)
        allowed = {
            (102.5, 67.0, 204.5),
            (108.5, 73.0, 210.5),
        }
        self.assertEqual(2, len(candidates))
        self.assertTrue(all(position in allowed for position, _yaw in candidates))
        self.assertEqual(2, len({position for position, _yaw in candidates}))


class LichTowerGeneratedCatalogTests(unittest.TestCase):
    def test_generated_tower_tiles_contain_repaired_palette_windows_and_roofs(self):
        structure_root = (
            ROOT
            / "TwilightBossSliceB"
            / "structures"
            / "tf_slice"
            / "ruins"
        )
        tower_tiles = list((structure_root / "lich_tower").rglob("*.mcstructure"))
        tower_tiles.extend(
            (structure_root / "surface_native" / "lich_tower").rglob(
                "*.mcstructure"
            )
        )
        self.assertTrue(tower_tiles)

        palettes = []
        for path in tower_tiles:
            root = read_mcstructure(path)
            palettes.extend(
                root["structure"]["palette"]["default"]["block_palette"]
            )

        names = {entry["name"] for entry in palettes}
        self.assertTrue(
            {
                "minecraft:stone_bricks",
                "minecraft:cracked_stone_bricks",
                "minecraft:mossy_stone_bricks",
                "minecraft:infested_stone_bricks",
                "minecraft:glass_pane",
            }.issubset(names)
        )
        self.assertNotIn("minecraft:mossy_cobblestone", names)

        roof_stairs = [
            entry for entry in palettes if entry["name"] == "minecraft:birch_stairs"
        ]
        self.assertTrue(roof_stairs)
        self.assertEqual(
            {0, 1, 2, 3},
            {
                int(entry["states"]["weirdo_direction"])
                for entry in roof_stairs
            },
        )
        self.assertTrue(
            all(
                not bool(entry["states"].get("upside_down_bit"))
                for entry in roof_stairs
            )
        )

    def test_generated_tower_tiles_exclude_unknown_oak_pressure_plate(self):
        structure_root = (
            ROOT
            / "TwilightBossSliceB"
            / "structures"
            / "tf_slice"
            / "ruins"
        )
        tower_tiles = list((structure_root / "lich_tower").rglob("*.mcstructure"))
        tower_tiles.extend(
            (structure_root / "surface_native" / "lich_tower").rglob(
                "*.mcstructure"
            )
        )
        self.assertTrue(tower_tiles)
        for path in tower_tiles:
            self.assertNotIn(b"minecraft:oak_pressure_plate", path.read_bytes())

    def test_generated_catalog_exposes_v3_lich_contract(self):
        path = (
            ROOT
            / "TwilightBossSliceB"
            / "structures"
            / "tf_slice"
            / "ruins"
            / "structure_catalog_v1.json"
        )
        catalog = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(3, catalog["schemaVersion"])
        entry = {
            value["id"]: value for value in catalog["structures"]
        }["lich_tower"]
        self.assertEqual(8, len(entry["variants"]))
        for index, variant in enumerate(entry["variants"]):
            metadata = builder.lich_tower(index).lich_tower_metadata
            self.assertEqual(
                metadata["bossSpawnerOffset"],
                variant["bossSpawnerOffset"],
            )
            self.assertEqual(
                metadata["controlledSpawnOffsets"],
                variant["controlledSpawnOffsets"],
            )
        self.assertEqual("lich", entry["bossSpawner"]["kind"])
        self.assertEqual("tf_slice:lich", entry["bossSpawner"]["entity"])
        self.assertEqual(9, entry["bossSpawner"]["activationRadius"])
        self.assertEqual(-4, entry["bossSpawner"]["minPlayerYOffset"])
        self.assertEqual(0.5, entry["bossSpawner"]["spawnYOffset"])
        self.assertEqual(
            "tf_naga_defeated",
            entry["bossSpawner"]["progressObjective"],
        )
        self.assertEqual(12, entry["controlledSpawns"]["cap"])


if __name__ == "__main__":
    unittest.main()
