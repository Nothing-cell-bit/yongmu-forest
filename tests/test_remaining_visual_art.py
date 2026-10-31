"""Cosmetic contracts: preserve UV, alpha, state and native resource scope."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from tools.block_texture_beautification import normalize_resource_document

ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / 'TwilightBossSliceR'
BANK = ROOT / 'resource_art/remaining_visuals/v1'
MANIFEST = json.loads((BANK / 'manifest.json').read_text(encoding='utf-8'))

def pixels(path):
    return np.array(Image.open(path).convert('RGBA'))

@pytest.mark.parametrize('entry', MANIFEST['entries'], ids=lambda e: e['output_relative'])
def test_original_dimensions_alpha_and_material_budget(entry):
    old_path = BANK / 'source_baselines' / entry['output_relative']
    current_path = RP / (entry['runtime_path'] + '.png')
    assert hashlib.sha256(old_path.read_bytes()).hexdigest() == entry['source_sha256']
    assert hashlib.sha256(current_path.read_bytes()).hexdigest() == entry['output_sha256']
    assert current_path.read_bytes() == (BANK / 'assets' / entry['output_relative']).read_bytes()
    old, new = pixels(old_path), pixels(current_path)
    assert list(Image.open(current_path).size) == entry['native_size']
    assert old.shape == new.shape
    assert np.array_equal(old[:, :, 3], new[:, :, 3])
    assert np.array_equal(old[old[:, :, 3] == 0], new[old[:, :, 3] == 0])
    assert int((old != new).any(2).sum()) == entry['changed_pixels'] > 0
    assert np.abs(old.astype(int) - new.astype(int)).max() <= 55
    if entry['source_kind'] == 'project':
        from tools.retired_runtime_pngs import original_texture
        source = original_texture(RP / (entry['source_runtime_path'] + '.png'), ROOT)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == entry['source_sha256']
    if 'twilight_sky/' in entry['output_relative']:
        for region in [np.s_[:16, :], np.s_[-16:, :], np.s_[:, :16], np.s_[:, -16:]]:
            assert np.array_equal(old[region], new[region])
        background = old[:, :, :3].max(2) <= 90
        assert np.array_equal(old[background], new[background])
    if 'magic_map_icons/' in entry['output_relative']:
        outline = old[:, :, :3].max(2) <= 25
        assert np.array_equal(old[outline], new[outline])

def test_all_fire_frames_and_only_two_particle_regions_have_detail():
    old = pixels(BANK / 'source_baselines/native/blocks/fire_0.png')
    new = pixels(RP / 'textures/tf_beautified/remaining/native/blocks/fire_0.png')
    assert old.shape == new.shape == (512, 16, 4)
    for frame in range(32):
        assert (old[frame*16:(frame+1)*16] != new[frame*16:(frame+1)*16]).any()
    old = pixels(BANK / 'source_baselines/native/particle/particles.png')
    new = pixels(RP / 'textures/tf_beautified/remaining/native/particle/particles.png')
    allowed = np.zeros((128, 128), dtype=bool)
    for region in [np.s_[24:32, 0:8], np.s_[40:48, 8:16]]:
        allowed[region] = True
        assert (old[region] != new[region]).any()
    assert np.array_equal(old[~allowed], new[~allowed])

def test_protected_palette_and_ur_ghast_assets():
    from tools.retired_runtime_pngs import original_texture
    for relative, digest in MANIFEST['protected_files'].items():
        source = original_texture(ROOT / relative, ROOT)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    for relative in MANIFEST['excluded_documents']:
        path = RP / relative
        value = json.loads(path.read_text(encoding='utf-8'))
        assert normalize_resource_document(path, value) == value

def test_real_writer_routes_armor_and_helpers_without_empty_animation_nodes():
    path = RP / 'attachables/fiery_chestplate.attachable.json'
    original = {'textures': {'default': 'textures/models/tf_slice/armor/fiery_1', 'enchanted': 'textures/misc/enchanted_actor_glint'}}
    rewritten = normalize_resource_document(path, original)
    assert rewritten['textures']['default'] == 'textures/tf_beautified/remaining/models/tf_slice/armor/fiery_1'
    assert rewritten['textures']['enchanted'] == original['textures']['enchanted']
    assert normalize_resource_document(path, rewritten) == rewritten
    segment = json.loads((RP / 'entity/forest_wyrm_segment.entity.json').read_text())['minecraft:client_entity']['description']
    assert 'animations' not in segment
    assert 'animate' not in segment.get('scripts', {})

def test_external_native_routes_are_document_scoped():
    data = {'texture': 'textures/particle/particles'}
    changed = normalize_resource_document(RP / 'particles/hydra_flame.json', data)
    assert changed['texture'] == 'textures/tf_beautified/remaining/native/particle/particles'
    assert normalize_resource_document(RP / 'particles/unrelated.json', data) == data
    data = {'texture': 'textures/blocks/slime'}
    assert normalize_resource_document(RP / 'particles/slime_splash.json', data)['texture'] == 'textures/tf_beautified/base/slime'
    assert normalize_resource_document(RP / 'particles/unrelated.json', data) == data

def test_every_current_resource_document_is_already_routed():
    from tools.remaining_visual_overrides import apply_remaining_visual_overrides
    for path in RP.rglob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        assert apply_remaining_visual_overrides(path, data) == data, str(path)

def test_dynamic_map_marker_and_sky_paths_exist():
    bp = ROOT / 'TwilightBossSliceB/TwilightBossSlice'
    prefix = 'textures/tf_beautified/remaining/ui/tf_slice/'
    for name in ['magicMapUI.py', 'magicMapHudUI.py']:
        code = (bp / name).read_text(encoding='utf-8')
        assert '"' + prefix + 'magic_map_player/" + direction' in code
        assert '"textures/ui/tf_slice/magic_map_icons/' not in code
        for direction in ['north', 'east', 'south', 'west', 'off_map']:
            assert (RP / (prefix + 'magic_map_player/' + direction + '.png')).is_file()
    code = (bp / 'config.py').read_text(encoding='utf-8')
    for direction in ['negative_z', 'positive_x', 'positive_z', 'negative_x', 'positive_y', 'negative_y']:
        # User-requested smaller-star candidate has its own reversible set;
        # the original beautified assets remain governed by the v1 manifest.
        texture = 'textures/environment/twilight_sky_small/' + direction
        assert '"' + texture + '"' in code
        assert (RP / (texture + '.png')).is_file()
