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

import labyrinth_logic
import maze_slime_logic
import minotaur_logic
import ruin_worldgen_logic


class LabyrinthLayoutTests(unittest.TestCase):
    def test_route_megastructures_never_auto_backfill_old_chunks(self):
        for kind in ("labyrinth", "hydra_lair"):
            self.assertFalse(
                ruin_worldgen_logic.allows_automatic_route_placement(
                    kind, "new_chunk"
                )
            )
            self.assertTrue(
                ruin_worldgen_logic.allows_automatic_route_placement(
                    kind, "surface_feature"
                )
            )
            self.assertFalse(
                ruin_worldgen_logic.allows_automatic_route_placement(
                    kind, "loaded_chunk_backfill"
                )
            )
            self.assertFalse(
                ruin_worldgen_logic.allows_automatic_route_placement(
                    kind, "player_proximity_backfill"
                )
            )
            self.assertFalse(
                ruin_worldgen_logic.allows_automatic_route_placement(
                    kind, "surface_watchdog"
                )
            )
        self.assertTrue(
            ruin_worldgen_logic.allows_automatic_route_placement(
                "naga_courtyard", "loaded_chunk_backfill"
            )
        )

    def test_eight_layouts_are_deterministic_and_two_levels_each(self):
        first = [labyrinth_logic.build_layout(seed) for seed in range(8)]
        second = [labyrinth_logic.build_layout(seed) for seed in range(8)]
        self.assertEqual(first, second)
        for layout in first:
            self.assertEqual((110, 110), tuple(layout["size_xz"]))
            self.assertEqual(2, len(layout["levels"]))
            self.assertTrue(layout["connected"])

    def test_level_room_contract_matches_locked_source(self):
        layout = labyrinth_logic.build_layout(0)
        self.assertEqual(
            sorted(["entrance", "exit", "collapse", "collapse", "fountain", "spawner_chest", "spawner_chest"]),
            sorted(layout["levels"][0]["rooms"]),
        )
        self.assertEqual(
            sorted(["entrance", "minoshroom", "mushroom", "mushroom", "vault", "spawner_chest", "spawner_chest"]),
            sorted(layout["levels"][1]["rooms"]),
        )

    def test_controlled_spawn_pool_preserves_weights_and_groups(self):
        self.assertEqual(
            [
                ("minotaur", 20, 2, 3),
                ("cave_spider", 10, 1, 2),
                ("creeper", 10, 1, 2),
                ("maze_slime", 10, 2, 4),
                ("enderman", 1, 1, 2),
                ("fire_beetle", 10, 1, 2),
                ("slime_beetle", 10, 1, 2),
                ("pinch_beetle", 10, 1, 1),
            ],
            labyrinth_logic.SPAWN_POOL,
        )

    def test_marker_catalog_covers_boss_chests_spawns_and_map_center(self):
        self.assertEqual(
            frozenset(("boss", "chest", "spawn_zone", "map_center")),
            labyrinth_logic.REQUIRED_MARKER_KINDS,
        )


