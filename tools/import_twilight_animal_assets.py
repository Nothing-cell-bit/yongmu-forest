#!/usr/bin/env python3
"""Copy audited 4.3.2508 small-animal assets into the resource pack."""

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "textures"
    / "model"
)
TARGET = ROOT / "TwilightBossSliceR" / "textures" / "entity" / "tf_slice"
ASSETS = (
    "tinybirdblue.png",
    "tinybirdbrown.png",
    "tinybirdgold.png",
    "tinybirdred.png",
    "squirrel2.png",
    "bunnybrown.png",
    "bunnydutch.png",
    "bunnywhite.png",
)
SOUND_SOURCE = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "sounds"
    / "mob"
    / "tiny_bird"
)
SOUND_TARGET = (
    ROOT / "TwilightBossSliceR" / "sounds" / "mob" / "tiny_bird"
)
SOUNDS = (
    "chirp1.ogg",
    "chirp2.ogg",
    "chirp3.ogg",
    "hurt1.ogg",
    "hurt2.ogg",
    "song1.ogg",
    "song2.ogg",
)


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for filename in ASSETS:
        source = SOURCE / filename
        target = TARGET / filename
        if not source.is_file():
            raise SystemExit("missing upstream texture: %s" % source)
        shutil.copyfile(source, target)
        if source.read_bytes() != target.read_bytes():
            raise SystemExit("texture copy verification failed: %s" % target)
        print("%s <- %s" % (target.relative_to(ROOT), filename))
    SOUND_TARGET.mkdir(parents=True, exist_ok=True)
    for filename in SOUNDS:
        source = SOUND_SOURCE / filename
        target = SOUND_TARGET / filename
        if not source.is_file():
            raise SystemExit("missing upstream sound: %s" % source)
        shutil.copyfile(source, target)
        if source.read_bytes() != target.read_bytes():
            raise SystemExit("sound copy verification failed: %s" % target)
        print("%s <- %s" % (target.relative_to(ROOT), filename))


if __name__ == "__main__":
    main()
