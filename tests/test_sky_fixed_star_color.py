"""Native boundary contracts; these tests do not certify rendered frames."""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

import pytest
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import biome_sky
from TwilightBossSlice.twilight_environment import GuardedEnvironment
from tests.test_guarded_environment import ready


def scene():
    native = mock.Mock()
    color = [(.1, .2, .3, 1.)]
    textures = [[]]
    native.GetUseSkyColor.return_value = False
    native.GetSkyColor.side_effect = lambda: color[0]
    def set_color(value):
        color[0] = value
        native.GetUseSkyColor.return_value = True
        return True
    native.SetSkyColor.side_effect = set_color
    native.GetSkyTextures.side_effect = lambda: textures[0]
    native.SetSkyTextures.side_effect = lambda value: textures.__setitem__(0, value[:]) or True
    factory = mock.Mock(return_value=native)
    desired = [biome_sky.textures_for_biome('dm33027004_plains')]
    env = GuardedEnvironment(33027004, desired[0], factory, wait_frames=3,
        texture_provider=lambda: desired[0], texture_poll_ticks=1,
        texture_transition=biome_sky.SkyTransition(desired[0]),
        star_textures=biome_sky.STAR_TEXTURES, color_decoder=biome_sky.rgba_from_textures)
    ready(env)
    return env, native, factory, desired, color


def run(env, ticks=120):
    for _ in range(ticks):
        env.render_frame(False); env.tick(False)


def test_real_controller_crosses_all_biomes_without_replacing_star_textures():
    env, native, _, desired, _ = scene()
    run(env)
    native.SetSkyTextures.assert_called_once_with(biome_sky.STAR_TEXTURES)
    for biome in biome_sky.ENVIRONMENT_COLORS:
        desired[0] = biome_sky.textures_for_biome(biome)
        run(env, 150)
        assert env.active
        assert native.SetSkyColor.call_args.args[0] == biome_sky.rgba_from_textures(desired[0])
    native.SetSkyTextures.assert_called_once()
    colors = [call.args[0] for call in native.SetSkyColor.call_args_list]
    for left, right in zip(colors, colors[1:]):
        assert max(abs(a-b) for a,b in zip(left, right)) <= 8 / 255.0 + 1e-9
    before = len(colors)
    run(env, 500)
    assert native.SetSkyColor.call_count == before


def test_real_client_constructor_selects_fixed_stars_and_color_backend():
    source = (ROOT / 'TwilightBossSliceB/TwilightBossSlice/clientSystem.py').read_text(encoding='utf-8')
    call = source.split('self._guarded_environment = ', 1)[1].split('self._guarded_environment_last_status', 1)[0].strip()
    obj = SimpleNamespace(_create_guarded_sky_component=lambda: None,
        _get_twilight_biome_sky_textures=lambda: None)
    env = eval(call, {'self':obj, 'biome_sky':biome_sky,
        'twilight_environment':SimpleNamespace(GuardedEnvironment=GuardedEnvironment),
        'config':SimpleNamespace(DIMENSION_ID=33027004,TWILIGHT_POST_ENTRY_ENVIRONMENT_FRAMES=60,
                               TWILIGHT_SKY_TEXTURES=biome_sky.textures_for_color(biome_sky.DEFAULT_COLOR))})
    assert env.star_textures == biome_sky.STAR_TEXTURES
    assert env.color_decoder is biome_sky.rgba_from_textures


def test_delayed_color_readback_polls_without_resubmitting_or_advancing():
    env, native, _, desired, color = scene()
    run(env)
    native.SetSkyColor.side_effect = lambda _: True  # Native accepts but readback lags.
    desired[0] = biome_sky.textures_for_biome('dm33027004_swampland')
    before = native.SetSkyColor.call_count
    run(env, 20)
    assert native.SetSkyColor.call_count == before + 1
    assert env.awaiting_readback and not env.active
    color[0] = native.SetSkyColor.call_args.args[0]
    assert env.tick(False)
    native.SetSkyTextures.assert_called_once()


