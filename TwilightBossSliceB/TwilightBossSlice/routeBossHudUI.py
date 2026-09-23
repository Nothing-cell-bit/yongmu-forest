# -*- coding: utf-8 -*-
import client.extraClientApi as clientApi
import TwilightBossSlice.boss_hud_logic as boss_hud_logic


ScreenNode = clientApi.GetScreenNodeCls()
_MINOSHROOM_UI = None
_HYDRA_UI = None
_KNIGHT_PHANTOMS_UI = None
_UR_GHAST_UI = None
_PENDING_MINOSHROOMS = []
_PENDING_HYDRAS = []
_PENDING_KNIGHT_PHANTOMS = []
_PENDING_UR_GHASTS = []
_PENDING_MINOSHROOM_SLOT = 0
_PENDING_HYDRA_SLOT = 0
_PENDING_KNIGHT_PHANTOMS_SLOT = 0
_PENDING_UR_GHAST_SLOT = 0


def set_minoshrooms(bosses, stack_slot=None):
    global _PENDING_MINOSHROOMS, _PENDING_MINOSHROOM_SLOT
    _PENDING_MINOSHROOMS = list(bosses or ())
    if stack_slot is not None:
        _PENDING_MINOSHROOM_SLOT = max(0, int(stack_slot))
    if _MINOSHROOM_UI is not None:
        _MINOSHROOM_UI.ApplyBosses(
            _PENDING_MINOSHROOMS,
            _PENDING_MINOSHROOM_SLOT,
        )


def set_hydras(bosses, stack_slot=None):
    global _PENDING_HYDRAS, _PENDING_HYDRA_SLOT
    _PENDING_HYDRAS = list(bosses or ())
    if stack_slot is not None:
        _PENDING_HYDRA_SLOT = max(0, int(stack_slot))
    if _HYDRA_UI is not None:
        _HYDRA_UI.ApplyBosses(_PENDING_HYDRAS, _PENDING_HYDRA_SLOT)


def set_knight_phantoms(bosses, stack_slot=None):
    global _PENDING_KNIGHT_PHANTOMS, _PENDING_KNIGHT_PHANTOMS_SLOT
    _PENDING_KNIGHT_PHANTOMS = list(bosses or ())
    if stack_slot is not None:
        _PENDING_KNIGHT_PHANTOMS_SLOT = max(0, int(stack_slot))
    if _KNIGHT_PHANTOMS_UI is not None:
        _KNIGHT_PHANTOMS_UI.ApplyBosses(
            _PENDING_KNIGHT_PHANTOMS,
            _PENDING_KNIGHT_PHANTOMS_SLOT,
        )


def set_ur_ghasts(bosses, stack_slot=None):
    global _PENDING_UR_GHASTS, _PENDING_UR_GHAST_SLOT
    _PENDING_UR_GHASTS = list(bosses or ())
    if stack_slot is not None:
        _PENDING_UR_GHAST_SLOT = max(0, int(stack_slot))
    if _UR_GHAST_UI is not None:
        _UR_GHAST_UI.ApplyBosses(_PENDING_UR_GHASTS, _PENDING_UR_GHAST_SLOT)


def minoshroom_active():
    return _MINOSHROOM_UI is not None and _MINOSHROOM_UI.IsReady()


def hydra_active():
    return _HYDRA_UI is not None and _HYDRA_UI.IsReady()


def knight_phantoms_active():
    return _KNIGHT_PHANTOMS_UI is not None and _KNIGHT_PHANTOMS_UI.IsReady()


def ur_ghast_active():
    return _UR_GHAST_UI is not None and _UR_GHAST_UI.IsReady()


def invalidate():
    global _MINOSHROOM_UI, _HYDRA_UI, _KNIGHT_PHANTOMS_UI
    global _UR_GHAST_UI
    _MINOSHROOM_UI = None
    _HYDRA_UI = None
    _KNIGHT_PHANTOMS_UI = None
    _UR_GHAST_UI = None


