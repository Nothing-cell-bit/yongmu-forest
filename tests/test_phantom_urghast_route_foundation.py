# -*- coding: utf-8 -*-
import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
PACKAGE_ROOT = BP / "TwilightBossSlice"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

import route_progression_logic
from TwilightBossSlice import biome_catalog


class PhantomUrGhastProgressionFoundationTests(unittest.TestCase):
    def test_v3_adds_route_fields_without_losing_hydra_progress(self):
        migrated = route_progression_logic.migrate_progress(
            {
                "version": 2,
                "tf_naga_defeated": True,
                "tf_lich_defeated": True,
                "tf_minoshroom_defeated": True,
                "tf_meef_stroganoff_eaten": True,
                "tf_hydra_defeated": True,
            }
        )
        self.assertEqual(3, migrated["version"])
        for field in (
            "naga_defeated",
            "lich_defeated",
            "minoshroom_defeated",
            "meef_stroganoff_eaten",
            "hydra_defeated",
        ):
            self.assertTrue(migrated[field], field)
        for field in (
            "trophy_pedestal_activated",
            "knight_phantoms_defeated",
            "ghast_trap_activated",
            "ur_ghast_defeated",
        ):
            self.assertFalse(migrated[field], field)

    def test_lich_opens_dark_forest_without_hydra_route_requirements(self):
        progress = route_progression_logic.default_progress()
        progress["lich_defeated"] = True
        self.assertTrue(route_progression_logic.can_enter_dark_forest(progress))
        self.assertFalse(progress["minoshroom_defeated"])
        self.assertFalse(progress["meef_stroganoff_eaten"])
        self.assertFalse(progress["hydra_defeated"])

    def test_stronghold_and_dark_tower_have_separate_route_gates(self):
        progress = route_progression_logic.default_progress()
        progress["lich_defeated"] = True
        self.assertFalse(
            route_progression_logic.can_enter_knight_stronghold(progress)
        )
        progress["trophy_pedestal_activated"] = True
        self.assertTrue(
            route_progression_logic.can_enter_knight_stronghold(progress)
        )
        self.assertFalse(
            route_progression_logic.can_enter_dark_forest_center(progress)
        )
        progress["knight_phantoms_defeated"] = True
        self.assertTrue(
            route_progression_logic.can_enter_dark_forest_center(progress)
        )
        self.assertTrue(route_progression_logic.can_enter_dark_tower(progress))

    def test_center_restriction_matches_progress_knights_only(self):
        progress = route_progression_logic.default_progress()
        progress["knight_phantoms_defeated"] = True
        self.assertFalse(progress["lich_defeated"])
        self.assertTrue(
            route_progression_logic.can_enter_dark_forest_center(progress)
        )
        locked = route_progression_logic.biome_penalty(
            "dark_forest_center",
            route_progression_logic.default_progress(),
        )
        self.assertEqual(
            {"effect": "darkness", "duration": 100, "amplifier": 0},
            locked,
        )

    def test_trap_progress_is_not_an_ur_ghast_death_prerequisite(self):
        progress = route_progression_logic.default_progress()
        progress["lich_defeated"] = True
        progress["trophy_pedestal_activated"] = True
        progress["knight_phantoms_defeated"] = True
        self.assertFalse(progress["ghast_trap_activated"])
        self.assertTrue(route_progression_logic.can_credit_ur_ghast(progress))


