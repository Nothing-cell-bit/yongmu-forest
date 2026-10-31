"""First cubemap publication remains behind the existing bounded entry cover."""
from types import SimpleNamespace
from unittest import mock
import json

from tests.test_guarded_environment import setup, ready
from tests.test_fortification_lifecycle_runtime import load_methods
from tests.test_fortification_lifecycle_runtime import ROOT
from TwilightBossSlice import twilight_environment


def test_cover_requires_actual_post_apply_frames_and_duplicate_request_is_idempotent():
    cover = twilight_environment.InitialSkyPresentation(settle_frames=3, max_ticks=30)
    cover.request()
    for _ in range(5): cover.frame(False); assert cover.tick(False)
    cover.frame(True); cover.tick(False)
    cover.request()
    cover.frame(True); assert cover.tick(False)
    cover.frame(True); assert not cover.tick(False)
    assert cover.reason == 'settled'
    cover.request()
    assert not cover.active


def test_cover_timeout_and_cancel_cannot_hold_the_screen_forever():
    cover = twilight_environment.InitialSkyPresentation(settle_frames=3, max_ticks=2)
    cover.request()
    assert cover.tick(False)
    assert not cover.tick(False)
    assert cover.reason == 'timeout'
    cover.cancel(); cover.request()
    assert cover.active
    cover.cancel()
    assert not cover.active


def test_real_arrival_tick_keeps_cover_through_apply_and_releases_after_render_frames():
    visible = []
    portal = SimpleNamespace(set_visible=lambda value: visible.append(value))
    cls = load_methods('clientSystem.py', ['OnPortalArrivalFinished', '_end_portal_loading',
        '_update_guarded_environment', 'OnBlockChainRender'], dict(
            config=SimpleNamespace(DIMENSION_ID=33027004, TWILIGHT_POST_ENTRY_ENVIRONMENT_ENABLED=True),
            portalLoadingUI=portal))
    client = cls()
    env, _, component = setup(); ready(env)
    client._guarded_environment = env
    client._initial_sky_presentation = twilight_environment.InitialSkyPresentation(settle_frames=3)
    client._guarded_environment_last_status = None
    client._log_twilight_sky = mock.Mock()
    client._chain_visuals = SimpleNamespace(render=lambda: None)
    client._portal_loading_active = True
    client.OnPortalArrivalFinished({'cancelled': False})
    assert not client._portal_loading_active  # Server movement handshake is finished.
    assert visible[-1] is True
    for _ in range(3): client.OnBlockChainRender(); client._update_guarded_environment()
    component.SetSkyTextures.assert_called_once()
    assert visible[-1] is True
    for _ in range(3): client.OnBlockChainRender(); client._update_guarded_environment()
    assert visible[-1] is False


def test_first_load_cover_is_opaque_to_the_native_black_flash():
    document = json.loads((ROOT / 'TwilightBossSliceR/ui/portal_loading.json').read_text(encoding='utf-8'))
    overlay = document['main']['controls'][0]['overlay']
    assert overlay['alpha'] == 1.0


def test_late_native_finish_does_not_hide_the_initial_cover():
    visible = mock.Mock()
    cls = load_methods('clientSystem.py', ['OnDimensionChangeFinishClientEvent'], dict(
        CF=SimpleNamespace(CreateGame=lambda _: SimpleNamespace(GetCurrentDimension=lambda: 33027004)),
        LEVEL_ID='level', config=SimpleNamespace(DIMENSION_ID=33027004),
        portalLoadingUI=SimpleNamespace(set_visible=visible)))
    client = cls()
    client._is_local_dimension_event = lambda _: True
    client._portal_loading_server_finished = True
    client._portal_loading_active = False
    client._guarded_environment, _, _ = setup()
    client._initial_sky_presentation = twilight_environment.InitialSkyPresentation()
    client._initial_sky_presentation.request()
    client._discard_twilight_sky_renderer_candidate = mock.Mock()
    client._log_twilight_sky = mock.Mock()
    client._update_twilight_sky = mock.Mock()
    client._update_twilight_cloud_layer = mock.Mock()
    client.OnDimensionChangeFinishClientEvent({})
    visible.assert_called_once_with(True)
    assert not client._portal_loading_active
