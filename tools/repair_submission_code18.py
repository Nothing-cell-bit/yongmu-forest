"""Repair only the reported timeout method in a hash-bound submission ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from submission_codecheck import require_clean, check_source

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "tools"))
import release_audit

SERVER = "behavior_pack/TwilightBossSlice/serverSystem.py"


def repair_timeout(data):
    source = data.decode("utf-8-sig")
    start = source.index("    def _process_portal_background_preloads(self):")
    end = source.index("\n    def ", start + 1)
    method = source[start:end]
    replacements = [("if inflight is not None:", "if isinstance(inflight, dict):"),
                    ('inflight["timedOut"] = True', 'inflight.update({"timedOut": True})')]
    for before, after in replacements:
        if method.count(before) != 1:
            raise ValueError("Unexpected timeout method; refusing a broad replacement")
        method = method.replace(before, after, 1)
    return (source[:start] + method + source[end:]).encode("utf-8")


def build(source, output, evidence, expected_sha256):
    source, output, evidence = Path(source), Path(output), Path(evidence)
    if output.exists():
        raise ValueError("Never overwrite a release candidate")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Rejected archive hash changed")
    check_source(ROOT / "TwilightBossSliceB")
    rows = release_audit.members(source.resolve())
    original = dict(rows)
    rows = [(name, repair_timeout(data) if name == SERVER else data) for name, data in rows]
    if SERVER not in original:
        raise ValueError("Missing reported runtime script")
    require_clean(rows)
    audit = release_audit.audit(rows, list(release_audit.DEFAULT_REQUIRED), ["behavior_pack/"])
    if audit["status"] != "local_preflight_pass":
        raise ValueError("Release preflight failed: " + repr(audit))
    if {n.split("/")[0] for n, _ in rows} != {"behavior_pack", "resource_pack"}:
        raise ValueError("Unexpected upload roots")
    for name, data in rows:
        if name.endswith(".json"):
            json.loads(data.decode("utf-8-sig"))
    # Preserve member metadata, empty directories and all unrelated bytes.
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(output, "x") as new:
        fixed = dict(rows)
        new.comment = old.comment
        for info in old.infolist():
            new.writestr(info, fixed[info.filename])
    final = release_audit.members(output.resolve())
    require_clean(final)
    final_audit = release_audit.audit(final, list(release_audit.DEFAULT_REQUIRED), ["behavior_pack/"])
    if final_audit["status"] != "local_preflight_pass" or dict(final) != dict(rows):
        raise ValueError("Final archive readback failed")
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError("Final archive CRC failed")
    changed = [n for n, b in final if original[n] != b]
    if changed != [SERVER]:
        raise ValueError("Unexpected changed members: " + repr(changed))
    evidence.mkdir(parents=True, exist_ok=True)
    # Exact final script inputs for existing SDK-boundary regression tests.
    for name, data in final:
        if name.startswith("behavior_pack/") and name.endswith((".py", ".json")):
            dest = evidence / "runtime-test" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    report = {"baseline": str(source.resolve()), "baseline_sha256": digest,
              "archive": str(output.resolve()), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "changed": changed, "added": [], "removed": [], "members": len(final),
              "all_other_member_bytes_preserved": True, "version": "0.12.5",
              "source_codecheck": "pass", "archive_codecheck": "pass",
              "archive_audit": final_audit, "runtime_acceptance": "not_run",
              "platform_review": "not_submitted"}
    (evidence / "repair-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    build(args.input, args.output, args.evidence, args.expected_sha256)
