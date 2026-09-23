# -*- coding: utf-8 -*-
import math
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
)
sys.path.insert(0, str(PACKAGE_ROOT))

import naga_logic


class FixedRandom(object):
    def __init__(self, integers=None, floats=None):
        self.integers = list(integers or [])
        self.floats = list(floats or [])

    def randint(self, lower, upper):
        value = self.integers.pop(0) if self.integers else lower
        if value < lower or value > upper:
            raise AssertionError("fixed integer outside requested range")
        return value

    def random(self):
        return self.floats.pop(0) if self.floats else 0.0


class NagaStatsTests(unittest.TestCase):
    def test_original_health_by_difficulty(self):
        self.assertEqual(120.0, naga_logic.max_health_for_difficulty(1))
        self.assertEqual(200.0, naga_logic.max_health_for_difficulty(2))
        self.assertEqual(250.0, naga_logic.max_health_for_difficulty(3))

    def test_head_and_body_contact_damage_do_not_scale_with_difficulty(self):
        self.assertEqual(5.0, naga_logic.head_damage_for_difficulty(1))
        self.assertEqual(5.0, naga_logic.head_damage_for_difficulty(2))
        self.assertEqual(5.0, naga_logic.head_damage_for_difficulty(3))
        self.assertEqual(2.0, naga_logic.body_damage_for_difficulty(1))
        self.assertEqual(2.0, naga_logic.body_damage_for_difficulty(2))
        self.assertEqual(2.0, naga_logic.body_damage_for_difficulty(3))

    def test_segment_collision_hurts_all_living_entities_and_triples_animal_damage(self):
        self.assertEqual(2.0, naga_logic.segment_collision_damage(False))
        self.assertEqual(6.0, naga_logic.segment_collision_damage(True))

    def test_segments_follow_original_health_formula(self):
        self.assertEqual(12, naga_logic.segment_count(200.0, 200.0))
        self.assertEqual(12, naga_logic.segment_count(120.0, 200.0))
        self.assertEqual(10, naga_logic.segment_count(100.0, 200.0))
        self.assertEqual(10, naga_logic.segment_count(100.0, 250.0))
        self.assertEqual(2, naga_logic.segment_count(1.0, 200.0))
        self.assertEqual(0, naga_logic.segment_count(0.0, 200.0))

    def test_original_melee_reach_uses_naga_and_target_width(self):
        self.assertAlmostEqual(
            16.6,
            naga_logic.attack_reach_squared(2.0, 0.6),
            places=4,
        )

    def test_melee_knockback_uses_naga_yaw_instead_of_target_radial_vector(self):
        self.assertEqual((0.0, 2.0), naga_logic.melee_push_vector(0.0))
        east = naga_logic.melee_push_vector(90.0)
        self.assertAlmostEqual(-2.0, east[0], places=4)
        self.assertAlmostEqual(0.0, east[1], places=4)

    def test_segment_collision_requires_actual_two_block_aabb_overlap(self):
        self.assertTrue(
            naga_logic.collision_boxes_overlap(
                (0.0, 64.0, 0.0),
                (2.0, 2.0),
                (1.29, 64.0, 0.0),
                (0.6, 1.8),
            )
        )
        self.assertFalse(
            naga_logic.collision_boxes_overlap(
                (0.0, 64.0, 0.0),
                (2.0, 2.0),
                (1.31, 64.0, 0.0),
                (0.6, 1.8),
            )
        )
        self.assertFalse(
            naga_logic.collision_boxes_overlap(
                (0.0, 64.0, 0.0),
                (2.0, 2.0),
                (0.0, 66.01, 0.0),
                (0.6, 1.8),
            )
        )

    def test_shorter_naga_moves_faster(self):
        self.assertAlmostEqual(0.52, naga_logic.speed_for_segments(12), places=4)
        self.assertAlmostEqual(0.54, naga_logic.speed_for_segments(6), places=4)
        self.assertAlmostEqual(0.62, naga_logic.speed_for_segments(2), places=4)

    def test_stunless_chance_rises_as_health_falls(self):
        self.assertEqual(0.0, naga_logic.stunless_chance(200.0, 200.0, 2))
        self.assertAlmostEqual(
            0.35, naga_logic.stunless_chance(100.0, 200.0, 2), places=4
        )
        self.assertEqual(0.5, naga_logic.stunless_chance(1.0, 200.0, 3))


