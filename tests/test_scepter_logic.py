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

import scepter_logic


class ScepterUseTests(unittest.TestCase):
    def test_twilight_scepter_has_99_charges_and_six_damage(self):
        state = scepter_logic.new_scepter_state("twilight_scepter")
        self.assertEqual(99, state["charges"])
        use = scepter_logic.use_twilight_scepter(state)
        self.assertTrue(use["used"])
        self.assertEqual(6.0, use["damage"])
        self.assertEqual(98, state["charges"])

    def test_empty_scepter_refuses_use(self):
        state = scepter_logic.new_scepter_state("twilight_scepter", 0)
        self.assertFalse(scepter_logic.use_twilight_scepter(state)["used"])

    def test_player_projectile_starts_in_front_of_first_person_camera(self):
        spawn = scepter_logic.player_projectile_spawn_position(
            (10.0, 64.0, -4.0), (0.0, 0.0, 1.0)
        )

        self.assertEqual((10.0, 65.55, -3.0), spawn)

    def test_player_projectile_muzzle_offset_follows_vertical_aim(self):
        spawn = scepter_logic.player_projectile_spawn_position(
            (10.0, 64.0, -4.0), (0.0, -1.0, 0.0)
        )

        self.assertEqual((10.0, 64.55, -4.0), spawn)

    def test_lifedrain_pulses_damage_and_healing_on_source_intervals(self):
        state = scepter_logic.new_scepter_state("lifedrain_scepter")
        damage = scepter_logic.lifedrain_tick(state, 5, True)
        self.assertEqual(1.0, damage["damage"])
        self.assertEqual(0.0, damage["healing"])
        self.assertEqual(98, state["charges"])

        healing = scepter_logic.lifedrain_tick(state, 10, True)
        self.assertEqual(1.0, healing["damage"])
        self.assertEqual(1.0, healing["healing"])
        self.assertEqual(1, healing["food"])
        self.assertEqual(97, state["charges"])

    def test_zombie_scepter_spawns_limited_life_strength_zombie(self):
        state = scepter_logic.new_scepter_state("zombie_scepter")
        result = scepter_logic.use_zombie_scepter(state, "owner")
        self.assertEqual("tf_slice:loyal_zombie", result["entity"])
        self.assertEqual("owner", result["ownerId"])
        self.assertEqual(1200, result["lifeTicks"])
        self.assertEqual(1, result["strengthAmplifier"])
        self.assertEqual(8, state["charges"])

    def test_lifedrain_selects_the_entity_under_the_crosshair(self):
        candidates = (
            ("near_off_axis", (1.0, 1.55, 2.0)),
            ("aimed", (0.1, 1.55, 8.0)),
        )

        target = scepter_logic.select_aimed_target(
            (0.0, 1.55, 0.0),
            (0.0, 0.0, 1.0),
            candidates,
        )

        self.assertEqual("aimed", target)

    def test_lifedrain_rejects_entities_outside_the_aim_beam(self):
        candidates = (
            ("behind", (0.0, 1.55, -2.0)),
            ("beside", (2.0, 1.55, 5.0)),
        )

        target = scepter_logic.select_aimed_target(
            (0.0, 1.55, 0.0),
            (0.0, 0.0, 1.0),
            candidates,
        )

        self.assertIsNone(target)

    def test_lifedrain_aim_beam_allows_normal_entity_height_variation(self):
        target = scepter_logic.select_aimed_target(
            (0.0, 1.55, 0.0),
            (0.0, 0.0, 1.0),
            (("adult_mob", (0.0, 0.75, 4.0)),),
        )

        self.assertEqual("adult_mob", target)

    def test_zombie_spawn_raycast_returns_last_open_cell_before_block(self):
        def block_name(position):
            return "minecraft:stone" if position[1] <= 0 else "minecraft:air"

        spawn = scepter_logic.raycast_spawn_position(
            (0.0, 2.0, 0.0),
            (0.0, -0.5, 1.0),
            block_name,
            max_distance=8.0,
        )

        self.assertEqual((0.5, 1.0, 1.5), spawn)

    def test_zombie_spawn_raycast_requires_a_solid_hit(self):
        spawn = scepter_logic.raycast_spawn_position(
            (0.0, 2.0, 0.0),
            (0.0, 0.0, 1.0),
            lambda _position: "minecraft:air",
            max_distance=8.0,
        )

        self.assertIsNone(spawn)


class FortificationTests(unittest.TestCase):
    def test_fortification_replenishes_five_temporary_shields(self):
        scepter = scepter_logic.new_scepter_state("fortification_scepter")
        shields = scepter_logic.new_shield_state()
        result = scepter_logic.use_fortification_scepter(scepter, shields)
        self.assertTrue(result["used"])
        self.assertEqual(5, shields["temporary"])
        self.assertEqual(240, shields["decayTimer"])
        self.assertEqual(1200, result["cooldown"])

    def test_shields_decay_and_have_twenty_tick_break_interval(self):
        shields = scepter_logic.new_shield_state(temporary=5)
        scepter_logic.tick_shields(shields, 239)
        self.assertEqual(5, shields["temporary"])
        scepter_logic.tick_shields(shields, 1)
        self.assertEqual(4, shields["temporary"])

        first = scepter_logic.break_shield(shields)
        second = scepter_logic.break_shield(shields)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(3, shields["temporary"])
        scepter_logic.tick_shields(shields, 20)
        self.assertTrue(scepter_logic.break_shield(shields))
        self.assertEqual(2, shields["temporary"])

    def test_break_cooldown_never_allows_damage_through_remaining_shields(self):
        shields = scepter_logic.new_shield_state(temporary=5)

        self.assertTrue(scepter_logic.has_shield(shields))
        self.assertTrue(scepter_logic.break_shield(shields))
        self.assertEqual(4, shields["temporary"])
        self.assertTrue(scepter_logic.has_shield(shields))
        self.assertFalse(scepter_logic.break_shield(shields))
        self.assertTrue(scepter_logic.has_shield(shields))

    def test_recharge_ingredients_are_locked_per_scepter(self):
        self.assertTrue(
            scepter_logic.can_recharge(
                "twilight_scepter", ["minecraft:ender_pearl"]
            )
        )
        self.assertTrue(
            scepter_logic.can_recharge(
                "lifedrain_scepter", ["minecraft:fermented_spider_eye"]
            )
        )
        self.assertTrue(
            scepter_logic.can_recharge(
                "zombie_scepter",
                ["minecraft:rotten_flesh", "minecraft:potion:strength"],
            )
        )
        self.assertTrue(
            scepter_logic.can_recharge(
                "fortification_scepter", ["minecraft:golden_apple"]
            )
        )


if __name__ == "__main__":
    unittest.main()
