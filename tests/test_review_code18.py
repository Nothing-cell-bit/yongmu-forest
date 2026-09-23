"""Submission regressions: forbidden modules and disabled file diagnostics."""
import ast
import importlib.util
from functools import lru_cache
from lib2to3.refactor import RefactoringTool
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
PY2_READER = RefactoringTool(["lib2to3.fixes.fix_print", "lib2to3.fixes.fix_except"])


@lru_cache(maxsize=128)
def parse_script(path):
    source = path.read_text(encoding="utf-8")
    try:
        return ast.parse(source)
    except SyntaxError:
        return ast.parse(str(PY2_READER.refactor_string(source + "\n", str(path))))


def load_script(name):
    spec = importlib.util.spec_from_file_location(name + "_review_test", SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def server_method(name):
    tree = parse_script(SCRIPTS / "serverSystem.py")
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ServerSystem")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "serverSystem.py", "exec"), namespace)
    return namespace[name]


class ReviewCode18Tests(unittest.TestCase):
    def test_runtime_pack_does_not_import_os_or_tempfile(self):
        violations = []
        for path in SCRIPTS.glob("*.py"):
            for node in ast.walk(parse_script(path)):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                for module in modules:
                    if module.split(".")[0] in ("os", "tempfile"):
                        violations.append("%s:%s %s" % (path.name, node.lineno, module))
        self.assertEqual([], violations)

    def test_entry_diagnostics_cannot_write_even_when_explicitly_enabled(self):
        diagnostics = load_script("entry_diagnostics")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entry.jsonl"
            writer = diagnostics.EntryDiagnostics(path=str(path), activate=True, worldgen_enabled=True)
            self.assertFalse(writer.write("entry", playerId="player"))
            self.assertFalse(diagnostics.write_worldgen_event("worldgen"))
            writer.deactivate()
            self.assertFalse(path.exists())

    def test_chain_diagnostics_do_not_write_files(self):
        chain = load_script("chain_visual_client")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chain.jsonl"
            client = object.__new__(chain.ChainVisuals)
            client.trace_path = str(path)
            client.trace_records = [{"event": "test"}]
            client.flush_trace()
            self.assertFalse(path.exists())
            self.assertEqual([], client.trace_records)
        self.assertIsNone(chain.diagnostic_path())

    def test_portal_callback_updates_the_same_dictionary_and_ignores_stale_keys(self):
        callback = server_method("_on_portal_background_chunk_ready")
        item = {"key": (7, 1, 2), "done": False}
        server = SimpleNamespace(_portal_background_preload_inflight=item)
        callback(server, (7, 9, 9), True)
        self.assertFalse(item["done"])
        callback(server, item["key"], False)
        self.assertTrue(item["done"])
        self.assertFalse(item["result"])
        callback(server, item["key"], None)
        self.assertTrue(item["result"])
        for invalid in (None, [], "stale"):
            server._portal_background_preload_inflight = invalid
            callback(server, item["key"], True)

    def test_reflector_selection_preserves_first_tie_and_supports_negative_scores(self):
        recover = server_method("_recover_ur_ghast_fireball_reflector")
        scores = iter([-3.0, None, -2.0, -2.0])
        recover.__globals__.update(
            math=math,
            entity_registry_logic=SimpleNamespace(matching_entity_key=lambda items, key: key),
            ur_ghast_logic=SimpleNamespace(reflection_recovery_score=lambda *args: next(scores)),
        )
        server = SimpleNamespace(
            _ur_ghast_projectiles={"fireball": {"velocity": (0, 0, 1)}},
            _get_foot_pos=lambda key: (0, 0, 0),
            _get_dimension=lambda key: 7,
            _get_online_players=lambda: ["first", "invalid", "best", "tie"],
            _get_rotation=lambda key: (0, 0),
            _entry_trace=lambda *args, **kwargs: None,
        )
        self.assertEqual("best", recover(server, "fireball"))
        server._get_online_players = lambda: []
        self.assertIsNone(recover(server, "fireball"))
        server._get_foot_pos = lambda key: None
        self.assertIsNone(recover(server, "fireball"))

    def test_raycast_does_not_use_placeholder_when_first_sample_is_solid(self):
        scepter = load_script("scepter_logic")
        self.assertIsNone(scepter.raycast_spawn_position(
            (0, 0, 0), (0, 0, 1), lambda cell: "minecraft:stone"))
        self.assertEqual((0.5, 0.0, 0.5), scepter.raycast_spawn_position(
            (0, 0, 0), (0, 0, 1),
            lambda cell: "minecraft:stone" if cell[2] >= 1 else "minecraft:air"))
        self.assertIsNone(scepter.raycast_spawn_position(
            (0, 0, 0), (0, 0, 1),
            lambda cell: "minecraft:stone" if cell[2] >= 1 or cell[1] >= 1 else "minecraft:air"))


if __name__ == "__main__":
    unittest.main()