class NagaMovementTests(unittest.TestCase):
    def test_short_chain_holds_when_the_head_only_rotates_in_place(self):
        self.assertTrue(
            naga_logic.short_chain_should_hold(
                3,
                (0.0, 64.0, 0.0),
                (0.03, 64.0, 0.02),
                naga_logic.CIRCLE,
            )
        )
        self.assertFalse(
            naga_logic.short_chain_should_hold(
                4,
                (0.0, 64.0, 0.0),
                (0.03, 64.0, 0.02),
                naga_logic.CIRCLE,
            )
        )
        self.assertFalse(
            naga_logic.short_chain_should_hold(
                2,
                (0.0, 64.0, 0.0),
                (0.2, 64.0, 0.0),
                naga_logic.CIRCLE,
            )
        )
        self.assertFalse(
            naga_logic.short_chain_should_hold(
                2,
                (0.0, 64.0, 0.0),
                (0.0, 64.0, 0.0),
                naga_logic.CHARGE,
            )
        )

    def test_head_clear_volume_covers_the_full_expanded_aabb(self):
        positions = naga_logic.head_clear_positions(
            (0.0, 64.0, 0.0), max_blocks=80
        )

        self.assertEqual(80, len(positions))
        self.assertEqual(set(range(-2, 2)), {pos[0] for pos in positions})
        self.assertEqual({64, 65, 66, 67, 68}, {pos[1] for pos in positions})
        self.assertEqual(set(range(-2, 2)), {pos[2] for pos in positions})
        self.assertIn((-2, 64, 1), positions)
        self.assertIn((1, 68, -2), positions)

    def test_destructive_head_clear_starts_above_the_floor(self):
        positions = naga_logic.head_clear_positions(
            (0.0, 64.0, 0.0), destroy_all=True, max_blocks=80
        )

        self.assertEqual(64, len(positions))
        self.assertEqual({65, 66, 67, 68}, {pos[1] for pos in positions})

    def test_fractional_head_position_does_not_truncate_expanded_aabb(self):
        positions = naga_logic.head_clear_positions(
            (0.5, 64.0, 0.5), max_blocks=125
        )
        self.assertEqual(125, len(positions))
        self.assertEqual(set(range(-2, 3)), {pos[0] for pos in positions})
        self.assertEqual(set(range(-2, 3)), {pos[2] for pos in positions})

    def test_segment_follows_behind_leader_at_two_block_spacing(self):
        destination, yaw, pitch = naga_logic.follow_segment(
            leader_pos=(0.0, 64.0, 0.0),
            leader_yaw=0.0,
            segment_pos=(0.0, 64.0, -3.0),
            segment_index=0,
            on_ground=False,
        )
        self.assertAlmostEqual(0.0, destination[0], places=4)
        self.assertAlmostEqual(64.0, destination[1], places=4)
        self.assertAlmostEqual(-2.0, destination[2], places=4)
        self.assertAlmostEqual(0.0, pitch, places=4)
        self.assertAlmostEqual(0.0, yaw, places=4)

    def test_segment_in_wall_lifts_toward_original_two_block_escape_height(self):
        destination, _, _ = naga_logic.follow_segment(
            leader_pos=(0.0, 64.0, 0.0),
            leader_yaw=0.0,
            segment_pos=(0.0, 64.0, -3.0),
            segment_index=0,
            on_ground=True,
        )
        self.assertGreater(destination[1], 65.0)

    def test_floated_first_segment_keeps_exact_normalized_two_block_spacing(self):
        destination, _, _ = naga_logic.follow_segment(
            leader_pos=(0.0, 64.0, 0.0),
            leader_yaw=0.0,
            segment_pos=(0.0, 66.0, -1.0),
            segment_index=0,
            on_ground=False,
        )
        self.assertGreater(abs(destination[1] - 64.0), 0.75)
        self.assertAlmostEqual(
            2.0,
            math.sqrt(
                destination[0] ** 2
                + (destination[1] - 64.0) ** 2
                + destination[2] ** 2
            ),
            places=4,
        )

    def test_new_segments_spawn_behind_their_leader(self):
        self.assertEqual(
            (0.0, 64.0, -2.0),
            naga_logic.segment_spawn_position(
                (0.0, 64.0, 0.0), 0.0
            ),
        )
        east = naga_logic.segment_spawn_position(
            (10.0, 64.0, 20.0), 90.0
        )
        self.assertAlmostEqual(12.0, east[0], places=4)
        self.assertAlmostEqual(64.0, east[1], places=4)
        self.assertAlmostEqual(20.0, east[2], places=4)

    def test_straight_spawned_chain_stays_extended_instead_of_collapsing(self):
        leader_pos = (0.0, 64.0, 0.0)
        leader_yaw = 0.0
        points = []
        for index in range(naga_logic.MAX_SEGMENTS):
            segment_pos = naga_logic.segment_spawn_position(
                leader_pos, leader_yaw
            )
            leader_pos, leader_yaw, _ = naga_logic.follow_segment(
                leader_pos=leader_pos,
                leader_yaw=leader_yaw,
                segment_pos=segment_pos,
                segment_index=index,
                on_ground=False,
            )
            points.append(leader_pos)

        self.assertAlmostEqual(24.0, math.hypot(*(
            points[-1][0], points[-1][2]
        )), places=4)
        minimum_non_adjacent = min(
            math.hypot(
                points[first][0] - points[second][0],
                points[first][2] - points[second][2],
            )
            for first in range(len(points))
            for second in range(first + 2, len(points))
        )
        self.assertGreaterEqual(minimum_non_adjacent, 3.99)

    def test_segment_pose_snapshot_preserves_a_curved_formation(self):
        offsets = naga_logic.segment_pose_offsets(
            (10.0, 64.0, 20.0),
            [
                (9.0, 64.0, 18.25),
                (7.5, 64.0, 17.0),
                None,
            ],
        )
        self.assertEqual(
            [
                (-1.0, 0.0, -1.75),
                (-2.5, 0.0, -3.0),
                None,
            ],
            offsets,
        )
        self.assertEqual(
            [
                (19.0, 70.0, 28.25),
                (17.5, 70.0, 27.0),
                None,
            ],
            naga_logic.segment_pose_positions(
                (20.0, 70.0, 30.0), offsets
            ),
        )

    def test_only_solid_blocks_count_as_segment_ground_support(self):
        self.assertFalse(naga_logic.is_segment_support_block(None))
        self.assertFalse(naga_logic.is_segment_support_block("minecraft:air"))
        self.assertFalse(naga_logic.is_segment_support_block("minecraft:water"))
        self.assertFalse(
            naga_logic.is_segment_support_block("minecraft:tallgrass")
        )
        self.assertTrue(
            naga_logic.is_segment_support_block("minecraft:grass")
        )
        self.assertTrue(
            naga_logic.is_segment_support_block("minecraft:oak_leaves")
        )

    def test_segment_chain_bends_from_actual_leader_positions_not_a_bone_wave(self):
        first, _, _ = naga_logic.follow_segment(
            leader_pos=(0.0, 64.0, 0.0),
            leader_yaw=90.0,
            segment_pos=(-1.0, 64.0, 2.0),
            segment_index=0,
            on_ground=False,
        )
        second, second_yaw, _ = naga_logic.follow_segment(
            leader_pos=first,
            leader_yaw=135.0,
            segment_pos=(-2.0, 64.0, 4.0),
            segment_index=1,
            on_ground=False,
        )
        self.assertAlmostEqual(2.0, math.hypot(first[0], first[2]), places=4)
        self.assertAlmostEqual(
            2.0,
            math.hypot(second[0] - first[0], second[2] - first[2]),
            places=4,
        )
        self.assertNotEqual(first, second)
        self.assertNotEqual(0.0, second_yaw)

    def test_original_head_slither_adds_lateral_strafe_outside_charge_and_daze(self):
        self.assertAlmostEqual(
            math.cos(10.0 * 0.3) * 0.6,
            naga_logic.slither_strafe(10, naga_logic.CIRCLE),
            places=4,
        )
        self.assertEqual(0.0, naga_logic.slither_strafe(10, naga_logic.DAZE))
        self.assertAlmostEqual(
            0.32,
            naga_logic.slither_strafe(10, naga_logic.CHARGE, 0.4),
            places=4,
        )
        self.assertAlmostEqual(
            0.32,
            naga_logic.slither_strafe(10, naga_logic.INTIMIDATE, 0.4),
            places=4,
        )
        self.assertAlmostEqual(
            math.cos(10.0 * 0.3) * 0.6,
            naga_logic.slither_strafe(10, naga_logic.STUNLESS_CHARGE, 0.4),
            places=4,
        )

    def test_idle_patrol_is_bounded_and_repeats_after_one_full_loop(self):
        self.assertEqual(12.0, naga_logic.IDLE_PATROL_RADIUS)
        self.assertEqual(
            naga_logic.COMBAT_WAYPOINT_TOLERANCE,
            naga_logic.IDLE_PATROL_REACHED_DISTANCE,
        )
        home = (12.5, 64.0, -7.5)
        first_loop = [
            naga_logic.idle_patrol_point(home, index)
            for index in range(naga_logic.IDLE_PATROL_POINT_COUNT)
        ]
        second_loop = [
            naga_logic.idle_patrol_point(
                home, index + naga_logic.IDLE_PATROL_POINT_COUNT
            )
            for index in range(naga_logic.IDLE_PATROL_POINT_COUNT)
        ]

        self.assertEqual(first_loop, second_loop)
        self.assertEqual(naga_logic.IDLE_PATROL_POINT_COUNT, len(set(first_loop)))
        for point in first_loop:
            self.assertAlmostEqual(
                naga_logic.IDLE_PATROL_RADIUS,
                math.hypot(point[0] - home[0], point[2] - home[2]),
                places=4,
            )
            self.assertEqual(home[1], point[1])

    def test_idle_patrol_pauses_then_advances_after_reaching_a_point(self):
        self.assertEqual(1, naga_logic.IDLE_PATROL_PAUSE_TICKS)
        home = (0.0, 64.0, 0.0)
        first = naga_logic.idle_patrol_point(home, 0)
        index, pause_until, destination, stopped = naga_logic.idle_patrol_step(
            first,
            home,
            0,
            tick_count=100,
            pause_until_tick=0,
        )
        self.assertEqual(1, index)
        self.assertEqual(100 + naga_logic.IDLE_PATROL_PAUSE_TICKS, pause_until)
        self.assertIsNone(destination)
        self.assertTrue(stopped)

        waiting = naga_logic.idle_patrol_step(
            first,
            home,
            index,
            tick_count=pause_until - 1,
            pause_until_tick=pause_until,
        )
        self.assertEqual((index, pause_until, None, False), waiting)

        resumed = naga_logic.idle_patrol_step(
            first,
            home,
            index,
            tick_count=pause_until,
            pause_until_tick=pause_until,
        )
        self.assertEqual(index, resumed[0])
        self.assertEqual(
            naga_logic.idle_patrol_point(home, index), resumed[2]
        )
        self.assertFalse(resumed[3])

    def test_slither_preserves_faster_navigation_at_the_circle_floor(self):
        from_rest = naga_logic.slither_motion(
            (0.0, 0.0, 0.0),
            (1.0, 0.0),
            0.6,
            minimum_forward=0.075,
            lateral_scale=0.085,
        )
        self.assertAlmostEqual(0.075, from_rest[0], places=4)
        self.assertAlmostEqual(0.0, from_rest[1], places=4)
        self.assertAlmostEqual(0.051, from_rest[2], places=4)

        from_faster_navigation = naga_logic.slither_motion(
            (0.2, 0.04, 0.03),
            (1.0, 0.0),
            0.6,
            minimum_forward=0.075,
            lateral_scale=0.085,
        )
        self.assertAlmostEqual(0.2, from_faster_navigation[0], places=4)
        self.assertAlmostEqual(0.04, from_faster_navigation[1], places=4)
        self.assertAlmostEqual(0.051, from_faster_navigation[2], places=4)

        self.assertEqual(
            (0.2, 0.04, 0.03),
            naga_logic.slither_motion(
                (0.2, 0.04, 0.03),
                (0.0, 0.0),
                0.6,
                minimum_forward=0.075,
            ),
        )

    def test_idle_and_circle_share_segment_scaled_navigation_speed(self):
        self.assertEqual(
            1.0,
            naga_logic.scaled_navigation_speed(1.0, naga_logic.MAX_SEGMENTS),
        )
        for segments in (naga_logic.MAX_SEGMENTS, 6, 2):
            expected = (
                naga_logic.speed_for_segments(segments)
                / naga_logic.speed_for_segments(naga_logic.MAX_SEGMENTS)
            )
            self.assertAlmostEqual(
                expected,
                naga_logic.scaled_navigation_speed(1.0, segments),
                places=6,
            )
        self.assertGreater(
            naga_logic.scaled_navigation_speed(1.0, 2),
            naga_logic.scaled_navigation_speed(
                1.0, naga_logic.MAX_SEGMENTS
            ),
        )
        self.assertEqual(0.0, naga_logic.scaled_navigation_speed(-1.0, 12))

    def test_nearest_target_uses_distance_and_honors_range(self):
        candidates = [
            ("far", (30.0, 64.0, 0.0)),
            ("near", (4.0, 64.0, 3.0)),
            ("outside", (81.0, 64.0, 0.0)),
        ]
        self.assertEqual(
            "near",
            naga_logic.nearest_target(
                (0.0, 64.0, 0.0), candidates, 80.0
            ),
        )
        self.assertIsNone(
            naga_logic.nearest_target(
                (0.0, 64.0, 0.0), [("outside", (81.0, 64.0, 0.0))], 80.0
            )
        )
        self.assertIsNone(
            naga_logic.nearest_target(
                (0.0, 64.0, 0.0), [("above", (0.0, 145.0, 0.0))], 80.0
            )
        )

    def test_nearest_target_is_deterministic_when_distances_tie(self):
        candidates = [
            ("player-b", (3.0, 64.0, 4.0)),
            ("player-a", (-3.0, 64.0, -4.0)),
        ]
        self.assertEqual(
            "player-a",
            naga_logic.nearest_target(
                (0.0, 64.0, 0.0), candidates, 80.0
            ),
        )

    def test_circle_point_matches_original_orbit_geometry(self):
        destination = naga_logic.circle_point(
            (13.0, 64.0, 0.0),
            (0.0, 65.0, 0.0),
            False,
            12.0,
            1.0,
        )
        self.assertAlmostEqual(math.cos(-1.0) * 12.0, destination[0], places=4)
        self.assertEqual(64.0, destination[1])
        self.assertAlmostEqual(math.sin(-1.0) * 12.0, destination[2], places=4)

    def test_original_path_step_advances_inside_four_head_widths(self):
        self.assertTrue(naga_logic.path_step_finished(7.99, 2.0))
        self.assertFalse(naga_logic.path_step_finished(8.0, 2.0))
        self.assertFalse(naga_logic.path_step_finished(8.01, 2.0))

    def test_path_step_advance_distance_scales_with_collision_width(self):
        self.assertTrue(naga_logic.path_step_finished(3.99, 1.0))
        self.assertFalse(naga_logic.path_step_finished(4.0, 1.0))

    def test_combat_waypoint_requires_arrival_at_the_final_destination(self):
        self.assertFalse(naga_logic.combat_waypoint_reached(7.99))
        self.assertFalse(naga_logic.combat_waypoint_reached(3.01))
        self.assertTrue(naga_logic.combat_waypoint_reached(3.0))
        self.assertTrue(naga_logic.combat_waypoint_reached(0.0))

    def test_initial_orbit_finishes_after_eight_waypoints(self):
        brain = naga_logic.NagaBrain(FixedRandom(integers=[0]))
        self.assertEqual(8, brain.counter)
        for _index in range(7):
            self.assertEqual(naga_logic.CIRCLE, brain.complete_path_step())
        self.assertEqual(1, brain.counter)
        self.assertEqual(naga_logic.INTIMIDATE, brain.complete_path_step())

    def test_legacy_circle_snapshot_is_clamped_to_the_short_orbit_budget(self):
        brain = naga_logic.NagaBrain.from_snapshot(
            {"state": naga_logic.CIRCLE, "counter": 15}
        )
        self.assertEqual(8, brain.counter)

    def test_state_cycle_is_circle_intimidate_charge_circle(self):
        brain = naga_logic.NagaBrain(FixedRandom(integers=[0, 0]))
        self.assertEqual(naga_logic.CIRCLE, brain.state)
        brain.counter = 0
        brain.tick_counter(target_above=False, use_stunless=False)
        self.assertEqual(naga_logic.INTIMIDATE, brain.state)
        self.assertEqual(14, brain.counter)
        brain.counter = 0
        brain.tick_counter(target_above=False, use_stunless=False)
        self.assertEqual(naga_logic.CHARGE, brain.state)
        self.assertEqual(2, brain.counter)
        brain.counter = 0
        brain.tick_counter(target_above=False, use_stunless=False)
        self.assertEqual(naga_logic.CIRCLE, brain.state)
        self.assertEqual(7, brain.counter)

    def test_path_states_only_count_completed_waypoints(self):
        brain = naga_logic.NagaBrain(FixedRandom(integers=[0]))
        self.assertEqual(naga_logic.CIRCLE, brain.complete_path_step())
        self.assertEqual(7, brain.counter)
        brain.counter = 1
        self.assertEqual(naga_logic.INTIMIDATE, brain.complete_path_step())

        brain.state = naga_logic.CHARGE
        brain.counter = 2
        self.assertEqual(naga_logic.CHARGE, brain.complete_path_step())
        self.assertEqual(1, brain.counter)
        self.assertEqual(naga_logic.CIRCLE, brain.complete_path_step())
        self.assertEqual(7, brain.counter)

    def test_yaw_turning_is_shortest_path_and_rate_limited(self):
        self.assertEqual(15.0, naga_logic.step_yaw(0.0, 90.0, 15.0))
        self.assertEqual(-15.0, naga_logic.step_yaw(0.0, -90.0, 15.0))
        self.assertEqual(-175.0, naga_logic.step_yaw(170.0, -170.0, 15.0))
        self.assertEqual(20.0, naga_logic.step_yaw(10.0, 20.0, 15.0))

    def test_daze_recoil_has_a_short_window_then_hard_stops(self):
        self.assertFalse(naga_logic.daze_recoil_finished(103, 104))
        self.assertTrue(naga_logic.daze_recoil_finished(104, 104))
        self.assertTrue(naga_logic.daze_recoil_finished(105, 104))

    def test_timed_states_count_each_server_tick(self):
        brain = naga_logic.NagaBrain(FixedRandom())
        brain.state = naga_logic.DAZE
        brain.counter = 2
        self.assertEqual(naga_logic.DAZE, brain.advance_timed_state())
        self.assertEqual(1, brain.counter)
        self.assertEqual(naga_logic.DAZE, brain.advance_timed_state())
        self.assertEqual(0, brain.counter)
        self.assertEqual(naga_logic.CIRCLE, brain.advance_timed_state())

    def test_elevated_target_inserts_crumble_before_charge(self):
        brain = naga_logic.NagaBrain(FixedRandom(integers=[0]))
        brain.state = naga_logic.INTIMIDATE
        brain.transition(target_above=True, use_stunless=False)
        self.assertEqual(naga_logic.CRUMBLE, brain.state)
        self.assertEqual(20, brain.counter)
        brain.transition(target_above=False, use_stunless=False)
        self.assertEqual(naga_logic.CHARGE, brain.state)

    def test_crumble_requires_target_feet_above_the_three_block_head(self):
        self.assertFalse(naga_logic.target_is_above_naga(64.0, 67.0))
        self.assertTrue(naga_logic.target_is_above_naga(64.0, 67.01))

    def test_normal_charge_block_causes_daze(self):
        brain = naga_logic.NagaBrain(FixedRandom(integers=[17]))
        brain.state = naga_logic.CHARGE
        result = brain.resolve_contact(blocking=True)
        self.assertEqual("shield_daze", result["kind"])
        self.assertEqual(0.0, result["target_damage"])
        self.assertEqual(2.0, result["self_damage"])
        self.assertEqual(5, result["shield_damage"])
        self.assertEqual(naga_logic.DAZE, brain.state)
        self.assertEqual(77, brain.counter)

    def test_stunless_charge_breaks_guard_without_daze(self):
        brain = naga_logic.NagaBrain(FixedRandom())
        brain.state = naga_logic.STUNLESS_CHARGE
        result = brain.resolve_contact(blocking=True)
        self.assertEqual("shield_break", result["kind"])
        self.assertEqual(4.0, result["target_damage"])
        self.assertEqual(10, result["shield_damage"])
        self.assertEqual(200, result["shield_cooldown"])
        self.assertEqual(naga_logic.CIRCLE, brain.state)

    def test_unblocked_head_contact_ends_both_charge_variants(self):
        for charge_state in (
            naga_logic.CHARGE,
            naga_logic.STUNLESS_CHARGE,
        ):
            brain = naga_logic.NagaBrain(FixedRandom(integers=[0]))
            brain.state = charge_state
            result = brain.resolve_contact(blocking=False)
            self.assertEqual("melee", result["kind"])
            self.assertEqual(naga_logic.CIRCLE, brain.state)
            self.assertEqual(7, brain.counter)

    def test_shield_recoil_restores_the_locked_source_bounce(self):
        player, naga = naga_logic.shield_recoil_motions(
            (0.8, 0.1, -0.4),
            (0.2, 0.0, -0.1),
        )
        for actual, expected in zip(player, (2.6, 0.75, -1.3)):
            self.assertAlmostEqual(expected, actual, places=6)
        # Entity.push adds the -1.25x impulse to the captured 1.0x motion,
        # leaving a net -0.25x horizontal reversal and preserving old Y.
        for actual, expected in zip(naga, (-0.2, 0.6, 0.1)):
            self.assertAlmostEqual(expected, actual, places=6)

    def test_shield_separation_moves_the_player_to_a_fixed_safe_distance(self):
        player, direction = naga_logic.shield_separation_position(
            (0.0, 64.0, 0.0),
            (0.2, 64.0, 0.1),
        )
        self.assertAlmostEqual(2.25, math.hypot(player[0], player[2]))
        self.assertEqual(64.0, player[1])
        self.assertAlmostEqual(1.0, math.hypot(*direction))

        fallback_player, fallback_direction = (
            naga_logic.shield_separation_position(
                (5.0, 70.0, 5.0),
                (5.0, 70.0, 5.0),
                fallback_direction=(0.0, 1.0),
            )
        )
        self.assertEqual((5.0, 70.0, 7.25), fallback_player)
        self.assertEqual((0.0, 1.0), fallback_direction)

    def test_dazed_naga_cannot_attack_and_damage_breaks_stun(self):
        brain = naga_logic.NagaBrain(FixedRandom())
        brain.state = naga_logic.DAZE
        self.assertEqual(0.0, brain.resolve_contact(False)["target_damage"])
        self.assertFalse(brain.record_damage(15.0))
        self.assertTrue(brain.record_damage(1.0))
        self.assertEqual(naga_logic.CIRCLE, brain.state)

    def test_sub_threshold_stun_damage_carries_into_the_next_daze(self):
        brain = naga_logic.NagaBrain(FixedRandom())
        brain.state = naga_logic.DAZE
        self.assertFalse(brain.record_damage(10.0))
        brain.do_circle()
        brain.do_daze()
        self.assertTrue(brain.record_damage(6.0))
        self.assertEqual(naga_logic.CIRCLE, brain.state)
        self.assertEqual(0.0, brain.damage_during_stun)

    def test_stun_damage_uses_the_original_integer_accumulator(self):
        brain = naga_logic.NagaBrain(FixedRandom())
        brain.state = naga_logic.DAZE
        self.assertFalse(brain.record_damage(15.9))
        self.assertEqual(15, brain.damage_during_stun)
        self.assertFalse(brain.record_damage(0.9))
        self.assertTrue(brain.record_damage(1.0))


