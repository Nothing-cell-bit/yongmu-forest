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

import lich_logic


class FixedRandom(object):
    def __init__(self, values=None):
        self.values = list(values or [])

    def randrange(self, maximum):
        value = self.values.pop(0) if self.values else 0
        if value < 0 or value >= maximum:
            raise AssertionError("fixed value outside requested range")
        return value

    def triangular(self, low, high, mode):
        return 0.0

    def gauss(self, mean, deviation):
        return mean


class LichPhaseTests(unittest.TestCase):
    def test_only_worldgen_managed_lich_can_conquer_a_landmark(self):
        manual = lich_logic.new_lich_state()
        manual["worldgenManaged"] = False
        landmark = lich_logic.new_lich_state(spawner_spawned=True)
        landmark["worldgenManaged"] = True

        self.assertFalse(lich_logic.landmark_death_is_authoritative(manual))
        self.assertTrue(lich_logic.landmark_death_is_authoritative(landmark))

    def test_new_lich_matches_locked_source_stats(self):
        state = lich_logic.new_lich_state()
        self.assertEqual(100.0, state["health"])
        self.assertEqual(6, state["shieldStrength"])
        self.assertEqual(9, state["minionsRemaining"])
        self.assertEqual(0, state["attackCooldown"])
        self.assertEqual(0, state["spawnTime"])
        self.assertEqual(0, state["popCooldown"])
        self.assertEqual(0, state["nextAttackType"])
        self.assertEqual(lich_logic.PHASE_SHADOW, state["phase"])

        spawner_state = lich_logic.new_lich_state(spawner_spawned=True)
        self.assertEqual(40, spawner_state["attackCooldown"])
        self.assertEqual(20, spawner_state["spawnTime"])

    def test_target_range_is_source_monster_follow_distance(self):
        self.assertEqual(35.0, lich_logic.TARGET_RANGE)

    def test_phase_one_uses_the_locked_jar_shield_damage_tag(self):
        state = lich_logic.new_lich_state()
        blocked = lich_logic.resolve_incoming_damage(state, "melee", 20.0)
        self.assertEqual(0.0, blocked["healthDamage"])
        self.assertTrue(blocked["shieldContact"])
        self.assertEqual(6, state["shieldStrength"])

        weak = lich_logic.resolve_incoming_damage(
            state, "reflected_lich_bolt", 2.0
        )
        self.assertEqual(0, weak["shieldDamage"])
        self.assertEqual(6, state["shieldStrength"])

        reflected = lich_logic.resolve_incoming_damage(
            state, "reflected_lich_bolt", 6.0
        )
        self.assertEqual(1, reflected["shieldDamage"])
        self.assertEqual(5, state["shieldStrength"])

        for source_kind in (
            "magic",
            "indirect_magic",
            "sonic_boom",
            "twilight_scepter",
        ):
            before = state["shieldStrength"]
            result = lich_logic.resolve_incoming_damage(
                state, source_kind, 3.0
            )
            self.assertEqual(1, result["shieldDamage"])
            self.assertEqual(before - 1, state["shieldStrength"])

    def test_lich_owned_damage_is_ignored_and_bypass_damage_crosses_shield(self):
        state = lich_logic.new_lich_state()
        friendly = lich_logic.resolve_incoming_damage(
            state, "lich_owned", 50.0
        )
        self.assertFalse(friendly["accepted"])
        self.assertEqual(100.0, state["health"])
        bypass = lich_logic.resolve_incoming_damage(state, "bypass", 7.0)
        self.assertTrue(bypass["accepted"])
        self.assertEqual(93.0, state["health"])

    def test_shield_exhaustion_enters_minion_phase_and_caps_active_minions(self):
        state = lich_logic.new_lich_state()
        state["shieldStrength"] = 0
        lich_logic.refresh_phase(state)
        self.assertEqual(lich_logic.PHASE_MINION, state["phase"])

        state["spawnTime"] = 0
        state["attackCooldown"] = 16
        state["activeMinions"] = 2
        actions = lich_logic.advance_combat_tick(
            state, 10.0, True, FixedRandom([0])
        )
        self.assertIn("spawn_minion", [action["type"] for action in actions])
        self.assertEqual(3, state["activeMinions"])
        self.assertEqual(8, state["minionsRemaining"])

        state["attackCooldown"] = 16
        actions = lich_logic.advance_combat_tick(
            state, 10.0, True, FixedRandom([0])
        )
        self.assertNotIn("spawn_minion", [action["type"] for action in actions])

    def test_minion_budget_exhaustion_enters_melee_phase(self):
        state = lich_logic.new_lich_state()
        state.update(
            {
                "shieldStrength": 0,
                "minionsRemaining": 0,
                "activeMinions": 0,
            }
        )
        lich_logic.refresh_phase(state)
        self.assertEqual(lich_logic.PHASE_MELEE, state["phase"])

    def test_low_health_lich_winds_up_before_absorbing_a_minion(self):
        state = lich_logic.new_lich_state()
        state.update(
            {
                "shieldStrength": 0,
                "health": 42.0,
                "activeMinions": 2,
                "spawnTime": 0,
            }
        )
        actions = lich_logic.advance_combat_tick(
            state,
            10.0,
            True,
            FixedRandom([0]),
            minion_target={"id": "minion-1", "health": 11.5},
        )
        self.assertEqual(["start_absorb"], [a["type"] for a in actions])
        self.assertEqual(20, state["scepterTime"])
        self.assertEqual(42.0, state["health"])
        for _unused in range(20):
            actions = lich_logic.advance_combat_tick(
                state, 10.0, True, FixedRandom()
            )
        self.assertEqual(["absorb_minion"], [a["type"] for a in actions])
        self.assertEqual(53.5, state["health"])
        self.assertEqual(1, state["activeMinions"])
        self.assertEqual(40, state["popCooldown"])

    def test_pop_cast_heals_exactly_two_for_the_selected_poppable(self):
        state = lich_logic.new_lich_state()
        state["health"] = 80.0
        healed = lich_logic.add_pop_healing(state, 1)
        self.assertEqual(2.0, healed)
        self.assertEqual(82.0, state["health"])

    def test_absorb_goal_is_not_blocked_by_pop_mob_cooldown(self):
        state = lich_logic.new_lich_state()
        state.update(
            {
                "shieldStrength": 0,
                "health": 42.0,
                "activeMinions": 1,
                "popCooldown": 20,
                "spawnTime": 0,
            }
        )
        actions = lich_logic.advance_combat_tick(
            state,
            0.0,
            False,
            FixedRandom([0]),
            minion_target={"id": "minion-1", "health": 10.0},
            has_target=False,
        )
        self.assertEqual(["start_absorb"], [a["type"] for a in actions])

    def test_injured_lich_prioritizes_popping_tagged_mob_and_heals_two(self):
        state = lich_logic.new_lich_state()
        state.update({"health": 80.0, "spawnTime": 0})
        actions = lich_logic.advance_combat_tick(
            state,
            10.0,
            True,
            FixedRandom([0]),
            pop_target={"id": "zombie-1", "health": 20.0},
        )
        self.assertEqual(["start_pop"], [a["type"] for a in actions])
        for _unused in range(20):
            actions = lich_logic.advance_combat_tick(
                state, 10.0, True, FixedRandom()
            )
        self.assertEqual(["pop_mob"], [a["type"] for a in actions])
        self.assertEqual(82.0, state["health"])

    def test_pop_mob_cast_does_not_require_a_player_target(self):
        state = lich_logic.new_lich_state()
        state.update({"health": 80.0, "spawnTime": 0})
        actions = lich_logic.advance_combat_tick(
            state,
            0.0,
            False,
            FixedRandom([0]),
            pop_target={"id": "zombie-1", "health": 20.0},
            has_target=False,
        )
        self.assertEqual(["start_pop"], [a["type"] for a in actions])

    def test_shadow_teleport_and_clone_spawn_share_attack_cooldown_sixty(self):
        state = lich_logic.new_lich_state()
        state.update({"spawnTime": 0, "attackCooldown": 61})
        actions = lich_logic.advance_combat_tick(
            state, 10.0, True, FixedRandom()
        )
        self.assertEqual(
            ["teleport", "spawn_clone"],
            [action["type"] for action in actions],
        )
        self.assertEqual(1, state["cloneCount"])

    def test_spawn_windup_delays_first_attack_and_requests_candle_extinguish(self):
        state = lich_logic.new_lich_state(spawner_spawned=True)
        for _unused in range(19):
            actions = lich_logic.advance_combat_tick(
                state, 10.0, True, FixedRandom()
            )
            self.assertNotIn("shoot_bolt", [a["type"] for a in actions])
        self.assertEqual(1, state["spawnTime"])
        actions = lich_logic.advance_combat_tick(
            state, 10.0, True, FixedRandom()
        )
        self.assertIn("extinguish_candles", [a["type"] for a in actions])
        self.assertEqual(40, state["attackCooldown"])

    def test_melee_phase_chases_until_it_can_attack(self):
        state = lich_logic.new_lich_state()
        state.update(
            {
                "shieldStrength": 0,
                "minionsRemaining": 0,
                "activeMinions": 0,
                "spawnTime": 0,
            }
        )
        actions = lich_logic.advance_combat_tick(
            state, 8.0, True, FixedRandom()
        )
        self.assertEqual(["chase"], [action["type"] for action in actions])

    def test_clone_has_independent_source_attack_cycle(self):
        state = lich_logic.new_clone_state("boss-1", 61)
        actions = lich_logic.advance_clone_tick(
            state, 10.0, True, FixedRandom()
        )
        self.assertEqual(["teleport"], [action["type"] for action in actions])
        state["attackCooldown"] = 1
        actions = lich_logic.advance_clone_tick(
            state, 10.0, True, FixedRandom([0])
        )
        self.assertEqual(["shoot_bolt"], [action["type"] for action in actions])
        self.assertEqual(100, state["attackCooldown"])

    def test_persistent_state_round_trip_keeps_fight_budget_and_home(self):
        state = lich_logic.new_lich_state()
        state.update(
            {
                "health": 63.0,
                "shieldStrength": 2,
                "minionsRemaining": 4,
                "attackCooldown": 71,
                "popCooldown": 17,
                "spawnTime": 0,
                "nextAttackType": 1,
                "home": (10.5, 80.0, -3.5),
                "dimensionId": 33027004,
                "participants": set(["player-1"]),
            }
        )
        restored = lich_logic.restore_persistent_state(
            lich_logic.serialize_persistent_state(state)
        )
        for key in (
            "health",
            "shieldStrength",
            "minionsRemaining",
            "attackCooldown",
            "popCooldown",
            "spawnTime",
            "nextAttackType",
            "home",
            "dimensionId",
        ):
            self.assertEqual(state[key], restored[key])
        self.assertEqual(set(["player-1"]), restored["participants"])

    def test_hurt_teleport_probability_changes_in_phase_three(self):
        self.assertTrue(
            lich_logic.should_teleport_after_hurt(
                lich_logic.PHASE_SHADOW, FixedRandom([0])
            )
        )
        self.assertFalse(
            lich_logic.should_teleport_after_hurt(
                lich_logic.PHASE_SHADOW, FixedRandom([1])
            )
        )
        self.assertTrue(
            lich_logic.should_teleport_after_hurt(
                lich_logic.PHASE_MELEE, FixedRandom([0])
            )
        )
        self.assertFalse(
            lich_logic.should_teleport_after_hurt(
                lich_logic.PHASE_MELEE, FixedRandom([1])
            )
        )


