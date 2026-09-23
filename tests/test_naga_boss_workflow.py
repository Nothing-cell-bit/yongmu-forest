# -*- coding: utf-8 -*-
import hashlib
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
sys.path.insert(0, str(PACKAGE_ROOT))

import naga_logic


SERVER = PACKAGE_ROOT / "serverSystem.py"
CLIENT = PACKAGE_ROOT / "clientSystem.py"
NAGA_HUD_LOGIC = PACKAGE_ROOT / "nagaBossHudUI.py"
NAGA_HUD_JSON = ROOT / "TwilightBossSliceR" / "ui" / "naga_boss_hud.json"
UI_DEFS = ROOT / "TwilightBossSliceR" / "ui" / "_ui_defs.json"
BP_ITEMS = ROOT / "TwilightBossSliceB" / "items"
BP_RECIPES = ROOT / "TwilightBossSliceB" / "recipes"
RP_ITEMS = ROOT / "TwilightBossSliceR" / "textures" / "items"
UPSTREAM_ITEMS = (
    ROOT
    / "tmp"
    / "upstream-twilightforest"
    / "src"
    / "main"
    / "resources"
    / "assets"
    / "twilightforest"
    / "textures"
    / "item"
)
BOSS_EVIDENCE = ROOT / "boss_acceptance" / "naga.json"
BOSS_VALIDATOR = (
    ROOT
    / ".agents"
    / "skills"
    / "port-boss-entities"
    / "scripts"
    / "validate_boss_evidence.py"
)
MODEL_VALIDATOR = (
    ROOT
    / ".agents"
    / "skills"
    / "port-entity-models"
    / "scripts"
    / "validate_model_acceptance.py"
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class NagaDeathSequenceTests(unittest.TestCase):
    def test_locked_source_death_timeline_and_xp(self):
        self.assertEqual(24, naga_logic.DEATH_ANIMATION_TICKS)
        self.assertEqual(120, naga_logic.DEATH_PARTICLE_TICKS)
        self.assertEqual(144, naga_logic.DEATH_TICKS)
        self.assertEqual(217, naga_logic.XP_REWARD)

    def test_death_trail_starts_after_animation_and_follows_source_curve(self):
        start = (0.0, 65.5, 0.0)
        end = (20.0, 64.5, 10.0)
        self.assertEqual([], naga_logic.death_trail_positions(start, end, 24))
        first = naga_logic.death_trail_positions(start, end, 25)
        self.assertEqual(1, len(first))
        self.assertEqual(start[0], first[0][0])
        self.assertEqual(start[1], first[0][1])
        self.assertLess(abs(first[0][2] - start[2]), 2.01)
        final = naga_logic.death_trail_positions(start, end, 143)
        self.assertEqual(16, len(final))
        self.assertGreater(max(position[0] for position in final), 19.0)
        self.assertLess(max(position[0] for position in final), 20.5)
        self.assertEqual([], naga_logic.death_trail_positions(start, end, 144))

    def test_death_finish_uses_three_source_clouds_of_forty_particles(self):
        destination = (20.5, 64.15, 10.5)
        self.assertEqual(
            [],
            naga_logic.death_burst_positions(
                destination, 140, random.Random(7)
            ),
        )
        for death_time in (141, 142, 143):
            positions = naga_logic.death_burst_positions(
                destination, death_time, random.Random(7)
            )
            self.assertEqual(40, len(positions))
            self.assertTrue(
                all(abs(position[0] - destination[0]) < 1.5 for position in positions)
            )
        self.assertEqual(
            [],
            naga_logic.death_burst_positions(
                destination, 144, random.Random(7)
            ),
        )

    def test_brain_snapshot_restores_mid_fight_state(self):
        brain = naga_logic.NagaBrain()
        brain.state = naga_logic.DAZE
        brain.counter = 37
        brain.clockwise = True
        brain.damage_during_stun = 9
        restored = naga_logic.NagaBrain.from_snapshot(brain.snapshot())
        self.assertEqual(naga_logic.DAZE, restored.state)
        self.assertEqual(37, restored.counter)
        self.assertTrue(restored.clockwise)
        self.assertEqual(9, restored.damage_during_stun)


class NagaServerBossContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = SERVER.read_text(encoding="utf-8")
        cls.client = CLIENT.read_text(encoding="utf-8")

    def test_server_runs_persisted_staged_death_and_atomic_reward(self):
        for marker in (
            "def _begin_naga_death(",
            "def _update_naga_death(",
            "def _finalize_naga_death(",
            "def _spawn_naga_experience(",
            "naga_logic.death_trail_positions(",
            "naga_logic.death_burst_positions(",
            'self._ruin_worldgen.claim_boss_reward(',
            '"naga"',
        ):
            self.assertIn(marker, self.server)
        self.assertIn("naga_logic.XP_REWARD", self.server)
        self.assertIn('state.get("dying")', self.server)
        self.assertIn('"deathTime"', self.server)
        self.assertIn('"lootAwarded"', self.server)

    def test_only_accepted_player_damage_creates_persisted_participants(self):
        self.assertIn('"participants"', self.server)
        self.assertIn('state["participants"].add(str(attackerId))', self.server)
        award = self.server[self.server.index("    def _award_naga_progress") :]
        award = award[: award.index("    def _lich_player_candidate")]
        self.assertIn("participantIds", award)
        self.assertIn("if str(playerId) not in participantIds", award)
        self.assertNotIn("naga_logic.inside_home(playerPos, home)", award)

    def test_client_renders_source_death_trail_and_custom_ten_notch_hud(self):
        self.assertIn('"NagaDeathEffect"', self.client)
        self.assertIn("def OnNagaDeathEffect(", self.client)
        death_effect = self.client[self.client.index("    def OnNagaDeathEffect") :]
        death_effect = death_effect[: death_effect.index("    def OnNagaCombatEffect")]
        self.assertIn('"tf_slice:naga_composter_single"', death_effect)
        self.assertIn('"tf_slice:naga_death_burst_single"', death_effect)
        self.assertNotIn('"minecraft:crop_growth_emitter"', death_effect)
        self.assertTrue(NAGA_HUD_LOGIC.is_file())
        self.assertTrue(NAGA_HUD_JSON.is_file())
        self.assertIn("nagaBossHudUI", self.client)
        hud = json.loads(NAGA_HUD_JSON.read_text(encoding="utf-8"))
        self.assertEqual("naga_boss_hud", hud["namespace"])
        frame = hud["main"]["controls"][0]["boss_root"][
            "controls"
        ][1]["bar_frame"]
        notches = [
            control
            for control in frame["controls"]
            if next(iter(control)).startswith("notch_")
        ]
        self.assertEqual(9, len(notches))
        self.assertIn("ui/naga_boss_hud.json", json.loads(UI_DEFS.read_text(encoding="utf-8"))["ui_defs"])


class NagaRelatedItemTests(unittest.TestCase):
    def test_naga_armor_items_match_source_material_stats(self):
        expectations = {
            "naga_chestplate": ("slot.armor.chest", 7, 336, "armor_torso"),
            "naga_leggings": ("slot.armor.legs", 6, 315, "armor_legs"),
        }
        for name, (slot, protection, durability, enchant_slot) in expectations.items():
            item_path = BP_ITEMS / (name + ".item.json")
            texture_path = RP_ITEMS / (name + ".png")
            source_texture = UPSTREAM_ITEMS / (name + ".png")
            self.assertTrue(item_path.is_file(), name)
            self.assertTrue(texture_path.is_file(), name)
            self.assertEqual(sha256(source_texture), sha256(texture_path), name)
            components = json.loads(item_path.read_text(encoding="utf-8"))[
                "minecraft:item"
            ]["components"]
            self.assertEqual(slot, components["minecraft:wearable"]["slot"])
            self.assertEqual(
                protection, components["minecraft:wearable"]["protection"]
            )
            self.assertEqual(
                durability,
                components["minecraft:durability"]["max_durability"],
            )
            self.assertEqual(
                enchant_slot, components["minecraft:enchantable"]["slot"]
            )
            self.assertEqual(15, components["minecraft:enchantable"]["value"])

    def test_scale_recipes_restore_both_original_armor_patterns(self):
        expectations = {
            "naga_chestplate": ["# #", "###", "###"],
            "naga_leggings": ["###", "# #", "# #"],
        }
        for name, pattern in expectations.items():
            recipe = json.loads(
                (BP_RECIPES / (name + ".recipe.json")).read_text(encoding="utf-8")
            )["minecraft:recipe_shaped"]
            self.assertEqual(pattern, recipe["pattern"])
            self.assertEqual(
                {"item": "tf_slice:naga_scale"}, recipe["key"]["#"]
            )
            self.assertEqual("tf_slice:" + name, recipe["result"]["item"])
            self.assertEqual("AlwaysUnlocked", recipe["unlock"]["context"])

    def test_base_scale_drop_uses_locked_six_to_eleven_range(self):
        loot = json.loads(
            (
                ROOT
                / "TwilightBossSliceB"
                / "loot_tables"
                / "chests"
                / "naga_courtyard.json"
            ).read_text(encoding="utf-8")
        )
        count = loot["pools"][0]["entries"][0]["functions"][0]["count"]
        self.assertEqual({"min": 6, "max": 11}, count)


class NagaAcceptanceEvidenceTests(unittest.TestCase):
    def test_boss_evidence_preserves_the_current_visual_rejection(self):
        self.assertTrue(BOSS_EVIDENCE.is_file())
        evidence = json.loads(BOSS_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual("rejected", evidence["status"])
        self.assertEqual("rejected", evidence["tracks"]["model"]["status"])
        self.assertEqual("rejected", evidence["tracks"]["assets"]["status"])
        result = subprocess.run(
            [
                sys.executable,
                str(BOSS_VALIDATOR),
                str(BOSS_EVIDENCE),
                "--root",
                str(ROOT),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_entity_source_and_behavior_gate_passes(self):
        result = subprocess.run(
            [
                sys.executable,
                str(MODEL_VALIDATOR),
                "--entity",
                "forest_wyrm",
                "--require-behavior-implemented",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
