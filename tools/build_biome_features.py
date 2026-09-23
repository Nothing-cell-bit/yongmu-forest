#!/usr/bin/env python3
"""Build deterministic NetEase feature definitions for Twilight biomes."""

import json
from pathlib import Path

from build_enchanted_forest import build_enchanted_forest
from build_mushroom_forest import build_mushroom_forest
from build_spooky_forest import build_spooky_forest
from build_swamp_features import build_swamp_features
from landmark_surface_decorations import (
    normalize_landmark_surface_decorations,
)
from native_structure_worldgen_safety import guard_native_structure_rules


ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "TwilightBossSliceB" / "netease_features"
RULES = ROOT / "TwilightBossSliceB" / "netease_feature_rules"

TREE_PROFILES = {
    "dense_forest": {
        "iterations": 6,
        "features": [
            ["tf_slice:canopy_tree_selector_feature", 5],
            ["tf_slice:twilight_tree_mix_selector_feature", 2],
        ],
    },
    "oak_savannah": {
        "iterations": 2,
        "features": [
            ["tf_slice:twilight_oak_tree_feature", 5],
            ["tf_slice:large_twilight_oak_tree_feature", 2],
            ["tf_slice:canopy_tree_feature", 1],
        ],
    },
    "firefly_forest": {
        "iterations": 4,
        "features": [
            ["tf_slice:canopy_tree_selector_feature", 3],
            ["tf_slice:twilight_tree_mix_selector_feature", 2],
        ],
    },
    "enchanted_forest": {
        "iterations": "5 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
        "features": [
            ["tf_slice:enchanted_regular_rainbow_tree_trigger_feature", 650],
            ["tf_slice:enchanted_vanilla_oak_tree_trigger_feature", 150],
            ["tf_slice:enchanted_vanilla_birch_tree_trigger_feature", 128],
            ["tf_slice:enchanted_large_rainbow_tree_trigger_feature", 72],
        ],
    },
}


def write_json(path, document):
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def tree_feature(identifier, trunk_block, leaf_block, height, radius):
    return {
        "format_version": "1.14.0",
        "minecraft:tree_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "trunk": {
                "trunk_height": {
                    "range_min": height[0],
                    "range_max": height[1],
                },
                "trunk_block": {"name": trunk_block},
            },
            "canopy": {
                "canopy_offset": {"min": -1, "max": 0},
                "variation_chance": {"numerator": 1, "denominator": 3},
                "leaf_block": {"name": leaf_block},
                "canopy_slope": {
                    "rise": 2,
                    "run": 3,
                },
                "canopy_radius": radius,
                "min_width": 1,
            },
            "base_block": ["minecraft:dirt"],
            "may_grow_on": [
                "minecraft:grass",
                "minecraft:grass_block",
                "minecraft:dirt",
                "minecraft:podzol",
                "minecraft:mycelium",
            ],
            "may_replace": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
                "tf_slice:fallen_leaves",
            ],
            "may_grow_through": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
            ],
        },
    }


def dead_canopy_tree_feature():
    """Approximate upstream BranchingTrunkPlacer with NetEase fancy trunk.

    Upstream uses a 20 + rand(0..5) + rand(0..5) block trunk, starts branches
    seven blocks below the top, and deliberately supplies air as foliage.
    NetEase has no Twilight decorator/trunk type, but its mega trunk exposes
    the same two height intervals, branch length, slope and altitude window.
    """
    return {
        "format_version": "1.14.0",
        "minecraft:tree_feature": {
            "description": {
                "identifier": "tf_slice:spooky_dead_tree_feature"
            },
            "mega_trunk": {
                "trunk_width": 1,
                "trunk_height": {
                    "base": 20,
                    "intervals": [6, 6],
                },
                "trunk_block": {"name": "tf_slice:canopy_log"},
                "branches": {
                    "branch_length": 10,
                    "branch_slope": -0.2,
                    "branch_interval": {
                        "range_min": 2.0,
                        "range_max": 3.0,
                    },
                    "branch_altitude_factor": {
                        "min": 0.65,
                        "max": 1.0,
                    },
                    "branch_canopy": {
                        "mega_canopy": {
                            "canopy_height": 1,
                            "base_radius": 0,
                            "core_width": 1,
                            "leaf_block": {
                                "name": "minecraft:air"
                            },
                        }
                    },
                },
            },
            "mega_canopy": {
                "canopy_height": 1,
                "base_radius": 0,
                "core_width": 1,
                "leaf_block": {"name": "minecraft:air"},
            },
            "base_block": ["minecraft:dirt"],
            "may_grow_on": [
                "minecraft:grass",
                "minecraft:grass_block",
                "minecraft:dirt",
                "minecraft:podzol",
            ],
            "may_replace": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
                "tf_slice:fallen_leaves",
            ],
            "may_grow_through": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
            ],
        },
    }


