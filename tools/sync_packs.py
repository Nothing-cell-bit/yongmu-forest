# -*- coding: utf-8 -*-
"""Validate and mirror the two AddOn packs into explicit runtime targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

ROOT = Path(__file__).resolve().parents[1]
PACK_NAMES = ("TwilightBossSliceB", "TwilightBossSliceR")
MAX_UNREVIEWED_SYNC_CHANGES = 32
CENTER_TREE_RULE_RELATIVE = (
    "netease_feature_rules/"
    "dark_forest_center_tree_profile_feature_rule.json"
)
IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
WORLD_PACK_REFERENCE_FILES = (
    "netease_world_behavior_packs.json",
    "netease_world_resource_packs.json",
    "world_behavior_packs.json",
    "world_resource_packs.json",
)


@dataclass(frozen=True)
class SyncResult:
    copied: int
    removed: int


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class PackSyncProcessLock:
    """A role-neutral, process-owned lock for all pack synchronization."""

    def __init__(
        self,
        path: Path,
        owner_pid: int | None = None,
        process_is_alive: Callable[[int], bool] = _process_is_alive,
    ) -> None:
        self.path = Path(path)
        self.owner_directory = self.path.with_name(self.path.name + ".owner")
        self.owner_pid = int(owner_pid if owner_pid is not None else os.getpid())
        self.process_is_alive = process_is_alive
        self.token = uuid.uuid4().hex
        self.held = False

    def _read(self) -> dict[str, object]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "pack sync lock is unreadable; stop and inspect %s" % self.path
            ) from error
        if not isinstance(document, dict):
            raise RuntimeError(
                "pack sync lock has an invalid shape; stop and inspect %s"
                % self.path
            )
        return document

    def acquire(self, mode: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                self.owner_directory.mkdir()
            except FileExistsError:
                current = self._read()
                current_pid = int(current.get("ownerPid", 0))
                if self.process_is_alive(current_pid):
                    raise RuntimeError(
                        "pack synchronization is already owned by live PID %d; "
                        "wait for it to exit" % current_pid
                    )
                stale_token = str(current.get("token", ""))
                current = self._read()
                if str(current.get("token", "")) != stale_token:
                    continue
                try:
                    self.path.unlink()
                    self.owner_directory.rmdir()
                except (FileNotFoundError, OSError):
                    continue
                continue
            else:
                if self.path.exists():
                    current = self._read()
                    current_pid = int(current.get("ownerPid", 0))
                    if self.process_is_alive(current_pid):
                        self.owner_directory.rmdir()
                        raise RuntimeError(
                            "pack synchronization is already owned by live "
                            "PID %d; wait for it to exit" % current_pid
                        )
                document = {
                    "schemaVersion": 1,
                    "status": "active",
                    "ownerPid": self.owner_pid,
                    "token": self.token,
                    "mode": str(mode),
                    "startedAt": datetime.now(timezone.utc).isoformat(),
                }
                self.path.write_text(
                    json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                self.held = True
                return
        raise RuntimeError(
            "pack synchronization lock changed concurrently; retry after the "
            "current synchronization exits"
        )

    def release(self) -> None:
        if not self.held:
            return
        current = self._read()
        if str(current.get("token", "")) != self.token:
            raise RuntimeError(
                "pack sync lock ownership changed; refusing to remove %s"
                % self.path
            )
        self.path.unlink()
        self.owner_directory.rmdir()
        self.held = False

    @contextmanager
    def hold(self, mode: str) -> Iterator[None]:
        self.acquire(mode)
        try:
            yield
        finally:
            self.release()


def _files(root: Path) -> dict[str, Path]:
    result = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if (
            path.is_file()
            and not IGNORED_PARTS.intersection(relative.parts)
            and path.suffix.lower() not in IGNORED_SUFFIXES
        ):
            result[relative.as_posix()] = path
    return result


def _all_files(root: Path) -> dict[str, Path]:
    result = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path
    return result


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_digest(path: Path) -> str:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_tree_digest(root: Path) -> str:
    entries = {
        relative: _digest(path)
        for relative, path in sorted(_files(Path(root)).items())
    }
    payload = json.dumps(
        entries,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_cold_start_attestation(
    source_root: Path,
    behavior_differences: list[str],
) -> None:
    structure_change = any(
        "structures/tf_slice/ruins/" in difference.replace("\\", "/")
        for difference in behavior_differences
    )
    if not structure_change:
        return
    attestation_path = (
        Path(source_root)
        / "source_locks"
        / "runtime_cold_start_attestation.json"
    )
    if not attestation_path.is_file():
        raise RuntimeError(
            "large structure sync requires a cold-start attestation"
        )
    attestation = json.loads(
        attestation_path.read_text(encoding="utf-8-sig")
    )
    catalog_path = (
        Path(source_root)
        / "TwilightBossSliceB"
        / "structures"
        / "tf_slice"
        / "ruins"
        / "structure_catalog_v1.json"
    )
    if int(attestation.get("schemaVersion", 0)) != 2:
        raise RuntimeError(
            "cold-start attestation schema is stale; a new runtime "
            "verification is required"
        )
    expected = str(attestation.get("catalogSha256", ""))
    actual = _canonical_json_digest(catalog_path)
    if expected != actual:
        raise RuntimeError(
            "cold-start attestation does not match the structure catalog: "
            f"expected={expected} actual={actual}"
        )
    behavior_root = Path(source_root) / "TwilightBossSliceB"
    expected_pack = str(attestation.get("behaviorPackSha256", ""))
    actual_pack = _canonical_tree_digest(behavior_root)
    if expected_pack != actual_pack:
        raise RuntimeError(
            "cold-start attestation does not match the behavior pack: "
            f"expected={expected_pack} actual={actual_pack}"
        )


def diff_pack(source: Path, target: Path) -> list[str]:
    source_files = _files(Path(source))
    # The deployment must be clean, not merely equivalent after applying the
    # source-side ignore rules.  In particular, Python 3 ``__pycache__``
    # artifacts are invalid payload for the NetEase Python runtime and must be
    # reported (and removed by ``mirror_pack``) when already present.
    target_files = _all_files(Path(target))
    differences = []
    for relative in sorted(source_files.keys() | target_files.keys()):
        if relative not in source_files:
            differences.append("extra: %s" % relative)
        elif relative not in target_files:
            differences.append("missing: %s" % relative)
        elif _digest(source_files[relative]) != _digest(target_files[relative]):
            differences.append("changed: %s" % relative)
    return sorted(differences)


def mirror_pack(
    source: Path,
    target: Path,
    allow_large_sync: bool = False,
) -> SyncResult:
    source = Path(source).resolve()
    target = Path(target).resolve()
    if not source.is_dir():
        raise ValueError("Source pack does not exist: %s" % source)
    if source == target or source in target.parents:
        raise ValueError("Target must be outside the source pack: %s" % target)

    pending_differences = diff_pack(source, target)
    if (
        len(pending_differences) > MAX_UNREVIEWED_SYNC_CHANGES
        and not allow_large_sync
    ):
        preview = "; ".join(pending_differences[:8])
        raise RuntimeError(
            "large sync requires explicit review: "
            f"{len(pending_differences)} changes exceed "
            f"{MAX_UNREVIEWED_SYNC_CHANGES}; {preview}"
        )

    target.mkdir(parents=True, exist_ok=True)
    source_files = _files(source)
    target_files = _all_files(target)
    removed = 0
    for relative in sorted(target_files.keys() - source_files.keys()):
        target_files[relative].unlink()
        removed += 1

    copied = 0
    for relative, source_path in sorted(source_files.items()):
        target_path = target / Path(relative)
        if target_path.is_file() and _digest(source_path) == _digest(target_path):
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied += 1

    for directory, _, _ in os.walk(target, topdown=False):
        path = Path(directory)
        if path != target and not any(path.iterdir()):
            path.rmdir()

    differences = diff_pack(source, target)
    if differences:
        raise RuntimeError(
            "Pack verification failed for %s: %s"
            % (target, "; ".join(differences))
        )
    return SyncResult(copied=copied, removed=removed)


def _selected_addon_targets(
    target_root: Path,
    selections: list[str],
    target_pack_roots: dict[str, Path] | None = None,
) -> list[tuple[str, str, Path]]:
    target_root = Path(target_root).resolve()
    selected = {}
    for selection in selections:
        pack_name, separator, relative_text = str(selection).partition(":")
        if not separator or pack_name not in PACK_NAMES:
            raise ValueError("Unknown pack in scoped sync: %s" % selection)
        relative_text = relative_text.replace("\\", "/")
        relative = PurePosixPath(relative_text)
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or ":" in relative_text
        ):
            raise ValueError(
                "Scoped sync requires a relative pack path: %s" % selection
            )

        target_pack = (
            Path(target_pack_roots[pack_name]).resolve()
            if target_pack_roots is not None
            else (target_root / pack_name).resolve()
        )
        target_path = (
            target_pack / Path(*relative.parts)
        ).resolve()
        if target_pack not in target_path.parents:
            raise ValueError(
                "Scoped sync requires a relative pack path: %s" % selection
            )
        key = "%s:%s" % (pack_name, relative.as_posix())
        selected[key] = (
            pack_name,
            relative.as_posix(),
            target_path,
        )
    return [selected[key] for key in sorted(selected)]


def _selected_addon_files(
    source_root: Path,
    target_root: Path,
    selections: list[str],
    target_pack_roots: dict[str, Path] | None = None,
) -> list[tuple[str, str, Path, Path]]:
    source_root = Path(source_root).resolve()
    targets = _selected_addon_targets(
        target_root,
        selections,
        target_pack_roots=target_pack_roots,
    )
    selected = []
    for pack_name, relative, target_path in targets:
        source_pack = (source_root / pack_name).resolve()
        source_path = (source_pack / Path(relative)).resolve()
        if source_pack not in source_path.parents:
            raise ValueError(
                "Scoped sync requires a relative pack path: %s:%s"
                % (pack_name, relative)
            )
        if not source_path.is_file():
            raise ValueError(
                "Source file does not exist for scoped sync: %s"
                % source_path
            )
        selected.append((pack_name, relative, source_path, target_path))
    return selected


def _validate_selected_source_files(
    selected: list[tuple[str, str, Path, Path]],
) -> None:
    for pack_name, relative, source_path, _ in selected:
        if source_path.suffix.lower() != ".json":
            continue
        try:
            document = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                "Invalid selected JSON file: %s" % source_path
            ) from error
        if (
            pack_name == "TwilightBossSliceB"
            and relative == CENTER_TREE_RULE_RELATIVE
        ):
            body = (
                document.get("minecraft:feature_rules", {})
                if isinstance(document, dict)
                else {}
            )
            description = body.get("description", {})
            distribution = body.get("distribution", {})
            iterations = distribution.get("iterations")
            expected_feature = (
                "tf_slice:dark_forest_center_"
                "tree_ground_search_feature"
            )
            if (
                type(iterations) is not int
                or iterations != 16
                or description.get("places_feature") != expected_feature
            ):
                raise ValueError(
                    "Dark Forest center tree rule must not contain a "
                    "spatial exclusion: %s" % source_path
                )
        if not relative.startswith("netease_blocks/"):
            continue
        if not isinstance(document, dict):
            raise ValueError(
                "Invalid selected block document: %s" % source_path
            )
        block = document.get("minecraft:block")
        description = block.get("description") if isinstance(block, dict) else None
        identifier = (
            description.get("identifier")
            if isinstance(description, dict)
            else None
        )
        if not isinstance(identifier, str) or ":" not in identifier:
            raise ValueError(
                "Invalid selected block document: %s" % source_path
            )


def _mirror_selected_rows(
    source_root: Path,
    selected: list[tuple[str, str, Path, Path]],
    removals: list[tuple[str, str, Path]] | None = None,
    allow_large_sync: bool = False,
) -> dict[str, SyncResult]:
    removals = list(removals or ())
    if not selected and not removals:
        raise ValueError("Scoped sync requires at least one selected file")
    copied_keys = {"%s:%s" % (row[0], row[1]) for row in selected}
    removal_keys = {"%s:%s" % (row[0], row[1]) for row in removals}
    overlap = sorted(copied_keys & removal_keys)
    if overlap:
        raise ValueError(
            "Scoped sync cannot copy and remove the same file: "
            + ", ".join(overlap)
        )
    _validate_selected_source_files(selected)
    if (
        len(selected) + len(removals) > MAX_UNREVIEWED_SYNC_CHANGES
        and not allow_large_sync
    ):
        raise RuntimeError(
            "large sync requires explicit review: "
            f"{len(selected) + len(removals)} selected files exceed "
            f"{MAX_UNREVIEWED_SYNC_CHANGES}"
        )

    behavior_differences = [
        "changed: %s" % relative
        for pack_name, relative, _, _ in selected
        if pack_name == "TwilightBossSliceB"
    ] + [
        "removed: %s" % relative
        for pack_name, relative, _ in removals
        if pack_name == "TwilightBossSliceB"
    ]
    if any(
        "structures/tf_slice/ruins/" in difference
        for difference in behavior_differences
    ):
        _require_cold_start_attestation(
            Path(source_root),
            behavior_differences,
        )

    copied = {pack_name: 0 for pack_name in PACK_NAMES}
    for pack_name, relative, source_path, target_path in selected:
        if (
            target_path.is_file()
            and _digest(source_path) == _digest(target_path)
        ):
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = target_path.with_name(
            target_path.name + ".scoped-sync-tmp"
        )
        if temporary.exists():
            raise RuntimeError(
                "Scoped sync temporary path already exists: %s" % temporary
            )
        try:
            shutil.copy2(source_path, temporary)
            if _digest(source_path) != _digest(temporary):
                raise RuntimeError(
                    "Scoped sync temporary verification failed: %s"
                    % relative
                )
            os.replace(str(temporary), str(target_path))
        finally:
            if temporary.exists():
                temporary.unlink()
        if _digest(source_path) != _digest(target_path):
            raise RuntimeError(
                "Scoped sync verification failed: %s" % relative
            )
        copied[pack_name] += 1

    removed = {pack_name: 0 for pack_name in PACK_NAMES}
    for pack_name, relative, target_path in removals:
        if target_path.is_dir():
            raise RuntimeError(
                "Scoped sync removal target is a directory: %s" % target_path
            )
        if target_path.is_file():
            target_path.unlink()
            removed[pack_name] += 1
        if target_path.exists():
            raise RuntimeError(
                "Scoped sync removal verification failed: %s" % relative
            )

    touched_packs = {row[0] for row in selected} | {
        row[0] for row in removals
    }
    return {
        pack_name: SyncResult(
            copied=copied[pack_name],
            removed=removed[pack_name],
        )
        for pack_name in PACK_NAMES
        if pack_name in touched_packs
    }


def mirror_selected_addon_files(
    source_root: Path,
    target_root: Path,
    selections: list[str],
    removals: list[str] | None = None,
    allow_large_sync: bool = False,
) -> dict[str, SyncResult]:
    """Atomically copy only explicitly selected AddOn files."""
    selected = _selected_addon_files(
        source_root,
        target_root,
        selections,
    )
    removal_rows = _selected_addon_targets(
        target_root,
        list(removals or ()),
    )
    return _mirror_selected_rows(
        source_root,
        selected,
        removals=removal_rows,
        allow_large_sync=allow_large_sync,
    )


def mirror_selected_runtime_addon_files(
    source_root: Path,
    behavior_root: Path,
    resource_root: Path,
    selections: list[str],
    removals: list[str] | None = None,
    allow_large_sync: bool = False,
) -> dict[str, SyncResult]:
    """Atomically copy selected files into separate runtime pack roots."""
    behavior_root = Path(behavior_root).resolve()
    resource_root = Path(resource_root).resolve()
    target_pack_roots = {
        "TwilightBossSliceB": behavior_root / "TwilightBossSliceB",
        "TwilightBossSliceR": resource_root / "TwilightBossSliceR",
    }
    selected = _selected_addon_files(
        source_root,
        behavior_root,
        selections,
        target_pack_roots=target_pack_roots,
    )
    removal_rows = _selected_addon_targets(
        behavior_root,
        list(removals or ()),
        target_pack_roots=target_pack_roots,
    )
    return _mirror_selected_rows(
        source_root,
        selected,
        removals=removal_rows,
        allow_large_sync=allow_large_sync,
    )


def mirror_selected_world_addon_files(
    source_root: Path,
    world_root: Path,
    selections: list[str],
    removals: list[str] | None = None,
    allow_large_sync: bool = False,
) -> dict[str, SyncResult]:
    """Atomically copy selected files into an embedded world's two packs."""
    world_root = Path(world_root).resolve()
    target_pack_roots = {
        "TwilightBossSliceB": (
            world_root / "behavior_packs" / "TwilightBossSliceB"
        ),
        "TwilightBossSliceR": (
            world_root / "resource_packs" / "TwilightBossSliceR"
        ),
    }
    selected = _selected_addon_files(
        source_root,
        world_root,
        selections,
        target_pack_roots=target_pack_roots,
    )
    removal_rows = _selected_addon_targets(
        world_root,
        list(removals or ()),
        target_pack_roots=target_pack_roots,
    )
    results = _mirror_selected_rows(
        source_root,
        selected,
        removals=removal_rows,
        allow_large_sync=allow_large_sync,
    )
    _sync_world_pack_references(source_root, world_root)
    return results


