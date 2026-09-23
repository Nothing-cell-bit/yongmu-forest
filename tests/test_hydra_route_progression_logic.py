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

import route_progression_logic


class RouteProgressionTests(unittest.TestCase):
    def test_v1_progress_migrates_without_losing_naga_or_lich(self):
        migrated = route_progression_logic.migrate_progress(
            {"tf_naga_defeated": True, "tf_lich_defeated": True}
        )
        self.assertEqual(3, migrated["version"])
        self.assertTrue(migrated["naga_defeated"])
        self.assertTrue(migrated["lich_defeated"])
        self.assertFalse(migrated["meef_stroganoff_eaten"])
        self.assertFalse(migrated["minoshroom_defeated"])
        self.assertFalse(migrated["hydra_defeated"])
        self.assertFalse(migrated["trophy_pedestal_activated"])
        self.assertFalse(migrated["knight_phantoms_defeated"])
        self.assertFalse(migrated["ghast_trap_activated"])
        self.assertFalse(migrated["ur_ghast_defeated"])

    def test_fire_swamp_unlock_depends_on_lich_and_stroganoff_not_kill_credit(self):
        base = route_progression_logic.default_progress()
        base["lich_defeated"] = True
        base["meef_stroganoff_eaten"] = True
        self.assertTrue(route_progression_logic.can_enter_fire_swamp(base))
        self.assertFalse(base["minoshroom_defeated"])

    def test_biome_penalties_keep_original_timing(self):
        self.assertEqual(
            {"effect": "hunger", "duration": 100, "amplifier": 3},
            route_progression_logic.biome_penalty(
                "swamp", route_progression_logic.default_progress(), 2
            ),
        )
        self.assertEqual(
            {"effect": "fire", "seconds": 8},
            route_progression_logic.biome_penalty(
                "fire_swamp", route_progression_logic.default_progress(), 0
            ),
        )
        self.assertIsNone(
            route_progression_logic.biome_penalty(
                "swamp", {"lich_defeated": True}, 0
            )
        )

    def test_charms_choose_highest_tier_and_keep_exact_slots(self):
        inventory = list(range(36))
        tier, slots = route_progression_logic.keeping_charm_snapshot(
            inventory=inventory,
            armor=["helmet", "chest", "legs", "boots"],
            offhand="shield",
            selected_hotbar_slot=4,
            charm_counts={1: 2, 2: 1, 3: 0},
        )
        self.assertEqual(2, tier)
        self.assertEqual(list(range(9)), slots["inventory_slots"])
        self.assertEqual("shield", slots["offhand"])
        self.assertEqual(["helmet", "chest", "legs", "boots"], slots["armor"])

    def test_tier_one_keeps_only_selected_hotbar_slot(self):
        tier, slots = route_progression_logic.keeping_charm_snapshot(
            inventory=list(range(36)),
            armor=[],
            offhand=None,
            selected_hotbar_slot=7,
            charm_counts={1: 1},
        )
        self.assertEqual(1, tier)
        self.assertEqual([7], slots["inventory_slots"])

    def test_fire_react_probability_duration_and_thorns_conflict(self):
        self.assertAlmostEqual(0.45, route_progression_logic.fire_react_chance(3))
        self.assertEqual(2, route_progression_logic.fire_react_seconds(1, 0))
        self.assertEqual(8, route_progression_logic.fire_react_seconds(3, 2))
        self.assertFalse(
            route_progression_logic.can_apply_fire_react({"minecraft:thorns": 1})
        )


if __name__ == "__main__":
    unittest.main()
