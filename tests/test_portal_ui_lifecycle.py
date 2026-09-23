"""Exercise portal UI readiness and failed engine registration/recreation."""
import importlib.util
import sys
import types
import unittest
from unittest import mock

from tests.test_fortification_lifecycle_runtime import ROOT, load_methods


class PortalState:
    def __init__(self):
        self.active = False
        self.visible = False

    def is_active(self):
        return self.active

    def invalidate(self):
        self.active = False

    def set_visible(self, value):
        self.visible = value


class Engine:
    def __init__(self, portal):
        self.portal = portal
        self.register_result = True
        self.create_result = False
        self.registered = False
        self.calls = []

    def RegisterUI(self, *args):
        self.calls.append('register')
        if isinstance(self.register_result, Exception):
            raise self.register_result
        self.registered = self.register_result is not False
        return self.register_result

    def GetUI(self, *args):
        # Engine lookup may lag behind the returned CreateUI node.
        return None

    def CreateUI(self, *args):
        self.calls.append('create')
        if not self.registered or not self.create_result:
            return None
        return types.SimpleNamespace(Init=lambda: setattr(self.portal, 'active', True))


class PortalUiLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.portal = PortalState()
        self.engine = Engine(self.portal)
        noop = lambda *args: None
        namespace = dict(clientApi=self.engine, portalLoadingUI=self.portal,
                         config=types.SimpleNamespace(ModName='TwilightBossSlice', PORTAL_LOADING_UI_NAME='PortalLoadingUI'),
                         magicMapHudUI=types.SimpleNamespace(is_active=lambda: False),
                         lichBossHudUI=types.SimpleNamespace(invalidate=noop),
                         nagaBossHudUI=types.SimpleNamespace(invalidate=noop),
                         routeBossHudUI=types.SimpleNamespace(invalidate=noop))
        cls = load_methods('clientSystem.py', ['_ensure_portal_loading_ui', 'OnUiInitFinished'], namespace)
        self.client = cls()
        self.client._portal_loading_active = True
        self.client._portal_loading_tick = 0
        self.client._portal_loading_registered = False
        self.client._portal_loading_ui_ready = True
        self.client._portal_loading_ui_attempts = 0
        self.client._portal_loading_ui_retry_at = 0
        for name in ('_reset_twilight_cloud_layer', '_reset_twilight_sky', '_log_twilight_sky',
                     '_ensure_magic_map_player_pose', '_ensure_magic_map_ui'):
            setattr(self.client, name, noop)

    def test_no_native_ui_calls_before_ui_initialized(self):
        self.client._portal_loading_ui_ready = False
        self.assertFalse(self.client._ensure_portal_loading_ui())
        self.assertEqual([], self.engine.calls)

    def test_rejected_registration_does_not_create(self):
        self.engine.register_result = False
        self.assertFalse(self.client._ensure_portal_loading_ui())
        self.assertEqual(['register'], self.engine.calls)

    def test_failed_creation_is_bounded_across_many_ticks(self):
        for tick in range(180):
            self.client._portal_loading_tick = tick
            self.client._ensure_portal_loading_ui()
        self.assertEqual(3, self.engine.calls.count('register'))
        self.assertEqual(3, self.engine.calls.count('create'))

    def test_registration_exception_uses_same_retry_budget(self):
        self.engine.register_result = RuntimeError('UI registry unavailable')
        for tick in range(180):
            self.client._portal_loading_tick = tick
            self.client._ensure_portal_loading_ui()
        self.assertEqual(['register'] * 3, self.engine.calls)

    def test_ui_epoch_rebuilds_missing_registration_and_recovers(self):
        self.client._portal_loading_registered = True
        self.client._portal_loading_ui_ready = False
        self.client._portal_loading_ui_attempts = 3
        self.client._portal_loading_ui_retry_at = 10000
        self.engine.create_result = True
        self.client.OnUiInitFinished({})
        self.assertEqual(['register', 'create'], self.engine.calls)
        self.assertTrue(self.portal.is_active())
        self.assertTrue(self.portal.visible)

    def test_create_return_value_is_used_without_waiting_for_lookup(self):
        self.engine.create_result = True
        self.assertTrue(self.client._ensure_portal_loading_ui())
        self.assertTrue(self.client._ensure_portal_loading_ui())
        self.assertEqual(['register', 'create'], self.engine.calls)

    def test_overlay_is_not_active_until_its_control_exists(self):
        class Screen:
            def __init__(self, *args):
                self.control = None

            def GetBaseUIControl(self, path):
                return self.control

        api = types.ModuleType('client.extraClientApi')
        api.GetScreenNodeCls = lambda: Screen
        client_package = types.ModuleType('client')
        client_package.extraClientApi = api
        with mock.patch.dict(sys.modules, {'client': client_package, 'client.extraClientApi': api}):
            path = ROOT / 'TwilightBossSliceB/TwilightBossSlice/portalLoadingUI.py'
            spec = importlib.util.spec_from_file_location('portal_ui_under_test', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            node = module.PortalLoadingUI('n', 'k', {})
            node.Init()
            self.assertFalse(module.is_active())
            node.control = types.SimpleNamespace(SetVisible=lambda value: None)
            node.Init()
            self.assertTrue(module.is_active())
            node.Destroy()
            self.assertFalse(module.is_active())


if __name__ == '__main__':
    unittest.main()
