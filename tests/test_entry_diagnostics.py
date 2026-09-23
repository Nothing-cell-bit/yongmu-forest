import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
    / "entry_diagnostics.py"
)
SERVER_PATH = (
    ROOT
    / "TwilightBossSliceB"
    / "TwilightBossSlice"
    / "serverSystem.py"
)


def load_diagnostics_module():
    if not MODULE_PATH.is_file():
        raise AssertionError("missing entry diagnostics module: %s" % MODULE_PATH)
    spec = importlib.util.spec_from_file_location(
        "twilight_entry_diagnostics_under_test",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EntryDiagnosticsTests(unittest.TestCase):
    def test_writer_is_disabled_and_never_creates_a_log(self):
        diagnostics = load_diagnostics_module()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "entry.log"
            writer = diagnostics.EntryDiagnostics(
                path=str(path), version="test", session="test",
                activate=True, worldgen_enabled=True,
            )
            self.assertFalse(writer.worldgen_enabled)
            self.assertIsNone(writer.path)
            self.assertIs(writer, writer.activate())
            self.assertFalse(writer.write("entry", position=(1, 2, 3)))
            self.assertFalse(diagnostics.write_worldgen_event("worldgen"))
            self.assertFalse(writer.deactivate())
            self.assertIsNone(diagnostics.get_active_diagnostics())
            self.assertFalse(path.exists())

    def test_old_environment_switch_does_not_restore_file_diagnostics(self):
        diagnostics = load_diagnostics_module()
        with mock.patch.dict(os.environ, {"TWILIGHT_WORLDGEN_TRACE": "1"}):
            writer = diagnostics.EntryDiagnostics(activate=True)
            self.assertFalse(writer.worldgen_enabled)
            self.assertFalse(writer.write("entry"))
            self.assertFalse(diagnostics.write_worldgen_event("worldgen"))
            self.assertIsNone(diagnostics.default_trace_path("C:/Users/test"))

    def test_server_instruments_every_native_entry_boundary(self):
        server = SERVER_PATH.read_text(encoding="utf-8")
        required_events = (
            "system.init",
            "chat.received",
            "enter.begin",
            "enter.dimension.call",
            "enter.dimension.result",
            "enter.position.call",
            "enter.position.result",
            "enter.queued",
            "entry.bootstrap.begin",
            "dimension.component.create.call",
            "dimension.component.create.return",
            "dimension.native_change.call",
            "dimension.native_change.return",
            "dimension.change.return",
            "structure_feature.bypassed",
            "dimension.event.start",
            "dimension.event.finish",
            "portal.inside.begin",
            "portal.dimension.call",
            "portal.dimension.result",
            "portal.surface.call",
            "portal.surface.result",
            "portal.exit.call",
            "portal.exit.result",
        )
        for event in required_events:
            self.assertIn('"%s"' % event, server, event)

    def test_server_does_not_call_rejected_native_tip_api(self):
        server = SERVER_PATH.read_text(encoding="utf-8")
        notify = server[server.index("    def _notify(") :]
        notify = notify[: notify.index("    def _notify_lines(")]

        self.assertNotIn(".SetNotifyMsg(", notify)
        self.assertIn('"notify.native_tip_skipped"', notify)


if __name__ == "__main__":
    unittest.main()
