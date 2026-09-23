import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools import sync_packs
from tools.sync_packs import (
    diff_pack,
    ensure_safe_deployment_modes,
    mirror_addon,
    mirror_pack,
    mirror_selected_addon_files,
    mirror_selected_runtime_addon_files,
    mirror_selected_world_addon_files,
    mirror_world_addon,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pack_digest(root):
    entries = {}
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        entries[relative.as_posix()] = _sha256(path)
    return hashlib.sha256(
        json.dumps(
            entries,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class PackSyncTests(unittest.TestCase):
    @staticmethod
    def _write_center_tree_rule(path, iterations):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "format_version": "1.14.0",
                    "minecraft:feature_rules": {
                        "description": {
                            "identifier": (
                                "tf_slice:dark_forest_center_"
                                "tree_profile_feature_rule"
                            ),
                            "places_feature": (
                                "tf_slice:dark_forest_center_"
                                "tree_ground_search_feature"
                            ),
                        },
                        "conditions": {
                            "placement_pass": "after_surface_pass"
                        },
                        "distribution": {
                            "iterations": iterations,
                            "x": 0,
                            "y": 0,
                            "z": 0,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_scoped_sync_rejects_center_tree_spatial_exclusion(self):
        relative = (
            "netease_feature_rules/"
            "dark_forest_center_tree_profile_feature_rule.json"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / relative
            self._write_center_tree_rule(
                source,
                "((variable.originx * variable.originx <= 6400) ? 0 : 16)",
            )
            selected = [
                (
                    "TwilightBossSliceB",
                    relative,
                    source,
                    Path(temp_dir) / "target.json",
                )
            ]
            with self.assertRaisesRegex(
                ValueError,
                "must not contain a spatial exclusion",
            ):
                sync_packs._validate_selected_source_files(selected)

    def test_scoped_sync_accepts_center_tree_without_exclusion(self):
        relative = (
            "netease_feature_rules/"
            "dark_forest_center_tree_profile_feature_rule.json"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / relative
            self._write_center_tree_rule(source, 16)
            selected = [
                (
                    "TwilightBossSliceB",
                    relative,
                    source,
                    Path(temp_dir) / "target.json",
                )
            ]
            sync_packs._validate_selected_source_files(selected)

    @staticmethod
    def _write_scoped_cli_fixture(root):
        source = root / "tmp" / "payload"
        world = root / "world"
        for pack, pack_id, folder in (
            (
                "TwilightBossSliceB",
                "behavior-id",
                world / "behavior_packs" / "TwilightBossSliceB",
            ),
            (
                "TwilightBossSliceR",
                "resource-id",
                world / "resource_packs" / "TwilightBossSliceR",
            ),
        ):
            source_pack = source / pack
            source_pack.mkdir(parents=True)
            folder.mkdir(parents=True)
            (source_pack / "manifest.json").write_text(
                json.dumps({
                    "header": {
                        "uuid": pack_id,
                        "version": [0, 11, 73],
                    }
                }),
                encoding="utf-8",
            )
            (folder / "manifest.json").write_text(
                json.dumps({
                    "header": {
                        "uuid": pack_id,
                        "version": [0, 11, 72],
                    }
                }),
                encoding="utf-8",
            )
        (source / "TwilightBossSliceB" / "selected.py").write_text(
            "new", encoding="utf-8"
        )
        (
            world
            / "behavior_packs"
            / "TwilightBossSliceB"
            / "selected.py"
        ).write_text("old", encoding="utf-8")
        return source, world

    def test_scoped_world_cli_accepts_restricted_source_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, world = self._write_scoped_cli_fixture(root)
            argv = [
                "sync_packs.py",
                "--source-root",
                str(source),
                "--world-root",
                str(world),
                "--include-file",
                "TwilightBossSliceB:manifest.json",
                "--include-file",
                "TwilightBossSliceB:selected.py",
            ]

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ):
                self.assertEqual(0, sync_packs.main())

            self.assertEqual(
                "new",
                (
                    world
                    / "behavior_packs"
                    / "TwilightBossSliceB"
                    / "selected.py"
                ).read_text(encoding="utf-8"),
            )

    def test_scoped_world_cli_rejects_source_root_outside_task_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, world = self._write_scoped_cli_fixture(root)
            outside = root / "outside"
            source.rename(outside)
            argv = [
                "sync_packs.py",
                "--source-root",
                str(outside),
                "--world-root",
                str(world),
                "--include-file",
                "TwilightBossSliceB:selected.py",
            ]

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ), self.assertRaises(SystemExit):
                sync_packs.main()

    def test_full_cli_requires_explicit_full_mirror_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target"
            argv = ["sync_packs.py", "--target-root", str(target)]
            stderr = io.StringIO()

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ), mock.patch.object(sync_packs, "_validate_source"), mock.patch.object(
                sync_packs, "mirror_addon", return_value={}
            ), redirect_stderr(stderr), self.assertRaises(SystemExit):
                sync_packs.main()

            self.assertIn("--acknowledge-full-mirror", stderr.getvalue())
            self.assertFalse(target.exists())

    def test_scoped_cli_rejects_full_mirror_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, world = self._write_scoped_cli_fixture(root)
            argv = [
                "sync_packs.py",
                "--source-root",
                str(source),
                "--world-root",
                str(world),
                "--include-file",
                "TwilightBossSliceB:selected.py",
                "--acknowledge-full-mirror",
            ]
            stderr = io.StringIO()

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ), redirect_stderr(stderr), self.assertRaises(SystemExit):
                sync_packs.main()

            self.assertIn("cannot be combined", stderr.getvalue())

    def test_cli_reports_scoped_and_full_modes_explicitly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, world = self._write_scoped_cli_fixture(root)
            scoped_argv = [
                "sync_packs.py",
                "--source-root",
                str(source),
                "--world-root",
                str(world),
                "--include-file",
                "TwilightBossSliceB:selected.py",
            ]
            scoped_output = io.StringIO()
            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", scoped_argv
            ), redirect_stdout(scoped_output):
                self.assertEqual(0, sync_packs.main())
            self.assertIn("MODE: SCOPED", scoped_output.getvalue())

            full_argv = [
                "sync_packs.py",
                "--target-root",
                str(root / "full-target"),
                "--acknowledge-full-mirror",
            ]
            full_output = io.StringIO()
            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", full_argv
            ), mock.patch.object(sync_packs, "_validate_source"), mock.patch.object(
                sync_packs, "mirror_addon", return_value={}
            ), redirect_stdout(full_output):
                self.assertEqual(0, sync_packs.main())
            self.assertIn("MODE: FULL_MIRROR", full_output.getvalue())

    def test_cold_start_candidate_cli_rejects_non_isolated_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            argv = [
                "sync_packs.py",
                "--target-root",
                str(root / "active-studio"),
                "--allow-large-sync",
                "--acknowledge-full-mirror",
                "--prepare-cold-start-candidate",
            ]
            stderr = io.StringIO()

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ), redirect_stderr(stderr), self.assertRaises(SystemExit):
                sync_packs.main()

            self.assertIn("runtime_backups or tmp", stderr.getvalue())

    def test_cold_start_candidate_cli_requires_large_sync_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = root / "runtime_backups" / "candidate" / "AddOn"
            argv = [
                "sync_packs.py",
                "--target-root",
                str(candidate),
                "--acknowledge-full-mirror",
                "--prepare-cold-start-candidate",
            ]
            stderr = io.StringIO()

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ), redirect_stderr(stderr), self.assertRaises(SystemExit):
                sync_packs.main()

            self.assertIn("--allow-large-sync", stderr.getvalue())

    def test_cold_start_candidate_cli_bypasses_only_the_old_attestation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = root / "runtime_backups" / "candidate" / "AddOn"
            argv = [
                "sync_packs.py",
                "--target-root",
                str(candidate),
                "--allow-large-sync",
                "--acknowledge-full-mirror",
                "--prepare-cold-start-candidate",
            ]
            output = io.StringIO()

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ), mock.patch.object(sync_packs, "_validate_source"), mock.patch.object(
                sync_packs, "mirror_addon", return_value={}
            ) as mirror, redirect_stdout(output):
                self.assertEqual(0, sync_packs.main())

            self.assertIn("MODE: COLD_START_CANDIDATE", output.getvalue())
            mirror.assert_called_once_with(
                root,
                candidate.resolve(),
                candidate.resolve(),
                allow_large_sync=True,
                require_cold_start_attestation=False,
                allow_source_bound_target=True,
            )

    def test_cold_start_candidate_cli_accepts_registered_isolated_world(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root = base / "repo"
            uid = "6f0af3ac9d244e0ca3b2f17d88603c71"
            world = base / "mcstudio" / uid
            world.mkdir(parents=True)
            (world / "work.mcscfg").write_text(
                json.dumps(
                    {
                        "UID": uid,
                        "Name": "Codex Cold Start",
                        "EditMapUID": uid,
                        "TestMapUID": uid,
                    }
                ),
                encoding="utf-8",
            )
            (world / "studio.json").write_text(
                json.dumps(
                    {
                        "Id": uid,
                        "IsMap": True,
                        "SaveBackMapPath": str(world.resolve()),
                    }
                ),
                encoding="utf-8",
            )
            argv = [
                "sync_packs.py",
                "--world-root",
                str(world),
                "--allow-large-sync",
                "--acknowledge-full-mirror",
                "--prepare-cold-start-candidate",
            ]

            with mock.patch.object(sync_packs, "ROOT", root), mock.patch.object(
                sys, "argv", argv
            ), mock.patch.object(sync_packs, "_validate_source"), mock.patch.object(
                sync_packs, "mirror_world_addon", return_value={}
            ) as mirror:
                self.assertEqual(0, sync_packs.main())

            mirror.assert_called_once_with(
                root,
                world.resolve(),
                allow_large_sync=True,
                require_cold_start_attestation=False,
                allow_source_bound_target=True,
            )

    def test_process_lock_serializes_live_syncs_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "pack_sync_process_lock.json"
            alive = {101, 202}
            first = sync_packs.PackSyncProcessLock(
                lock_path,
                owner_pid=101,
                process_is_alive=lambda pid: pid in alive,
            )
            second = sync_packs.PackSyncProcessLock(
                lock_path,
                owner_pid=202,
                process_is_alive=lambda pid: pid in alive,
            )

            with first.hold("scoped"):
                document = json.loads(lock_path.read_text(encoding="utf-8"))
                self.assertEqual(101, document["ownerPid"])
                with self.assertRaisesRegex(RuntimeError, "live PID 101"):
                    with second.hold("full-mirror"):
                        pass

            self.assertFalse(lock_path.exists())

    def test_process_lock_reclaims_a_dead_owner_and_fails_closed_on_corruption(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "pack_sync_process_lock.json"
            lock_path.write_text(
                json.dumps({"ownerPid": 101, "token": "old"}),
                encoding="utf-8",
            )
            lock = sync_packs.PackSyncProcessLock(
                lock_path,
                owner_pid=202,
                process_is_alive=lambda pid: False,
            )
            with lock.hold("scoped"):
                self.assertEqual(
                    202,
                    json.loads(lock_path.read_text(encoding="utf-8"))["ownerPid"],
                )
            self.assertFalse(lock_path.exists())

            lock_path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unreadable"):
                with lock.hold("scoped"):
                    pass

    def test_studio_and_global_runtime_require_explicit_parallel_opt_in(self):
        with self.assertRaisesRegex(ValueError, "duplicate pack stack"):
            ensure_safe_deployment_modes(
                target_roots=[Path("studio")],
                behavior_root=Path("behavior_packs"),
                resource_root=Path("resource_packs"),
                world_roots=[],
                allow_multiple=False,
            )
        ensure_safe_deployment_modes(
            target_roots=[Path("studio")],
            behavior_root=Path("behavior_packs"),
            resource_root=Path("resource_packs"),
            world_roots=[],
            allow_multiple=True,
        )

    @unittest.skipUnless(
        os.environ.get("TF_SLICE_TEST_WORLD_ROOT")
        or os.environ.get("TF_SLICE_TEST_TARGET_ROOT"),
        "set TF_SLICE_TEST_WORLD_ROOT or TF_SLICE_TEST_TARGET_ROOT",
    )
    def test_active_world_has_current_labyrinth_artifacts(self):
        source = ROOT / "TwilightBossSliceB"
        if os.environ.get("TF_SLICE_TEST_TARGET_ROOT"):
            deployed = (
                Path(os.environ["TF_SLICE_TEST_TARGET_ROOT"])
                / "TwilightBossSliceB"
            )
        else:
            deployed = (
                Path(os.environ["TF_SLICE_TEST_WORLD_ROOT"])
                / "behavior_packs"
                / "TwilightBossSliceB"
            )
        critical_files = (
            "TwilightBossSlice/ruin_catalog_data.py",
            "structures/tf_slice/ruins/structure_catalog_v1.json",
            "structures/tf_slice/ruins/labyrinth/v00/x048_z048.mcstructure",
            "structures/tf_slice/ruins/labyrinth/v00/x016_z048.mcstructure",
            "structures/tf_slice/ruins/surface_native/labyrinth/v00/mx08_mz08/xp00_zp00.mcstructure",
            "structures/tf_slice/ruins/surface_native/labyrinth/v00/mx08_mz08/xm02_zp00.mcstructure",
        )
        for relative in critical_files:
            source_path = source / relative
            deployed_path = deployed / relative
            self.assertTrue(source_path.is_file(), relative)
            self.assertTrue(deployed_path.is_file(), relative)
            self.assertEqual(
                _sha256(source_path),
                _sha256(deployed_path),
                relative,
            )

    def test_world_sync_updates_matching_netease_pack_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            world_root = root / "world"
            behavior_id = "behavior-pack-id"
            resource_id = "resource-pack-id"
            for pack_name, pack_id in (
                ("TwilightBossSliceB", behavior_id),
                ("TwilightBossSliceR", resource_id),
            ):
                pack_root = source / pack_name
                pack_root.mkdir(parents=True)
                (pack_root / "manifest.json").write_text(
                    json.dumps(
                        {
                            "header": {
                                "uuid": pack_id,
                                "version": [0, 9, 7],
                            }
                        }
                    ),
                    encoding="utf-8",
                )
            world_root.mkdir()
            behavior_refs = world_root / "netease_world_behavior_packs.json"
            resource_refs = world_root / "netease_world_resource_packs.json"
            behavior_refs.write_text(
                json.dumps(
                    [
                        {"pack_id": behavior_id, "version": [0, 9, 3]},
                        {"pack_id": resource_id, "version": [0, 9, 3]},
                        {"pack_id": "unrelated", "version": [1, 2, 3]},
                    ]
                ),
                encoding="utf-8",
            )
            resource_refs.write_text(
                json.dumps(
                    [{"pack_id": resource_id, "version": [0, 9, 3]}]
                ),
                encoding="utf-8",
            )

            mirror_world_addon(source, world_root)

            behavior = json.loads(
                behavior_refs.read_text(encoding="utf-8")
            )
            resource = json.loads(
                resource_refs.read_text(encoding="utf-8")
            )
            self.assertEqual([0, 9, 7], behavior[0]["version"])
            self.assertEqual([0, 9, 7], behavior[1]["version"])
            self.assertEqual([1, 2, 3], behavior[2]["version"])
            self.assertEqual([0, 9, 7], resource[0]["version"])

    def test_world_sync_accepts_bom_prefixed_pack_references(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            world_root = root / "world"
            pack_root = source / "TwilightBossSliceB"
            pack_root.mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)
            (pack_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "header": {
                            "uuid": "behavior-pack-id",
                            "version": [0, 9, 8],
                        }
                    }
                ),
                encoding="utf-8",
            )
            world_root.mkdir()
            references = world_root / "world_behavior_packs.json"
            references.write_text(
                json.dumps(
                    [
                        {
                            "pack_id": "behavior-pack-id",
                            "version": [0, 9, 7],
                        }
                    ]
                ),
                encoding="utf-8-sig",
            )

            mirror_world_addon(source, world_root)

            updated = json.loads(
                references.read_text(encoding="utf-8-sig")
            )
            self.assertEqual([0, 9, 8], updated[0]["version"])

    def test_addon_can_sync_into_a_worlds_embedded_pack_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            world_root = root / "world"
            (source / "TwilightBossSliceB").mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)
            (source / "TwilightBossSliceB" / "behavior.txt").write_text(
                "behavior", encoding="utf-8"
            )
            (source / "TwilightBossSliceR" / "resource.txt").write_text(
                "resource", encoding="utf-8"
            )

            mirror_world_addon(source, world_root)

            self.assertEqual(
                "behavior",
                (
                    world_root
                    / "behavior_packs"
                    / "TwilightBossSliceB"
                    / "behavior.txt"
                ).read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "resource",
                (
                    world_root
                    / "resource_packs"
                    / "TwilightBossSliceR"
                    / "resource.txt"
                ).read_text(encoding="utf-8"),
            )

    def test_addon_can_sync_to_separate_behavior_and_resource_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            behavior_root = root / "behavior_packs"
            resource_root = root / "resource_packs"
            (source / "TwilightBossSliceB").mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)
            (source / "TwilightBossSliceB" / "behavior.txt").write_text(
                "behavior", encoding="utf-8"
            )
            (source / "TwilightBossSliceR" / "resource.txt").write_text(
                "resource", encoding="utf-8"
            )

            mirror_addon(source, behavior_root, resource_root)

            self.assertEqual(
                "behavior",
                (
                    behavior_root
                    / "TwilightBossSliceB"
                    / "behavior.txt"
                ).read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "resource",
                (
                    resource_root
                    / "TwilightBossSliceR"
                    / "resource.txt"
                ).read_text(encoding="utf-8"),
            )

    def test_scoped_runtime_sync_uses_separate_pack_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            behavior_root = root / "behavior_packs"
            resource_root = root / "resource_packs"
            behavior = source / "TwilightBossSliceB"
            resources = source / "TwilightBossSliceR"
            deployed_resources = resource_root / "TwilightBossSliceR"
            behavior.mkdir(parents=True)
            resources.mkdir(parents=True)
            deployed_resources.mkdir(parents=True)
            (resources / "selected.json").write_text(
                '{"new": true}', encoding="utf-8"
            )
            (resources / "unrelated.json").write_text(
                '{"source": true}', encoding="utf-8"
            )
            (deployed_resources / "selected.json").write_text(
                '{"old": true}', encoding="utf-8"
            )
            (deployed_resources / "unrelated.json").write_text(
                '{"target": true}', encoding="utf-8"
            )

            results = mirror_selected_runtime_addon_files(
                source,
                behavior_root,
                resource_root,
                ["TwilightBossSliceR:selected.json"],
            )

            self.assertEqual(1, results["TwilightBossSliceR"].copied)
            self.assertEqual(
                '{"new": true}',
                (deployed_resources / "selected.json").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual(
                '{"target": true}',
                (deployed_resources / "unrelated.json").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertFalse(
                (behavior_root / "TwilightBossSliceB").exists()
            )

    def test_scoped_addon_sync_only_copies_allowlisted_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source_pack = source / "TwilightBossSliceB"
            target_pack = target / "TwilightBossSliceB"
            source_pack.mkdir(parents=True)
            target_pack.mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)
            (target / "TwilightBossSliceR").mkdir(parents=True)
            (source_pack / "selected.txt").write_text(
                "new selected", encoding="utf-8"
            )
            (target_pack / "selected.txt").write_text(
                "old selected", encoding="utf-8"
            )
            (source_pack / "unrelated.txt").write_text(
                "new unrelated", encoding="utf-8"
            )
            (target_pack / "unrelated.txt").write_text(
                "old unrelated", encoding="utf-8"
            )

            results = mirror_selected_addon_files(
                source,
                target,
                ["TwilightBossSliceB:selected.txt"],
            )

            self.assertEqual(1, results["TwilightBossSliceB"].copied)
            self.assertEqual(0, results["TwilightBossSliceB"].removed)
            self.assertEqual(
                "new selected",
                (target_pack / "selected.txt").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "old unrelated",
                (target_pack / "unrelated.txt").read_text(encoding="utf-8"),
            )

    def test_scoped_addon_sync_deletes_only_allowlisted_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source_pack = source / "TwilightBossSliceB"
            target_pack = target / "TwilightBossSliceB"
            source_pack.mkdir(parents=True)
            target_pack.mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)
            (target / "TwilightBossSliceR").mkdir(parents=True)
            (source_pack / "selected.txt").write_text(
                "new selected", encoding="utf-8"
            )
            (target_pack / "selected.txt").write_text(
                "old selected", encoding="utf-8"
            )
            (target_pack / "retired.txt").write_text(
                "retired", encoding="utf-8"
            )
            (target_pack / "unrelated.txt").write_text(
                "keep", encoding="utf-8"
            )

            results = mirror_selected_addon_files(
                source,
                target,
                ["TwilightBossSliceB:selected.txt"],
                removals=["TwilightBossSliceB:retired.txt"],
            )

            self.assertEqual(1, results["TwilightBossSliceB"].copied)
            self.assertEqual(1, results["TwilightBossSliceB"].removed)
            self.assertFalse((target_pack / "retired.txt").exists())
            self.assertEqual(
                "keep",
                (target_pack / "unrelated.txt").read_text(encoding="utf-8"),
            )

    def test_scoped_world_sync_updates_only_selected_files_and_pack_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            world = root / "world"
            behavior = source / "TwilightBossSliceB"
            resources = source / "TwilightBossSliceR"
            deployed_behavior = (
                world / "behavior_packs" / "TwilightBossSliceB"
            )
            deployed_resources = (
                world / "resource_packs" / "TwilightBossSliceR"
            )
            for path in (
                behavior, resources, deployed_behavior, deployed_resources
            ):
                path.mkdir(parents=True)
            for pack, pack_id in (
                (behavior, "behavior-id"),
                (resources, "resource-id"),
            ):
                (pack / "manifest.json").write_text(
                    json.dumps({
                        "header": {
                            "uuid": pack_id,
                            "version": [0, 11, 73],
                        }
                    }),
                    encoding="utf-8",
                )
            (behavior / "selected.py").write_text("new", encoding="utf-8")
            (resources / "selected.json").write_text("{}", encoding="utf-8")
            (deployed_behavior / "selected.py").write_text(
                "old", encoding="utf-8"
            )
            (deployed_resources / "selected.json").write_text(
                '{"old": true}', encoding="utf-8"
            )
            (deployed_behavior / "unrelated.py").write_text(
                "keep", encoding="utf-8"
            )
            (world / "netease_world_behavior_packs.json").write_text(
                json.dumps([
                    {"pack_id": "behavior-id", "version": [0, 11, 72]},
                    {"pack_id": "resource-id", "version": [0, 11, 72]},
                ]),
                encoding="utf-8",
            )
            (world / "netease_world_resource_packs.json").write_text(
                json.dumps([
                    {"pack_id": "resource-id", "version": [0, 11, 72]}
                ]),
                encoding="utf-8",
            )

            results = mirror_selected_world_addon_files(
                source,
                world,
                [
                    "TwilightBossSliceB:manifest.json",
                    "TwilightBossSliceB:selected.py",
                    "TwilightBossSliceR:manifest.json",
                    "TwilightBossSliceR:selected.json",
                ],
            )

            self.assertEqual(2, results["TwilightBossSliceB"].copied)
            self.assertEqual(2, results["TwilightBossSliceR"].copied)
            self.assertEqual(
                "new",
                (deployed_behavior / "selected.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "keep",
                (deployed_behavior / "unrelated.py").read_text(encoding="utf-8"),
            )
            behavior_refs = json.loads(
                (world / "netease_world_behavior_packs.json").read_text(
                    encoding="utf-8"
                )
            )
            resource_refs = json.loads(
                (world / "netease_world_resource_packs.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual([0, 11, 73], behavior_refs[0]["version"])
            self.assertEqual([0, 11, 73], behavior_refs[1]["version"])
            self.assertEqual([0, 11, 73], resource_refs[0]["version"])

    def test_scoped_world_sync_repairs_single_placeholder_pack_references(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            world = root / "world"
            behavior = source / "TwilightBossSliceB"
            resources = source / "TwilightBossSliceR"
            behavior.mkdir(parents=True)
            resources.mkdir(parents=True)
            world.mkdir()
            for pack, pack_id in (
                (behavior, "behavior-id"),
                (resources, "resource-id"),
            ):
                (pack / "manifest.json").write_text(
                    json.dumps({
                        "header": {
                            "uuid": pack_id,
                            "version": [0, 11, 79],
                        }
                    }),
                    encoding="utf-8",
                )
            (world / "world_behavior_packs.json").write_text(
                json.dumps([
                    {
                        "pack_id": "placeholder-behavior-id",
                        "type": "Addon",
                        "version": [0, 0, 1],
                    }
                ]),
                encoding="utf-8",
            )
            (world / "world_resource_packs.json").write_text(
                json.dumps([
                    {
                        "pack_id": "placeholder-resource-id",
                        "type": "Addon",
                        "version": [0, 0, 1],
                    }
                ]),
                encoding="utf-8",
            )

            mirror_selected_world_addon_files(
                source,
                world,
                [
                    "TwilightBossSliceB:manifest.json",
                    "TwilightBossSliceR:manifest.json",
                ],
            )

            behavior_ref = json.loads(
                (world / "world_behavior_packs.json").read_text(
                    encoding="utf-8"
                )
            )[0]
            resource_ref = json.loads(
                (world / "world_resource_packs.json").read_text(
                    encoding="utf-8"
                )
            )[0]
            self.assertEqual("behavior-id", behavior_ref["pack_id"])
            self.assertEqual([0, 11, 79], behavior_ref["version"])
            self.assertEqual("resource-id", resource_ref["pack_id"])
            self.assertEqual([0, 11, 79], resource_ref["version"])

    def test_scoped_addon_sync_rejects_invalid_selected_block_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source_block = (
                source
                / "TwilightBossSliceB"
                / "netease_blocks"
                / "selected.json"
            )
            target_block = (
                target
                / "TwilightBossSliceB"
                / "netease_blocks"
                / "selected.json"
            )
            source_block.parent.mkdir(parents=True)
            target_block.parent.mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)
            (target / "TwilightBossSliceR").mkdir(parents=True)
            source_block.write_text("{", encoding="utf-8")
            target_block.write_text("old target", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid selected JSON"):
                mirror_selected_addon_files(
                    source,
                    target,
                    [
                        "TwilightBossSliceB:"
                        "netease_blocks/selected.json"
                    ],
                )

            self.assertEqual(
                "old target",
                target_block.read_text(encoding="utf-8"),
            )

    def test_scoped_addon_sync_rejects_paths_outside_a_pack(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            (source / "TwilightBossSliceB").mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "relative pack path"):
                mirror_selected_addon_files(
                    source,
                    target,
                    ["TwilightBossSliceB:../outside.json"],
                )

    def test_scoped_addon_sync_rejects_unknown_packs_and_missing_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            (source / "TwilightBossSliceB").mkdir(parents=True)
            (source / "TwilightBossSliceR").mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "Unknown pack"):
                mirror_selected_addon_files(
                    source,
                    target,
                    ["OtherPack:selected.json"],
                )
            with self.assertRaisesRegex(ValueError, "Source file does not exist"):
                mirror_selected_addon_files(
                    source,
                    target,
                    ["TwilightBossSliceB:missing.json"],
                )

    def test_mirror_removes_stale_files_and_produces_an_exact_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            (source / "nested").mkdir(parents=True)
            (target / "nested").mkdir(parents=True)
            (source / "manifest.json").write_text("new", encoding="utf-8")
            (source / "nested" / "current.json").write_text(
                "current", encoding="utf-8"
            )
            (target / "manifest.json").write_text("old", encoding="utf-8")
            (target / "nested" / "stale.json").write_text(
                "stale", encoding="utf-8"
            )

            result = mirror_pack(source, target)

            self.assertEqual(2, result.copied)
            self.assertEqual(1, result.removed)
            self.assertFalse((target / "nested" / "stale.json").exists())
            self.assertEqual([], diff_pack(source, target))

    def test_mirror_does_not_deploy_python_bytecode_and_purges_stale_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            (source / "package" / "__pycache__").mkdir(parents=True)
            (target / "package" / "__pycache__").mkdir(parents=True)
            (source / "package" / "logic.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            (source / "package" / "__pycache__" / "logic.cpython-314.pyc").write_bytes(
                b"source-bytecode"
            )
            stale_cache = (
                target
                / "package"
                / "__pycache__"
                / "logic.cpython-311.pyc"
            )
            stale_cache.write_bytes(b"stale-bytecode")

            result = mirror_pack(source, target)

            self.assertEqual(1, result.copied)
            self.assertEqual(1, result.removed)
            self.assertTrue((target / "package" / "logic.py").is_file())
            self.assertFalse(stale_cache.exists())
            self.assertFalse((target / "package" / "__pycache__").exists())

    def test_mirror_does_not_rewrite_byte_identical_target_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "stable.mcstructure").write_bytes(b"same-template")
            destination = target / "stable.mcstructure"
            destination.write_bytes(b"same-template")
            original_mtime = destination.stat().st_mtime_ns

            result = mirror_pack(source, target)

            self.assertEqual(0, result.copied)
            self.assertEqual(original_mtime, destination.stat().st_mtime_ns)

    def test_mirror_rejects_an_unreviewed_large_change_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            for index in range(33):
                (source / f"changed_{index:02d}.txt").write_text(
                    "new",
                    encoding="utf-8",
                )
                (target / f"changed_{index:02d}.txt").write_text(
                    "old",
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(RuntimeError, "large sync"):
                mirror_pack(source, target)

            self.assertEqual(
                "old",
                (target / "changed_00.txt").read_text(encoding="utf-8"),
            )

    def test_mirror_allows_an_explicitly_reviewed_large_change_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            for index in range(33):
                (source / f"changed_{index:02d}.txt").write_text(
                    "new",
                    encoding="utf-8",
                )
                (target / f"changed_{index:02d}.txt").write_text(
                    "old",
                    encoding="utf-8",
                )

            result = mirror_pack(
                source,
                target,
                allow_large_sync=True,
            )

            self.assertEqual(33, result.copied)
            self.assertEqual([], diff_pack(source, target))

    def test_candidate_mirror_accepts_pack_roots_bound_to_the_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            for pack_name in ("TwilightBossSliceB", "TwilightBossSliceR"):
                (source / pack_name).mkdir()

            with self.assertRaisesRegex(ValueError, "outside the source"):
                mirror_addon(source, source, source)

            results = mirror_addon(
                source,
                source,
                source,
                allow_source_bound_target=True,
            )

            self.assertEqual(0, results["TwilightBossSliceB"].copied)
            self.assertEqual(0, results["TwilightBossSliceR"].copied)

    def test_large_structure_sync_requires_matching_cold_start_attestation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            behavior = source / "TwilightBossSliceB"
            resources = source / "TwilightBossSliceR"
            catalog_path = (
                behavior
                / "structures"
                / "tf_slice"
                / "ruins"
                / "structure_catalog_v1.json"
            )
            catalog_path.parent.mkdir(parents=True)
            resources.mkdir(parents=True)
            catalog = {"structures": []}
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            for index in range(33):
                path = (
                    behavior
                    / "structures"
                    / "tf_slice"
                    / "ruins"
                    / f"piece_{index:02d}.mcstructure"
                )
                path.write_bytes(b"new")

            lock_root = source / "source_locks"
            lock_root.mkdir()
            attestation = lock_root / "runtime_cold_start_attestation.json"
            attestation.write_text(
                json.dumps({"schemaVersion": 2, "catalogSha256": "stale"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "cold-start attestation"):
                mirror_addon(
                    source,
                    target,
                    target,
                    allow_large_sync=True,
                )

            digest = hashlib.sha256(
                json.dumps(
                    catalog,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            attested_pack_digest = _pack_digest(behavior)
            attestation.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "catalogSha256": digest,
                        "behaviorPackSha256": attested_pack_digest,
                    }
                ),
                encoding="utf-8",
            )

            (behavior / "logic.py").write_text(
                "changed after cold start\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "behavior pack",
            ):
                mirror_addon(
                    source,
                    target,
                    target,
                    allow_large_sync=True,
                )

            attestation.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "catalogSha256": digest,
                        "behaviorPackSha256": _pack_digest(behavior),
                    }
                ),
                encoding="utf-8",
            )

            result = mirror_addon(
                source,
                target,
                target,
                allow_large_sync=True,
            )

            self.assertEqual(35, result["TwilightBossSliceB"].copied)

    def test_diff_reports_missing_changed_and_extra_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "missing.txt").write_text("source", encoding="utf-8")
            (source / "changed.txt").write_text("source", encoding="utf-8")
            (target / "changed.txt").write_text("target", encoding="utf-8")
            (target / "extra.txt").write_text("extra", encoding="utf-8")

            differences = diff_pack(source, target)

            self.assertEqual(
                [
                    "changed: changed.txt",
                    "extra: extra.txt",
                    "missing: missing.txt",
                ],
                differences,
            )


if __name__ == "__main__":
    unittest.main()
