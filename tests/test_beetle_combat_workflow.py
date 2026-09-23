import importlib.util
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGIC_PATH = (
    ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "beetle_combat_logic.py"
)
SPEC = importlib.util.spec_from_file_location("beetle_combat_logic", LOGIC_PATH)
LOGIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGIC)
UPSTREAM = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree"


def load_entity(name):
    path = ROOT / "TwilightBossSliceB" / "entities" / (name + ".entity.json")
    return json.loads(path.read_text(encoding="utf-8"))["minecraft:entity"]


class BeetleCombatWorkflowTests(unittest.TestCase):
    def test_attack_sources_are_locked_to_4_3_2508(self):
        expected = {
            "twilightforest/entity/ai/goal/BreathAttackGoal.class":
                "37740A4937C8EFFC644B30E01290A74FAC8B0E36B058BFB2B968F72084BA50BB",
            "twilightforest/entity/ai/goal/ChargeAttackGoal.class":
                "A3F2EA6C92BED099468889BEBA5A6C5405E34543F2E4CC99C3AD63FDBDB6537D",
            "twilightforest/entity/projectile/SlimeProjectile.class":
                "648CD1AFAC56070E3B5A8D315807EF65C13E564D518452B565033A9E520DCB94",
        }
        for relative, digest in expected.items():
            actual = hashlib.sha256((UPSTREAM / relative).read_bytes()).hexdigest().upper()
            self.assertEqual(digest, actual, relative)

    def test_fire_breath_is_a_timed_frozen_ray(self):
        self.assertTrue(LOGIC.fire_can_start(25, True, True, 0.099))
        self.assertFalse(LOGIC.fire_can_start(25.01, True, True, 0.0))
        self.assertFalse(LOGIC.fire_can_start(4, False, True, 0.0))
        self.assertFalse(LOGIC.fire_is_damaging(5))
        self.assertTrue(LOGIC.fire_is_damaging(6))
        self.assertFalse(LOGIC.fire_is_damaging(30))
        self.assertFalse(LOGIC.fire_goal_check_ready(8, 9))
        self.assertTrue(LOGIC.fire_goal_check_ready(9, 9))
        self.assertTrue(LOGIC.beam_hit((0, 1, 0), (0, 1, 5), (0.5, 1, 10)))
        self.assertFalse(LOGIC.beam_hit((0, 1, 0), (0, 1, 5), (2, 1, 10)))
        self.assertEqual(1.62, LOGIC.fire_target_eye_height(1.8, True))
        self.assertEqual(1.7, LOGIC.fire_target_eye_height(2.0, False))
        self.assertEqual(
            ((0.9, 1.0, 0.0), (1.5, 1.0, 0.0)),
            LOGIC.fire_breath_visual_points(
                (0, 1, 0), (5, 1, 0), (0.0, 0.6)
            ),
        )
        self.assertEqual(
            (), LOGIC.fire_breath_visual_points((1, 1, 1), (1, 1, 1), (0.0,))
        )
        fire = load_entity("fire_beetle")
        self.assertNotIn("minecraft:behavior.ranged_attack", fire["components"])
        self.assertNotIn("minecraft:shooter", fire["components"])
        self.assertIn("tf_slice:breathing", fire["component_groups"])
        self.assertIn("tf_slice:start_breathing", fire["events"])
        self.assertIn("tf_slice:stop_breathing", fire["events"])

    def test_slime_ballistics_and_impact_contract(self):
        self.assertEqual((3.0, 4.0, 4.0), LOGIC.slime_aim_vector((0, 0, 0), (3, 3, 4)))
        slime = load_entity("slime_beetle")["components"]
        self.assertEqual(1.5, slime["minecraft:behavior.ranged_attack"]["attack_interval_min"])
        self.assertEqual(1.5, slime["minecraft:behavior.ranged_attack"]["attack_interval_max"])
        self.assertEqual(10, slime["minecraft:behavior.ranged_attack"]["attack_radius"])
        self.assertEqual("tf_slice:slime_blob", slime["minecraft:shooter"]["def"])
        blob = load_entity("slime_blob")["components"]
        self.assertFalse(blob["minecraft:physics"]["has_gravity"])
        projectile = blob["minecraft:projectile"]
        self.assertEqual(LOGIC.SLIME_POWER, projectile["power"])
        self.assertEqual(LOGIC.SLIME_GRAVITY, projectile["gravity"])
        self.assertEqual(LOGIC.SLIME_INACCURACY, projectile["uncertainty_base"])
        self.assertEqual(1, projectile["anchor"])
        self.assertEqual([0, -0.1, 0], projectile["offset"])

    def test_pinch_charge_uses_source_attack_reach(self):
        self.assertAlmostEqual(
            6.36,
            LOGIC.pinch_attack_reach_sq(1.2, 0.6),
            places=6,
        )

    def test_pinch_charge_has_windup_overshoot_and_carry(self):
        self.assertTrue(LOGIC.pinch_can_start(16, True, True, 0.0))
        self.assertTrue(LOGIC.pinch_can_start(64, True, True, 0.099))
        self.assertFalse(LOGIC.pinch_can_start(15.9, True, True, 0.0))
        self.assertEqual(15, LOGIC.pinch_windup_ticks(0))
        self.assertEqual(44, LOGIC.pinch_windup_ticks(29))
        self.assertEqual((7.1, 0.0, 0.0), LOGIC.pinch_charge_destination((0, 0, 0), (5, 0, 0)))
        self.assertTrue(LOGIC.pinch_melee_can_grab(False, None))
        self.assertTrue(LOGIC.pinch_melee_can_grab(False, "minecraft:boat"))
        self.assertFalse(LOGIC.pinch_melee_can_grab(True, None))
        self.assertFalse(
            LOGIC.pinch_melee_can_grab(False, "tf_slice:pinch_beetle")
        )
        self.assertTrue(LOGIC.pinch_charge_should_continue(1, True))
        self.assertTrue(LOGIC.pinch_charge_should_continue(0, False))
        self.assertFalse(LOGIC.pinch_charge_should_continue(0, True))
        pinch = load_entity("pinch_beetle")
        self.assertNotIn("minecraft:behavior.charge_attack", pinch["components"])
        self.assertNotIn("minecraft:behavior.melee_attack", pinch["components"])
        self.assertNotIn("minecraft:behavior.random_stroll", pinch["components"])
        self.assertIn("minecraft:rideable", pinch["components"])
        normal_ai = pinch["component_groups"]["tf_slice:normal_ai"]
        self.assertEqual(4, normal_ai["minecraft:behavior.melee_attack"]["priority"])
        self.assertEqual(6, normal_ai["minecraft:behavior.random_stroll"]["priority"])
        self.assertIn("tf_slice:normal_ai", pinch["events"]["minecraft:entity_spawned"]["add"]["component_groups"])
        self.assertIn("tf_slice:normal_ai", pinch["events"]["tf_slice:start_charging"]["remove"]["component_groups"])
        self.assertIn("tf_slice:normal_ai", pinch["events"]["tf_slice:stop_charging"]["add"]["component_groups"])
        carry = pinch["component_groups"]["tf_slice:carrying"]
        self.assertEqual(LOGIC.PINCH_CARRY_WIDTH, carry["minecraft:collision_box"]["width"])
        self.assertEqual(LOGIC.PINCH_CARRY_HEIGHT, carry["minecraft:collision_box"]["height"])

    def test_production_wiring_uses_all_three_contracts(self):
        server = (
            ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        client = (
            ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        for identifier in ("tf_slice:fire_beetle", "tf_slice:slime_beetle", "tf_slice:pinch_beetle"):
            self.assertIn(identifier, server)
        for marker in (
            "beetle_combat_logic.fire_can_start",
            "beetle_combat_logic.fire_is_damaging",
            "beetle_combat_logic.fire_breath_visual_points",
            "beetle_combat_logic.fire_goal_check_ready",
            "beetle_combat_logic.pinch_can_start",
            "beetle_combat_logic.pinch_charge_destination",
            "beetle_combat_logic.pinch_attack_reach_sq",
            "CreateBulletAttributes",
            "GetSourceEntityId",
            '"slime_trail"',
            "def _start_pinch_charge_navigation",
            "beetle_combat_logic.PINCH_CHARGE_SPEED",
            'state.get("chargeNavDone")',
            '"tf_slice:start_charging"',
            '"tf_slice:stop_charging"',
            "SetRiderRideEntity",
            "SetEntityLockRider(True)",
            '"BeetleCombatEffect"',
        ):
            self.assertIn(marker, server)
        self.assertNotIn("SetEntityLockRider(entityId, True)", server)
        self.assertIn("def _set_entity_on_fire(self, entityId, seconds, burnDamage=1)", server)
        self.assertIn('"BeetleCombatEffect"', client)
        self.assertNotIn("def _update_slime_beetle", server)
        self.assertNotIn("def _spawn_slime_blob", server)
        self.assertNotIn("beetle_combat_logic.slime_projectile_velocity", server)
        self.assertNotIn("0.35 * beetle_combat_logic.PINCH_CHARGE_SPEED", server)

    def test_manual_beetle_particles_are_emitted(self):
        client = (
            ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        branch = client.split("def OnBeetleCombatEffect", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("particleComp.EmitManually(particleId)", branch)
        self.assertIn('"tf_slice:hydra_flame"', branch)
        self.assertNotIn('"minecraft:basic_flame_particle"', branch)

    def test_slime_feedback_uses_pack_owned_particle(self):
        client = (
            ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        branch = client.split("def OnBeetleCombatEffect", 1)[1].split("\n    def ", 1)[0]
        self.assertNotIn('"minecraft:slime_particle"', branch)
        self.assertIn('"tf_slice:slime_splash"', branch)

        particle_path = ROOT / "TwilightBossSliceR" / "particles" / "slime_splash.json"
        self.assertTrue(particle_path.is_file())
        particle = json.loads(particle_path.read_text(encoding="utf-8"))[
            "particle_effect"
        ]
        description = particle["description"]
        self.assertEqual("tf_slice:slime_splash", description["identifier"])
        self.assertEqual(
            "textures/blocks/slime",
            description["basic_render_parameters"]["texture"],
        )
        self.assertLessEqual(
            particle["components"]["minecraft:particle_lifetime_expression"][
                "max_lifetime"
            ],
            0.35,
        )

    def test_fire_breath_uses_last_attacker_and_source_feedback(self):
        server = (
            ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        stop = server.split("def _stop_fire_breath", 1)[1].split("\n    def ", 1)[0]
        branch = server.split("def _update_fire_beetle", 1)[1].split("\n    def ", 1)[0]
        self.assertIn('state["fireNextCheckTick"]', stop)
        self.assertIn("FIRE_GOAL_CHECK_INTERVAL_TICKS", stop)
        self.assertIn("fire_goal_check_ready", branch)
        self.assertIn('state.get("lastHurtById")', branch)
        self.assertIn('"mob.ghast.fireball"', branch)
        self.assertIn("if self._hurt(", branch)
        self.assertIn("fire_breath_visual_points", branch)

    def test_pinch_native_melee_invokes_forced_carry(self):
        server = (
            ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        hurt = server.split("def OnActuallyHurtServerEvent", 1)[1].split(
            "\n    def ", 1
        )[0]
        self.assertIn('== "tf_slice:pinch_beetle"', hurt)
        self.assertIn("beetle_combat_logic.pinch_melee_can_grab", hurt)
        self.assertIn("self._grab_pinch_target(attackerId, entityId, False)", hurt)

    def test_pinch_charge_stop_releases_component_lock_without_new_move(self):
        server = (
            ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        stop = server.split("def _stop_pinch_charge", 1)[1].split(
            "\n    def ", 1
        )[0]
        self.assertNotIn("self._cancel_move_to_path(entityId)", stop)
        self.assertIn('"tf_slice:stop_charging"', stop)


if __name__ == "__main__":
    unittest.main()
