"""Merge reviewed J gameplay changes into the original compact submission pack.

No installed pack writes, structure rebuild, asset pruning or GUI interaction.
The original release's resources, recipes, models, notices and unrelated scripts
are preserved; runtime diagnostics are stripped from copied gameplay scripts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import prepare_release_candidate as cleanup
import release_texture_layout as layout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "tools"))
import release_audit
from submission_codecheck import check_source, require_clean

SCRIPT_NAMES = ("serverSystem.py", "structureWorldgenService.py", "spawn_policy.py",
                "ledger_json_cache.py", "water_marker_cleanup.py")
LAND_RUINS = ("monolith", "stone_circle", "well", "foundation", "druid_hut",
              "outside_stalagmite", "grove_ruins")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(base_archive, accepted_archive, output, evidence):
    output, evidence = Path(output), Path(evidence)
    if output.exists():
        raise ValueError("Never overwrite a submission archive")
    check_source(ROOT / "TwilightBossSliceB")
    evidence.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(base_archive) as z:
        rows = {i.filename: z.read(i) for i in z.infolist()}
    original = dict(rows)
    for pack in ("behavior_pack", "resource_pack"):
        if json.loads(rows[pack + "/manifest.json"])["header"]["version"] != [0, 12, 4]:
            raise ValueError("Expected the reviewed 0.12.4 submission baseline")
    worldgen_prefixes = ("netease_dimension/", "netease_biomes/", "netease_features/",
                        "netease_feature_rules/", "structures/")
    with zipfile.ZipFile(accepted_archive) as z:
        selected = [n.split("/", 1)[1] for n in z.namelist()
                    if n.startswith("TwilightBossSliceB/") and not n.endswith("/")
                    and n.split("/", 1)[1].startswith(worldgen_prefixes)]
        for rel in selected:
            name = "behavior_pack/" + rel
            # The original submission already checks the full 15x15 stump
            # footprint. J's older 9x9 slope envelope must not replace it.
            if rel == "netease_features/hollow_stump_scatter_feature.json":
                continue
            data = z.read("TwilightBossSliceB/" + rel)
            if rows.get(name) != data:
                rows[name] = data
        rows["resource_pack/ui/portal_loading.json"] = z.read("TwilightBossSliceR/ui/portal_loading.json")
    missing_worldgen = {n for n in original if n.startswith("behavior_pack/netease_feature_rules/")
                        and not n.endswith("/") and n[len("behavior_pack/"):] not in selected}
    retired = {"behavior_pack/netease_feature_rules/" + kind + "_tree_profile_feature_rule.json"
               for kind in ("dense_forest", "firefly_forest", "oak_savannah")}
    if missing_worldgen != retired:
        raise ValueError("Unreviewed worldgen retirement: " + repr(missing_worldgen))
    for name in retired:
        del rows[name]
    source_hashes = {}
    for name in SCRIPT_NAMES:
        source = ROOT / "TwilightBossSliceB/TwilightBossSlice" / name
        data = source.read_bytes()
        source_hashes[str(source)] = sha(data)
        text = data.decode("utf-8-sig").replace("\r\n", "\n")
        text = layout.rewrite(cleanup.clean_script(name, text))
        rows["behavior_pack/TwilightBossSlice/" + name] = text.encode("utf-8")
        saved = evidence / "reviewed-source" / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(data)
    for pack in ("behavior_pack", "resource_pack"):
        name = pack + "/manifest.json"
        doc = json.loads(rows[name])
        doc["header"]["version"] = [0, 12, 5]
        for module in doc.get("modules", []):
            module["version"] = [0, 12, 5]
        for dep in doc.get("dependencies", []):
            if "uuid" in dep:
                dep["version"] = [0, 12, 5]
        rows[name] = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    name = "behavior_pack/TwilightBossSlice/release_metadata.py"
    text = rows[name].decode("utf-8")
    text = re.sub(r"^PACK_VERSION = .*$", "PACK_VERSION = (0, 12, 5)", text, flags=re.M)
    text = re.sub(r"^RELEASE_STAGE = .*$", 'RELEASE_STAGE = "submission_candidate_20261020"', text, flags=re.M)
    rows[name] = text.encode("utf-8")

    # No debug stub: remove both the module and callers, preserving real APIs.
    for name in rows:
        if name.endswith(".py"):
            if re.search(rb"[A-Za-z]:[/\\]|native_world_diag|chunk_latency_probe|loadprobe|StartProfile|StopProfile",
                         rows[name]):
                raise ValueError("Development code remains: " + name)
    for n in rows:
        if n.split("/")[0] not in ("behavior_pack", "resource_pack"):
            raise ValueError("Unexpected upload root: " + n)
        if n.endswith(".json"):
            json.loads(rows[n])
    require_clean(rows.items())
    audit = release_audit.audit(sorted(rows.items()), list(release_audit.DEFAULT_REQUIRED), ["behavior_pack/"])
    (evidence / "source-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if audit["status"] != "local_preflight_pass":
        raise ValueError("Source preflight failed")
    # Static module and feature references for the newly copied entry points.
    modules = {n[len("behavior_pack/"):-3].replace("/", ".")
               for n in rows if n.startswith("behavior_pack/") and n.endswith(".py")}
    for name in SCRIPT_NAMES:
        text = rows["behavior_pack/TwilightBossSlice/" + name].decode("utf-8")
        for target in re.findall(r"^import (TwilightBossSlice\.\w+)", text, re.M):
            if target not in modules:
                raise ValueError("Missing runtime dependency: " + target)
    for rel in selected:
        if not rel.startswith("netease_features/"):
            continue
        doc = json.loads(rows["behavior_pack/" + rel])
        def references(value, context=""):
            if isinstance(value, dict):
                for key, child in value.items():
                    references(child, key)
            elif isinstance(value, list):
                for child in value:
                    references(child, context)
            elif isinstance(value, str) and value.startswith("tf_slice:"):
                if context in ("places_feature", "features", "feature", "places_tree"):
                    dest = "behavior_pack/netease_features/" + value.split(":")[-1] + ".json"
                    if dest not in rows:
                        raise ValueError("Missing native feature: " + dest)
                elif context == "places_structure":
                    dest = "behavior_pack/structures/" + value.replace(":", "/", 1) + ".mcstructure"
                    if dest not in rows:
                        raise ValueError("Missing native structure: " + dest)
        references(doc)
    for path, digest in source_hashes.items():
        if sha(Path(path).read_bytes()) != digest:
            raise ValueError("Shared source changed during packaging: " + path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(rows.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o40755 << 16) | 0x10) if name.endswith("/") else (0o100644 << 16)
            z.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert {n: sha(z.read(n)) for n in z.namelist()} == {n: sha(data) for n, data in rows.items()}
    # Re-run the actual archive reader with its size/zip-safety bounds.
    final_rows = release_audit.members(output.resolve())
    require_clean(final_rows)
    final_audit = release_audit.audit(final_rows, list(release_audit.DEFAULT_REQUIRED), ["behavior_pack/"])
    (evidence / "archive-audit.json").write_text(json.dumps(final_audit, indent=2), encoding="utf-8")
    assert final_audit["status"] == "local_preflight_pass"
    from check_block_mining import check as check_mining
    from check_public_block_models import check as check_models
    for label, check in (("mining", check_mining), ("public-models", check_models)):
        result = check(output)
        (evidence / (label + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
        if result["issues"]:
            raise ValueError(label + " check failed")
    # Exact final runtime inputs for SDK-boundary tests; no local installed writes.
    test_root = evidence / "runtime-test/behavior_pack"
    for name, data in rows.items():
        if name.startswith(("behavior_pack/TwilightBossSlice/", "behavior_pack/entities/")) and not name.endswith("/"):
            target = evidence / "runtime-test" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    changed = sorted(n for n, data in rows.items() if data != original.get(n))
    unchanged_assets = [n for n in original if n.startswith("resource_pack/") and n != "resource_pack/manifest.json"
                        and n != "resource_pack/ui/portal_loading.json"]
    assert all(rows[n] == original[n] for n in unchanged_assets)
    assert all(rows[n] == data for n, data in original.items() if "/structures/" in n)
    report = {"archive": str(output.resolve()), "sha256": sha(output.read_bytes()),
              "bytes": output.stat().st_size, "version": "0.12.5",
              "baseline": str(Path(base_archive).resolve()), "baselineSha256": sha(Path(base_archive).read_bytes()),
              "acceptedCandidateSha256": sha(Path(accepted_archive).read_bytes()),
              "changed": changed, "removed": sorted(retired),
              "files": sum(not n.endswith("/") for n in rows),
              "originalAssetsAndStructuresPreserved": True,
              "originalStumpFootprintPreserved": True,
              "uuidsPreserved": all(json.loads(rows[p + "/manifest.json"])["header"]["uuid"] ==
                                    json.loads(original[p + "/manifest.json"])["header"]["uuid"]
                                    for p in ("behavior_pack", "resource_pack")),
              "sourceHashes": source_hashes, "runtimeTestRoot": str(test_root.resolve()),
              "runtimeAcceptance": "not_run", "platformReview": "not_submitted"}
    (evidence / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("changed", "sourceHashes")}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-archive", type=Path, required=True)
    p.add_argument("--accepted-archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    a = p.parse_args()
    build(a.base_archive, a.accepted_archive, a.output, a.evidence)
