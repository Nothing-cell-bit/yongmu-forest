"""Exercise the actual client handler without importing the game SDK."""

import ast
import json
import textwrap
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest import TestCase, mock

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def server_method(name):
    path = ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py"
    source = path.read_text("utf-8")
    source = source[source.index("    def " + name + "("):]
    source = source[:source.index("\n    def ", 1)]
    namespace = {
        "UR_GHAST_TROPHY_BLOCKS": {
            "tf_slice:ur_ghast_trophy", "tf_slice:ur_ghast_wall_trophy"
        }
    }
    exec(textwrap.dedent(source), namespace)
    return namespace[name]


class TrophyBreakEffectTests(TestCase):
    def setUp(self):
        source = ROOT / "TwilightBossSliceB/TwilightBossSlice/clientSystem.py"
        text = source.read_text(encoding="utf-8-sig")
        text = text[text.index("    def OnTrophyBreakEffect") :]
        text = text[:text.index("\n    def ", 1)]
        tree = ast.parse(textwrap.dedent(text))
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "OnTrophyBreakEffect")
        self.factory = mock.Mock()
        self.factory.CreateGame.return_value.GetCurrentDimension.return_value = 7
        namespace = {"CF": self.factory, "LEVEL_ID": "level"}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
        self.handler = namespace[method.name]
        self.client = SimpleNamespace(_spawn_naga_state_particle=mock.Mock())
        self.event = {"x": 2, "y": 64, "z": -5, "dimensionId": 7}

    def test_break_emits_one_textured_burst_without_manual_emission(self):
        self.handler(self.client, self.event)
        self.client._spawn_naga_state_particle.assert_called_once_with(
            "tf_slice:ur_ghast_trophy_break", (2.5, 64.65, -4.5)
        )

    def test_floor_and_wall_removal_deliver_a_break_burst_without_cached_visual(self):
        server = SimpleNamespace(
            _ur_ghast_trophy_visuals={},
            _remove_ur_ghast_trophy_visuals=mock.Mock(),
            _play_world_sound=mock.Mock(),
        )
        def deliver(event_name, payload):
            self.assertEqual("TrophyBreakEffect", event_name)
            self.handler(self.client, payload)
        server.BroadcastToAllClient = deliver
        server._broadcast_trophy_break_effect = MethodType(
            server_method("_broadcast_trophy_break_effect"), server
        )
        remove = server_method("OnBlockRemoveServerEvent")
        for name in ("ur_ghast_trophy", "ur_ghast_wall_trophy"):
            with self.subTest(block=name):
                path = ROOT / "TwilightBossSliceB/netease_blocks" / (name + ".json")
                block = json.loads(path.read_text("utf-8"))["minecraft:block"]
                self.client._spawn_naga_state_particle.reset_mock()
                server._remove_ur_ghast_trophy_visuals.reset_mock()
                # NetEase only dispatches removal for opted-in block types.
                if block["components"].get("netease:listen_block_remove", {}).get("value", False):
                    remove(server, {
                        "fullName": block["description"]["identifier"],
                        "x": 2, "y": 64, "z": -5, "dimension": 7,
                    })
                self.client._spawn_naga_state_particle.assert_called_once_with(
                    "tf_slice:ur_ghast_trophy_break", (2.5, 64.65, -4.5)
                )
                server._remove_ur_ghast_trophy_visuals.assert_called_once_with((2, 64, -5), 7)

    def test_other_dimension_does_not_show_break_particles(self):
        self.event["dimensionId"] = 0
        self.handler(self.client, self.event)
        self.client._spawn_naga_state_particle.assert_not_called()

    def test_malformed_event_does_not_emit_at_world_origin(self):
        for event in ({}, {"x": "bad", "y": 0, "z": 0, "dimensionId": 7}):
            self.handler(self.client, event)
        self.client._spawn_naga_state_particle.assert_not_called()

    def test_break_particle_uses_opaque_model_texels_and_gravity(self):
        path = ROOT / "TwilightBossSliceR/particles/ur_ghast_trophy_break.json"
        self.assertTrue(path.exists(), "missing trophy debris effect")
        effect = json.loads(path.read_text("utf-8"))["particle_effect"]
        self.assertEqual("textures/entity/tf_slice/trophies/ur_ghast",
                         effect["description"]["basic_render_parameters"]["texture"])
        components = effect["components"]
        self.assertGreaterEqual(components["minecraft:emitter_rate_instant"]["num_particles"], 24)
        self.assertNotIn("minecraft:emitter_rate_manual", components)
        self.assertLess(components["minecraft:particle_motion_dynamic"]["linear_acceleration"][1], 0)
        texture = Image.open(ROOT / "TwilightBossSliceR/textures/entity/tf_slice/trophies/ur_ghast.png").convert("RGBA")
        self.assertEqual((64, 32), texture.size)
        # Every 2x2 UV selection lies within the opaque 16x16 body face.
        self.assertEqual((255, 255), texture.getchannel("A").crop((16, 16, 32, 32)).getextrema())
