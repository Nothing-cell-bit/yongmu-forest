"""Preserve native grass IDs and other biome samples while making fire grass red."""
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_fire_swamp_palette_is_red_and_only_its_reserved_texels_change(tmp_path):
    from tools import build_fire_swamp_grass_palette as grass
    report = grass.build(tmp_path)
    source = Image.open(grass.SOURCES / 'grass.png').convert('RGBA')
    result = Image.open(tmp_path / 'textures/colormap/grass.png').convert('RGBA')
    assert result.size == source.size == (256, 256)
    changed = {(x, y) for y in range(256) for x in range(256) if source.getpixel((x, y)) != result.getpixel((x, y))}
    assert changed == {(x, y) for x in (0, 1) for y in (151, 152, 153, 154)}
    assert result.getpixel((0, 153)) == (0x57, 0x2E, 0x23, 255)
    assert report['changed_texels'] == 8
    assert list(tmp_path.rglob('*.png')) == [tmp_path / 'textures/colormap/grass.png']


def test_every_other_declared_biome_and_native_climate_sample_is_unchanged(tmp_path):
    from tools import build_fire_swamp_grass_palette as grass
    from TwilightBossSlice import biome_catalog
    grass.build(tmp_path)
    source = Image.open(grass.SOURCES / 'grass.png').convert('RGBA')
    result = Image.open(tmp_path / 'textures/colormap/grass.png').convert('RGBA')
    native = json.loads((grass.SOURCES / 'source.json').read_text())['native_climates']
    others = [b for b in biome_catalog.BIOMES if b['key'] != 'fire_swamp']
    for biome in native + others:
        # Include temperature lowering as well as each exact base climate.
        for step in range(257):
            t = max(0.0, min(1.0, biome['temperature'])) * step / 256.0
            x = int((1.0 - t) * 255)
            y = int((1.0 - t * biome['downfall']) * 255)
            assert result.getpixel((x, y)) == source.getpixel((x, y)), biome['identifier']


def test_climate_collision_fails_before_any_palette_is_written(tmp_path):
    from tools import build_fire_swamp_grass_palette as grass
    extra = [{'identifier': 'other:hot_wet', 'temperature': 1.0, 'downfall': 0.4}]
    with pytest.raises(ValueError, match='collision'):
        grass.build(tmp_path, extra_climates=extra)
    assert not (tmp_path / 'textures').exists()


def test_build_never_replaces_native_block_or_biome_definitions(tmp_path):
    from tools import build_fire_swamp_grass_palette as grass
    paths = list((ROOT / 'TwilightBossSliceB/netease_biomes').rglob('*.json'))
    paths += list((ROOT / 'TwilightBossSliceB/netease_blocks').glob('*.json'))
    paths += [ROOT / 'TwilightBossSliceR/blocks.json']
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    grass.build(tmp_path)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in before.items())
    fire = json.loads((ROOT / 'TwilightBossSliceB/netease_biomes/dm33027004/dm33027004_swampland_mutated.json').read_text())
    assert fire['minecraft:biome']['components']['minecraft:surface_parameters']['top_material'] == 'minecraft:grass'
