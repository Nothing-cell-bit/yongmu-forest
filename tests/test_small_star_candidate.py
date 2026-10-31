"""User asks for smaller stars, keeping the established sky palette/positions."""
import math
from unittest import mock

import pytest

from tools import build_twilight_skybox as sky


def test_smaller_star_candidate_scales_geometry_without_moving_star_centres(tmp_path):
    with mock.patch.object(sky, '_star_quad', wraps=sky._star_quad) as quads:
        original = sky.build_skybox(tmp_path / 'reference')
        before = list(quads.call_args_list)
        quads.reset_mock()
        smaller = sky.build_skybox(tmp_path / 'small', star_scale=0.55)
        after = list(quads.call_args_list)
    assert original == smaller
    assert len(before) > 1400
    for old, new in zip(before, after):
        assert old.args[0] == new.args[0]  # Seed and direction unchanged.
        assert old.args[2] == new.args[2]  # Rotation unchanged.
        assert math.isclose(new.args[1], old.args[1] * 0.55)
    from PIL import Image
    import numpy as np
    for face in sky.FACE_NAMES:
        old = np.array(Image.open(tmp_path / 'reference' / (face + '.png')))
        new = np.array(Image.open(tmp_path / 'small' / (face + '.png')))
        assert old.shape == new.shape == (512, 512, 4)
        assert np.array_equal(old[:, :, 3], new[:, :, 3])
        assert tuple(new[256, 256]) == tuple(old[256, 256]) == sky.SKY_COLOR
        assert (new[:, :, :3].min(2) > 180).sum() < (old[:, :, :3].min(2) > 180).sum()


@pytest.mark.parametrize('scale', [0, -1, 1.1, float('inf'), float('nan')])
def test_invalid_scale_rejected_before_writing(tmp_path, scale):
    target = tmp_path / 'invalid'
    with pytest.raises(ValueError):
        sky.build_skybox(target, star_scale=scale)
    assert not target.exists()
