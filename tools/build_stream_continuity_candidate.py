"""Bounded bank widening and rare dry-land guards; never rebuild structures."""
import argparse
import copy
import json
from pathlib import Path
import build_ruin_structures as ruins

# Target SDK IDs for C's eleven river-eligible land biomes.
ELIGIBLE = (1, 6, 14, 15, 21, 29, 132, 134, 155, 157, 160)


def bank_condition():
    center = "query.get_neighborhood_is_biome(0, 0, %s)" % ", ".join(map(str, ELIGIBLE))
    neighbors = " || ".join("query.get_neighborhood_is_biome(%d, %d, 7)" % p
                            for p in ((-1, 0), (1, 0), (0, -1), (0, 1)))
    return "(%s && (%s)) ? 0 : -1" % (center, neighbors)


def build_dimension(source):
    result = copy.deepcopy(source)
    stages = result["netease:dimension_info"]["components"]["netease:biome_source"]
    if len(stages) != 17 or stages[-1].get("pool") != ["dm33027004_river"]:
        raise ValueError("Expected the reviewed C/H 17-stage source")
    stages.append({"type": "condition", "condition": bank_condition(),
                   "pool": ["dm33027004_river"]})
    return result


def build(source_root, output_root):
    source, out = Path(source_root), Path(output_root)
    bp, target = source / "TwilightBossSliceB", out / "TwilightBossSliceB"
    dim = "netease_dimension/dm33027004.json"
    documents = {dim: build_dimension(json.loads((bp / dim).read_text(encoding="utf-8")))}
    catalog = json.loads((bp / "structures/tf_slice/ruins/structure_catalog_v1.json").read_text(encoding="utf-8"))
    entries = {row["id"]: row for row in catalog["structures"]}
    for kind in ruins.DRY_GROUND_RUINS:
        bounds = [v["bounds"] for v in entries[kind]["variants"]]
        sx = max(b[3] - b[0] + 1 for b in bounds)
        sz = max(b[5] - b[2] + 1 for b in bounds)
        rel = "netease_features/%s_scatter_feature.json" % kind
        current = json.loads((bp / rel).read_text(encoding="utf-8"))
        expected = "tf_slice:%s_structure_selector_feature" % kind
        if current["minecraft:scatter_feature"]["places_feature"] != expected:
            raise ValueError("Unreviewed small-ruin feature: " + kind)
        guard = "tf_slice:%s_dry_ground_feature" % kind
        current["minecraft:scatter_feature"]["places_feature"] = guard
        documents[rel] = current
        documents.update({"netease_features/" + name: document
                          for name, document in
                          ruins._dry_footprint_documents(guard, expected, sx, sz).items()})
    for rel, document in documents.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return list(documents)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.source_root.resolve() == args.output_root.resolve():
        parser.error("Use an isolated candidate output root")
    print(json.dumps(build(args.source_root, args.output_root)))
