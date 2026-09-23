# -*- coding: utf-8 -*-
import hashlib
import json
import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = runpy.run_path(
    str(ROOT / "tools" / "build_ruin_structures.py"),
    run_name="route_structure_parity_contract",
)


class RouteStructureParityTests(unittest.TestCase):
    def test_labyrinth_uses_minecraft_legacy_random_source_sequence(self):
        rng = BUILDER["_JavaRandomSource"](0)

        self.assertEqual(0, rng.next_int(20))
        self.assertEqual(8, rng.next_int(20))
        self.assertAlmostEqual(0.24053639, rng.next_float(), places=8)
        self.assertTrue(rng.next_boolean())

    def test_labyrinth_layout_matches_locked_432508_source_vector(self):
        raw, raw_width, raw_depth, room_cells = BUILDER[
            "_source_maze_layout"
        ](22, 22, 0, (11, 11), 7)

        self.assertEqual(
            [
                (11, 11),
                (1, 9),
                (16, 14),
                (12, 2),
                (20, 15),
                (16, 5),
                (5, 16),
            ],
            room_cells,
        )
        self.assertEqual((45, 45), (raw_width, raw_depth))
        self.assertEqual(
            "11880e03c3285f001fcdecbb3b0a2789917f04a58dc5fd144ac2294e4655f1d0",
            hashlib.sha256(bytes(raw)).hexdigest(),
        )

    def test_labyrinth_trigger_uses_the_structure_surface_ground_y(self):
        structure = BUILDER["labyrinth_structure"](0)
        trigger_path = (
            ROOT
            / "TwilightBossSliceB"
            / "netease_feature_rules"
            / "ruin_landmark_surface_swamp_feature_rule.json"
        )
        trigger = json.loads(trigger_path.read_text(encoding="utf-8"))
        y_expression = trigger["minecraft:feature_rules"]["distribution"]["y"]

        self.assertTrue(
            y_expression.endswith(" - %d" % structure.surface_ground_y),
            "labyrinth placement must subtract the same local ground Y used by "
            "the structure; otherwise the entire mound becomes an elevated cliff",
        )
        self.assertEqual(1, y_expression.count("query.get_height_at"))
        self.assertNotIn("math.max", y_expression)
        self.assertNotIn("math.min", y_expression)

    def test_labyrinth_is_source_scale_and_only_entrance_mound_touches_surface(self):
        structure = BUILDER["labyrinth_structure"](0)
        markers = structure.landmark_metadata

        self.assertEqual([22, 22], markers["mazeGrid"])
        self.assertEqual(5, markers["cellPitch"])
        self.assertEqual(10, markers["levelOffset"])
        self.assertEqual((112, 54, 112), structure.size)
        self.assertEqual(41, structure.surface_ground_y)
        self.assertTrue(markers["lowerBedrockShell"])
        self.assertTrue(
            all(room["size"] == [16, 5, 16] for room in markers["rooms"])
        )

        surface_columns = structure.surface_columns
        self.assertGreater(len(surface_columns), 500)
        self.assertLess(len(surface_columns), 1100)
        self.assertTrue(
            all(
                (x - markers["mapCenter"][0]) ** 2
                + (z - markers["mapCenter"][2]) ** 2
                < 19 ** 2
                for x, z in surface_columns
            )
        )
        self.assertFalse(
            any(
                block[0] == "minecraft:grass_block"
                and (
                    (x - markers["mapCenter"][0]) ** 2
                    + (z - markers["mapCenter"][2]) ** 2
                    >= 19 ** 2
                )
                for (x, _y, z), block in structure.blocks.items()
            )
        )
        self.assertGreater(
            sum(
                1
                for block in structure.blocks.values()
                if block[0] == "minecraft:bedrock"
            ),
            1000,
        )

    def test_route_bosses_have_physical_source_style_spawners(self):
        labyrinth = BUILDER["labyrinth_structure"](0)
        labyrinth_boss = tuple(labyrinth.landmark_metadata["boss"]["offset"])
        self.assertEqual(
            "tf_slice:minoshroom_boss_spawner",
            labyrinth.blocks[labyrinth_boss][0],
        )

        hydra = BUILDER["hydra_lair_structure"](0)
        hydra_boss = tuple(hydra.landmark_metadata["boss"]["offset"])
        self.assertEqual(
            "tf_slice:hydra_boss_spawner",
            hydra.blocks[hydra_boss][0],
        )

    def test_labyrinth_roof_stays_buried_below_rolling_swamp_terrain(self):
        """The underground roof must stay below the authored entrance mound."""
        structure = BUILDER["labyrinth_structure"](0)
        markers = structure.landmark_metadata
        upper_ceiling_y = markers["ceilings"][0]

        self.assertGreaterEqual(
            structure.surface_ground_y - upper_ceiling_y,
            24,
        )
        self.assertEqual(
            "tf_slice:mazestone",
            structure.blocks[(1, upper_ceiling_y, 1)][0],
        )

    def test_labyrinth_surface_and_interlevel_shafts_are_physically_open(self):
        """Both advertised vertical routes must cross their ceiling layers."""
        structure = BUILDER["labyrinth_structure"](0)
        markers = structure.landmark_metadata
        rooms = markers["rooms"]
        upper_exit = next(
            room for room in rooms if room["level"] == 0 and room["kind"] == "exit"
        )
        upper_entrance = next(
            room
            for room in rooms
            if room["level"] == 0 and room["kind"] == "entrance"
        )

        exit_x, _exit_y, exit_z = upper_exit["offset"]
        entrance_x, _entrance_y, entrance_z = upper_entrance["offset"]
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(exit_x, markers["ceilings"][1], exit_z)][0],
        )
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(entrance_x, markers["ceilings"][0], entrance_z)][0],
        )

    def test_labyrinth_surface_entrance_has_the_source_building_and_brick_shaft(self):
        structure = BUILDER["labyrinth_structure"](0)
        markers = structure.landmark_metadata
        entrance = markers["surfaceEntrance"]
        origin_x, ground_y, origin_z = entrance["origin"]

        self.assertEqual(35, entrance["moundDiameter"])
        self.assertEqual(4, entrance["crossTunnelWidth"])
        self.assertEqual([6, 6], entrance["shaftOuter"])
        self.assertEqual([4, 4], entrance["shaftInner"])

        # Source upper entrance: decorative/brick wall bands and a two-wide
        # opening inside a complete four-high fence panel.
        self.assertEqual(
            "tf_slice:decorative_mazestone",
            structure.blocks[(origin_x, ground_y + 1, origin_z)][0],
        )
        self.assertEqual(
            "tf_slice:mazestone_brick",
            structure.blocks[(origin_x, ground_y + 2, origin_z)][0],
        )
        self.assertEqual(
            "minecraft:oak_fence",
            structure.blocks[(origin_x + 6, ground_y + 1, origin_z)][0],
        )
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(origin_x + 7, ground_y + 1, origin_z)][0],
        )
        self.assertEqual(
            "minecraft:oak_fence",
            structure.blocks[(origin_x + 7, ground_y + 4, origin_z)][0],
        )

        # The central opening is a 4x4 void inside a 6x6 brick-lined shaft.
        shaft_y = markers["ceilings"][0] + 4
        self.assertEqual(
            "tf_slice:mazestone_brick",
            structure.blocks[(origin_x + 5, shaft_y, origin_z + 5)][0],
        )
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(origin_x + 6, shaft_y, origin_z + 6)][0],
        )
        self.assertEqual(
            "tf_slice:decorative_mazestone",
            structure.blocks[(origin_x + 5, ground_y + 1, origin_z + 5)][0],
        )
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(origin_x + 6, ground_y + 1, origin_z + 6)][0],
        )

        # MazeEntranceShaftComponent terminates at the maze ceiling. It does
        # not continue down into the entrance room as a freestanding booth.
        room_air_y = markers["levels"][0]
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(origin_x + 5, room_air_y, origin_z + 5)][0],
        )

    def test_labyrinth_mound_supports_cross_tunnels_without_foundation_gaps(self):
        structure = BUILDER["labyrinth_structure"](0)
        center_x, _center_y, center_z = structure.landmark_metadata["mapCenter"]
        ground_y = structure.surface_ground_y

        # The terrain envelope needs authored base-height columns under both
        # the central shaft and the four approaches. The structure merge then
        # reopens the actual shaft/tunnel air without exposing foundation sides.
        self.assertEqual(
            ground_y, structure.surface_columns[(center_x, center_z)]
        )
        self.assertEqual(
            ground_y, structure.surface_columns[(center_x, center_z + 12)]
        )
        self.assertIn((center_x, center_z + 7), structure.surface_columns)
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(center_x, ground_y, center_z)][0],
        )
        self.assertEqual(
            "minecraft:grass_block",
            structure.blocks[(center_x, ground_y, center_z + 12)][0],
        )
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(center_x, ground_y + 1, center_z + 12)][0],
        )

        prepared = BUILDER["_surface_native_envelope"](
            structure, "labyrinth"
        )
        margin = BUILDER["SURFACE_NATIVE_WORLDGEN_MARGIN"]
        tunnel_x = center_x + margin
        tunnel_z = center_z + 12 + margin
        self.assertEqual(
            "minecraft:dirt",
            prepared.blocks[(tunnel_x, ground_y - 1, tunnel_z)][0],
        )
        self.assertEqual(
            "minecraft:air",
            prepared.blocks[(tunnel_x, ground_y + 1, tunnel_z)][0],
        )

    def test_labyrinth_lower_shell_is_hidden_behind_the_source_maze_boundary(self):
        structure = BUILDER["labyrinth_structure"](0)
        self.assertEqual("minecraft:bedrock", structure.blocks[(0, 0, 0)][0])
        self.assertEqual("minecraft:bedrock", structure.blocks[(0, 7, 0)][0])

        visible_boundary = set()
        for coordinate in range(1, 111):
            visible_boundary.update(
                {
                    (1, coordinate),
                    (111, coordinate),
                    (coordinate, 1),
                    (coordinate, 111),
                }
            )
        for x, z in visible_boundary:
            for y in range(2, 6):
                self.assertNotEqual(
                    "minecraft:bedrock",
                    structure.blocks[(x, y, z)][0],
                )

    def test_labyrinth_room_doorways_use_complete_source_fence_panels(self):
        structure = BUILDER["labyrinth_structure"](0)
        room = next(
            room
            for room in structure.landmark_metadata["rooms"]
            if room["level"] == 0 and room["kind"] == "spawner_chest"
        )
        origin_x, floor_y, origin_z = room["origin"]

        self.assertEqual(
            "minecraft:oak_fence",
            structure.blocks[(origin_x + 6, floor_y + 1, origin_z)][0],
        )
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(origin_x + 7, floor_y + 1, origin_z)][0],
        )
        self.assertEqual(
            "minecraft:oak_fence",
            structure.blocks[(origin_x + 7, floor_y + 4, origin_z)][0],
        )

    def test_labyrinth_dead_end_fountains_are_walled_and_cannot_flood_the_maze(self):
        fountains = []
        for seed in range(8):
            structure = BUILDER["labyrinth_structure"](seed)
            for decoration in structure.landmark_metadata["decorations"]:
                if decoration["component"] != "dead_end":
                    continue
                if decoration["kind"] not in ("water", "lava"):
                    continue
                fountains.append((structure, decoration))

        self.assertGreater(len(fountains), 0)
        for structure, decoration in fountains:
            source_offsets = decoration["sourceOffsets"]
            receptacle_offsets = decoration["receptacleOffsets"]
            self.assertEqual(2, len(source_offsets))
            self.assertEqual(2, len(receptacle_offsets))
            self.assertTrue(
                all(
                    structure.blocks[tuple(offset)][0]
                    == "minecraft:%s" % decoration["kind"]
                    for offset in source_offsets
                )
            )
            self.assertTrue(
                all(
                    structure.blocks[tuple(offset)][0] == "minecraft:air"
                    for offset in receptacle_offsets
                )
            )
            self.assertTrue(
                all(
                    offset[1] == decoration["floorY"] + 3
                    for offset in source_offsets
                )
            )

    def test_labyrinth_decorations_only_use_real_cells_and_supported_corridors(self):
        structures = [BUILDER["labyrinth_structure"](seed) for seed in range(8)]
        decorations = [
            decoration
            for structure in structures
            for decoration in structure.landmark_metadata["decorations"]
        ]
        self.assertGreater(len(decorations), 0)
        self.assertTrue(
            all(decoration["rawCellValue"] == 1 for decoration in decorations)
        )
        self.assertTrue(
            all(
                decoration["sideWallsVerified"]
                for decoration in decorations
                if decoration["component"] == "corridor"
            )
        )

    def test_labyrinth_torches_are_wall_facing_and_do_not_replace_wall_blocks(self):
        structures = [BUILDER["labyrinth_structure"](seed) for seed in range(8)]
        torches = [
            (position, block)
            for structure in structures
            for position, block in structure.blocks.items()
            if block[0] == "minecraft:torch"
        ]
        self.assertGreater(len(torches), 0)
        self.assertTrue(
            all(
                block[1].get("torch_facing_direction")
                in ("north", "south", "east", "west")
                for _position, block in torches
            )
        )

    def test_labyrinth_wall_torches_have_support_in_the_bedrock_attachment_direction(self):
        attachment_delta = {
            "east": (1, 0),
            "west": (-1, 0),
            "south": (0, 1),
            "north": (0, -1),
        }
        unsupported = []
        for seed in range(8):
            structure = BUILDER["labyrinth_structure"](seed)
            for (x, y, z), block in structure.blocks.items():
                if block[0] != "minecraft:torch":
                    continue
                direction = block[1].get("torch_facing_direction")
                dx, dz = attachment_delta[direction]
                support = structure.blocks.get((x + dx, y, z + dz))
                if support is None or support[0] in (
                    "minecraft:air",
                    "minecraft:cave_air",
                    "minecraft:structure_void",
                ):
                    unsupported.append((seed, (x, y, z), direction))
        self.assertEqual([], unsupported)

    def test_labyrinth_shafts_match_the_source_fall_pits_without_ladders(self):
        air_blocks = {
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:structure_void",
        }
        for seed in range(8):
            structure = BUILDER["labyrinth_structure"](seed)
            metadata = structure.landmark_metadata
            self.assertFalse(
                any(
                    block[0] == "minecraft:ladder"
                    for block in structure.blocks.values()
                )
            )

            surface_origin = metadata["surfaceEntrance"]["origin"]
            surface_x, ground_y, surface_z = surface_origin
            exit_room = next(
                room
                for room in metadata["rooms"]
                if room["level"] == 0 and room["kind"] == "exit"
            )
            exit_x, upper_floor_y, exit_z = exit_room["origin"]
            shaft_contracts = (
                (surface_x, surface_z, metadata["ceilings"][0], ground_y),
                (exit_x, exit_z, metadata["ceilings"][1], upper_floor_y),
            )
            for origin_x, origin_z, minimum_y, maximum_y in shaft_contracts:
                for y in range(minimum_y, maximum_y + 1):
                    for local_x in range(5, 11):
                        for local_z in range(5, 11):
                            block = structure.blocks.get(
                                (origin_x + local_x, y, origin_z + local_z)
                            )
                            if local_x in (5, 10) or local_z in (5, 10):
                                self.assertIsNotNone(block)
                                self.assertNotIn(block[0], air_blocks)
                            else:
                                self.assertIsNotNone(block)
                                self.assertIn(block[0], air_blocks)

            # MazeRoomExitComponent surrounds the upper opening with a 6x6
            # decorative/iron-bar cage and leaves a 4x4 drop in its middle.
            for local_y, expected in (
                (1, "tf_slice:decorative_mazestone"),
                (2, "minecraft:iron_bars"),
                (3, "minecraft:iron_bars"),
                (4, "tf_slice:decorative_mazestone"),
            ):
                for local_x in range(5, 11):
                    for local_z in range(5, 11):
                        block = structure.blocks[
                            (
                                exit_x + local_x,
                                upper_floor_y + local_y,
                                exit_z + local_z,
                            )
                        ][0]
                        if 6 <= local_x <= 9 and 6 <= local_z <= 9:
                            self.assertIn(block, air_blocks)
                        else:
                            self.assertEqual(expected, block)

    def test_labyrinth_trapped_dead_end_matches_the_source_hidden_tnt_dais(self):
        traps = []
        for seed in range(8):
            structure = BUILDER["labyrinth_structure"](seed)
            for decoration in structure.landmark_metadata["decorations"]:
                if (
                    decoration["component"] == "dead_end"
                    and decoration["kind"] == "trap"
                ):
                    traps.append((structure, decoration))

        self.assertGreater(len(traps), 0)
        for structure, decoration in traps:
            origin_x, floor_y, origin_z = decoration["origin"]
            direction = decoration["opening"]
            stair_back_direction = {
                "north": "south",
                "south": "north",
                "west": "east",
                "east": "west",
            }[direction]
            expected_stair_direction = {
                "east": 0,
                "west": 1,
                "south": 2,
                "north": 3,
            }[stair_back_direction]
            expected_chest_direction = {
                "north": 2,
                "south": 3,
                "west": 4,
                "east": 5,
            }[direction]

            def transform(local_x, local_z):
                if direction == "north":
                    return origin_x + local_x, origin_z + local_z
                if direction == "south":
                    return origin_x + local_x, origin_z + 5 - local_z
                if direction == "west":
                    return origin_x + local_z, origin_z + local_x
                return origin_x + 5 - local_z, origin_z + local_x

            chest_positions = []
            for local_x in (2, 3):
                stair_x, stair_z = transform(local_x, 3)
                plank_x, plank_z = transform(local_x, 4)
                chest_positions.append((plank_x, floor_y + 2, plank_z))
                self.assertEqual(
                    "minecraft:oak_stairs",
                    structure.blocks[(stair_x, floor_y + 1, stair_z)][0],
                )
                self.assertEqual(
                    expected_stair_direction,
                    structure.blocks[(stair_x, floor_y + 1, stair_z)][1][
                        "weirdo_direction"
                    ],
                    "the stair high side must meet the rear chest platform",
                )
                self.assertEqual(
                    "minecraft:oak_planks",
                    structure.blocks[(plank_x, floor_y + 1, plank_z)][0],
                )
                self.assertEqual(
                    "minecraft:trapped_chest",
                    structure.blocks[(plank_x, floor_y + 2, plank_z)][0],
                )
                self.assertEqual(
                    expected_chest_direction,
                    structure.blocks[(plank_x, floor_y + 2, plank_z)][1][
                        "facing_direction"
                    ],
                    "the chest front must face the barred entrance",
                )

                for local_z, expected_cover in (
                    (3, "minecraft:oak_stairs"),
                    (4, "minecraft:oak_planks"),
                ):
                    tnt_x, tnt_z = transform(local_x, local_z)
                    self.assertEqual(
                        "minecraft:tnt",
                        structure.blocks[(tnt_x, floor_y, tnt_z)][0],
                    )
                    self.assertEqual(
                        expected_cover,
                        structure.blocks[(tnt_x, floor_y + 1, tnt_z)][0],
                    )

            # The source calls setDoubleLootChest: this is one large chest,
            # not two visually adjacent single chests.
            first, second = chest_positions
            first_entity = structure.blocks[first][2]
            second_entity = structure.blocks[second][2]
            self.assertEqual(second[0], first_entity["pairx"])
            self.assertEqual(second[2], first_entity["pairz"])
            self.assertEqual(first[0], second_entity["pairx"])
            self.assertEqual(first[2], second_entity["pairz"])
            self.assertNotEqual(
                bool(first_entity["pairlead"]),
                bool(second_entity["pairlead"]),
            )

            for local_z in (0, 1):
                for local_x in (1, 4):
                    wall_x, wall_z = transform(local_x, local_z)
                    for local_y in range(1, 4):
                        self.assertEqual(
                            "tf_slice:cut_mazestone",
                            structure.blocks[
                                (wall_x, floor_y + local_y, wall_z)
                            ][0],
                        )
                for local_x in (2, 3):
                    bar_x, bar_z = transform(local_x, local_z)
                    for local_y in range(1, 4):
                        self.assertEqual(
                            "minecraft:iron_bars",
                            structure.blocks[(bar_x, floor_y + local_y, bar_z)][0],
                        )

    def test_labyrinth_tnt_traps_are_not_left_visibly_exposed(self):
        structures = [BUILDER["labyrinth_structure"](seed) for seed in range(8)]
        exposed = []
        tnt_count = 0
        for seed, structure in enumerate(structures):
            for (x, y, z), block in structure.blocks.items():
                if block[0] != "minecraft:tnt":
                    continue
                tnt_count += 1
                cover = structure.blocks.get((x, y + 1, z))
                if cover is None or cover[0] in (
                    "minecraft:air",
                    "minecraft:cave_air",
                    "minecraft:structure_void",
                ):
                    exposed.append((seed, (x, y, z)))
        self.assertGreater(tnt_count, 0)
        self.assertEqual([], exposed)

    def test_labyrinth_spawner_rooms_have_four_complete_pillar_enclosures(self):
        """Spawner rooms use the original cut-stone, stair, plank and bar cages."""
        structure = BUILDER["labyrinth_structure"](0)
        room = next(
            room
            for room in structure.landmark_metadata["rooms"]
            if room["kind"] == "spawner_chest"
        )
        origin_x, floor_y, origin_z = room["origin"]

        for enclosure_x, enclosure_z in ((3, 3), (10, 3), (3, 10), (10, 10)):
            for pillar_x, pillar_z in (
                (enclosure_x, enclosure_z),
                (enclosure_x + 2, enclosure_z),
                (enclosure_x, enclosure_z + 2),
                (enclosure_x + 2, enclosure_z + 2),
            ):
                for y in range(floor_y + 1, floor_y + 5):
                    self.assertEqual(
                        "tf_slice:cut_mazestone",
                        structure.blocks[
                            (origin_x + pillar_x, y, origin_z + pillar_z)
                        ][0],
                    )
            expected_center = (
                "minecraft:wooden_pressure_plate"
                if (enclosure_x, enclosure_z) == (10, 10)
                else "minecraft:oak_planks"
            )
            self.assertEqual(
                expected_center,
                structure.blocks[
                    (origin_x + enclosure_x + 1, floor_y + 1, origin_z + enclosure_z + 1)
                ][0],
            )
            self.assertEqual(
                "minecraft:iron_bars",
                structure.blocks[
                    (origin_x + enclosure_x + 1, floor_y + 2, origin_z + enclosure_z)
                ][0],
            )

    def test_labyrinth_spawner_room_uses_the_four_source_pillar_assignments(self):
        structure = BUILDER["labyrinth_structure"](0)
        room = next(
            room
            for room in structure.landmark_metadata["rooms"]
            if room["kind"] == "spawner_chest"
        )
        origin_x, floor_y, origin_z = room["origin"]

        spawner = structure.blocks[(origin_x + 4, floor_y + 2, origin_z + 4)]
        self.assertEqual("minecraft:mob_spawner", spawner[0])
        self.assertEqual("tf_slice:minotaur", spawner[2]["EntityIdentifier"])
        for local_x, local_z in ((4, 11), (11, 4)):
            self.assertEqual(
                "minecraft:chest",
                structure.blocks[(origin_x + local_x, floor_y + 2, origin_z + local_z)][0],
            )
        self.assertEqual(
            "minecraft:wooden_pressure_plate",
            structure.blocks[(origin_x + 11, floor_y + 1, origin_z + 11)][0],
        )
        for local_x, local_z in ((10, 11), (11, 10), (11, 12), (12, 11)):
            self.assertEqual(
                "minecraft:tnt",
                structure.blocks[(origin_x + local_x, floor_y, origin_z + local_z)][0],
            )
            self.assertEqual(
                "minecraft:oak_stairs",
                structure.blocks[(origin_x + local_x, floor_y + 1, origin_z + local_z)][0],
            )

    def test_minoshroom_room_matches_source_chest_shelves_and_sealed_fences(self):
        structure = BUILDER["labyrinth_structure"](0)
        room = next(
            room
            for room in structure.landmark_metadata["rooms"]
            if room["kind"] == "minoshroom"
        )
        origin_x, floor_y, origin_z = room["origin"]

        boss_offset = tuple(structure.landmark_metadata["boss"]["offset"])
        expected_spawner = (origin_x + 7, floor_y + 2, origin_z + 7)
        self.assertEqual(expected_spawner, boss_offset)
        self.assertEqual(
            "tf_slice:minoshroom_boss_spawner",
            structure.blocks[expected_spawner][0],
        )
        self.assertEqual(
            "minecraft:air",
            structure.blocks[(origin_x + 7, floor_y + 1, origin_z + 7)][0],
        )

        for local_x, local_z in ((3, 3), (12, 3), (3, 12), (12, 12)):
            self.assertEqual(
                "minecraft:chest",
                structure.blocks[(origin_x + local_x, floor_y + 2, origin_z + local_z)][0],
            )

        expected_shelf_blocks = {
            (1, 1, 1): "minecraft:red_mushroom_block",
            (1, 2, 4): "minecraft:red_mushroom_block",
            (4, 3, 1): "minecraft:red_mushroom_block",
            (12, 1, 1): "minecraft:brown_mushroom_block",
            (14, 3, 4): "minecraft:brown_mushroom_block",
            (1, 1, 12): "minecraft:red_mushroom_block",
            (12, 1, 12): "minecraft:red_mushroom_block",
            (5, 4, 5): "minecraft:brown_mushroom_block",
            (8, 4, 8): "minecraft:red_mushroom_block",
        }
        for (local_x, local_y, local_z), expected in expected_shelf_blocks.items():
            self.assertEqual(
                expected,
                structure.blocks[(origin_x + local_x, floor_y + local_y, origin_z + local_z)][0],
            )

        stems = [
            position
            for position, block in structure.blocks.items()
            if block[0] == "minecraft:mushroom_stem"
            and origin_x <= position[0] <= origin_x + 15
            and floor_y <= position[1] <= floor_y + 5
            and origin_z <= position[2] <= origin_z + 15
        ]
        self.assertEqual([], stems)

        for local_x, local_z in ((7, 0), (7, 15), (0, 7), (15, 7)):
            for local_y in range(1, 4):
                self.assertEqual(
                    "minecraft:oak_fence",
                    structure.blocks[
                        (origin_x + local_x, floor_y + local_y, origin_z + local_z)
                    ][0],
                )

    def test_regular_mushroom_room_uses_source_medium_and_bracket_mushrooms(self):
        structure = BUILDER["labyrinth_structure"](0)
        room = next(
            room
            for room in structure.landmark_metadata["rooms"]
            if room["kind"] == "mushroom"
        )
        origin_x, floor_y, origin_z = room["origin"]

        for local_x, local_y, local_z, block_name in (
            (5, 3, 9, "minecraft:red_mushroom_block"),
            (9, 2, 5, "minecraft:red_mushroom_block"),
            (6, 3, 4, "minecraft:brown_mushroom_block"),
            (10, 1, 9, "minecraft:brown_mushroom_block"),
        ):
            self.assertEqual(
                block_name,
                structure.blocks[(origin_x + local_x, floor_y + local_y, origin_z + local_z)][0],
            )
        self.assertEqual(
            "minecraft:mushroom_stem",
            structure.blocks[(origin_x + 5, floor_y + 1, origin_z + 9)][0],
        )
        for local_x, local_y, local_z in ((1, 2, 1), (14, 3, 1), (1, 1, 14)):
            self.assertEqual(
                "minecraft:mushroom_stem",
                structure.blocks[(origin_x + local_x, floor_y + local_y, origin_z + local_z)][0],
            )

    def test_regular_mushroom_caps_expose_their_skin_on_the_outward_faces(self):
        structure = BUILDER["labyrinth_structure"](0)
        room = next(
            room
            for room in structure.landmark_metadata["rooms"]
            if room["kind"] == "mushroom"
        )
        origin_x, floor_y, origin_z = room["origin"]

        # The isolated source mushroom centred at local (9, 2, 5) is a clean
        # state-vector: Bedrock bits 1..9 must follow physical NW..SE faces.
        expected_bits = {
            (-1, -1): 1,
            (0, -1): 2,
            (1, -1): 3,
            (-1, 0): 4,
            (0, 0): 5,
            (1, 0): 6,
            (-1, 1): 7,
            (0, 1): 8,
            (1, 1): 9,
        }
        for (dx, dz), expected in expected_bits.items():
            block = structure.blocks[
                (origin_x + 9 + dx, floor_y + 2, origin_z + 5 + dz)
            ]
            self.assertEqual("minecraft:red_mushroom_block", block[0])
            self.assertEqual(expected, block[1].get("huge_mushroom_bits"))

    def test_labyrinth_restores_source_wall_palette_and_corridor_width(self):
        structures = [BUILDER["labyrinth_structure"](seed) for seed in range(8)]
        marker = structures[0].landmark_metadata
        self.assertEqual(4, marker["corridorWidth"])
        self.assertEqual(
            {"brick": 50, "cracked": 30, "mossy": 20},
            marker["wallPalettePercent"],
        )

        wall_counts = {name: 0 for name in (
            "tf_slice:mazestone_brick",
            "tf_slice:cracked_mazestone",
            "tf_slice:mossy_mazestone",
        )}
        for structure in structures:
            for block in structure.blocks.values():
                if block[0] in wall_counts:
                    wall_counts[block[0]] += 1
        weathered = (
            wall_counts["tf_slice:cracked_mazestone"]
            + wall_counts["tf_slice:mossy_mazestone"]
        )
        self.assertGreaterEqual(weathered / float(sum(wall_counts.values())), 0.35)

    def test_labyrinth_restores_dead_end_and_straight_corridor_components(self):
        structures = [BUILDER["labyrinth_structure"](seed) for seed in range(8)]
        dead_end_kinds = set()
        corridor_kinds = set()
        component_count = 0
        for structure in structures:
            decorations = structure.landmark_metadata["decorations"]
            component_count += len(decorations)
            dead_end_kinds.update(
                row["kind"] for row in decorations if row["component"] == "dead_end"
            )
            corridor_kinds.update(
                row["kind"] for row in decorations if row["component"] == "corridor"
            )

        self.assertGreater(component_count, 100)
        self.assertTrue(
            {"chest", "trap", "torches", "water", "lava", "roots", "shrooms"}
            <= dead_end_kinds
        )
        self.assertTrue({"fence_arch", "iron_gate", "roots", "shrooms"} <= corridor_kinds)

    def test_hydra_lair_is_an_open_dome_with_source_geology(self):
        structures = [BUILDER["hydra_lair_structure"](seed) for seed in range(8)]
        structure = structures[0]
        markers = structure.landmark_metadata
        ground_y = structure.surface_ground_y

        self.assertEqual("open_wedge", markers["terrainShape"])
        self.assertEqual(34, markers["featureRadius"])
        self.assertEqual("northwest", markers["entranceDirection"])
        self.assertEqual(ground_y, markers["boss"]["offset"][1])
        self.assertEqual(ground_y + 26, structure.surface_columns[(40, 40)])
        self.assertEqual(ground_y, structure.surface_columns[(0, 40)])
        self.assertNotIn((24, 24), structure.surface_columns)
        self.assertIn((56, 56), structure.surface_columns)
        self.assertGreater(
            sum(
                1
                for x in range(8, 41)
                for z in range(8, 41)
                if structure.blocks.get((x, ground_y + 1, z), (None,))[0]
                in ("minecraft:air", "minecraft:cave_air")
            ),
            100,
        )

        palette = set(
            block[0]
            for candidate in structures
            for block in candidate.blocks.values()
        )
        self.assertIn("minecraft:glowstone", palette)
        self.assertIn("minecraft:raw_iron_block", palette)
        self.assertNotIn("minecraft:lapis_ore", palette)

        self.assertNotIn("SURFACE_ENVIRONMENT_PROFILES", BUILDER)
        self.assertNotIn("_bake_surface_environment", BUILDER)


if __name__ == "__main__":
    unittest.main()
