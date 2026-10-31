"""Native pre-feature river channel fill and dry-land ruin guards.

K's documented replace shape asserted with evaluated height 0..0 in client
3.9. Use the fill shape shipped in the local editor and strict fixed ranges.
This is a new-world terrain pipeline, never a live-world repair. Native channel
continuity, absence of assertions and complete landmarks need joint acceptance.
"""
import argparse
import copy
import json
from pathlib import Path
import build_ruin_structures as ruins

# Exact historical J input recognition. Preserve the existing terrain-only
# replacement set while correcting the destination field of both nodes.
TERRAIN = ("minecraft:sand", "minecraft:gravel", "minecraft:dirt",
           "minecraft:grass_block", "minecraft:stone", "minecraft:clay",
           "minecraft:podzol", "minecraft:mycelium")


def _retired_surface_adjustment():
    def replace(low, high, block):
        return {"type": "replace", "min_height": low, "max_height": high,
                "percentage": 1.0, "from_block_pool": list(TERRAIN),
                "pool": [{"fill_block": block, "weight": 1}]}
    return {"adjustments": [
        replace(63, "math.max(63, math.min(255, variable.height))", "minecraft:air"),
        replace(61, 62, "minecraft:water"),
    ]}


def _failed_replace_adjustment():
    # Official NetEase biome-height replace contract, unlike fill's `pool`:
    # docs: custom dimensions / biome terrain / section 5-3, replace.
    result = _retired_surface_adjustment()
    for step in result["adjustments"]:
        step["to_block_pool"] = step.pop("pool")
    return result


def _channel_surface_adjustment():
    # Native biome height runs before structures/vegetation. Clearing stops at
    # the dimension's last valid Y; the two water-surface layers do not refill
    # the deep bed below Y61 or change the inherited river height profile.
    return {"adjustments": [
        {"type": "fill", "min_height": 63, "max_height": 255,
         "pool": [{"fill_block": "minecraft:air", "weight": 1}]},
        # L's 61..62 only changed Y61; Y62 remained the blocking sand cap.
        # 3.9 L/M native snapshots: [61,62) changes only Y61; [61,63) also
        # replaces the Y62 sand cap. Keep this upper endpoint exclusive.
        {"type": "fill", "min_height": 61, "max_height": 63,
         "pool": [{"fill_block": "minecraft:water", "weight": 1}]},
    ]}


def _previous_fill_adjustment():
    result = _channel_surface_adjustment()
    result["adjustments"][1]["max_height"] = 62
    return result


def river_candidate(document):
    result = copy.deepcopy(document)
    biome = result["minecraft:biome"]
    if biome["description"] != {"identifier": "dm33027004_river", "inherits": "river"}:
        raise ValueError("Only the existing Twilight river may be adjusted")
    components = biome["components"]
    if components.get("minecraft:overworld_height") not in (
        {"noise_type": "river"}, {"noise_type": "ocean"}
    ):
        raise ValueError("Expected an explicitly reviewed native depth profile")
    corrected = _channel_surface_adjustment()
    if "netease:overworld_surface" in components:
        if components["netease:overworld_surface"] not in (
            _retired_surface_adjustment(), _failed_replace_adjustment(),
            _previous_fill_adjustment(), corrected
        ):
            raise ValueError("Unreviewed surface pipeline must not be overwritten")
    components["netease:overworld_surface"] = corrected
    return result


def build(source_root, output_root):
    bp = Path(source_root) / "TwilightBossSliceB"
    output = Path(output_root) / "TwilightBossSliceB"
    rel = "netease_biomes/dm33027004/dm33027004_river.json"
    documents = {rel: river_candidate(json.loads((bp / rel).read_text(encoding="utf-8")))}
    catalog = json.loads((bp / "structures/tf_slice/ruins/structure_catalog_v1.json").read_text(encoding="utf-8"))
    entries = {row["id"]: row for row in catalog["structures"]}
    for kind in ruins.DRY_GROUND_RUINS:
        rel = "netease_features/%s_scatter_feature.json" % kind
        current = json.loads((bp / rel).read_text(encoding="utf-8"))
        selector = "tf_slice:%s_structure_selector_feature" % kind
        guard = "tf_slice:%s_dry_ground_feature" % kind
        if current["minecraft:scatter_feature"]["places_feature"] == guard:
            continue  # Already installed in I; do not rewrite tested entries.
        if current["minecraft:scatter_feature"]["places_feature"] != selector:
            raise ValueError("Unexpected placement graph: " + kind)
        bounds = [v["bounds"] for v in entries[kind]["variants"]]
        sx = max(b[3] - b[0] + 1 for b in bounds)
        sz = max(b[5] - b[2] + 1 for b in bounds)
        current["minecraft:scatter_feature"]["places_feature"] = guard
        documents[rel] = current
        documents.update({"netease_features/" + name: doc for name, doc in
                          ruins._dry_footprint_documents(guard, selector, sx, sz).items()})
    for rel, doc in documents.items():
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return list(documents)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()
    if args.source_root.resolve() == args.output_root.resolve():
        p.error("Use an isolated candidate directory")
    print(json.dumps(build(args.source_root, args.output_root)))
