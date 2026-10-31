"""All six production HUD classes recreate against a fresh native UI registry."""
import importlib.util
import json
import sys
import types
from unittest import mock
import pytest
from tests.test_boss_hud_rejoin import PACKAGE, ROOT, Screen, client_methods, logic

KINDS = ('lich', 'naga', 'minoshroom', 'hydra', 'knight_phantoms', 'ur_ghast')


def environment():
    api = types.ModuleType('client.extraClientApi')
    api.GetScreenNodeCls = lambda: Screen
    client = types.ModuleType('client'); client.extraClientApi = api
    modules = {}
    with mock.patch.dict(sys.modules, {'client': client, 'client.extraClientApi': api}):
        for name in ('lichBossHudUI', 'nagaBossHudUI', 'routeBossHudUI'):
            spec = importlib.util.spec_from_file_location('rejoin_'+name, PACKAGE/(name+'.py'))
            mod = importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
            modules[name] = mod
    config = types.SimpleNamespace(ModName='TwilightBossSlice', BOSS_HUD_RANGE=64)
    for kind in KINDS: setattr(config, kind.upper()+'_BOSS_HUD_UI_NAME', kind)
    nodes, registrations, calls = {}, {}, []
    state = {'ready': False, 'registration_result': True, 'create_failure': False}
    classes = dict(lich=modules['lichBossHudUI'].LichBossHudUI,
                   naga=modules['nagaBossHudUI'].NagaBossHudUI)
    for kind, name in [('minoshroom','Minoshroom'),('hydra','Hydra'),
                       ('knight_phantoms','KnightPhantoms'),('ur_ghast','UrGhast')]:
        classes[kind] = getattr(modules['routeBossHudUI'],name+'BossHudUI')
    definitions = {}
    for file in json.loads((ROOT/'TwilightBossSliceR/ui/_ui_defs.json').read_text())['ui_defs']:
        doc = json.loads((ROOT/'TwilightBossSliceR'/file).read_text('utf-8'))
        definitions.update({doc['namespace']+'.'+key: value for key,value in doc.items() if isinstance(value,dict)})
    def register(namespace, kind, cls, definition):
        assert state['ready'], 'RegisterUI called before UiInitFinished'
        assert definitions[definition]['type'] == 'screen'
        calls.append(('register',kind))
        if state['registration_result'] is True: registrations[kind] = True
        return state['registration_result']
    def create(namespace, kind, params):
        assert registrations.get(kind), 'CreateUI without successful registration'
        calls.append(('create',kind))
        if state['create_failure']: return None
        node = classes[kind](namespace,kind,params);node.Create();nodes[kind]=node
        return node
    api.RegisterUI, api.CreateUI = register, create
    api.GetUI = lambda namespace, kind: nodes.get(kind)
    api.GetLocalPlayerId = lambda: 'player'
    ns = dict(clientApi=api, config=config, LEVEL_ID='level', boss_hud_logic=logic,
              CF=types.SimpleNamespace(CreateGame=lambda _: types.SimpleNamespace(GetCurrentDimension=lambda: None),
                                       CreatePos=lambda _: types.SimpleNamespace(GetFootPos=lambda: None)), **modules)
    host = client_methods(ns)();host._magic_map_ui_retry_tick=0
    host.NotifyToServer=lambda *args: None
    host._reset_boss_hud_session()
    def snapshot(seq):
        host.OnBossSync({'seq':seq,'bosses':[dict(id=k,kind=k,health=71,maxHealth=360,
            hudVisible=True,hudDistanceSquared=4,dimensionId=0,membersAlive=6) for k in KINDS]})
    def ready():
        state['ready']=True;host._on_boss_hud_ui_ready()
    return host, nodes, calls, state, snapshot, ready, registrations


def test_all_six_rejoin_without_healing_or_early_creation():
    host,nodes,calls,state,snapshot,ready,registrations=environment()
    snapshot(1);assert calls == []
    ready();snapshot(2)
    assert set(nodes) == set(KINDS)
    assert all(n.controls['/boss_root'].visible for n in nodes.values())
    old=list(nodes.values())
    for node in old: node.detached=True
    nodes.clear();registrations.clear();state['ready']=False
    host._reset_boss_hud_session()
    calls.clear();snapshot(1);assert calls == []
    ready();snapshot(2)
    assert set(nodes)==set(KINDS)
    assert all(n not in old and n.controls['/boss_root'].visible for n in nodes.values())
    assert all(b['health']==71 for b in host._bosses.values())


@pytest.mark.parametrize('failure', [False,None])
def test_failed_registration_is_bounded_and_retried_for_every_kind(failure):
    host,nodes,calls,state,snapshot,ready,registrations=environment()
    ready();state['registration_result']=failure
    for seq in range(1,11): snapshot(seq)
    assert len(calls)==6 and not nodes
    state['registration_result']=True;host._magic_map_ui_retry_tick+=20
    snapshot(11)
    assert set(nodes)==set(KINDS)


def test_native_creation_returning_none_rebinds_instead_of_sticking_registered():
    host,nodes,calls,state,snapshot,ready,registrations=environment()
    ready();state['create_failure']=True;snapshot(1)
    assert not nodes
    registrations.clear();state['create_failure']=False
    host._magic_map_ui_retry_tick+=20;snapshot(2)
    assert set(nodes)==set(KINDS)


def test_packets_during_retry_wait_never_write_detached_controls():
    host,nodes,calls,state,snapshot,ready,registrations=environment()
    ready();snapshot(1)
    def stale_write(*args): raise AssertionError('Wrote a detached native screen')
    for node in nodes.values():
        node.detached=True;node.ApplyBosses=stale_write
    snapshot(2)  # Still inside the bounded retry interval.
    assert all(b['health']==71 for b in host._bosses.values())
    nodes.clear();host._magic_map_ui_retry_tick+=20
    snapshot(3)
    assert set(nodes)==set(KINDS)
