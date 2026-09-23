"""Numerical motion regression tests; these do not emulate engine rendering."""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'TwilightBossSliceB'))
from TwilightBossSlice import fortification_visual_logic as logic


class ShieldMotionTests(unittest.TestCase):
    def test_initial_position_and_zero_phase(self):
        self.assertEqual(((100.0, 65.0, -20.0), 0.0), logic.sample({}, (100, 65, -20), 10))

    def test_step_smoothing_is_frame_rate_independent(self):
        positions = []
        for fps in (30, 60, 120):
            state = {}
            logic.sample(state, (0, 0, 0), 0)
            for frame in range(1, fps // 10 + 1):
                position, age = logic.sample(state, (0.2, 0, 0), frame / fps)
            positions.append(position[0])
            self.assertAlmostEqual(0.1, age)
        for position in positions:
            self.assertAlmostEqual(0.2 * (1 - math.exp(-0.1 / 0.025)), position)

    def test_staircase_samples_have_bounded_lag_and_no_overshoot(self):
        state = {}
        logic.sample(state, (0, 0, 0), 0)
        previous = 0
        for frame in range(1, 601):
            target = (frame // 3) * 0.3  # 20 Hz samples, 60 Hz render frames.
            position, _ = logic.sample(state, (target, 0, 0), frame / 60)
            self.assertGreaterEqual(position[0], previous)
            self.assertLessEqual(position[0], target)
            self.assertLessEqual(target - position[0], 0.25000001)
            previous = position[0]

    def test_teleport_snaps_but_preserves_phase(self):
        state = {}
        logic.sample(state, (0, 0, 0), 0)
        logic.sample(state, (0, 0, 0), 0.1)
        position, age = logic.sample(state, (100, 80, -100), 0.2)
        self.assertEqual((100, 80, -100), position)
        self.assertAlmostEqual(0.2, age)

    def test_long_pause_snaps_and_caps_animation_jump(self):
        state = {}
        logic.sample(state, (0, 0, 0), 0)
        self.assertEqual(((1.0, 0.0, 0.0), 0.1), logic.sample(state, (1, 0, 0), 10))

    def test_shared_state_does_not_advance_twice_in_one_render_frame(self):
        state = {}
        logic.sample(state, (0, 0, 0), 0)
        first = logic.sample(state, (0.2, 0, 0), 1 / 60)
        self.assertEqual(first, logic.sample(state, (0.2, 0, 0), 1 / 60))

    def test_clock_rollback_does_not_reverse_rotation(self):
        state = {}
        logic.sample(state, (0, 0, 0), 10)
        logic.sample(state, (0, 0, 0), 10.1)
        _, age = logic.sample(state, (0, 0, 0), 9)
        self.assertAlmostEqual(0.1, age)

    def test_stop_settles_without_drift(self):
        state = {}
        logic.sample(state, (0, 0, 0), 0)
        for frame in range(1, 61):
            position, _ = logic.sample(state, (0.2, 0, 0), frame / 60)
        self.assertAlmostEqual(0.2, position[0])

    def test_smoothing_preserves_three_dimensional_direction(self):
        state = {}
        logic.sample(state, (0, 0, 0), 0)
        position, _ = logic.sample(state, (0.1, 0.1, -0.1), 1 / 60)
        self.assertAlmostEqual(position[0], position[1])
        self.assertAlmostEqual(position[0], -position[2])
