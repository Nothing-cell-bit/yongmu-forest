# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BEHAVIOR_ROOT = ROOT / "TwilightBossSliceB"
UI_PATH = BEHAVIOR_ROOT / "TwilightBossSlice" / "magicMapUI.py"


class FakeControl(object):
    def __init__(self):
        self.visible = False
        self.alpha = 0.0

    def SetVisible(self, visible):
        self.visible = bool(visible)

    def SetAlpha(self, alpha):
        self.alpha = float(alpha)


class FakeViewBinder(object):
    BF_BindString = 1

    @staticmethod
    def binding(_flag, _binding_name=None):
        def decorate(function):
            return function

        return decorate


def load_ui_module():
    client_package = types.ModuleType("client")
    client_api = types.ModuleType("client.extraClientApi")
    client_api.GetScreenNodeCls = lambda: object
    client_api.GetEngineCompFactory = lambda: object()
    client_api.GetViewBinderCls = lambda: FakeViewBinder
    client_package.extraClientApi = client_api
    sys.modules["client"] = client_package
    sys.modules["client.extraClientApi"] = client_api
    sys.path.insert(0, str(BEHAVIOR_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "magic_map_ui_renderer_under_test",
            str(UI_PATH),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class MagicMapFullScreenRendererTests(unittest.TestCase):
    def test_full_screen_retires_old_bitmap_after_new_texture_settles(self):
        ui = load_ui_module()
        renderer = object.__new__(ui.MagicMapUI)
        renderer._snapshot = {"mapId": 11, "gridSize": 128}
        renderer._cells = {0: "forest", 16383: "stream"}
        renderer._biome_bitmap_controls = {
            "a": FakeControl(),
            "b": FakeControl(),
            "c": FakeControl(),
        }
        renderer._bitmap_paths = {
            "a": "C:/cache/old.png",
            "b": "",
            "c": "",
        }
        renderer._bitmap_latest_slot = "a"
        renderer._bitmap_next_slot_index = 1
        renderer._bitmap_pending_slot = None
        renderer._bitmap_retention_ticks = 0
        renderer._biome_bitmap_controls["a"].visible = True
        renderer._biome_bitmap_controls["a"].alpha = 1.0
        renderer._bitmap_dirty = True
        ui.magic_map_bitmap_cache.render_magic_map_bitmap = (
            lambda _map_id, _cells: "C:/cache/new.png"
        )

        renderer._render_biome_bitmap()

        self.assertEqual("b", renderer._bitmap_pending_slot)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["b"].alpha)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["c"].alpha)
        self.assertEqual("C:/cache/old.png", renderer.GetBitmapPath("a"))
        self.assertEqual("C:/cache/new.png", renderer.GetBitmapPath("b"))
        for _index in range(ui.BITMAP_RETENTION_TICKS):
            renderer._advance_bitmap_retention()

        self.assertEqual("b", renderer._bitmap_latest_slot)
        self.assertIsNone(renderer._bitmap_pending_slot)
        self.assertFalse(renderer._biome_bitmap_controls["a"].visible)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertTrue(renderer._biome_bitmap_controls["b"].visible)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["b"].alpha)
        self.assertEqual(renderer.GetBitmapPath("a"), renderer.GetBitmapPathA())
        self.assertEqual(renderer.GetBitmapPath("b"), renderer.GetBitmapPathB())
        self.assertEqual(renderer.GetBitmapPath("c"), renderer.GetBitmapPathC())

    def test_server_delta_cannot_rewind_locally_sampled_player_position(self):
        ui = load_ui_module()
        renderer = object.__new__(ui.MagicMapUI)
        renderer._snapshot = {
            "mapId": 11,
            "gridSize": 128,
            "player": [320, 640],
            "players": [],
        }
        renderer._cells = {}
        renderer._canvas = None
        renderer._player_control = None
        renderer._local_player_position_ready = True

        renderer.ApplyDelta(
            {
                "mapId": 11,
                "player": [288, 608],
                "biomeRuns": [],
            }
        )

        self.assertEqual([320, 640], renderer._snapshot["player"])

    def test_full_screen_marks_successful_client_position_as_authoritative(self):
        ui = load_ui_module()
        renderer = object.__new__(ui.MagicMapUI)
        renderer._snapshot = {"player": [0, 0]}
        renderer._cells = {}
        renderer._player_control = None
        renderer._live_tick = 2
        renderer._bitmap_pending_slot = None
        renderer._bitmap_dirty = False

        class Position(object):
            def GetFootPos(self):
                return (12.75, 64.0, 56.25)

        class Rotation(object):
            def GetRot(self):
                return (0.0, 90.0)

        class Factory(object):
            def CreatePos(self, _player_id):
                return Position()

            def CreateRot(self, _player_id):
                return Rotation()

        ui.clientApi.GetLocalPlayerId = lambda: "local"
        ui.CF = Factory()

        renderer.Update()

        self.assertTrue(renderer._local_player_position_ready)
        self.assertEqual([12, 56], renderer._snapshot["player"])


if __name__ == "__main__":
    unittest.main()
