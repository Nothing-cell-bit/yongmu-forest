"""Initial entry must wait for the actual loaded biome, never flash a fallback."""
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import biome_sky
from tests.test_guarded_environment import setup, ready


def scene():
    env, factory, component = setup()
    env.base_textures = biome_sky.textures_for_biome('dm33027004_plains')
    env.textures = env.base_textures[:]
    env.texture_transition = biome_sky.SkyTransition(env.base_textures)
    env.texture_poll_ticks = 1
    written = []
    component.SetSkyTextures.side_effect = lambda textures: written.append(textures[:]) or True
    component.GetSkyTextures.side_effect = lambda: written[-1][:]
    ready(env)
    for _ in range(3): env.render_frame(False)
    return env, factory, component, written


def test_initial_unknown_biome_never_writes_default_cubemap_then_writes_swamp_once():
    env, factory, component, written = scene()
    current = None
    env.texture_provider = lambda: current
    for _ in range(50):
        env.render_frame(False); env.tick(False)
    factory.assert_not_called()
    assert written == []
    swamp = biome_sky.textures_for_biome('dm33027004_swampland')
    current = swamp
    assert not env.tick(False)
    assert env.tick(False)
    for _ in range(150): env.render_frame(False); env.tick(False)
    assert written == [swamp]
    component.SetSkyTextures.assert_called_once_with(swamp)


def test_initial_changing_biome_does_not_publish_any_intermediate_or_stale_palette():
    env, factory, _, written = scene()
    forest = biome_sky.textures_for_biome('dm33027004_plains')
    swamp = biome_sky.textures_for_biome('dm33027004_swampland')
    provider = mock.Mock(side_effect=[forest, swamp, forest, None, swamp, swamp])
    env.texture_provider = provider
    for _ in range(5):
        assert not env.tick(False)
    factory.assert_not_called()
    assert env.tick(False)
    assert written == [swamp]


def test_ui_rebuild_waits_for_current_biome_instead_of_replaying_previous_sky():
    env, _, _, written = scene()
    forest = biome_sky.textures_for_biome('dm33027004_plains')
    swamp = biome_sky.textures_for_biome('dm33027004_swampland')
    current = forest
    env.texture_provider = lambda: current
    env.tick(False); env.tick(False)
    assert written == [forest]
    env.ui_ready()
    current = None
    for _ in range(10): env.render_frame(False); env.tick(False)
    assert written == [forest]
    current = swamp
    env.tick(False); env.tick(False)
    assert written == [forest, swamp]


def test_missing_or_failed_query_breaks_initial_consecutive_confirmation():
    env, factory, _, written = scene()
    swamp = biome_sky.textures_for_biome('dm33027004_swampland')
    provider = mock.Mock(side_effect=[swamp, RuntimeError('chunk not ready'), swamp, None, swamp, swamp])
    env.texture_provider = provider
    for _ in range(5):
        assert not env.tick(False)
    factory.assert_not_called()
    assert env.tick(False)
    assert written == [swamp]
