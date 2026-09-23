import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import build_ruin_structures as builder


class RuinBuildCliSafetyTests(unittest.TestCase):
    def test_check_validates_existing_artifacts_without_calling_build(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            catalog = {"structures": []}
            (output_root / "structure_catalog_v1.json").write_text(
                json.dumps(catalog),
                encoding="utf-8",
            )

            with (
                mock.patch.object(
                    builder,
                    "_exclusive_build_lock",
                    return_value=contextlib.nullcontext(),
                ),
                mock.patch.object(builder, "OUTPUT_ROOT", output_root),
                mock.patch.object(
                    builder,
                    "build",
                    side_effect=AssertionError("check mode mutated artifacts"),
                ) as build,
                mock.patch.object(builder, "validate") as validate,
            ):
                self.assertEqual(0, builder.main(["--check"]))

            build.assert_not_called()
            validate.assert_called_once_with(catalog)

    def test_write_is_the_explicit_mutating_mode(self):
        catalog = {"structures": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            lease_path = Path(temp_dir) / "write_lease.json"
            lease_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "status": "active",
                        "token": "unit-test-lease",
                    }
                ),
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    builder,
                    "_exclusive_build_lock",
                    return_value=contextlib.nullcontext(),
                ),
                mock.patch.object(builder, "WRITE_LEASE_PATH", lease_path),
                mock.patch.object(
                    builder,
                    "build",
                    return_value=catalog,
                ) as build,
                mock.patch.object(builder, "validate") as validate,
            ):
                self.assertEqual(
                    0,
                    builder.main(
                        [
                            "--write",
                            "--acknowledge-shared-artifact-write",
                            "--write-lease-token",
                            "unit-test-lease",
                        ]
                    ),
                )

            lease = json.loads(lease_path.read_text(encoding="utf-8"))
            self.assertEqual("frozen", lease["status"])
            self.assertNotIn("token", lease)

        build.assert_called_once_with()
        validate.assert_called_once_with(catalog)

    def test_write_refuses_to_clean_shared_artifacts_without_ownership_ack(self):
        with mock.patch.object(builder, "build") as build:
            with self.assertRaises(SystemExit):
                builder.main(["--write"])

        build.assert_not_called()

    def test_write_refuses_a_frozen_shared_artifact_lease(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lease_path = Path(temp_dir) / "write_lease.json"
            lease_path.write_text(
                json.dumps({"schemaVersion": 1, "status": "frozen"}),
                encoding="utf-8",
            )
            with (
                mock.patch.object(builder, "WRITE_LEASE_PATH", lease_path),
                mock.patch.object(builder, "build") as build,
            ):
                with self.assertRaisesRegex(RuntimeError, "frozen"):
                    builder.main(
                        [
                            "--write",
                            "--acknowledge-shared-artifact-write",
                            "--write-lease-token",
                            "not-active",
                        ]
                    )

            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
