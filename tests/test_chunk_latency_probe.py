import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from tests.test_fortification_lifecycle_runtime import load_methods

ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'TwilightBossSliceB/TwilightBossSlice/chunk_latency_probe.py'
    assert path.exists(), 'Missing bounded, opt-in chunk latency recorder'
    spec = importlib.util.spec_from_file_location('chunk_latency_probe', path)
    value = importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def test_disabled_probe_never_calls_clock_sdk_or_files(tmp_path):
    mod = module();clock = mock.Mock(side_effect=AssertionError('disabled clock'))
    probe = mod.Probe('client', clock)
    probe.record('chunk', {'chunkPosX': 1})
    probe.frame();probe.tick();probe.stop()
    assert list(tmp_path.iterdir()) == []
    clock.assert_not_called()


def test_server_profile_ownership_duplicate_start_and_svg_export(tmp_path):
    mod = module();now = [100.0]
    sdk = SimpleNamespace(StartProfile=mock.Mock(return_value=True), StopProfile=mock.Mock(return_value=True))
    probe = mod.Probe('server', lambda: now[0], sdk)
    assert probe.start(str(tmp_path), '123-4')
    assert not probe.start(str(tmp_path), 'other')
    args = {'dimensionId': 33027004, 'chunkPosX': 3, 'chunkPosZ': -4}
    probe.record('generated', args);args['chunkPosX'] = 900
    now[0] += 21
    assert probe.stop()
    sdk.StartProfile.assert_called_once()
    sdk.StopProfile.assert_called_once_with(str(tmp_path).replace('\\', '/') + '/123-4-server.svg')
    data = json.loads((tmp_path/'123-4-server.json').read_text())
    assert data['events'][0]['fields']['chunkPosX'] == 3
    assert data['durationSeconds'] == 21
    assert data['profileStopped'] is True
    assert probe.stop() is False
    assert sdk.StopProfile.call_count == 1


def test_failed_profile_start_keeps_trace_without_stopping_other_profile(tmp_path):
    mod = module();sdk = SimpleNamespace(StartProfile=mock.Mock(return_value=False), StopProfile=mock.Mock())
    probe = mod.Probe('server', lambda: 100.0, sdk)
    assert probe.start(str(tmp_path), '123')
    assert probe.stop()
    sdk.StopProfile.assert_not_called()
    data = json.loads((tmp_path/'123-server.json').read_text())
    assert data['profileStarted'] is False
    assert data['errors']


def test_bounded_events_and_wall_clock_timeout(tmp_path):
    mod = module();now = [10.0];probe = mod.Probe('client', lambda: now[0])
    probe.start(str(tmp_path), '123')
    for i in range(5000):probe.record('loaded', {'chunkPosX': i});probe.frame()
    assert len(probe.events) <= 4096
    now[0] = 71.0
    assert probe.tick() is True
    data = json.loads((tmp_path/'123-client.json').read_text())
    assert data['droppedEvents'] > 0
    assert data['frameCount'] == 5000
    assert data['reason'] == 'timeout'
    assert not probe.active


def test_export_error_is_reported_and_profile_stop_still_runs(tmp_path):
    mod = module();sdk = SimpleNamespace(StartProfile=lambda: True, StopProfile=mock.Mock(return_value=False))
    probe = mod.Probe('server', lambda: 10.0, sdk)
    probe.start(str(tmp_path/'missing'), '123')
    assert not probe.stop()
    assert any('export' in e for e in probe.errors)
    assert any('profile_stop' in e for e in probe.errors)


@pytest.mark.parametrize('token', ['../escape', '', 'x/y', 'a'*80])
def test_invalid_session_rejected_without_activity(tmp_path, token):
    mod = module();probe = mod.Probe('client', lambda: 10.0)
    assert not probe.start(str(tmp_path), token)
    assert not probe.active


def test_real_client_records_chunks_after_portal_overlay_closed():
    cls = load_methods('clientSystem.py', ['OnChunkLoadedClientEvent'],
                       dict(config=SimpleNamespace(DIMENSION_ID=33027004)))
    client = cls();client._portal_loading_active = False
    client._chunk_latency_probe = mock.Mock()
    event = {'dimension': 33027004, 'chunkPosX': 4, 'chunkPosZ': 5}
    client.OnChunkLoadedClientEvent(event)
    client._chunk_latency_probe.record.assert_called_once_with('client_loaded', event)


