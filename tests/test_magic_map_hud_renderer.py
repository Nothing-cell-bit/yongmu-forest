# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BEHAVIOR_ROOT = ROOT / "TwilightBossSliceB"
HUD_PATH = BEHAVIOR_ROOT / "TwilightBossSlice" / "magicMapHudUI.py"


class FakeControl(object):
    def __init__(self):
        self.visible = False
        self.alpha = 0.0

    def SetVisible(self, visible):
        self.visible = bool(visible)

    def SetAlpha(self, alpha):
        self.alpha = float(alpha)


class FakeHost(object):
    pass


class FakeViewBinder(object):
    BF_BindString = 1

    @staticmethod
    def binding(_flag, _binding_name=None):
        def decorate(function):
            return function

        return decorate


def load_hud_module():
    client_package = types.ModuleType("client")
    client_api = types.ModuleType("client.extraClientApi")
    client_api.GetScreenNodeCls = lambda: object
    client_api.GetUIScreenProxyCls = lambda: object
    client_api.GetEngineCompFactory = lambda: object()
    client_api.GetViewBinderCls = lambda: FakeViewBinder
    client_package.extraClientApi = client_api
    sys.modules["client"] = client_package
    sys.modules["client.extraClientApi"] = client_api
    sys.path.insert(0, str(BEHAVIOR_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "magic_map_hud_renderer_under_test",
            str(HUD_PATH),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def advance_retention(renderer, ticks):
    for _index in range(ticks):
        renderer._advance_bitmap_retention()


class MagicMapHudRendererTests(unittest.TestCase):
    def test_bitmap_ring_retires_old_layers_after_new_texture_settles(self):
        hud = load_hud_module()
        renderer = hud.MagicMapHudRenderer(FakeHost(), ())
        renderer._snapshot = {"mapId": 7, "gridSize": 128}
        renderer._cells = {0: "forest"}
        renderer._biome_bitmap_controls = {
            "a": FakeControl(),
            "b": FakeControl(),
            "c": FakeControl(),
        }
        rendered = []

        def render_bitmap(map_id, cells):
            path = "C:/cache/map_%d.png" % (len(rendered) + 1)
            rendered.append((map_id, dict(cells), path))
            return path

        hud.magic_map_bitmap_cache.render_magic_map_bitmap = render_bitmap
        renderer._bitmap_dirty = True

        renderer._render_biome_bitmap()

        self.assertEqual("a", renderer._bitmap_pending_slot)
        self.assertEqual("a", renderer._bitmap_latest_slot)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertTrue(renderer._biome_bitmap_controls["a"].visible)
        self.assertEqual("C:/cache/map_1.png", renderer.GetBitmapPath("a"))
        advance_retention(renderer, hud.BITMAP_RETENTION_TICKS - 1)
        self.assertEqual("a", renderer._bitmap_pending_slot)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["a"].alpha)

        renderer._advance_bitmap_retention()

        self.assertIsNone(renderer._bitmap_pending_slot)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["b"].alpha)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["c"].alpha)

        renderer._cells[1] = "lake"
        renderer._bitmap_dirty = True
        renderer._render_biome_bitmap()
        self.assertEqual("b", renderer._bitmap_pending_slot)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["b"].alpha)
        renderer._bitmap_dirty = True
        renderer._render_biome_bitmap()
        self.assertEqual(2, len(rendered))

        advance_retention(renderer, hud.BITMAP_RETENTION_TICKS)
        self.assertFalse(renderer._biome_bitmap_controls["a"].visible)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertTrue(renderer._biome_bitmap_controls["b"].visible)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["b"].alpha)
        renderer._cells[2] = "stream"
        renderer._bitmap_dirty = True
        renderer._render_biome_bitmap()

        self.assertEqual("c", renderer._bitmap_pending_slot)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["b"].alpha)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["c"].alpha)

        advance_retention(renderer, hud.BITMAP_RETENTION_TICKS)
        self.assertFalse(renderer._biome_bitmap_controls["b"].visible)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["b"].alpha)
        self.assertTrue(renderer._biome_bitmap_controls["c"].visible)
        renderer._cells[3] = "forest"
        renderer._bitmap_dirty = True
        renderer._render_biome_bitmap()

        self.assertEqual("a", renderer._bitmap_pending_slot)
        self.assertEqual("C:/cache/map_4.png", renderer.GetBitmapPath("a"))
        self.assertEqual(1.0, renderer._biome_bitmap_controls["a"].alpha)
        self.assertEqual(0.0, renderer._biome_bitmap_controls["b"].alpha)
        self.assertEqual(1.0, renderer._biome_bitmap_controls["c"].alpha)

        proxy = object.__new__(hud.MagicMapHudProxy)
        proxy._renderer = renderer
        fallback = object.__new__(hud.MagicMapHudUI)
        fallback._renderer = renderer
        self.assertEqual(renderer.GetBitmapPath("a"), proxy.GetBitmapPathA())
        self.assertEqual(renderer.GetBitmapPath("b"), proxy.GetBitmapPathB())
        self.assertEqual(renderer.GetBitmapPath("c"), proxy.GetBitmapPathC())
        self.assertEqual(renderer.GetBitmapPath("a"), fallback.GetBitmapPathA())
        self.assertEqual(renderer.GetBitmapPath("b"), fallback.GetBitmapPathB())
        self.assertEqual(renderer.GetBitmapPath("c"), fallback.GetBitmapPathC())

    def test_empty_exact_cells_hide_both_bitmap_buffers(self):
        hud = load_hud_module()
        renderer = hud.MagicMapHudRenderer(FakeHost(), ())
        renderer._snapshot = {"mapId": 7, "gridSize": 128}
        renderer._cells = {}
        renderer._biome_bitmap_controls = {
            "a": FakeControl(),
            "b": FakeControl(),
            "c": FakeControl(),
        }
        for control in renderer._biome_bitmap_controls.values():
            control.visible = True
            control.alpha = 1.0
        renderer._bitmap_dirty = True

        renderer._render_biome_bitmap()

        self.assertTrue(
            all(
                not control.visible and control.alpha == 0.0
                for control in renderer._biome_bitmap_controls.values()
            )
        )
        self.assertFalse(renderer._bitmap_dirty)

    def test_active_delta_updates_cells_without_rebuilding_pending_snapshot(self):
        hud = load_hud_module()
        renderer = hud.MagicMapHudRenderer(FakeHost(), ())
        renderer._snapshot = {
            "mapId": 7,
            "gridSize": 128,
            "biomeRuns": [],
        }
        hud._ACTIVE_UI = renderer

        def fail_full_merge(_snapshot, _delta):
            raise AssertionError("active HUD delta rebuilt the full snapshot")

        hud.magic_map_logic.merge_map_delta = fail_full_merge
        hud.apply_delta(
            {
                "mapId": 7,
                "gridSize": 128,
                "biomeCells": [[0, "forest"]],
            }
        )

        self.assertEqual("forest", renderer._cells[0])
        self.assertTrue(renderer._bitmap_dirty)

    def test_server_delta_cannot_rewind_locally_sampled_player_position(self):
        hud = load_hud_module()
        renderer = hud.MagicMapHudRenderer(FakeHost(), ())
        renderer._snapshot = {
            "mapId": 7,
            "gridSize": 128,
            "player": [320, 640],
        }
        renderer._local_player_position_ready = True

        renderer.ApplyDelta(
            {
                "mapId": 7,
                "player": [288, 608],
                "biomeCells": [],
            }
        )

        self.assertEqual([320, 640], renderer._snapshot["player"])

    def test_server_delta_remains_initial_position_fallback(self):
        hud = load_hud_module()
        renderer = hud.MagicMapHudRenderer(FakeHost(), ())
        renderer._snapshot = {
            "mapId": 7,
            "gridSize": 128,
            "player": [0, 0],
        }
        renderer._local_player_position_ready = False

        renderer.ApplyDelta(
            {
                "mapId": 7,
                "player": [32, 64],
                "biomeCells": [],
            }
        )

        self.assertEqual([32, 64], renderer._snapshot["player"])

    def test_hidden_hud_does_not_advance_or_render_bitmap(self):
        hud = load_hud_module()
        renderer = hud.MagicMapHudRenderer(FakeHost(), ())
        renderer._root = object()
        renderer._canvas = object()
        renderer._root_visible = False
        renderer._tick = hud.BITMAP_RENDER_INTERVAL_TICKS - 1
        renderer._bitmap_dirty = True
        renderer._bitmap_pending_slot = None
        rendered = []
        renderer._render_biome_bitmap = lambda: rendered.append(True)

        renderer.Update()

        self.assertEqual([], rendered)

    def test_visible_hud_marks_successful_client_position_as_authoritative(self):
        hud = load_hud_module()
        renderer = hud.MagicMapHudRenderer(FakeHost(), ())
        renderer._root = object()
        renderer._canvas = object()
        renderer._root_visible = True
        renderer._tick = 2

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

        hud.clientApi.GetLocalPlayerId = lambda: "local"
        hud.CF = Factory()

        renderer.Update()

        self.assertTrue(renderer._local_player_position_ready)
        self.assertEqual([12, 56], renderer._snapshot["player"])


if __name__ == "__main__":
    unittest.main()
