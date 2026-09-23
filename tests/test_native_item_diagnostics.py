# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
    / "native_item_diagnostics.py"
)


def load_diagnostics():
    spec = importlib.util.spec_from_file_location(
        "native_item_diagnostics",
        str(MODULE_PATH),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeItemDiagnosticsTests(unittest.TestCase):
    def test_invalid_inputs_fail_closed_and_tokens_are_sanitized(self):
        diagnostics = load_diagnostics()
        self.assertFalse(diagnostics.should_trace(None))
        self.assertFalse(diagnostics.should_trace(0))
        self.assertFalse(diagnostics.should_trace(1))
        self.assertEqual(
            "fallback", diagnostics._safe_token(None, "fallback")
        )
        self.assertEqual(
            "fallback", diagnostics._safe_token("", "fallback")
        )

        class BadString(object):
            def __str__(self):
                raise RuntimeError("no string")

        self.assertEqual(
            "unprintable", diagnostics._safe_token(BadString())
        )

        line = diagnostics.end_line(
            "client",
            11,
            "offhand",
            122,
            "invalid",
            {"newItemName": "name with=separator"},
        )
        self.assertIn("item=name_with_separator", line)
        self.assertIn("elapsedMs=0", line)
        self.assertIn(
            "item=none",
            diagnostics.end_line(
                "client", 12, "offhand", 123, 0, {}
            ),
        )

    def test_detailed_window_and_sparse_tail_are_bounded(self):
        diagnostics = load_diagnostics()
        self.assertTrue(diagnostics.should_trace(1, enabled=True))
        self.assertTrue(diagnostics.should_trace(4096, enabled=True))
        self.assertFalse(diagnostics.should_trace(4097, enabled=True))
        self.assertTrue(diagnostics.should_trace(4200, enabled=True))

    def test_begin_line_identifies_the_native_call_without_player_data(self):
        diagnostics = load_diagnostics()
        line = diagnostics.begin_line("server", 7, "carried", 90)
        self.assertEqual(
            "[TF_NATIVE_ITEM_DIAG] phase=begin side=server seq=7 "
            "hand=carried tick=90",
            line,
        )
        self.assertNotIn("player", line.lower())

    def test_end_line_records_result_duration_and_error_class_only(self):
        diagnostics = load_diagnostics()
        success = diagnostics.end_line(
            "client",
            9,
            "offhand",
            120,
            12.9,
            {"itemName": "tf_slice:filled_magic_map"},
        )
        self.assertIn("phase=end side=client seq=9", success)
        self.assertIn("success=1", success)
        self.assertIn("item=tf_slice:filled_magic_map", success)
        self.assertIn("elapsedMs=12", success)
        self.assertIn("error=none", success)

        error = diagnostics.end_line(
            "server",
            10,
            "carried",
            121,
            3.0,
            None,
            ValueError("sensitive details"),
        )
        self.assertIn("success=0", error)
        self.assertIn("error=ValueError", error)
        self.assertNotIn("sensitive details", error)


if __name__ == "__main__":
    unittest.main()
