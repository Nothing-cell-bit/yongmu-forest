# -*- coding: utf-8 -*-
import client.extraClientApi as clientApi


ScreenNode = clientApi.GetScreenNodeCls()
_PENDING = {}
_SUBMIT_CALLBACK = None


def set_snapshot(snapshot):
    global _PENDING
    _PENDING = dict(snapshot or {})


def set_submit_callback(callback):
    global _SUBMIT_CALLBACK
    _SUBMIT_CALLBACK = callback


class FireReactUI(ScreenNode):
    """Small armor-slot picker; the server validates the final selection."""

    def __init__(self, namespace, name, param):
        super(FireReactUI, self).__init__(namespace, name, param)
        self._snapshot = dict(_PENDING)

    def Create(self):
        level = max(1, min(3, int(self._snapshot.get("level", 1))))
        self._set_label(
            "/panel/title",
            u"火焰反击 %d" % level,
        )
        self._set_label(
            "/panel/cost",
            u"选择护甲（消耗 %d 级经验）" % (level * 3),
        )
        choices = list(self._snapshot.get("choices", ()))[:4]
        for index in range(4):
            path = "/panel/armor_%d" % index
            control = self.GetBaseUIControl(path)
            available = index < len(choices)
            if control is None:
                continue
            control.SetVisible(available)
            if not available:
                continue
            choice = choices[index]
            self._set_label(
                path + "/armor_label",
                self._choice_text(choice, index),
            )
            button = control.asButton()
            if button is not None:
                button.AddTouchEventParams({"isSwallow": True})
                button.SetButtonTouchUpCallback(
                    self._choice_callback(choice.get("slot"))
                )

        close_control = self.GetBaseUIControl("/panel/close_button")
        if close_control is not None:
            button = close_control.asButton()
            if button is not None:
                button.AddTouchEventParams({"isSwallow": True})
                button.SetButtonTouchUpCallback(self._close)

    @staticmethod
    def _choice_text(choice, index):
        names = (u"头盔", u"胸甲", u"护腿", u"靴子")
        try:
            slot = max(0, min(3, int(choice.get("slot", index))))
        except (TypeError, ValueError):
            slot = index
        item_name = str(choice.get("itemName", ""))
        return u"%s  %s" % (names[slot], item_name)

    def _set_label(self, path, text):
        control = self.GetBaseUIControl(path)
        if control is None:
            return
        label = control.asLabel()
        if label is not None:
            label.SetText(text)

    def _choice_callback(self, slot):
        def submit(_args=None):
            global _SUBMIT_CALLBACK
            if _SUBMIT_CALLBACK is not None:
                _SUBMIT_CALLBACK(slot)
            clientApi.PopScreen()

        return submit

    def _close(self, _args=None):
        clientApi.PopScreen()