def blob_tree_feature(identifier, trunk_block, leaf_block, height):
    """Build the conservative canopy shape used as a sapling fallback."""
    return {
        "format_version": "1.14.0",
        "minecraft:tree_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "trunk": {
                "trunk_height": {
                    "range_min": height[0],
                    "range_max": height[1],
                },
                "trunk_block": {"name": trunk_block},
            },
            "canopy": {
                "canopy_offset": {"min": -3, "max": 0},
                "variation_chance": [
                    {"numerator": 1, "denominator": 2},
                    {"numerator": 1, "denominator": 2},
                    {"numerator": 1, "denominator": 2},
                    {"numerator": 1, "denominator": 1},
                ],
                "leaf_block": {"name": leaf_block},
            },
            "base_block": ["minecraft:dirt"],
            "may_grow_on": [
                "minecraft:grass",
                "minecraft:grass_block",
                "minecraft:dirt",
                "minecraft:podzol",
                "minecraft:mycelium",
            ],
            "may_replace": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
                "tf_slice:fallen_leaves",
            ],
            "may_grow_through": [
                "minecraft:air",
                "minecraft:tallgrass",
                "minecraft:double_plant",
            ],
        },
    }


def biome_filter(keys):
    tags = [
        {
            "test": "has_biome_tag",
            "operator": "==",
            "value": "tf_slice_biome_%s" % key,
        }
        for key in keys
    ]
    selected = tags[0] if len(tags) == 1 else {"any_of": tags}
    return [
        {
            "all_of": [
                {
                    "test": "has_biome_tag",
                    "operator": "==",
                    "value": "dm33027004",
                },
                selected,
            ]
        }
    ]


def ensure_tree_features_grow_on_native_landmark_grass():
    """Keep natural trees compatible with authored ordinary grass surfaces.

    Large landmarks are generated in the surface pass before the decoration
    pass. Their naturalizable
    roofs and exterior lawns use the modern ``minecraft:grass_block`` name,
    while protected arenas use a custom block that is deliberately omitted.
    """
    updated = 0
    protected = "tf_slice:landmark_protected_grass"
    for path in sorted(FEATURES.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        tree = document.get("minecraft:tree_feature")
        if tree is None:
            continue
        grow_on = list(tree.setdefault("may_grow_on", []))
        grow_on = [name for name in grow_on if name != protected]
        if "minecraft:grass_block" not in grow_on:
            try:
                index = grow_on.index("minecraft:grass") + 1
            except ValueError:
                index = 0
            grow_on.insert(index, "minecraft:grass_block")
        tree["may_grow_on"] = grow_on
        write_json(path, document)
        updated += 1
    return updated


def surface_rule(identifier, feature, keys, iterations, chance=None, y=None):
    distribution = {
        "iterations": iterations,
        "coordinate_eval_order": "xzy",
        "x": {"distribution": "uniform", "extent": [0, 15]},
        "y": y or "query.get_height_at(variable.worldx, variable.worldz)",
        "z": {"distribution": "uniform", "extent": [0, 15]},
    }
    if chance is not None:
        distribution["scatter_chance"] = chance
    return {
        "format_version": "1.14.0",
        "minecraft:feature_rules": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "places_feature": "tf_slice:%s" % feature,
            },
            "conditions": {
                "placement_pass": "after_surface_pass",
                "minecraft:biome_filter": biome_filter(keys),
            },
            "distribution": distribution,
        },
    }