class MinotaurAndMinoshroomTests(unittest.TestCase):
    def test_source_melee_reach_uses_attacker_and_target_widths(self):
        self.assertAlmostEqual(
            2.56,
            minotaur_logic.melee_attack_reach_sq(0.7, 0.6),
        )
        self.assertAlmostEqual(
            8.44,
            minotaur_logic.melee_attack_reach_sq(1.4, 0.6),
        )

    def test_melee_attacks_immediately_then_once_per_source_cooldown(self):
        cooldown = 0
        attack_ticks = []
        for tick in range(41):
            cooldown, attack = minotaur_logic.advance_melee(
                cooldown,
                has_target=True,
                target_in_range=True,
                special_active=False,
            )
            if attack:
                attack_ticks.append(tick)
        self.assertEqual(20, minotaur_logic.MELEE_COOLDOWN_TICKS)
        self.assertEqual([0, 20, 40], attack_ticks)

    def test_melee_is_blocked_without_a_close_target_or_during_specials(self):
        cases = (
            dict(has_target=False, target_in_range=True, special_active=False),
            dict(has_target=True, target_in_range=False, special_active=False),
            dict(has_target=True, target_in_range=True, special_active=True),
        )
        for case in cases:
            cooldown, attack = minotaur_logic.advance_melee(0, **case)
            self.assertEqual(0, cooldown)
            self.assertFalse(attack)

    def test_server_owned_melee_preserves_source_damage(self):
        self.assertEqual(
            5.0,
            minotaur_logic.melee_damage(False),
        )
        self.assertEqual(
            7.0,
            minotaur_logic.melee_damage(True),
        )

    def test_melee_only_targets_living_players_in_attackable_modes(self):
        self.assertTrue(minotaur_logic.can_target_player(0, True, True))
        self.assertTrue(minotaur_logic.can_target_player(2, True, True))
        for game_type in (1, 3, 6):
            self.assertFalse(
                minotaur_logic.can_target_player(game_type, True, True)
            )
        self.assertFalse(minotaur_logic.can_target_player(0, False, True))
        self.assertFalse(minotaur_logic.can_target_player(0, True, False))

    def test_spawn_weapon_matches_the_locked_java_equipment_rule(self):
        self.assertEqual(
            "tf_slice:diamond_minotaur_axe",
            minotaur_logic.spawn_weapon(True, 9, 0.0),
        )
        self.assertEqual(
            "tf_slice:gold_minotaur_axe",
            minotaur_logic.spawn_weapon(False, 0, 0.0),
        )
        self.assertEqual(
            "minecraft:golden_axe",
            minotaur_logic.spawn_weapon(False, 1, 0.0),
        )
        self.assertEqual(
            "tf_slice:gold_minotaur_axe",
            minotaur_logic.spawn_weapon(False, 2, 2.0),
        )
        self.assertEqual(
            "minecraft:golden_axe",
            minotaur_logic.spawn_weapon(False, 3, 2.0),
        )

    def test_minotaur_source_stats_and_charge_start_predicates(self):
        self.assertEqual(30.0, minotaur_logic.MINOTAUR_HEALTH)
        eligible = dict(
            is_minoshroom=False,
            on_ground=True,
            has_line_of_sight=True,
            random_roll=0,
        )
        self.assertTrue(minotaur_logic.can_start_charge(16.0, **eligible))
        self.assertTrue(minotaur_logic.can_start_charge(64.0, **eligible))
        self.assertFalse(minotaur_logic.can_start_charge(15.99, **eligible))
        self.assertFalse(minotaur_logic.can_start_charge(64.01, **eligible))
        self.assertFalse(
            minotaur_logic.can_start_charge(
                25.0, **dict(eligible, on_ground=False)
            )
        )
        self.assertFalse(
            minotaur_logic.can_start_charge(
                25.0, **dict(eligible, has_line_of_sight=False)
            )
        )
        self.assertFalse(
            minotaur_logic.can_start_charge(
                25.0, **dict(eligible, random_roll=1)
            )
        )

    def test_minoshroom_charge_uses_source_squared_range_bonus(self):
        eligible = dict(
            is_minoshroom=True,
            on_ground=True,
            has_line_of_sight=True,
            random_roll=0,
        )
        self.assertFalse(minotaur_logic.can_start_charge(24.99, **eligible))
        self.assertTrue(minotaur_logic.can_start_charge(25.0, **eligible))
        self.assertTrue(minotaur_logic.can_start_charge(73.0, **eligible))
        self.assertFalse(minotaur_logic.can_start_charge(73.01, **eligible))

    def test_charge_windup_and_speed_contract(self):
        self.assertEqual((15, 44), minotaur_logic.CHARGE_WINDUP_RANGE)
        self.assertEqual(15, minotaur_logic.charge_windup(0))
        self.assertEqual(44, minotaur_logic.charge_windup(29))
        self.assertAlmostEqual(1.5, minotaur_logic.CHARGE_SPEED)
        self.assertAlmostEqual(2.1, minotaur_logic.CHARGE_OVERSHOOT)

    def test_charge_timeline_attacks_once_and_cleans_up(self):
        state = minotaur_logic.start_charge(0, (6.1, 64.0, 0.0), "player")
        attacks = 0
        navigations = 0
        for tick in range(18):
            state, actions = minotaur_logic.advance_charge(
                state,
                navigation_done=(tick >= 16),
                target_in_range=(tick >= 14),
            )
            attacks += int(actions["attack"])
            navigations += int(actions["navigate"])
        self.assertEqual(1, attacks)
        self.assertEqual(1, navigations)
        self.assertEqual("stopped", state["phase"])
        self.assertTrue(actions["clear_charging"])

    def test_minoshroom_ground_attack_contract(self):
        self.assertEqual(120.0, minotaur_logic.MINOSHROOM_HEALTH)
        self.assertEqual(100, minotaur_logic.MINOSHROOM_XP_REWARD)
        self.assertEqual(20.0, minotaur_logic.MINOSHROOM_HOME_RADIUS)
        self.assertTrue(minotaur_logic.can_start_slam(2.0, True, True, 0, 0))
        self.assertTrue(minotaur_logic.can_start_slam(9.0, True, True, 0, 0))
        self.assertFalse(minotaur_logic.can_start_slam(1.99, True, True, 0, 0))
        self.assertFalse(minotaur_logic.can_start_slam(9.01, True, True, 0, 0))
        self.assertFalse(minotaur_logic.can_start_slam(4.0, False, True, 0, 0))
        self.assertFalse(minotaur_logic.can_start_slam(4.0, True, True, 1, 0))
        self.assertTrue(minotaur_logic.can_start_slam(4.0, True, False, 0, 0))
        self.assertFalse(minotaur_logic.can_start_slam(4.0, True, False, 20, 0))
        self.assertEqual((200, 399), minotaur_logic.SLAM_COOLDOWN_RANGE)
        self.assertEqual((30, 59), minotaur_logic.SLAM_WINDUP_RANGE)
        self.assertEqual(
            ((-7.5, 0.0, -7.5), (7.5, 3.0, 7.5)),
            minotaur_logic.ground_attack_bounds((0, 64, 0), relative=True),
        )
        self.assertEqual(0.5, minotaur_logic.ground_attack_damage(1.0, True))
        self.assertEqual(0.0, minotaur_logic.ground_attack_damage(1.0, False))

    def test_slam_timeline_has_source_windup_and_one_impact(self):
        state = minotaur_logic.start_slam(0, 0, "player")
        impacts = 0
        for _ in range(32):
            state, actions = minotaur_logic.advance_slam(state)
            impacts += int(actions["impact"])
        self.assertEqual(1, impacts)
        self.assertEqual("stopped", state["phase"])
        self.assertTrue(actions["clear_ground_attack"])

    def test_slam_visual_recovery_lasts_the_source_six_ticks(self):
        self.assertEqual(6, minotaur_logic.SLAM_RECOVERY_TICKS)
        remaining = minotaur_logic.SLAM_RECOVERY_TICKS
        observed = []
        cleared = []
        for _ in range(minotaur_logic.SLAM_RECOVERY_TICKS):
            remaining, should_clear = minotaur_logic.advance_slam_recovery(
                remaining
            )
            observed.append(remaining)
            cleared.append(should_clear)
        self.assertEqual([5, 4, 3, 2, 1, 0], observed)
        self.assertEqual([False, False, False, False, False, True], cleared)
        self.assertEqual(
            (0, False), minotaur_logic.advance_slam_recovery(0)
        )


