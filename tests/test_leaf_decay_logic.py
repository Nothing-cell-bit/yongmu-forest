# -*- coding: utf-8 -*-
"""Leaf-decay parity tests.

As a player, I want naturally generated Twilight leaves to decay after their
last supporting log is removed, while hand-placed and source-nondecaying
leaves remain available for building.
"""

import sys
import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import config, leaf_decay_logic


class LeafDecayClassificationTests(unittest.TestCase):
    def test_only_source_decayable_leaf_families_are_removed(self):
        self.assertTrue(
            leaf_decay_logic.is_decayable_leaf(
                "tf_slice:twilight_oak_leaves"
            )
        )
        self.assertTrue(
            leaf_decay_logic.is_decayable_leaf(
                "tf_slice:rainbow_oak_leaves_15"
            )
        )
        self.assertTrue(
            leaf_decay_logic.is_decayable_leaf(
                "tf_slice:enchanted_canopy_leaves"
            )
        )
        self.assertTrue(
            leaf_decay_logic.is_decayable_leaf(
                "tf_slice:spooky_twilight_oak_leaves"
            )
        )
        self.assertFalse(
            leaf_decay_logic.is_decayable_leaf("tf_slice:dark_leaves")
        )
        self.assertFalse(
            leaf_decay_logic.is_decayable_leaf(
                "tf_slice:hardened_dark_leaves"
            )
        )
        self.assertFalse(
            leaf_decay_logic.is_decayable_leaf("tf_slice:fallen_leaves")
        )

    def test_dark_leaves_bridge_distance_but_do_not_decay_themselves(self):
        self.assertTrue(
            leaf_decay_logic.is_connecting_leaf("tf_slice:dark_leaves")
        )
        self.assertFalse(
            leaf_decay_logic.is_connecting_leaf(
                "tf_slice:hardened_dark_leaves"
            )
        )

    def test_vanilla_leaves_bridge_support_without_entering_custom_decay(self):
        self.assertTrue(
            leaf_decay_logic.is_connecting_leaf("minecraft:oak_leaves")
        )
        self.assertFalse(
            leaf_decay_logic.is_decayable_leaf("minecraft:oak_leaves")
        )
        self.assertIn(
            "minecraft:oak_leaves",
            leaf_decay_logic.listener_block_ids(),
        )

    def test_twilight_and_vanilla_logs_support_leaves(self):
        for block_name in (
            "tf_slice:twilight_oak_log",
            "tf_slice:canopy_log",
            "tf_slice:mangrove_log",
            "minecraft:oak_log",
            "minecraft:dark_oak_wood",
            "minecraft:crimson_stem",
        ):
            self.assertTrue(
                leaf_decay_logic.is_support_log(block_name), block_name
            )
        self.assertFalse(
            leaf_decay_logic.is_support_log("tf_slice:towerwood")
        )


class LeafDistanceTests(unittest.TestCase):
    @staticmethod
    def _getter(world):
        return lambda position: {
            "name": world.get(tuple(position), "minecraft:air")
        }

    def test_leaf_is_supported_through_six_connected_leaf_blocks(self):
        world = {(0, 0, 0): "tf_slice:twilight_oak_log"}
        for x in range(1, 7):
            world[(x, 0, 0)] = "tf_slice:twilight_oak_leaves"

        self.assertTrue(
            leaf_decay_logic.is_leaf_supported(
                (6, 0, 0), self._getter(world)
            )
        )

    def test_seventh_leaf_block_is_outside_source_decay_distance(self):
        world = {(0, 0, 0): "tf_slice:twilight_oak_log"}
        for x in range(1, 8):
            world[(x, 0, 0)] = "tf_slice:twilight_oak_leaves"

        self.assertFalse(
            leaf_decay_logic.is_leaf_supported(
                (7, 0, 0), self._getter(world)
            )
        )

    def test_other_supported_tree_keeps_overlapping_canopy_alive(self):
        world = {
            (0, 0, 0): "tf_slice:twilight_oak_leaves",
            (1, 0, 0): "tf_slice:dark_leaves",
            (2, 0, 0): "minecraft:birch_log",
        }

        self.assertTrue(
            leaf_decay_logic.is_leaf_supported(
                (0, 0, 0), self._getter(world)
            )
        )

    def test_unloaded_block_view_defers_the_decision(self):
        def getter(_position):
            return None

        self.assertIsNone(
            leaf_decay_logic.is_leaf_supported((0, 0, 0), getter)
        )


