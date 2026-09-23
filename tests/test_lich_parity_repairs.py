# -*- coding: utf-8 -*-
"""Regression contracts for the locked 4.3.2508 Twilight Lich port."""

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PACKAGE_ROOT = BP / "TwilightBossSlice"
sys.path.insert(0, str(PACKAGE_ROOT))

import lich_logic


def load_json(path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class LichSourceParityRepairs(unittest.TestCase):
    def test_phase_three_melee_uses_the_source_attack_attribute(self):
        state = lich_logic.new_lich_state()
        state.update(
            {
                "shieldStrength": 0,
                "minionsRemaining": 0,
                "activeMinions": 0,
                "spawnTime": 0,
                "attackCooldown": 0,
            }
        )
        actions = lich_logic.advance_combat_tick(state, 1.0, True, _ZeroRandom())
        self.assertEqual(3.0, actions[0]["damage"])

    def test_death_reward_and_home_restriction_constants_match_source(self):
        self.assertEqual(175, lich_logic.DEATH_TICKS)
        self.assertEqual(217, lich_logic.XP_REWARD)
        self.assertEqual(1.25, lich_logic.RETURN_HOME_SPEED)
        self.assertTrue(lich_logic.should_return_home(20.01))
        self.assertFalse(lich_logic.should_return_home(20.0))

    def test_position_visibility_has_a_separate_adapter(self):
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _lich_positions_can_see", server)
        self.assertNotIn("_lich_can_see(destination, targetPos, dimensionId)", server)
        self.assertNotIn("_lich_can_see(\n                destination, targetPos, dimensionId", server)
        self.assertIn("def _return_lich_home", server)
        self.assertIn("math.sqrt(_distance_sq(position, home))", server)

    def test_source_length_death_sequence_and_xp_are_server_authoritative(self):
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _begin_lich_death", server)
        self.assertIn("def _update_lich_death", server)
        self.assertIn("lich_logic.DEATH_TICKS", server)
        self.assertIn("lich_logic.XP_REWARD", server)

    def test_lifedrain_classification_is_scoped_to_the_actual_pulse(self):
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("self._recent_lifedrain_hits", server)
        self.assertNotIn(
            "matching_entity_key(\n            self._lifedrain_users, sourceId",
            server,
        )


class LichEntityAndFeedbackRepairs(unittest.TestCase):
    def test_lich_can_be_renamed_and_cannot_be_pushed(self):
        entity = load_json(BP / "entities" / "lich.entity.json")["minecraft:entity"]
        components = entity["components"]
        self.assertTrue(components["minecraft:nameable"]["allow_name_tag_renaming"])
        self.assertFalse(components["minecraft:pushable"]["is_pushable"])
        self.assertFalse(components["minecraft:pushable"]["is_pushable_by_piston"])

    def test_lich_minion_keeps_zombie_ecology_but_not_forced_persistence(self):
        entity = load_json(BP / "entities" / "lich_minion.entity.json")["minecraft:entity"]
        components = entity["components"]
        self.assertNotIn("minecraft:persistent", components)
        self.assertIn("minecraft:burns_in_daylight", components)
        self.assertIn("minecraft:behavior.nearest_attackable_target", components)
        target_filters = json.dumps(
            components["minecraft:behavior.nearest_attackable_target"],
            sort_keys=True,
        )
        for family in ("player", "villager", "iron_golem", "turtle"):
            self.assertIn(family, target_filters)
        self.assertIn("minecraft:behavior.look_at_player", components)
        self.assertIn("minecraft:behavior.random_look_around", components)
        self.assertIn("tf_slice:strengthened", entity["component_groups"])
        self.assertIn("tf_slice:set_strengthened", entity["events"])

        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        minion_loop = server[
            server.index("        for minionId, minionState") : server.index(
                "        for zombieId, loyal"
            )
        ]
        # User-requested arena rule supersedes unrestricted zombie pursuit.
        self.assertIn("self._lich_minion_target_on_floor", minion_loop)
        self.assertIn("self._keep_lich_minion_on_floor", minion_loop)

    def test_lich_sound_contract_uses_source_vanilla_events(self):
        sounds = load_json(RP / "sounds.json")
        lich = sounds["entity_sounds"]["entities"]["tf_slice:lich"]
        self.assertEqual("mob.blaze.breathe", lich["events"]["ambient"])
        self.assertEqual("mob.blaze.hit", lich["events"]["hurt"])
        self.assertEqual("mob.blaze.death", lich["events"]["death"])
        self.assertEqual("mob.ghast.fireball", lich["events"]["shoot"])
        self.assertNotIn("pop_mob", lich["events"])
        self.assertEqual(
            "mob.chorusfruit.teleport", lich["events"]["teleport"]
        )
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn('"mob.chicken.plop"', server)
        self.assertIn('"random.break", position, 1.0, 1.0', server)

    def test_phase_aware_boss_hud_is_registered(self):
        ui_defs = load_json(RP / "ui" / "_ui_defs.json")["ui_defs"]
        self.assertIn("ui/lich_boss_hud.json", ui_defs)
        hud = load_json(RP / "ui" / "lich_boss_hud.json")
        self.assertIn("lich_boss_hud", hud["namespace"])
        client = (PACKAGE_ROOT / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn("lichBossHudUI.set_bosses", client)
        self.assertIn("LichCombatEffect", client)

    def test_attack_windup_and_melee_phase_particles_are_synchronized(self):
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        client = (PACKAGE_ROOT / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn('"attackCooldown": int(', server)
        self.assertIn('"nextAttackType": int(', server)
        self.assertIn('boss.get("attackCooldown", 0)', client)
        self.assertIn("tf_slice:lich_bolt_charge", client)
        self.assertIn("tf_slice:lich_bomb_charge", client)
        self.assertIn("tf_slice:lich_angry", client)
        self.assertNotIn("minecraft:enchanting_table_particle", client)
        for name, identifier in (
            ("lich_bolt_charge.json", "tf_slice:lich_bolt_charge"),
            ("lich_bomb_charge.json", "tf_slice:lich_bomb_charge"),
        ):
            particle = load_json(RP / "particles" / name)["particle_effect"]
            self.assertEqual(identifier, particle["description"]["identifier"])
            self.assertEqual(
                "textures/particle/ominous_flame",
                particle["description"]["basic_render_parameters"]["texture"],
            )

    def test_custom_name_and_shield_helpers_are_synchronized(self):
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        hud = (PACKAGE_ROOT / "lichBossHudUI.py").read_text(encoding="utf-8")
        self.assertIn("def _lich_display_name", server)
        self.assertIn('"name": self._lich_display_name(bossId)', server)
        self.assertIn("\u5deb\u5996", hud)
        self.assertNotIn("\\u00ce\\u00d7\\u00d1\\u0131", hud)
        hud_layout = load_json(RP / "ui" / "lich_boss_hud.json")
        title = hud_layout["main"]["controls"][0]["boss_root"]["controls"][0]["title"]
        self.assertEqual("\u5deb\u5996", title["text"])
        self.assertIn('result.get("shieldContact")', server)

    def test_source_projectile_trails_and_clone_hit_feedback_are_preserved(self):
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        client = (PACKAGE_ROOT / "clientSystem.py").read_text(encoding="utf-8")
        self.assertIn('"clone_hurt"', server)
        self.assertIn('"style": str(args.get("style", ""))', client)
        self.assertIn('trailCount = 1 if "bomb" in style else 2', client)

    def test_clone_physics_and_source_death_staging_are_preserved(self):
        clone = load_json(BP / "entities" / "lich_shadow_clone.entity.json")
        components = clone["minecraft:entity"]["components"]
        self.assertFalse(components["minecraft:pushable"]["is_pushable"])
        self.assertFalse(components["minecraft:pushable"]["is_pushable_by_piston"])
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _lich_death_soul_position", server)
        self.assertIn("if deathTime == 50:", server)
        self.assertIn('"death_mid_burst"', server)


class LichAssetAndLootRepairs(unittest.TestCase):
    def test_original_projectile_and_effect_textures_are_present(self):
        expected = {
            RP / "textures" / "items" / "twilight_orb.png":
                "6C1F4D12DEAD1364038CC69440FE36BD429971FDAE9CD0650C7E0573DF547B66",
            RP / "textures" / "particle" / "ominous_flame.png":
                "62FECEFBAC21F21F3879B1D19DAEF9C7E853AC553B04B0FAE25EE96B4E67E108",
            RP / "textures" / "entity" / "tf_slice" / "chest" / "twilight" / "twilight.png":
                "F5721B8797D5B7AA6A91881E538978284D1605FDDCB2C516CFF4827D4FC0A7DE",
            RP / "textures" / "entity" / "tf_slice" / "chest" / "twilight" / "left.png":
                "61CB8B85542CF1E7B73BD4FCFBE07AB96DCFD9C21159271EFF5916B85CB2B0C3",
            RP / "textures" / "entity" / "tf_slice" / "chest" / "twilight" / "right.png":
                "F328C03C07A6932B1D7785D451670F22E2148F8FEF8833F09DD6BB409659CA31",
            RP / "textures" / "entity" / "tf_slice" / "chest" / "canopy" / "canopy.png":
                "CFF377A4A37798294755582319590EC65C3D441100175F4F705F3A626294E208",
            RP / "textures" / "entity" / "tf_slice" / "chest" / "canopy" / "left.png":
                "473A4A33D59E31185EA7AA2B79D82BD088002578AF71032A60D52DF2984E7525",
            RP / "textures" / "entity" / "tf_slice" / "chest" / "canopy" / "right.png":
                "B146BB91986BCCDF757B85AC705C136362AF901DB2E1AEA52B1D84E247A947A4",
            RP / "textures" / "entity" / "tf_slice" / "banner" / "lich.png":
                "3294924290B4E4C5ACA08EAFC99DD7C05E1C39A28E651140A48F89E019DA9D14",
        }
        for path, digest in expected.items():
            self.assertTrue(path.is_file(), str(path))
            self.assertEqual(digest, sha256(path))

    def test_projectiles_reference_source_appropriate_textures(self):
        for name in ("lich_bolt.entity.json", "twilight_wand_bolt.entity.json"):
            entity = load_json(RP / "entity" / name)["minecraft:client_entity"]
            self.assertEqual(
                "textures/items/twilight_orb",
                entity["description"]["textures"]["default"],
            )
        bomb = load_json(RP / "entity" / "lich_bomb.entity.json")
        self.assertEqual(
            "textures/items/magma_cream",
            bomb["minecraft:client_entity"]["description"]["textures"]["default"],
        )

    def test_trophy_uses_a_3d_model_and_the_lich_skin(self):
        block = load_json(BP / "netease_blocks" / "lich_trophy.json")
        components = block["minecraft:block"]["components"]
        self.assertEqual(
            "geometry.tf_slice.lich_trophy_rotation_0",
            components["minecraft:geometry"],
        )
        self.assertEqual(
            "tf_slice:lich_trophy_model",
            components["minecraft:material_instances"]["*"]["texture"],
        )
        rotation_geometry = (
            RP / "models" / "blocks" / "trophy_floor_rotations.geo.json"
        )
        self.assertTrue(rotation_geometry.is_file())
        identifiers = {
            entry["description"]["identifier"]
            for entry in load_json(rotation_geometry)["minecraft:geometry"]
        }
        self.assertIn("geometry.tf_slice.lich_trophy_rotation_0", identifiers)

    def test_reward_table_matches_source_rolls_and_counts(self):
        loot = load_json(
            BP / "loot_tables" / "chests" / "tf_slice" / "lich_tower_reward.json"
        )
        gold_pool = loot["pools"][1]
        self.assertEqual({"min": 2, "max": 4}, gold_pool["rolls"])
        self.assertEqual({1}, {entry["weight"] for entry in gold_pool["entries"]})
        for entry in gold_pool["entries"]:
            enchant = entry["functions"][0]
            self.assertEqual("enchant_with_levels", enchant["function"])
            self.assertEqual({"min": 10, "max": 40}, enchant["levels"])
        pearl_count = loot["pools"][2]["entries"][0]["functions"][0]["count"]
        bone_count = loot["pools"][3]["entries"][0]["functions"][0]["count"]
        self.assertEqual({"min": 1, "max": 4}, pearl_count)
        self.assertEqual({"min": 5, "max": 9}, bone_count)
        for pool_index in (2, 3):
            functions = loot["pools"][pool_index]["entries"][0]["functions"]
            self.assertEqual("looting_enchant", functions[1]["function"])
            self.assertEqual({"min": 0, "max": 1}, functions[1]["count"])

    def test_pop_cast_consumes_only_one_visible_source_tag_target(self):
        server = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _lich_pop_targets", server)
        execute = server[
            server.index("    def _execute_lich_action") : server.index(
                "    def _drive_lich_bosses"
            )
        ]
        self.assertNotIn("additionalTargets", execute)
        self.assertNotIn("ignoreReadiness=True", execute)


class _ZeroRandom(object):
    def randrange(self, maximum):
        return 0

    def triangular(self, low, high, mode):
        return 0.0


if __name__ == "__main__":
    unittest.main()
