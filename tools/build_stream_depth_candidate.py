"""Build a one-component river-height candidate without rebuilding worldgen.

The locked Java stream uses its custom 5x5 terrain warp. Its -1.65/.25 values
are not NetEase units. This candidate removes the port's shallow override and
uses an explicitly selected target-client native preset for calibration.
It is not a claim of Java voxel parity, a fixed water depth, or measured speed.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HEIGHT = "minecraft:overworld_height"


def build_candidate(source, native, preset="river"):
    if preset not in ("river", "ocean"):
        raise ValueError("Unreviewed native calibration profile")
    source_biome = source.get("minecraft:biome", {})
    description = source_biome.get("description", {})
    if description != {"identifier": "dm33027004_river", "inherits": "river"}:
        raise ValueError("Expected the existing Twilight stream biome")
    native_biome = native.get("minecraft:biome", {})
    if native_biome.get("description", {}).get("identifier") != "minecraft:" + preset:
        raise ValueError("Height donor must match the selected native profile")
    height = native_biome.get("components", {}).get(HEIGHT)
    if height != {"noise_type": preset}:
        raise ValueError("Unreviewed native height preset")
    old = source_biome.get("components", {}).get(HEIGHT)
    if old not in ({"noise_params": [-0.1, 0.0]},
                   {"noise_type": "river"}, {"noise_type": "ocean"}):
        raise ValueError("Unreviewed existing stream height")
    result = copy.deepcopy(source)
    result["minecraft:biome"]["components"][HEIGHT] = copy.deepcopy(height)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--native-river", "--native-biome", dest="native_river",
                        type=Path, required=True)
    parser.add_argument("--profile", choices=("river", "ocean"), default="river")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    inputs = {args.source.resolve(), args.native_river.resolve()}
    if args.output.resolve() in inputs or args.report.resolve() in inputs:
        raise ValueError("Never overwrite either input")
    source_data, native_data = args.source.read_bytes(), args.native_river.read_bytes()
    candidate = build_candidate(json.loads(source_data), json.loads(native_data), args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    report = {"sourceSha256": hashlib.sha256(source_data).hexdigest(),
              "nativeRiverSha256": hashlib.sha256(native_data).hexdigest(),
              "outputSha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
              "changedComponent": HEIGHT, "runtimeAcceptance": "pending",
              "nativePreset": args.profile, "javaParity": "calibration_pending",
              "fixedWaterDepth": None, "additionalBiomeSourceStages": 0,
              "additionalScriptWorldWrites": 0}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
