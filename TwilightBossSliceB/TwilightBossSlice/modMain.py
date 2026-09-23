# -*- coding: utf-8 -*-
from common.mod import Mod
import server.extraServerApi as serverApi
import client.extraClientApi as clientApi
import TwilightBossSlice.config as config


@Mod.Binding(name=config.ModName, version=config.PACK_VERSION_STRING)
class TwilightBossSliceMod(object):

    @Mod.InitServer()
    def ServerInit(self):
        serverApi.RegisterSystem(
            config.ModName,
            config.ServerSystemName,
            config.ModName + ".serverSystem.ServerSystem"
        )

    @Mod.DestroyServer()
    def ServerDestroy(self):
        pass

    @Mod.InitClient()
    def ClientInit(self):
        clientApi.RegisterSystem(
            config.ModName,
            config.ClientSystemName,
            config.ModName + ".clientSystem.ClientSystem"
        )

    @Mod.DestroyClient()
    def ClientDestroy(self):
        pass