def test_color_rejection_is_bounded_and_never_reloads_stars():
    env, native, _, desired, _ = scene()
    run(env)
    native.SetSkyColor.return_value = False
    native.SetSkyColor.side_effect = None
    before = native.SetSkyColor.call_count
    desired[0] = biome_sky.textures_for_biome('dm33027004_swampland')
    run(env, 500)
    assert native.SetSkyColor.call_count == before + 3
    native.SetSkyTextures.assert_called_once()


@pytest.mark.parametrize('previous_override', [False, True])
def test_exit_restores_previous_color_on_safe_tick_without_old_component_calls(previous_override):
    env, native, factory, _, color = scene()
    native.GetUseSkyColor.return_value = previous_override
    original = color[0]
    run(env)
    native.reset_mock()
    env.begin_change(); env.finish_change(0); env.ui_ready()
    assert native.mock_calls == []
    new = mock.Mock()
    new.GetSkyColor.return_value = color[0]
    new.GetUseSkyColor.return_value = True
    factory.return_value = new
    run(env, 2)
    assert new.mock_calls == []
    run(env, 100)
    assert native.mock_calls == []
    if previous_override:
        new.SetSkyColor.assert_called_once_with(original)
        new.ResetSkyColor.assert_not_called()
    else:
        new.ResetSkyColor.assert_called_once()
    new.SetSkyTextures.assert_not_called()


def test_exit_does_not_override_another_color_owner():
    env, native, _, _, color = scene()
    run(env)
    color[0] = (.9, .8, .7, 1.)
    env.begin_change(); env.finish_change(0); env.ui_ready()
    native.reset_mock()
    run(env)
    native.ResetSkyColor.assert_not_called()
    native.SetSkyColor.assert_not_called()


def test_ui_rebuild_and_reentry_each_allow_one_new_star_submission():
    env, native, _, desired, _ = scene()
    run(env)
    env.ui_ready()
    desired[0] = biome_sky.textures_for_biome('dm33027004_swampland')
    run(env)
    assert native.SetSkyTextures.call_count == 2
    env.begin_change(); env.finish_change(0); env.ui_ready()
    run(env)
    ready(env)
    run(env)
    assert native.SetSkyTextures.call_count == 3


@pytest.mark.parametrize('failure', ['rejected', 'exception'])
def test_exit_restore_failures_are_bounded(failure):
    env, native, factory, _, color = scene()
    run(env)
    env.begin_change(); env.finish_change(0); env.ui_ready()
    new = mock.Mock()
    new.GetSkyColor.return_value = color[0]
    new.GetUseSkyColor.return_value = True
    if failure == 'rejected':
        new.ResetSkyColor.return_value = False
    else:
        new.ResetSkyColor.side_effect = RuntimeError('not ready')
    factory.return_value = new
    run(env, 500)
    assert new.ResetSkyColor.call_count == 3
    new.SetSkyTextures.assert_not_called()


def test_star_layer_matches_original_star_coverage_without_baked_background(tmp_path):
    from tools.build_biome_skyboxes import build_star_layer
    from tools.build_twilight_skybox import build_skybox
    build_star_layer(tmp_path / 'candidate')
    build_skybox(tmp_path / 'reference', star_scale=.55)
    for name in biome_sky.FACE_NAMES:
        path = tmp_path / 'candidate/textures/environment/twilight_stars_alpha' / (name+'.png')
        with Image.open(path) as stars, Image.open(tmp_path / 'reference' / (name+'.png')) as original:
            assert stars.mode == 'RGBA' and stars.size == (512,512)
            assert stars.getchannel('A').getextrema()[0] == 0
            assert stars.getchannel('R').getextrema() == (255,255)
            expected = original.getchannel('R').point(lambda x: round(max(0,x-32)*255/223))
            assert ImageChops.difference(stars.getchannel('A'), expected).getbbox() is None
            for color in biome_sky.ENVIRONMENT_COLORS.values():
                rgb = tuple(int(color[i:i+2],16) for i in (1,3,5))
                rendered = Image.alpha_composite(Image.new('RGBA',stars.size,rgb+(255,)),stars)
                assert rendered.getpixel((0,0))[:3] == rgb