class LeafDecayQueueTests(unittest.TestCase):
    def test_queue_keeps_earliest_due_tick_and_respects_tick_budget(self):
        queue = {}
        leaf_decay_logic.enqueue_candidate(queue, 7, (1, 2, 3), 40)
        leaf_decay_logic.enqueue_candidate(queue, 7, (1, 2, 3), 60)
        leaf_decay_logic.enqueue_candidate(queue, 7, (4, 5, 6), 30)
        leaf_decay_logic.enqueue_candidate(queue, 7, (7, 8, 9), 30)

        self.assertEqual(
            [(7, (4, 5, 6))],
            leaf_decay_logic.pop_due_candidates(queue, 30, 1),
        )
        self.assertEqual(2, len(queue))
        self.assertEqual(
            [(7, (7, 8, 9)), (7, (1, 2, 3))],
            leaf_decay_logic.pop_due_candidates(queue, 40, 8),
        )
        self.assertEqual({}, queue)

    def test_position_keys_round_trip_and_reject_malformed_save_data(self):
        key = leaf_decay_logic.position_key(33027004, (-3, 80, 17))
        self.assertEqual(
            (33027004, (-3, 80, 17)),
            leaf_decay_logic.parse_position_key(key),
        )
        self.assertIsNone(leaf_decay_logic.parse_position_key("broken"))


class LeafDecayPacingTests(unittest.TestCase):
    def test_visible_decay_uses_a_wide_ten_to_sixty_second_window(self):
        self.assertGreaterEqual(config.LEAF_DECAY_MIN_DELAY_TICKS, 200)
        self.assertGreaterEqual(config.LEAF_DECAY_MAX_DELAY_TICKS, 1200)

    def test_large_canopies_peak_at_four_removed_leaves_per_second(self):
        self.assertEqual(1, config.LEAF_DECAY_TICK_BUDGET)
        self.assertGreaterEqual(config.LEAF_DECAY_PROCESS_INTERVAL_TICKS, 5)
        self.assertTrue(
            leaf_decay_logic.is_decay_processing_tick(
                10, config.LEAF_DECAY_PROCESS_INTERVAL_TICKS
            )
        )
        self.assertFalse(
            leaf_decay_logic.is_decay_processing_tick(
                11, config.LEAF_DECAY_PROCESS_INTERVAL_TICKS
            )
        )


class LeafDecayDropTests(unittest.TestCase):
    def test_every_scripted_sapling_drop_exists_in_the_behavior_pack(self):
        declared = set()
        for path in (BP / "netease_blocks").glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            declared.add(
                document["minecraft:block"]["description"]["identifier"]
            )
        self.assertTrue(
            set(leaf_decay_logic.SAPLING_BY_LEAF.values()).issubset(declared)
        )

    def test_twilight_oak_leaf_uses_source_sapling_and_stick_chances(self):
        self.assertEqual(
            [
                {
                    "itemName": "tf_slice:twilight_oak_sapling",
                    "count": 1,
                    "auxValue": 0,
                },
                {"itemName": "minecraft:stick", "count": 2, "auxValue": 0},
            ],
            leaf_decay_logic.decay_drops(
                "tf_slice:twilight_oak_leaves",
                sapling_roll=0.049,
                stick_roll=0.019,
                stick_count_roll=0.9,
            ),
        )

    def test_rainbow_leaf_uses_source_lower_sapling_chance(self):
        self.assertEqual(
            [],
            leaf_decay_logic.decay_drops(
                "tf_slice:rainbow_oak_leaves_08",
                sapling_roll=0.03,
                stick_roll=0.5,
                stick_count_roll=0.0,
            ),
        )
        self.assertEqual(
            "tf_slice:rainbow_oak_sapling",
            leaf_decay_logic.decay_drops(
                "tf_slice:rainbow_oak_leaves_08",
                sapling_roll=0.02,
                stick_roll=0.5,
                stick_count_roll=0.0,
            )[0]["itemName"],
        )

    def test_existing_mangrove_sapling_uses_source_sapling_chance(self):
        self.assertEqual(
            [],
            leaf_decay_logic.decay_drops(
                "tf_slice:mangrove_leaves",
                sapling_roll=0.06,
                stick_roll=0.5,
                stick_count_roll=0.0,
            ),
        )
        self.assertEqual(
            "tf_slice:mangrove_sapling",
            leaf_decay_logic.decay_drops(
                "tf_slice:mangrove_leaves",
                sapling_roll=0.04,
                stick_roll=0.5,
                stick_count_roll=0.0,
            )[0]["itemName"],
        )


if __name__ == "__main__":
    unittest.main()
