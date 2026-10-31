"""An accepted asynchronous sky write must not repeatedly reset its cubemap."""
from tests.test_guarded_environment import setup, ready, TEXTURES


def test_accepted_texture_write_waits_for_delayed_readback_without_reapplying():
    env, factory, component = setup()
    ready(env)
    component.GetSkyTextures.side_effect = [None] * 8 + [TEXTURES[:]]
    for _ in range(3): env.render_frame(False)
    assert not env.tick(False)
    for _ in range(20):
        env.render_frame(False)
        env.tick(False)
    assert env.active
    component.SetSkyTextures.assert_called_once_with(TEXTURES)
    factory.assert_called_once()


def test_accepted_write_readback_timeout_does_not_keep_replacing_textures():
    env, _, component = setup()
    ready(env)
    component.GetSkyTextures.return_value = None
    for _ in range(400): env.render_frame(False); env.tick(False)
    component.SetSkyTextures.assert_called_once()
    assert not env.active
    assert env.last_error == 'readback_timeout'


def test_readback_exception_can_recover_without_another_write_or_component():
    env, factory, component = setup()
    ready(env)
    component.GetSkyTextures.side_effect = [RuntimeError('texture not ready'), TEXTURES[:]]
    for _ in range(3): env.render_frame(False)
    assert not env.tick(False)
    assert env.tick(False)
    component.SetSkyTextures.assert_called_once()
    factory.assert_called_once()


def test_leaving_cancels_pending_readback_without_calling_detaching_renderer():
    env, _, component = setup()
    ready(env)
    component.GetSkyTextures.return_value = None
    for _ in range(3): env.render_frame(False)
    env.tick(False)
    component.reset_mock()
    env.begin_change(); env.finish_change(0)
    for _ in range(100): env.render_frame(False); env.tick(False)
    assert component.mock_calls == []
