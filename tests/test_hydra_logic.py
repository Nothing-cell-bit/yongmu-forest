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

import hydra_logic


class FixedRandom(object):
    def __init__(self, values=None):
        self.values = list(values or [])

    def randint(self, lower, upper):
        value = self.values.pop(0) if self.values else lower
        if value < lower or value > upper:
            raise AssertionError("fixed value outside requested range")
        return value


class HydraDamageTests(unittest.TestCase):
    def test_locked_stats_and_head_budget(self):
        self.assertEqual(360.0, hydra_logic.MAX_HEALTH)
        self.assertEqual(511, hydra_logic.XP_REWARD)
        self.assertEqual(7, hydra_logic.MAX_HEADS)
        self.assertEqual(3, hydra_logic.INITIAL_ACTIVE_HEADS)
        self.assertEqual(12.0, hydra_logic.ROOT_COLLISION_HEIGHT)
        self.assertEqual(10.2, hydra_logic.HYDRA_EYE_HEIGHT)
        self.assertEqual(120.0, hydra_logic.HEAD_DAMAGE_THRESHOLD)

    def test_source_sensing_ray_starts_at_the_full_hydra_eye_height(self):
        self.assertEqual(
            (520.5, 73.2, 504.5),
            hydra_logic.hydra_eye_position((520.5, 63.0, 504.5)),
        )

    def test_part_actor_health_is_only_a_nonlethal_damage_proxy(self):
        self.assertGreater(
            hydra_logic.PART_ACTOR_HEALTH,
            hydra_logic.HEAD_DAMAGE_THRESHOLD * hydra_logic.MAX_HEADS,
        )

    def test_one_swing_cannot_settle_overlapping_parts_twice(self):
        self.assertTrue(
            hydra_logic.can_settle_part_impact(None, None, 80, "player")
        )
        self.assertFalse(
            hydra_logic.can_settle_part_impact(80, "player", 80, "player")
        )
        self.assertTrue(
            hydra_logic.can_settle_part_impact(80, "player", 80, "other")
        )
        self.assertTrue(
            hydra_logic.can_settle_part_impact(80, "player", 81, "player")
        )

    def test_all_parts_share_the_source_living_entity_hurt_window(self):
        first = hydra_logic.shared_hurt_resolution(10.0, 0.0, None, 100)
        self.assertEqual(10.0, first["healthDamage"])
        self.assertEqual(10.0, first["lastHurtAmount"])
        self.assertEqual(100, first["windowStartTick"])

        repeated = hydra_logic.shared_hurt_resolution(
            10.0, first["lastHurtAmount"], first["windowStartTick"], 101
        )
        self.assertEqual(0.0, repeated["healthDamage"])
        self.assertEqual(10.0, repeated["lastHurtAmount"])
        self.assertEqual(100, repeated["windowStartTick"])

        stronger = hydra_logic.shared_hurt_resolution(15.0, 10.0, 100, 102)
        self.assertEqual(5.0, stronger["healthDamage"])
        self.assertEqual(15.0, stronger["lastHurtAmount"])
        self.assertEqual(100, stronger["windowStartTick"])

        weaker = hydra_logic.shared_hurt_resolution(7.0, 15.0, 100, 103)
        self.assertEqual(0.0, weaker["healthDamage"])
        self.assertEqual(15.0, weaker["lastHurtAmount"])
        self.assertEqual(100, weaker["windowStartTick"])

        boundary = hydra_logic.shared_hurt_resolution(10.0, 15.0, 100, 110)
        self.assertEqual(10.0, boundary["healthDamage"])
        self.assertEqual(10.0, boundary["lastHurtAmount"])
        self.assertEqual(110, boundary["windowStartTick"])

    def test_zero_damage_does_not_open_or_replace_the_shared_hurt_window(self):
        result = hydra_logic.shared_hurt_resolution(0.0, 8.0, 100, 105)
        self.assertEqual(0.0, result["healthDamage"])
        self.assertEqual(8.0, result["lastHurtAmount"])
        self.assertEqual(100, result["windowStartTick"])

    def test_body_and_closed_head_take_one_eighth_damage(self):
        self.assertEqual(6.0, hydra_logic.accepted_damage(48.0, "body", False))
        self.assertEqual(6.0, hydra_logic.accepted_damage(48.0, "head", False))
        self.assertEqual(48.0, hydra_logic.accepted_damage(48.0, "head", True))
        self.assertEqual(0.0, hydra_logic.accepted_damage(3.9, "neck", False))
        self.assertEqual(1.0, hydra_logic.accepted_damage(4.0, "neck", False))
        self.assertEqual(7, hydra_logic.head_damage_credit(7.9))

    def test_dead_head_and_one_extra_dead_slot_respawn_after_one_hundred_ticks(self):
        heads = [True, True, False, False, False, False, False]
        result = hydra_logic.respawn_heads(heads, killed_index=1, dead_ticks=100)
        self.assertTrue(result[1])
        self.assertEqual(3, sum(1 for alive in result if alive))

    def test_locked_respawn_counter_only_decrements_after_a_head_is_dead(self):
        self.assertEqual(
            (100, False),
            hydra_logic.advance_respawn_counter("dying", 100),
        )
        self.assertEqual(
            (99, False),
            hydra_logic.advance_respawn_counter("dead", 100),
        )
        self.assertEqual(
            (-1, True),
            hydra_logic.advance_respawn_counter("dead", 1),
        )
        self.assertEqual(
            (-1, False),
            hydra_logic.advance_respawn_counter("dead", -1),
        )

    def test_cut_head_and_extra_dormant_head_use_independent_source_timeline(self):
        killed_state = "dying"
        killed_ticks = 0
        killed_counter = hydra_logic.HEAD_RESPAWN_TICKS
        extra_state = "dead"
        extra_counter = hydra_logic.HEAD_RESPAWN_TICKS
        extra_born_at = None
        killed_born_at = None

        for world_tick in range(1, 181):
            extra_counter, extra_born = hydra_logic.advance_respawn_counter(
                extra_state, extra_counter
            )
            if extra_born and extra_born_at is None:
                extra_born_at = world_tick

            killed_counter, killed_born = hydra_logic.advance_respawn_counter(
                killed_state, killed_counter
            )
            if killed_born and killed_born_at is None:
                killed_born_at = world_tick

            killed_ticks += 1
            if killed_state == "dying" and killed_ticks >= hydra_logic.STATE_DURATIONS["dying"]:
                killed_state = "dead"
                killed_ticks = 0

        self.assertEqual(100, extra_born_at)
        self.assertEqual(170, killed_born_at)

    def test_regeneration_starts_only_after_one_thousand_ticks(self):
        self.assertEqual(0.0, hydra_logic.heal_amount(1000))
        self.assertEqual(1.0, hydra_logic.heal_amount(1005))
        self.assertEqual(1.0, hydra_logic.heal_amount(1010))

    def test_dormant_heads_do_not_enter_the_respawn_timer_at_birth(self):
        active = hydra_logic.initial_head_state(0)
        dormant = hydra_logic.initial_head_state(3)
        self.assertEqual(
            {"alive": True, "state": "idle", "dead_ticks": -1}, active
        )
        self.assertEqual(
            {"alive": False, "state": "dead", "dead_ticks": -1}, dormant
        )
        self.assertEqual(-1, hydra_logic.next_dead_ticks(-1))
        self.assertEqual(100, hydra_logic.next_dead_ticks(99))


