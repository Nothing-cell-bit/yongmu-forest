"""Regression: crossing a biome edge must not swap straight to its final sky."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice import biome_sky
from tests.test_guarded_environment import setup, ready

FOREST = 'dm33027004_plains'
SWAMP = 'dm33027004_swampland'
ENCHANTED = 'dm33027004_birch_forest_mutated'


def palette(biome):
    return biome_sky.textures_for_biome(biome)


def rgb(textures):
    color = biome_sky.color_from_textures(textures)
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def advance(blend, ticks=1):
    results = []
    for _ in range(ticks):
        textures = blend.next_textures()
        blend.applied(textures)
        results.append(textures)
    return results


def initial(blend):
    blend.set_target(palette(FOREST))
    blend.set_target(palette(FOREST))
    advance(blend, 2)


def test_crossing_swamp_has_intermediate_colors_and_limited_change_per_step():
    blend = biome_sky.SkyTransition(palette(FOREST))
    initial(blend)
    blend.set_target(palette(SWAMP))
    blend.set_target(palette(SWAMP))
    frames = [palette(FOREST)] + advance(blend, 30)
    assert frames[-1] != palette(SWAMP)  # Do not rush subtle changes in <1s.
    frames += advance(blend, 70)
    assert frames[1] != palette(SWAMP)
    assert frames[-1] == palette(SWAMP)
    distinct = [rgb(frames[0])]
    for old, new in zip(frames, frames[1:]):
        a, b = rgb(old), rgb(new)
        assert max(abs(x - y) for x, y in zip(a, b)) <= 8
        if b != distinct[-1]:
            distinct.append(b)
    assert len(distinct) > 5


def test_border_jitter_requires_two_consecutive_samples_of_same_palette():
    blend = biome_sky.SkyTransition(palette(FOREST))
    initial(blend)
    for _ in range(20):
        blend.set_target(palette(SWAMP))
        advance(blend, 15)
        blend.set_target(palette(FOREST))
        assert advance(blend, 15)[-1] == palette(FOREST)


def test_reverse_and_third_biome_retarget_continue_from_displayed_color():
    blend = biome_sky.SkyTransition(palette(FOREST))
    initial(blend)
    blend.set_target(palette(SWAMP)); blend.set_target(palette(SWAMP))
    frames = advance(blend, 8)
    blend.set_target(palette(FOREST)); blend.set_target(palette(FOREST))
    frames += advance(blend, 4)
    blend.set_target(palette(ENCHANTED)); blend.set_target(palette(ENCHANTED))
    frames += advance(blend, 160)
    assert frames[-1] == palette(ENCHANTED)
    for old, new in zip(frames, frames[1:]):
        assert max(abs(a - b) for a, b in zip(rgb(old), rgb(new))) <= 8


def test_failed_write_does_not_advance_to_another_step():
    blend = biome_sky.SkyTransition(palette(FOREST))
    initial(blend)
    blend.set_target(palette(SWAMP)); blend.set_target(palette(SWAMP))
    proposed = blend.next_textures()
    assert proposed != palette(SWAMP)
    for _ in range(20):
        assert blend.next_textures() == proposed


def test_controller_uses_intermediates_and_keeps_failure_retries_bounded():
    env, factory, component = setup()
    env.textures = palette(FOREST)
    env.base_textures = palette(FOREST)
    env.texture_transition = biome_sky.SkyTransition(palette(FOREST))
    desired = palette(FOREST)
    env.texture_provider = lambda: desired[:]
    env.texture_poll_ticks = 1
    writes = []
    component.SetSkyTextures.side_effect = lambda textures: writes.append(textures[:]) or True
    component.GetSkyTextures.side_effect = lambda: writes[-1][:]
    ready(env)
    for _ in range(3):
        env.render_frame(False)
    assert not env.tick(False)
    assert env.tick(False)
    desired = palette(SWAMP)
    for _ in range(100):
        env.render_frame(False); env.tick(False)
    assert len(writes) > 5
    assert writes[-1] == palette(SWAMP)
    for a, b in zip(writes, writes[1:]):
        assert max(abs(x - y) for x, y in zip(rgb(a), rgb(b))) <= 8
    assert factory.call_count == 1  # Healthy renderer is reused through a fade.
    desired = palette(ENCHANTED)
    component.SetSkyTextures.side_effect = lambda _: False
    count = component.SetSkyTextures.call_count
    for _ in range(200):
        env.render_frame(False); env.tick(False)
    assert component.SetSkyTextures.call_count - count == 3


def test_all_pairs_have_symmetric_finite_paths_without_missing_steps():
    import itertools
    colors = sorted({biome_sky.DEFAULT_COLOR} | set(biome_sky.ENVIRONMENT_COLORS.values()))
    for a, b in itertools.combinations(colors, 2):
        path = biome_sky.transition_colors(a, b)
        assert path[0] == a and path[-1] == b
        assert path == list(reversed(biome_sky.transition_colors(b, a)))
        assert len(path) == 33
        for old, new in zip(path, path[1:]):
            left = rgb(biome_sky.textures_for_color(old))
            right = rgb(biome_sky.textures_for_color(new))
            assert max(abs(x - y) for x, y in zip(left, right)) <= 8


@pytest.mark.parametrize('textures', [None, [], ['bad'] * 6,
    ['textures/environment/twilight_sky_biomes/gggggg/' + name for name in biome_sky.FACE_NAMES]])
def test_unknown_texture_sets_cannot_start_transition(textures):
    assert biome_sky.color_from_textures(textures) is None
    with pytest.raises(ValueError):
        biome_sky.SkyTransition(textures)
    blend = biome_sky.SkyTransition(palette(FOREST))
    initial(blend)
    blend.set_target(textures)
    assert advance(blend, 10)[-1] == palette(FOREST)


def test_failed_step_recovers_after_goal_changes_and_lifecycle_still_blocks_calls():
    env, factory, component = setup()
    env.textures = env.base_textures = palette(FOREST)
    env.texture_transition = biome_sky.SkyTransition(palette(FOREST))
    desired = palette(FOREST)
    env.texture_provider = lambda: desired[:]
    env.texture_poll_ticks = 1
    written = []
    component.SetSkyTextures.side_effect = lambda textures: written.append(textures[:]) or True
    component.GetSkyTextures.side_effect = lambda: written[-1][:]
    ready(env)
    for _ in range(3): env.render_frame(False)
    assert not env.tick(False)
    assert env.tick(False)
    desired = palette(SWAMP)
    component.SetSkyTextures.side_effect = lambda _: False
    for _ in range(100): env.render_frame(False); env.tick(False)
    assert not env.active
    component.SetSkyTextures.side_effect = lambda textures: written.append(textures[:]) or True
    desired = palette(ENCHANTED)
    for _ in range(100): env.render_frame(False); env.tick(False)
    assert env.active and written[-1] == palette(ENCHANTED)
    component.reset_mock()
    factory.reset_mock()
    env.begin_change(); env.finish_change(0)
    for _ in range(100): env.render_frame(False); env.tick(False)
    factory.assert_not_called()
    assert component.mock_calls == []


def test_initial_join_and_ui_recreation_choose_current_biome_without_stale_fade():
    blend = biome_sky.SkyTransition(palette(FOREST))
    blend.set_target(palette(SWAMP))
    assert blend.next_textures() is None
    blend.set_target(palette(SWAMP))
    assert advance(blend)[0] == palette(SWAMP)
    blend.reset()
    blend.set_target(palette(ENCHANTED))
    assert blend.next_textures() is None
    blend.set_target(palette(ENCHANTED))
    assert advance(blend)[0] == palette(ENCHANTED)
    assert biome_sky.transition_colors('#000000', '#000000') == ['#000000']
    source = (ROOT / 'TwilightBossSliceB/TwilightBossSlice/clientSystem.py').read_text(encoding='utf-8')
    assert 'texture_transition=biome_sky.SkyTransition(config.TWILIGHT_SKY_TEXTURES)' in source


def test_generated_transition_frames_have_exact_background_and_identical_star_indices(tmp_path):
    from tools import build_biome_skyboxes as builder
    from PIL import Image
    result = builder.build_transitions(tmp_path)
    colors = builder.transition_palette_colors()
    assert result['faces'] == len(colors) * 6
    masks = {}
    for color in colors:
        expected = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
        for name, texture in zip(biome_sky.FACE_NAMES, biome_sky.textures_for_color(color)):
            path = tmp_path / (texture + '.png')
            with Image.open(path) as image:
                assert image.mode == 'P'
                assert image.size == (512, 512)
                assert max(image.convert('RGBA').getcolors(512 * 512))[1] == expected
                if name not in masks:
                    masks[name] = image.tobytes()
                assert image.tobytes() == masks[name]