def test_real_chat_to_client_control_and_both_chunk_callbacks_export(tmp_path):
    mod = module()
    sdk = SimpleNamespace(StartProfile=mock.Mock(return_value=True), StopProfile=mock.Mock(return_value=True))
    config = SimpleNamespace(DIMENSION_ID=33027004, CHUNK_LATENCY_PROBE_OUTPUT_DIR=str(tmp_path))
    text = mock.Mock()
    client_cls = load_methods('clientSystem.py', ['OnEnvironmentStatusRequest', 'OnChunkLoadedClientEvent'],
        dict(config=config, chunk_latency_probe=mod,
             CF=SimpleNamespace(CreateTextNotifyClient=lambda _: text), LEVEL_ID='level'))
    client = client_cls()
    client._guarded_environment = SimpleNamespace(status=lambda: dict(
        active=True, uiReady=True, serverConfirmed=True, frames=60, attempts=1, error=None))
    client._guarded_clouds_enabled = False;client._twilight_cloud_particle_ids = []
    client._log_twilight_sky = mock.Mock();client._portal_loading_active = False
    server_cls = load_methods('serverSystem.py', ['OnServerChatEvent', '_control_chunk_latency_probe',
        '_worldgen_perf_snapshot', '_worldgen_perf_increment', 'OnChunkLoadedServerEvent', 'OnChunkGeneratedServerEvent'],
        dict(config=config, chunk_latency_probe=mod, serverApi=sdk, time=SimpleNamespace(time=lambda: 100.0)))
    server = server_cls();server._tick = 1;server._ruin_worldgen = None
    server._entry_trace = mock.Mock()
    server.NotifyToClient = lambda _player, _event, payload: client.OnEnvironmentStatusRequest(payload)
    server.OnServerChatEvent({'playerId': 'a', 'message': '!slice loadprobe start'})
    server.OnServerChatEvent({'playerId': 'b', 'message': '!slice loadprobe stop'})
    assert server._chunk_latency_probe.active
    event = {'dimensionId': 33027004, 'chunkPosX': 4, 'chunkPosZ': 5}
    server.OnChunkGeneratedServerEvent(event);server.OnChunkLoadedServerEvent(event)
    client.OnChunkLoadedClientEvent(event)
    server.OnServerChatEvent({'playerId': 'a', 'message': '!slice loadprobe stop'})
    assert not server._chunk_latency_probe.active
    assert not client._chunk_latency_probe.active
    data = json.loads((tmp_path/'100000-1-server.json').read_text())
    assert [e['event'] for e in data['events']] == ['start_counters', 'server_generated', 'server_loaded', 'end_counters']
    client_data = json.loads((tmp_path/'100000-1-client.json').read_text())
    assert client_data['events'][0]['fields']['chunkPosX'] == 4
    sdk.StartProfile.assert_called_once();sdk.StopProfile.assert_called_once()
    assert '.json' not in sdk.StopProfile.call_args.args[0]


def test_unavailable_release_pack_cannot_start_sdk_or_files(tmp_path):
    mod = module();sdk = mock.Mock()
    cls = load_methods('serverSystem.py', ['_control_chunk_latency_probe'],
        dict(config=SimpleNamespace(CHUNK_LATENCY_PROBE_OUTPUT_DIR=None),
             chunk_latency_probe=mod, serverApi=sdk))
    server = cls();server.NotifyToClient = mock.Mock()
    server._control_chunk_latency_probe('a', 'start')
    assert not hasattr(server, '_chunk_latency_probe')
    assert sdk.mock_calls == []


def test_sdk_exceptions_and_bad_snapshot_do_not_break_game_callbacks(tmp_path):
    mod = module();sdk = SimpleNamespace(StartProfile=mock.Mock(side_effect=RuntimeError('unsupported')))
    probe = mod.Probe('server', lambda: 100.0, sdk)
    assert probe.start(str(tmp_path), 'unicode-token')
    class NativeValue:
        def __deepcopy__(self, memo):raise RuntimeError('not a data object')
    probe.record('generated', {'native': NativeValue()})
    assert probe.dropped == 1
    assert probe.stop()
    sdk = SimpleNamespace(StartProfile=lambda: True, StopProfile=mock.Mock(side_effect=RuntimeError('busy')))
    probe = mod.Probe('server', lambda: 100.0, sdk)
    assert probe.start(str(tmp_path), 'retry')
    assert not probe.stop()
    assert probe.owned_profile
    assert not probe.start(str(tmp_path), 'new')
    sdk.StopProfile.side_effect = None;sdk.StopProfile.return_value = True
    assert probe.stop()
    assert not probe.owned_profile
