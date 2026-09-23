"""Locked 4.3.2508 parity tests for the mosquito swarm.

User journey: as a player fighting a mosquito swarm, I should see and hear the
world entity pursue me, take its normal melee damage, and receive the original
difficulty-scaled Hunger effect without a non-source screen overlay.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PACKAGE = BP / "TwilightBossSlice"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MosquitoSwarmLogicTests(unittest.TestCase):
    def test_hunger_duration_matches_locked_difficulty_switch(self):
        import mosquito_swarm_logic

        self.assertEqual(7, mosquito_swarm_logic.hunger_seconds(1))
        self.assertEqual(15, mosquito_swarm_logic.hunger_seconds(2))
        self.assertEqual(30, mosquito_swarm_logic.hunger_seconds(3))
        self.assertEqual(15, mosquito_swarm_logic.hunger_seconds(None))

    def test_only_successful_mosquito_hits_apply_hunger(self):
        import mosquito_swarm_logic

        mosquito = "tf_slice:mosquito_swarm"
        self.assertTrue(
            mosquito_swarm_logic.should_apply_hunger(
                mosquito, damage=3.0
            )
        )
        self.assertFalse(
            mosquito_swarm_logic.should_apply_hunger(
                mosquito, damage=0.0
            )
        )
        self.assertFalse(
            mosquito_swarm_logic.should_apply_hunger(
                "tf_slice:minotaur", damage=3.0
            )
        )
        self.assertFalse(
            mosquito_swarm_logic.should_apply_hunger(
                mosquito, damage="not-a-number"
            )
        )


class MosquitoSwarmContentContractTests(unittest.TestCase):
    def test_behavior_matches_locked_goal_and_attribute_contract(self):
        entity = read_json(BP / "entities" / "mosquito_swarm.entity.json")[
            "minecraft:entity"
        ]
        components = entity["components"]

        self.assertEqual(12, components["minecraft:health"]["max"])
        self.assertEqual(0.23, components["minecraft:movement"]["value"])
        self.assertEqual(3, components["minecraft:attack"]["damage"])
        self.assertEqual(
            {"width": 0.7, "height": 1.9},
            components["minecraft:collision_box"],
        )
        self.assertEqual(16, components["minecraft:follow_range"]["value"])

        expected_priorities = {
            "minecraft:behavior.float": 0,
            "minecraft:behavior.hurt_by_target": 1,
            "minecraft:behavior.nearest_attackable_target": 2,
            "minecraft:behavior.melee_attack": 3,
            "minecraft:behavior.random_stroll": 6,
        }
        for name, priority in expected_priorities.items():
            self.assertEqual(priority, components[name]["priority"], name)

        target = components["minecraft:behavior.nearest_attackable_target"]
        self.assertTrue(target["must_see"])
        self.assertTrue(target["reselect_targets"])
        self.assertEqual(16, target["entity_types"][0]["max_dist"])
        self.assertTrue(
            components["minecraft:navigation.walk"]["avoid_water"]
        )
        self.assertIn("minecraft:behavior.random_stroll", components)
        self.assertIn("minecraft:behavior.float", components)

    def test_swamp_spawns_are_single_swarms_like_the_locked_biome(self):
        rules = read_json(BP / "spawn_rules" / "mosquito_swarm.json")
        condition = rules["minecraft:spawn_rules"]["conditions"][0]
        self.assertEqual(
            {"min_size": 1, "max_size": 1},
            condition["minecraft:herd"],
        )

    def test_empty_source_loot_and_ambient_feedback_are_present(self):
        entity = read_json(BP / "entities" / "mosquito_swarm.entity.json")[
            "minecraft:entity"
        ]
        components = entity["components"]
        self.assertEqual(
            "loot_tables/entities/tf_slice/mosquito_swarm.json",
            components["minecraft:loot"]["table"],
        )
        self.assertEqual(
            {"pools": []},
            read_json(
                BP
                / "loot_tables"
                / "entities"
                / "tf_slice"
                / "mosquito_swarm.json"
            ),
        )
        self.assertEqual(
            "ambient",
            components["minecraft:ambient_sound_interval"]["event_name"],
        )
        sounds = read_json(RP / "sounds.json")["entity_sounds"]["entities"]
        self.assertEqual(
            {"ambient": "mob.silverfish.say"},
            sounds["tf_slice:mosquito_swarm"]["events"],
        )

    def test_non_source_screen_overlay_is_fully_removed(self):
        self.assertFalse((RP / "ui" / "mosquito_overlay.json").exists())
        ui_defs = read_json(RP / "ui" / "_ui_defs.json")["ui_defs"]
        self.assertNotIn("ui/mosquito_overlay.json", ui_defs)

        for relative in (
            "clientSystem.py",
            "routeBossHudUI.py",
            "config.py",
        ):
            source = (PACKAGE / relative).read_text(encoding="utf-8")
            self.assertNotIn("mosquito_overlay", source, relative)

    def test_successful_hurt_event_applies_original_hunger_effect(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        handler = source.split("def OnActuallyHurtServerEvent", 1)[1].split(
            "def _queue_flying_hurt_stabilization", 1
        )[0]
        self.assertIn("mosquito_swarm_logic.should_apply_hunger", handler)
        self.assertIn("mosquito_swarm_logic.hunger_seconds", handler)
        self.assertIn("AddEffectToEntity(", handler)
        self.assertIn('"hunger", hungerSeconds, 0, True', handler)

        driver = source.split("def _drive_route_mobs", 1)[1].split(
            "def _drive_maze_slimes", 1
        )[0]
        self.assertNotIn("mosquito_overlay", driver)

    def test_hydra_route_generators_preserve_mosquito_parity(self):
        model_builder = (
            ROOT / "tools" / "build_hydra_route_models.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def mosquito_swarm_behavior():", model_builder)
        self.assertIn(
            '"mosquito_swarm": mosquito_swarm_behavior()', model_builder
        )

        acceptance_builder = (
            ROOT / "tools" / "build_hydra_route_acceptance.py"
        ).read_text(encoding="utf-8")
        mosquito_contract = acceptance_builder.split(
            '    "mosquito_swarm": {', 1
        )[1].split('    "hydra": {', 1)[0]
        self.assertIn("mosquito_swarm_logic.py", mosquito_contract)
        self.assertIn("tests/test_mosquito_swarm_parity.py", mosquito_contract)
        self.assertNotIn("swamp-overlay", mosquito_contract)


if __name__ == "__main__":
    unittest.main()
