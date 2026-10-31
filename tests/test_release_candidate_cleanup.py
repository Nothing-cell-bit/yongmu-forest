import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def tool():
    path = ROOT / 'tools/prepare_release_candidate.py'
    assert path.exists(), 'Missing repeatable release cleanup entrypoint'
    spec = importlib.util.spec_from_file_location('release_candidate', path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def method(source, name):
    match = re.search(r'^    def ' + name + r'\(', source, re.M)
    end = re.search(r'^    (?:def |@)', source[match.end():], re.M)
    return source[match.start():match.end()+end.start() if end else len(source)]


def test_clean_real_callers_removes_probe_without_reverting_entry_fix():
    module = tool()
    bp = ROOT/'TwilightBossSliceB/TwilightBossSlice'
    server = (bp/'serverSystem.py').read_text(encoding='utf-8-sig')
    clean = module.clean_script('serverSystem.py', server)
    assert 'chunk_latency_probe' not in clean
    assert 'loadprobe' not in clean
    assert '_control_chunk_latency_probe' not in clean
    for name in ['_process_portal_arrivals', '_relocate_staged_portal_entry', 'OnPortalArrivalEngineReady']:
        assert method(clean, name) == method(server, name)
    body = method(clean, 'OnServerChatEvent')
    assert 'return' in body and '_enter_slice' not in body
    client = module.clean_script('clientSystem.py', (bp/'clientSystem.py').read_text(encoding='utf-8-sig'))
    assert 'chunk_latency_probe' not in client and 'load_probe' not in client
    assert 'key_transition' not in method(client, 'OnKeyPressInGame')
    assert 'self._guarded_environment.tick' in client


def test_cleaner_preserves_real_io_users_and_is_idempotent():
    module = tool();bp=ROOT/'TwilightBossSliceB/TwilightBossSlice'
    for name in ['biome_catalog.py', 'magic_map_bitmap_cache.py']:
        text=(bp/name).read_text(encoding='utf-8-sig')
        assert module.clean_script(name,text)==text
    for name in ['serverSystem.py','clientSystem.py','config.py']:
        text=module.clean_script(name,(bp/name).read_text(encoding='utf-8-sig'))
        assert module.clean_script(name,text)==text
        assert 'CHUNK_LATENCY_PROBE_OUTPUT_DIR' not in text


def test_world_diagnostics_are_removed_without_removing_water_repair():
    module = tool()
    source = (ROOT / 'TwilightBossSliceB/TwilightBossSlice/serverSystem.py').read_text(encoding='utf-8-sig')
    clean = module.clean_script('serverSystem.py', source)
    assert 'native_world_diag' not in clean
    assert 'diagnostic_args' not in clean
    body = method(clean, '_tick_water_marker_cleanup')
    assert 'self._block_comp.SetBlockNew(' in body
    assert 'self._chunk_comp.CheckChunkState(dimension, position)' in body
    assert 'return self._get_block(position, dimension)' in body
    assert 'cleanup.tick(self._tick, paused, ready, read, clear_marker)' in body
    assert 'cleanup.record_event(args, self._tick)' in clean
    for name in ['_process_portal_arrivals', 'OnPortalArrivalEngineReady', '_dispatch_structure_feature_event']:
        assert method(clean, name) == method(source, name)
