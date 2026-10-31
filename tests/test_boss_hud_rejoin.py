"""Exercise real client/Hydra HUD lifecycle methods at the engine boundary."""
import importlib.util
from pathlib import Path
import sys
import textwrap
import types
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'TwilightBossSliceB/TwilightBossSlice'
sys.path.insert(0, str(PACKAGE.parent))
import TwilightBossSlice.boss_hud_logic as logic


class Control:
    def __init__(self):
        self.visible = False
    def SetVisible(self, value): self.visible = value
    def SetFullPosition(self, *args): pass
    def SetSize(self, value): self.size = value
    def asLabel(self): return self
    def SetText(self, value): self.text = value
    def asImage(self): return self
    def SetSpriteColor(self, value): pass


class Screen:
    def __init__(self, *args):
        self.detached = False
        self.controls = {p: Control() for p in (
            '/boss_root', '/boss_root/title', '/boss_root/bar_frame/bar_fill_clip',
            '/boss_root/bar_frame/bar_fill_clip/bar_fill')}
    def GetBaseUIControl(self, path):
        return None if self.detached else self.controls.get(path)


def client_methods(namespace):
    # The deployed client targets Python 2. Only print syntax is translated;
    # the production handlers and HUD implementation execute unchanged.
    from lib2to3.refactor import RefactoringTool
    converter = RefactoringTool(['lib2to3.fixes.fix_print'])
    source = (PACKAGE / 'clientSystem.py').read_text('utf-8')
    host = type('Host', (), {})
    for name in ('_reset_boss_hud_session', '_on_boss_hud_ui_ready',
                 '_can_attempt_boss_hud', '_ensure_lich_boss_hud',
                 '_ensure_naga_boss_hud', '_ensure_route_boss_hud', 'OnBossSync'):
        marker = '    def ' + name + '('
        if marker not in source:
            continue
        method = marker + source.split(marker, 1)[1].split('\n    def ', 1)[0]
        method = method.split('\n    @', 1)[0]
        method = textwrap.dedent(method)
        exec(str(converter.refactor_string(method.rstrip() + '\n', name)), namespace)
        setattr(host, name, namespace[name])
    return host


def setup_client():
    api = types.ModuleType('client.extraClientApi')
    api.GetScreenNodeCls = lambda: Screen
    client = types.ModuleType('client')
    client.extraClientApi = api
    with mock.patch.dict(sys.modules, {'client': client, 'client.extraClientApi': api}):
        spec = importlib.util.spec_from_file_location('route_hud_rejoin_test', PACKAGE / 'routeBossHudUI.py')
        route = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(route)
    class OtherHud:
        def invalidate(self): pass
        def set_bosses(self, *args): pass
    config = types.SimpleNamespace(ModName='TwilightBossSlice', HYDRA_BOSS_HUD_UI_NAME='hydra', BOSS_HUD_RANGE=64)
    current = {'node': None, 'creates': 0, 'fail': False, 'registers': 0,
               'registration_result': True}
    def register(*args):
        current['registers'] += 1
        return current['registration_result']
    api.RegisterUI = register
    api.GetUI = lambda *args: current['node']
    api.GetLocalPlayerId = lambda: 'player'
    def create(*args):
        current['creates'] += 1
        if current['fail']:
            raise RuntimeError('UI not ready')
        current['node'] = route.HydraBossHudUI('test', 'hydra', {})
        current['node'].Init()
        return current['node']
    api.CreateUI = create
    namespace = dict(clientApi=api, config=config, LEVEL_ID='level',
                     CF=types.SimpleNamespace(CreateGame=lambda _: types.SimpleNamespace(GetCurrentDimension=lambda: None),
                                              CreatePos=lambda _: types.SimpleNamespace(GetFootPos=lambda: None)),
                     boss_hud_logic=logic, routeBossHudUI=route,
                     lichBossHudUI=OtherHud(), nagaBossHudUI=OtherHud())
    host = client_methods(namespace)()
    host._last_sequence = 100
    host._sequence_gaps = 0
    host._received_packets = 0
    host._hydra_boss_hud_registered = False
    host._boss_hud_ui_ready = True
    host._boss_hud_retry_at = {}
    host._magic_map_ui_retry_tick = 0
    host.NotifyToServer = lambda *args: None
    return host, route, current


