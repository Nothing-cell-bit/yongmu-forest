"""Build biome sky variants into an explicit resource-pack output directory.

Canonical output is a generated-artifact rebuild and needs project approval.
An isolated preview may be built with --output under the task evidence directory.
"""
import argparse
from pathlib import Path
import sys
import itertools
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
sys.path.insert(0, str(ROOT))
from TwilightBossSlice import biome_sky, biome_catalog
from tools.biome_render_compat import legacy_document
from tools.build_twilight_skybox import build_skybox


def build(output, root=ROOT):
    profiles = legacy_document(root)['biomes']
    colors = set()
    for entry in biome_catalog.BIOMES:
        identifier = entry['identifier']
        color = profiles[identifier]['fog_color'].upper()
        if color != biome_sky.color_for_biome(identifier):
            raise ValueError('Biome sky/environment palette drift: ' + identifier)
        if color != biome_sky.DEFAULT_COLOR:
            colors.add(color)
    results = {}
    for color in sorted(colors):
        rgba = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5)) + (255,)
        directory = Path(output) / 'textures/environment/twilight_sky_biomes' / color[1:].lower()
        results[color] = build_skybox(directory, star_scale=0.55, sky_color=rgba)
    return results


def transition_palette_colors():
    endpoints = set(biome_sky.ENVIRONMENT_COLORS.values()) | {biome_sky.DEFAULT_COLOR}
    return sorted({color for a, b in itertools.combinations(sorted(endpoints), 2)
                   for color in biome_sky.transition_colors(a, b)} - endpoints)


def build_transitions(output):
    """Indexed PNGs retain the identical star coverage with compact palettes.

    Render the reference star field once; no runtime pixel processing, texture
    writes, global shaders, or third-party image generation is involved.
    Existing seven endpoint sets remain untouched.
    """
    colors = transition_palette_colors()
    with tempfile.TemporaryDirectory(prefix='twilight-sky-reference-') as directory:
        build_skybox(directory, star_scale=0.55)
        faces = {}
        for name in biome_sky.FACE_NAMES:
            with Image.open(Path(directory) / (name + '.png')) as reference:
                faces[name] = Image.frombytes('P', reference.size, reference.getchannel('R').tobytes())
        for color in colors:
            backgrounds = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
            table = [int(round(background + max(0, value - 32) * (255 - background) / 223.0))
                     for value in range(256) for background in backgrounds]
            destination = Path(output) / 'textures/environment/twilight_sky_biomes' / color[1:].lower()
            destination.mkdir(parents=True, exist_ok=True)
            for name, face in faces.items():
                face.putpalette(table)
                face.save(destination / (name + '.png'), optimize=True)
    return {'palettes': len(colors), 'faces': len(colors) * 6}


def build_star_layer(output):
    """Separate star coverage from its baked background for a fixed cubemap.

    The native cubemap material uses SourceAlpha/OneMinusSrcAlpha blending.
    White RGB plus coverage alpha composites over SetSkyColor without loading
    a different texture for every intermediate color.
    """
    destination = Path(output) / 'textures/environment/twilight_stars_alpha'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='twilight-stars-alpha-') as directory:
        build_skybox(directory, star_scale=0.55)
        table = [int(round(max(0, value - 32) * 255.0 / 223.0))
                 for value in range(256)]
        for name in biome_sky.FACE_NAMES:
            with Image.open(Path(directory) / (name + '.png')) as reference:
                alpha = reference.getchannel('R').point(table)
                image = Image.new('RGBA', reference.size, (255, 255, 255, 0))
                image.putalpha(alpha)
                image.save(destination / (name + '.png'), optimize=True)
    return {'faces': 6, 'mode': 'RGBA', 'background_alpha': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='Resource-pack root receiving the 36 new PNGs')
    parser.add_argument('--transitions-only', action='store_true',
                        help='Write only the intermediate transition palettes')
    parser.add_argument('--stars-only', action='store_true',
                        help='Write only the six fixed transparent star faces')
    args = parser.parse_args()
    if args.stars_only and args.transitions_only:
        parser.error('Choose one generation mode')
    if args.stars_only:
        print(build_star_layer(args.output))
    elif args.transitions_only:
        print(build_transitions(args.output))
    else:
        results = build(args.output)
        print('Built %d biome palettes (%d faces) in %s' % (len(results), len(results) * 6, args.output))


if __name__ == '__main__':
    main()
