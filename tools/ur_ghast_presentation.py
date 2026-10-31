"""Approved yellow-stain presentation; Twilight geometry/logic stay locked.

User-directed palette adaptation retains original Twilight pixels and shading.
Only tears use Mojang's hash-verified 1.20.1 ghast-tear PNG, unchanged.
"""

from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tools/references/minecraft_java_1_20_1/ghast_presentation"
YELLOW_REFERENCE = ROOT / "tools/references/ur_ghast_review_20261009"
OVERRIDES = {
    "towerboss.png": "ur_ghast_yellow.png",
    "towerboss_openeyes.png": "ur_ghast_open_yellow.png",
    "towerboss_fire.png": "ur_ghast_attack_yellow.png",
}


def texture_source(original):
    original = Path(original)
    if original.name == "fiery_tears.png":
        return REFERENCE / "ghast_tear.png"
    replacement = OVERRIDES.get(original.name)
    return YELLOW_REFERENCE / replacement if replacement else original


def yellow_stain_image(original):
    """Change red hue to yellow, preserving HSL lightness/saturation and alpha.

    A red-dominant pixel has R=max(R,G,B). Yellow has R=G=max and B=min.
    Keeping both extrema preserves lightness, saturation and shade ordering;
    the original lattice, gradient footprint and all neutral pixels stay exact.
    """
    image = Image.open(original).convert("RGBA")
    pixels = []
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = image.getpixel((x, y))
            if alpha and red > green and red > blue:
                pixels.append((red, red, min(green, blue), alpha))
            else:
                pixels.append((red, green, blue, alpha))
    image.putdata(pixels)
    return image
