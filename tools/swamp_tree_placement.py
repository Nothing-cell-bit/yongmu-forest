"""Build only the Swamp tree probe/placement/cleanup feature graph.

The aggregate must work in either execution order. Cleanup is restricted to
the probe's log with replaceable space above; a complete template supplies a
second trunk block there. No search, template rebuild, or runtime code is used.
"""
import argparse
import json
from pathlib import Path


SWAMP_TREE_LOGS = {
    "mangrove": "tf_slice:mangrove_log",
    "swampy_oak": "tf_slice:twilight_oak_log",
}
TREE_LOGS = dict(SWAMP_TREE_LOGS, canopy="tf_slice:canopy_log")
TREE_GROUND = (
    "minecraft:grass", "minecraft:grass_block", "minecraft:dirt",
    "minecraft:clay", "minecraft:podzol", "minecraft:mycelium",
)
TREE_REPLACEABLE = (
    "minecraft:air", "minecraft:water", "minecraft:flowing_water",
    "minecraft:tallgrass", "minecraft:short_grass", "minecraft:vine",
)


def _document(kind, identifier, **body):
    return {
        "format_version": "1.21.40" if kind == "single_block_feature" else "1.20.30",
        "minecraft:" + kind: {
            "description": {"identifier": "tf_slice:" + identifier},
            **body,
        },
    }


def tree_placement_documents(kind):
    return structure_tree_documents(kind + "_tree", TREE_LOGS[kind],
                                    TREE_GROUND, TREE_REPLACEABLE, 4)


def structure_tree_documents(prefix, log, ground, replaceable, variants):
    anchor = prefix + "_anchor_feature"
    cleanup = prefix + "_cleanup_probe_feature"
    documents = {
        anchor + ".json": _document(
            "single_block_feature", anchor,
            places_block=[{"block": log, "weight": 1}],
            enforce_placement_rules=False,
            enforce_survivability_rules=False,
            may_replace=list(replaceable),
            may_attach_to={
                "auto_rotate": False,
                "min_sides_must_attach": 2,
                "bottom": list(ground),
                "top": list(replaceable),
            },
        ),
        cleanup + ".json": _document(
            "single_block_feature", cleanup,
            places_block=[{"block": "minecraft:air", "weight": 1}],
            enforce_placement_rules=False,
            enforce_survivability_rules=False,
            may_replace=[log],
            may_attach_to={
                "auto_rotate": False,
                "min_sides_must_attach": 1,
                "top": list(replaceable),
            },
        ),
    }
    for variant in range(variants):
        variant_prefix = "%s_v%02d" % (prefix, variant)
        placement = variant_prefix + "_placement_feature"
        documents[variant_prefix + "_sequence_feature.json"] = _document(
            "sequence_feature", variant_prefix + "_sequence_feature",
            features=["tf_slice:" + anchor, "tf_slice:" + placement],
        )
        documents[placement + ".json"] = _document(
            "aggregate_feature", placement,
            features=["tf_slice:" + variant_prefix + "_offset_feature", "tf_slice:" + cleanup],
            # No ordering assumption: cleanup may run before or after the
            # template. Never short-circuit just because cleanup succeeded.
            early_out="none",
        )
    return documents


def all_placement_documents():
    return {name: document for kind in SWAMP_TREE_LOGS
            for name, document in tree_placement_documents(kind).items()}


def check_placement_documents(feature_documents):
    """Return filenames whose graph is absent or differs from the safe graph."""
    return [name for name, expected in all_placement_documents().items()
            if feature_documents.get(name) != expected]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--output-root", type=Path, required=True,
                        help="Root containing TwilightBossSliceB; use an isolated preview first")
    parser.add_argument("--acknowledge-source-pack-write", action="store_true")
    args = parser.parse_args(argv)
    root = args.output_root.resolve()
    canonical = Path(__file__).resolve().parents[1]
    feature_dir = root / "TwilightBossSliceB" / "netease_features"
    if args.write:
        if root == canonical and not args.acknowledge_source_pack_write:
            parser.error("source-pack rebuild requires --acknowledge-source-pack-write")
        feature_dir.mkdir(parents=True, exist_ok=True)
        for name, document in all_placement_documents().items():
            (feature_dir / name).write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("Wrote 20 Swamp tree placement JSON files to %s" % feature_dir)
        return 0
    actual = {}
    for name in all_placement_documents():
        path = feature_dir / name
        if path.is_file():
            actual[name] = json.loads(path.read_text(encoding="utf-8"))
    differences = check_placement_documents(actual)
    for name in differences:
        print("Missing or stale: " + name)
    if not differences:
        print("Swamp tree placement graph matches (20 files)")
    return int(bool(differences))


if __name__ == "__main__":
    raise SystemExit(main())