def mirror_addon(
    source_root: Path,
    behavior_root: Path,
    resource_root: Path,
    allow_large_sync: bool = False,
    require_cold_start_attestation: bool = True,
    allow_source_bound_target: bool = False,
) -> dict[str, SyncResult]:
    source_root = Path(source_root)
    destinations = {
        "TwilightBossSliceB": Path(behavior_root) / "TwilightBossSliceB",
        "TwilightBossSliceR": Path(resource_root) / "TwilightBossSliceR",
    }
    behavior_differences = diff_pack(
        source_root / "TwilightBossSliceB",
        destinations["TwilightBossSliceB"],
    )
    if (
        allow_large_sync
        and len(behavior_differences) > MAX_UNREVIEWED_SYNC_CHANGES
        and require_cold_start_attestation
    ):
        _require_cold_start_attestation(
            source_root,
            behavior_differences,
        )
    results = {}
    for pack_name in PACK_NAMES:
        source_pack = (source_root / pack_name).resolve()
        target_pack = destinations[pack_name].resolve()
        if allow_source_bound_target and source_pack == target_pack:
            results[pack_name] = SyncResult(copied=0, removed=0)
            continue
        results[pack_name] = mirror_pack(
            source_pack,
            target_pack,
            allow_large_sync=allow_large_sync,
        )
    return results


