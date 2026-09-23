#!/usr/bin/env python3
"""Copy audited Quest Grove assets from Twilight Forest 4.3.2508."""

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "textures"
)
COPIES = (
    ("model/questram.png", "textures/entity/tf_slice/quest_ram.png"),
    ("item/crumble_horn.png", "textures/items/crumble_horn.png"),
    ("item/trophy_quest.png", "textures/blocks/quest_ram_trophy.png"),
)


def main():
    for source_name, target_name in COPIES:
        source = ASSET_ROOT / source_name
        target = ROOT / "TwilightBossSliceR" / target_name
        if not source.is_file():
            raise SystemExit("missing upstream texture: %s" % source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if source.read_bytes() != target.read_bytes():
            raise SystemExit("texture copy verification failed: %s" % target)
        print("%s <- %s" % (target.relative_to(ROOT), source_name))


if __name__ == "__main__":
    main()