class NagaLifecycleTests(unittest.TestCase):
    def test_lost_segments_explode_tail_first_at_original_twelve_tick_interval(self):
        self.assertEqual(
            [(11, 12), (10, 24), (9, 36)],
            naga_logic.segment_destruction_schedule(12, 9),
        )
        self.assertEqual([], naga_logic.segment_destruction_schedule(7, 9))

    def test_healing_starts_after_600_ticks_without_damage(self):
        self.assertEqual(0.0, naga_logic.heal_amount(600))
        self.assertEqual(0.0, naga_logic.heal_amount(619))
        self.assertEqual(1.0, naga_logic.heal_amount(620))
        self.assertEqual(1.0, naga_logic.heal_amount(640))

    def test_home_bounds_match_original_courtyard(self):
        home = (0.0, 64.0, 0.0)
        self.assertTrue(naga_logic.inside_home((46.0, 71.0, -46.0), home))
        self.assertFalse(naga_logic.inside_home((46.1, 64.0, 0.0), home))
        self.assertFalse(naga_logic.inside_home((0.0, 71.1, 0.0), home))

    def test_overlapping_courtyards_can_only_own_one_naga(self):
        self.assertTrue(
            naga_logic.courtyards_overlap(
                (0.0, 64.0, 0.0), (20.0, 64.0, 20.0)
            )
        )
        self.assertFalse(
            naga_logic.courtyards_overlap(
                (0.0, 64.0, 0.0), (100.0, 64.0, 0.0)
            )
        )
        self.assertFalse(
            naga_logic.courtyards_overlap(
                (0.0, 64.0, 0.0), (0.0, 90.0, 0.0)
            )
        )

    def test_navigation_result_codes_match_modsdk_contract(self):
        self.assertTrue(naga_logic.navigation_failed(-1))
        self.assertFalse(naga_logic.navigation_failed(0))
        self.assertTrue(naga_logic.navigation_failed(1))
        self.assertTrue(naga_logic.navigation_failed(2))
        self.assertTrue(naga_logic.navigation_failed(3))
        self.assertFalse(naga_logic.navigation_failed(None))
        self.assertTrue(naga_logic.navigation_succeeded(0))
        self.assertFalse(naga_logic.navigation_succeeded(1))
        self.assertFalse(naga_logic.navigation_succeeded(None))
        self.assertFalse(naga_logic.navigation_finished(-1))
        self.assertTrue(naga_logic.navigation_finished(0))
        self.assertFalse(naga_logic.navigation_finished(1))
        self.assertFalse(naga_logic.navigation_finished(2))
        self.assertFalse(naga_logic.navigation_finished(3))
        self.assertFalse(naga_logic.navigation_finished(None))

    def test_navigation_progress_ignores_jitter_and_resets_on_real_advance(self):
        best, stalled = naga_logic.update_navigation_progress(
            None, 10.0, 0, 2, 0.12
        )
        self.assertEqual((10.0, 0), (best, stalled))

        best, stalled = naga_logic.update_navigation_progress(
            best, 9.95, stalled, 2, 0.12
        )
        self.assertEqual((10.0, 2), (best, stalled))

        best, stalled = naga_logic.update_navigation_progress(
            best, 10.05, stalled, 2, 0.12
        )
        self.assertEqual((10.0, 4), (best, stalled))

        best, stalled = naga_logic.update_navigation_progress(
            best, 9.70, stalled, 2, 0.12
        )
        self.assertEqual((9.70, 0), (best, stalled))

    def test_block_damage_policy_honors_state_gamerule_and_protected_blocks(self):
        self.assertFalse(
            naga_logic.should_destroy_block(
                "minecraft:oak_leaves", naga_logic.CIRCLE, False
            )
        )
        self.assertTrue(
            naga_logic.should_destroy_block(
                "minecraft:oak_leaves", naga_logic.CIRCLE, True
            )
        )
        self.assertFalse(
            naga_logic.should_destroy_block(
                "minecraft:stone", naga_logic.CIRCLE, True
            )
        )
        self.assertTrue(
            naga_logic.should_destroy_block(
                "minecraft:stone", naga_logic.CHARGE, True
            )
        )
        self.assertFalse(
            naga_logic.should_destroy_block(
                "minecraft:stone", naga_logic.CRUMBLE, True
            )
        )
        self.assertTrue(
            naga_logic.should_destroy_block(
                "minecraft:stone",
                naga_logic.CRUMBLE,
                True,
                targeted_crumble=True,
            )
        )
        self.assertTrue(
            naga_logic.should_destroy_block(
                "minecraft:stone",
                naga_logic.CIRCLE,
                True,
                outside_home=True,
            )
        )
        self.assertFalse(
            naga_logic.should_destroy_block(
                "minecraft:bedrock",
                naga_logic.STUNLESS_CHARGE,
                True,
                protected=True,
            )
        )

    def test_damage_immunity_matches_original_source_and_explosion_rules(self):
        self.assertTrue(
            naga_logic.naga_damage_is_blocked("entity_explosion")
        )
        self.assertTrue(
            naga_logic.naga_damage_is_blocked(
                "entity_attack", attacker_inside=False
            )
        )
        self.assertTrue(
            naga_logic.naga_damage_is_blocked(
                "projectile", attacker_inside=True, direct_inside=False
            )
        )
        self.assertFalse(
            naga_logic.naga_damage_is_blocked(
                "entity_attack", attacker_inside=True
            )
        )
        self.assertFalse(naga_logic.naga_damage_is_blocked("fall"))


if __name__ == "__main__":
    unittest.main()
