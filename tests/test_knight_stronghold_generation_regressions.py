# -*- coding: utf-8 -*-
import collections
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_ruin_structures as ruin_builder
import knight_stronghold_legacy_port as stronghold


def render_api():
    return {
        "SparseStructure": ruin_builder.SparseStructure,
        "FORBIDDEN_OUTPUT_BLOCKS": ruin_builder.FORBIDDEN_OUTPUT_BLOCKS,
        "set_loot_container": ruin_builder.set_loot_container,
        "set_spawner": ruin_builder.set_spawner,
    }


class KnightStrongholdGenerationRegressionTests(unittest.TestCase):
    def _rendered(self, seed_index):
        seed = stronghold.FIXED_SOURCE_SEEDS[seed_index]
        graph = stronghold.StrongholdGraph(seed)
        source, _entry, _columns = stronghold._compile_buffer(graph, {})
        structure, markers, validation, room_graph, source_port = (
            stronghold.render_stronghold(seed_index, render_api())
        )
        boss_local = tuple(
            markers["bossGroupSpawner"]["offset"][axis]
            + (structure.surface_ground_y if axis == 1 else 0)
            for axis in range(3)
        )
        translation = tuple(
            boss_local[axis] - source.boss_spawner[axis]
            for axis in range(3)
        )
        return (
            graph,
            source,
            structure,
            markers,
            validation,
            room_graph,
            source_port,
            translation,
        )

    @staticmethod
    def _walkable_route(structure, markers):
        air = {
            "minecraft:air",
            "minecraft:cave_air",
            "minecraft:void_air",
        }
        unsupported = air | {
            "minecraft:lava",
            "minecraft:water",
            "minecraft:flowing_water",
        }
        blocks = dict(structure.blocks)
        for position, block in list(blocks.items()):
            if block[0] == "tf_slice:stronghold_shield":
                blocks[position] = ("minecraft:air", {}, {})

        def block_name(position):
            return blocks.get(position, ("minecraft:stone",))[0]

        def can_stand(position):
            x, y, z = position
            return (
                block_name(position) in air
                and block_name((x, y + 1, z)) in air
                and block_name((x, y - 1, z)) not in unsupported
            )

        entrance = markers["surfaceEntrance"]["offset"]
        entrance = (
            int(entrance[0]),
            int(entrance[1]) + int(structure.surface_ground_y),
            int(entrance[2]),
        )
        boss = markers["bossRoom"]["offset"]
        boss = (
            int(boss[0]),
            int(boss[1]) + int(structure.surface_ground_y),
            int(boss[2]),
        )
        boss_radius = int(markers["bossRoom"].get("radius", 4))
        starts = {
            (x, y, z)
            for x in range(entrance[0] - 2, entrance[0] + 3)
            for y in range(entrance[1] - 2, entrance[1] + 3)
            for z in range(entrance[2] - 2, entrance[2] + 3)
            if can_stand((x, y, z))
        }
        goals = {
            (x, y, z)
            for x in range(boss[0] - boss_radius, boss[0] + boss_radius + 1)
            for y in range(boss[1] - 2, boss[1] + 4)
            for z in range(boss[2] - boss_radius, boss[2] + boss_radius + 1)
            if can_stand((x, y, z))
        }
        visited = set(starts)
        pending = collections.deque(starts)
        while pending:
            current = pending.popleft()
            if current in goals:
                return True
            x, y, z = current
            for delta_x, delta_z in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                moved = False
                for delta_y in (0, 1, -1):
                    neighbor = (
                        x + delta_x,
                        y + delta_y,
                        z + delta_z,
                    )
                    if neighbor in visited or not can_stand(neighbor):
                        continue
                    visited.add(neighbor)
                    pending.append(neighbor)
                    moved = True
                    break
                if moved:
                    continue
                fall_x = x + delta_x
                fall_z = z + delta_z
                if block_name((fall_x, y, fall_z)) not in air:
                    continue
                for fall_y in range(y - 1, y - 17, -1):
                    if block_name((fall_x, fall_y, fall_z)) not in air:
                        break
                    landing = (fall_x, fall_y, fall_z)
                    if landing in visited or not can_stand(landing):
                        continue
                    visited.add(landing)
                    pending.append(landing)
                    break
        return False

    def test_atrium_fence_ring_has_the_source_balcony_below_it(self):
        atriums = []
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            atriums.extend(
                (component, buffer)
                for component in graph.components
                if component.kind == "atrium"
            )

        self.assertTrue(atriums, "the release bank must exercise an atrium")
        for component, buffer in atriums:
            for x in range(5, 13):
                for z in range(5, 13):
                    if x not in (5, 12) and z not in (5, 12):
                        continue
                    fence = component.local_to_world(x, 8, z)
                    support = component.local_to_world(x, 7, z)
                    self.assertEqual(
                        "minecraft:cobblestone_wall",
                        buffer.blocks[fence][0],
                    )
                    self.assertNotEqual(
                        stronghold.AIR,
                        buffer.blocks.get(support, (stronghold.AIR,))[0],
                        (component.uid, x, z),
                    )

    def test_final_template_contains_every_compiled_room_block(self):
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            source, _entry, _columns = stronghold._compile_buffer(graph, {})
            structure, markers, validation, _room_graph, _source_port = (
                stronghold.render_stronghold(seed_index, render_api())
            )
            replaced = {
                entry[0] for entry in source.loot
            } | {
                position for position, _entity_id in source.spawners
            }
            missing = []
            outside = []
            for position, block in source.blocks.items():
                local = structure.source_local_positions[position]
                if not all(
                    0 <= local[axis] < structure.size[axis]
                    for axis in range(3)
                ):
                    outside.append((position, local))
                elif position not in replaced and (
                    local not in structure.blocks
                    or structure.blocks[local][0] != block[0]
                ) and local not in structure.surface_entry_overrides:
                    missing.append((position, local, block[0]))
            self.assertEqual([], outside[:16], seed_index)
            self.assertEqual([], missing[:16], seed_index)
            self.assertTrue(validation["finalDoorwaysConnected"])
            self.assertTrue(validation["bossSpawnerPresent"])
            self.assertEqual(0, validation["clippedBlockCount"])

    def test_release_layouts_match_the_typical_single_boss_source_band(self):
        bank_types = set()
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            bank_types.update(component.kind for component in graph.components)
            boss_rooms = [
                component
                for component in graph.components
                if component.kind == "boss_room"
            ]
            self.assertEqual(1, len(boss_rooms), seed_index)
            adjacency = collections.defaultdict(set)
            for left, right in graph.edges:
                adjacency[left].add(right)
                adjacency[right].add(left)
            distances = {graph.entrance.uid: 0}
            pending = collections.deque((graph.entrance.uid,))
            while pending:
                current = pending.popleft()
                for neighbor in adjacency[current]:
                    if neighbor in distances:
                        continue
                    distances[neighbor] = distances[current] + 1
                    pending.append(neighbor)
            xs = [
                value
                for component in graph.components
                for value in (component.bbox[0], component.bbox[3])
            ]
            zs = [
                value
                for component in graph.components
                for value in (component.bbox[2], component.bbox[5])
            ]
            self.assertGreaterEqual(len(graph.components), 36, seed_index)
            self.assertLessEqual(len(graph.components), 55, seed_index)
            self.assertGreaterEqual(distances[boss_rooms[0].uid], 5, seed_index)
            self.assertLessEqual(distances[boss_rooms[0].uid], 9, seed_index)
            self.assertLessEqual(max(xs) - min(xs) + 1, 162, seed_index)
            self.assertLessEqual(max(zs) - min(zs) + 1, 162, seed_index)
        self.assertEqual(
            {"entrance", "access_chamber"}
            | set(stronghold.LOWER_GRAMMAR)
            | set(stronghold.UPPER_GRAMMAR),
            bank_types,
        )

    def test_release_bank_has_high_room_variety_in_every_layout(self):
        rare_coverage = collections.Counter()
        required = (
            {"entrance", "access_chamber"}
            | set(stronghold.LOWER_GRAMMAR)
            | set(stronghold.UPPER_GRAMMAR)
        )
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            types = {component.kind for component in graph.components}
            self.assertGreaterEqual(len(types), 19, seed_index)
            self.assertLessEqual(len(required - types), 1, seed_index)
            for kind in ("foundry", "treasure_room", "upper_ascender"):
                if kind in types:
                    rare_coverage[kind] += 1
        for kind in ("foundry", "treasure_room", "upper_ascender"):
            self.assertGreaterEqual(rare_coverage[kind], 2, kind)

    def test_directional_stairs_rotate_with_the_component(self):
        # Functional flights are validated from their final visible ascent,
        # not from a Java decorative FACING literal.  Bedrock's geometric
        # high side therefore uses the direct world-axis state table.
        expected_up = {
            stronghold.SOUTH: 2,
            stronghold.WEST: 1,
            stronghold.NORTH: 3,
            stronghold.EAST: 0,
        }
        for direction, expected in expected_up.items():
            bbox = stronghold._component_box(
                100, 20, 100, -4, -1, 0, 9, 14, 9, direction
            )
            component = stronghold.Component(
                0, "small_stairs", 1, direction, bbox
            )
            component.enter_bottom = True
            buffer = stronghold.RenderBuffer({})
            stronghold._render_shell(buffer, component)
            stronghold._render_small_stairs(buffer, component)
            stair_directions = {
                buffer.blocks[
                    component.local_to_world(x, step, step)
                ][1].get("weirdo_direction")
                for step in range(1, 8)
                for x in range(3, 6)
            }
            self.assertEqual({expected}, stair_directions, direction)

    def test_release_validation_checks_source_facing_stair_runs(self):
        for seed_index in range(len(stronghold.FIXED_SOURCE_SEEDS)):
            _structure, _markers, validation, _room_graph, _source_port = (
                stronghold.render_stronghold(seed_index, render_api())
            )
            self.assertTrue(
                validation["stairRunsTraversable"],
                seed_index,
            )

    def test_every_functional_stair_faces_its_world_ascent(self):
        bedrock_state_from_world_ascent = {
            (1, 0): 0,
            (-1, 0): 1,
            (0, 1): 2,
            (0, -1): 3,
        }

        def expected_direction(low, high):
            delta_x = (high[0] > low[0]) - (high[0] < low[0])
            delta_z = (high[2] > low[2]) - (high[2] < low[2])
            return bedrock_state_from_world_ascent[(delta_x, delta_z)]

        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            flights = []
            for component in graph.components:
                specs = []
                if component.kind == "small_stairs":
                    rotation = (
                        stronghold.ROT_NONE
                        if component.enter_bottom
                        else stronghold.ROT_BACK
                    )
                    specs.append(
                        (
                            rotation,
                            [(3, step, step) for step in range(1, 8)],
                        )
                    )
                elif component.kind == "balcony_room":
                    for rotation in (
                        stronghold.ROT_NONE,
                        stronghold.ROT_BACK,
                    ):
                        specs.append(
                            (
                                rotation,
                                [
                                    (step + 6, step, 5)
                                    for step in range(1, 8)
                                ],
                            )
                        )
                elif component.kind == "upper_ascender":
                    positions = []
                    for step in range(1, 6):
                        y = step
                        z = step + 2 if component.exit_top else 7 - step
                        row = [
                            component.local_to_world(x, y, z)
                            for x in range(1, 4)
                        ]
                        positions.extend(row)
                    presence = [
                        buffer.blocks.get(
                            position,
                            (stronghold.AIR,),
                        )[0]
                        == "minecraft:stone_brick_stairs"
                        for position in positions
                    ]
                    if not any(presence):
                        continue
                    self.assertTrue(
                        all(presence),
                        (seed_index, component.uid, component.kind),
                    )
                    expected = expected_direction(
                        min(positions, key=lambda position: position[1]),
                        max(positions, key=lambda position: position[1]),
                    )
                    actual = [
                        buffer.blocks[position][1]["weirdo_direction"]
                        for position in positions
                    ]
                    flights.append((component.uid, component.kind))
                    self.assertEqual(
                        [expected] * len(positions),
                        actual,
                        (seed_index, component.uid, component.kind),
                    )
                    continue

                for rotation, coordinates in specs:
                    positions = []
                    for x, y, z in coordinates:
                        local = stronghold.RenderBuffer.rotated_local_position(
                            component,
                            x,
                            y,
                            z,
                            rotation,
                        )
                        positions.append(component.local_to_world(*local))
                    low = min(positions, key=lambda position: position[1])
                    high = max(positions, key=lambda position: position[1])
                    expected = expected_direction(low, high)
                    actual = [
                        buffer.blocks[position][1]["weirdo_direction"]
                        for position in positions
                    ]
                    flights.append((component.uid, component.kind))
                    self.assertEqual(
                        [expected] * len(positions),
                        actual,
                        (seed_index, component.uid, component.kind),
                    )
            self.assertTrue(flights, seed_index)

    def test_reverse_upper_ascender_finishes_on_its_exit_platform(self):
        component = stronghold.Component(
            0,
            "upper_ascender",
            1,
            stronghold.SOUTH,
            [0, 20, 0, 4, 29, 9],
        )
        component.exit_top = False
        buffer = stronghold.RenderBuffer({})
        stronghold._render_shell(buffer, component)
        stronghold._render_upper_ascender(buffer, component)

        for step in range(1, 6):
            for x in range(1, 4):
                self.assertEqual(
                    "minecraft:stone_brick_stairs",
                    buffer.blocks[
                        component.local_to_world(x, step, 7 - step)
                    ][0],
                    (step, x),
                )
        for x in range(1, 4):
            self.assertEqual(
                "minecraft:stone_bricks",
                buffer.blocks[component.local_to_world(x, 5, 1)][0],
                x,
            )

    def test_release_upper_ascenders_are_complete_or_absent_at_void_landings(self):
        ascender_count = 0
        rendered_count = 0
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            for component in graph.components:
                if component.kind != "upper_ascender":
                    continue
                ascender_count += 1
                if component.exit_top:
                    high_neighbor = next(
                        graph.components[right]
                        for left, right in graph.edges
                        if left == component.uid
                    )
                    door_pairs = stronghold._adjacent_door_pairs(
                        component,
                        high_neighbor,
                    )
                    high_index = 1
                else:
                    high_neighbor = component.parent
                    door_pairs = stronghold._adjacent_door_pairs(
                        high_neighbor,
                        component,
                    )
                    high_index = 0

                self.assertEqual(1, len(door_pairs), component.uid)
                first, second = door_pairs[0]
                high_door = door_pairs[0][high_index]
                low_door = door_pairs[0][1 - high_index]
                inward = (
                    high_door[0] - low_door[0],
                    high_door[2] - low_door[2],
                )
                landing_supports = {
                    (first[0], first[1] - 1, first[2]),
                    (second[0], second[1] - 1, second[2]),
                    (
                        high_door[0] + inward[0],
                        high_door[1] - 1,
                        high_door[2] + inward[1],
                    ),
                }
                landing_survived = all(
                    buffer.blocks.get(
                        position,
                        (stronghold.AIR,),
                    )[0]
                    != stronghold.AIR
                    for position in landing_supports
                )

                stair_positions = []
                for step in range(1, 6):
                    z = step + 2 if component.exit_top else 7 - step
                    for x in range(1, 4):
                        stair_positions.append(
                            component.local_to_world(x, step, z)
                        )

                platform_z = 8 if component.exit_top else 1
                platform_positions = [
                    component.local_to_world(x, 5, platform_z)
                    for x in range(1, 4)
                ]
                stair_presence = [
                    buffer.blocks.get(
                        position,
                        (stronghold.AIR,),
                    )[0]
                    == "minecraft:stone_brick_stairs"
                    for position in stair_positions
                ]
                platform_presence = [
                    buffer.blocks.get(
                        position,
                        (stronghold.AIR,),
                    )[0]
                    == "minecraft:stone_bricks"
                    for position in platform_positions
                ]
                self.assertEqual(
                    [landing_survived] * len(stair_positions),
                    stair_presence,
                    (seed_index, component.uid, "stairs"),
                )
                self.assertEqual(
                    [landing_survived] * len(platform_positions),
                    platform_presence,
                    (seed_index, component.uid, "platform"),
                )
                if landing_survived:
                    rendered_count += 1

        self.assertGreater(ascender_count, 0)
        self.assertLess(rendered_count, ascender_count)

    def test_upper_ascender_uses_thin_tread_supports_not_tall_side_buttresses(self):
        for exit_top in (True, False):
            component = stronghold.Component(
                0,
                "upper_ascender",
                1,
                stronghold.SOUTH,
                [0, 20, 0, 4, 29, 9],
            )
            component.exit_top = exit_top
            buffer = stronghold.RenderBuffer({})
            stronghold._render_upper_ascender(
                buffer,
                component,
                surface_y=17,
            )

            expected_stairs = set()
            expected_tread_supports = set()
            for step in range(1, 6):
                z = step + 2 if exit_top else 7 - step
                for x in range(1, 4):
                    expected_stairs.add(
                        component.local_to_world(x, step, z)
                    )
                    expected_tread_supports.add(
                        component.local_to_world(x, step - 1, z)
                    )

            platform_z = 8 if exit_top else 1
            expected_platform = {
                component.local_to_world(x, 5, platform_z)
                for x in range(1, 4)
            }
            low_step_z = 3 if exit_top else 6
            low_center = component.local_to_world(2, 0, low_step_z)
            expected_ground_pier = {
                (low_center[0], y, low_center[2])
                for y in range(17, 20)
            }

            actual_stairs = {
                position
                for position, block in buffer.blocks.items()
                if block[0] == "minecraft:stone_brick_stairs"
            }
            actual_solids = {
                position
                for position, block in buffer.blocks.items()
                if block[0] != stronghold.AIR
            }
            self.assertEqual(expected_stairs, actual_stairs, exit_top)
            self.assertEqual(
                expected_stairs
                | expected_tread_supports
                | expected_platform
                | expected_ground_pier,
                actual_solids,
                exit_top,
            )
            self.assertFalse(
                any(
                    component.local_to_world(side_x, y, z)
                    in actual_solids
                    for side_x in (0, 4)
                    for y in range(6)
                    for z in range(1, 9)
                ),
                exit_top,
            )

    def test_release_bank_avoids_overrepresented_sparse_upper_graphs(self):
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            upper = [
                component
                for component in graph.components
                if component.kind.startswith("upper_")
            ]
            upper_ids = {component.uid for component in upper}
            upper_edges = [
                (left, right)
                for left, right in graph.edges
                if right in upper_ids
            ]
            child_counts = collections.Counter(
                left for left, _right in upper_edges
            )
            depths = {graph.access.uid: 0}
            for left, right in upper_edges:
                depths[right] = depths.get(left, 0) + 1

            self.assertGreaterEqual(len(upper), 13, seed_index)
            self.assertGreaterEqual(
                sum(count > 1 for count in child_counts.values()),
                2,
                seed_index,
            )
            self.assertGreaterEqual(
                max(depths.get(component.uid, 0) for component in upper),
                6,
                seed_index,
            )
            self.assertEqual(
                set(stronghold.UPPER_GRAMMAR),
                {component.kind for component in upper},
                seed_index,
            )

    def test_statue_and_room_decorative_stairs_match_locked_java_facing(self):
        def component(kind, size):
            return stronghold.Component(
                0,
                kind,
                1,
                stronghold.SOUTH,
                [0, 0, 0, size[0] - 1, size[1] - 1, size[2] - 1],
            )

        def assert_states(buffer, piece, expected):
            for local, direction in expected.items():
                block = buffer.blocks[piece.local_to_world(*local)]
                self.assertEqual(
                    "minecraft:stone_brick_stairs",
                    block[0],
                    (piece.kind, local),
                )
                self.assertEqual(direction, block[1]["weirdo_direction"])

        statue_piece = component("entrance", (18, 7, 18))
        corner = stronghold.RenderBuffer({})
        stronghold._place_corner_statue(corner, statue_piece, 4, 1, 4, 0)
        assert_states(
            corner,
            statue_piece,
            {
                (4, 4, 5): 3,  # Java SOUTH -> Bedrock north/back edge
                (5, 4, 4): 1,  # Java EAST -> Bedrock west/back edge
                (4, 1, 5): 3,
                (5, 1, 4): 1,
            },
        )

        wall = stronghold.RenderBuffer({})
        stronghold._place_wall_statue(
            wall,
            statue_piece,
            8,
            1,
            8,
            stronghold.ROT_NONE,
        )
        assert_states(
            wall,
            statue_piece,
            {
                (7, 4, 8): 0,  # Java WEST
                (9, 4, 8): 1,  # Java EAST
                (7, 4, 7): 2,  # Java NORTH
                (9, 4, 7): 2,
            },
        )

        crossing_piece = component("crossing", (18, 7, 18))
        crossing = stronghold.RenderBuffer({})
        stronghold._render_crossing_details(crossing, crossing_piece)
        for local, expected in {
            (5, 1, 3): 0,
            (5, 1, 4): 3,
            (6, 1, 3): 2,
            (6, 1, 4): 1,
            (5, 1, 2): 3,
            (7, 1, 3): 0,
            (6, 1, 5): 2,
            (4, 1, 4): 1,
        }.items():
            self.assertEqual(
                expected,
                crossing.blocks[crossing_piece.local_to_world(*local)][1][
                    "weirdo_direction"
                ],
                local,
            )

        dead_end_piece = component("dead_end", (9, 7, 9))
        dead_end = stronghold.RenderBuffer({})
        stronghold._render_dead_end(dead_end, dead_end_piece)
        assert_states(
            dead_end,
            dead_end_piece,
            {
                **{(3, 1, z): 0 for z in range(2, 5)},
                **{(5, 1, z): 1 for z in range(2, 5)},
                (4, 1, 2): 2,
                (4, 1, 4): 3,
                (4, 2, 3): 2,
            },
        )

        treasure_piece = component("treasure_corridor", (9, 7, 27))
        treasure = stronghold.RenderBuffer({})
        stronghold._render_treasure_corridor(treasure, treasure_piece)
        assert_states(
            treasure,
            treasure_piece,
            {
                (8, 3, 12): 3,
                (8, 3, 13): 0,
                (8, 3, 14): 2,
                (7, 1, 12): 3,
                (7, 1, 13): 0,
                (7, 1, 14): 2,
            },
        )

        boss_piece = component("boss_room", (27, 7, 27))
        sarcophagus = stronghold.RenderBuffer({})
        stronghold._render_sarcophagus(
            sarcophagus,
            boss_piece,
            8,
            8,
            stronghold.JavaRandom(7),
        )
        assert_states(
            sarcophagus,
            boss_piece,
            {
                (8, 1, 8): 2,
                (8, 1, 11): 3,
                (9, 1, 9): 1,
                (9, 1, 10): 1,
                (7, 1, 9): 0,
                (7, 1, 10): 0,
            },
        )

    def test_small_stair_treasure_keeps_all_nine_source_stairs(self):
        piece = stronghold.Component(
            0,
            "small_stairs",
            1,
            stronghold.SOUTH,
            [0, 0, 0, 8, 13, 8],
        )
        piece.enter_bottom = True
        piece.has_treasure = True
        buffer = stronghold.RenderBuffer({})
        stronghold._render_shell(buffer, piece)
        stronghold._render_small_stairs(buffer, piece)
        expected = {
            **{(3, 1, z): 0 for z in range(5, 8)},
            **{(5, 1, z): 1 for z in range(5, 8)},
            (4, 1, 5): 2,
            (4, 1, 7): 3,
            (4, 2, 6): 2,
        }
        for local, direction in expected.items():
            block = buffer.blocks[piece.local_to_world(*local)]
            self.assertEqual("minecraft:stone_brick_stairs", block[0], local)
            self.assertEqual(direction, block[1]["weirdo_direction"], local)

    def test_surface_spiral_stairs_follow_the_final_world_ascent(self):
        self.assertEqual(1, stronghold._surface_stair_direction((0, 0), (1, 0)))
        self.assertEqual(0, stronghold._surface_stair_direction((0, 0), (-1, 0)))
        self.assertEqual(3, stronghold._surface_stair_direction((0, 0), (0, 1)))
        self.assertEqual(2, stronghold._surface_stair_direction((0, 0), (0, -1)))

    def test_surface_graph_stays_at_source_height_while_lower_graph_is_buried(self):
        for seed_index in range(len(stronghold.FIXED_SOURCE_SEEDS)):
            structure, markers, _validation, _room_graph, source_port = (
                stronghold.render_stronghold(seed_index, render_api())
            )
            self.assertEqual(2, source_port["surfaceAccessDepth"], seed_index)
            self.assertEqual(6, source_port["lowerGraphBurialDepth"], seed_index)
            self.assertEqual(
                "source_access_chamber",
                source_port["surfaceAccessStyle"],
                seed_index,
            )

            ground_y = int(structure.surface_ground_y)
            entrance = markers["surfaceEntrance"]["offset"]
            center_x = int(entrance[0])
            center_z = int(entrance[2])
            source_floor_y = (
                ground_y
                - source_port["surfaceAccessDepth"]
                - source_port["lowerGraphBurialDepth"]
            )
            graph = stronghold.StrongholdGraph(
                stronghold.FIXED_SOURCE_SEEDS[seed_index]
            )
            source_access_y = graph.access.local_to_world(4, 0, 4)[1]
            highest_lower_roof = max(
                source_floor_y + component.bbox[4] - source_access_y
                for component in graph.components
                if not component.kind.startswith("upper_")
            )
            self.assertLess(highest_lower_roof, ground_y, seed_index)
            self.assertEqual(
                stronghold.AIR,
                structure.blocks[(center_x, ground_y, center_z)][0],
                seed_index,
            )
            for delta_x, delta_z in (
                (0, 4),
                (-4, 0),
                (0, -4),
                (4, 0),
            ):
                for delta_y in (-1, 0):
                    self.assertEqual(
                        stronghold.AIR,
                        structure.blocks[
                            (
                                center_x + delta_x,
                                ground_y + delta_y,
                                center_z + delta_z,
                            )
                        ][0],
                        (seed_index, delta_x, delta_z, delta_y),
                    )
            self.assertFalse(
                any(
                    block[0] != stronghold.AIR
                    for (x, y, z), block in structure.blocks.items()
                    if y > ground_y
                    and abs(x - center_x) <= 4
                    and abs(z - center_z) <= 4
                ),
                seed_index,
            )

    def test_raised_source_access_profile_moves_the_surface_graph_up_four(self):
        structure, markers, validation, _room_graph, source_port = (
            stronghold.render_stronghold(
                0,
                render_api(),
                access_floor_depth=-2,
            )
        )
        ground_y = int(structure.surface_ground_y)

        self.assertEqual(-2, source_port["surfaceAccessDepth"])
        self.assertEqual(2, markers["surfaceEntrance"]["offset"][1])
        self.assertEqual(3, markers["trophyPedestal"]["offset"][1])
        self.assertEqual(
            {1},
            {offset[1] for offset in markers["shieldWalls"]},
        )
        self.assertTrue(validation["surfaceToBossWalkable"])
        self.assertEqual(
            "tf_slice:trophy_pedestal",
            structure.blocks[
                (
                    int(markers["trophyPedestal"]["offset"][0]),
                    ground_y + 3,
                    int(markers["trophyPedestal"]["offset"][2]),
                )
            ][0],
        )

    def test_raised_access_keeps_the_lower_graph_at_the_stable_burial_depth(self):
        lower, lower_markers, _validation, _room_graph, _source_port = (
            stronghold.render_stronghold(
                0,
                render_api(),
                access_floor_depth=2,
            )
        )
        raised, raised_markers, validation, _room_graph, _source_port = (
            stronghold.render_stronghold(
                0,
                render_api(),
                access_floor_depth=-2,
            )
        )

        self.assertEqual(
            lower_markers["bossRoom"]["offset"],
            raised_markers["bossRoom"]["offset"],
        )
        self.assertEqual(
            lower_markers["bossGroupSpawner"]["offset"],
            raised_markers["bossGroupSpawner"]["offset"],
        )
        self.assertEqual(
            sorted(lower_markers["lootChests"]),
            sorted(raised_markers["lootChests"]),
        )

        graph = stronghold.StrongholdGraph(stronghold.FIXED_SOURCE_SEEDS[0])
        lower_buffer = stronghold._compile_selected_buffer(
            graph,
            render_api(),
            lambda component: not stronghold._is_surface_component(component),
            access_floor_depth=-2,
        )
        ground_y = int(raised.surface_ground_y)
        entrance = raised_markers["surfaceEntrance"]["offset"]
        center_x = int(entrance[0])
        center_z = int(entrance[2])
        surfaced_lower_solids = [
            raised.source_local_positions[position]
            for position, block in lower_buffer.blocks.items()
            if block[0] != stronghold.AIR
            and position in raised.source_local_positions
            and raised.source_local_positions[position][1] >= ground_y
            and (
                abs(raised.source_local_positions[position][0] - center_x) > 4
                or abs(raised.source_local_positions[position][2] - center_z) > 4
            )
        ]
        self.assertEqual([], surfaced_lower_solids)
        self.assertTrue(validation["surfaceToBossWalkable"])

    def test_access_chamber_never_serializes_a_complete_roof_in_source_sky(self):
        for access_floor_depth in (2, -2):
            for seed_index in range(len(stronghold.FIXED_SOURCE_SEEDS)):
                structure, markers, validation, _room_graph, source_port = (
                    stronghold.render_stronghold(
                        seed_index,
                        render_api(),
                        access_floor_depth=access_floor_depth,
                    )
                )
                ground_y = int(structure.surface_ground_y)
                entrance = markers["surfaceEntrance"]["offset"]
                center_x = int(entrance[0])
                center_z = int(entrance[2])
                floor_y = ground_y - int(source_port["surfaceAccessDepth"])
                roof_y = floor_y + 4
                authored_roof = [
                    (x, roof_y, z)
                    for x in range(center_x - 4, center_x + 5)
                    for z in range(center_z - 4, center_z + 5)
                    if structure.blocks.get(
                        (x, roof_y, z), (stronghold.AIR,)
                    )[0]
                    != stronghold.AIR
                ]

                self.assertEqual(
                    [],
                    authored_roof,
                    (seed_index, access_floor_depth),
                )
                self.assertEqual(
                    "tf_slice:trophy_pedestal",
                    markers["trophyPedestal"]["block"],
                )
                self.assertEqual(25, len(markers["shieldWalls"]))
                self.assertTrue(validation["surfaceToBossWalkable"])

    def test_stronghold_loot_preserves_source_facing_states(self):
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            self.assertTrue(buffer.loot, seed_index)
            for loot in buffer.loot:
                self.assertEqual(3, len(loot), (seed_index, loot))
                self.assertIn(
                    "facing_direction",
                    loot[2],
                    (seed_index, loot),
                )

    def test_surface_entrance_exposes_the_source_access_gate(self):
        expected_stairs = {
            **{(-2, z): 1 for z in range(-1, 3)},
            **{(2, z): 0 for z in range(-2, 3)},
            **{(x, -2): 3 for x in range(-1, 2)},
            **{(x, 2): 2 for x in range(-1, 2)},
        }
        for seed_index in range(len(stronghold.FIXED_SOURCE_SEEDS)):
            structure, markers, _validation, _graph, _source_port = (
                stronghold.render_stronghold(seed_index, render_api())
            )
            ground_y = int(structure.surface_ground_y)
            entrance = markers["surfaceEntrance"]["offset"]
            center_x = int(entrance[0])
            center_z = int(entrance[2])

            pedestal = markers["trophyPedestal"]["offset"]
            pedestal_position = (
                int(pedestal[0]),
                int(pedestal[1]) + ground_y,
                int(pedestal[2]),
            )
            self.assertEqual(
                (center_x - 2, ground_y - 1, center_z - 2),
                pedestal_position,
                seed_index,
            )
            self.assertEqual(
                "tf_slice:trophy_pedestal",
                structure.blocks[pedestal_position][0],
                seed_index,
            )

            shield_positions = {
                (
                    int(offset[0]),
                    int(offset[1]) + ground_y,
                    int(offset[2]),
                )
                for offset in markers["shieldWalls"]
            }
            self.assertEqual(25, len(shield_positions), seed_index)
            self.assertEqual(
                {center_x + delta for delta in range(-2, 3)},
                {x for x, _y, _z in shield_positions},
                seed_index,
            )
            self.assertEqual(
                {center_z + delta for delta in range(-2, 3)},
                {z for _x, _y, z in shield_positions},
                seed_index,
            )
            self.assertEqual(
                {ground_y - 3},
                {y for _x, y, _z in shield_positions},
                seed_index,
            )
            self.assertTrue(
                all(
                    structure.blocks[position][0]
                    == "tf_slice:stronghold_shield"
                    for position in shield_positions
                ),
                seed_index,
            )

            for delta_x in range(-1, 2):
                for delta_z in range(-1, 2):
                    self.assertEqual(
                        stronghold.AIR,
                        structure.blocks[
                            (
                                center_x + delta_x,
                                ground_y,
                                center_z + delta_z,
                            )
                        ][0],
                        (seed_index, delta_x, delta_z),
                    )

            for (delta_x, delta_z), direction in expected_stairs.items():
                stair = structure.blocks[
                    (
                        center_x + delta_x,
                        ground_y - 2,
                        center_z + delta_z,
                    )
                ]
                self.assertEqual(
                    "minecraft:stone_brick_stairs",
                    stair[0],
                    (seed_index, delta_x, delta_z),
                )
                self.assertEqual(
                    direction,
                    stair[1]["weirdo_direction"],
                    (seed_index, delta_x, delta_z),
                )

            self.assertEqual(
                1,
                sum(
                    block[0] == "tf_slice:trophy_pedestal"
                    for block in structure.blocks.values()
                ),
                seed_index,
            )
            self.assertEqual(
                25,
                sum(
                    block[0] == "tf_slice:stronghold_shield"
                    for block in structure.blocks.values()
                ),
                seed_index,
            )

    def test_every_balcony_has_both_source_stair_flights(self):
        balconies = []
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            balconies.extend(
                (component, buffer)
                for component in graph.components
                if component.kind == "balcony_room"
            )
        self.assertTrue(balconies)
        for component, buffer in balconies:
            stairs = [
                position
                for position, block in buffer.blocks.items()
                if component.contains(position)
                and block[0] == "minecraft:stone_brick_stairs"
            ]
            self.assertGreaterEqual(len(stairs), 42, component.uid)

    def test_entrance_and_feature_rooms_keep_source_statue_silhouettes(self):
        exercised = set()
        required_fences = {
            "entrance": 16,
            "crossing": 12,
            "training_room": 10,
            "treasure_room": 10,
        }
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            for component in graph.components:
                minimum = required_fences.get(component.kind)
                if minimum is None:
                    continue
                exercised.add(component.kind)
                fences = sum(
                    block[0] == "minecraft:oak_fence"
                    for position, block in buffer.blocks.items()
                    if component.contains(position)
                )
                self.assertGreaterEqual(
                    fences,
                    minimum,
                    (component.uid, component.kind),
                )
        self.assertEqual(set(required_fences), exercised)

    def test_balcony_pillars_and_atrium_grass_match_source_scale(self):
        balconies = 0
        atriums = 0
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            for component in graph.components:
                if component.kind == "balcony_room":
                    balconies += 1
                    stairs = sum(
                        block[0] == "minecraft:stone_brick_stairs"
                        for position, block in buffer.blocks.items()
                        if component.contains(position)
                    )
                    self.assertGreater(stairs, 42, component.uid)
                elif component.kind == "atrium":
                    atriums += 1
                    grass = sum(
                        block[0]
                        == ruin_builder.LANDMARK_PROTECTED_GRASS_BLOCK
                        for position, block in buffer.blocks.items()
                        if component.contains(position)
                    )
                    self.assertGreaterEqual(grass, 16, component.uid)
                    self.assertLessEqual(grass, 36, component.uid)
        self.assertGreater(balconies, 0)
        self.assertGreater(atriums, 0)

    def test_atrium_floor_cannot_spawn_a_second_native_darkwood_tree(self):
        atriums = 0
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            for component in graph.components:
                if component.kind != "atrium":
                    continue
                atriums += 1
                guarded = 0
                for x in range(6, 12):
                    for z in range(6, 12):
                        block = buffer.blocks.get(
                            component.local_to_world(x, 0, z),
                            (stronghold.AIR,),
                        )[0]
                        self.assertNotEqual(
                            "minecraft:grass_block",
                            block,
                            (component.uid, x, z),
                        )
                        if block == ruin_builder.LANDMARK_PROTECTED_GRASS_BLOCK:
                            guarded += 1
                self.assertGreaterEqual(guarded, 16, component.uid)
        self.assertGreater(atriums, 0)

    def test_upper_graph_uses_an_eroded_surface_shell(self):
        bbox = stronghold._component_box(
            100,
            20,
            100,
            -2,
            -1,
            0,
            5,
            5,
            9,
            stronghold.SOUTH,
        )
        component = stronghold.Component(
            0,
            "upper_corridor",
            1,
            stronghold.SOUTH,
            bbox,
        )
        buffer = stronghold.RenderBuffer({})
        surface_y = component.bbox[1] + 1
        stronghold._render_upper_shell(buffer, component, surface_y)
        self.assertEqual(
            stronghold.AIR,
            buffer.blocks[component.local_to_world(2, 1, 2)][0],
        )
        self.assertNotEqual(
            stronghold.AIR,
            buffer.blocks[component.local_to_world(0, 1, 2)][0],
        )
        size_x, size_y, size_z = component.size
        possible = 0
        authored = 0
        for x in range(size_x):
            for y in range(size_y):
                for z in range(size_z):
                    position = component.local_to_world(x, y, z)
                    boundary = (
                        x in (0, size_x - 1)
                        or y in (0, size_y - 1)
                        or z in (0, size_z - 1)
                    )
                    if not boundary or position[1] <= surface_y:
                        continue
                    possible += 1
                    if buffer.blocks.get(
                        position, (stronghold.AIR,)
                    )[0] != stronghold.AIR:
                        authored += 1
        self.assertGreater(authored, 0)
        self.assertLess(authored, possible)

    def test_surface_upper_corridors_preserve_only_their_authored_air(self):
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            structure, markers, _validation, _room_graph, _source_port = (
                stronghold.render_stronghold(
                    seed_index,
                    render_api(),
                    access_floor_depth=2,
                )
            )
            surface_buffer = stronghold._compile_selected_buffer(
                graph,
                render_api(),
                stronghold._is_surface_component,
                access_floor_depth=2,
            )
            ground_y = int(structure.surface_ground_y)
            entrance_columns = set(structure.surface_access_columns)
            authored_surface_air = {
                structure.source_local_positions[position]
                for position, block in surface_buffer.blocks.items()
                if block[0] == stronghold.AIR
                and position in structure.source_local_positions
                and structure.source_local_positions[position][1] >= ground_y
                and (
                    structure.source_local_positions[position][0],
                    structure.source_local_positions[position][2],
                )
                not in entrance_columns
            }
            actual_surface_air = {
                position
                for position, block in structure.blocks.items()
                if block[0] == stronghold.AIR
                and position[1] >= ground_y
                and (position[0], position[2]) not in entrance_columns
            }

            self.assertGreater(len(authored_surface_air), 0, seed_index)
            self.assertEqual(
                authored_surface_air,
                actual_surface_air,
                seed_index,
            )

    def test_upper_ruins_never_clear_sky_or_leave_floating_islands(self):
        for seed_index, seed in enumerate(stronghold.FIXED_SOURCE_SEEDS):
            graph = stronghold.StrongholdGraph(seed)
            surface_y = (
                graph.access.local_to_world(4, 0, 4)[1]
                + stronghold.SOURCE_ACCESS_FLOOR_DEPTH
            )
            buffer = stronghold._compile_selected_buffer(
                graph,
                {},
                lambda component: component.kind.startswith("upper_"),
                access_floor_depth=2,
            )

            self.assertFalse(
                any(
                    position[1] > surface_y
                    and block[0] == stronghold.AIR
                    for position, block in buffer.blocks.items()
                ),
                seed_index,
            )

            solids = {
                position
                for position, block in buffer.blocks.items()
                if block[0] != stronghold.AIR
            }
            grounded = {
                position for position in solids if position[1] <= surface_y
            }
            reached = set(grounded)
            pending = collections.deque(grounded)
            while pending:
                x, y, z = pending.popleft()
                for neighbor in (
                    (x + 1, y, z),
                    (x - 1, y, z),
                    (x, y + 1, z),
                    (x, y - 1, z),
                    (x, y, z + 1),
                    (x, y, z - 1),
                ):
                    if neighbor in solids and neighbor not in reached:
                        reached.add(neighbor)
                        pending.append(neighbor)
            self.assertEqual(
                solids,
                reached,
                (seed_index, len(solids - reached)),
            )

    def test_atrium_bank_exercises_source_tree_families(self):
        leaf_families = set()
        atriums = 0
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            for component in graph.components:
                if component.kind != "atrium":
                    continue
                atriums += 1
                leaves = {
                    block[0]
                    for position, block in buffer.blocks.items()
                    if component.contains(position)
                    and (
                        block[0].endswith("_leaves")
                        or "rainbow_oak_leaves" in block[0]
                    )
                }
                self.assertEqual(1, len(leaves), component.uid)
                leaf_families.update(leaves)
        self.assertGreaterEqual(atriums, 4)
        self.assertGreaterEqual(len(leaf_families), 3)

    def test_foundry_uses_source_high_mass_and_inner_supports(self):
        foundries = 0
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            for component in graph.components:
                if component.kind != "foundry":
                    continue
                foundries += 1
                high_mass = sum(
                    buffer.blocks.get(
                        component.local_to_world(x, y, z),
                        (stronghold.AIR,),
                    )[0]
                    not in (stronghold.AIR, "minecraft:lava")
                    for x in range(4, 14)
                    for y in range(20, 23)
                    for z in range(4, 14)
                )
                self.assertGreater(high_mass, 0, component.uid)
                for x, z in ((1, 1), (16, 1), (1, 16), (16, 16)):
                    self.assertNotEqual(
                        stronghold.AIR,
                        buffer.blocks.get(
                            component.local_to_world(x, 10, z),
                            (stronghold.AIR,),
                        )[0],
                        (component.uid, x, z),
                    )
        self.assertEqual(len(stronghold.FIXED_SOURCE_SEEDS), foundries)

    def test_boss_room_restores_pillar_stairs_and_source_posts(self):
        bosses = 0
        torches = 0
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            for component in graph.components:
                if component.kind != "boss_room":
                    continue
                bosses += 1
                blocks = [
                    block[0]
                    for position, block in buffer.blocks.items()
                    if component.contains(position)
                ]
                self.assertGreaterEqual(
                    blocks.count("minecraft:stone_brick_stairs"),
                    70,
                    component.uid,
                )
                post_names = []
                for sarcophagus_x in (8, 13, 18):
                    for sarcophagus_z in (8, 15):
                        for post_x, post_z in (
                            (sarcophagus_x - 1, sarcophagus_z),
                            (sarcophagus_x + 1, sarcophagus_z),
                            (sarcophagus_x - 1, sarcophagus_z + 3),
                            (sarcophagus_x + 1, sarcophagus_z + 3),
                        ):
                            post_names.append(
                                buffer.blocks[
                                    component.local_to_world(
                                        post_x,
                                        2,
                                        post_z,
                                    )
                                ][0]
                            )
                self.assertEqual(24, len(post_names), component.uid)
                self.assertTrue(
                    all(
                        name
                        in ("minecraft:torch", "minecraft:cobblestone_wall")
                        for name in post_names
                    ),
                    component.uid,
                )
                torches += blocks.count("minecraft:torch")
        self.assertEqual(len(stronghold.FIXED_SOURCE_SEEDS), bosses)
        self.assertGreater(torches, 0)

    def test_surface_entrance_is_visible_and_connects_to_every_boss_room(self):
        for seed_index in range(len(stronghold.FIXED_SOURCE_SEEDS)):
            (
                _graph,
                _source,
                structure,
                markers,
                validation,
                _room_graph,
                _source_port,
                _translation,
            ) = self._rendered(seed_index)
            entrance = markers["surfaceEntrance"]["offset"]
            self.assertEqual(-2, entrance[1], seed_index)
            ground_y = int(structure.surface_ground_y)
            center_x = int(entrance[0])
            center_z = int(entrance[2])
            visible_access_ring = {
                (x, z)
                for x in range(center_x - 4, center_x + 5)
                for z in range(center_z - 4, center_z + 5)
                if structure.blocks.get(
                    (x, ground_y, z),
                    (stronghold.AIR,),
                )[0]
                != stronghold.AIR
            }
            # Upstream aligns the Access Chamber floor two blocks below the
            # terrain contact. At ground level only its 9x9 perimeter remains,
            # minus the four source doorway centers: 32 - 4 = 28 blocks.
            self.assertEqual(28, len(visible_access_ring), seed_index)
            self.assertTrue(
                all(
                    structure.blocks.get(
                        (x, ground_y, z),
                        (stronghold.AIR,),
                    )[0]
                    == stronghold.AIR
                    for x in range(center_x - 3, center_x + 4)
                    for z in range(center_z - 3, center_z + 4)
                ),
                seed_index,
            )
            self.assertEqual(
                -1,
                markers["trophyPedestal"]["offset"][1],
                seed_index,
            )
            self.assertEqual(
                {-3},
                {offset[1] for offset in markers["shieldWalls"]},
                seed_index,
            )
            self.assertEqual(
                0,
                sum(
                    1
                    for x in range(center_x - 4, center_x + 5)
                    for z in range(center_z - 4, center_z + 5)
                    if structure.blocks.get(
                        (x, ground_y + 2, z),
                        (stronghold.AIR,),
                    )[0]
                    != stronghold.AIR
                ),
                seed_index,
            )
            self.assertTrue(
                self._walkable_route(structure, markers),
                seed_index,
            )
            self.assertTrue(validation["surfaceToBossWalkable"])

    def test_stronghold_uses_the_source_random_underbrick_floor_palette(self):
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _entry, _columns = stronghold._compile_buffer(graph, {})
            self.assertNotIn(
                stronghold.FLOOR,
                {block[0] for block in buffer.blocks.values()},
            )

    def test_stronghold_bury_envelope_preserves_the_native_forest(self):
        structure, _markers, _validation, _graph, _source_port = (
            stronghold.render_stronghold(0, render_api())
        )
        envelope = ruin_builder._surface_native_envelope(
            structure,
            "knight_stronghold",
            environment_seed=271828,
        )
        integration = envelope.environment_integration
        self.assertEqual(0, integration["protectedColumns"])
        self.assertEqual(
            0,
            ruin_builder._surface_native_terrain_clearance(
                "knight_stronghold"
            ),
        )
        protected = {
            (x, z)
            for (x, y, z), block in envelope.blocks.items()
            if block[0] == ruin_builder.LANDMARK_PROTECTED_GRASS_BLOCK
            and y == structure.surface_ground_y
        }
        self.assertEqual(set(), protected)

        margin = ruin_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        expected_air = {
            (x + margin, y, z + margin)
            for (x, y, z), block in structure.blocks.items()
            if block[0] == stronghold.AIR
            and y > structure.surface_ground_y
        }
        actual_air = {
            (x, y, z)
            for (x, y, z), block in envelope.blocks.items()
            if block[0] == stronghold.AIR
            and y > structure.surface_ground_y
        }
        self.assertEqual(expected_air, actual_air)

    def test_surface_protection_preserves_the_authored_entrance(self):
        margin = ruin_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        for seed_index in range(len(stronghold.FIXED_SOURCE_SEEDS)):
            structure, markers, _validation, _graph, _source_port = (
                stronghold.render_stronghold(seed_index, render_api())
            )
            envelope = ruin_builder._surface_native_envelope(
                structure,
                "knight_stronghold",
                environment_seed=271828,
            )
            ground_y = structure.surface_ground_y
            authored_surface = {
                (x, y, z): block
                for (x, y, z), block in structure.blocks.items()
                if y == ground_y
            }
            self.assertTrue(authored_surface, seed_index)
            for (x, y, z), block in authored_surface.items():
                self.assertEqual(
                    block,
                    envelope.blocks[(x + margin, y, z + margin)],
                    (seed_index, x, y, z),
                )

            entrance = markers["surfaceEntrance"]["offset"]
            entrance_position = (
                int(entrance[0]) + margin,
                ground_y,
                int(entrance[2]) + margin,
            )
            self.assertEqual(
                stronghold.AIR,
                envelope.blocks[entrance_position][0],
                seed_index,
            )


if __name__ == "__main__":
    unittest.main()