class MazeSlimeBehaviorTests(unittest.TestCase):
    def test_spawn_size_uses_vanilla_power_of_two_roll_and_local_upgrade(self):
        self.assertEqual(1, maze_slime_logic.spawn_size(0, 1.0, 0.0))
        self.assertEqual(2, maze_slime_logic.spawn_size(1, 1.0, 0.0))
        self.assertEqual(4, maze_slime_logic.spawn_size(2, 0.0, 1.0))
        self.assertEqual(2, maze_slime_logic.spawn_size(0, 0.0, 1.0))
        self.assertEqual(4, maze_slime_logic.spawn_size(1, 0.0, 1.0))

    def test_source_size_stats_include_double_health_and_extra_xp(self):
        self.assertEqual(
            {"health": 32, "damage": 4, "collision": 2.08, "xp": 7},
            maze_slime_logic.size_stats(4),
        )
        self.assertEqual(
            {"health": 8, "damage": 2, "collision": 1.04, "xp": 5},
            maze_slime_logic.size_stats(2),
        )
        self.assertEqual(
            {"health": 2, "damage": 1, "collision": 0.52, "xp": 4},
            maze_slime_logic.size_stats(1),
        )

    def test_split_plan_halves_size_and_stops_at_tiny_slimes(self):
        self.assertEqual([2, 2], maze_slime_logic.split_plan(4, 0))
        self.assertEqual([1, 1, 1, 1], maze_slime_logic.split_plan(2, 2))
        self.assertEqual([], maze_slime_logic.split_plan(1, 2))


if __name__ == "__main__":
    unittest.main()
