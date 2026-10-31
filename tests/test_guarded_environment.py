import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))
from TwilightBossSlice.twilight_environment import GuardedEnvironment

TEXTURES = ['textures/test/' + str(i) for i in range(6)]

def setup():
    component = mock.Mock()
    component.SetSkyTextures.return_value = True
    component.GetSkyTextures.return_value = TEXTURES[:]
    factory = mock.Mock(return_value=component)
    return GuardedEnvironment(33027004, TEXTURES, factory, wait_frames=3), factory, component

def ready(env):
    env.begin_change()
    env.finish_change(33027004)
    env.ui_ready()
    env.confirm_arrival(True)

def test_no_renderer_api_before_all_gates_and_actual_render_frames():
    env, factory, component = setup()
    env.begin_change()
    for _ in range(10):env.render_frame(False);env.tick(False)
    env.finish_change(33027004)
    for _ in range(10):env.render_frame(False);env.tick(False)
    env.ui_ready()
    for _ in range(10):env.render_frame(False);env.tick(False)
    factory.assert_not_called()
    env.confirm_arrival(True)
    for _ in range(2):env.render_frame(False);env.tick(False)
    factory.assert_not_called()
    env.render_frame(False)
    factory.assert_not_called()  # Render event records evidence, never calls native API.
    assert env.tick(False)
    component.SetSkyTextures.assert_called_once_with(TEXTURES)

def test_loading_overlay_resets_stability_and_never_becomes_ready():
    env, factory, _ = setup();ready(env)
    for _ in range(20):env.render_frame(True);env.tick(True)
    factory.assert_not_called()
    for _ in range(3):env.render_frame(False)
    assert env.tick(False)

def test_failed_native_apply_retries_are_bounded_and_not_per_tick():
    env, factory, component = setup();ready(env)
    component.SetSkyTextures.return_value = False
    for _ in range(1000):env.render_frame(False);env.tick(False)
    assert factory.call_count == 3
    assert not env.active
    assert env.status()['attempts'] == 3

def test_readback_failure_does_not_enable_clouds():
    env, _, component = setup();ready(env)
    component.GetSkyTextures.return_value = ['wrong']
    for _ in range(3):env.render_frame(False)
    assert not env.tick(False)
    assert not env.active

def test_leaving_dimension_only_discards_component_no_calls_during_detach():
    env, _, component = setup();ready(env)
    for _ in range(3):env.render_frame(False)
    assert env.tick(False)
    component.reset_mock()
    env.begin_change();env.finish_change(0);env.ui_ready();env.confirm_arrival(True)
    for _ in range(100):env.render_frame(False);env.tick(False)
    assert component.mock_calls == []
    assert not env.active

def test_ui_recreation_requires_new_frames_before_reapply():
    env, factory, _ = setup();ready(env)
    for _ in range(3):env.render_frame(False)
    assert env.tick(False)
    env.ui_ready();assert not env.active
    assert not env.tick(False)
    for _ in range(3):env.render_frame(False)
    assert env.tick(False)
    assert factory.call_count == 2

def test_initial_join_can_use_authoritative_arrival_after_ui_ready():
    env, factory, _ = setup();env.ui_ready();env.confirm_arrival(True)
    for _ in range(3):env.render_frame(False)
    assert env.tick(False)
    assert factory.call_count == 1

def test_cancelled_entry_never_enables_environment():
    env, factory, _ = setup();ready(env);env.confirm_arrival(False)
    for _ in range(50):env.render_frame(False);env.tick(False)
    factory.assert_not_called()

def test_no_repeated_texture_writes_after_success():
    env, _, component = setup();ready(env)
    for _ in range(1000):env.render_frame(False);env.tick(False)
    component.SetSkyTextures.assert_called_once()

def test_client_tick_and_render_event_use_guarded_controller():
    from tests.test_fortification_lifecycle_runtime import load_methods
    env, factory, _ = setup()
    namespace = {'config': SimpleNamespace(TWILIGHT_POST_ENTRY_ENVIRONMENT_ENABLED=True)}
    cls = load_methods('clientSystem.py', ['OnBlockChainRender', '_update_guarded_environment'], namespace)
    client = cls()
    client._chain_visuals = SimpleNamespace(render=lambda: None)
    client._guarded_environment = env
    client._portal_loading_active = True
    client._guarded_environment_last_status = None
    client._log_twilight_sky = lambda *args: None
    ready(env)
    for _ in range(5):client.OnBlockChainRender();client._update_guarded_environment()
    factory.assert_not_called()
    client._portal_loading_active = False
    for _ in range(3):client.OnBlockChainRender()
    factory.assert_not_called()
    client._update_guarded_environment()
    assert env.active

