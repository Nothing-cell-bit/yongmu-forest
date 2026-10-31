from types import SimpleNamespace
from unittest import mock

from tests import test_portal_arrival_runtime as arrival
from tests.test_fortification_lifecycle_runtime import load_methods


def test_environment_chat_includes_existing_counters_without_querying_world():
    case = arrival.PortalArrivalRuntimeTests()
    case.setUp()
    server = case.system
    server._worldgen_perf_counters = {'chunkGenerated': 11, 'chunkLoaded': 18}
    server._last_perf = {'avgMs': 2.5, 'p95Ms': 4.0}
    server.OnServerChatEvent({'playerId': 'player', 'message': '!slice environment'})
    player, event, payload = case.client_notifications[-1]
    assert (player, event) == ('player', 'EnvironmentStatusRequest')
    assert payload['streaming']['generated'] == 11
    assert payload['streaming']['loaded'] == 18
    assert payload['streaming']['queue'] == 0
    assert payload['streaming']['scriptAvgMs'] == 2.5
    assert arrival.FACTORY.chunk.checked == []
    assert arrival.FACTORY.chunk.async_tasks == []


def test_status_client_displays_streaming_counts_and_script_time():
    text = mock.Mock()
    cls = load_methods('clientSystem.py', ['OnEnvironmentStatusRequest'],
        dict(CF=SimpleNamespace(CreateTextNotifyClient=lambda _: text), LEVEL_ID='level'))
    client = cls()
    client._guarded_environment = SimpleNamespace(status=lambda: dict(
        active=True, uiReady=True, serverConfirmed=True, frames=60, attempts=1, error=None))
    client._guarded_clouds_enabled = False
    client._twilight_cloud_particle_ids = []
    client._log_twilight_sky = mock.Mock()
    client.OnEnvironmentStatusRequest({'streaming': dict(
        generated=11, loaded=18, queue=0, inflight=False,
        prewarm=False, scriptAvgMs=2.5, scriptP95Ms=4.0)})
    message = text.SetLeftCornerNotify.call_args.args[0]
    assert 'generated=11 loaded=18' in message
    assert 'prewarm=False queue=0' in message
    assert 'scriptAvgMs=2.5' in message
