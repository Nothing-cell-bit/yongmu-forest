"""Execute production adapters against explicit component replacement semantics."""
import copy
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from tests.test_beetle_combat_workflow import ROOT, LOGIC, load_entity


def adapter(name, **globals_):
    source = (ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py").read_text(
        encoding="utf-8"
    )
    signature = "    def " + name + "("
    body = signature + source.split(signature, 1)[1]
    body = body.split("\n    def ", 1)[0]
    namespace = dict(globals_)
    exec(compile(textwrap.dedent(body), str(ROOT / "server-adapter"), "exec"), namespace)
    return namespace[name]


class FireHarness:
    def __init__(self):
        self.entity = load_entity("fire_beetle")
        self.components = copy.deepcopy(self.entity["components"])
        self.target = "player"
        self.target_pos = (0, 0, 4)
        self._tick = 100
        self._trigger_entity_event("beetle", "minecraft:entity_spawned")
        self.state = {"lastHurtById": "player", "dimensionId": 0}

    def _trigger_entity_event(self, entity_id, event):
        # Removing a replacement component is not a stack pop to its old value.
        def apply(action):
            for step in action.get("sequence", []):
                apply(step)
            for group in action.get("remove", {}).get("component_groups", []):
                for key in self.entity["component_groups"][group]:
                    self.components.pop(key, None)
            for group in action.get("add", {}).get("component_groups", []):
                self.components.update(copy.deepcopy(self.entity["component_groups"][group]))
        apply(self.entity["events"].get(event, {}))

    def _get_foot_pos(self, target):
        return self.target_pos if target == "player" else None

    def _set_attack_target(self, entity, target):
        self.target = target

    def _reset_attack_target(self, entity):
        self.target = None

    _is_online_player = lambda self, target: True
    _is_invulnerable_player = lambda self, target: False
    _beetle_can_see = lambda self, *args: True
    _beetle_target_eye = lambda self, target, pos: (pos[0], pos[1] + 1.62, pos[2])
    _set_full_motion = lambda self, *args: None
    _face_position = lambda self, *args: None
    _broadcast_beetle_effect = lambda self, *args: None
    _play_world_sound = lambda self, *args: None
    _hurt = lambda self, *args: False


FireHarness._stop_fire_breath = adapter("_stop_fire_breath", beetle_combat_logic=LOGIC)
FireHarness._update_fire_beetle = adapter(
    "_update_fire_beetle", beetle_combat_logic=LOGIC,
    random=SimpleNamespace(random=lambda: 0.0, uniform=lambda a, b: a),
    _distance_sq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b)),
)


class BeetleStateTransitionTests(unittest.TestCase):
    def assert_mobile(self, harness):
        self.assertEqual(0.23, harness.components.get("minecraft:movement", {}).get("value"))
        self.assertIn("minecraft:behavior.melee_attack", harness.components)
        self.assertIn("minecraft:behavior.random_stroll", harness.components)

    def test_stop_reinstalls_normal_movement_even_when_called_twice(self):
        h = FireHarness()
        h._update_fire_beetle("beetle", h.state, (0, 0, 0))
        for _ in range(2):
            h._stop_fire_breath("beetle", h.state)
            self.assert_mobile(h)

    def test_three_breath_cycles_preserve_target_and_release_movement_goals(self):
        h = FireHarness()
        for _ in range(3):
            self.assert_mobile(h)
            h._update_fire_beetle("beetle", h.state, (0, 0, 0))
            self.assertEqual("breathing", h.state["beetlePhase"])
            self.assertEqual("player", h.target)
            self.assertEqual(0.0, h.components["minecraft:movement"]["value"])
            self.assertNotIn("minecraft:behavior.melee_attack", h.components)
            self.assertNotIn("minecraft:behavior.random_stroll", h.components)
            h._tick += LOGIC.FIRE_DURATION_TICKS
            h._update_fire_beetle("beetle", h.state, (0, 0, 0))
            self.assertIsNone(h.state["beetlePhase"])
            self.assert_mobile(h)
            h._tick += LOGIC.FIRE_GOAL_CHECK_INTERVAL_TICKS

    def test_target_loss_also_restores_movement(self):
        h = FireHarness()
        h._update_fire_beetle("beetle", h.state, (0, 0, 0))
        h.target_pos = None
        h._tick += 1
        h._update_fire_beetle("beetle", h.state, (0, 0, 0))
        self.assertIsNone(h.state["beetlePhase"])
        self.assert_mobile(h)

    def test_pinch_charge_calls_damage_once_but_native_melee_does_not_duplicate(self):
        ride = Mock()
        ride.SetRiderRideEntity.return_value = True
        grab = adapter("_grab_pinch_target", CF=SimpleNamespace(CreateRide=lambda _: ride))
        h = Mock()
        h._hurt.return_value = True
        self.assertTrue(grab(h, "beetle", "player"))
        h._hurt.assert_called_once_with("player", 4.0, "beetle")
        h._hurt.reset_mock()
        self.assertTrue(grab(h, "beetle", "player", False))
        h._hurt.assert_not_called()
        ride.SetRiderRideEntity.return_value = False
        self.assertFalse(grab(h, "beetle", "player"))
        h._hurt.assert_not_called()
