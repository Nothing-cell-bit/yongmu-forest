"""Biome sky selection through the guarded client entry, without a game launch."""
import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from tests.test_guarded_environment import setup, ready, TEXTURES
from tests.test_fortification_lifecycle_runtime import load_methods


def test_guarded_tick_follows_biome_and_returns_to_original_sky():
    env, _, component = setup()
    desired = TEXTURES[:]
    provider = mock.Mock(side_effect=lambda: desired[:])
    env.texture_provider = provider
    env.texture_poll_ticks = 2
    component.GetSkyTextures.side_effect = lambda: env.textures[:]
    ready(env)
    for _ in range(2):
        env.render_frame(False)
        env.tick(False)
    provider.assert_not_called()
    env.render_frame(False)
    assert env.tick(False)
    desired = ['textures/swamp/' + str(i) for i in range(6)]
    for _ in range(3):
        env.render_frame(False)
        env.tick(False)
    assert component.SetSkyTextures.call_args.args[0] == desired
    for _ in range(50):
        env.render_frame(False)
        env.tick(False)
    assert component.SetSkyTextures.call_count == 2
    desired = TEXTURES[:]
    for _ in range(3):
        env.render_frame(False)
        env.tick(False)
    assert component.SetSkyTextures.call_args.args[0] == TEXTURES
    assert component.SetSkyTextures.call_count == 3
    component.reset_mock()
    provider.reset_mock()
    env.begin_change()
    env.finish_change(0)
    for _ in range(10):
        env.render_frame(False)
        env.tick(False)
    provider.assert_not_called()
    assert component.mock_calls == []


def test_client_biome_query_uses_loaded_position_tuple_and_negative_floor():
    from TwilightBossSlice import biome_sky
    biome = mock.Mock()
    biome.GetBiomeName.return_value = 'minecraft:dm33027004_swampland'
    client_class = load_methods('clientSystem.py', ['_get_twilight_biome_sky_textures'], {
        'clientApi': SimpleNamespace(GetLocalPlayerId=lambda: 'player'),
        'CF': SimpleNamespace(CreatePos=lambda _: SimpleNamespace(GetFootPos=lambda: (-0.2, 70.5, -16.2))),
        'math': math, 'biome_sky': biome_sky,
    })
    client = client_class()
    client._ambient_biome_comp = biome
    assert client._get_twilight_biome_sky_textures() == biome_sky.textures_for_biome('dm33027004_swampland')
    biome.GetBiomeName.assert_called_once_with((-1, 70, -17))


def test_palette_covers_all_declared_biomes_and_matches_environment_fog():
    from TwilightBossSlice import biome_sky, biome_catalog
    from tools.biome_render_compat import legacy_document
    render = legacy_document(ROOT)['biomes']
    for entry in biome_catalog.BIOMES:
        identifier = entry['identifier']
        assert biome_sky.color_for_biome(identifier) == render[identifier]['fog_color'].upper()
        assert len(biome_sky.textures_for_biome(identifier)) == 6
    assert biome_sky.color_for_biome('dm33027004_swampland') == '#003F21'
    assert biome_sky.textures_for_biome(None) is None
    assert biome_sky.textures_for_biome('minecraft:swampland') is None


def test_generator_changes_background_without_changing_star_geometry(tmp_path):
    from tools import build_twilight_skybox as sky
    original = sky.build_skybox(tmp_path / 'default', star_scale=0.55)
    swamp = sky.build_skybox(tmp_path / 'swamp', star_scale=0.55, sky_color=(0, 63, 33, 255))
    assert original == swamp
    import numpy as np
    for name in sky.FACE_NAMES:
        old = np.asarray(Image.open(tmp_path / 'default' / (name + '.png'))).astype(float)
        new = np.asarray(Image.open(tmp_path / 'swamp' / (name + '.png'))).astype(float)
        assert tuple(new[0, 0]) == (0, 63, 33, 255)
        # White-star coverage above each background survives palette changes;
        # allow only the final 8-bit rounding from antialiasing.
        # Lanczos also rings *below* the background. That negative coverage
        # clips at black in a zero-red palette; compare actual star coverage.
        old_mask = np.clip((old[:, :, 0] - 32) / (255 - 32), 0, 1)
        new_mask = np.clip(new[:, :, 0] / 255, 0, 1)
        assert abs(old_mask - new_mask).max() < 0.01


def test_query_failure_keeps_sky_and_recovers_on_later_sample():
    env, _, component = setup()
    provider = mock.Mock(side_effect=[RuntimeError('chunk missing'), None, ['bad'], TEXTURES])
    env.texture_provider = provider
    env.texture_poll_ticks = 1
    ready(env)
    for _ in range(3):
        env.render_frame(False)
    for _ in range(4):
        assert env.tick(False)
    assert env.status()['biomeError'] is None
    component.SetSkyTextures.assert_called_once_with(TEXTURES)


