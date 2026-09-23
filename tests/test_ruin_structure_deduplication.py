import json
import pathlib
import sys
import tempfile
import types
import unittest
import warnings

from lib2to3.refactor import RefactoringTool


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
MODULE_ROOT = BP / "TwilightBossSlice"
SERVICE_PATH = MODULE_ROOT / "structureWorldgenService.py"
sys.path.insert(0, str(BP))
sys.path.insert(0, str(ROOT))

from tools import build_ruin_structures as builder
from TwilightBossSlice import ruin_worldgen_logic


def load_service_module():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    if not source.endswith("\n"):
        source += "\n"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        converted = RefactoringTool(
            ["lib2to3.fixes.fix_print"]
        ).refactor_string(source, str(SERVICE_PATH))
    module = types.ModuleType("structure_worldgen_deduplication_under_test")
    module.__file__ = str(SERVICE_PATH)
    exec(compile(str(converted), str(SERVICE_PATH), "exec"), module.__dict__)
    return module


SERVICE = load_service_module()


class RuinStructureDeduplicationTests(unittest.TestCase):
    def test_external_literal_references_pin_engine_visible_structures(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            bp = pathlib.Path(temporary_directory) / "TwilightBossSliceB"
            output = bp / "structures" / "tf_slice" / "ruins"
            pinned = output / "native" / "pinned.mcstructure"
            dynamic = output / "surface_native" / "dynamic.mcstructure"
            pinned.parent.mkdir(parents=True)
            dynamic.parent.mkdir(parents=True)
            pinned.write_bytes(b"pinned")
            dynamic.write_bytes(b"dynamic")
            feature = bp / "netease_features" / "pinned_feature.json"
            feature.parent.mkdir(parents=True)
            feature.write_text(
                json.dumps(
                    {
                        "minecraft:structure_template_feature": {
                            "places_structure": "tf_slice:ruins/native/pinned"
                        }
                    }
                ),
                encoding="utf-8",
            )
            (output / "ignored_catalog.json").write_text(
                json.dumps(
                    {"structure": "tf_slice/ruins/surface_native/dynamic"}
                ),
                encoding="utf-8",
            )

            references = builder.collect_external_ruin_structure_references(
                bp,
                output,
            )

            self.assertEqual(
                {"tf_slice/ruins/native/pinned"},
                references,
            )

    def test_exact_duplicates_are_removed_without_deleting_pinned_targets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = pathlib.Path(temporary_directory) / "tf_slice" / "ruins"
            first = output / "dynamic" / "a.mcstructure"
            second = output / "dynamic" / "b.mcstructure"
            pinned = output / "dynamic" / "pinned.mcstructure"
            pinned_twin = output / "dynamic" / "also_pinned.mcstructure"
            dynamic_twin = output / "dynamic" / "c.mcstructure"
            unique = output / "dynamic" / "unique.mcstructure"
            for path in (
                first,
                second,
                pinned,
                pinned_twin,
                dynamic_twin,
                unique,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
            first.write_bytes(b"A" * 96)
            second.write_bytes(b"A" * 96)
            pinned.write_bytes(b"B" * 128)
            pinned_twin.write_bytes(b"B" * 128)
            dynamic_twin.write_bytes(b"B" * 128)
            unique.write_bytes(b"C" * 160)

            aliases, statistics = builder.deduplicate_ruin_structure_files(
                output,
                {
                    "tf_slice/ruins/dynamic/pinned",
                    "tf_slice/ruins/dynamic/also_pinned",
                },
            )

            self.assertTrue(first.is_file())
            self.assertFalse(second.exists())
            self.assertTrue(pinned.is_file())
            self.assertTrue(pinned_twin.is_file())
            self.assertFalse(dynamic_twin.exists())
            self.assertTrue(unique.is_file())
            self.assertEqual(
                "tf_slice/ruins/dynamic/a",
                aliases["tf_slice/ruins/dynamic/b"],
            )
            self.assertEqual(
                "tf_slice/ruins/dynamic/also_pinned",
                aliases["tf_slice/ruins/dynamic/c"],
            )
            self.assertNotIn("tf_slice/ruins/dynamic/pinned", aliases)
            self.assertNotIn("tf_slice/ruins/dynamic/also_pinned", aliases)
            self.assertEqual(2, statistics["removedFileCount"])
            self.assertEqual(224, statistics["removedUncompressedBytes"])
            self.assertEqual(2, statistics["retainedPinnedFileCount"])

    def test_alias_resolution_is_transitive_and_rejects_cycles(self):
        aliases = {
            "tf_slice/ruins/old/a": "tf_slice/ruins/old/b",
            "tf_slice/ruins/old/b": "tf_slice/ruins/shared/canonical",
        }
        self.assertEqual(
            "tf_slice/ruins/shared/canonical",
            builder.resolve_ruin_structure_reference(
                "tf_slice/ruins/old/a",
                aliases,
            ),
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            builder.resolve_ruin_structure_reference(
                "tf_slice/ruins/old/a",
                {
                    "tf_slice/ruins/old/a": "tf_slice/ruins/old/b",
                    "tf_slice/ruins/old/b": "tf_slice/ruins/old/a",
                },
            )

    def test_deduplication_does_not_cross_runtime_structure_domains(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = pathlib.Path(temporary_directory) / "tf_slice" / "ruins"
            surface = (
                output
                / "surface_native"
                / "dark_tower"
                / "v00"
                / "tile.mcstructure"
            )
            cleanup = (
                output
                / "dark_tower_canopy_cleanup"
                / "v00"
                / "tile.mcstructure"
            )
            other_surface = (
                output
                / "surface_native"
                / "lich_tower"
                / "v00"
                / "tile.mcstructure"
            )
            for path in (surface, cleanup, other_surface):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"same bytes" * 12)

            aliases, removals, statistics = (
                builder.plan_ruin_structure_deduplication(output)
            )

            self.assertEqual({}, aliases)
            self.assertEqual([], removals)
            self.assertEqual(3, statistics["canonicalFileCount"])
            self.assertEqual(0, statistics["removedFileCount"])

    def test_runtime_resolves_algorithmic_surface_tile_before_engine_lookup(self):
        logical_reference = ruin_worldgen_logic.surface_native_tile_reference(
            "tf_slice/ruins/surface_native/lich_tower/v00",
            "8,8",
            -2,
            3,
        )
        canonical_reference = "tf_slice/ruins/shared/canonical"

        self.assertEqual(
            "tf_slice:ruins/shared/canonical",
            SERVICE._structure_engine_name(
                logical_reference,
                {logical_reference: canonical_reference},
            ),
        )


if __name__ == "__main__":
    unittest.main()
