# -*- coding: utf-8 -*-
"""Normalize collision boxes for solid NetEase custom-geometry blocks."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOCKS = ROOT / "TwilightBossSliceB" / "netease_blocks"
FULL_BLOCK_BOX = {
    "min": [0.0, 0.0, 0.0],
    "max": [1.0, 1.0, 1.0],
}


def _has_volume(box):
    if isinstance(box, list):
        return any(_has_volume(value) for value in box)
    if not isinstance(box, dict):
        return False
    minimum = box.get("min")
    maximum = box.get("max")
    return (
        isinstance(minimum, list)
        and isinstance(maximum, list)
        and len(minimum) == 3
        and len(maximum) == 3
        and all(float(maximum[index]) > float(minimum[index]) for index in range(3))
    )


def ensure_solid_block_collisions(block_root=BLOCKS):
    changed = []
    for path in sorted(Path(block_root).glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        components = document.get("minecraft:block", {}).get("components", {})
        if not (
            components.get("minecraft:geometry")
            and components.get("netease:solid", {}).get("value") is True
        ):
            continue

        aabb = components.get("netease:aabb")
        if not isinstance(aabb, dict):
            aabb = {}
            components["netease:aabb"] = aabb

        updated = False
        for box_name in ("collision", "clip"):
            if not _has_volume(aabb.get(box_name)):
                aabb[box_name] = {
                    "min": list(FULL_BLOCK_BOX["min"]),
                    "max": list(FULL_BLOCK_BOX["max"]),
                }
                updated = True

        if updated:
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed.append(path)
    return changed


if __name__ == "__main__":
    updated_paths = ensure_solid_block_collisions()
    print("updated solid custom block collisions: %d" % len(updated_paths))
