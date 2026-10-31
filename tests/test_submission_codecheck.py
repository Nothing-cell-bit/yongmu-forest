"""Reported E1137 rejection, renamed variants, and exact archive repair."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import submission_codecheck as guard
import repair_submission_code18 as repair


OLD = '''class ServerSystem:
    def _process_portal_background_preloads(self):
        inflight = getattr(self, "_portal_background_preload_inflight", None)
        if inflight is not None:
            if not inflight.get("timedOut"):
                inflight["timedOut"] = True
    def next_method(self):
        pass
'''


class SubmissionCodecheckTests(unittest.TestCase):
    def test_rejects_reported_assignment_and_renamed_multiline_variant(self):
        for source in (OLD, OLD.replace("inflight", "pending").replace(
                '"_portal_background_preload_pending"', '"_portal_background_preload_inflight"')
                .replace('getattr(self,', 'getattr(\n            self,')):
            with self.subTest(source=source):
                issues = guard.check_rows([("behavior_pack/Test/server.py", source.encode())])
                self.assertEqual(1, len(issues))
                self.assertEqual("known-portal-state-E1137", issues[0]["symbol"])
                with self.assertRaises(ValueError):
                    guard.require_clean([("behavior_pack/Test/server.py", source.encode())])

    def test_repaired_method_passes_and_preserves_dictionary_identity(self):
        fixed = repair.repair_timeout(OLD.encode())
        self.assertEqual([], guard.check_rows([("behavior_pack/Test/server.py", fixed)]))
        namespace = {}
        exec(compile(fixed, "submission.py", "exec"), namespace)
        server = namespace["ServerSystem"]()
        item = {"key": (7, 1, 2), "done": False}
        server._portal_background_preload_inflight = item
        server._process_portal_background_preloads()
        self.assertIs(item, server._portal_background_preload_inflight)
        self.assertEqual({"key": (7, 1, 2), "done": False, "timedOut": True}, item)
        for state in (None, [], "stale"):
            server._portal_background_preload_inflight = state
            server._process_portal_background_preloads()

    def test_unrelated_dictionary_assignment_is_allowed(self):
        guard.require_clean([("behavior_pack/test.py", b'def f():\n    d = {}\n    d["key"] = True\n')])

    def test_source_runtime_has_no_reported_pattern(self):
        guard.check_source(ROOT / "TwilightBossSliceB")

    def test_repair_refuses_repeated_or_already_repaired_input(self):
        with self.assertRaises(ValueError):
            repair.repair_timeout(repair.repair_timeout(OLD.encode()))

    def test_real_repair_entry_preserves_all_other_members_and_old_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, new = root / "old.zip", root / "fixed.zip"
            members = {repair.SERVER: OLD.encode(),
                       "behavior_pack/manifest.json": b'{"header":{"version":[0,12,5]}}',
                       "resource_pack/manifest.json": b'{"header":{"version":[0,12,5]}}',
                       "resource_pack/textures/": b'',
                       "resource_pack/textures/preserved.png": b'asset-bytes'}
            with zipfile.ZipFile(old, "x") as z:
                for name, data in members.items():
                    z.writestr(name, data)
            before = old.read_bytes()
            digest = hashlib.sha256(before).hexdigest()
            with contextlib.redirect_stdout(io.StringIO()):
                repair.build(old, new, root / "evidence", digest)
            self.assertEqual(before, old.read_bytes())
            with zipfile.ZipFile(new) as z:
                self.assertEqual(set(members), set(z.namelist()))
                for name, data in members.items():
                    self.assertEqual(repair.repair_timeout(data) if name == repair.SERVER else data,
                                     z.read(name))
            report = json.loads((root / "evidence/repair-report.json").read_text())
            self.assertEqual([repair.SERVER], report["changed"])
            with self.assertRaises(ValueError):
                repair.build(old, new, root / "evidence", digest)
            with self.assertRaises(ValueError):
                repair.build(old, root / "bad.zip", root / "evidence", "wrong-hash")
            self.assertFalse((root / "bad.zip").exists())


if __name__ == "__main__":
    unittest.main()