def _source_pack_versions(source_root: Path) -> dict[str, list[int]]:
    versions = {}
    for pack_name in PACK_NAMES:
        manifest_path = Path(source_root) / pack_name / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        header = manifest.get("header", {})
        pack_id = header.get("uuid")
        version = header.get("version")
        if pack_id and isinstance(version, list):
            versions[str(pack_id)] = [int(value) for value in version]
    return versions


def _sync_world_pack_references(
    source_root: Path,
    world_root: Path,
) -> int:
    versions = _source_pack_versions(source_root)
    if not versions:
        return 0
    expected_by_file_kind = {}
    for file_kind, pack_name in (
        ("behavior", "TwilightBossSliceB"),
        ("resource", "TwilightBossSliceR"),
    ):
        manifest_path = Path(source_root) / pack_name / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        header = manifest.get("header", {})
        pack_id = str(header.get("uuid", ""))
        version = header.get("version")
        if pack_id and isinstance(version, list):
            expected_by_file_kind[file_kind] = {
                "pack_id": pack_id,
                "version": [int(value) for value in version],
            }
    changed = 0
    for file_name in WORLD_PACK_REFERENCE_FILES:
        path = Path(world_root) / file_name
        if not path.is_file():
            continue
        references = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(references, list):
            raise ValueError(
                "World pack reference file must contain a list: %s" % path
            )
        file_changed = False
        for reference in references:
            if not isinstance(reference, dict):
                continue
            pack_id = str(reference.get("pack_id", ""))
            file_kind = "behavior" if "behavior" in file_name else "resource"
            expected = expected_by_file_kind.get(file_kind)
            if len(references) == 1 and pack_id not in versions and expected:
                reference["pack_id"] = expected["pack_id"]
                reference["version"] = list(expected["version"])
                changed += 1
                file_changed = True
                continue
            version = versions.get(pack_id)
            if version is None or reference.get("version") == version:
                continue
            reference["version"] = list(version)
            changed += 1
            file_changed = True
        if file_changed:
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(
                json.dumps(references, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(str(temporary), str(path))
    return changed


def mirror_world_addon(
    source_root: Path,
    world_root: Path,
    allow_large_sync: bool = False,
    require_cold_start_attestation: bool = True,
    allow_source_bound_target: bool = False,
) -> dict[str, SyncResult]:
    world_root = Path(world_root)
    results = mirror_addon(
        source_root,
        world_root / "behavior_packs",
        world_root / "resource_packs",
        allow_large_sync=allow_large_sync,
        require_cold_start_attestation=require_cold_start_attestation,
        allow_source_bound_target=allow_source_bound_target,
    )
    _sync_world_pack_references(source_root, world_root)
    return results


def _validate_source() -> None:
    validator = ROOT / "tools" / "validate_slice.py"
    result = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--allow-model-candidates",
            "--no-package",
        ],
        cwd=str(ROOT),
    )
    if result.returncode:
        raise SystemExit(result.returncode)