class LichSpawnerAndProjectileTests(unittest.TestCase):
    def test_effect_damage_without_health_event_cause_is_still_magic(self):
        for attribute_type in (3, 4, 5):
            self.assertEqual(
                "magic",
                lich_logic.effect_damage_source_kind(None, attribute_type),
            )
        self.assertEqual(
            "magic", lich_logic.effect_damage_source_kind("magic", None)
        )
        self.assertIsNone(
            lich_logic.effect_damage_source_kind("entity_attack", 0)
        )

    def test_unreflected_lich_owned_bolt_cannot_break_its_master_shield(self):
        self.assertEqual(
            "lich_owned",
            lich_logic.lich_bolt_source_kind(False, True),
        )
        self.assertEqual(
            "reflected_lich_bolt",
            lich_logic.lich_bolt_source_kind(True, False),
        )

    def test_projectile_lifecycle_expires_and_removes_stalled_entities(self):
        moving = lich_logic.new_projectile_state(
            "bolt", "lich-1", 100, (0.5, 0.0, 0.0)
        )
        self.assertEqual(
            "keep",
            lich_logic.projectile_lifecycle_action(
                moving, 101, True, (0.5, 0.0, 0.0)
            ),
        )
        self.assertEqual(
            "destroy",
            lich_logic.projectile_lifecycle_action(
                moving, 100 + lich_logic.PROJECTILE_TTL_TICKS, True,
                (0.5, 0.0, 0.0),
            ),
        )

        stalled = lich_logic.new_projectile_state(
            "bolt", "lich-1", 200, (0.5, 0.0, 0.0)
        )
        self.assertEqual(
            "keep",
            lich_logic.projectile_lifecycle_action(
                stalled, 201, True, (0.0, 0.0, 0.0)
            ),
        )
        self.assertEqual(
            "destroy",
            lich_logic.projectile_lifecycle_action(
                stalled,
                201 + lich_logic.PROJECTILE_STALL_TICKS,
                True,
                (0.0, 0.0, 0.0),
            ),
        )

    def test_spawner_uses_nine_block_range_and_y_floor(self):
        spawner = (10.5, 80.5, 20.5)
        self.assertTrue(
            lich_logic.player_can_activate_spawner(
                (10.5, 80.0, 29.0), spawner
            )
        )
        self.assertFalse(
            lich_logic.player_can_activate_spawner(
                (10.5, 80.0, 30.0), spawner
            )
        )
        self.assertFalse(
            lich_logic.player_can_activate_spawner(
                (10.5, 76.4, 20.5), spawner
            )
        )

    def test_reflected_bolt_reassigns_owner_and_uses_source_speed(self):
        reflected = lich_logic.reflect_bolt(
            "player-1", (0.0, 0.0, 2.0)
        )
        self.assertEqual("player-1", reflected["ownerId"])
        self.assertEqual((0.0, 0.0, 1.5), reflected["velocity"])

    def test_source_projectile_aim_uses_half_speed_and_configured_inaccuracy(self):
        velocity = lich_logic.aim_projectile_velocity(
            (0.0, 0.0, 2.0), 0.5, 1.0, FixedRandom()
        )
        self.assertEqual((0.0, 0.0, 0.5), velocity)

    def test_death_tome_damage_and_slow_duration_match_difficulty(self):
        self.assertEqual(8.0, lich_logic.death_tome_incoming_damage(4.0, True))
        self.assertEqual(4.0, lich_logic.death_tome_incoming_damage(4.0, False))
        self.assertEqual(40, lich_logic.death_tome_slow_ticks(1))
        self.assertEqual(120, lich_logic.death_tome_slow_ticks(2))
        self.assertEqual(160, lich_logic.death_tome_slow_ticks(3))


if __name__ == "__main__":
    unittest.main()
