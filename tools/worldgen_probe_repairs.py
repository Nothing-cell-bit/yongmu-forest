"""Scoped canopy/dead-tree placement repair; no full biome build."""
import argparse
import json
from pathlib import Path

from build_spooky_forest import dead_tree_placement_documents
from swamp_tree_placement import tree_placement_documents

FEATURE_PATH = Path("TwilightBossSliceB/netease_features")


def patch_lily_server_hooks(source):
    """Apply only this task's five hooks to a destination's own server file.

    This avoids deploying unrelated concurrent edits from the shared server.
    A missing or ambiguous anchor is a hard error, never a full-file fallback.
    """
    pairs = [
        (
            "from TwilightBossSlice.mushroomWorldgenService import (\n    MushroomWorldgenService\n)\n",
            "from TwilightBossSlice.mushroomWorldgenService import (\n    MushroomWorldgenService\n)\n"
            "from TwilightBossSlice.lilyPadWorldgenService import (\n    LilyPadWorldgenService, TRIGGER as LILY_PAD_CANDIDATE\n)\n",
        ),
        (
            "        try:\n            self._mushroom_worldgen = MushroomWorldgenService(\n",
            "        try:\n"
            "            lilyChunk = CF.CreateChunkSource(LEVEL_ID)\n"
            "            self._lily_pad_worldgen = LilyPadWorldgenService(\n"
            "                CF.CreateFeature(LEVEL_ID), self._get_block, self._set_block,\n"
            "                config.DIMENSION_ID,\n"
            "                lambda position, dimension: bool(lilyChunk.CheckChunkState(dimension, position)),\n"
            "            )\n"
            "        except Exception as error:\n"
            "            self._lily_pad_worldgen = None\n"
            "            print \"[TwilightBossSlice] lily worldgen init failed:\", error\n"
            "        try:\n            self._mushroom_worldgen = MushroomWorldgenService(\n",
        ),
        (
            "        if self._mushroom_worldgen is not None:\n            self._mushroom_worldgen.destroy()\n",
            "        if self._mushroom_worldgen is not None:\n            self._mushroom_worldgen.destroy()\n"
            "        if self._lily_pad_worldgen is not None:\n            self._lily_pad_worldgen.destroy()\n",
        ),
        (
            "        self._update_lifedrain_users()\n",
            "        self._update_lifedrain_users()\n"
            "        if (\n            self._lily_pad_worldgen is not None\n"
            "            and not self._dimension_change_in_progress\n        ):\n"
            "            self._lily_pad_worldgen.tick()\n",
        ),
        (
            "        structureName = str(structureName or \"\")\n"
            "        if structureName.startswith(\"tf_slice:mushroom/canopy_trigger/\"):\n",
            "        structureName = str(structureName or \"\")\n"
            "        if structureName == LILY_PAD_CANDIDATE:\n"
            "            if self._lily_pad_worldgen is not None:\n"
            "                self._lily_pad_worldgen.on_structure_feature_event(args)\n"
            "            return\n"
            "        if structureName.startswith(\"tf_slice:mushroom/canopy_trigger/\"):\n",
        ),
    ]
    for old, new in pairs:
        if source.count(new) == 1:
            continue
        if source.count(old) != 1:
            raise ValueError("Missing or ambiguous lily server hook: " + old.splitlines()[0])
        source = source.replace(old, new, 1)
    return source


def feature_documents():
    documents = tree_placement_documents("canopy")
    documents.update(dead_tree_placement_documents())
    return documents


def removed_features():
    return []


def air_to_air_probes(documents):
    result = []
    for name, document in documents.items():
        if str(name).endswith("huge_lily_pad_clearance_block_feature.json"):
            # This legacy predicate is intentionally a no-op block write. It
            # keeps the following ordinary block feature out of the native
            # transactional structure path that crashes Streaming Pool.
            continue
        if not isinstance(document, dict):
            continue
        feature = document.get("minecraft:single_block_feature", {})
        blocks = feature.get("places_block", [])
        if isinstance(blocks, str):
            blocks = [{"block": blocks}]
        if not isinstance(blocks, list):
            continue
        if any(item.get("block") == "minecraft:air" for item in blocks):
            if "minecraft:air" in feature.get("may_replace", ["minecraft:air"]):
                result.append(str(name))
    return sorted(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--acknowledge-source-pack-write", action="store_true")
    args = parser.parse_args(argv)
    root = args.output_root.resolve()
    canonical = Path(__file__).resolve().parents[1]
    documents = feature_documents()
    if args.write:
        if root == canonical and not args.acknowledge_source_pack_write:
            parser.error("source-pack rebuild requires explicit acknowledgment")
        directory = root / FEATURE_PATH
        directory.mkdir(parents=True, exist_ok=True)
        for name, document in documents.items():
            (directory / name).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        for name in removed_features():
            path = directory / name
            if path.is_file():
                path.unlink()
        print("Wrote %d canopy/dead-tree feature JSONs" % len(documents))
        return 0
    mismatches = []
    for name, expected in documents.items():
        path = root / FEATURE_PATH / name
        if not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != expected:
            mismatches.append(name)
    mismatches.extend(name for name in removed_features() if (root / FEATURE_PATH / name).exists())
    for name in mismatches:
        print("Missing/stale: " + name)
    print("Scoped probe repair: %s" % ("FAIL" if mismatches else "PASS"))
    return int(bool(mismatches))


if __name__ == "__main__":
    raise SystemExit(main())