def test_rejected_biome_switch_has_bounded_retries_and_recovers_for_next_biome():
    env, _, component = setup()
    desired = TEXTURES[:]
    env.texture_provider = lambda: desired[:]
    env.texture_poll_ticks = 1
    component.GetSkyTextures.side_effect = lambda: env.textures[:]
    ready(env)
    for _ in range(3):
        env.render_frame(False)
    assert env.tick(False)
    desired = ['textures/swamp/' + str(i) for i in range(6)]
    component.SetSkyTextures.return_value = False
    for _ in range(100):
        env.render_frame(False)
        env.tick(False)
    assert component.SetSkyTextures.call_count == 4
    assert env.status()['error'] == 'apply_rejected'
    component.SetSkyTextures.return_value = True
    desired = TEXTURES[:]
    assert env.tick(False)
    assert component.SetSkyTextures.call_count == 5


@pytest.mark.parametrize('rgba', [(0, 1, 2), (0, 1, 2, 0), (-1, 0, 0, 255), (0.5, 1, 2, 255)])
def test_generator_rejects_invalid_background_before_writing(tmp_path, rgba):
    from tools import build_twilight_skybox as sky
    with pytest.raises(ValueError):
        sky.build_skybox(tmp_path / 'invalid', sky_color=rgba)
    assert not (tmp_path / 'invalid').exists()


def test_saved_ui_recreation_resamples_current_biome():
    env, _, component = setup()
    desired = ['textures/swamp/' + str(i) for i in range(6)]
    env.texture_provider = lambda: desired[:]
    env.texture_poll_ticks = 15
    component.GetSkyTextures.side_effect = lambda: env.textures[:]
    ready(env)
    for _ in range(3):
        env.render_frame(False)
    assert env.tick(False)
    desired = TEXTURES[:]
    env.ui_ready()
    assert not env.tick(False)
    for _ in range(3):
        env.render_frame(False)
    assert env.tick(False)
    assert component.SetSkyTextures.call_args.args[0] == TEXTURES


def test_all_palette_resources_close_and_default_stars_remain_byte_identical(tmp_path):
    from TwilightBossSlice import biome_sky, biome_catalog
    from tools import build_biome_skyboxes as builder
    from tools import build_twilight_skybox as sky
    results = builder.build(tmp_path)
    assert len(results) == 6
    assert {result['accepted_stars'] for result in results.values()} == {1554}
    for entry in biome_catalog.BIOMES:
        color = biome_sky.color_for_biome(entry['identifier'])
        rgb = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
        for texture in biome_sky.textures_for_biome(entry['identifier']):
            path = (ROOT / 'TwilightBossSliceR' if color == biome_sky.DEFAULT_COLOR else tmp_path) / (texture + '.png')
            with Image.open(path) as face:
                assert face.size == (512, 512)
                assert face.mode == 'RGBA'
                assert face.getchannel('A').getextrema() == (255, 255)
                # A corner can contain an upstream star or Lanczos ringing.
                # The dominant background, rather than any chosen pixel,
                # must match this biome's environment color exactly.
                assert max(face.getcolors(512 * 512))[1] == rgb + (255,)
    sky.build_skybox(tmp_path / 'default', star_scale=0.55)
    for name in sky.FACE_NAMES:
        assert (tmp_path / 'default' / (name + '.png')).read_bytes() == (
            ROOT / 'TwilightBossSliceR/textures/environment/twilight_sky_small' / (name + '.png')).read_bytes()


def test_builder_rejects_palette_drift_before_any_resource_write(tmp_path, monkeypatch):
    from tools import build_biome_skyboxes as builder
    monkeypatch.setitem(builder.biome_sky.ENVIRONMENT_COLORS, 'dm33027004_swampland', '#FFFFFF')
    with pytest.raises(ValueError, match='palette drift'):
        builder.build(tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_real_client_tick_applies_current_biome_only_after_entry_gates():
    from TwilightBossSlice import biome_sky
    env, factory, component = setup()
    biome = mock.Mock()
    biome.GetBiomeName.return_value = 'dm33027004_swampland'
    namespace = {
        'config': SimpleNamespace(TWILIGHT_POST_ENTRY_ENVIRONMENT_ENABLED=True),
        'clientApi': SimpleNamespace(GetLocalPlayerId=lambda: 'player'),
        'CF': SimpleNamespace(CreatePos=lambda _: SimpleNamespace(GetFootPos=lambda: (0, 70, 0))),
        'math': math, 'biome_sky': biome_sky,
    }
    cls = load_methods('clientSystem.py', ['_update_guarded_environment',
                                         '_get_twilight_biome_sky_textures'], namespace)
    client = cls()
    client._guarded_environment = env
    client._ambient_biome_comp = biome
    client._portal_loading_active = True
    client._guarded_environment_last_status = None
    client._log_twilight_sky = mock.Mock()
    env.texture_provider = client._get_twilight_biome_sky_textures
    component.GetSkyTextures.side_effect = lambda: env.textures[:]
    ready(env)
    for _ in range(30):
        env.render_frame(True)
        client._update_guarded_environment()
    biome.GetBiomeName.assert_not_called()
    factory.assert_not_called()
    client._portal_loading_active = False
    for _ in range(3):
        env.render_frame(False)
        client._update_guarded_environment()
    assert env.active
    component.SetSkyTextures.assert_called_once_with(biome_sky.textures_for_biome('dm33027004_swampland'))
    source = (ROOT / 'TwilightBossSliceB/TwilightBossSlice/clientSystem.py').read_text(encoding='utf-8')
    assert 'texture_provider=self._get_twilight_biome_sky_textures' in source
