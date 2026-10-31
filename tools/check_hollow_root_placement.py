"""Read-only check joining hollow-root templates to actual pack placement rules."""
import argparse
import io
import json
from pathlib import Path
import re
import build_ruin_structures as builder


def read_template(path):
    stream = io.BytesIO(path.read_bytes())
    if builder._read_number(stream, "B") != builder.TAG_COMPOUND:
        raise ValueError("Not a compound: " + str(path))
    builder._read_string(stream, "<")
    result = builder._read_payload(stream, builder.TAG_COMPOUND, "<")
    if stream.read():
        raise ValueError("Trailing template bytes: " + str(path))
    return result


def inspect(bp):
    bp = Path(bp)
    issues, families = [], []
    # Natural giant-tree root collar is one block below the sampled surface.
    # Stump logs start on the sampled surface; their root collar is below it.
    for kind, bury in (("hollow_tree", 1), ("hollow_stump", 0)):
        paths = sorted((bp / "structures/tf_slice/ruins" / kind).rglob("*.mcstructure"))
        if not paths:
            issues.append(kind + ": missing templates")
            continue
        lows = []
        for path in paths:
            template = read_template(path)
            size = template["size"]
            palette = template["structure"]["palette"]["default"]["block_palette"]
            indices = template["structure"]["block_indices"][0]
            ys = [(index // size[2]) % size[1] for index, pi in enumerate(indices)
                  if pi >= 0 and palette[pi]["name"] == "tf_slice:twilight_oak_log"]
            if ys:
                lows.append(min(ys))
        if not lows:
            issues.append(kind + ": no upright trunk in templates")
            continue
        surface = min(lows)
        required = surface + bury
        rule_path = bp / "netease_feature_rules" / (kind + "_feature_rule.json")
        rule = json.loads(rule_path.read_text(encoding="utf-8"))["minecraft:feature_rules"]
        expression = rule["distribution"]["y"]
        match = re.search(r" - (\d+)\)?$", str(expression))
        actual = int(match.group(1)) if match else None
        families.append({"kind": kind, "templateCount": len(paths),
                         "trunkLocalY": surface, "requiredOffset": required,
                         "actualOffset": actual, "expression": expression})
        if actual != required:
            issues.append("%s: root collar requires -%d, actual -%s" % (kind, required, actual))
        if rule["conditions"]["placement_pass"] != "after_surface_pass":
            issues.append(kind + ": wrong placement pass")
    return {"families": families, "issues": issues}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--behavior-pack", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.behavior_pack)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["issues"]))
