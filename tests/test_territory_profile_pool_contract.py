# -*- coding: utf-8 -*-
import importlib
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
PROFILE_PATH = BP / "TwilightBossSlice" / "territory_profiles.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))


class TerritoryProfilePoolContractTests(unittest.TestCase):
    def _load_isolated_catalog(self, profile_payload=None):
        source = BP / "TwilightBossSlice" / "biome_catalog.py"
        temporary_directory = tempfile.TemporaryDirectory()
        isolated_root = Path(temporary_directory.name)
        isolated_source = isolated_root / "biome_catalog.py"
        if profile_payload is not None:
            (isolated_root / "territory_profiles.json").write_text(
                profile_payload,
                encoding="utf-8",
            )
        try:
            namespace = {
                "__file__": str(isolated_source),
                "__name__": "isolated_biome_catalog",
            }
            exec(
                compile(
                    source.read_text(encoding="utf-8"),
                    str(source),
                    "exec",
                ),
                namespace,
            )
            return namespace
        finally:
            temporary_directory.cleanup()

    def test_catalog_import_survives_missing_runtime_profile_sidecar(self):
        catalog = self._load_isolated_catalog()
        self.assertEqual(
            (
                "fire_route",
                "dark_route",
                "glacier_route",
                "final_highlands_route",
            ),
            tuple(
                profile["id"]
                for profile in catalog["ACTIVE_TERRITORY_PROFILES"]
            ),
        )
        self.assertEqual(
            ("fire_route", "dark_route"),
            tuple(
                profile["id"]
                for profile in catalog[
                    "ACTIVE_TERRITORY_CONTENT_PROFILES"
                ]
            ),
        )
        self.assertTrue(catalog["TERRITORY_PROFILE_LOAD_ERROR"])

    def test_catalog_import_survives_invalid_runtime_profile_sidecar(self):
        catalog = self._load_isolated_catalog("{not valid json")
        self.assertEqual(4, len(catalog["TERRITORY_PROFILES"]))
        self.assertEqual(4, len(catalog["TERRITORY_SLOT_LOCALS"]))
        self.assertTrue(catalog["TERRITORY_PROFILE_LOAD_ERROR"])

    def test_profile_pool_reserves_all_four_upstream_slots(self):
        self.assertTrue(PROFILE_PATH.is_file())
        document = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(1, document["schemaVersion"])
        self.assertEqual(
            [[2, 2], [6, 2], [6, 6], [2, 6]],
            document["slotLocals"],
        )
        profiles = document["profiles"]
        self.assertEqual(4, len(profiles))
        self.assertEqual(
            ["fire_route", "dark_route", "glacier_route", "final_highlands_route"],
            [profile["id"] for profile in profiles],
        )
        self.assertEqual([0, 1, 2, 3], [profile["homeSlot"] for profile in profiles])
        self.assertEqual(
            ["fire_route", "dark_route"],
            [profile["id"] for profile in profiles if profile["enabled"]],
        )
        self.assertEqual(
            ["glacier_route", "final_highlands_route"],
            [profile["id"] for profile in profiles if not profile["enabled"]],
        )
        self.assertEqual(
            ["fire_route", "dark_route"],
            [profile["fallbackProfile"] for profile in profiles[2:]],
        )

    def test_catalog_geometry_is_derived_from_enabled_profiles(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        self.assertEqual(4, len(catalog.TERRITORY_PROFILES))
        self.assertEqual(
            (
                "fire_route",
                "dark_route",
                "glacier_route",
                "final_highlands_route",
            ),
            tuple(profile["id"] for profile in catalog.ACTIVE_TERRITORY_PROFILES),
        )
        self.assertEqual(
            ("fire_route", "dark_route"),
            tuple(
                profile["id"]
                for profile in catalog.ACTIVE_TERRITORY_CONTENT_PROFILES
            ),
        )
        self.assertEqual(
            ((2, 2), (6, 2), (6, 6), (2, 6)),
            catalog.TERRITORY_SLOT_LOCALS,
        )
        for variant in range(4):
            expected = {}
            for profile in catalog.ACTIVE_TERRITORY_PROFILES:
                slot = (int(profile["homeSlot"]) + variant) % 4
                expected[profile["id"]] = catalog.TERRITORY_SLOT_LOCALS[slot]
            self.assertEqual(
                expected,
                catalog.ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT[variant],
            )

    def test_fallback_profiles_fill_all_slots_and_preserve_each_cardinal_group(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        expected_profile_ids = {
            "fire_route",
            "dark_route",
            "glacier_route",
            "final_highlands_route",
        }
        self.assertEqual(
            Counter({"fire_swamp": 2, "dark_forest_center": 2}),
            Counter(
                profile["coreBiome"]
                for profile in catalog.ACTIVE_TERRITORY_PROFILES
            ),
        )
        for variant in catalog.ROUTE_LAYOUT_VARIANTS:
            cores = catalog.ROUTE_PROFILE_CORE_LOCALS_BY_VARIANT[variant]
            companions = (
                catalog.ROUTE_PROFILE_COMPANION_LOCALS_BY_VARIANT[variant]
            )
            self.assertEqual(expected_profile_ids, set(cores))
            self.assertEqual(set(catalog.TERRITORY_SLOT_LOCALS), set(cores.values()))
            for profile_id, core in cores.items():
                self.assertEqual(
                    {
                        (core[0] - 1, core[1]),
                        (core[0] + 1, core[1]),
                        (core[0], core[1] - 1),
                        (core[0], core[1] + 1),
                    },
                    set(companions[profile_id]),
                )

    def test_structure_mapping_and_phases_come_from_the_same_profiles(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        for profile in catalog.ACTIVE_TERRITORY_CONTENT_PROFILES:
            core = catalog.BIOMES_BY_KEY[profile["coreBiome"]]["identifier"]
            companion = catalog.BIOMES_BY_KEY[profile["companionBiome"]]["identifier"]
            self.assertEqual(
                profile["mainLandmark"],
                catalog.SPECIAL_LANDMARK_BY_BIOME[core],
            )
            self.assertEqual(
                profile["companionLandmark"],
                catalog.SPECIAL_LANDMARK_BY_BIOME[companion],
            )
            self.assertEqual(
                profile["outerPhase"],
                catalog.ROUTE_OUTER_PHASE_OFFSET_BY_KEY[profile["coreBiome"]],
            )
            self.assertEqual(
                profile["corePhase"],
                catalog.ROUTE_CORE_PHASE_OFFSET_BY_KEY[profile["coreBiome"]],
            )

    def test_magic_map_route_palette_comes_from_enabled_profiles(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        map_logic = importlib.import_module("TwilightBossSlice.magic_map_logic")
        bitmap = importlib.import_module(
            "TwilightBossSlice.magic_map_bitmap_cache"
        )
        expected_tail = tuple(
            biome_key
            for profile in catalog.ACTIVE_TERRITORY_CONTENT_PROFILES
            for biome_key in (
                profile["companionBiome"],
                profile["coreBiome"],
            )
        )
        self.assertEqual(
            expected_tail,
            map_logic.TWILIGHT_BIOME_PALETTE[-len(expected_tail) :],
        )
        for profile in catalog.ACTIVE_TERRITORY_CONTENT_PROFILES:
            self.assertEqual(
                tuple(profile["companionMapColor"]),
                bitmap.MAGIC_MAP_BIOME_RGBA[profile["companionBiome"]],
            )
            self.assertEqual(
                tuple(profile["coreMapColor"]),
                bitmap.MAGIC_MAP_BIOME_RGBA[profile["coreBiome"]],
            )
        palette_builder = (
            ROOT / "tools" / "generate_magic_map_hud_pool.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("territory_profiles.json", palette_builder)
        self.assertIn("companionMapColor", palette_builder)
        self.assertIn("coreMapColor", palette_builder)

    def test_dimension_stage_specs_iterate_enabled_profiles_without_geometry_code(self):
        catalog = importlib.import_module("TwilightBossSlice.biome_catalog")
        builder = importlib.import_module("tools.build_dark_forest_biomes")
        seed_specs = builder.route_seed_stage_specs()
        stabilize_specs = builder.route_stabilize_stage_specs()
        self.assertEqual(
            2 * len(catalog.ACTIVE_TERRITORY_CONTENT_PROFILES),
            len(seed_specs),
        )
        self.assertEqual(
            2 * len(catalog.ACTIVE_TERRITORY_CONTENT_PROFILES),
            len(stabilize_specs),
        )
        self.assertEqual(
            [
                (profile["companionBiome"], profile["id"])
                for profile in catalog.ACTIVE_TERRITORY_CONTENT_PROFILES
                for _kind in ("companion",)
            ]
            + [],
            [
                (spec["biomeKey"], spec["profileId"])
                for spec in seed_specs[::2]
            ],
        )
        for profile_index, profile in enumerate(
            catalog.ACTIVE_TERRITORY_CONTENT_PROFILES
        ):
            seed_pair = seed_specs[profile_index * 2 : profile_index * 2 + 2]
            stable_pair = stabilize_specs[profile_index * 2 : profile_index * 2 + 2]
            self.assertEqual(
                [profile["companionBiome"], profile["coreBiome"]],
                [spec["biomeKey"] for spec in seed_pair],
            )
            self.assertEqual(
                [profile["companionBiome"], profile["coreBiome"]],
                [spec["biomeKey"] for spec in stable_pair],
            )
            self.assertTrue(all(spec["profileId"] == profile["id"] for spec in seed_pair))
            self.assertTrue(all(spec["profileId"] == profile["id"] for spec in stable_pair))
            expected_instances = tuple(
                instance["id"]
                for instance in catalog.ACTIVE_TERRITORY_PROFILES
                if instance["sourceProfileId"] == profile["id"]
            )
            self.assertTrue(
                all(
                    spec["profileIds"] == expected_instances
                    for spec in seed_pair + stable_pair
                )
            )
            for spec in seed_pair:
                sizes = tuple(
                    len(spec["geometryByVariant"][variant])
                    for variant in catalog.ROUTE_LAYOUT_VARIANTS
                )
                expected_size = (
                    4 * len(expected_instances)
                    if spec["biomeKey"] == profile["companionBiome"]
                    else len(expected_instances)
                )
                self.assertEqual((expected_size,) * 4, sizes)


if __name__ == "__main__":
    unittest.main()
