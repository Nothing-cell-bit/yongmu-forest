"""Review-neutral presentation must survive the real resource build paths."""

import ast
import colorsys
import hashlib
import json
import random
import shutil
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
sys.path.insert(0, str(ROOT / "tools"))

VANILLA = {
    "ghast_tear.png": "6f13587b4de52bb1d27d2b7e52ee0787984e30af86fb301615006395b934db06",
}
UPSTREAM = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted/00_original_tree/assets/twilightforest/textures/model"
SKINS = {"ur_ghast": "towerboss.png", "ur_ghast_open": "towerboss_openeyes.png", "ur_ghast_attack": "towerboss_fire.png"}


def assert_yellow_only(case, source, target):
    original = Image.open(source).convert("RGBA")
    edited = Image.open(target).convert("RGBA")
    case.assertEqual((64, 32), edited.size)
    changed = 0
    for y in range(original.height):
        for x in range(original.width):
            old, new = original.getpixel((x, y)), edited.getpixel((x, y))
            red, green, blue, alpha = old
            if alpha and red > green and red > blue:
                changed += 1
                old_hls = colorsys.rgb_to_hls(*(channel / 255.0 for channel in old[:3]))
                new_hls = colorsys.rgb_to_hls(*(channel / 255.0 for channel in new[:3]))
                case.assertAlmostEqual(1.0 / 6.0, new_hls[0])
                case.assertAlmostEqual(old_hls[1], new_hls[1])
                case.assertAlmostEqual(old_hls[2], new_hls[2])
                case.assertEqual(alpha, new[3])
            else:
                case.assertEqual(old, new)
    case.assertGreater(changed, 100)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UrGhastReviewPresentationTests(unittest.TestCase):
    def test_all_boss_branches_and_placed_trophy_keep_original_pixels_except_red_hue(self):
        client = json.loads((RP / "entity/ur_ghast.entity.json").read_text(encoding="utf-8"))
        bindings = client["minecraft:client_entity"]["description"]["textures"]
        for branch, stem in (("default", "ur_ghast"), ("open", "ur_ghast_open"), ("attack", "ur_ghast_attack")):
            with self.subTest(branch=branch):
                assert_yellow_only(self, UPSTREAM / SKINS[stem], RP / (bindings[branch] + ".png"))
        trophy = json.loads((RP / "entity/ur_ghast_trophy_visual.entity.json").read_text(encoding="utf-8"))
        texture = trophy["minecraft:client_entity"]["description"]["textures"]["default"]
        assert_yellow_only(self, UPSTREAM / "towerboss.png", RP / (texture + ".png"))

    def test_model_texture_copy_entry_does_not_restore_bloody_upstream_skin(self):
        import build_phantom_urghast_models as models
        with tempfile.TemporaryDirectory() as directory, patch.object(models, "RP", Path(directory)):
            models.copy_textures()
            for stem, source in SKINS.items():
                assert_yellow_only(self, UPSTREAM / source, Path(directory) / "textures/entity/tf_slice" / (stem + ".png"))

    def test_falling_tears_and_drop_icon_use_the_same_vanilla_tear(self):
        import build_ur_ghast_effect_assets as effects
        document = json.loads((RP / "particles/ur_ghast_tear.json").read_text(encoding="utf-8"))
        self.assertEqual(effects.documents()["ur_ghast_tear.json"], document)
        texture = document["particle_effect"]["description"]["basic_render_parameters"]["texture"]
        self.assertEqual("textures/items/ghast_tear", texture)
        self.assertEqual(VANILLA["ghast_tear.png"], digest(RP / (texture + ".png")))
        self.assertEqual(VANILLA["ghast_tear.png"], digest(RP / "textures/items/fiery_tears.png"))

    def test_trophy_build_entry_keeps_yellow_skin_in_isolated_output(self):
        import build_public_block_shapes as shapes
        geometry = shapes.trophy_geometry_document()["minecraft:geometry"]
        by_identifier = {entry["description"]["identifier"]: entry for entry in geometry}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            # Stage the actual model inputs because trophy_document reads the
            # floor-rotation family again. Keep production logic unmodified.
            shutil.copytree(RP / "models", output / "R/models")
            with patch.object(shapes, "RP", output / "R"), patch.object(shapes, "BP", output / "B"), patch.object(shapes, "TROPHY_SPECS", {"ur_ghast": shapes.TROPHY_SPECS["ur_ghast"]}):
                shapes.build_trophies({}, {}, {}, by_identifier)
            assert_yellow_only(self, UPSTREAM / "towerboss.png", output / "R/textures/entity/tf_slice/trophies/ur_ghast.png")

    def test_death_effect_real_client_entry_emits_neutral_particles(self):
        source = (ROOT / "TwilightBossSliceB/TwilightBossSlice/clientSystem.py").read_text(encoding="utf-8")
        source = source[source.index("    def OnUrGhastEffect("):]
        method = ast.parse(textwrap.dedent(source[:source.index("\n    def ", 1)])).body[0]
        namespace = {"random": random, "CF": types.SimpleNamespace(CreateGame=lambda unused: types.SimpleNamespace(GetCurrentDimension=lambda: 0)), "LEVEL_ID": "level"}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "clientSystem.py", "exec"), namespace)
        for kind, count in (("death_burst", 12), ("death_trail", 40)):
            emissions = []
            client = types.SimpleNamespace(_spawn_naga_state_particle=lambda particle, pos: emissions.append((particle, pos)))
            namespace["OnUrGhastEffect"](client, {"dimensionId": 0, "kind": kind, "positions": [(0, 20, 0)]})
            self.assertEqual(count, len(emissions))
            self.assertLessEqual({particle for particle, unused in emissions}, {"minecraft:large_explosion", "minecraft:basic_smoke_particle"})


if __name__ == "__main__":
    unittest.main()
