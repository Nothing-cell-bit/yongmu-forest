# -*- coding: utf-8 -*-
import client.extraClientApi as clientApi


ScreenNode = clientApi.GetScreenNodeCls()
_PORTAL_LOADING_UI = None


def is_active():
    return _PORTAL_LOADING_UI is not None


def set_visible(visible):
    if _PORTAL_LOADING_UI is not None:
        _PORTAL_LOADING_UI.SetOverlayVisible(bool(visible))


def invalidate():
    global _PORTAL_LOADING_UI
    _PORTAL_LOADING_UI = None


class PortalLoadingUI(ScreenNode):
    def __init__(self, namespace, name, param):
        super(PortalLoadingUI, self).__init__(namespace, name, param)
        self._overlay = None

    def Create(self):
        self.Init()

    def Init(self):
        global _PORTAL_LOADING_UI
        self._overlay = self.GetBaseUIControl("/overlay")
        if self._overlay is None:
            if _PORTAL_LOADING_UI is self:
                _PORTAL_LOADING_UI = None
            return
        _PORTAL_LOADING_UI = self
        self.SetOverlayVisible(False)

    def SetOverlayVisible(self, visible):
        if self._overlay is not None:
            self._overlay.SetVisible(bool(visible))

    def Destroy(self):
        global _PORTAL_LOADING_UI
        if _PORTAL_LOADING_UI is self:
            _PORTAL_LOADING_UI = None
        self._overlay = None
