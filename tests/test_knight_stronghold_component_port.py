# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import knight_stronghold_legacy_port as stronghold


class KnightStrongholdComponentPortTests(unittest.TestCase):
    def _corridor(self, direction):
        bbox = stronghold._component_box(
            100, 20, 100, -4, -1, 0, 9, 7, 18, direction
        )
        return stronghold.Component(
            0, "small_hallway", 1, direction, bbox
        )

    def test_local_to_world_matches_minecraft_structure_piece_rotation(self):
        expected_corners = {
            stronghold.SOUTH: ((96, 19, 100), (104, 25, 117)),
            stronghold.WEST: ((100, 19, 96), (83, 25, 104)),
            stronghold.NORTH: ((96, 19, 100), (104, 25, 83)),
            stronghold.EAST: ((100, 19, 96), (117, 25, 104)),
        }
        for direction, (origin, far_corner) in expected_corners.items():
            component = self._corridor(direction)
            self.assertEqual(origin, component.local_to_world(0, 0, 0))
            self.assertEqual(far_corner, component.local_to_world(8, 6, 17))

    def test_rotated_rectangles_keep_their_authored_local_dimensions(self):
        for direction in (
            stronghold.SOUTH,
            stronghold.WEST,
            stronghold.NORTH,
            stronghold.EAST,
        ):
            self.assertEqual((9, 7, 18), self._corridor(direction).size)

    def test_each_rotated_shell_stays_inside_its_source_bounding_box(self):
        for direction in (
            stronghold.SOUTH,
            stronghold.WEST,
            stronghold.NORTH,
            stronghold.EAST,
        ):
            component = self._corridor(direction)
            buffer = stronghold.RenderBuffer({})
            stronghold._render_shell(buffer, component)
            outside = [
                position
                for position in buffer.blocks
                if not component.contains(position)
            ]
            self.assertEqual([], outside, (direction, outside[:8]))

    def test_surface_entrance_is_the_source_access_chamber_not_a_ladder_shaft(self):
        graph = stronghold.StrongholdGraph(stronghold.FIXED_SOURCE_SEEDS[0])
        buffer, surface_entry, surface_columns = stronghold._compile_buffer(
            graph, {}
        )
        access = graph.access
        self.assertEqual((9, 5, 9), access.size)
        self.assertEqual(access.local_to_world(4, 0, 4), surface_entry)
        self.assertEqual(
            {
                access.local_to_world(x, -1, z)
                for x in range(2, 7)
                for z in range(2, 7)
            },
            set(buffer.shields),
        )
        self.assertFalse(
            any(value[0] == "minecraft:ladder" for value in buffer.blocks.values())
        )
        self.assertEqual(
            {
                (position[0], position[2])
                for position in (
                    access.local_to_world(x, 0, z)
                    for x in range(9)
                    for z in range(9)
                )
            },
            set(surface_columns),
        )

    def test_parent_and_child_doorways_are_adjacent_not_written_outside_parent(self):
        graph = stronghold.StrongholdGraph(stronghold.FIXED_SOURCE_SEEDS[0])
        for left, right in graph.edges:
            if (left, right) == (graph.entrance.uid, graph.access.uid):
                continue
            parent = graph.components[left]
            child = graph.components[right]
            parent_doors = {
                parent.local_to_world(*door) for door in parent.doors
            }
            child_doors = {
                child.local_to_world(*door) for door in child.doors
            }
            connected = [
                (parent_door, child_door)
                for parent_door in parent_doors
                for child_door in child_doors
                if parent_door[1] == child_door[1]
                and abs(parent_door[0] - child_door[0])
                + abs(parent_door[2] - child_door[2]) == 1
            ]
            self.assertTrue(
                connected,
                (left, parent.kind, right, child.kind),
            )
            self.assertTrue(
                all(parent.contains(position) for position in parent_doors),
                (left, parent.kind, parent.doors),
            )

    def test_recursive_limits_and_boss_weight_match_locked_source(self):
        boss_rule = next(
            rule for rule in stronghold.PIECE_RULES if rule[0] == "boss_room"
        )
        self.assertEqual(("boss_room", 15, 1, 4), boss_rule)
        source = (TOOLS / "knight_stronghold_legacy_port.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("parent.index + 1 > 30", source)
        self.assertIn("> 75", source)
        self.assertNotIn("> 112", source)

    def test_every_compiled_room_edge_has_two_open_adjacent_door_planes(self):
        for seed in stronghold.FIXED_SOURCE_SEEDS:
            graph = stronghold.StrongholdGraph(seed)
            buffer, _surface_entry, _surface_columns = (
                stronghold._compile_buffer(graph, {})
            )
            for left, right in graph.edges:
                if (left, right) == (graph.entrance.uid, graph.access.uid):
                    continue
                parent = graph.components[left]
                child = graph.components[right]
                parent_doors = {
                    parent.local_to_world(*door) for door in parent.doors
                }
                child_doors = {
                    child.local_to_world(*door) for door in child.doors
                }
                pairs = [
                    (parent_door, child_door)
                    for parent_door in parent_doors
                    for child_door in child_doors
                    if parent_door[1] == child_door[1]
                    and abs(parent_door[0] - child_door[0])
                    + abs(parent_door[2] - child_door[2]) == 1
                ]
                self.assertTrue(pairs, (left, right))
                self.assertTrue(
                    any(
                        all(
                            buffer.blocks.get(
                                (door[0], door[1] + dy, door[2]),
                                (stronghold.AIR,),
                            )[0]
                            == stronghold.AIR
                            for door in pair
                            for dy in (0, 1)
                        )
                        for pair in pairs
                    ),
                    (left, parent.kind, right, child.kind),
                )

            # AccessChamber -> Entrance is vertical and intentionally blocked
            # only by the removable 5x5 shield plane.
            shaft_x, _shaft_y, shaft_z = graph.access.local_to_world(4, 0, 4)
            shield_y = graph.access.local_to_world(4, -1, 4)[1]
            self.assertEqual(
                "tf_slice:stronghold_shield",
                buffer.blocks[(shaft_x, shield_y, shaft_z)][0],
            )
            for y in range(graph.entrance.bbox[4] - 1, graph.access.bbox[1] + 3):
                if y != shield_y:
                    self.assertEqual(
                        stronghold.AIR,
                        buffer.blocks.get(
                            (shaft_x, y, shaft_z), (stronghold.AIR,)
                        )[0],
                    )


if __name__ == "__main__":
    unittest.main()
