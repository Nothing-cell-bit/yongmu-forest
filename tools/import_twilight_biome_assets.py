#!/usr/bin/env python3
"""Copy the audited 4.3.2508 biome textures into the resource pack."""

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
BLOCK_SOURCE = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "textures"
    / "block"
)
MODEL_SOURCE = BLOCK_SOURCE.parent / "model"
TARGET = ROOT / "TwilightBossSliceR" / "textures" / "blocks"
ASSETS = (
    (BLOCK_SOURCE, "fiddlehead.png", "fiddlehead.png"),
    (BLOCK_SOURCE, "mushgloom.png", "mushgloom.png"),
    (BLOCK_SOURCE, "firefly.png", "firefly.png"),
    (MODEL_SOURCE, "firefly-tiny.png", "firefly_model.png"),
    (BLOCK_SOURCE, "jar_side.png", "jar_side.png"),
    (BLOCK_SOURCE, "jar_side.png", "firefly_jar.png"),
    (BLOCK_SOURCE, "jar_side.png", "cicada_jar.png"),
    (BLOCK_SOURCE, "jar_top.png", "jar_top.png"),
    (BLOCK_SOURCE, "jar_bottom.png", "jar_bottom.png"),
    (
        BLOCK_SOURCE,
        "firefly_jar_cork.png",
        "firefly_jar_cork.png",
    ),
    (
        BLOCK_SOURCE,
        "cicada_jar_cork.png",
        "cicada_jar_cork.png",
    ),
    (
        BLOCK_SOURCE,
        "transformation_leaves.png",
        "rainbow_oak_leaves.png",
    ),
    (BLOCK_SOURCE, "darkwood_leaves.png", "fallen_leaves.png"),
    (BLOCK_SOURCE, "root_strand.png", "root_strand.png"),
    (
        BLOCK_SOURCE,
        "torchberry_plant.png",
        "torchberry_plant.png",
    ),
    (
        BLOCK_SOURCE,
        "torchberry_plant_glow.png",
        "torchberry_plant_glow.png",
    ),
)


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for source_root, source_name, target_name in ASSETS:
        source = source_root / source_name
        if not source.is_file():
            raise SystemExit("missing upstream texture: %s" % source)
        target = TARGET / target_name
        shutil.copyfile(source, target)
        if source.read_bytes() != target.read_bytes():
            raise SystemExit("texture copy verification failed: %s" % target)
        print("%s <- %s" % (target.relative_to(ROOT), source_name))


if __name__ == "__main__":
    main()
