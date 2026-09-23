"""Exact-byte deduplication helpers for generated Twilight ruin structures."""

from __future__ import print_function

import filecmp
import hashlib
import re

try:
    from pathlib import Path
except ImportError:  # pragma: no cover - build tooling requires Python 3
    Path = None


RUIN_STRUCTURE_REFERENCE_PREFIX = "tf_slice/ruins/"
RUIN_STRUCTURE_LITERAL_PATTERN = re.compile(
    r"tf_slice(?::|/)ruins/[A-Za-z0-9_./-]+"
)


def resolve_ruin_structure_reference(reference, aliases=None):
    """Resolve one logical ruin reference to an existing canonical file."""
    current = str(reference)
    mapping = aliases if isinstance(aliases, dict) else {}
    visited = set()
    while current in mapping:
        if current in visited:
            raise ValueError(
                "ruin structure alias cycle at %s" % current
            )
        visited.add(current)
        current = str(mapping[current])
    if current in visited:
        raise ValueError("ruin structure alias cycle at %s" % current)
    if not current.startswith(RUIN_STRUCTURE_REFERENCE_PREFIX):
        raise ValueError("invalid ruin structure reference: %s" % current)
    return current


def _ruin_reference_for_path(output_root, path):
    relative = path.relative_to(output_root).with_suffix("").as_posix()
    return RUIN_STRUCTURE_REFERENCE_PREFIX + relative


def _ruin_structure_domain(reference):
    relative = reference[len(RUIN_STRUCTURE_REFERENCE_PREFIX) :]
    parts = relative.split("/")
    if parts[0] == "surface_native" and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]


def collect_external_ruin_structure_references(bp_root, output_root):
    """Find literal engine references that cannot use the runtime alias map."""
    bp_root = Path(bp_root)
    output_root = Path(output_root)
    generated_runtime_catalog = (
        bp_root / "TwilightBossSlice" / "ruin_catalog_data.py"
    )
    references = set()
    text_suffixes = frozenset((".json", ".py", ".mcfunction"))
    for path in bp_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        if path == generated_runtime_catalog:
            continue
        try:
            path.relative_to(output_root)
            continue
        except ValueError:
            pass
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for match in RUIN_STRUCTURE_LITERAL_PATTERN.findall(content):
            reference = match.replace("tf_slice:ruins/", "tf_slice/ruins/", 1)
            if reference.endswith(".mcstructure"):
                reference = reference[: -len(".mcstructure")]
            relative = reference[len(RUIN_STRUCTURE_REFERENCE_PREFIX) :]
            target = output_root / (relative + ".mcstructure")
            if target.is_file():
                references.add(reference)
    return references


def _partition_exact_structure_files(paths):
    partitions = []
    for path in sorted(paths, key=lambda value: value.as_posix()):
        for representative, members in partitions:
            if filecmp.cmp(str(path), str(representative), shallow=False):
                members.append(path)
                break
        else:
            partitions.append((path, [path]))
    return [members for _representative, members in partitions]


def plan_ruin_structure_deduplication(output_root, pinned_references=None):
    """Plan exact deduplication without modifying the generated structure set."""
    output_root = Path(output_root)
    pinned_references = set(pinned_references or ())
    files = sorted(output_root.rglob("*.mcstructure"))
    by_digest = {}
    for path in files:
        reference = _ruin_reference_for_path(output_root, path)
        domain = _ruin_structure_domain(reference)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        by_digest.setdefault(
            (domain, path.stat().st_size, digest),
            [],
        ).append(path)

    aliases = {}
    removal_paths = []
    removed_bytes = 0
    duplicate_groups = 0
    retained_pinned = set()
    for paths in by_digest.values():
        if len(paths) < 2:
            reference = _ruin_reference_for_path(output_root, paths[0])
            if reference in pinned_references:
                retained_pinned.add(reference)
            continue
        for exact_group in _partition_exact_structure_files(paths):
            references = dict(
                (
                    _ruin_reference_for_path(output_root, path),
                    path,
                )
                for path in exact_group
            )
            pinned = sorted(set(references).intersection(pinned_references))
            retained_pinned.update(pinned)
            if len(exact_group) < 2:
                continue
            duplicate_groups += 1
            canonical = pinned[0] if pinned else sorted(references)[0]
            retained = set(pinned or (canonical,))
            for reference in sorted(references):
                if reference in retained:
                    continue
                path = references[reference]
                removed_bytes += path.stat().st_size
                aliases[reference] = canonical
                removal_paths.append(path)

    statistics = {
        "inputFileCount": len(files),
        "canonicalFileCount": len(files) - len(aliases),
        "removedFileCount": len(aliases),
        "removedUncompressedBytes": removed_bytes,
        "duplicateGroupCount": duplicate_groups,
        "retainedPinnedFileCount": len(retained_pinned),
    }
    return dict(sorted(aliases.items())), removal_paths, statistics


def deduplicate_ruin_structure_files(output_root, pinned_references=None):
    """Remove exact duplicate ruin files while retaining engine-pinned names."""
    output_root = Path(output_root)
    aliases, removal_paths, statistics = plan_ruin_structure_deduplication(
        output_root,
        pinned_references,
    )
    for path in removal_paths:
        path.unlink()

    directories = sorted(
        (path for path in output_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass
    return aliases, statistics
