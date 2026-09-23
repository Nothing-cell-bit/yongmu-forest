# -*- coding: utf-8 -*-
import client.extraClientApi as clientApi
import TwilightBossSlice.boss_hud_logic as boss_hud_logic


ScreenNode = clientApi.GetScreenNodeCls()
_ACTIVE_UI = None
_PENDING_BOSSES = []
_PENDING_STACK_SLOT = 0


def set_bosses(bosses, stack_slot=None):
    global _PENDING_BOSSES, _PENDING_STACK_SLOT
    _PENDING_BOSSES = list(bosses or ())
    if stack_slot is not None:
        _PENDING_STACK_SLOT = max(0, int(stack_slot))
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.ApplyBosses(_PENDING_BOSSES, _PENDING_STACK_SLOT)


def is_active():
    return _ACTIVE_UI is not None


def invalidate():
    global _ACTIVE_UI
    _ACTIVE_UI = None


class NagaBossHudUI(ScreenNode):
    """Vanilla-shaped green, ten-section HUD from the 4.3.2508 contract."""

    STACK_HEIGHT = 20.0

    def __init__(self, namespace, name, param):
        super(NagaBossHudUI, self).__init__(namespace, name, param)
        self._root = None
        self._title = None
        self._fill = None
        self._fill_clip = None

    def Create(self):
        self.Init()

    def Init(self):
        global _ACTIVE_UI
        _ACTIVE_UI = self
        try:
            self._root = self.GetBaseUIControl("/boss_root")
            self._title = self.GetBaseUIControl("/boss_root/title")
            self._fill_clip = self.GetBaseUIControl(
                "/boss_root/bar_frame/bar_fill_clip"
            )
            self._fill = self.GetBaseUIControl(
                "/boss_root/bar_frame/bar_fill_clip/bar_fill"
            )
        except Exception:
            self._root = None
            self._title = None
            self._fill = None
            self._fill_clip = None
        self.ApplyBosses(_PENDING_BOSSES, _PENDING_STACK_SLOT)

    def ApplyBosses(self, bosses, stack_slot=0):
        if self._root is None:
            return
        self._root.SetFullPosition(
            "y",
            {"absoluteValue": self.STACK_HEIGHT * max(0, int(stack_slot))},
        )
        naga = bosses[0] if bosses else None
        self._root.SetVisible(naga is not None)
        if naga is None:
            return
        maximum = max(1.0, float(naga.get("maxHealth", 200.0)))
        health = max(0.0, min(maximum, float(naga.get("health", 0.0))))
        fraction = health / maximum
        displayName = naga.get("name", u"\u5a1c\u8fe6") or u"\u5a1c\u8fe6"
        if self._title is not None and self._title.asLabel() is not None:
            self._title.asLabel().SetText(displayName)
        if self._fill is not None:
            image = self._fill.asImage()
            if image is not None:
                style = boss_hud_logic.source_boss_bar_style("naga", 1)
                image.SetSpriteColor(style["color"])
                fillWidth = boss_hud_logic.precise_fill_width(fraction)
                self._fill_clip.SetSize((fillWidth, 5.0))
                self._fill_clip.SetVisible(fillWidth > 0.0)

    def Destroy(self):
        global _ACTIVE_UI
        if _ACTIVE_UI is self:
            _ACTIVE_UI = None
        self._root = None
        self._title = None
        self._fill = None
        self._fill_clip = None
