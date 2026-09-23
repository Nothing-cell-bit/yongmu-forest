# -*- coding: utf-8 -*-
import hashlib
import json
import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"

CAVE_PLANTS = {
    "root_strand": {
        "block": "tf_slice:root_strand",
        "origin_attempts": 4,
        "origin_y": 10,
        "scan_samples": 24,
        "scan_y": [-42, 0],
    },
    "torchberry_plant": {
        "block": "tf_slice:torchberry_plant",
        "origin_attempts": 8,
        "origin_y": 60,
        "scan_samples": 64,
        "scan_y": [-92, 0],
    },
    "hanging_roots": {
        "block": "minecraft:hanging_roots",
        "origin_attempts": 16,
        "origin_y": 0,
        "scan_samples": 32,
        "scan_y": [-32, 0],
    },
}
UPSTREAM_TEXTURE_HASHES = {
    "root_strand.png": "703bef92113767adcdf95ced21f6d8a9fa833322362d9472913a06bbc5241ea0",
    "torchberry_plant.png": "a113afa41cff6218d688e2afadb988bd93f921a03f000c69e2b797152360f0f9",
    "torchberry_plant_glow.png": "410a2fe9a20e449e1b81e07555b88b98fd514baaaa0a06c1916a74fbabdf0a05",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class CavePlantWorldgenContractTests(unittest.TestCase):
    def test_cave_plant_scans_keep_upstream_origin_counts_and_depths(self):
        for key, spec in CAVE_PLANTS.items():
            with self.subTest(plant=key):
                single_name = "cave_%s_single_feature" % key
                scan_name = "cave_%s_scan_feature" % key
                single = read_json(
                    BP / "netease_features" / (single_name + ".json")
                )["minecraft:single_block_feature"]
                scan = read_json(
                    BP / "netease_features" / (scan_name + ".json")
                )["minecraft:scatter_feature"]
                rule = read_json(
                    BP
                    / "netease_feature_rules"
                    / (scan_name + "_rule.json")
                )["minecraft:feature_rules"]

                self.assertEqual(spec["block"], single["places_block"][0]["block"])
                self.assertEqual(["minecraft:air"], single["may_replace"])
                ceiling_blocks = single["may_attach_to"]["top"]
                self.assertIn("minecraft:stone", ceiling_blocks)
                self.assertIn("minecraft:dirt", ceiling_blocks)
                self.assertIn("tf_slice:root_block", ceiling_blocks)
                self.assertEqual("tf_slice:" + single_name, scan["places_feature"])
                self.assertEqual(spec["scan_samples"], scan["distribution"]["iterations"])
                self.assertEqual(
                    {"distribution": "uniform", "extent": spec["scan_y"]},
                    scan["distribution"]["y"],
                )
                self.assertEqual(spec["origin_attempts"], rule["distribution"]["iterations"])
                self.assertEqual(spec["origin_y"], rule["distribution"]["y"])
                self.assertIn(
                    "tf_slice_has_underground_roots",
                    json.dumps(rule["conditions"]),
                )

    def test_custom_cave_plants_use_original_textures_and_mobile_safe_models(self):
        for filename, expected_hash in UPSTREAM_TEXTURE_HASHES.items():
            with self.subTest(texture=filename):
                path = RP / "textures" / "blocks" / filename
                self.assertTrue(path.is_file())
                self.assertEqual(
                    expected_hash,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )

        server_blocks = {
            read_json(path)["minecraft:block"]["description"]["identifier"]: read_json(path)["minecraft:block"]
            for path in (BP / "netease_blocks").glob("*.json")
        }
        client_blocks = read_json(RP / "blocks.json")
        atlas = read_json(RP / "textures" / "terrain_texture.json")["texture_data"]
        for block_id in (
            "tf_slice:root_strand",
            "tf_slice:torchberry_plant",
            "tf_slice:torchberry_plant_empty",
        ):
            self.assertIn(block_id, server_blocks)
            self.assertIn(block_id, client_blocks)
            components = server_blocks[block_id]["components"]
            self.assertFalse(components["minecraft:collision_box"])
            self.assertEqual("optionalAlpha", components["netease:render_layer"]["value"])

        self.assertGreaterEqual(
            server_blocks["tf_slice:torchberry_plant"]["components"]["minecraft:light_emission"],
            10,
        )
        for texture_id in (
            "tf_slice:root_strand",
            "tf_slice:torchberry_plant",
            "tf_slice:torchberry_plant_glow",
        ):
            self.assertIn(texture_id, atlas)

        geometry = read_json(RP / "models" / "blocks" / "cave_plants.geo.json")
        geometry_ids = {
            entry["description"]["identifier"]
            for entry in geometry["minecraft:geometry"]
        }
        self.assertEqual(
            {
                "geometry.tf_slice.root_strand",
                "geometry.tf_slice.torchberry_plant",
                "geometry.tf_slice.torchberry_plant_empty",
            },
            geometry_ids,
        )


class TorchberryHarvestContractTests(unittest.TestCase):
    def test_harvest_logic_replaces_the_plant_and_awards_the_existing_item(self):
        logic_path = BP / "TwilightBossSlice" / "cave_plant_logic.py"
        self.assertTrue(logic_path.is_file())
        logic = runpy.run_path(str(logic_path), run_name="cave_plant_contract")
        self.assertEqual(
            {
                "replacement": "tf_slice:torchberry_plant_empty",
                "item": {
                    "newItemName": "tf_slice:torchberries",
                    "newAuxValue": 0,
                    "count": 1,
                },
            },
            logic["torchberry_harvest"]("tf_slice:torchberry_plant"),
        )
        self.assertIsNone(
            logic["torchberry_harvest"]("tf_slice:torchberry_plant_empty")
        )

    def test_server_listens_for_custom_block_use_and_runs_harvest_transaction(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"ServerBlockUseEvent", self.OnServerBlockUseEvent', source)
        self.assertIn("def OnServerBlockUseEvent(self, args):", source)
        self.assertIn("cave_plant_logic.torchberry_harvest", source)
        self.assertIn("self._set_block(", source)
        self.assertIn("self._deliver_item(", source)


if __name__ == "__main__":
    unittest.main()