def packet(sequence, health=37.5):
    return {'seq': sequence, 'bosses': [{'id': 'hydra', 'kind': 'hydra',
            'health': health, 'maxHealth': 360, 'hudVisible': True,
            'hudDistanceSquared': 9, 'dimensionId': 0}]}


def test_destroyed_native_root_is_not_an_active_hud_without_destroy_callback():
    host, route, current = setup_client()
    host._last_sequence = -1
    host.OnBossSync(packet(1))
    old = current['node']
    assert route.hydra_active()
    old.detached = True
    assert not route.hydra_active()
    host._magic_map_ui_retry_tick += 20
    host.OnBossSync(packet(2, 75))
    assert current['node'] is not old
    assert current['node'].controls['/boss_root'].visible
    assert host._bosses['hydra']['health'] == 75


def test_world_session_reset_releases_old_nodes_and_accepts_new_server_sequence():
    host, route, current = setup_client()
    old = route.HydraBossHudUI('old', 'old', {})
    old.Init()
    current['node'] = old
    assert route.hydra_active()
    host._reset_boss_hud_session()
    assert not route.hydra_active()
    assert host._last_sequence == -1
    old.detached = True
    host._on_boss_hud_ui_ready()
    host.OnBossSync(packet(1))
    assert current['node'] is not old
    assert host._bosses['hydra']['health'] == 37.5
    assert current['node'].controls['/boss_root'].visible


def test_ui_creation_failure_recovers_on_next_snapshot_without_changing_health():
    host, route, current = setup_client()
    host._last_sequence = -1
    current['fail'] = True
    host.OnBossSync(packet(1))
    assert host._bosses['hydra']['health'] == 37.5
    assert not route.hydra_active()
    current['fail'] = False
    host._magic_map_ui_retry_tick += 20
    host.OnBossSync(packet(2))
    assert route.hydra_active()
    assert current['node'].controls['/boss_root'].visible


def test_session_reset_is_wired_at_both_world_entry_and_exit():
    source = (PACKAGE / 'clientSystem.py').read_text('utf-8')
    for name in ('__init__', 'Destroy'):
        body = source.split('    def ' + name + '(', 1)[1].split('\n    def ', 1)[0]
        assert 'self._reset_boss_hud_session()' in body
    body = source.split('    def OnUiInitFinished(', 1)[1].split('\n    def ', 1)[0]
    assert 'self._on_boss_hud_ui_ready()' in body


def test_early_snapshot_waits_for_native_ui_definitions_and_keeps_health():
    host, route, current = setup_client()
    host._reset_boss_hud_session()
    host.OnBossSync(packet(1, 83))
    assert host._bosses['hydra']['health'] == 83
    assert current['registers'] == current['creates'] == 0
    host._on_boss_hud_ui_ready()
    host.OnBossSync(packet(2, 82))
    assert current['registers'] == current['creates'] == 1
    assert route.hydra_active()


def test_failed_registration_never_creates_and_retries_after_definitions_ready():
    for result in (False, None):
        host, route, current = setup_client()
        host._last_sequence = -1
        current['registration_result'] = result
        host.OnBossSync(packet(1))
        assert not route.hydra_active()
        assert current['creates'] == 0
        current['registration_result'] = True
        host._magic_map_ui_retry_tick += 20
        host.OnBossSync(packet(2))
        assert route.hydra_active()
        assert current['registers'] == 2


def test_repeated_ui_ready_rebinds_registration_without_resetting_server_sequence():
    host, route, current = setup_client()
    host._last_sequence = -1
    host.OnBossSync(packet(41, 73))
    current['node'].detached = True
    host._on_boss_hud_ui_ready()
    assert host._last_sequence == 41
    assert host._bosses['hydra']['health'] == 73
    host.OnBossSync(packet(42, 72))
    assert current['registers'] == 2
    assert route.hydra_active()
