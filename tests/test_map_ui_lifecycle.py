"""Map UI teardown must tolerate native controls that are already gone."""
import unittest
from unittest import mock

from tests.test_magic_map_hud_renderer import FakeHost, load_hud_module
from tests.test_magic_map_ui_renderer import load_ui_module


class DeadControl:
    def SetVisible(self, value):
        raise AssertionError("native control was already destroyed")

    def SetAlpha(self, value):
        raise AssertionError("native control was already destroyed")


class MapUiLifecycleTests(unittest.TestCase):
    def hud(self):
        module = load_hud_module()
        renderer = module.MagicMapHudRenderer(FakeHost(), ("/held_map_root",))
        renderer._snapshot = {"mapId": 7, "gridSize": 128}
        renderer._cells = {0: "forest"}
        module._ACTIVE_UI = renderer
        return module, renderer

    def screen(self):
        module = load_ui_module()
        renderer = object.__new__(module.MagicMapUI)
        renderer._snapshot = {"mapId": 7}
        renderer._live_tick = 0
        renderer._canvas = DeadControl()
        renderer._cells = {0: "forest"}
        renderer._biome_bitmap_controls = dict.fromkeys(("a", "b", "c"))
        module._ACTIVE_UI = renderer
        return module, renderer

    def test_hud_destroy_never_calls_dead_native_controls(self):
        module, renderer = self.hud()
        renderer._biome_bitmap_controls["a"] = DeadControl()
        renderer._player_control = DeadControl()
        renderer._landmark_pool = [DeadControl()]
        renderer._landmark_count = 1
        renderer.Destroy()
        self.assertIsNone(module._ACTIVE_UI)
        self.assertEqual(7, module._PENDING_SNAPSHOT["mapId"])
        self.assertTrue(module._PENDING_SNAPSHOT["biomeRuns"])
        self.assertIsNone(renderer._player_control)
        self.assertEqual([], renderer._landmark_pool)

    def test_screen_destroy_never_calls_dead_native_controls(self):
        module, renderer = self.screen()
        renderer._biome_bitmap_controls["a"] = DeadControl()
        renderer.Destroy()
        self.assertIsNone(module._ACTIVE_UI)
        self.assertIsNone(renderer._canvas)
        self.assertEqual("", renderer.GetBitmapPathA())

    def test_destroyed_hud_ignores_late_callbacks_and_cannot_rebind(self):
        module, renderer = self.hud()
        renderer.Destroy()
        snapshot = dict(module._PENDING_SNAPSHOT)
        with mock.patch.object(renderer, "_bind_controls", side_effect=AssertionError("rebind")):
            for _ in range(40):
                renderer.Update()
            renderer.Init()
            renderer.SetHeldVisible(True)
            renderer.ApplySnapshot({"mapId": 8})
            renderer.ApplyDelta({"mapId": 7, "biomeCells": [[1, "stream"]]})
        renderer.Destroy()
        self.assertIsNone(module._ACTIVE_UI)
        self.assertEqual(snapshot, module._PENDING_SNAPSHOT)
        self.assertFalse(renderer._bitmap_dirty)

    def test_late_hud_destroy_does_not_overwrite_replacement_snapshot(self):
        module, renderer = self.hud()
        replacement = object()
        module._ACTIVE_UI = replacement
        module._PENDING_SNAPSHOT = {"mapId": 99}
        renderer.Destroy()
        self.assertIs(replacement, module._ACTIVE_UI)
        self.assertEqual({"mapId": 99}, module._PENDING_SNAPSHOT)

    def test_destroyed_screen_ignores_late_updates_and_deltas(self):
        module, renderer = self.screen()
        renderer.Destroy()
        with mock.patch.object(renderer, "_advance_bitmap_retention", side_effect=AssertionError("late render")):
            renderer.Update()
            renderer.ApplySnapshot({"mapId": 8})
            renderer.ApplyDelta({"mapId": 7, "biomeCells": [[1, "stream"]]})
        renderer.Destroy()
        self.assertIsNone(module._ACTIVE_UI)
        self.assertFalse(renderer._bitmap_dirty)


if __name__ == "__main__":
    unittest.main()
