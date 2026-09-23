# -*- coding: utf-8 -*-
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_SYSTEM = ROOT / "TwilightBossSliceB" / "TwilightBossSlice" / "serverSystem.py"


def extracted_listener_class():
    source = SERVER_SYSTEM.read_text(encoding="utf-8")
    start = source.index("    def _listen_engine(")
    end = source.index("\n    def ", start + 1)
    namespace = {
        "ENGINE_NAMESPACE": "Minecraft",
        "ENGINE_SYSTEM": "engine",
    }
    exec("class ExtractedServerSystem(object):\n" + source[start:end], namespace)
    return namespace["ExtractedServerSystem"]


class ServerEventListenerBindingTests(unittest.TestCase):
    def server(self):
        base = extracted_listener_class()

        class ProbeServer(base):
            def __init__(self):
                self.registrations = []

            def ListenForEvent(self, *args):
                self.registrations.append(args)

            def own_callback(self, unused_args):
                pass

        return ProbeServer()

    def test_bound_helper_callback_uses_the_helper_as_listener_instance(self):
        class ItemEffectsProbe(object):
            def on_damage(self, unused_args):
                pass

        server = self.server()
        helper = ItemEffectsProbe()
        server._listen_engine("DamageEvent", helper.on_damage)

        registration = server.registrations[-1]
        self.assertIs(helper, registration[3])
        self.assertIs(helper.on_damage.__self__, registration[4].__self__)

    def test_server_callback_and_plain_callable_keep_server_as_listener(self):
        server = self.server()
        server._listen_engine("OwnEvent", server.own_callback)
        self.assertIs(server, server.registrations[-1][3])

        callback = lambda unused_args: None
        server._listen_engine("PlainEvent", callback)
        self.assertIs(server, server.registrations[-1][3])

    def test_python_two_bound_method_owner_is_supported(self):
        helper = object()

        class PythonTwoCallbackProbe(object):
            im_self = helper

            def __call__(self, unused_args):
                pass

        server = self.server()
        callback = PythonTwoCallbackProbe()
        server._listen_engine("PythonTwoEvent", callback)
        self.assertIs(helper, server.registrations[-1][3])


if __name__ == "__main__":
    unittest.main()
