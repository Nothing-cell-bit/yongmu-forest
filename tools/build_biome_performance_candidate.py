#!/usr/bin/env python3
"""Build a benchmark-only upstream-style Twilight biome-source candidate.

This file deliberately does not replace the canonical dimension source.  The
candidate removes the recursive companion dilation chain so cold-start timing
can be measured independently before route landmark spacing is migrated.
"""

from __future__ import print_function

import argparse
import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog
from tools import build_dark_forest_biomes


PERFORMANCE_KEY_GRID = {
    "len_x": 8,
    "len_z": 8,
    "border_x": 2,
    "border_z": 2,
}
CARDINAL_OFFSETS = ((-1, 0), (0, -1), (0, 1), (1, 0))
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "biome_candidates"
    / "dm33027004_upstream_associated.json"
)


def _classifier_condition():
    region_x = "math.floor(variable.worldx / %d)" % (
        PERFORMANCE_KEY_GRID["len_x"]
    )
    region_z = "math.floor(variable.worldz / %d)" % (
        PERFORMANCE_KEY_GRID["len_z"]
    )
    region_sum = "(%s + %s)" % (region_x, region_z)
    odd_region = "(%s - (math.floor(%s / 2) * 2)) == 1" % (
        region_sum,
        region_sum,
    )
    anchor_type = biome_catalog.BIOME_QUERY_TYPES[
        biome_catalog.KEY_BIOME_ANCHOR_KEY
    ]
    return (
        "(query.get_neighborhood_is_biome(0, 0, %d)) && (%s) ? 0 : -1"
        % (anchor_type, odd_region)
    )


def candidate_biome_source():
    source = [
        {
            "type": "random_with_weight",
            "pool": [
                {
                    "biome_type": entry["identifier"],
                    "weight": entry["weight"],
                }
                for entry in biome_catalog.RANDOM_SOURCE_BIOMES
            ],
        }
    ]
    anchor = biome_catalog.BIOMES_BY_KEY[
        biome_catalog.KEY_BIOME_ANCHOR_KEY
    ]
    key_stage = dict({"type": "gen_key_biomes"}, **PERFORMANCE_KEY_GRID)
    key_stage["pool"] = [
        {
            "biome_type": anchor["identifier"],
            "weight": anchor["weight"],
        }
    ]
    source.append(key_stage)
    source.append(
        {
            "type": "condition",
            "condition": _classifier_condition(),
            "pool": [
                biome_catalog.BIOMES_BY_KEY[
                    biome_catalog.KEY_BIOME_ALTERNATE_KEY
                ]["identifier"]
            ],
        }
    )
    for entry in biome_catalog.RARE_KEY_BIOMES:
        companion_key = biome_catalog.RARE_KEY_COMPANION_KEYS[entry["key"]]
        companion = biome_catalog.BIOMES_BY_KEY[companion_key]
        source.append(
            {
                "type": "associated",
                "core_biome": entry["identifier"],
                "associated_biomes": [
                    {
                        "biome_type": companion["identifier"],
                        "relative_pos": [offset_x, offset_z],
                    }
                    for offset_x, offset_z in CARDINAL_OFFSETS
                ],
            }
        )
    source.append({"type": "fuzzy_zoom_2x"})
    source.extend({"type": "vanilla_zoom_2x"} for _index in range(6))
    stream = biome_catalog.BIOMES_BY_KEY["stream"]["identifier"]
    source.extend(
        {
            "type": "transition",
            "biome_a": first,
            "biome_b": second,
            "biome_transition": stream,
        }
        for first, second in biome_catalog.STREAM_TRANSITION_IDENTIFIER_PAIRS
    )
    return source


def candidate_document():
    document = copy.deepcopy(build_dark_forest_biomes.dimension_document())
    document["netease:dimension_info"]["components"][
        "netease:biome_source"
    ] = candidate_biome_source()
    return document


def main():
    parser = argparse.ArgumentParser(
        description="write the benchmark-only upstream associated candidate"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(candidate_document(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote biome performance candidate %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
