"""Exercise actual spawn entry points; only SDK calls are simulated."""
from tests.test_portal_arrival_runtime import SERVER


class ChunkState:
    def __init__(self, ready):
        self.ready = ready
        self.calls = []

    def CheckChunkState(self, dimension, position):
        self.calls.append((dimension, tuple(position)))
        return self.ready


def host(ready=True, result='entity-1'):
    system = object.__new__(SERVER.ServerSystem)
    system._tick = 0
    system._chunk_comp = ChunkState(ready)
    system._segment_owners = {}
    calls = []
    def create(*args):
        calls.append(args)
        return result if system._chunk_comp.ready else None
    system.CreateEngineEntityByTypeStr = create
    return system, calls


def test_unloaded_ruin_spawn_never_reaches_native_entity_manager():
    system, calls = host(False)
    for tick in range(60):
        system._tick = tick
        assert system._spawn_ruin_entity('tf_slice:redcap', (1.5, 64, 3.5), 45, 33027004) is None
    assert calls == []
    system._chunk_comp.ready = True
    system._tick += 1
    assert system._spawn_ruin_entity('tf_slice:redcap', (1.5, 64, 3.5), 45, 33027004) == 'entity-1'
    assert calls == [('tf_slice:redcap', (1.5, 64, 3.5), (0.0, 45.0), 33027004, False, False)]


def test_unloaded_segment_keeps_slot_empty_and_resumes_when_loaded():
    system, calls = host(False)
    state = {'dimensionId': 0, 'segmentIds': [None]}
    assert system._spawn_segment('boss', state, 0, (-0.2, 64, -16.1), 90) is None
    assert calls == [] and state['segmentIds'] == [None]
    assert system._segment_owners == {}
    assert system._chunk_comp.calls[-1] == (0, (-1, 64, -17))
    system._chunk_comp.ready = True
    system._tick = 1
    assert system._spawn_segment('boss', state, 0, (-0.2, 64, -16.1), 90) == 'entity-1'
    assert state['segmentIds'] == ['entity-1']
    assert system._segment_owners == {'entity-1': ('boss', 0)}


def test_native_failure_has_bounded_retry_without_blocking_other_spawn_positions():
    system, calls = host(True, result=None)
    for tick in range(30):
        system._tick = tick
        assert system._spawn_ruin_entity('tf_slice:redcap', (0, 64, 0), 0, 0) is None
    assert len(calls) == 3
    system.CreateEngineEntityByTypeStr = lambda *args: 'recovered'
    assert system._spawn_ruin_entity('tf_slice:redcap', (1, 64, 0), 0, 0) == 'recovered'
    system._tick = 30
    assert system._spawn_ruin_entity('tf_slice:redcap', (0, 64, 0), 0, 0) == 'recovered'


def test_native_failure_sentinel_is_not_registered_as_a_segment():
    for result in ('-1', -1, False, None, ''):
        system, calls = host(True, result=result)
        state = {'dimensionId': 0, 'segmentIds': [None]}
        assert system._spawn_segment('boss', state, 0, (0, 64, 0), 0) is None
        assert state['segmentIds'] == [None]
        assert system._segment_owners == {}


def test_landmark_boss_creation_waits_without_leaving_a_false_pending_record():
    system, calls = host(False)
    for name in ('_bosses', '_lich_bosses', '_hydras', '_route_mobs', '_ur_ghasts'):
        setattr(system, name, {})
    system._pending_naga_spawns = []
    system._pending_courtyard_nagas = []
    system._ruin_worldgen = None
    identifier = SERVER.config.BOSS_IDENTIFIER
    assert system._spawn_courtyard_naga(identifier, (32, 64, 32), 180, 33027004) is None
    assert calls == []
    assert system._pending_courtyard_nagas == []
    system._chunk_comp.ready = True
    system._tick = 1
    assert system._spawn_courtyard_naga(identifier, (32, 64, 32), 180, 33027004) == 'entity-1'
    assert len(system._pending_courtyard_nagas) == 1
    assert system._pending_courtyard_nagas[0]['entityId'] == 'entity-1'


def test_checker_exception_never_attempts_entity_creation():
    system, calls = host(True)
    def unavailable(*args):
        raise RuntimeError('chunk component not ready')
    system._chunk_comp.CheckChunkState = unavailable
    assert system._spawn_ruin_entity('tf_slice:redcap', (0, 64, 0), 0, 0) is None
    assert calls == []
    assert system._worldgen_perf_counters['entitySpawnReadinessError'] == 1


def test_native_exceptions_are_counted_and_failure_cache_is_bounded():
    system, calls = host(True)
    def unavailable(*args):
        calls.append(args)
        raise RuntimeError('native actor unavailable')
    system.CreateEngineEntityByTypeStr = unavailable
    for x in range(200):
        assert system._spawn_ruin_entity('tf_slice:redcap', (x, 64, 0), 0, 0) is None
    assert len(system._entity_spawn_gate.retry_after) <= 128
    assert system._worldgen_perf_counters['entitySpawnNativeFailed'] == 200
    assert system._spawn_ruin_entity('tf_slice:redcap', (199, 64, 0), 0, 0) is None
    assert len(calls) == 200
    assert system._worldgen_perf_counters['entitySpawnDeferredRetry'] == 1