class HydraHeadStateTests(unittest.TestCase):
    def test_regrown_head_mouth_follows_one_continuous_birth_curve(self):
        brain = hydra_logic.HydraHeadBrain("born", 0)
        previous_state = "dead"
        samples = []

        while True:
            before = brain.state
            active_state = brain.tick()
            if active_state != before:
                previous_state = before
            samples.append(
                (
                    active_state,
                    hydra_logic.interpolated_head_pose(
                        previous_state,
                        active_state,
                        3,
                        brain.ticks,
                    )[3],
                )
            )
            if active_state == "idle" and brain.ticks == 9:
                break

        born = [value for state, value in samples if state == "born"]
        opening = [
            value
            for state, value in samples
            if state in ("roar_start", "roar")
        ]
        closing = [value for state, value in samples if state == "idle"]

        self.assertEqual({0.0}, set(born))
        self.assertEqual(sorted(opening), opening)
        self.assertEqual(sorted(closing, reverse=True), closing)
        values = [value for unused_state, value in samples]
        self.assertLessEqual(
            max(abs(after - before) for before, after in zip(values, values[1:])),
            0.100001,
        )

    def test_bite_state_contract_has_exact_boundaries(self):
        brain = hydra_logic.HydraHeadBrain()
        brain.begin("bite")
        observed = []
        for _ in range(40 + 80 + 7 + 40):
            observed.append(brain.tick())
        self.assertEqual("bite_begin", observed[0])
        self.assertEqual("bite_ready", observed[39])
        self.assertEqual("biting", observed[119])
        self.assertEqual("bite_end", observed[126])
        self.assertEqual("cooldown", brain.state)

    def test_bite_victim_is_only_settled_once_during_seven_tick_window(self):
        victims = set()
        self.assertTrue(hydra_logic.register_attack_victim(victims, "player"))
        self.assertFalse(hydra_logic.register_attack_victim(victims, "player"))
        self.assertEqual({"player"}, victims)

    def test_flame_and_mortar_damage_contract(self):
        self.assertEqual(48.0, hydra_logic.BITE_DAMAGE)
        self.assertEqual(19.0, hydra_logic.FLAME_DAMAGE)
        self.assertEqual(18.0, hydra_logic.MORTAR_DAMAGE)
        self.assertEqual(4.0, hydra_logic.mortar_blast_power(True))
        self.assertEqual(0.1, hydra_logic.mortar_blast_power(False))

    def test_mortar_reflection_transfers_owner_and_motion(self):
        reflected = hydra_logic.reflect_mortar(
            old_owner="hydra", player="player", look=(0.0, 0.0, 1.0)
        )
        self.assertEqual("player", reflected["owner"])
        self.assertEqual((0.0, 0.0, 1.5), reflected["motion"])
        self.assertEqual(20, reflected["added_fuse"])
        self.assertAlmostEqual(0.1, reflected["inaccuracy"])

    def test_death_timeline_settles_exactly_once_at_tick_two_hundred(self):
        self.assertFalse(hydra_logic.death_event(199)["settle"])
        self.assertTrue(hydra_logic.death_event(200)["settle"])
        self.assertFalse(hydra_logic.death_event(201)["settle"])

    def test_primary_attack_selection_matches_source_ranges_and_rolls(self):
        self.assertEqual(
            "bite",
            hydra_logic.choose_primary_attack(
                0, 6.0, False, 3, 0.0, 0, 99, 159
            ),
        )
        self.assertEqual(
            "flame",
            hydra_logic.choose_primary_attack(
                4, 12.0, False, 4, 0.0, 9, 0, 159
            ),
        )
        self.assertEqual(
            "mortar",
            hydra_logic.choose_primary_attack(
                2, 24.0, False, 3, 0.0, 9, 99, 0
            ),
        )
        self.assertIsNone(
            hydra_logic.choose_primary_attack(
                2, 24.0, True, 3, 0.0, 9, 99, 0
            )
        )

    def test_secondary_heads_use_the_source_ten_and_sixteen_rolls(self):
        self.assertEqual(
            "flame",
            hydra_logic.choose_secondary_attack(1, 12.0, True, 0, 15),
        )
        self.assertEqual(
            "mortar",
            hydra_logic.choose_secondary_attack(6, 24.0, True, 9, 0),
        )
        self.assertIsNone(
            hydra_logic.choose_secondary_attack(0, 12.0, True, 0, 0)
        )
        self.assertIsNone(
            hydra_logic.choose_secondary_attack(2, 12.0, False, 0, 0)
        )

    def test_attack_concurrency_counts_bites_as_three_heads(self):
        self.assertEqual(
            5.0,
            hydra_logic.attack_weight(
                ["biting", "flaming", "mortar_shoot", "idle"]
            ),
        )
        self.assertFalse(hydra_logic.can_start_attack(3, 2.0, 0.3))
        self.assertTrue(hydra_logic.can_start_attack(7, 2.0, 0.3))
        self.assertEqual(
            0.0,
            hydra_logic.attack_weight(
                ["bite_end", "flame_end", "mortar_end", "cooldown"]
            ),
        )

    def test_mortar_fuse_only_burns_while_grounded(self):
        self.assertEqual(80, hydra_logic.mortar_fuse_after_tick(80, False))
        self.assertEqual(79, hydra_logic.mortar_fuse_after_tick(80, True))

    def test_mortar_launch_uses_locked_pitch_offset_speed_and_inaccuracy(self):
        clean = hydra_logic.mortar_launch_motion(
            pitch=0.0, yaw=0.0, triangular_noise=(0.0, 0.0, 0.0)
        )
        self.assertAlmostEqual(0.0, clean[0], places=6)
        self.assertAlmostEqual(0.171010, clean[1], places=6)
        self.assertAlmostEqual(0.469846, clean[2], places=6)
        self.assertAlmostEqual(
            0.5, sum(value * value for value in clean) ** 0.5, places=6
        )

        scattered = hydra_logic.mortar_launch_motion(
            pitch=0.0, yaw=0.0, triangular_noise=(1.0, -1.0, 0.5)
        )
        self.assertNotEqual(clean, scattered)
        self.assertAlmostEqual(
            0.5, sum(value * value for value in scattered) ** 0.5, places=6
        )

    def test_mortar_fires_at_source_ticks_zero_ten_and_twenty_only(self):
        self.assertEqual(
            [0, 10, 20],
            [tick for tick in range(26) if hydra_logic.mortar_shot_ticks(tick)],
        )

    def test_flame_selects_nearest_entity_intersecting_head_look_ray(self):
        candidates = (
            ("behind", (0.0, 0.0, -2.0), 0.6),
            ("off_axis", (4.0, 0.0, 5.0), 0.6),
            ("far", (0.2, 0.0, 12.0), 0.6),
            ("near", (0.1, 0.0, 6.0), 0.6),
        )
        self.assertEqual(
            "near",
            hydra_logic.flame_ray_target(
                (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), candidates
            ),
        )

    def test_head_turning_is_bounded_to_five_degrees_per_tick(self):
        self.assertEqual(5.0, hydra_logic.approach_angle(0.0, 90.0, 5.0))
        self.assertEqual(-5.0, hydra_logic.approach_angle(0.0, -90.0, 5.0))
        self.assertAlmostEqual(181.0, hydra_logic.approach_angle(179.0, -179.0, 5.0))
        self.assertAlmostEqual(-181.0, hydra_logic.approach_angle(-179.0, 179.0, 5.0))


