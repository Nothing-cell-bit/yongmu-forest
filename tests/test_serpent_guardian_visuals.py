import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
TEXTURE_DIR = RP / "textures" / "entity"
GENERATOR = ROOT / "tools" / "generate_serpent_guardian_textures.py"
HEAD_GEOMETRY = RP / "models" / "entity" / "forest_wyrm.geo.json"
SEGMENT_GEOMETRY = RP / "models" / "entity" / "forest_wyrm_segment.geo.json"

TEXTURES = (
    "nagahead.png",
    "nagahead_charging.png",
    "nagahead_dazed.png",
    "nagahead_dazed_full.png",
    "nagasegment.png",
)
UPSTREAM_HASHES = {
    "EBB7FC828670EC90E53DA56D9CED872BC120391F171A1E74217A7D77BB15DD5A",
    "A461E4235001B8CEF4B0D5ABA54D4F5D0BD27CF37EA0BF8A8A5EA8DD94187481",
    "04CF31782C830144216BBCF7BF69340550E4256716E113BE5FED9C75088FED75",
    "25BA1909182FC01787621ED14891CB1B7167BACCF8BD52C281DB4B5B4528A8CA",
    "0903329270516D884F6A771550596D2956F974FB88D3AF21125442EA9F452865",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        if source.read(8) != b"\x89PNG\r\n\x1a\n":
            raise AssertionError("not a PNG: %s" % path)
        source.read(4)
        if source.read(4) != b"IHDR":
            raise AssertionError("missing IHDR: %s" % path)
        return struct.unpack(">II", source.read(8))


class SerpentGuardianVisualTests(unittest.TestCase):
    def test_original_texture_generator_rebuilds_packaged_assets(self):
        self.assertTrue(GENERATOR.is_file())
        with tempfile.TemporaryDirectory(prefix="serpent_guardian_textures_") as output:
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--output-dir", output],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for filename in TEXTURES:
                generated = Path(output) / filename
                packaged = TEXTURE_DIR / filename
                self.assertTrue(generated.is_file(), filename)
                self.assertEqual(generated.read_bytes(), packaged.read_bytes(), filename)

    def test_all_character_textures_are_original_128_pixel_atlases(self):
        hashes = set()
        for filename in TEXTURES:
            path = TEXTURE_DIR / filename
            self.assertEqual((128, 128), png_dimensions(path), filename)
            digest = sha256(path)
            self.assertNotIn(digest, UPSTREAM_HASHES, filename)
            hashes.add(digest)
        self.assertEqual(len(TEXTURES), len(hashes))

    def test_head_is_a_composite_masked_guardian(self):
        geometries = json.loads(HEAD_GEOMETRY.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ]
        head = next(
            item
            for item in geometries
            if item["description"]["identifier"] == "geometry.tf_slice.forest_wyrm"
        )
        self.assertEqual(128, head["description"]["texture_width"])
        self.assertEqual(128, head["description"]["texture_height"])
        bones = {bone["name"]: bone for bone in head["bones"]}
        for name in (
            "head",
            "mask",
            "eye_left",
            "eye_right",
            "horn_left",
            "horn_right",
            "fin_left",
            "fin_right",
        ):
            self.assertIn(name, bones)
        cubes = [cube for bone in bones.values() for cube in bone.get("cubes", ())]
        self.assertGreaterEqual(len(cubes), 12)
        self.assertFalse(any(cube.get("size") == [16.08, 16.08, 16.08] for cube in cubes))

    def test_dazed_overlay_contains_only_two_eyelids(self):
        geometries = json.loads(HEAD_GEOMETRY.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ]
        eyelids = next(
            item
            for item in geometries
            if item["description"]["identifier"]
            == "geometry.tf_slice.forest_wyrm_eyelids"
        )
        cubes = [cube for bone in eyelids["bones"] for cube in bone.get("cubes", ())]
        self.assertEqual(2, len(cubes))
        self.assertTrue(all(0.0 < float(cube["inflate"]) <= 0.05 for cube in cubes))

    def test_segment_uses_core_and_four_part_copper_ring(self):
        geometry = json.loads(SEGMENT_GEOMETRY.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ][0]
        self.assertEqual(128, geometry["description"]["texture_width"])
        bones = {bone["name"]: bone for bone in geometry["bones"]}
        self.assertIn("segment", bones)
        self.assertIn("segment_ring", bones)
        cubes = [cube for bone in bones.values() for cube in bone.get("cubes", ())]
        self.assertGreaterEqual(len(cubes), 5)
        self.assertTrue(all(isinstance(cube['uv'], dict) for cube in cubes))
        self.assertLessEqual(max(cube['size'][0] for cube in cubes), 16)

    def test_player_visible_name_and_spawn_egg_use_the_new_identity(self):
        zh = (RP / "texts" / "zh_CN.lang").read_text(encoding="utf-8")
        en = (RP / "texts" / "en_US.lang").read_text(encoding="utf-8")
        self.assertIn("entity.tf_slice:forest_wyrm.name=烬铜盘蛇", zh)
        self.assertIn("entity.tf_slice:forest_wyrm.name=Cindercoil Guardian", en)
        client = json.loads(
            (RP / "entity" / "forest_wyrm.entity.json").read_text(encoding="utf-8")
        )["minecraft:client_entity"]["description"]
        self.assertEqual("#17152C", client["spawn_egg"]["base_color"])
        self.assertEqual("#D6762D", client["spawn_egg"]["overlay_color"])


if __name__ == "__main__":
    unittest.main()
