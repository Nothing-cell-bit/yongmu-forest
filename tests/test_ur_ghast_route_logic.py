# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
PACKAGE = BP / "TwilightBossSlice"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))


class UrGhastLogicTests(unittest.TestCase):
    def test_locked_combat_constants_and_three_shot_volley(self):
        import ur_ghast_logic as logic

        state = logic.create_state((0, 180, 0), [(10, 180, 10), (-10, 180, -10)])
        self.assertEqual(250.0, state["health"])
        self.assertEqual(128, logic.TRACKING_RANGE)
        self.assertEqual(20, logic.HOVER_HEIGHT)
        self.assertEqual(3, len(logic.fireball_volley((0, 200, 0), (10, 180, 10))))

    def test_first_10_damage_toggles_tantrum_then_resets_to_18(self):
        import ur_ghast_logic as logic

        state = logic.create_state(
            (0, 180, 0), [(10, 160, 0), (-10, 160, 0)]
        )
        first = logic.apply_damage(state, 9, "alice")
        self.assertEqual(9.0, first["effectiveDamage"])
        self.assertEqual("normal", state["phase"])
        logic.apply_damage(state, 1, "alice")
        self.assertEqual("tantrum", state["phase"])
        self.assertEqual(18.0, state["damageUntilNextPhase"])
        reduced = logic.apply_damage(state, 10, "alice")
        self.assertEqual(1.0, reduced["effectiveDamage"])
        plans = logic.tantrum_minion_spawns(state)
        self.assertEqual(2, len(plans))
        self.assertEqual([6, 6], [plan["count"] for plan in plans])

    def test_three_deaths_charge_trap_and_activation_runs_for_120_ticks(self):
        import ur_ghast_logic as logic

        trap = logic.create_trap_state((0, 180, 0))
        for entity_id in ("a", "b", "c"):
            logic.record_mini_ghast_death(trap, entity_id)
        self.assertTrue(trap["charged"])
        state = logic.create_state((0, 200, 0), [(0, 180, 0)])
        state["phase"] = "tantrum"
        event = logic.activate_trap(trap)
        self.assertTrue(event["activated"])
        self.assertTrue(event["pull"])
        self.assertEqual(0, event["damage"])
        self.assertEqual("tantrum", state["phase"])
        self.assertEqual(0, trap["deathCount"])
        self.assertTrue(trap["active"])
        logic.advance_trap(trap, 119)
        self.assertTrue(trap["active"])
        logic.advance_trap(trap, 1)
        self.assertFalse(trap["active"])

    def test_trap_uses_source_charge_and_active_boxes_then_pulls_each_tick(self):
        import ur_ghast_logic as logic

        trap = logic.create_trap_state((0, 180, 0))
        self.assertTrue(
            logic.trap_accepts_mini_ghast_death(trap, (10, 196, 10))
        )
        self.assertFalse(
            logic.trap_accepts_mini_ghast_death(trap, (11, 196, 10))
        )
        self.assertFalse(
            logic.trap_accepts_mini_ghast_death(trap, (10, 197, 10))
        )
        trap["charged"] = True
        logic.activate_trap(trap)
        self.assertTrue(logic.trap_affects_entity(trap, (6, 212, 6)))
        self.assertFalse(logic.trap_affects_entity(trap, (7, 212, 6)))
        self.assertFalse(logic.trap_affects_entity(trap, (6, 214, 6)))

        state = logic.create_state((0, 200, 0), [(0, 180, 0)])
        state["phase"] = "tantrum"
        event = logic.apply_active_trap_to_ur_ghast(
            trap, state, (0.5, 200, 0.5), deal_damage=True
        )
        self.assertTrue(event["affected"])
        self.assertEqual("normal", state["phase"])
        self.assertEqual(7.0, event["damage"])
        self.assertLess(event["motion"][1], 0.0)

    def test_stationary_death_sequence_and_rewards_are_unique_across_reload(self):
        import ur_ghast_logic as logic

        state = logic.create_state((0, 200, 0), [])
        state["health"] = 0
        home = list(state["home"])
        stages = [
            logic.advance_death_sequence(state, 1)["stage"]
            for _ in range(90)
        ]
        self.assertEqual(home, state["home"])
        self.assertEqual("burst", stages[0])
        self.assertEqual("trail", stages[30])
        self.assertEqual("complete", stages[-1])
        self.assertTrue(logic.claim_reward(state))
        restored = logic.load_state(json.loads(json.dumps(state)))
        self.assertFalse(logic.claim_reward(restored))

    def test_trap_progress_is_independent_of_death_credit(self):
        import ur_ghast_logic as logic

        state = logic.create_state((0, 200, 0), [])
        state["participants"] = ["alice"]
        state["health"] = 0
        self.assertEqual(["alice"], logic.final_progress_players(state))
        self.assertFalse(state["ghastTrapActivated"])


class UrGhastRuntimeContractTests(unittest.TestCase):
    def test_server_wires_ghast_trap_and_unique_route_reward(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("UR_GHAST_IDENTIFIER", source)
        self.assertIn('"kind": "ur_ghast"', source)
        self.assertIn('"tf_slice:ghast_trap"', source)
        self.assertIn('"tf_ghast_trap_activated"', source)
        self.assertIn('"tf_ur_ghast_defeated"', source)
        self.assertIn("ur_ghast_reward.json", source)
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        hud = (PACKAGE / "routeBossHudUI.py").read_text(encoding="utf-8")
        self.assertIn(
            'visible_bosses(\n            self._bosses.values(),\n            "ur_ghast"',
            client,
        )
        self.assertIn("class UrGhastBossHudUI", hud)

    def test_server_uses_source_trap_boxes_and_sustained_active_ticks(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        deaths = source[
            source.index("        if entityType == MINI_GHAST_IDENTIFIER:") :
            source.index("        urKey =", source.index("        if entityType == MINI_GHAST_IDENTIFIER:"))
        ]
        self.assertIn("trap_accepts_mini_ghast_death", deaths)
        self.assertNotIn("32.0 * 32.0", deaths)

        activation = source[
            source.index("    def _activate_ghast_trap") :
            source.index("    def _dark_tower_connected_mechanism_blocks")
        ]
        self.assertIn("activate_trap(trap)", activation)
        self.assertNotIn("nearest =", activation)

        drive = source[
            source.index("    def _drive_ur_ghasts") :
            source.index("    def _place_ur_ghast_reward")
        ]
        self.assertIn("apply_active_trap_to_ur_ghast", drive)
        self.assertIn("_active_ghast_trap", drive)


if __name__ == "__main__":
    unittest.main()