class PhantomUrGhastBiomeFoundationTests(unittest.TestCase):
    def test_two_key_biomes_are_equal_weight_and_fully_enveloped(self):
        self.assertEqual(
            ("fire_swamp", "dark_forest_center"),
            biome_catalog.RARE_KEY_BIOME_KEYS,
        )
        self.assertEqual(
            ("swamp", "dark_forest"),
            biome_catalog.ASSOCIATED_BIOME_KEYS,
        )
        self.assertEqual(
            {1},
            {entry["weight"] for entry in biome_catalog.RARE_KEY_BIOMES},
        )
        for key, envelope in (
            ("fire_swamp", "swamp"),
            ("dark_forest_center", "dark_forest"),
        ):
            self.assertEqual(
                envelope,
                biome_catalog.RARE_KEY_COMPANION_KEYS[key],
            )
            self.assertEqual(
                {(0, 0)} | set(biome_catalog.IMMEDIATE_COMPANION_POSITIONS),
                set(biome_catalog.KEY_BIOME_CORE_POSITIONS),
            )
            self.assertEqual(8, len(biome_catalog.IMMEDIATE_COMPANION_POSITIONS))

    def test_dark_forest_center_has_no_direct_stream_seam(self):
        pairs = {frozenset(pair) for pair in biome_catalog.STREAM_TRANSITION_KEY_PAIRS}
        self.assertNotIn(
            frozenset(("dark_forest", "dark_forest_center")), pairs
        )
        self.assertIn(frozenset(("dark_forest", "forest")), pairs)

    def test_magic_map_landmarks_are_absolute_biome_mappings(self):
        self.assertEqual(
            "knight_stronghold",
            biome_catalog.SPECIAL_LANDMARK_BY_BIOME[
                "dm33027004_roofed_forest_mutated"
            ],
        )
        self.assertEqual(
            "dark_tower",
            biome_catalog.SPECIAL_LANDMARK_BY_BIOME[
                "dm33027004_redwood_taiga_mutated"
            ],
        )


class PhantomUrGhastReleaseFoundationTests(unittest.TestCase):
    def test_release_version_is_a_single_importable_source(self):
        release = importlib.import_module("release_metadata")
        self.assertEqual((0, 12, 0), release.PACK_VERSION)
        self.assertEqual("0.12.0", release.PACK_VERSION_STRING)
        for manifest_path in (BP / "manifest.json", ROOT / "TwilightBossSliceR" / "manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                list(release.PACK_VERSION), manifest["header"]["version"]
            )

    def test_progress_keys_preserve_v2_until_v3_write_succeeds(self):
        config = importlib.import_module("config")
        self.assertEqual("tf_slice:boss_progress_v3", config.PLAYER_PROGRESS_KEY)
        self.assertIn(
            "tf_slice:boss_progress_v2", config.LEGACY_PLAYER_PROGRESS_KEYS
        )
        self.assertIn(
            "tf_slice:boss_progress_v1", config.LEGACY_PLAYER_PROGRESS_KEYS
        )

    def test_route_source_lock_records_required_jar_and_commit(self):
        lock_path = ROOT / "source_locks" / "phantom_urghast_route.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(3, lock["schemaVersion"])
        self.assertEqual(
            "0BDC89263616D1B35C32EF82C5E9C14CBD20368E2FE8B468C72A28320BE7A778",
            lock["source"]["jarSha256"],
        )
        self.assertEqual(
            "a7dd8f13c653e137f977f5ffaa870fcb20fc1625",
            lock["source"]["sourceCommit"],
        )
        categories = set(lock["inventories"])
        self.assertEqual(
            {
                "structures",
                "entities",
                "blocks",
                "items",
                "recipes",
                "lootTables",
                "sounds",
                "models",
                "effects",
            },
            categories,
        )

    def test_server_migrates_all_legacy_keys_and_exposes_new_objectives(self):
        source = (PACKAGE_ROOT / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("for legacyKey in config.LEGACY_PLAYER_PROGRESS_KEYS", source)
        for objective in (
            "tf_trophy_pedestal_activated",
            "tf_knight_phantoms_defeated",
            "tf_ghast_trap_activated",
            "tf_ur_ghast_defeated",
        ):
            self.assertIn('"%s"' % objective, source)
        self.assertIn('penalty["effect"] == "darkness"', source)


if __name__ == "__main__":
    unittest.main()
