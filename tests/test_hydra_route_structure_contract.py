# -*- coding: utf-8 -*-
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
CATALOG_PATH = (
    BP / "structures" / "tf_slice" / "ruins" / "structure_catalog_v1.json"
)
ROUTE_ROOT = BP / "structures" / "tf_slice" / "ruins"


class HydraRouteStructureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads(CATALOG_PATH.read_text("utf-8"))
        cls.entries = {entry["id"]: entry for entry in catalog["structures"]}

    def test_eight_deterministic_variants_and_surface_passes(self):
        expected = {
            "labyrinth": ("surface_pass", [112, 54, 112]),
            "hydra_lair": ("surface_pass", [80, 43, 80]),
        }
        for identifier, (placement_pass, source_size) in expected.items():
            entry = self.entries[identifier]
            self.assertEqual(placement_pass, entry["placementPass"])
            self.assertEqual(8, len(entry["variants"]))
            self.assertEqual(list(range(8)), [v["layoutSeed"] for v in entry["variants"]])
            self.assertEqual(8, len({v["layoutSha256"] for v in entry["variants"]}))
            for variant in entry["variants"]:
                native = variant["surfaceNative"]
                self.assertEqual(placement_pass, native["placementPass"])
                expected_anchor = {"mode": "center_height", "radius": 0}
                self.assertEqual(expected_anchor, native["terrainAnchor"])
                self.assertEqual(
                    12,
                    native["terrainClearance"],
                )
                self.assertEqual(source_size, native["sourceSize"])
                environment = native["environmentIntegration"]
                self.assertFalse(environment["runtimeWrites"])
                self.assertEqual("native_biome_decorations", environment["mode"])
                self.assertEqual(0, environment["bakedTrees"])
                self.assertEqual(0, environment["bakedGroundcover"])
                self.assertEqual(0, environment["protectedColumns"])

    def test_all_route_pieces_are_real_sixteen_by_sixteen_or_smaller(self):
        for identifier in ("labyrinth", "hydra_lair"):
            for variant in self.entries[identifier]["variants"]:
                for piece in variant["pieces"]:
                    self.assertLessEqual(piece["size"][0], 16)
                    self.assertLessEqual(piece["size"][2], 16)
                    path = BP / "structures" / (piece["structure"] + ".mcstructure")
                    self.assertTrue(path.is_file(), path)
                    self.assertGreater(path.stat().st_size, 64)

    def test_labyrinth_metadata_covers_levels_map_chests_boss_and_spawns(self):
        entry = self.entries["labyrinth"]
        self.assertEqual(3, entry["clearanceChunks"])
        spawn_contract = entry["controlledSpawns"]
        weights = [
            (row["entity"], row["weight"], row["group"][0], row["group"][1])
            for row in spawn_contract["weights"]
        ]
        self.assertEqual(
            [
                ("tf_slice:minotaur", 20, 2, 3),
                ("minecraft:cave_spider", 10, 1, 2),
                ("minecraft:creeper", 10, 1, 2),
                ("tf_slice:maze_slime", 10, 2, 4),
                ("minecraft:enderman", 1, 1, 2),
                ("tf_slice:fire_beetle", 10, 1, 2),
                ("tf_slice:slime_beetle", 10, 1, 2),
                ("tf_slice:pinch_beetle", 10, 1, 1),
            ],
            weights,
        )
        self.assertEqual(18, spawn_contract["cap"])
        for variant in entry["variants"]:
            markers = variant["markers"]
            self.assertTrue(markers["connected"])
            self.assertEqual([12, 2], markers["levels"])
            self.assertEqual("minoshroom", markers["boss"]["kind"])
            self.assertGreaterEqual(len(markers["chests"]), 4)
            self.assertEqual({"2", "12"}, set(markers["mapPassageRuns"]))
            self.assertTrue(all(markers["mapPassageRuns"].values()))

    def test_labyrinth_boss_spawner_matches_source_range_height_and_progression(self):
        entry = self.entries["labyrinth"]
        self.assertEqual(9, entry["bossSpawner"]["activationRadius"])
        self.assertEqual(-1.5, entry["bossSpawner"]["spawnYOffset"])
        self.assertEqual(3.5, entry["bossSpawner"]["maxPlayerYOffset"])
        self.assertNotIn("progressAll", entry["bossSpawner"])
        for variant in entry["variants"]:
            spawner = variant["bossSpawner"]
            self.assertEqual(9, spawner["activationRadius"])
            self.assertEqual(-1.5, spawner["spawnYOffset"])
            self.assertEqual(3.5, spawner["maxPlayerYOffset"])
            self.assertNotIn("progressAll", spawner)

    def test_hydra_lair_geology_and_boss_marker_are_complete(self):
        entry = self.entries["hydra_lair"]
        self.assertEqual(2, entry["clearanceChunks"])
        self.assertEqual(50, entry["bossSpawner"]["activationRadius"])
        self.assertNotIn("progressAll", entry["bossSpawner"])
        for variant in entry["variants"]:
            markers = variant["markers"]
            geology = markers["geology"]
            self.assertEqual("hydra", markers["boss"]["kind"])
            self.assertEqual(50, variant["bossSpawner"]["activationRadius"])
            self.assertNotIn("progressAll", variant["bossSpawner"])
            self.assertEqual(64, len(geology["oreStalactites"]))
            self.assertEqual(64, len(geology["stoneStalactites"]))
            self.assertEqual(8, len(geology["stalagmites"]))

    def test_compiled_route_structures_have_no_marker_blocks(self):
        forbidden = (
            b"minecraft:structure_block",
            b"minecraft:jigsaw",
            b"tf_slice:marker",
        )
        for folder in ("labyrinth", "hydra_lair"):
            payload = b"".join(
                path.read_bytes()
                for path in sorted((ROUTE_ROOT / folder).rglob("*.mcstructure"))
            )
            for value in forbidden:
                self.assertNotIn(value, payload)

    def test_route_structure_payload_stays_under_budget(self):
        folders = (
            ROUTE_ROOT / "labyrinth",
            ROUTE_ROOT / "hydra_lair",
            ROUTE_ROOT / "surface_native" / "labyrinth",
            ROUTE_ROOT / "surface_native" / "hydra_lair",
        )
        total = sum(
            path.stat().st_size
            for folder in folders
            for path in folder.rglob("*.mcstructure")
        )
        self.assertLessEqual(total, 150 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