class _RouteBossHudBase(ScreenNode):
    STACK_HEIGHT = 20.0

    def __init__(self, namespace, name, param):
        super(_RouteBossHudBase, self).__init__(namespace, name, param)
        self._root = None
        self._title = None
        self._fill = None
        self._fill_clip = None

    def Create(self):
        self.Init()

    def Init(self):
        self._root = None
        self._title = None
        self._fill = None
        self._fill_clip = None
        try:
            self._root = self.GetBaseUIControl("/boss_root")
        except Exception:
            self._root = None
        try:
            self._title = self.GetBaseUIControl("/boss_root/title")
        except Exception:
            self._title = None
        try:
            self._fill_clip = self.GetBaseUIControl(
                "/boss_root/bar_frame/bar_fill_clip"
            )
            if self._fill_clip is not None:
                self._fill = self.GetBaseUIControl(
                    "/boss_root/bar_frame/bar_fill_clip/bar_fill"
                )
        except Exception:
            self._fill_clip = None
            self._fill = None

    def IsReady(self):
        return self._root is not None

    def _apply(
        self,
        bosses,
        fallback_name,
        kind,
        stack_slot=0,
        preciseFill=False,
    ):
        if self._root is None:
            return
        self._root.SetFullPosition(
            "y",
            {"absoluteValue": self.STACK_HEIGHT * max(0, int(stack_slot))},
        )
        boss = bosses[0] if bosses else None
        self._root.SetVisible(boss is not None)
        if boss is None:
            return
        maximum = max(1.0, float(boss.get("maxHealth", 1.0)))
        health = max(0.0, min(maximum, float(boss.get("health", 0.0))))
        fraction = health / maximum
        title = boss.get("name", fallback_name) or fallback_name
        if self._title is not None and self._title.asLabel() is not None:
            self._title.asLabel().SetText(title)
        if self._fill is not None:
            image = self._fill.asImage()
            if image is not None:
                style = boss_hud_logic.source_boss_bar_style(
                    kind,
                    boss.get("phase", 1),
                )
                image.SetSpriteColor(style["color"])
                if preciseFill and self._fill_clip is not None:
                    fillWidth = boss_hud_logic.precise_fill_width(fraction)
                    self._fill_clip.SetSize((fillWidth, 5.0))
                    self._fill_clip.SetVisible(fillWidth > 0.0)

    def _clear(self):
        self._root = None
        self._title = None
        self._fill = None
        self._fill_clip = None


class MinoshroomBossHudUI(_RouteBossHudBase):
    def Init(self):
        global _MINOSHROOM_UI
        _RouteBossHudBase.Init(self)
        _MINOSHROOM_UI = self
        self.ApplyBosses(_PENDING_MINOSHROOMS, _PENDING_MINOSHROOM_SLOT)

    def ApplyBosses(self, bosses, stack_slot=0):
        self._apply(
            bosses,
            u"\u7c73\u8bfa\u83c7",
            "minoshroom",
            stack_slot,
            preciseFill=True,
        )

    def Destroy(self):
        global _MINOSHROOM_UI
        if _MINOSHROOM_UI is self:
            _MINOSHROOM_UI = None
        self._clear()


class HydraBossHudUI(_RouteBossHudBase):
    def Init(self):
        global _HYDRA_UI
        _RouteBossHudBase.Init(self)
        _HYDRA_UI = self
        self.ApplyBosses(_PENDING_HYDRAS, _PENDING_HYDRA_SLOT)

    def ApplyBosses(self, bosses, stack_slot=0):
        self._apply(
            bosses,
            u"\u4e5d\u5934\u86c7",
            "hydra",
            stack_slot,
            preciseFill=True,
        )

    def Destroy(self):
        global _HYDRA_UI
        if _HYDRA_UI is self:
            _HYDRA_UI = None
        self._clear()


class KnightPhantomsBossHudUI(_RouteBossHudBase):
    def Init(self):
        global _KNIGHT_PHANTOMS_UI
        _RouteBossHudBase.Init(self)
        _KNIGHT_PHANTOMS_UI = self
        self.ApplyBosses(
            _PENDING_KNIGHT_PHANTOMS,
            _PENDING_KNIGHT_PHANTOMS_SLOT,
        )

    def ApplyBosses(self, bosses, stack_slot=0):
        self._apply(
            bosses,
            u"幻影骑士",
            "knight_phantoms",
            stack_slot,
            preciseFill=True,
        )

    def Destroy(self):
        global _KNIGHT_PHANTOMS_UI
        if _KNIGHT_PHANTOMS_UI is self:
            _KNIGHT_PHANTOMS_UI = None
        self._clear()


class UrGhastBossHudUI(_RouteBossHudBase):
    def Init(self):
        global _UR_GHAST_UI
        _RouteBossHudBase.Init(self)
        _UR_GHAST_UI = self
        self.ApplyBosses(_PENDING_UR_GHASTS, _PENDING_UR_GHAST_SLOT)

    def ApplyBosses(self, bosses, stack_slot=0):
        self._apply(
            bosses,
            u"暮色恶魂",
            "ur_ghast",
            stack_slot,
            preciseFill=True,
        )

    def Destroy(self):
        global _UR_GHAST_UI
        if _UR_GHAST_UI is self:
            _UR_GHAST_UI = None
        self._clear()