def ensure_safe_deployment_modes(
    target_roots: list[Path],
    behavior_root: Path | None,
    resource_root: Path | None,
    world_roots: list[Path],
    allow_multiple: bool = False,
) -> None:
    """Reject accidental deployment of one UUID into multiple active stacks."""
    active_modes = int(bool(target_roots)) + int(
        bool(behavior_root or resource_root)
    ) + int(bool(world_roots))
    if active_modes > 1 and not allow_multiple:
        raise ValueError(
            "multiple deployment modes can create a duplicate pack stack; "
            "use exactly one mode or pass --allow-multiple-deployment-modes "
            "after verifying the targets cannot be loaded together"
        )


def _is_registered_cold_start_world(world_root: Path) -> bool:
    """Recognize a separately registered MC Studio cold-start world."""
    world_root = Path(world_root).resolve()
    config_path = world_root / "work.mcscfg"
    studio_path = world_root / "studio.json"
    if not config_path.is_file() or not studio_path.is_file():
        return False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        studio = json.loads(studio_path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    uid = str(config.get("UID", ""))
    name = str(config.get("Name", ""))
    if not re.fullmatch(r"[0-9a-fA-F]{32}", uid):
        return False
    if "cold start" not in name.casefold() and "冷启动" not in name:
        return False
    try:
        saved_path = Path(str(studio.get("SaveBackMapPath", ""))).resolve()
    except (OSError, ValueError):
        return False
    return (
        world_root.name.casefold() == uid.casefold()
        and str(config.get("EditMapUID", "")).casefold() == uid.casefold()
        and str(config.get("TestMapUID", "")).casefold() == uid.casefold()
        and str(studio.get("Id", "")).casefold() == uid.casefold()
        and studio.get("IsMap") is True
        and saved_path == world_root
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the source AddOn, mirror both packs, remove stale files, "
            "and verify every copied file by SHA-256."
        )
    )
    parser.add_argument(
        "--target-root",
        action="append",
        type=Path,
        default=[],
        help="MC Studio directory that directly contains both AddOn packs",
    )
    parser.add_argument(
        "--behavior-root",
        type=Path,
        help="Runtime behavior_packs directory",
    )
    parser.add_argument(
        "--resource-root",
        type=Path,
        help="Runtime resource_packs directory",
    )
    parser.add_argument(
        "--world-root",
        action="append",
        type=Path,
        default=[],
        help=(
            "Minecraft world directory containing embedded behavior_packs "
            "and resource_packs directories"
        ),
    )
    parser.add_argument(
        "--allow-multiple-deployment-modes",
        action="store_true",
        help=(
            "explicitly allow Studio, global runtime, and embedded-world "
            "destinations in one invocation"
        ),
    )
    parser.add_argument(
        "--allow-large-sync",
        action="store_true",
        help=(
            "confirm that a reviewed deployment may change more than "
            f"{MAX_UNREVIEWED_SYNC_CHANGES} files in one pack"
        ),
    )
    parser.add_argument(
        "--acknowledge-full-mirror",
        action="store_true",
        help=(
            "confirm that a non-scoped sync may copy changed files and remove "
            "target files that are absent from the source packs"
        ),
    )
    parser.add_argument(
        "--prepare-cold-start-candidate",
        action="store_true",
        help=(
            "prepare a full-mirror candidate only inside this repository's "
            "runtime_backups or tmp directory; the candidate is used to "
            "produce a new cold-start attestation"
        ),
    )
    parser.add_argument(
        "--include-file",
        action="append",
        default=[],
        metavar="PACK:RELATIVE_PATH",
        help=(
            "copy only one explicitly selected file; repeat for additional "
            "files and use with exactly one target, runtime, or world mode"
        ),
    )
    parser.add_argument(
        "--remove-file",
        action="append",
        default=[],
        metavar="PACK:RELATIVE_PATH",
        help=(
            "remove only one explicitly selected target file; repeat for "
            "additional files and use with exactly one destination mode"
        ),
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help=(
            "alternate AddOn source for scoped sync; must resolve inside "
            "this repository's tmp or deployment_payloads directory"
        ),
    )
    args = parser.parse_args()
    if bool(args.behavior_root) != bool(args.resource_root):
        parser.error("--behavior-root and --resource-root must be used together")
    if not args.target_root and not args.behavior_root and not args.world_root:
        parser.error("at least one synchronization destination is required")
    scoped = bool(args.include_file or args.remove_file)
    if scoped and args.acknowledge_full_mirror:
        parser.error(
            "--acknowledge-full-mirror cannot be combined with scoped files"
        )
    if not scoped and not args.acknowledge_full_mirror:
        parser.error(
            "full mirror synchronization requires --acknowledge-full-mirror; "
            "use --include-file for a scoped synchronization"
        )
    if scoped:
        scoped_modes = (
            len(args.target_root)
            + len(args.world_root)
            + int(bool(args.behavior_root))
        )
        if scoped_modes != 1:
            parser.error(
                "scoped files require exactly one --target-root, "
                "runtime root pair, or --world-root"
            )
    elif args.source_root:
        parser.error("--source-root is supported only with scoped files")
    if args.prepare_cold_start_candidate:
        if scoped or args.source_root or args.behavior_root:
            parser.error(
                "--prepare-cold-start-candidate supports only full-mirror "
                "--target-root and --world-root destinations"
            )
        if not args.allow_large_sync:
            parser.error(
                "--prepare-cold-start-candidate requires --allow-large-sync"
            )
        allowed_candidate_roots = (
            (ROOT / "runtime_backups").resolve(),
            (ROOT / "tmp").resolve(),
        )
        candidate_destinations = [
            (path.resolve(), False) for path in args.target_root
        ] + [
            (path.resolve(), True) for path in args.world_root
        ]
        for destination, is_world in candidate_destinations:
            inside_repository_candidate = any(
                destination == allowed
                or allowed in destination.parents
                for allowed in allowed_candidate_roots
            )
            if not inside_repository_candidate and not (
                is_world and _is_registered_cold_start_world(destination)
            ):
                parser.error(
                    "cold-start candidate destinations must stay inside "
                    "runtime_backups or tmp, or be a separately registered "
                    "MC Studio Cold Start world"
                )
    try:
        ensure_safe_deployment_modes(
            args.target_root,
            args.behavior_root,
            args.resource_root,
            args.world_root,
            args.allow_multiple_deployment_modes,
        )
    except ValueError as error:
        parser.error(str(error))
    scoped_source_root = ROOT
    if args.source_root:
        scoped_source_root = args.source_root.resolve()
        allowed_roots = (
            (ROOT / "tmp").resolve(),
            (ROOT / "deployment_payloads").resolve(),
        )
        if not any(
            scoped_source_root == allowed
            or allowed in scoped_source_root.parents
            for allowed in allowed_roots
        ):
            parser.error(
                "--source-root must stay inside tmp or deployment_payloads"
            )
        for pack_name in PACK_NAMES:
            if not (scoped_source_root / pack_name).is_dir():
                parser.error(
                    "--source-root is missing pack: %s" % pack_name
                )
    mode = (
        "scoped"
        if scoped
        else "cold-start-candidate"
        if args.prepare_cold_start_candidate
        else "full-mirror"
    )
    print(
        "MODE: %s"
        % (
            "SCOPED"
            if scoped
            else "COLD_START_CANDIDATE"
            if args.prepare_cold_start_candidate
            else "FULL_MIRROR"
        )
    )
    lock = PackSyncProcessLock(
        ROOT / "source_locks" / "pack_sync_process_lock.json"
    )
    with lock.hold(mode):
        if not args.include_file:
            _validate_source()
        for target_root in args.target_root:
            target_root = target_root.resolve()
            print("TARGET: %s" % target_root)
            if scoped:
                results = mirror_selected_addon_files(
                    scoped_source_root,
                    target_root,
                    args.include_file,
                    removals=args.remove_file,
                    allow_large_sync=args.allow_large_sync,
                )
            else:
                results = mirror_addon(
                    ROOT,
                    target_root,
                    target_root,
                    allow_large_sync=args.allow_large_sync,
                    require_cold_start_attestation=(
                        not args.prepare_cold_start_candidate
                    ),
                    allow_source_bound_target=(
                        args.prepare_cold_start_candidate
                    ),
                )
            for pack_name, result in results.items():
                print(
                    "SYNCED: %s copied=%d removed=%d"
                    % (pack_name, result.copied, result.removed)
                )
        if args.behavior_root:
            print(
                "RUNTIME: behavior=%s resource=%s"
                % (args.behavior_root.resolve(), args.resource_root.resolve())
            )
            if scoped:
                results = mirror_selected_runtime_addon_files(
                    scoped_source_root,
                    args.behavior_root.resolve(),
                    args.resource_root.resolve(),
                    args.include_file,
                    removals=args.remove_file,
                    allow_large_sync=args.allow_large_sync,
                )
            else:
                results = mirror_addon(
                    ROOT,
                    args.behavior_root.resolve(),
                    args.resource_root.resolve(),
                    allow_large_sync=args.allow_large_sync,
                )
            for pack_name, result in results.items():
                print(
                    "SYNCED: %s copied=%d removed=%d"
                    % (pack_name, result.copied, result.removed)
                )
        for world_root in args.world_root:
            world_root = world_root.resolve()
            print("WORLD: %s" % world_root)
            if scoped:
                results = mirror_selected_world_addon_files(
                    scoped_source_root,
                    world_root,
                    args.include_file,
                    removals=args.remove_file,
                    allow_large_sync=args.allow_large_sync,
                )
            else:
                results = mirror_world_addon(
                    ROOT,
                    world_root,
                    allow_large_sync=args.allow_large_sync,
                    require_cold_start_attestation=(
                        not args.prepare_cold_start_candidate
                    ),
                    allow_source_bound_target=(
                        args.prepare_cold_start_candidate
                    ),
                )
            for pack_name, result in results.items():
                print(
                    "SYNCED: %s copied=%d removed=%d"
                    % (pack_name, result.copied, result.removed)
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
