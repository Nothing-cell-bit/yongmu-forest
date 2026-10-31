"""Retire superseded pack PNGs while keeping immutable development originals."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image

ARCHIVE = Path("resource_art/retired_runtime_pngs")
# Additional reviewed private legacy resources: these are not engine-default
# names. Rain now uses native dimension-local weather; the current Phantom
# renderer uses separate skeleton/armor art; no current banner consumer exists.
LEGACY_ORPHANS = {
    "textures/entity/tf_slice/banner/lich.png": "3294924290b4e4c5aca08eafc99dd7c05e1c39a28e651140a48f89e019da9d14",
    "textures/entity/tf_slice/knight_phantom.png": "bc2a8c916dfd316cca716311856813749a563625442b022eb26f2b5b45ea7e34",
    "textures/particle/ur_ghast_rain.png": "acf55dab62918a2dc54cf439de31c067334c8d8cff8b3a5cc0351824bd408c38",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original_texture(path, project_root):
    """Resolve a removed runtime baseline only through the exact reviewed ledger."""
    path, root = Path(path), Path(project_root)
    if path.is_file():
        return path
    try:
        relative = path.resolve().relative_to((root / "TwilightBossSliceR").resolve()).as_posix()
    except ValueError:
        return path
    ledger = root / ARCHIVE / "manifest.json"
    if not ledger.is_file():
        return path
    entry = json.loads(ledger.read_text(encoding="utf-8"))["files"].get(relative)
    if not entry:
        return path
    archived = (root / entry["archive"]).resolve()
    if (root / ARCHIVE).resolve() not in archived.parents:
        raise ValueError("Archived texture path escapes development bank")
    if digest(archived) != entry["sha256"]:
        raise ValueError("Archived texture hash mismatch: " + relative)
    return archived


def runtime_references(root):
    exact, prefixes, errors = set(), set(), []

    def strings(value):
        if isinstance(value, str):
            if value.startswith("textures/"):
                path = value.removesuffix(".png")
                if any(character in path for character in ("%", "{", "*")):
                    prefixes.add(re.split(r"[%{*]", path, 1)[0])
                elif path.endswith("/"):
                    prefixes.add(path)
                else:
                    exact.add(path)
        elif isinstance(value, dict):
            for child in value.values():
                strings(child)
        elif isinstance(value, list):
            for child in value:
                strings(child)

    for pack in ("TwilightBossSliceB", "TwilightBossSliceR"):
        for path in (Path(root) / pack).rglob("*"):
            if path.suffix.lower() not in (".json", ".py", ".material", ".materials") or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
                if path.suffix.lower() == ".json":
                    strings(json.loads(text))
                else:
                    for match in re.finditer(r'''(["'])(textures/[^"'\r\n]*)\1''', text):
                        strings(match.group(2))
            except (ValueError, UnicodeError, OSError) as error:
                errors.append({"file": str(path), "error": str(error)})
    return exact, prefixes, errors


def replacement_routes(root):
    root = Path(root)
    routes = {}

    def add(source, replacement):
        if source and replacement and source != replacement and not source.startswith("textures/tf_beautified/"):
            routes.setdefault(source, set()).add(replacement)

    for bank in ("block_beautification", "remaining_visuals"):
        path = root / "resource_art" / bank / "v1/manifest.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("enabled"):
            for entry in data["entries"]:
                if entry.get("source_kind") not in ("project", "project-item"):
                    continue
                replacement = entry.get("runtime_path", "textures/tf_beautified/" + entry["output_relative"].removesuffix(".png"))
                add(entry["source_runtime_path"], replacement)
    path = root / "resource_art/entity_beautification/v1/manifest.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("enabled"):
            for entry in data["entities"].values():
                old = entry.get("source_textures", {"default": entry.get("source_texture")})
                new = entry.get("textures", {"default": entry.get("texture")})
                for alias, source in old.items():
                    add(source, new.get(alias))
    return routes


def is_retired_runtime_png(path, project_root):
    path, root = Path(path), Path(project_root)
    try:
        relative = path.resolve().relative_to((root / "TwilightBossSliceR").resolve()).as_posix()
    except ValueError:
        return False
    ledger = root / ARCHIVE / "manifest.json"
    return ledger.is_file() and relative in json.loads(ledger.read_text(encoding="utf-8"))["files"]


def plan(root):
    root = Path(root).resolve()
    rp = root / "TwilightBossSliceR"
    exact, prefixes, errors = runtime_references(root)
    selected, retained = {}, []
    for source, replacements in sorted(replacement_routes(root).items()):
        path = (rp / (source + ".png")).resolve()
        if rp.resolve() not in path.parents:
            raise ValueError("Texture selection escapes the resource pack")
        if not path.is_file():
            continue
        reason = None
        if source in exact or any(source.startswith(prefix) for prefix in prefixes):
            reason = "current exact/dynamic-prefix reference"
        elif source.startswith("textures/environment/"):
            reason = "engine environment resources require separate native-loader review"
        else:
            for replacement in replacements:
                target = (rp / (replacement + ".png")).resolve()
                if rp.resolve() not in target.parents or not target.is_file():
                    reason = "replacement missing or outside pack"
                    break
                with Image.open(path) as original, Image.open(target) as enhanced:
                    if original.size != enhanced.size:
                        reason = "replacement dimensions differ"
                        break
        if reason:
            retained.append({"path": path.relative_to(rp).as_posix(), "reason": reason})
        else:
            relative = path.relative_to(rp).as_posix()
            selected[relative] = {"sha256": digest(path), "archive": (ARCHIVE / "originals" / relative).as_posix(), "replacements": sorted(replacements), "replacement_sha256": {replacement: digest(rp / (replacement + ".png")) for replacement in sorted(replacements)}}
    for relative, expected in LEGACY_ORPHANS.items():
        path = (rp / relative).resolve()
        if rp.resolve() not in path.parents:
            raise ValueError("Legacy PNG selection escapes resource pack")
        if not path.exists():
            continue
        runtime = relative.removesuffix(".png")
        if runtime in exact or any(runtime.startswith(prefix) for prefix in prefixes) or digest(path) != expected:
            retained.append({"path": relative, "reason": "legacy file referenced or changed since review"})
        else:
            selected[relative] = {"sha256": expected, "archive": (ARCHIVE / "originals" / relative).as_posix(), "replacements": [], "replacement_sha256": {}, "reason": "explicitly reviewed legacy orphan"}
    return {"schema_version": 1, "files": selected, "retained": retained, "errors": errors}


def apply(root, proposed):
    root = Path(root).resolve()
    current = plan(root)
    if current != proposed or current["errors"]:
        raise ValueError("Cleanup inputs changed or reference scan failed")
    ledger_path = root / ARCHIVE / "manifest.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"schema_version": 1, "files": {}}
    # Preserve every baseline before removing any runtime file.
    for relative, entry in current["files"].items():
        source = (root / "TwilightBossSliceR" / relative).resolve()
        archived = (root / entry["archive"]).resolve()
        if (root / ARCHIVE).resolve() not in archived.parents:
            raise ValueError("Archive path escapes the development bank")
        archived.parent.mkdir(parents=True, exist_ok=True)
        if archived.exists() and digest(archived) != entry["sha256"]:
            raise ValueError("Existing baseline differs: " + relative)
        if not archived.exists():
            archived.write_bytes(source.read_bytes())
        if digest(archived) != entry["sha256"]:
            raise ValueError("Archive verification failed")
    ledger["files"].update(current["files"])
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for relative, entry in current["files"].items():
        source = (root / "TwilightBossSliceR" / relative).resolve()
        if (root / "TwilightBossSliceR").resolve() not in source.parents or digest(source) != entry["sha256"]:
            raise ValueError("Runtime texture changed before deletion")
        source.unlink()
    return ledger


def check(root):
    root = Path(root)
    path = root / ARCHIVE / "manifest.json"
    if not path.exists():
        return []
    exact, prefixes, errors = runtime_references(root)
    for relative, entry in json.loads(path.read_text(encoding="utf-8"))["files"].items():
        runtime = root / "TwilightBossSliceR" / relative
        if runtime.exists():
            errors.append({"file": relative, "error": "retired PNG was restored to runtime pack"})
        elif relative.removesuffix(".png") in exact or any(relative.removesuffix(".png").startswith(prefix) for prefix in prefixes):
            errors.append({"file": relative, "error": "runtime reference to retired PNG"})
        try:
            original_texture(runtime, root)
        except (OSError, ValueError) as error:
            errors.append({"file": relative, "error": str(error)})
        for replacement, expected in entry.get("replacement_sha256", {}).items():
            material = root / "TwilightBossSliceR" / (replacement + ".png")
            if not material.is_file():
                errors.append({"file": relative, "error": "replacement no longer exists: " + replacement})
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.check:
        errors = check(args.root)
        print(json.dumps({"errors": errors}, ensure_ascii=False))
        return bool(errors)
    result = plan(args.root)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected": len(result["files"]), "retained": len(result["retained"]), "errors": result["errors"]}, ensure_ascii=False))
    if args.apply:
        apply(args.root, result)
    return bool(result["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