def single_block_feature(identifier, block, bottom):
    return {
        "format_version": "1.21.40",
        "minecraft:single_block_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_block": [{"block": block, "weight": 1}],
            "enforce_placement_rules": False,
            "enforce_survivability_rules": False,
            "may_replace": ["minecraft:air", "minecraft:water"],
            "may_attach_to": {
                "auto_rotate": False,
                "min_sides_must_attach": 1,
                "bottom": bottom,
            },
        },
    }


def scatter_feature(identifier, placed, iterations, radius=7):
    return {
        "format_version": "1.21.10",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_feature": "tf_slice:%s" % placed,
            "project_input_to_floor": True,
            "distribution": {
                "iterations": iterations,
                "coordinate_eval_order": "xzy",
                "x": {"distribution": "triangle", "extent": [-radius, radius]},
                "y": 0,
                "z": {"distribution": "triangle", "extent": [-radius, radius]},
            },
        },
    }


def main():
    generated = {}
    generated["forest_vanilla_oak_tree_feature.json"] = tree_feature(
        "forest_vanilla_oak_tree_feature",
        "minecraft:oak_log",
        "minecraft:oak_leaves",
        (4, 7),
        2,
    )
    generated["forest_vanilla_birch_tree_feature.json"] = tree_feature(
        "forest_vanilla_birch_tree_feature",
        "minecraft:birch_log",
        "minecraft:birch_leaves",
        (5, 8),
        2,
    )
    generated["rainbow_oak_tree_feature.json"] = tree_feature(
        "rainbow_oak_tree_feature",
        "tf_slice:twilight_oak_log",
        "tf_slice:rainbow_oak_leaves",
        (5, 9),
        3,
    )
    generated["rainbow_oak_tree_fallback_feature.json"] = blob_tree_feature(
        "rainbow_oak_tree_fallback_feature",
        "tf_slice:twilight_oak_log",
        "tf_slice:rainbow_oak_leaves",
        (5, 9),
    )
    for biome_key, profile in TREE_PROFILES.items():
        feature_name = "%s_tree_profile_feature" % biome_key
        generated["%s.json" % feature_name] = {
            "format_version": "1.20.30",
            "minecraft:weighted_random_feature": {
                "description": {
                    "identifier": "tf_slice:%s" % feature_name
                },
                "features": profile["features"],
            },
        }
        rule_name = "%s_rule" % feature_name
        write_json(
            RULES / ("%s.json" % rule_name),
            surface_rule(
                rule_name,
                feature_name,
                [biome_key],
                profile["iterations"],
                y=None,
            ),
        )

    # The upstream spooky biome registers these as three independent placed
    # features. Each weighted count is 90% base and 10% base + 1.
    spooky_tree_rules = (
        ("spooky_dead_tree_feature", 2),
        ("spooky_twilight_oak_tree_feature", 1),
        ("spooky_large_twilight_oak_tree_feature", 1),
    )
    for rule_prefix, base_count in spooky_tree_rules:
        placed_feature = {
            "spooky_dead_tree_feature": "spooky_dead_tree_selector_feature",
            "spooky_twilight_oak_tree_feature": (
                "spooky_twilight_oak_tree_feature"
            ),
            "spooky_large_twilight_oak_tree_feature": (
                "spooky_large_twilight_oak_tree_feature"
            ),
        }[rule_prefix]
        rule_name = "%s_rule" % rule_prefix
        weighted_count = (
            "%d + (math.random_integer(0, 9) == 0 ? 1 : 0)" % base_count
        )
        write_json(
            RULES / ("%s.json" % rule_name),
            surface_rule(
                rule_name,
                placed_feature,
                ["spooky_forest"],
                weighted_count,
                # The projected position is the real trunk base. The dead-tree
                # variant sequence validates that block against ground before
                # applying its internal (-9, -5, -9) template offset.
                y=None,
            ),
        )

    # Remove the old weighted profile so rebuilding cannot leave the excessive
    # five-attempt, straight-trunk implementation active beside the new rules.
    for stale_path in (
        FEATURES / "spooky_dead_tree_feature.json",
        FEATURES / "spooky_forest_tree_profile_feature.json",
        RULES / "spooky_forest_tree_profile_feature_rule.json",
    ):
        if stale_path.exists():
            stale_path.unlink()

    plant_specs = {
        "mushgloom": {
            "block": "tf_slice:mushgloom",
            "keys": [
                "mushroom_forest",
                "dense_mushroom_forest",
                "firefly_forest",
            ],
            "patch": 96,
            "tries": 1,
            "chance": 20.0,
        },
        "fiddlehead": {
            "block": "tf_slice:fiddlehead",
            "keys": ["enchanted_forest"],
            "patch": 96,
            "tries": 1,
            "chance": None,
        },
        "fallen_leaves": {
            "block": "tf_slice:fallen_leaves",
            "keys": ["spooky_forest"],
            # One compact floor patch keeps the leaf litter readable without
            # covering whole chunks or strongly crossing biome boundaries.
            "patch": 16,
            "tries": 1,
            "radius": 3,
            "chance": None,
        },
    }
    ground = [
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:podzol",
        "minecraft:mycelium",
    ]
    for name, spec in plant_specs.items():
        base_name = "%s_feature" % name
        patch_name = "%s_patch_feature" % name
        generated["%s.json" % base_name] = single_block_feature(
            base_name, spec["block"], ground
        )
        generated["%s.json" % patch_name] = scatter_feature(
            patch_name,
            base_name,
            spec["patch"],
            spec.get("radius", 7),
        )
        write_json(
            RULES / ("%s_rule.json" % patch_name),
            surface_rule(
                "%s_rule" % patch_name,
                patch_name,
                spec["keys"],
                spec["tries"],
                spec["chance"],
            ),
        )

    generated["firefly_lamppost_feature.json"] = single_block_feature(
        "firefly_lamppost_feature", "tf_slice:firefly_jar", ground
    )
    write_json(
        RULES / "firefly_lamppost_feature_rule.json",
        surface_rule(
            "firefly_lamppost_feature_rule",
            "firefly_lamppost_feature",
            ["firefly_forest"],
            1,
            50.0,
        ),
    )

    generated["twilight_seagrass_feature.json"] = single_block_feature(
        "twilight_seagrass_feature",
        "minecraft:seagrass",
        [
            "minecraft:dirt",
            "minecraft:sand",
            "minecraft:gravel",
            "minecraft:clay",
        ],
    )
    generated["twilight_seagrass_patch_feature.json"] = scatter_feature(
        "twilight_seagrass_patch_feature",
        "twilight_seagrass_feature",
        48,
    )
    for biome_key, iterations in (("lake", 4), ("stream", 2)):
        write_json(
            RULES / ("%s_seagrass_feature_rule.json" % biome_key),
            surface_rule(
                "%s_seagrass_feature_rule" % biome_key,
                "twilight_seagrass_patch_feature",
                [biome_key],
                iterations,
            ),
        )

    for filename, document in generated.items():
        write_json(FEATURES / filename, document)
    build_spooky_forest(ROOT)
    build_enchanted_forest(ROOT)
    build_mushroom_forest(ROOT)
    build_swamp_features(ROOT)
    tree_feature_count = ensure_tree_features_grow_on_native_landmark_grass()
    surface_projection = normalize_landmark_surface_decorations(ROOT)
    structure_safety = guard_native_structure_rules(ROOT)
    print(
        "Generated %d biome features, %d feature rules, normalized %d trees, "
        "projected %d tree rules plus %d groundcover rules, and guarded %d "
        "native structure rules."
        % (
            len(generated),
            len(TREE_PROFILES) + len(plant_specs) + 3,
            tree_feature_count,
            surface_projection["treeRules"],
            surface_projection["projectedPatches"],
            structure_safety["guardedRules"],
        )
    )


if __name__ == "__main__":
    main()
