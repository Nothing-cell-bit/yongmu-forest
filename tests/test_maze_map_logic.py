# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
)
sys.path.insert(0, str(PACKAGE_ROOT))

import maze_map_logic


class MazeMapTests(unittest.TestCase):
    def test_identity_round_trip(self):
        encoded = maze_map_logic.encode_identity(
            "labyrinth:4:7", 128, 37, -256
        )
        self.assertEqual(
            ("labyrinth:4:7", 128, 37, -256),
            maze_map_logic.decode_identity(encoded),
        )
        self.assertIsNone(maze_map_logic.decode_identity("tfmm:v3:1:2:3"))

    def test_compiled_passages_translate_to_one_block_pixels(self):
        record = maze_map_logic.create_record("0,0", (55, 8, 55), 8)
        snapshot = maze_map_logic.build_snapshot(
            record,
            [[5, 4, 7]],
            (0, 0),
            (55, 8, 55),
        )
        self.assertEqual("maze", snapshot["mapKind"])
        self.assertEqual(1, snapshot["blocksPerPixel"])
        self.assertEqual([], snapshot["biomeRuns"])
        self.assertIn([14, 13, 16, "clearing"], maze_map_logic.snapshot_runs(
            [[5, 4, 7]], (0, 0), (55, 55),
        ))
        self.assertEqual("same", snapshot["verticalMarker"])

    def test_map_identity_is_center_snapped_and_one_block_per_pixel(self):
        record = maze_map_logic.create_record(
            labyrinth_id="labyrinth:4:7",
            center=(128, 32, -64),
            player_y=31,
        )
        self.assertEqual("maze", record["mapKind"])
        self.assertEqual("labyrinth:4:7", record["labyrinthId"])
        self.assertEqual(32, record["yCenter"])
        self.assertEqual(1, record["blocksPerPixel"])
        self.assertEqual(128, record["width"])
        self.assertEqual(128, record["height"])

    def test_only_passages_within_three_blocks_of_floor_are_visible(self):
        blocks = [
            (0, 28, 0, "mazestone"),
            (0, 29, 0, "air"),
            (1, 35, 0, "air"),
            (2, 36, 0, "air"),
        ]
        pixels = maze_map_logic.visible_passages(blocks, y_center=32)
        self.assertIn((0, 0), pixels)
        self.assertIn((1, 0), pixels)
        self.assertNotIn((2, 0), pixels)

    def test_cross_floor_marker_reports_up_and_down(self):
        self.assertEqual("up", maze_map_logic.vertical_marker(40, 32))
        self.assertEqual("down", maze_map_logic.vertical_marker(20, 32))
        self.assertEqual("same", maze_map_logic.vertical_marker(34, 32))


if __name__ == "__main__":
    unittest.main()