def test_source_wires_lifecycle_and_preserves_legacy_quarantine():
    path = ROOT / 'TwilightBossSliceB/TwilightBossSlice/clientSystem.py'
    source = path.read_text(encoding='utf-8')
    assert 'self._update_guarded_environment()' in source[source.index('    def OnScriptTickClient'):source.index('    def _notify_ur_ghast_hitbox_state')]
    for event, hook in [('OnDimensionChangeClientEvent','begin_change'), ('OnDimensionChangeFinishClientEvent','finish_change'), ('OnUiInitFinished','ui_ready'), ('OnPortalArrivalFinished','confirm_arrival')]:
        method = source[source.index('    def ' + event):].split('\n    def ',1)[0]
        assert 'self._guarded_environment.' + hook + '(' in method
    config = (ROOT / 'TwilightBossSliceB/TwilightBossSlice/config.py').read_text()
    assert 'TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED = False' in config

def test_unavailable_component_and_exception_do_not_escape_client_tick():
    env, factory, _ = setup();ready(env)
    factory.return_value = None
    for _ in range(3):env.render_frame(False)
    assert not env.tick(False)
    assert env.status()['error'] == 'component_unavailable'
    factory.side_effect = RuntimeError('renderer absent')
    for _ in range(3):env.render_frame(False)
    assert not env.tick(False)
    assert env.status()['error'] == 'renderer absent'

def test_bad_texture_count_is_rejected():
    with pytest.raises(ValueError):GuardedEnvironment(33027004, [], lambda: None)

def test_server_confirmation_before_native_finish_is_retained_but_not_applied():
    env, factory, _ = setup();env.begin_change();env.ui_ready();env.confirm_arrival(True)
    for _ in range(50):env.render_frame(False);env.tick(False)
    factory.assert_not_called()
    env.finish_change(33027004)
    for _ in range(3):env.render_frame(False)
    assert env.tick(False)

def test_late_native_finish_does_not_reopen_completed_portal_overlay():
    from tests.test_fortification_lifecycle_runtime import load_methods
    portal = SimpleNamespace(set_visible=mock.Mock())
    api = SimpleNamespace(GetLocalPlayerId=lambda: 'player')
    factory = SimpleNamespace(CreateGame=lambda _: SimpleNamespace(GetCurrentDimension=lambda: 33027004))
    config = SimpleNamespace(DIMENSION_ID=33027004, PORTAL_CLIENT_LOADING_TIMEOUT_TICKS=1800)
    names = ['_begin_portal_loading','_end_portal_loading','OnPortalArrivalFinished',
             '_is_local_dimension_event','OnDimensionChangeFinishClientEvent','_discard_twilight_sky_renderer_candidate']
    cls = load_methods('clientSystem.py', names, dict(portalLoadingUI=portal, clientApi=api, CF=factory, LEVEL_ID='level', config=config))
    client = cls();env, _, _ = setup();client._guarded_environment = env
    client._portal_loading_tick = 0
    client._ensure_portal_loading_ui = mock.Mock()
    client._log_twilight_sky = mock.Mock()
    client._update_twilight_sky = mock.Mock()
    client._update_twilight_cloud_layer = mock.Mock()
    client._begin_portal_loading()
    client.OnPortalArrivalFinished({'cancelled': False})
    assert not client._portal_loading_active
    client.OnDimensionChangeFinishClientEvent({'playerId': 'player'})
    assert not client._portal_loading_active
    portal.set_visible.assert_called_with(False)
    client._begin_portal_loading()
    assert client._portal_loading_active
    assert not client._portal_loading_server_finished

def test_cloud_switch_needs_successful_sky_gate_and_can_be_disabled():
    from tests.test_fortification_lifecycle_runtime import load_methods
    env, _, _ = setup()
    text = mock.Mock()
    cls = load_methods('clientSystem.py', ['OnEnvironmentStatusRequest', '_guarded_clouds_ready'],
                       dict(config=SimpleNamespace(TWILIGHT_POST_ENTRY_ENVIRONMENT_ENABLED=True),
                            CF=SimpleNamespace(CreateTextNotifyClient=lambda _: text), LEVEL_ID='level'))
    client = cls();client._guarded_environment = env;client._guarded_clouds_enabled = False
    client._portal_loading_active = False;client._twilight_cloud_particle_ids = []
    client._log_twilight_sky = mock.Mock();client._reset_twilight_cloud_layer = mock.Mock()
    client.OnEnvironmentStatusRequest({'clouds_enabled': True})
    assert not client._guarded_clouds_ready()
    ready(env)
    for _ in range(3):env.render_frame(False)
    assert env.tick(False)
    assert client._guarded_clouds_ready()
    client.OnEnvironmentStatusRequest({'clouds_enabled': False})
    assert not client._guarded_clouds_ready()
    client._reset_twilight_cloud_layer.assert_called_once()