class HydraModelPlacementTests(unittest.TestCase):
    def test_rest_head_offsets_match_locked_java_pose(self):
        expected = (
            (0.0, 9.062178, 3.5),
            (-7.675817, 4.562834, 4.431635),
            (7.675817, 4.562834, 4.431635),
            (-5.142301, 9.128356, 0.0),
            (5.142301, 9.128356, 0.0),
            (-8.86327, 1.437166, 0.0),
            (8.86327, 1.437166, 0.0),
        )
        for index, wanted in enumerate(expected):
            actual = hydra_logic.rest_head_offset(index)
            for observed, target in zip(actual, wanted):
                self.assertAlmostEqual(target, observed, places=5)

    def test_each_head_uses_five_neck_segments_from_head_to_body_anchor(self):
        segments = hydra_logic.rest_neck_segment_offsets(0)
        self.assertEqual(5, len(segments))
        self.assertEqual((0.0, 3.0, -1.0), segments[-1])
        self.assertAlmostEqual(0.0, segments[0][0], places=6)
        self.assertAlmostEqual(9.062178, segments[0][1], places=5)
        self.assertAlmostEqual(2.5, segments[0][2], places=6)
        for before, after in zip(segments, segments[1:]):
            self.assertLess(after[1], before[1])

    def test_side_neck_roots_include_the_locked_per_head_yaw(self):
        expected = (
            (0.0, 3.0, -1.0),
            (-3.0, 3.0, -1.0),
            (3.0, 3.0, -1.0),
            (-1.414214, 3.0, -2.828427),
            (1.414214, 3.0, -2.828427),
            (-2.828427, 3.0, -4.242641),
            (2.828427, 3.0, -4.242641),
        )
        for index, wanted in enumerate(expected):
            actual = hydra_logic.neck_root_offset(index)
            for observed, target in zip(actual, wanted):
                self.assertAlmostEqual(target, observed, places=5)

    def test_neck_transforms_interpolate_source_position_yaw_and_pitch(self):
        transforms = hydra_logic.neck_segment_transforms(
            start=(0.0, 3.0, -1.0),
            end=(0.0, 9.062178, 3.5),
            start_yaw=0.0,
            end_yaw=60.0,
            end_pitch=-20.0,
        )
        self.assertEqual(5, len(transforms))
        self.assertEqual((0.0, 3.0, -1.0), transforms[-1][0])
        self.assertEqual((0.0, 0.0), transforms[-1][1])
        self.assertEqual((-20.0, 60.0), transforms[0][1])
        self.assertAlmostEqual(0.813798, transforms[0][0][0], places=5)
        self.assertAlmostEqual(8.720158, transforms[0][0][1], places=5)
        self.assertAlmostEqual(3.030154, transforms[0][0][2], places=5)

    def test_looking_down_retracts_neck_endpoint_by_locked_one_block(self):
        transforms = hydra_logic.neck_segment_transforms(
            start=(0.0, 0.0, 0.0),
            end=(0.0, 5.0, 4.0),
            start_yaw=0.0,
            end_yaw=0.0,
            end_pitch=30.0,
        )
        self.assertAlmostEqual(3.0, transforms[0][0][2], places=6)

    def test_active_heads_use_locked_bounded_sinusoidal_sway(self):
        pose = hydra_logic.head_pose("idle", 0)
        animated = hydra_logic.animated_head_pose(pose, 0, 20, True)
        self.assertAlmostEqual(
            60.0 + __import__("math").sin(1.0) * 3.0 / __import__("math").pi,
            animated[0],
            places=6,
        )
        self.assertAlmostEqual(
            __import__("math").sin(2.0) * 5.0,
            animated[1],
            places=6,
        )
        self.assertEqual(pose, hydra_logic.animated_head_pose(pose, 0, 20, False))

    def test_flame_particle_sample_leaves_the_mouth_along_source_velocity(self):
        position = hydra_logic.flame_particle_position(
            mouth=(1.0, 2.0, 3.0),
            direction=(0.0, 0.0, 1.0),
            gaussian_noise=(0.0, 0.0, 0.0),
            spread=5.0,
            speed=2.0,
            age=1.5,
        )
        self.assertEqual((1.0, 2.0, 6.0), position)

    def test_flame_particle_sample_preserves_locked_gaussian_cone(self):
        position = hydra_logic.flame_particle_position(
            mouth=(0.0, 0.0, 0.0),
            direction=(0.0, 0.0, 1.0),
            gaussian_noise=(1.0, -1.0, 0.5),
            spread=5.0,
            speed=1.0,
            age=1.0,
        )
        self.assertEqual((0.0375, -0.0375, 1.01875), position)

    def test_flame_visual_samples_span_the_long_lived_source_stream(self):
        ages = hydra_logic.flame_visual_sample_ages(8, phase=0.5)
        self.assertEqual(8, len(ages))
        self.assertGreaterEqual(min(ages), 0.5)
        self.assertGreaterEqual(max(ages), 10.0)
        self.assertEqual(sorted(ages), list(ages))

    def test_flame_candidates_keep_retained_target_and_online_players(self):
        self.assertEqual(
            ["nearby", "retained", "online"],
            hydra_logic.merge_flame_candidate_ids(
                ["nearby", "retained"],
                "retained",
                ["online", "nearby"],
            ),
        )

    def test_neck_visual_rotation_preserves_segment_yaw_for_the_bedrock_actor(self):
        self.assertEqual(
            (-20.0, 60.0),
            hydra_logic.neck_visual_rotation((-20.0, 60.0)),
        )

    def test_attack_head_poses_match_locked_java_state_table(self):
        self.assertEqual(
            (30.0, 60.0, 9.0, 1.0),
            hydra_logic.head_pose("flaming", 1),
        )
        self.assertEqual(
            (-5.0, -30.0, 5.0, 0.2),
            hydra_logic.head_pose("biting", 0),
        )
        self.assertEqual(
            (0.0, -180.0, 4.0, 0.0),
            hydra_logic.head_pose("dead", 2),
        )

    def test_state_pose_interpolation_drives_position_and_mouth(self):
        pose = hydra_logic.interpolated_head_pose(
            "flame_begin", "flaming", 0, 50, 100
        )
        self.assertEqual((47.5, 0.0, 8.0, 0.875), pose)
        offset = hydra_logic.head_offset_for_pose(pose)
        self.assertGreater(offset[1], 8.0)
        self.assertGreater(offset[2], 5.0)

    def test_source_bite_pitch_offset_cannot_accumulate_into_head_spins(self):
        pitch = 0.0
        for unused_tick in range(80):
            pitch = hydra_logic.approach_angle(pitch, 0.0, 5.0)
            pitch = hydra_logic.bite_pitch_degrees(pitch)
            self.assertAlmostEqual(__import__("math").pi / 4.0, pitch, places=12)


if __name__ == "__main__":
    unittest.main()
