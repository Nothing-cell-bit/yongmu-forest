import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
sys.path.insert(0, str(BP))

from TwilightBossSlice import spawn_policy


DIMENSION_ID = 33027004
DARK_FOREST_CENTER = "dm33027004_redwood_taiga_mutated"


class TwilightSpawnIsolationTests(unittest.TestCase):
    def test_natural_vanilla_mobs_are_cancelled_in_twilight(self):
        self.assertTrue(
            spawn_policy.should_cancel_twilight_spawn(
                {
                    "identifier": "minecraft:zombie",
                    "realIdentifier": "minecraft:zombie",
                    "dimensionId": DIMENSION_ID,
                },
                DIMENSION_ID,
            )
        )

    def test_vanilla_allowlist_fails_closed_without_a_biome(self):
        self.assertTrue(
            spawn_policy.should_cancel_twilight_spawn(
                {
                    "identifier": "minecraft:chicken",
                    "realIdentifier": "minecraft:chicken",
                    "dimensionId": DIMENSION_ID,
                },
                DIMENSION_ID,
                biome_identifier=None,
            )
        )

    def test_natural_twilight_mobs_are_allowed(self):
        self.assertFalse(
            spawn_policy.should_cancel_twilight_spawn(
                {
                    "identifier": "tf_slice:deer",
                    "realIdentifier": "tf_slice:deer",
                    "dimensionId": DIMENSION_ID,
                },
                DIMENSION_ID,
            )
        )

    def test_mod_api_test_spawns_remain_available(self):
        self.assertFalse(
            spawn_policy.should_cancel_twilight_spawn(
                {
                    "identifier": "custom",
                    "realIdentifier": "minecraft:zombie",
                    "dimensionId": DIMENSION_ID,
                },
                DIMENSION_ID,
            )
        )

    def test_dark_forest_center_rejects_every_natural_spawn_table(self):
        for identifier in (
            "minecraft:chicken",
            "minecraft:wolf",
            "tf_slice:deer",
        ):
            self.assertTrue(
                spawn_policy.should_cancel_twilight_spawn(
                    {
                        "identifier": identifier,
                        "realIdentifier": identifier,
                        "dimensionId": DIMENSION_ID,
                    },
                    DIMENSION_ID,
                    biome_identifier=DARK_FOREST_CENTER,
                ),
                identifier,
            )

    def test_dark_forest_rejects_native_tables_for_controlled_replacement(self):
        dark_forest = spawn_policy.biome_catalog.BIOMES_BY_KEY[
            "dark_forest"
        ]["identifier"]
        for identifier in (
            "minecraft:zombie",
            "tf_slice:kobold",
            "tf_slice:mist_wolf",
        ):
            self.assertTrue(
                spawn_policy.should_cancel_twilight_spawn(
                    {
                        "identifier": identifier,
                        "realIdentifier": identifier,
                        "dimensionId": DIMENSION_ID,
                    },
                    DIMENSION_ID,
                    biome_identifier=dark_forest,
                ),
                identifier,
            )

    def test_dark_forest_center_keeps_explicit_scripted_spawns(self):
        self.assertFalse(
            spawn_policy.should_cancel_twilight_spawn(
                {
                    "identifier": "custom",
                    "realIdentifier": "tf_slice:tower_ghast",
                    "dimensionId": DIMENSION_ID,
                },
                DIMENSION_ID,
                biome_identifier=DARK_FOREST_CENTER,
            )
        )

    def test_other_dimensions_are_not_changed(self):
        self.assertFalse(
            spawn_policy.should_cancel_twilight_spawn(
                {
                    "identifier": "minecraft:zombie",
                    "realIdentifier": "minecraft:zombie",
                    "dimensionId": 0,
                },
                DIMENSION_ID,
            )
        )

    def test_server_spawn_hook_applies_policy_before_boss_handling(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        policy_call = source.index(
            "spawn_policy.should_cancel_twilight_spawn"
        )
        boss_guard = source.index(
            "if identifier != config.BOSS_IDENTIFIER:",
            policy_call,
        )
        self.assertLess(policy_call, boss_guard)


if __name__ == "__main__":
    unittest.main()
