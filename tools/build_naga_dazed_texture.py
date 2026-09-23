# -*- coding: utf-8 -*-
"""Build the Cindercoil dazed composite from locally generated textures."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TEXTURE_DIR = ROOT / "TwilightBossSliceR" / "textures" / "entity"
NORMAL = TEXTURE_DIR / "nagahead.png"
EYELIDS = TEXTURE_DIR / "nagahead_dazed.png"
OUTPUT = TEXTURE_DIR / "nagahead_dazed_full.png"


def build() -> None:
    with Image.open(NORMAL) as source:
        normal = source.convert("RGBA")
    with Image.open(EYELIDS) as source:
        eyelids = source.convert("RGBA")
    if normal.size != eyelids.size:
        raise ValueError(
            "Naga base and dazed overlay dimensions differ: %r != %r"
            % (normal.size, eyelids.size)
        )
    # V2 full eyelid tile replaces the eye tile for single-pass previews.
    # Runtime uses the separate eyelid mesh instead.
    normal.paste(eyelids.crop((64, 32, 96, 64)), (32, 32))
    normal.save(
        OUTPUT,
        format="PNG",
        optimize=False,
        compress_level=9,
    )


if __name__ == "__main__":
    build()
