"""Adapt the native grass color lookup data, retaining every native block ID.

Only a reserved fire-swamp climate footprint is changed. Other native and
Twilight climates, including temperature lowering, are checked for collisions.
This is deterministic lookup-table data processing, not texture artwork.
Write canonical output only after approval of the generated-artifact rebuild.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'resource_art/grass_palette_sources/netease-3.9'
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import biome_catalog

TARGET = (0x57, 0x2E, 0x23, 255)
# Includes float32-vs-double rounding and immediate filtering neighbors.
PATCH = frozenset((x, y) for x in (0, 1) for y in (151, 152, 153, 154))


def sample_index(temperature, downfall):
    temperature = max(0.0, min(1.0, float(temperature)))
    humidity = max(0.0, min(1.0, float(downfall))) * temperature
    return (int((1.0 - temperature) * 255), int((1.0 - humidity) * 255))


def build(output, extra_climates=()):
    metadata = json.loads((SOURCES / 'source.json').read_text(encoding='utf-8'))
    source = SOURCES / 'grass.png'
    if hashlib.sha256(source.read_bytes()).hexdigest() != metadata['palette_sha256']:
        raise ValueError('Locked native grass palette changed')
    fire = biome_catalog.BIOMES_BY_KEY['fire_swamp']
    if sample_index(fire['temperature'], fire['downfall']) not in PATCH:
        raise ValueError('Fire swamp climate no longer matches the reserved footprint')
    profile = json.loads((ROOT / 'resource_art/biome_profiles' / (fire['identifier'] + '.client_biome.json')).read_text(encoding='utf-8'))
    expected = profile['minecraft:client_biome']['components']['minecraft:grass_appearance']['color']
    if expected.upper() != '#572E23':
        raise ValueError('Locked fire swamp grass color changed')
    protected = list(metadata['native_climates']) + [b for b in biome_catalog.BIOMES if b['key'] != 'fire_swamp'] + list(extra_climates)
    for biome in protected:
        # A hot biome must not enter the footprint if its temperature is
        # lowered by elevation. All colder biomes remain to its right.
        for step in range(257):
            temperature = min(1.0, biome['temperature']) * step / 256.0
            if sample_index(temperature, biome['downfall']) in PATCH:
                raise ValueError('Grass palette climate collision: ' + biome['identifier'])
    with Image.open(source) as image:
        image = image.convert('RGBA')
        if image.size != (256, 256):
            raise ValueError('Native grass palette must be 256x256')
        for point in PATCH:
            image.putpixel(point, TARGET)
        destination = Path(output) / 'textures/colormap/grass.png'
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, optimize=True)
    return {'source_sha256': metadata['palette_sha256'],
            'output_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'changed_texels': len(PATCH), 'target': '#572E23',
            'native_climates_checked': len(metadata['native_climates']),
            'other_twilight_climates_checked': len(biome_catalog.BIOMES) - 1,
            'extra_climates_checked': len(extra_climates),
            'scope': 'Native grass lookup only; runtime world tint and native side rendering require acceptance'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Resource-pack root')
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
