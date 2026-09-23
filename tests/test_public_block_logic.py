# -*- coding: utf-8 -*-
import math
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import public_block_logic


class PublicBlockLogicTests(unittest.TestCase):
    def test_floor_trophy_visual_yaw_uses_four_cardinal_directions(self):
        values = {
            public_block_logic.floor_trophy_visual_yaw(rotation)
            for rotation in (0, 4, 8, 12)
        }
        self.assertEqual(4, len(values))
        self.assertEqual(0.0, public_block_logic.floor_trophy_visual_yaw(0))
        self.assertEqual(90.0, public_block_logic.floor_trophy_visual_yaw(4))
        self.assertEqual(337.5, public_block_logic.floor_trophy_visual_yaw(15))

    def test_ur_ghast_entity_yaw_faces_the_same_way_as_block_trophies(self):
        self.assertEqual(
            [180.0, 270.0, 0.0, 90.0],
            [
                public_block_logic.ur_ghast_trophy_entity_yaw(value)
                for value in (0.0, 90.0, 180.0, 270.0)
            ],
        )

    def test_ur_ghast_floor_and_wall_fronts_point_back_to_player_on_both_axes(self):
        # Exercise the server's state-to-entity adapter, including native
        # placement fallback, rather than only comparing a list of yaw numbers.
        source = (BP / "TwilightBossSlice/serverSystem.py").read_text("utf-8")
        method = source[source.index("    def _ur_ghast_trophy_visual_yaw(") :]
        method = method[:method.index("\n    def ", 1)]
        namespace = {"public_block_logic": public_block_logic}
        exec(textwrap.dedent(method), namespace)
        visual_yaw = namespace["_ur_ghast_trophy_visual_yaw"]
        # Player look: south, west, north, east. Trophy must look back.
        cases = (
            (0, "south", (0, -1)),
            (90, "west", (1, 0)),
            (180, "north", (0, 1)),
            (270, "east", (-1, 0)),
        )
        for player_yaw, native_facing, expected_xz in cases:
            for wall in (False, True):
                for native_only in (False, True):
                    with self.subTest(yaw=player_yaw, wall=wall, native=native_only):
                        states = {"minecraft:cardinal_direction": native_facing}
                        if not native_only:
                            if wall:
                                states["tf_slice:facing"] = public_block_logic.facing_towards_player(player_yaw)
                            else:
                                states["tf_slice:rotation"] = public_block_logic.trophy_rotation_from_yaw(player_yaw)
                        block = "tf_slice:ur_ghast_" + ("wall_" if wall else "") + "trophy"
                        angle = math.radians(visual_yaw(block, states))
                        self.assertAlmostEqual(expected_xz[0], -math.sin(angle), places=6)
                        self.assertAlmostEqual(expected_xz[1], math.cos(angle), places=6)

    def test_wall_trophy_visual_yaw_matches_baked_block_rotation(self):
        self.assertEqual(0.0, public_block_logic.wall_trophy_visual_yaw("north"))
        self.assertEqual(90.0, public_block_logic.wall_trophy_visual_yaw("east"))
        self.assertEqual(180.0, public_block_logic.wall_trophy_visual_yaw("south"))
        self.assertEqual(270.0, public_block_logic.wall_trophy_visual_yaw("west"))

    def test_effective_trophy_states_fall_back_to_native_cardinal_direction(self):
        self.assertEqual(
            4,
            public_block_logic.effective_trophy_rotation(
                {"tf_slice:rotation": 0, "minecraft:cardinal_direction": "west"}
            ),
        )
        self.assertEqual(
            8,
            public_block_logic.effective_trophy_rotation(
                {"tf_slice:rotation": 7, "minecraft:cardinal_direction": "west"}
            ),
        )
        self.assertEqual(
            "east",
            public_block_logic.effective_trophy_facing(
                {"tf_slice:facing": "north", "minecraft:cardinal_direction": "west"}
            ),
        )

    def test_trophy_removal_uses_live_block_when_event_name_is_missing(self):
        live = "tf_slice:ur_ghast_trophy"
        self.assertEqual(
            live,
            public_block_logic.trophy_event_block_name("", live),
        )
        self.assertEqual(
            live,
            public_block_logic.trophy_event_block_name("minecraft:air", live),
        )
        self.assertEqual(
            "tf_slice:naga_trophy",
            public_block_logic.trophy_event_block_name(
                "tf_slice:naga_trophy", live
            ),
        )

    def test_trophy_stack_splits_one_item_into_an_empty_head_slot(self):
        carried = {
            "itemName": "tf_slice:hydra_trophy",
            "count": 3,
            "extraId": "named-trophy",
        }
        remaining, equipped = public_block_logic.split_trophy_for_head(
            carried, None
        )
        self.assertEqual(2, remaining["count"])
        self.assertEqual(1, equipped["count"])
        self.assertEqual("named-trophy", equipped["extraId"])

    def test_trophy_head_equip_rejects_occupied_slots_and_other_items(self):
        trophy = {"itemName": "tf_slice:naga_trophy", "count": 1}
        helmet = {"itemName": "minecraft:diamond_helmet", "count": 1}
        self.assertIsNone(
            public_block_logic.split_trophy_for_head(trophy, helmet)
        )
        self.assertIsNone(
            public_block_logic.split_trophy_for_head(
                {"itemName": "minecraft:stone", "count": 1}, None
            )
        )

    def test_trophy_facing_points_back_towards_the_placing_player(self):
        self.assertEqual("north", public_block_logic.facing_towards_player(0))
        self.assertEqual("east", public_block_logic.facing_towards_player(90))
        self.assertEqual("south", public_block_logic.facing_towards_player(180))
        self.assertEqual("west", public_block_logic.facing_towards_player(-90))

    def test_floor_trophy_rotation_quantizes_to_four_cardinal_angles(self):
        expected = {
            0.0: 0,
            22.5: 0,
            90.0: 4,
            180.0: 8,
            270.0: 12,
            -90.0: 12,
            359.0: 0,
        }
        for yaw, rotation in expected.items():
            self.assertEqual(
                rotation,
                public_block_logic.trophy_rotation_from_yaw(yaw),
                yaw,
            )

    def test_one_trophy_block_item_selects_floor_or_hidden_wall_variant(self):
        item = "tf_slice:hydra_trophy_item"
        self.assertEqual(
            "tf_slice:hydra_trophy",
            public_block_logic.trophy_block_for_face(item, 1),
        )
        self.assertEqual(
            "tf_slice:hydra_trophy",
            public_block_logic.trophy_block_for_face(item, 0),
        )
        for face in (2, 3, 4, 5):
            self.assertEqual(
                "tf_slice:hydra_wall_trophy",
                public_block_logic.trophy_block_for_face(item, face),
                face,
            )
        self.assertIsNone(
            public_block_logic.trophy_block_for_face(
                "tf_slice:hydra_wall_trophy", 2
            )
        )
        self.assertIsNone(
            public_block_logic.trophy_block_for_face("minecraft:stone", 1)
        )

    def test_trophy_items_have_distinct_ids_from_their_blocks(self):
        self.assertIn(
            "tf_slice:naga_trophy_item",
            public_block_logic.TROPHY_ITEM_NAMES,
        )
        self.assertNotIn(
            "tf_slice:naga_trophy",
            public_block_logic.TROPHY_ITEM_NAMES,
        )
        self.assertEqual(
            "tf_slice:naga_trophy",
            public_block_logic.TROPHY_ITEM_TO_BLOCK[
                "tf_slice:naga_trophy_item"
            ],
        )

    def test_huge_lily_layout_has_four_unique_rotated_quadrants(self):
        anchor = (10, 64, 20)
        expected_positions = {
            (10, 64, 20),
            (11, 64, 20),
            (10, 64, 21),
            (11, 64, 21),
        }
        for facing in ("north", "east", "south", "west"):
            layout = public_block_logic.huge_lily_layout(anchor, facing)
            self.assertEqual(4, len(layout))
            self.assertEqual(expected_positions, set(layout))
            self.assertEqual(
                {"nw", "ne", "se", "sw"},
                {entry["quadrant"] for entry in layout.values()},
            )
            self.assertEqual(
                {facing}, {entry["facing"] for entry in layout.values()}
            )

    def test_each_quadrant_can_recover_the_same_anchor(self):
        anchor = (3, 70, -8)
        for facing in ("north", "east", "south", "west"):
            layout = public_block_logic.huge_lily_layout(anchor, facing)
            for position, entry in layout.items():
                self.assertEqual(
                    anchor,
                    public_block_logic.huge_lily_anchor(
                        position, entry["quadrant"], facing
                    ),
                )

    def test_single_huge_lily_clearance_covers_a_three_by_three_area(self):
        anchor = (10, 64, 20)
        self.assertEqual(
            {
                (x, 64, z)
                for x in range(9, 12)
                for z in range(19, 22)
            },
            set(public_block_logic.huge_lily_single_clearance_positions(anchor)),
        )


if __name__ == "__main__":
    unittest.main()
