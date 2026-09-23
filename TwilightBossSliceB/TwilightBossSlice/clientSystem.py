# -*- coding: utf-8 -*-
import math
import mod_log
import random
import time

import client.extraClientApi as clientApi
import TwilightBossSlice.config as config
import TwilightBossSlice.boss_hud_logic as boss_hud_logic
import TwilightBossSlice.clientItemLogic as clientItemLogic
import TwilightBossSlice.chain_visual_client as chain_visual_client
import TwilightBossSlice.fortification_visual_logic as fortification_visual_logic
import TwilightBossSlice.fortification_player_layer as fortification_player_layer
import TwilightBossSlice.fireReactUI as fireReactUI
import TwilightBossSlice.hydra_logic as hydra_logic
import TwilightBossSlice.lichBossHudUI as lichBossHudUI
import TwilightBossSlice.ur_ghast_effect_logic as ur_ghast_effect_logic
import TwilightBossSlice.ur_ghast_hitbox_debug_logic as hitbox_debug
import TwilightBossSlice.magicMapHudUI as magicMapHudUI
import TwilightBossSlice.magicMapUI as magicMapUI
import TwilightBossSlice.native_item_diagnostics as native_item_diagnostics
import TwilightBossSlice.nagaBossHudUI as nagaBossHudUI
import TwilightBossSlice.portal_logic as portal_logic
import TwilightBossSlice.portalLoadingUI as portalLoadingUI
import TwilightBossSlice.routeBossHudUI as routeBossHudUI


CF = clientApi.GetEngineCompFactory()
LEVEL_ID = clientApi.GetLevelId()
ENGINE_NAMESPACE = clientApi.GetEngineNamespace()
ENGINE_SYSTEM = clientApi.GetEngineSystemName()
NAGA_STUNLESS_STATE = 4
NAGA_DAZE_STATE = 5
FORTIFICATION_SHIELD_QUERY = "query.mod.tf_fortification_shields"
FORTIFICATION_VISUAL_IDENTIFIER = "tf_slice:fortification_shield_visual"
FORTIFICATION_MAX_ANCHOR_DISTANCE_SQ = 64.0


class ClientSystem(clientApi.GetClientSystemCls()):
    """Read-only client replica. It never proposes boss gameplay state."""

    def __init__(self, namespace, systemName):
        super(ClientSystem, self).__init__(namespace, systemName)
        self.ListenForEvent(config.ModName, config.ServerSystemName,
                            "TorchberryGlow", self, self.OnTorchberryGlow)
        self._last_sequence = -1
        self._chain_visuals = chain_visual_client.ChainVisuals(
            CF, LEVEL_ID, local_player=clientApi.GetLocalPlayerId,
            trace_path=chain_visual_client.diagnostic_path(),
            create_visual=self.CreateClientEntityByTypeStr,
            destroy_visual=self.DestroyClientEntity)
        self.ListenForEvent(config.ModName, config.ServerSystemName,
                            "BlockChainVisual", self, self.OnBlockChainVisual)
        self.ListenForEvent(ENGINE_NAMESPACE, ENGINE_SYSTEM,
                            "GameRenderTickEvent", self, self.OnBlockChainRender)
        self._received_packets = 0
        self._sequence_gaps = 0
        self._bosses = {}
        self._perf = {}
        self._ambient_tick = 0
        self._naga_effect_tick = 0
        self._ambient_particle_comp = CF.CreateParticleSystem(None)
        self._twilight_cloud_particle_comp = CF.CreateParticleSystem(None)
        self._twilight_cloud_particle_ids = []
        self._twilight_cloud_tick = 0
        try:
            self._ambient_biome_comp = CF.CreateBiome(LEVEL_ID)
        except Exception:
            self._ambient_biome_comp = None
        self._twilight_sky_diagnostic_count = 0
        self._magic_map_diagnostic_count = 0
        self._native_item_diag_sequence = 0
        self._twilight_sky_last_dimension = None
        self._twilight_sky_last_signature = None
        try:
            clientApi.SetMcpModLogCanPostDump(True)
        except Exception:
            pass
        # SkyRender touches LevelRenderer internally. Creating or calling it
        # from the client-system constructor races world rendering startup and
        # produces "has not levelrenderer" without applying a skybox.
        self._sky_render_comp = None
        self._twilight_sky_ui_ready = False
        self._twilight_sky_render_ready = False
        self._twilight_dimension_switching = False
        self._twilight_sky_render_warmup_tick = 0
        self._twilight_sky_active = False
        self._twilight_sky_override_dirty = False
        self._twilight_sky_refresh_tick = 0
        self._magic_map_ui_ready = False
        self._fire_react_ui_ready = False
        self._magic_map_hud_registered = False
        self._magic_map_hud_ui_ready = False
        self._magic_map_hud_node = None
        self._magic_map_native_screen_manager = None
        self._magic_map_native_proxy_registered = False
        self._magic_map_skin_ready = False
        self._magic_map_pose_registered = False
        self._magic_map_ui_retry_tick = 0
        self._magic_map_hold_tick = 0
        self._magic_map_was_held = False
        self._magic_map_held_signature = None
        self._magic_map_event_main_held = None
        self._magic_map_server_held = False
        self._pending_magic_map_snapshot = None
        self._lich_boss_hud_registered = False
        self._lich_boss_hud_node = None
        self._naga_boss_hud_registered = False
        self._naga_boss_hud_node = None
        self._minoshroom_boss_hud_registered = False
        self._minoshroom_boss_hud_node = None
        self._hydra_boss_hud_registered = False
        self._hydra_boss_hud_node = None
        self._knight_phantoms_boss_hud_registered = False
        self._knight_phantoms_boss_hud_node = None
        self._ur_ghast_boss_hud_registered = False
        self._ur_ghast_boss_hud_node = None
        self._portal_loading_registered = False
        self._portal_loading_ui_ready = False
        self._portal_loading_ui_attempts = 0
        self._portal_loading_ui_retry_at = 0
        self._portal_loading_node = None
        self._portal_loading_active = False
        self._portal_loading_destination = None
        self._portal_loading_token = None
        self._portal_loading_ready_ticks = 0
        self._portal_loading_loaded_chunks = set()
        self._portal_loading_required_chunks = set()
        self._portal_dimension_finish_seen = False
        self._portal_engine_ready_token = None
        self._portal_engine_ready_ticks = 0
        self._portal_engine_ready_ack_sent = False
        self._portal_loading_tick = 0
        self._portal_loading_deadline_tick = 0
        self._portal_loading_ack_sent = False
        self._lich_effect_tick = 0
        self._route_effect_tick = 0
        self._lich_projectile_trails = {}
        self._fortification_visuals = {}
        self._fortification_query_registered = False
        self._fortification_player_layer = (
            fortification_player_layer.PlayerShieldLayer(CF, LEVEL_ID)
            if config.FORTIFICATION_USE_PLAYER_LAYER else None)
        if self._fortification_player_layer is None:
            self.ListenForEvent(ENGINE_NAMESPACE, ENGINE_SYSTEM,
                                "GameRenderTickEvent", self, self.OnFortificationRender)
        self._hydra_actor_visuals = {}
        self._ur_ghast_effect_frame = 0
        self._ur_ghast_effect_tick = 0
        self._ur_ghast_storms = {}
        self._ur_ghast_storm_intensity = 0.0
        self._ur_ghast_last_rain_sound_tick = -1000
        self._ur_ghast_hitbox_enabled = False
        self._ur_ghast_hitbox_key_down = False
        self._ur_ghast_hitbox_shapes = {}
        try:
            self._ur_ghast_hitbox_drawing_comp = CF.CreateDrawing(LEVEL_ID)
        except Exception:
            self._ur_ghast_hitbox_drawing_comp = None
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "OnScriptTickClient",
            self,
            self.OnScriptTickClient,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "OnKeyPressInGame",
            self,
            self.OnKeyPressInGame,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "DimensionChangeClientEvent",
            self,
            self.OnDimensionChangeClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "DimensionChangeFinishClientEvent",
            self,
            self.OnDimensionChangeFinishClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "ChunkLoadedClientEvent",
            self,
            self.OnChunkLoadedClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "UiInitFinished",
            self,
            self.OnUiInitFinished,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "UpdatePlayerSkinClientEvent",
            self,
            self.OnUpdatePlayerSkinClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "OnCarriedNewItemChangedClientEvent",
            self,
            self.OnCarriedNewItemChangedClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "ClientItemTryUseEvent",
            self,
            self.OnKnightItemTryUseClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "ClientItemUseOnEvent",
            self,
            self.OnKnightItemUseOnClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "RightClickBeforeClientEvent",
            self,
            self.OnKnightRightClickBeforeClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "RightClickReleaseClientEvent",
            self,
            self.OnKnightRightClickReleaseClientEvent,
        )
        self.ListenForEvent(
            ENGINE_NAMESPACE,
            ENGINE_SYSTEM,
            "TapOrHoldReleaseClientEvent",
            self,
            self.OnTapOrHoldReleaseClientEvent,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "BossSync",
            self,
            self.OnBossSync
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "TrophyBreakEffect",
            self,
            self.OnTrophyBreakEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "SaplingGrowthEffect",
            self,
            self.OnSaplingGrowthEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "BossHudReset",
            self,
            self.OnBossHudReset,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "HydraHeadSync",
            self,
            self.OnHydraHeadSync,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "HydraActorFrame",
            self,
            self.OnHydraActorFrame,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "PerfSync",
            self,
            self.OnPerfSync
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "NagaSegmentBurst",
            self,
            self.OnNagaSegmentBurst
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "NagaCombatEffect",
            self,
            self.OnNagaCombatEffect
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "NagaDeathEffect",
            self,
            self.OnNagaDeathEffect
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "BeetleCombatEffect",
            self,
            self.OnBeetleCombatEffect
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "LichCombatEffect",
            self,
            self.OnLichCombatEffect
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "HydraRouteEffect",
            self,
            self.OnHydraRouteEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "FireSwampDeviceEffect",
            self,
            self.OnFireSwampDeviceEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "GhastTrapEffect",
            self,
            self.OnGhastTrapEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "DarkTowerMechanismEffect",
            self,
            self.OnDarkTowerMechanismEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "KnightPhantomEffect",
            self,
            self.OnKnightPhantomEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "UrGhastEffect",
            self,
            self.OnUrGhastEffect,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "FireReactOpen",
            self,
            self.OnFireReactOpen,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "MagicMapSnapshot",
            self,
            self.OnMagicMapSnapshot,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "MagicMapDelta",
            self,
            self.OnMagicMapDelta,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "MagicMapHeldState",
            self,
            self.OnMagicMapHeldState,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "PortalArrivalPrepared",
            self,
            self.OnPortalArrivalPrepared,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "PortalArrivalRelocated",
            self,
            self.OnPortalArrivalRelocated,
        )
        self.ListenForEvent(
            config.ModName,
            config.ServerSystemName,
            "PortalArrivalFinished",
            self,
            self.OnPortalArrivalFinished,
        )
        self._register_magic_map_hud_proxy()
        print "[TwilightBossSlice] client system ready"

    def Destroy(self):
        self._chain_visuals.clear()
        self._clear_ur_ghast_hitbox_shapes()
        self._clear_hydra_actor_visuals(True)
        self._clear_fortification_visuals()
        lichBossHudUI.set_bosses([])
        nagaBossHudUI.set_bosses([])
        routeBossHudUI.set_minoshrooms([])
        routeBossHudUI.set_hydras([])
        routeBossHudUI.set_knight_phantoms([])
        routeBossHudUI.set_ur_ghasts([])
        self._portal_loading_ui_ready = False
        portalLoadingUI.invalidate()
        self._end_portal_loading()
        fireReactUI.set_submit_callback(None)
        magicMapHudUI.set_held_visible(False)
        self._unregister_magic_map_hud_proxy()
        self._reset_twilight_cloud_layer()
        # LevelRenderer can already be gone when the client system is
        # destroyed. Do not call reset methods after that point.
        self._twilight_sky_render_ready = False
        self._reset_twilight_sky()
        print "[TwilightBossSlice] client system destroyed"

    def OnBlockChainVisual(self, args):
        self._chain_visuals.receive(args)

    def OnBlockChainRender(self, args=None):
        self._chain_visuals.render()

    def Update(self):
        self._magic_map_ui_retry_tick += 1
        held_hud_ready = (
            not config.MAGIC_MAP_HELD_HUD_ENABLED
            or (
                self._magic_map_hud_ui_ready
                and magicMapHudUI.is_active()
            )
        )
        if not (
            self._magic_map_ui_ready
            and held_hud_ready
        ):
            if self._magic_map_ui_retry_tick % 20 == 0:
                self._ensure_magic_map_ui()
        if (
            not self._magic_map_pose_registered
            and self._magic_map_ui_retry_tick % 40 == 0
        ):
            self._ensure_magic_map_player_pose()
        self._update_ambient_fireflies()

    def OnScriptTickClient(self):
        # ClientSystem.Update is not continuously scheduled by every NetEase
        # client lifecycle. The engine tick event is the stable 30 Hz driver.
        self._update_portal_loading()
        self._update_twilight_sky()
        self._update_twilight_cloud_layer()
        self._update_naga_state_effects()
        self._update_lich_state_effects()
        self._update_hydra_route_effects()
        self._update_hydra_actor_visuals()
        self._tick_ur_ghast_storm_presentation()
        self._update_ur_ghast_hitbox_debug()
        if config.MAGIC_MAP_HELD_HUD_ENABLED:
            self._update_magic_map_hud()

    def _notify_ur_ghast_hitbox_state(self):
        message = (
            u"暮色恶魂碰撞箱：开启（红=物理，绿=头身攻击）"
            if self._ur_ghast_hitbox_enabled
            else u"暮色恶魂碰撞箱：关闭"
        )
        try:
            CF.CreateTextNotifyClient(LEVEL_ID).SetLeftCornerNotify(message)
        except Exception:
            try:
                CF.CreateGame(LEVEL_ID).SetTipMessage(message)
            except Exception:
                pass

    def OnKeyPressInGame(self, args):
        if not isinstance(args, dict):
            return
        transition = hitbox_debug.key_transition(
            self._ur_ghast_hitbox_enabled,
            self._ur_ghast_hitbox_key_down,
            args.get("key"),
            args.get("isDown"),
        )
        self._ur_ghast_hitbox_enabled = transition["enabled"]
        self._ur_ghast_hitbox_key_down = transition["keyDown"]
        if not transition["toggled"]:
            return
        if not self._ur_ghast_hitbox_enabled:
            self._clear_ur_ghast_hitbox_shapes()
        else:
            self._update_ur_ghast_hitbox_debug()
        self._notify_ur_ghast_hitbox_state()

    @staticmethod
    def _remove_ur_ghast_hitbox_shape(shape):
        if shape is None:
            return
        try:
            shape.Remove()
        except Exception:
            pass

    def _clear_ur_ghast_hitbox_shapes(self, bossId=None):
        keys = (
            list(self._ur_ghast_hitbox_shapes)
            if bossId is None
            else [str(bossId)]
        )
        for key in keys:
            shapes = self._ur_ghast_hitbox_shapes.pop(key, {})
            for shape in shapes.values():
                self._remove_ur_ghast_hitbox_shape(shape)

    def _create_ur_ghast_hitbox_shapes(self, bossId, descriptors):
        if self._ur_ghast_hitbox_drawing_comp is None:
            try:
                self._ur_ghast_hitbox_drawing_comp = CF.CreateDrawing(
                    LEVEL_ID
                )
            except Exception:
                return False
        shapes = {}
        try:
            for descriptor in descriptors:
                shape = self._ur_ghast_hitbox_drawing_comp.AddBoxShape(
                    descriptor["center"],
                    descriptor["scale"],
                    descriptor["color"],
                )
                if not shape:
                    raise ValueError("Drawing AddBoxShape returned None")
                try:
                    shape.SetPriority(descriptor["priority"])
                except Exception:
                    pass
                shapes[descriptor["name"]] = shape
        except Exception:
            for shape in shapes.values():
                self._remove_ur_ghast_hitbox_shape(shape)
            return False
        self._ur_ghast_hitbox_shapes[str(bossId)] = shapes
        return True

    def _update_ur_ghast_hitbox_debug(self):
        if not self._ur_ghast_hitbox_enabled:
            if self._ur_ghast_hitbox_shapes:
                self._clear_ur_ghast_hitbox_shapes()
            return
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
        except Exception:
            currentDimension = None
        activeBosses = set()
        for bossId, boss in list(self._bosses.items()):
            if boss.get("kind") != "ur_ghast" or boss.get("dying"):
                continue
            if boss.get("dimensionId") != currentDimension:
                continue
            try:
                footPosition = CF.CreatePos(bossId).GetFootPos()
            except Exception:
                footPosition = None
            descriptors = hitbox_debug.box_descriptors(footPosition)
            if not descriptors:
                continue
            bossKey = str(bossId)
            activeBosses.add(bossKey)
            shapes = self._ur_ghast_hitbox_shapes.get(bossKey)
            if shapes is None:
                self._create_ur_ghast_hitbox_shapes(
                    bossKey, descriptors
                )
                continue
            valid = True
            for descriptor in descriptors:
                shape = shapes.get(descriptor["name"])
                try:
                    if shape is None or shape.SetPos(
                        descriptor["center"]
                    ) is False:
                        valid = False
                        break
                except Exception:
                    valid = False
                    break
            if not valid:
                self._clear_ur_ghast_hitbox_shapes(bossKey)
        for bossKey in list(self._ur_ghast_hitbox_shapes):
            if bossKey not in activeBosses:
                self._clear_ur_ghast_hitbox_shapes(bossKey)

    def OnTrophyBreakEffect(self, args):
        try:
            if int(args["dimensionId"]) != int(
                CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            ):
                return
            center = (
                float(args["x"]) + 0.5,
                float(args["y"]) + 0.65,
                float(args["z"]) + 0.5,
            )
        except (KeyError, TypeError, ValueError):
            return
        # The transparent block anchor cannot supply vanilla terrain fragments.
        # This one-shot emitter samples the visible trophy texture instead.
        self._spawn_naga_state_particle("tf_slice:ur_ghast_trophy_break", center)

    def _spawn_naga_state_particle(
        self, particleName, position, manual=False, rotation=None
    ):
        try:
            particleId = self._ambient_particle_comp.Create(
                particleName,
                position,
                rotation or (0.0, 0.0, 0.0),
            )
            if particleId:
                self._ambient_particle_comp.SetPos(particleId, position)
                if manual or particleName in (
                    "minecraft:basic_flame_particle",
                    "minecraft:basic_smoke_particle",
                    "minecraft:water_splash_particle_manual",
                ):
                    self._ambient_particle_comp.EmitManually(particleId)
            return bool(particleId)
        except Exception:
            return False

    def OnSaplingGrowthEffect(self, args):
        try:
            currentDimension = int(
                CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            )
            eventDimension = int(args.get("dimensionId", -1))
            rawPosition = args.get("position", ())
            position = (
                float(rawPosition[0]) + 0.5,
                float(rawPosition[1]) + 0.35,
                float(rawPosition[2]) + 0.5,
            )
        except (AttributeError, TypeError, ValueError, IndexError):
            return
        except Exception:
            return
        if currentDimension != eventDimension:
            return
        count = 1
        if bool(args.get("advanced", False)):
            count = 2
        if bool(args.get("grown", False)):
            count = 4
        for unusedIndex in range(count):
            self._spawn_naga_state_particle(
                "minecraft:crop_growth_emitter",
                (
                    position[0] + random.uniform(-0.18, 0.18),
                    position[1] + random.uniform(0.0, 0.35),
                    position[2] + random.uniform(-0.18, 0.18),
                ),
                manual=True,
            )

    def OnFireSwampDeviceEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
            rawPosition = args.get("position", ())
            position = (
                float(rawPosition[0]) + 0.5,
                float(rawPosition[1]),
                float(rawPosition[2]) + 0.5,
            )
        except (TypeError, ValueError, IndexError):
            return
        if currentDimension != eventDimension:
            return
        effect = str(args.get("effect", ""))
        if effect == "smoke":
            self._spawn_naga_state_particle(
                "minecraft:basic_smoke_particle",
                (position[0], position[1] + 0.95, position[2]),
            )
            return
        if effect == "pop":
            for _index in range(8):
                self._spawn_naga_state_particle(
                    "minecraft:lava_particle",
                    (
                        position[0] + random.uniform(-0.15, 0.15),
                        position[1] + 1.5,
                        position[2] + random.uniform(-0.15, 0.15),
                    ),
                )
        elif effect == "flame":
            self._spawn_naga_state_particle(
                "minecraft:basic_smoke_particle",
                (position[0], position[1] + 2.0, position[2]),
            )
            for offset in (
                (0.0, 2.0, 0.0),
                (-1.0, 2.0, 0.0),
                (0.0, 2.0, -1.0),
                (1.0, 2.0, 0.0),
                (0.0, 2.0, 1.0),
            ):
                self._spawn_naga_state_particle(
                    "tf_slice:hydra_flame",
                    (
                        position[0] + offset[0],
                        position[1] + offset[1],
                        position[2] + offset[2],
                    ),
                )
        soundName = {
            "pop": "liquid.lava",
            "jet_start": "fire.ignite",
            "jet_active": "fire.fire",
            "smoker_toggle": "random.fizz",
        }.get(effect)
        if soundName is None:
            return
        try:
            CF.CreateCustomAudio(LEVEL_ID).PlayCustomMusic(
                soundName,
                position,
                0.3 if effect in ("pop", "smoker_toggle") else 1.0,
                0.6 if effect in ("jet_start", "smoker_toggle") else 1.0,
                False,
                "",
            )
        except Exception:
            pass

    def _update_hydra_route_effects(self):
        self._route_effect_tick += 1
        if self._route_effect_tick % 3 == 0:
            return
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
        except Exception:
            return
        if self._route_effect_tick % 20 != 0:
            return
        try:
            playerId = clientApi.GetLocalPlayerId()
            position = CF.CreatePos(playerId).GetFootPos()
            if currentDimension != config.DIMENSION_ID or position is None:
                return
            biomeName = self._ambient_biome_comp.GetBiomeName(
                int(position[0]), int(position[2]), config.DIMENSION_ID
            )
        except Exception:
            return
        if str(biomeName).endswith("swampland_mutated"):
            self._spawn_naga_state_particle(
                "tf_slice:fire_swamp_ash",
                (
                    position[0] + random.uniform(-8.0, 8.0),
                    position[1] + random.uniform(2.0, 7.0),
                    position[2] + random.uniform(-8.0, 8.0),
                ),
            )

    def _update_naga_state_effects(self):
        # OnScriptTickClient runs at 30 Hz. Skipping every third callback
        # reproduces the original boss's 20 Hz client particle cadence.
        self._naga_effect_tick += 1
        if self._naga_effect_tick % 3 == 0:
            return
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
        except Exception:
            return
        for bossId, boss in self._bosses.items():
            if boss.get("kind") != "naga":
                continue
            if boss.get("dimensionId") != currentDimension:
                continue
            state = int(boss.get("state", 0))
            if state not in (NAGA_STUNLESS_STATE, NAGA_DAZE_STATE):
                continue
            if state == NAGA_DAZE_STATE:
                continue
            try:
                footPos = CF.CreatePos(bossId).GetFootPos()
            except Exception:
                continue
            if not footPos:
                continue
            angle = random.random() * math.pi * 2.0
            radius = random.random() * 0.85
            position = (
                float(footPos[0]) + math.cos(angle) * radius,
                float(footPos[1]) + 2.25,
                float(footPos[2]) + math.sin(angle) * radius,
            )
            self._spawn_naga_state_particle(
                "minecraft:villager_angry", position
            )

    def _clear_fortification_visuals(self):
        for ownerId in list(self._fortification_visuals):
            self._destroy_fortification_client_visual(ownerId)

    def _destroy_fortification_client_visual(self, ownerId):
        visual = self._fortification_visuals.get(ownerId)
        if visual is None:
            return
        visual["count"] = 0
        visual["removing"] = True
        layer = getattr(self, "_fortification_player_layer", None)
        if layer is not None:
            if layer.set_count(ownerId, 0, self._lich_effect_tick):
                self._fortification_visuals.pop(ownerId, None)
            return
        if self._remove_fortification_visual_entity(visual):
            self._fortification_visuals.pop(ownerId, None)

    def _remove_fortification_visual_entity(self, visual):
        previous = visual.get("previousVisual")
        if previous is not None:
            if not self._remove_fortification_visual_entity(previous):
                return False
            visual.pop("previousVisual", None)
        visualId = visual.get("entityId")
        if not visualId:
            return True
        ownerId = visual.get("ownerId")
        if ownerId is None or str(visualId) == str(ownerId):
            print "[TwilightBossSlice] refusing unsafe fortification removal:", visualId, ownerId
            return False
        if self._lich_effect_tick < int(visual.get("nextRemovalRetry", 0)):
            return False
        visual["nextRemovalRetry"] = self._lich_effect_tick + 30
        try:
            if visual.get("bound"):
                detached = CF.CreateModel(visualId).ResetBindEntity()
                if detached is not True:
                    if not visual.get("detachFailureLogged"):
                        print "[TwilightBossSlice] fortification detach failed:", visualId, ownerId, detached
                        visual["detachFailureLogged"] = True
                    return False
                visual["bound"] = False
            destroyed = self.DestroyClientEntity(visualId)
            if destroyed is False:
                return False
        except Exception as exc:
            if not visual.get("removalFailureLogged"):
                print "[TwilightBossSlice] fortification removal failed:", visualId, ownerId, exc
                visual["removalFailureLogged"] = True
            return False
        print "[TwilightBossSlice] fortification visual removed:", visualId, ownerId
        for key in ("entityId", "appliedCount", "anchorPosition", "nextRemovalRetry", "nextCountRetry", "lastOffset", "nextOffsetRetry", "modelComp", "basis", "nextBasisCheck", "expectedRoot", "nextFollowCheck", "followError"):
            visual.pop(key, None)
        return True

    def _ensure_fortification_query_registered(self):
        if self._fortification_query_registered:
            return True
        try:
            result = CF.CreateQueryVariable(LEVEL_ID).Register(
                FORTIFICATION_SHIELD_QUERY, 0.0
            )
            if CF.CreateQueryVariable(LEVEL_ID).Register(
                "query.mod.tf_fortification_time", 0.0
            ) is False:
                result = False
            for axis in ("x", "y", "z"):
                registered = CF.CreateQueryVariable(LEVEL_ID).Register(
                    "query.mod.tf_fortification_d" + axis, 0.0
                )
                if registered is False:
                    result = False
            self._fortification_query_registered = result is not False
        except Exception:
            self._fortification_query_registered = False
        return self._fortification_query_registered

    def _set_fortification_visual_count(self, visual, shieldCount):
        visualId = visual.get("entityId")
        if not visualId:
            return False
        if self._lich_effect_tick < int(visual.get("nextCountRetry", 0)):
            return False
        visual["nextCountRetry"] = self._lich_effect_tick + 30
        self._ensure_fortification_query_registered()
        try:
            query = CF.CreateQueryVariable(visualId)
            result = query.Set(
                "query.mod.tf_fortification_time", visual.get("motion", {}).get("age", 0.0)
            )
            if result is not False:
                result = query.Set(FORTIFICATION_SHIELD_QUERY, float(shieldCount))
        except Exception:
            result = False
        diagnostic = (visualId, shieldCount, result)
        if visual.get("countDiagnostic") != diagnostic:
            print "[TwilightBossSlice] fortification count result:", diagnostic
            visual["countDiagnostic"] = diagnostic
        if result is not False:
            visual["nextCountRetry"] = 0
            visual["appliedCount"] = int(shieldCount)
            self._fortification_query_registered = True
            return True
        return False

    def _create_fortification_client_visual(
        self, ownerId, visual, ownerPosition
    ):
        if self._lich_effect_tick < int(visual.get("nextCreateRetry", 0)):
            return False
        visual["nextCreateRetry"] = self._lich_effect_tick + 30
        # Register the query before the engine first parses this entity's render data.
        self._ensure_fortification_query_registered()
        try:
            visualId = self.CreateClientEntityByTypeStr(
                FORTIFICATION_VISUAL_IDENTIFIER,
                ownerPosition,
                (0.0, 0.0),
            )
        except Exception as exc:
            print "[TwilightBossSlice] fortification model create failed:", exc
            return False
        if not visualId:
            if not visual.get("createFailureLogged"):
                print "[TwilightBossSlice] fortification factory returned no entity:", FORTIFICATION_VISUAL_IDENTIFIER
                visual["createFailureLogged"] = True
            return False
        if str(visualId) == str(ownerId):
            print "[TwilightBossSlice] refusing player id as fortification visual:", ownerId
            return False
        # Retry backoff applies only to failed creation, not a successful
        # visual that needs a new anchor after fast movement.
        visual.pop("nextCreateRetry", None)
        visual["entityId"] = visualId
        visual["ownerId"] = ownerId
        visual["bound"] = False
        visual.setdefault("motion", {})
        print "[TwilightBossSlice] fortification independent model created:", visualId, ownerId
        visual["anchorPosition"] = tuple(ownerPosition)
        self._set_fortification_visual_count(
            visual, max(0, min(5, int(visual.get("count", 0))))
        )
        return True

    def _update_fortification_visuals(self, currentDimension):
        for ownerId, visual in list(self._fortification_visuals.items()):
            if visual.get("removing") or int(visual.get("count", 0)) <= 0:
                self._destroy_fortification_client_visual(ownerId)
                continue
            if int(visual.get("dimensionId", -1)) != int(currentDimension):
                self._destroy_fortification_client_visual(ownerId)
                continue
            try:
                ownerPosition = CF.CreatePos(ownerId).GetFootPos()
            except Exception:
                ownerPosition = None
            if ownerPosition is None:
                missingSince = visual.setdefault("missingSince", self._lich_effect_tick)
                if self._lich_effect_tick - missingSince >= 90:
                    self._destroy_fortification_client_visual(ownerId)
                continue
            visual.pop("missingSince", None)
            layer = getattr(self, "_fortification_player_layer", None)
            if layer is not None:
                layer.set_count(ownerId, visual.get("count", 0), self._lich_effect_tick)
                continue
            if not visual.get("entityId"):
                self._create_fortification_client_visual(
                    ownerId, visual, ownerPosition
                )
                continue
            shieldCount = max(0, min(5, int(visual.get("count", 0))))
            if int(visual.get("appliedCount", -1)) != shieldCount:
                self._set_fortification_visual_count(visual, shieldCount)
            anchor = visual.get("anchorPosition") or ownerPosition
            distanceSq = sum(
                (float(ownerPosition[index]) - float(anchor[index])) ** 2
                for index in range(3)
            )
            if (distanceSq > FORTIFICATION_MAX_ANCHOR_DISTANCE_SQ
                    and not visual.get("previousVisual")
                    and self._lich_effect_tick >= int(visual.get("nextCreateRetry", 0))):
                # Keep the existing model alive until the replacement has
                # received its phase/position/count and crossed a render tick.
                replacement = dict(count=shieldCount, dimensionId=visual.get("dimensionId"),
                                   motion=visual.setdefault("motion", {}))
                if self._create_fortification_client_visual(ownerId, replacement, ownerPosition):
                    previous = dict(visual)
                    visual.clear()
                    visual.update(replacement)
                    visual["previousVisual"] = previous
                else:
                    visual["nextCreateRetry"] = replacement.get("nextCreateRetry", self._lich_effect_tick + 30)

    def OnFortificationRender(self, args=None):
        if getattr(self, "_fortification_player_layer", None) is not None:
            return
        if self._twilight_dimension_switching:
            return
        now = getattr(self, "_fortification_clock", fortification_visual_logic.render_clock)()
        entries = []
        for ownerId, visual in list(self._fortification_visuals.items()):
            if visual.get("previousVisual") and not visual.get("removing"):
                entries.append((ownerId, visual["previousVisual"]))
            entries.append((ownerId, visual))
        for ownerId, visual in entries:
            visualId = visual.get("entityId")
            anchor = visual.get("anchorPosition")
            if not visualId or anchor is None or visual.get("removing"):
                continue
            if str(visualId) == str(ownerId):
                continue
            if self._lich_effect_tick < int(visual.get("nextOffsetRetry", 0)):
                continue
            try:
                ownerPosition = CF.CreatePos(ownerId).GetFootPos()
                if ownerPosition is None:
                    continue
                ownerPosition, animationTime = fortification_visual_logic.sample(
                    visual.setdefault("motion", {}), ownerPosition, now)
                offset = tuple(float(ownerPosition[i]) - float(anchor[i]) for i in range(3))
                basis = visual.get("basis")
                if basis is None and self._lich_effect_tick >= int(visual.get("nextBasisCheck", 0)):
                    visual["nextBasisCheck"] = self._lich_effect_tick + 30
                    # Bone reads are optional calibration, never a prerequisite
                    # for following: client BB models can return None here.
                    try:
                        modelComp = visual.get("modelComp")
                        if modelComp is None:
                            modelComp = CF.CreateModel(visualId)
                            visual["modelComp"] = modelComp
                        origin = modelComp.GetBonePositionFromMinecraftObject("tf_anchor")
                        probes = tuple(modelComp.GetBonePositionFromMinecraftObject(name)
                                       for name in ("tf_basis_x", "tf_basis_y", "tf_basis_z"))
                        if chain_visual_client.local_endpoint(origin, probes, origin) is not None:
                            # root's pivot is (0,16,0); these probes are outside
                            # the animated root, so late calibration stays valid.
                            basis = (origin, probes, probes[1])
                            visual["basis"] = basis
                            visual.pop("lastOffset", None)
                    except Exception:
                        pass
                if basis is None:
                    # The independent visual is spawned at yaw zero. This is
                    # the zero-yaw transform used by block_chain_projectile:
                    # world (dx,dy,dz) -> BB (16*dx,16*dy,-16*dz).
                    origin = tuple(float(value) for value in anchor)
                    probes = ((origin[0] + 1.0, origin[1], origin[2]),
                              (origin[0], origin[1] + 1.0, origin[2]),
                              (origin[0], origin[1], origin[2] - 1.0))
                    basis = (origin, probes, probes[1])
                origin, probes, root = basis
                # Compare the last requested root with the rendered bone on a
                # later frame. API return values alone cannot prove movement.
                if self._lich_effect_tick >= int(visual.get("nextFollowCheck", 0)):
                    visual["nextFollowCheck"] = self._lich_effect_tick + 30
                    try:
                        modelComp = visual.get("modelComp")
                        actual = modelComp.GetBonePositionFromMinecraftObject("root") if modelComp else None
                    except Exception:
                        actual = None
                    expected = visual.get("expectedRoot")
                    if actual is not None and expected is not None:
                        error = math.sqrt(sum((float(actual[i]) - expected[i]) ** 2 for i in range(3)))
                        previous = visual.get("followError")
                        visual["followError"] = error
                        if previous is None or (previous > 0.25) != (error > 0.25):
                            print "[TwilightBossSlice] fortification follow readback:", visualId, "actual", actual, "expected", expected, "error", error
                query = CF.CreateQueryVariable(visualId)
                if query.Set("query.mod.tf_fortification_time", animationTime) is False:
                    raise RuntimeError("shield animation time write failed")
                previous = visual.get("previousVisual")
                if (previous is not None and visual.get("renderReadyTick") is not None
                        and self._lich_effect_tick > visual["renderReadyTick"]
                        and int(visual.get("appliedCount", -1)) == int(visual.get("count", 0))):
                    if self._remove_fortification_visual_entity(previous):
                        visual.pop("previousVisual", None)
                if visual.get("lastOffset") == offset:
                    continue
                target = tuple(float(origin[i]) + offset[i] for i in range(3))
                # Reuse the measured-basis conversion already used by BB chain
                # geometry; this includes the engine's axis reflections and units.
                local = chain_visual_client.local_endpoint(origin, probes, target)
                if local is None:
                    raise RuntimeError("invalid shield render basis")
                for axis, value in zip(("x", "y", "z"), local):
                    if query.Set("query.mod.tf_fortification_d" + axis, value) is False:
                        raise RuntimeError("shield animation position write failed")
                visual["lastOffset"] = offset
                visual.setdefault("renderReadyTick", self._lich_effect_tick)
                visual["expectedRoot"] = tuple(float(root[i]) + offset[i] for i in range(3))
            except Exception as exc:
                visual["nextOffsetRetry"] = self._lich_effect_tick + 30
                if not visual.get("offsetFailureLogged"):
                    print "[TwilightBossSlice] fortification model offset failed:", visualId, exc
                    visual["offsetFailureLogged"] = True

    def _update_lich_state_effects(self):
        self._lich_effect_tick += 1
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
        except Exception:
            return
        self._update_fortification_visuals(currentDimension)
        # The engine callback is 30 Hz; the source visual tick is 20 Hz.
        if self._lich_effect_tick % 3 != 0:
            for bossId, boss in self._bosses.items():
                if (
                    boss.get("kind") != "lich"
                    or boss.get("dimensionId") != currentDimension
                ):
                    continue
                try:
                    footPos = CF.CreatePos(bossId).GetFootPos()
                except Exception:
                    footPos = None
                if not footPos:
                    continue
                if int(boss.get("phase", 1)) == 3:
                    self._spawn_naga_state_particle(
                        "tf_slice:lich_angry",
                        (
                            float(footPos[0]) + random.uniform(-1.1, 1.1),
                            float(footPos[1]) + random.uniform(1.0, 3.1),
                            float(footPos[2]) + random.uniform(-1.1, 1.1),
                        ),
                    )
                attackCooldown = max(
                    0, int(boss.get("attackCooldown", 0))
                )
                if attackCooldown <= 0:
                    continue
                spreadSteps = (80 - attackCooldown) // 10
                particleCount = (
                    random.randrange(spreadSteps)
                    if spreadSteps > 0
                    else 1
                )
                particleName = (
                    "tf_slice:lich_bomb_charge"
                    if int(boss.get("nextAttackType", 0)) != 0
                    else "tf_slice:lich_bolt_charge"
                )
                for _index in range(particleCount):
                    self._spawn_naga_state_particle(
                        particleName,
                        (
                            float(footPos[0]) + random.uniform(-0.18, 0.18),
                            float(footPos[1]) + random.uniform(1.72, 2.10),
                            float(footPos[2]) + random.uniform(-0.18, 0.18),
                        ),
                    )
                boss["attackCooldown"] = attackCooldown - 1
        for entityId, trail in list(self._lich_projectile_trails.items()):
            if self._lich_effect_tick >= int(trail.get("expires", 0)):
                self._lich_projectile_trails.pop(entityId, None)
                continue
            try:
                position = CF.CreatePos(entityId).GetFootPos()
            except Exception:
                position = None
            if not position:
                trail["missing"] = int(trail.get("missing", 0)) + 1
                if trail["missing"] > 6:
                    self._lich_projectile_trails.pop(entityId, None)
                continue
            trail["missing"] = 0
            style = str(trail.get("style", ""))
            if style == "tf_slice:twilight_wand_bolt":
                if self._lich_effect_tick % 4 != 0:
                    continue
                trailCount = 1
                particleName = "tf_slice:twilight_scepter_trail"
                jitter = 0.025
            else:
                if self._lich_effect_tick % 3 != 0:
                    continue
                trailCount = 1 if "bomb" in style else 2
                particleName = "tf_slice:lich_ominous_flame"
                jitter = 0.08
            for _index in range(trailCount):
                self._spawn_naga_state_particle(
                    particleName,
                    (
                        float(position[0]) + random.uniform(-jitter, jitter),
                        float(position[1]) + random.uniform(-jitter, jitter),
                        float(position[2]) + random.uniform(-jitter, jitter),
                    ),
                )

    def _is_local_dimension_event(self, args):
        if not isinstance(args, dict):
            return True
        playerId = args.get("playerId")
        localPlayerId = clientApi.GetLocalPlayerId()
        return (
            playerId is None
            or localPlayerId is None
            or str(playerId) == str(localPlayerId)
        )

    def _ensure_portal_loading_ui(self):
        # Native UI registration/creation is valid only after UiInitFinished.
        if not self._portal_loading_ui_ready:
            return False
        if portalLoadingUI.is_active():
            portalLoadingUI.set_visible(self._portal_loading_active)
            return True
        if (
            self._portal_loading_ui_attempts >= 3
            or self._portal_loading_tick < self._portal_loading_ui_retry_at
        ):
            return False
        self._portal_loading_ui_attempts += 1
        self._portal_loading_ui_retry_at = self._portal_loading_tick + 30
        try:
            node = clientApi.GetUI(
                config.ModName, config.PORTAL_LOADING_UI_NAME
            )
            if node is None:
                if not self._portal_loading_registered:
                    registered = clientApi.RegisterUI(
                        config.ModName,
                        config.PORTAL_LOADING_UI_NAME,
                        config.ModName + ".portalLoadingUI.PortalLoadingUI",
                        "portal_loading.main",
                    )
                    if registered is False:
                        return False
                    self._portal_loading_registered = True
                node = clientApi.CreateUI(
                    config.ModName,
                    config.PORTAL_LOADING_UI_NAME,
                    {"isHud": 1},
                )
                if node is None:
                    node = clientApi.GetUI(
                        config.ModName, config.PORTAL_LOADING_UI_NAME
                    )
            self._portal_loading_node = node
            if node is not None:
                node.Init()
            if not portalLoadingUI.is_active():
                # An absent engine definition must be registered again on a
                # bounded retry, rather than hammering CreateUI every tick.
                self._portal_loading_registered = False
                print "[TwilightBossSlice] portal loading UI unavailable; attempt", self._portal_loading_ui_attempts
                return False
            self._portal_loading_ui_attempts = 0
            portalLoadingUI.set_visible(self._portal_loading_active)
            return True
        except Exception as error:
            print "[TwilightBossSlice] portal loading UI initialization failed:", error
            self._portal_loading_node = None
            self._portal_loading_registered = False
            portalLoadingUI.invalidate()
            return False

    def _begin_portal_loading(self):
        self._portal_loading_active = True
        self._portal_loading_destination = None
        self._portal_loading_token = None
        self._portal_loading_ready_ticks = 0
        self._portal_loading_loaded_chunks = set()
        self._portal_loading_required_chunks = set()
        self._portal_dimension_finish_seen = False
        self._portal_engine_ready_token = None
        self._portal_engine_ready_ticks = 0
        self._portal_engine_ready_ack_sent = False
        self._portal_loading_ack_sent = False
        self._portal_loading_deadline_tick = (
            self._portal_loading_tick
            + config.PORTAL_CLIENT_LOADING_TIMEOUT_TICKS
        )
        self._ensure_portal_loading_ui()
        portalLoadingUI.set_visible(True)

    def _end_portal_loading(self):
        portalLoadingUI.set_visible(False)
        self._portal_loading_active = False
        self._portal_loading_destination = None
        self._portal_loading_token = None
        self._portal_loading_ready_ticks = 0
        self._portal_loading_loaded_chunks = set()
        self._portal_loading_required_chunks = set()
        self._portal_dimension_finish_seen = False
        self._portal_engine_ready_token = None
        self._portal_engine_ready_ticks = 0
        self._portal_engine_ready_ack_sent = False
        self._portal_loading_ack_sent = False

    def OnChunkLoadedClientEvent(self, args):
        if not self._portal_loading_active:
            return
        try:
            dimensionId = int(
                args.get("dimension", args.get("dimensionId", -1))
            )
            chunkX = int(args.get("chunkPosX"))
            chunkZ = int(args.get("chunkPosZ"))
        except (AttributeError, TypeError, ValueError):
            return
        if dimensionId != config.DIMENSION_ID:
            return
        self._portal_loading_loaded_chunks.add((chunkX, chunkZ))

    def _update_portal_loading(self):
        self._portal_loading_tick += 1
        if not self._portal_loading_active:
            return
        if (
            not portalLoadingUI.is_active()
            or self._portal_loading_tick % 20 == 0
        ):
            self._ensure_portal_loading_ui()
        portalLoadingUI.set_visible(True)
        if self._portal_engine_ready_token is not None:
            if self._portal_engine_ready_ack_sent:
                return
            if not self._portal_dimension_finish_seen:
                return
            if not portal_logic.client_required_chunks_loaded(
                self._portal_loading_required_chunks,
                self._portal_loading_loaded_chunks,
            ):
                return
            self._portal_engine_ready_ticks += 1
            if (
                self._portal_engine_ready_ticks
                < config.PORTAL_CLIENT_READY_STABLE_TICKS
            ):
                return
            try:
                self.NotifyToServer(
                    "PortalArrivalEngineReady",
                    {"token": self._portal_engine_ready_token},
                )
            except Exception as error:
                print (
                    "[TwilightBossSlice] portal engine-ready ACK failed:",
                    error,
                )
                return
            self._portal_engine_ready_ack_sent = True
            return
        if (
            self._portal_loading_destination is None
            or self._portal_loading_ack_sent
        ):
            return
        playerId = clientApi.GetLocalPlayerId()
        if playerId is None:
            return
        destination = self._portal_loading_destination
        if not portal_logic.client_required_chunks_loaded(
            self._portal_loading_required_chunks,
            self._portal_loading_loaded_chunks,
        ):
            return
        try:
            playerFoot = CF.CreatePos(playerId).GetFootPos()
            blockComp = CF.CreateBlockInfo(playerId)
            supportPosition = (
                int(math.floor(destination[0])),
                int(math.floor(destination[1])) - 1,
                int(math.floor(destination[2])),
            )
            supportBlock = blockComp.GetBlock(supportPosition)
            ready = portal_logic.client_destination_anchor_ready(
                playerFoot,
                destination,
                supportBlock,
            )
        except Exception:
            ready = False
        if ready:
            self._portal_loading_ready_ticks += 1
        else:
            self._portal_loading_ready_ticks = 0
        if (
            self._portal_loading_ready_ticks
            < config.PORTAL_CLIENT_READY_STABLE_TICKS
        ):
            return
        try:
            self.NotifyToServer(
                "PortalArrivalClientReady",
                {"token": self._portal_loading_token},
            )
        except Exception as error:
            print "[TwilightBossSlice] portal client-ready ACK failed:", error
            return
        self._portal_loading_ack_sent = True

    def OnPortalArrivalPrepared(self, args):
        try:
            position = args.get("position")
            destination = tuple(float(value) for value in position)
            if len(destination) != 3:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._portal_loading_active:
            self._begin_portal_loading()
        self._portal_loading_destination = destination
        self._portal_engine_ready_token = str(args.get("token", ""))
        self._portal_engine_ready_ticks = 0
        self._portal_engine_ready_ack_sent = False
        self._portal_loading_required_chunks = set(
            portal_logic.client_required_chunk_positions(
                destination,
                portal_logic.PORTAL_CLIENT_READY_CHUNK_RADIUS,
            )
        )
        self._ensure_portal_loading_ui()
        portalLoadingUI.set_visible(True)

    def OnPortalArrivalRelocated(self, args):
        try:
            position = args.get("position")
            destination = tuple(float(value) for value in position)
            if len(destination) != 3:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._portal_loading_active:
            self._begin_portal_loading()
        self._portal_loading_destination = destination
        self._portal_loading_token = str(args.get("token", ""))
        self._portal_engine_ready_token = None
        self._portal_engine_ready_ticks = 0
        self._portal_engine_ready_ack_sent = False
        self._portal_loading_ready_ticks = 0
        self._portal_loading_required_chunks = set(
            portal_logic.client_required_chunk_positions(
                destination,
                portal_logic.PORTAL_CLIENT_READY_CHUNK_RADIUS,
            )
        )
        self._portal_loading_ack_sent = False
        self._portal_loading_deadline_tick = (
            self._portal_loading_tick
            + config.PORTAL_CLIENT_READY_TIMEOUT_TICKS
            + 60
        )
        self._ensure_portal_loading_ui()
        portalLoadingUI.set_visible(True)

    def OnPortalArrivalFinished(self, args):
        del args
        self._end_portal_loading()

    def OnDimensionChangeClientEvent(self, args):
        self._chain_visuals.clear()
        if not self._is_local_dimension_event(args):
            return
        self._portal_loading_ui_ready = False
        portalLoadingUI.invalidate()
        self._portal_loading_node = None
        self._ur_ghast_hitbox_key_down = False
        self._clear_ur_ghast_hitbox_shapes()
        self._clear_hydra_actor_visuals(True)
        self._clear_fortification_visuals()
        try:
            targetDimension = int(
                args.get("toDimensionId", args.get("toDimension", -1))
            )
        except (AttributeError, TypeError, ValueError):
            targetDimension = -1
        if targetDimension == config.DIMENSION_ID:
            self._begin_portal_loading()
        elif targetDimension >= 0:
            self._end_portal_loading()
        # The old LevelRenderer is already being detached here. Restore the
        # old dimension while it is still safe, then force a fresh component.
        self._twilight_dimension_switching = True
        self._twilight_sky_ui_ready = False
        self._reset_twilight_cloud_layer()
        self._reset_twilight_sky()
        self._twilight_sky_last_dimension = None
        self._log_twilight_sky(
            "dimension_change_start",
            args if isinstance(args, dict) else {},
        )

    def OnDimensionChangeFinishClientEvent(self, args):
        if not self._is_local_dimension_event(args):
            return
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
        except Exception:
            currentDimension = None
        if currentDimension == config.DIMENSION_ID:
            if not self._portal_loading_active:
                self._begin_portal_loading()
            self._ensure_portal_loading_ui()
            portalLoadingUI.set_visible(True)
        elif currentDimension is not None:
            self._end_portal_loading()
        self._portal_dimension_finish_seen = (
            currentDimension == config.DIMENSION_ID
        )
        # Keep the native renderer quarantined on affected engine builds.
        # A future opt-in may warm it up from the normal client tick, but the
        # completion event must never force it ready.
        self._discard_twilight_sky_renderer_candidate()
        self._twilight_sky_ui_ready = True
        self._twilight_sky_render_ready = False
        self._twilight_sky_render_warmup_tick = 0
        self._twilight_sky_last_dimension = None
        self._log_twilight_sky(
            "dimension_change_finish",
            args if isinstance(args, dict) else {},
        )
        self._twilight_dimension_switching = False
        self._update_twilight_sky()
        self._update_twilight_cloud_layer()

    def OnUiInitFinished(self, args):
        # UiInitFinished is emitted again after a dimension switch. Any
        # SkyRender component created before this point may be permanently
        # detached from LevelRenderer, even though the Python object exists.
        self._twilight_sky_ui_ready = True
        self._portal_loading_ui_ready = True
        self._portal_loading_registered = False
        self._portal_loading_ui_attempts = 0
        self._portal_loading_ui_retry_at = 0
        portalLoadingUI.invalidate()
        self._portal_loading_node = None
        self._ensure_portal_loading_ui()
        portalLoadingUI.set_visible(self._portal_loading_active)
        self._reset_twilight_cloud_layer()
        self._reset_twilight_sky()
        self._log_twilight_sky("ui_ready")
        # The engine can destroy CreateUI HUD nodes during world or dimension
        # UI reloads while this client system survives. Never trust the old
        # Python-side ready flag after UiInitFinished.
        self._magic_map_hud_ui_ready = magicMapHudUI.is_active()
        if not self._magic_map_hud_ui_ready:
            self._magic_map_hud_node = None
        self._ensure_magic_map_player_pose()
        self._ensure_magic_map_ui()
        lichBossHudUI.invalidate()
        self._lich_boss_hud_node = None
        nagaBossHudUI.invalidate()
        self._naga_boss_hud_node = None
        routeBossHudUI.invalidate()
        self._minoshroom_boss_hud_node = None
        self._hydra_boss_hud_node = None
        self._knight_phantoms_boss_hud_node = None
        self._ur_ghast_boss_hud_node = None

    def _ensure_lich_boss_hud(self):
        if lichBossHudUI.is_active():
            return True
        if not self._lich_boss_hud_registered:
            try:
                registered = clientApi.RegisterUI(
                    config.ModName,
                    config.LICH_BOSS_HUD_UI_NAME,
                    config.ModName + ".lichBossHudUI.LichBossHudUI",
                    "lich_boss_hud.main",
                )
                self._lich_boss_hud_registered = registered is not False
            except Exception as error:
                print "[TwilightBossSlice] Lich boss HUD register failed:", error
                return False
        try:
            self._lich_boss_hud_node = clientApi.GetUI(
                config.ModName, config.LICH_BOSS_HUD_UI_NAME
            )
            if self._lich_boss_hud_node is None:
                clientApi.CreateUI(
                    config.ModName,
                    config.LICH_BOSS_HUD_UI_NAME,
                    {"isHud": 1},
                )
                self._lich_boss_hud_node = clientApi.GetUI(
                    config.ModName, config.LICH_BOSS_HUD_UI_NAME
                )
            if self._lich_boss_hud_node is not None:
                self._lich_boss_hud_node.Init()
            return lichBossHudUI.is_active()
        except Exception as error:
            print "[TwilightBossSlice] Lich boss HUD create failed:", error
            self._lich_boss_hud_node = None
            return False

    def _ensure_naga_boss_hud(self):
        if nagaBossHudUI.is_active():
            return True
        if not self._naga_boss_hud_registered:
            try:
                registered = clientApi.RegisterUI(
                    config.ModName,
                    config.NAGA_BOSS_HUD_UI_NAME,
                    config.ModName + ".nagaBossHudUI.NagaBossHudUI",
                    "naga_boss_hud.main",
                )
                self._naga_boss_hud_registered = registered is not False
            except Exception as error:
                print "[TwilightBossSlice] Naga boss HUD register failed:", error
                return False
        try:
            self._naga_boss_hud_node = clientApi.GetUI(
                config.ModName, config.NAGA_BOSS_HUD_UI_NAME
            )
            if self._naga_boss_hud_node is None:
                clientApi.CreateUI(
                    config.ModName,
                    config.NAGA_BOSS_HUD_UI_NAME,
                    {"isHud": 1},
                )
                self._naga_boss_hud_node = clientApi.GetUI(
                    config.ModName, config.NAGA_BOSS_HUD_UI_NAME
                )
            if self._naga_boss_hud_node is not None:
                self._naga_boss_hud_node.Init()
            return nagaBossHudUI.is_active()
        except Exception as error:
            print "[TwilightBossSlice] Naga boss HUD create failed:", error
            self._naga_boss_hud_node = None
            return False

    def _ensure_route_boss_hud(self, kind):
        if kind == "hydra":
            if routeBossHudUI.hydra_active():
                return True
            uiName = config.HYDRA_BOSS_HUD_UI_NAME
            classPath = config.ModName + ".routeBossHudUI.HydraBossHudUI"
            screen = "hydra_boss_hud.main"
            registeredName = "_hydra_boss_hud_registered"
            nodeName = "_hydra_boss_hud_node"
        elif kind == "knight_phantoms":
            if routeBossHudUI.knight_phantoms_active():
                return True
            uiName = config.KNIGHT_PHANTOMS_BOSS_HUD_UI_NAME
            classPath = config.ModName + ".routeBossHudUI.KnightPhantomsBossHudUI"
            screen = "minoshroom_boss_hud.main"
            registeredName = "_knight_phantoms_boss_hud_registered"
            nodeName = "_knight_phantoms_boss_hud_node"
        elif kind == "ur_ghast":
            if routeBossHudUI.ur_ghast_active():
                return True
            uiName = config.UR_GHAST_BOSS_HUD_UI_NAME
            classPath = config.ModName + ".routeBossHudUI.UrGhastBossHudUI"
            screen = "minoshroom_boss_hud.main"
            registeredName = "_ur_ghast_boss_hud_registered"
            nodeName = "_ur_ghast_boss_hud_node"
        else:
            if routeBossHudUI.minoshroom_active():
                return True
            uiName = config.MINOSHROOM_BOSS_HUD_UI_NAME
            classPath = config.ModName + ".routeBossHudUI.MinoshroomBossHudUI"
            screen = "minoshroom_boss_hud.main"
            registeredName = "_minoshroom_boss_hud_registered"
            nodeName = "_minoshroom_boss_hud_node"
        if not getattr(self, registeredName):
            try:
                registered = clientApi.RegisterUI(
                    config.ModName, uiName, classPath, screen
                )
                setattr(self, registeredName, registered is not False)
            except Exception as error:
                print "[TwilightBossSlice] route boss HUD register failed:", kind, error
                return False
        try:
            node = clientApi.GetUI(config.ModName, uiName)
            if node is None:
                clientApi.CreateUI(config.ModName, uiName, {"isHud": 1})
                node = clientApi.GetUI(config.ModName, uiName)
            setattr(self, nodeName, node)
            if node is not None:
                node.Init()
            return (
                routeBossHudUI.hydra_active()
                if kind == "hydra"
                else routeBossHudUI.knight_phantoms_active()
                if kind == "knight_phantoms"
                else routeBossHudUI.ur_ghast_active()
                if kind == "ur_ghast"
                else routeBossHudUI.minoshroom_active()
            )
        except Exception as error:
            print "[TwilightBossSlice] route boss HUD create failed:", kind, error
            setattr(self, nodeName, None)
            return False

    def _register_magic_map_hud_proxy(self):
        if not config.MAGIC_MAP_HELD_HUD_ENABLED:
            return False
        if self._magic_map_native_proxy_registered:
            return True
        try:
            managerClass = clientApi.GetNativeScreenManagerCls()
            self._magic_map_native_screen_manager = (
                managerClass.instance()
            )
            result = (
                self._magic_map_native_screen_manager.RegisterScreenProxy(
                    "hud.hud_screen",
                    config.ModName
                    + ".magicMapHudUI.MagicMapHudProxy",
                )
            )
            self._magic_map_native_proxy_registered = result is not False
        except Exception as error:
            self._magic_map_native_screen_manager = None
            self._magic_map_native_proxy_registered = False
            self._log_magic_map_hud(
                "native_proxy_register_error",
                {"error": repr(error)},
            )
        return self._magic_map_native_proxy_registered

    def _unregister_magic_map_hud_proxy(self):
        if (
            not self._magic_map_native_proxy_registered
            or self._magic_map_native_screen_manager is None
        ):
            return
        try:
            self._magic_map_native_screen_manager.UnRegisterScreenProxy(
                "hud.hud_screen"
            )
        except Exception:
            pass
        self._magic_map_native_proxy_registered = False
        self._magic_map_native_screen_manager = None

    def OnUpdatePlayerSkinClientEvent(self, args):
        if not isinstance(args, dict):
            return
        playerId = args.get("playerId")
        localPlayerId = clientApi.GetLocalPlayerId()
        if (
            playerId is None
            or localPlayerId is None
            or str(playerId) != str(localPlayerId)
        ):
            return
        # UiInitFinished can run while the player's skin/material table is
        # still loading. RebuildPlayerRender then reports success to Python
        # while the engine logs "can't find material definition" and drops
        # the custom first-person arm controller. The skin event is emitted
        # only after that render definition has been synchronized. It is also
        # emitted after an in-game skin change, which replaces the player
        # renderer and therefore requires us to attach the map pose again.
        self._magic_map_skin_ready = True
        self._magic_map_pose_registered = False
        self._ensure_magic_map_player_pose()

    def _ensure_magic_map_player_pose(self):
        if self._magic_map_pose_registered:
            return True
        if not self._magic_map_skin_ready:
            return False
        try:
            playerId = clientApi.GetLocalPlayerId()
            if playerId is None:
                return False
            actorRender = CF.CreateActorRender(playerId)
            materialKeys = actorRender.GetActorRenderParams(
                playerId,
                "materials",
            )
            if not materialKeys or "default" not in materialKeys:
                self._log_magic_map_hud(
                    "pose_wait_material",
                    {"materials": materialKeys},
                )
                return False
            heldCondition = (
                "query.is_item_name_any('slot.weapon.mainhand', "
                "'tf_slice:filled_magic_map') || "
                "query.is_item_name_any('slot.weapon.offhand', "
                "'tf_slice:filled_magic_map') || "
                "query.is_item_name_any('slot.weapon.mainhand', "
                "'tf_slice:filled_maze_map') || "
                "query.is_item_name_any('slot.weapon.offhand', "
                "'tf_slice:filled_maze_map')"
            )
            controllerResult = (
                actorRender.AddPlayerAnimationController(
                    "tf_magic_map_pose",
                    "controller.animation.tf_magic_map_pose",
                )
            )
            scriptResult = actorRender.AddPlayerScriptAnimate(
                "tf_magic_map_pose",
                (
                    "variable.is_first_person && "
                    "!variable.is_paperdoll && "
                    "!variable.map_face_icon && ("
                    + heldCondition
                    + ")"
                ),
                True,
            )
            renderResult = actorRender.AddPlayerRenderController(
                "controller.render.tf_magic_map_arms",
                (
                    "variable.is_first_person && "
                    "!variable.is_paperdoll && "
                    "!variable.map_face_icon && ("
                    + heldCondition
                    + ")"
                ),
            )
            rebuildResult = actorRender.RebuildPlayerRender()
            self._magic_map_pose_registered = (
                controllerResult is not False
                and scriptResult is not False
                and renderResult is not False
                and rebuildResult is not False
            )
            self._log_magic_map_hud(
                "pose_register",
                {
                    "animation": controllerResult,
                    "render": renderResult,
                    "rebuild": rebuildResult,
                    "script": scriptResult,
                    "success": self._magic_map_pose_registered,
                },
            )
        except Exception as error:
            self._magic_map_pose_registered = False
            self._log_magic_map_hud(
                "pose_register_error",
                {"error": repr(error)},
            )
        return self._magic_map_pose_registered

    def _ensure_fire_react_ui(self):
        if self._fire_react_ui_ready:
            return True
        try:
            registered = clientApi.RegisterUI(
                config.ModName,
                config.FIRE_REACT_UI_NAME,
                "TwilightBossSlice.fireReactUI.FireReactUI",
                "fire_react.main",
            )
            self._fire_react_ui_ready = registered is not False
        except Exception as error:
            self._fire_react_ui_ready = False
            print (
                "[TwilightBossSlice] Fire React UI registration failed:",
                error,
            )
        return self._fire_react_ui_ready

    def OnFireReactOpen(self, args):
        try:
            if int(args.get("schemaVersion", 0)) != 1:
                return
            level = max(1, min(3, int(args.get("level", 1))))
        except (TypeError, ValueError):
            return
        choices = []
        for raw in list(args.get("choices", ()))[:4]:
            if not isinstance(raw, dict):
                continue
            try:
                slot = int(raw.get("slot"))
            except (TypeError, ValueError):
                continue
            if slot < 0 or slot > 3:
                continue
            choices.append(
                {
                    "slot": slot,
                    "itemName": str(raw.get("itemName", "")),
                }
            )
        if not choices or not self._ensure_fire_react_ui():
            return
        fireReactUI.set_snapshot({"level": level, "choices": choices})
        fireReactUI.set_submit_callback(self._submit_fire_react_selection)
        try:
            topScreen = clientApi.GetTopScreen()
            if (
                topScreen is not None
                and topScreen.GetScreenName() == "fire_react.main"
            ):
                clientApi.PopScreen()
            uiNode = clientApi.PushScreen(
                config.ModName,
                config.FIRE_REACT_UI_NAME,
            )
            if uiNode is None:
                print "[TwilightBossSlice] Fire React UI push returned None"
        except Exception as error:
            print "[TwilightBossSlice] Fire React UI open failed:", error

    def _submit_fire_react_selection(self, slot):
        try:
            self.NotifyToServer("FireReactApplyRequest", {"slot": int(slot)})
        except (TypeError, ValueError):
            return
        except Exception as error:
            print "[TwilightBossSlice] Fire React selection failed:", error

    def _ensure_magic_map_ui(self):
        held_hud_enabled = bool(config.MAGIC_MAP_HELD_HUD_ENABLED)
        hud_active = False
        if held_hud_enabled:
            self._register_magic_map_hud_proxy()
            hud_active = magicMapHudUI.is_active()
            if self._magic_map_hud_ui_ready and not hud_active:
                self._log_magic_map_hud("stale_node")
                self._magic_map_hud_ui_ready = False
                self._magic_map_hud_node = None
            if hud_active:
                self._magic_map_hud_ui_ready = True
        else:
            magicMapHudUI.set_held_visible(False)
            self._magic_map_hud_ui_ready = False
            self._magic_map_hud_node = None
        if not self._magic_map_ui_ready:
            try:
                clientApi.RegisterUI(
                    config.ModName,
                    config.MAGIC_MAP_UI_NAME,
                    config.ModName + ".magicMapUI.MagicMapUI",
                    "magic_map.main",
                )
                self._magic_map_ui_ready = True
            except Exception as error:
                print (
                    "[TwilightBossSlice] magic map UI registration failed:",
                    error,
                )
                self._magic_map_ui_ready = False
        if held_hud_enabled and not self._magic_map_hud_ui_ready:
            if not self._magic_map_hud_registered:
                try:
                    registered = clientApi.RegisterUI(
                        config.ModName,
                        config.MAGIC_MAP_HUD_UI_NAME,
                        config.ModName + ".magicMapHudUI.MagicMapHudUI",
                        "magic_map_hud.main",
                    )
                    self._magic_map_hud_registered = (
                        registered is not False
                    )
                except Exception as error:
                    print (
                        "[TwilightBossSlice] held magic map HUD "
                        "registration failed:",
                        error,
                    )
            try:
                if not self._magic_map_hud_registered:
                    return
                # CreateUI does not return the ScreenNode on this NetEase
                # client. Retrieve it with GetUI, as required by ModSDK.
                self._magic_map_hud_node = clientApi.GetUI(
                    config.ModName,
                    config.MAGIC_MAP_HUD_UI_NAME,
                )
                if self._magic_map_hud_node is None:
                    clientApi.CreateUI(
                        config.ModName,
                        config.MAGIC_MAP_HUD_UI_NAME,
                        {"isHud": 1},
                    )
                    self._magic_map_hud_node = clientApi.GetUI(
                        config.ModName,
                        config.MAGIC_MAP_HUD_UI_NAME,
                    )
                if self._magic_map_hud_node is not None:
                    self._magic_map_hud_node.Init()
                self._magic_map_hud_ui_ready = (
                    self._magic_map_hud_node is not None
                    and magicMapHudUI.is_active()
                )
                self._log_magic_map_hud(
                    "create",
                    {
                        "active": magicMapHudUI.is_active(),
                        "node": self._magic_map_hud_node is not None,
                        "ready": self._magic_map_hud_ui_ready,
                    },
                )
                if not self._magic_map_hud_ui_ready:
                    print (
                        "[TwilightBossSlice] held magic map HUD creation "
                        "returned None"
                    )
            except Exception as error:
                print (
                    "[TwilightBossSlice] held magic map HUD creation "
                    "failed:",
                    error,
                )
                self._magic_map_hud_ui_ready = False
        if (
            self._magic_map_ui_ready
            and self._pending_magic_map_snapshot is not None
        ):
            snapshot = self._pending_magic_map_snapshot
            self._pending_magic_map_snapshot = None
            self._open_magic_map(snapshot)

    def OnMagicMapSnapshot(self, args):
        try:
            schemaVersion = int(args.get("schemaVersion", 0))
            dimensionId = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if (
            schemaVersion != 3
            or dimensionId != config.DIMENSION_ID
        ):
            return
        snapshot = dict(args)
        snapshot["landmarks"] = list(
            args.get("landmarks", ())
        )[:128]
        self._magic_map_server_held = True
        self._ensure_magic_map_ui()
        if config.MAGIC_MAP_HELD_HUD_ENABLED:
            magicMapHudUI.set_snapshot(snapshot)
        if not bool(snapshot.get("openScreen", True)):
            magicMapUI.set_snapshot(snapshot)
            if not config.MAGIC_MAP_HELD_HUD_ENABLED:
                return
            items, observed = self._get_magic_map_client_items()
            held = clientItemLogic.resolve_held_map_state(
                self._magic_map_server_held,
                items,
                observed,
                self._magic_map_event_main_held,
            )
            self._set_magic_map_hud_visible(held)
            return
        if not self._magic_map_ui_ready:
            self._pending_magic_map_snapshot = snapshot
            return
        self._open_magic_map(snapshot)

    def OnMagicMapDelta(self, args):
        try:
            schemaVersion = int(args.get("schemaVersion", 0))
            dimensionId = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if (
            schemaVersion != 3
            or dimensionId != config.DIMENSION_ID
        ):
            return
        self._magic_map_server_held = True
        self._ensure_magic_map_ui()
        magicMapUI.apply_delta(dict(args))
        if not config.MAGIC_MAP_HELD_HUD_ENABLED:
            return
        magicMapHudUI.apply_delta(dict(args))
        items, observed = self._get_magic_map_client_items()
        held = clientItemLogic.resolve_held_map_state(
            self._magic_map_server_held,
            items,
            observed,
            self._magic_map_event_main_held,
        )
        self._set_magic_map_hud_visible(held)

    def OnMagicMapHeldState(self, args):
        held = bool(args.get("held", False))
        changed = held != self._magic_map_server_held
        self._magic_map_server_held = held
        if not config.MAGIC_MAP_HELD_HUD_ENABLED:
            self._set_magic_map_hud_visible(False)
            return
        if held:
            self._ensure_magic_map_ui()
        items, observed = self._get_magic_map_client_items()
        display_held = clientItemLogic.resolve_held_map_state(
            held,
            items,
            observed,
            self._magic_map_event_main_held,
        )
        self._set_magic_map_hud_visible(display_held)
        if changed:
            self._log_magic_map_hud(
                "server_held",
                {
                    "held": held,
                    "uiReady": self._magic_map_hud_ui_ready,
                },
            )

    def _open_magic_map(self, snapshot):
        magicMapUI.set_snapshot(snapshot)
        try:
            topScreen = clientApi.GetTopScreen()
            if (
                topScreen is not None
                and topScreen.GetScreenName()
                == "magic_map.main"
            ):
                return
        except Exception:
            pass
        try:
            uiNode = clientApi.PushScreen(
                config.ModName,
                config.MAGIC_MAP_UI_NAME,
            )
            if uiNode is None:
                print "[TwilightBossSlice] magic map UI push returned None"
        except Exception as error:
            print "[TwilightBossSlice] magic map UI open failed:", error

    def _client_item_name(self, item):
        return clientItemLogic.item_name(item)

    def OnCarriedNewItemChangedClientEvent(self, args):
        self._magic_map_event_main_held = (
            clientItemLogic.event_holds_filled_magic_map(args)
        )
        if not config.MAGIC_MAP_HELD_HUD_ENABLED:
            self._magic_map_hold_tick = 0
            return
        offhand_items, observed = self._get_magic_map_client_items(
            include_carried=False,
        )
        held = clientItemLogic.resolve_held_map_state(
            self._magic_map_server_held,
            offhand_items,
            observed,
            self._magic_map_event_main_held,
        )
        self._set_magic_map_hud_visible(held)
        # The carried-item event already updated the main-hand state. Restart
        # the slower fallback cadence used for offhand/missed-event recovery.
        self._magic_map_hold_tick = 0

    def _notify_knight_item_use(self, args):
        if not isinstance(args, dict):
            return False
        item = args.get("itemDict") or args.get("item") or {}
        itemName = portal_logic.item_name(item)
        if not itemName:
            try:
                playerId = clientApi.GetLocalPlayerId()
                item = CF.CreateItem(playerId).GetCarriedItem() or {}
                itemName = portal_logic.item_name(item)
            except Exception:
                return False
        if itemName not in (
            "tf_slice:block_and_chain",
            "tf_slice:knightmetal_shield",
        ):
            return False
        if itemName == "tf_slice:block_and_chain":
            if "cancel" in args:
                args["cancel"] = True
            if "ret" in args:
                args["ret"] = True
        try:
            self.NotifyToServer(
                "KnightItemUseRequest",
                {"itemName": itemName, "active": True},
            )
        except Exception:
            return False
        print "[TwilightBossSlice] knight item input:", itemName
        return True

    def OnKnightItemTryUseClientEvent(self, args):
        self._notify_knight_item_use(args)

    def OnKnightItemUseOnClientEvent(self, args):
        self._notify_knight_item_use(args)

    def OnKnightRightClickBeforeClientEvent(self, args):
        self._notify_knight_item_use(args)

    def OnKnightRightClickReleaseClientEvent(self, args):
        self.OnTapOrHoldReleaseClientEvent(args)

    def OnTapOrHoldReleaseClientEvent(self, _args):
        playerId = clientApi.GetLocalPlayerId()
        if playerId is None:
            return
        try:
            itemComp = CF.CreateItem(playerId)
            carried = itemComp.GetCarriedItem()
            offhand = itemComp.GetOffhandItem()
        except Exception:
            return
        if portal_logic.item_name(carried or {}) == "tf_slice:lifedrain_scepter":
            self.NotifyToServer("LifedrainReleaseRequest", {})
        if any(
            portal_logic.item_name(item or {}) == "tf_slice:knightmetal_shield"
            for item in (carried, offhand)
        ):
            self.NotifyToServer(
                "KnightItemUseRequest",
                {"itemName": "tf_slice:knightmetal_shield", "active": False},
            )

    def _query_magic_map_client_item(self, hand, getter):
        self._native_item_diag_sequence += 1
        sequence = self._native_item_diag_sequence
        trace = native_item_diagnostics.should_trace(sequence)
        started = time.time()
        if trace:
            print native_item_diagnostics.begin_line(
                "client", sequence, hand, self._magic_map_hold_tick
            )
        try:
            item = getter()
        except Exception as error:
            if trace:
                print native_item_diagnostics.end_line(
                    "client",
                    sequence,
                    hand,
                    self._magic_map_hold_tick,
                    (time.time() - started) * 1000.0,
                    error=error,
                )
            return (None, False)
        if trace:
            print native_item_diagnostics.end_line(
                "client",
                sequence,
                hand,
                self._magic_map_hold_tick,
                (time.time() - started) * 1000.0,
                item=item,
            )
        return (item, True)

    def _get_magic_map_client_items(self, include_carried=True):
        player_id = clientApi.GetLocalPlayerId()
        item_comp = CF.CreateItem(player_id)
        items = []
        observed = False
        if include_carried:
            item, succeeded = self._query_magic_map_client_item(
                "carried", item_comp.GetCarriedItem
            )
            items.append(item)
            observed = observed or succeeded
        item, succeeded = self._query_magic_map_client_item(
            "offhand", item_comp.GetOffhandItem
        )
        items.append(item)
        observed = observed or succeeded
        return items, observed

    def _set_magic_map_hud_visible(self, held):
        if not config.MAGIC_MAP_HELD_HUD_ENABLED:
            magicMapHudUI.set_held_visible(False)
            return False
        perspective = None
        try:
            player_id = clientApi.GetLocalPlayerId()
            perspective = CF.CreatePlayerView(player_id).GetPerspective()
        except Exception:
            pass
        display_held = clientItemLogic.should_show_held_map(
            held,
            perspective,
        )
        if display_held:
            try:
                top_screen = clientApi.GetTopScreen()
                display_held = not (
                    top_screen is not None
                    and top_screen.GetScreenName() == "magic_map.main"
                )
            except Exception:
                pass
        magicMapHudUI.set_held_visible(display_held)
        return display_held

    def _update_magic_map_hud(self):
        if not config.MAGIC_MAP_HELD_HUD_ENABLED:
            return False
        self._magic_map_hold_tick += 1
        if (
            self._magic_map_hold_tick
            % config.MAGIC_MAP_CLIENT_RECONCILE_INTERVAL_TICKS
        ):
            return
        held_item = None
        items = ()
        observed = False
        try:
            items, observed = self._get_magic_map_client_items()
            for item in items:
                if clientItemLogic.is_filled_magic_map(item):
                    held_item = item
                    break
        except Exception:
            pass
        held = clientItemLogic.resolve_held_map_state(
            self._magic_map_server_held,
            items,
            observed,
            self._magic_map_event_main_held,
        )
        signature = clientItemLogic.filled_magic_map_signature(held_item)
        signature_changed = bool(
            signature is not None
            and self._magic_map_held_signature is not None
            and signature != self._magic_map_held_signature
        )
        self._set_magic_map_hud_visible(held)
        if held and (not self._magic_map_was_held or signature_changed):
            try:
                self.NotifyToServer(
                    "MagicMapOpenRequest",
                    {"openScreen": False},
                )
            except Exception:
                pass
        self._magic_map_was_held = held
        if signature is not None:
            self._magic_map_held_signature = signature
        elif not held:
            self._magic_map_held_signature = None

    def _log_magic_map_hud(self, event, fields=None):
        if not config.MAGIC_MAP_DIAGNOSTICS_ENABLED:
            return
        if self._magic_map_diagnostic_count >= 24:
            return
        parts = ["[TF_MAGIC_MAP_DIAG]", "event=%s" % event]
        for key in sorted((fields or {}).keys()):
            parts.append("%s=%r" % (key, fields[key]))
        message = " ".join(parts)
        self._magic_map_diagnostic_count += 1
        try:
            mod_log.logger.info(message)
        except Exception:
            pass
        try:
            print message
        except Exception:
            pass
        try:
            clientApi.PostMcpModDump(message)
        except Exception:
            pass

    def _log_twilight_sky(self, event, fields=None):
        if (
            self._twilight_sky_diagnostic_count
            >= config.TWILIGHT_SKY_DIAGNOSTIC_LIMIT
        ):
            return
        parts = ["[TF_SKY_DIAG]", "event=%s" % event]
        for key in sorted((fields or {}).keys()):
            parts.append("%s=%r" % (key, fields[key]))
        message = " ".join(parts)
        self._twilight_sky_diagnostic_count += 1
        try:
            mod_log.logger.info(message)
        except Exception:
            pass
        try:
            print message
        except Exception:
            pass
        try:
            clientApi.PostMcpModDump(message)
        except Exception:
            pass

    def _reset_twilight_sky(self):
        if (
            self._twilight_sky_override_dirty
            and self._twilight_sky_render_ready
            and self._sky_render_comp is not None
        ):
            try:
                self._sky_render_comp.ResetSkyTextures()
            except Exception as error:
                self._log_twilight_sky(
                    "reset_textures_error",
                    {"error": repr(error)},
                )
            try:
                self._sky_render_comp.ResetStarBrightness()
            except Exception as error:
                self._log_twilight_sky(
                    "reset_brightness_error",
                    {"error": repr(error)},
                )
        self._twilight_sky_active = False
        self._twilight_sky_override_dirty = False
        self._twilight_sky_refresh_tick = 0
        self._twilight_sky_render_warmup_tick = 0
        self._twilight_sky_last_signature = None
        self._sky_render_comp = None
        self._twilight_sky_render_ready = False

    def _discard_twilight_sky_renderer_candidate(self):
        """Retry with a fresh component after an early renderer call."""
        self._sky_render_comp = None
        self._twilight_sky_render_ready = False
        self._twilight_sky_render_warmup_tick = 0
        self._twilight_sky_refresh_tick = 0

    def _ensure_twilight_sky_component(self):
        if not config.TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED:
            return False
        if self._sky_render_comp is not None:
            return True
        try:
            self._sky_render_comp = CF.CreateSkyRender(LEVEL_ID)
        except Exception as error:
            self._sky_render_comp = None
            signature = ("component_error", repr(error))
            if signature != self._twilight_sky_last_signature:
                self._twilight_sky_last_signature = signature
                self._log_twilight_sky(
                    "component_error",
                    {"error": repr(error)},
                )
            return False
        available = self._sky_render_comp is not None
        signature = ("component_ready", available)
        if signature != self._twilight_sky_last_signature:
            self._twilight_sky_last_signature = signature
            self._log_twilight_sky(
                "component_ready",
                {"available": available},
            )
        return available

    def _twilight_sky_application_succeeded(
        self,
        textureResult,
        brightnessResult,
        observedTextures,
        observedUseBrightness,
        observedBrightness,
        observedError,
    ):
        return (
            observedError is None
            and textureResult is not False
            and observedTextures == list(config.TWILIGHT_SKY_TEXTURES)
            and brightnessResult is not False
            and observedUseBrightness is True
            and observedBrightness == config.TWILIGHT_STAR_BRIGHTNESS
        )

    def _advance_twilight_sky_renderer_warmup(self):
        if not config.TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED:
            return False
        if self._twilight_sky_render_ready:
            return True
        if not self._twilight_sky_ui_ready:
            return False
        try:
            playerId = clientApi.GetLocalPlayerId()
            if playerId is None:
                return False
            footPos = CF.CreatePos(playerId).GetFootPos()
            if not footPos:
                return False
        except Exception as error:
            signature = ("player_not_ready", repr(error))
            if signature != self._twilight_sky_last_signature:
                self._twilight_sky_last_signature = signature
                self._log_twilight_sky(
                    "player_not_ready",
                    {"error": repr(error)},
                )
            return False
        warmupTicks = config.TWILIGHT_SKY_RENDER_WARMUP_TICKS
        self._twilight_sky_render_warmup_tick += 1
        if (
            self._twilight_sky_render_warmup_tick
            < warmupTicks
        ):
            return False
        self._twilight_sky_render_ready = True
        self._log_twilight_sky(
            "renderer_dimension_ready",
            {
                "playerId": playerId,
                "ticks": self._twilight_sky_render_warmup_tick,
                "uiReady": self._twilight_sky_ui_ready,
            },
        )
        return True

    def _update_twilight_sky(self):
        if not config.TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED:
            return
        if self._twilight_dimension_switching:
            return
        if not self._twilight_sky_ui_ready:
            return
        try:
            currentDimension = CF.CreateGame(
                LEVEL_ID
            ).GetCurrentDimension()
        except Exception as error:
            signature = ("dimension_error", repr(error))
            if signature != self._twilight_sky_last_signature:
                self._twilight_sky_last_signature = signature
                self._log_twilight_sky(
                    "dimension_error",
                    {"error": repr(error)},
                )
            return
        if currentDimension != self._twilight_sky_last_dimension:
            self._twilight_sky_last_dimension = currentDimension
            self._log_twilight_sky(
                "dimension",
                {
                    "current": currentDimension,
                    "target": config.DIMENSION_ID,
                },
            )
        if currentDimension != config.DIMENSION_ID:
            self._reset_twilight_sky()
            return
        if not self._advance_twilight_sky_renderer_warmup():
            return
        self._twilight_sky_refresh_tick += 1
        if (
            self._twilight_sky_refresh_tick != 1
            and self._twilight_sky_refresh_tick
            % config.TWILIGHT_SKY_REFRESH_TICKS
        ):
            return
        if not self._ensure_twilight_sky_component():
            return
        # Mark the renderer override dirty before the call. Some engine builds
        # apply the value while returning None, so success cannot be used to
        # decide whether the overworld needs restoring.
        self._twilight_sky_override_dirty = True
        try:
            textureResult = self._sky_render_comp.SetSkyTextures(
                list(config.TWILIGHT_SKY_TEXTURES)
            )
            brightnessResult = self._sky_render_comp.SetStarBrightness(
                config.TWILIGHT_STAR_BRIGHTNESS
            )
        except Exception as error:
            signature = ("apply_error", repr(error))
            if signature != self._twilight_sky_last_signature:
                self._twilight_sky_last_signature = signature
                self._log_twilight_sky(
                    "apply_error",
                    {"error": repr(error)},
                )
            self._twilight_sky_active = False
            self._discard_twilight_sky_renderer_candidate()
            return
        observedTextures = None
        observedUseBrightness = None
        observedBrightness = None
        observedError = None
        try:
            observedTextures = self._sky_render_comp.GetSkyTextures()
            observedUseBrightness = (
                self._sky_render_comp.GetUseStarBrightness()
            )
            observedBrightness = (
                self._sky_render_comp.GetStarBrightness()
            )
        except Exception as error:
            observedError = repr(error)
        signature = repr(
            (
                textureResult,
                brightnessResult,
                observedTextures,
                observedUseBrightness,
                observedBrightness,
                observedError,
            )
        )
        if signature != self._twilight_sky_last_signature:
            self._twilight_sky_last_signature = signature
            self._log_twilight_sky(
                "apply",
                {
                    "brightnessResult": brightnessResult,
                    "observedBrightness": observedBrightness,
                    "observedError": observedError,
                    "observedTextures": observedTextures,
                    "observedUseBrightness": observedUseBrightness,
                    "textureResult": textureResult,
                },
            )
        self._twilight_sky_active = (
            self._twilight_sky_application_succeeded(
                textureResult,
                brightnessResult,
                observedTextures,
                observedUseBrightness,
                observedBrightness,
                observedError,
            )
        )
        if not self._twilight_sky_active:
            # Native calls made before LevelRenderer exists can return without
            # a Python exception. Never retain that component for the retry.
            self._discard_twilight_sky_renderer_candidate()

    def _reset_twilight_cloud_layer(self):
        for particleId in self._twilight_cloud_particle_ids:
            try:
                self._twilight_cloud_particle_comp.Remove(particleId)
            except Exception:
                pass
        self._twilight_cloud_particle_ids = []
        self._twilight_cloud_tick = 0

    def _twilight_cloud_positions(self, footPos):
        tileSize = config.TWILIGHT_CLOUD_TILE_SIZE
        drift = (
            self._twilight_cloud_tick
            * config.TWILIGHT_CLOUD_DRIFT_PER_TICK
        ) % tileSize
        centerX = (
            math.floor(
                (float(footPos[0]) - drift) / tileSize + 0.5
            )
            * tileSize
            + drift
        )
        centerZ = (
            math.floor(float(footPos[2]) / tileSize + 0.5)
            * tileSize
        )
        positions = []
        radius = config.TWILIGHT_CLOUD_GRID_RADIUS
        for zIndex in range(-radius, radius + 1):
            for xIndex in range(-radius, radius + 1):
                positions.append(
                    (
                        centerX + xIndex * tileSize,
                        config.TWILIGHT_CLOUD_HEIGHT,
                        centerZ + zIndex * tileSize,
                    )
                )
        return positions

    def _create_twilight_cloud_layer(self, positions):
        createdIds = []
        for position in positions:
            try:
                particleId = self._twilight_cloud_particle_comp.Create(
                    config.TWILIGHT_CLOUD_PARTICLE,
                    position,
                    (0.0, 0.0, 0.0),
                )
                if particleId is None or particleId is False:
                    raise RuntimeError("cloud particle creation failed")
                createdIds.append(particleId)
                if self._twilight_cloud_particle_comp.SetPos(
                    particleId,
                    position,
                ) is False:
                    raise RuntimeError("cloud particle positioning failed")
            except Exception as error:
                for createdId in createdIds:
                    try:
                        self._twilight_cloud_particle_comp.Remove(createdId)
                    except Exception:
                        pass
                self._twilight_cloud_particle_ids = []
                self._log_twilight_sky(
                    "cloud_create_error",
                    {"error": repr(error)},
                )
                return False
        self._twilight_cloud_particle_ids = createdIds
        self._log_twilight_sky(
            "cloud_ready",
            {"tiles": len(createdIds)},
        )
        return True

    def _update_twilight_cloud_layer(self):
        if not config.TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED:
            return
        if self._twilight_dimension_switching:
            return
        if not self._twilight_sky_ui_ready:
            return
        if not self._twilight_sky_render_ready:
            return
        try:
            currentDimension = CF.CreateGame(
                LEVEL_ID
            ).GetCurrentDimension()
        except Exception:
            return
        if currentDimension != config.DIMENSION_ID:
            if self._twilight_cloud_particle_ids:
                self._reset_twilight_cloud_layer()
            return

        self._twilight_cloud_tick += 1
        if (
            self._twilight_cloud_particle_ids
            and self._twilight_cloud_tick
            % config.TWILIGHT_CLOUD_UPDATE_TICKS
        ):
            return
        try:
            playerId = clientApi.GetLocalPlayerId()
            if playerId is None:
                return
            footPos = CF.CreatePos(playerId).GetFootPos()
            if not footPos:
                return
            positions = self._twilight_cloud_positions(footPos)
            if not self._twilight_cloud_particle_ids:
                if not self._create_twilight_cloud_layer(positions):
                    return
            if len(self._twilight_cloud_particle_ids) != len(positions):
                self._reset_twilight_cloud_layer()
                return
            for particleId, position in zip(
                self._twilight_cloud_particle_ids,
                positions,
            ):
                if self._twilight_cloud_particle_comp.SetPos(
                    particleId,
                    position,
                ) is False:
                    self._reset_twilight_cloud_layer()
                    return
        except Exception as error:
            self._log_twilight_sky(
                "cloud_update_error",
                {"error": repr(error)},
            )
            self._reset_twilight_cloud_layer()

    def _update_ambient_fireflies(self):
        if not config.TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED:
            return
        if self._twilight_dimension_switching:
            return
        if not self._twilight_sky_ui_ready:
            return
        if not self._twilight_sky_render_ready:
            return
        self._ambient_tick += 1
        if self._ambient_tick % config.AMBIENT_FIREFLY_INTERVAL_TICKS:
            return
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            if currentDimension != config.DIMENSION_ID:
                return
            playerId = clientApi.GetLocalPlayerId()
            footPos = CF.CreatePos(playerId).GetFootPos()
            if not footPos:
                return
            if self._ambient_biome_comp is None:
                return
            biomeName = self._ambient_biome_comp.GetBiomeName(
                (
                    int(footPos[0]),
                    int(footPos[1]),
                    int(footPos[2]),
                ),
                config.DIMENSION_ID,
            )
            if str(biomeName or "") not in (
                "dm33027004_birch_forest_mutated",
                "minecraft:dm33027004_birch_forest_mutated",
            ):
                return
            radius = config.AMBIENT_FIREFLY_RADIUS
            position = (
                float(footPos[0]) + random.uniform(-radius, radius),
                float(footPos[1]) + random.uniform(0.6, 4.6),
                float(footPos[2]) + random.uniform(-radius, radius),
            )
            particleId = self._ambient_particle_comp.Create(
                config.AMBIENT_FIREFLY_PARTICLE,
                position,
                (0.0, 0.0, 0.0),
            )
            if particleId:
                self._ambient_particle_comp.SetPos(particleId, position)
        except Exception:
            return

    def OnBossHudReset(self, unusedArgs):
        self._last_sequence = -1
        self._clear_ur_ghast_hitbox_shapes()
        lichBossHudUI.invalidate()
        nagaBossHudUI.invalidate()
        routeBossHudUI.invalidate()
        self._lich_boss_hud_node = None
        self._naga_boss_hud_node = None
        self._minoshroom_boss_hud_node = None
        self._hydra_boss_hud_node = None
        self._knight_phantoms_boss_hud_node = None
        self._ur_ghast_boss_hud_node = None

    def OnBossSync(self, args):
        try:
            sequence = int(args.get("seq", 0))
        except (TypeError, ValueError):
            return
        if sequence <= self._last_sequence:
            return
        if self._last_sequence >= 0 and sequence > self._last_sequence + 1:
            self._sequence_gaps += sequence - self._last_sequence - 1
        self._last_sequence = sequence
        self._received_packets += 1
        next_bosses = {}
        for boss in args.get("bosses", []):
            boss_id = str(boss.get("id", ""))
            if boss_id:
                next_bosses[boss_id] = {
                    "kind": str(boss.get("kind", "naga")),
                    "name": boss.get(
                        "name",
                        u"\u5a1c\u8fe6"
                        if str(boss.get("kind", "naga")) == "naga"
                        else u"\u5deb\u5996",
                    ),
                    "health": float(boss.get("health", 0.0)),
                    "maxHealth": float(boss.get("maxHealth", 1.0)),
                    "state": int(boss.get("state", 0)),
                    "segments": int(boss.get("segments", 0)),
                    "dying": bool(boss.get("dying", False)),
                    "deathTime": int(boss.get("deathTime", 0)),
                    "phase": int(boss.get("phase", 1)),
                    "shieldStrength": int(
                        boss.get("shieldStrength", 0)
                    ),
                    "minionsRemaining": int(
                        boss.get("minionsRemaining", 0)
                    ),
                    "attackCooldown": int(
                        boss.get("attackCooldown", 0)
                    ),
                    "nextAttackType": int(
                        boss.get("nextAttackType", 0)
                    ),
                    "dimensionId": int(boss.get("dimensionId", 0)),
                    "position": boss.get("position"),
                    "hudVisible": boss.get("hudVisible"),
                    "hudDistanceSquared": boss.get(
                        "hudDistanceSquared"
                    ),
                    "heads": [dict(head) for head in boss.get("heads", ())],
                    "membersAlive": int(boss.get("membersAlive", 0)),
                    "phaseName": str(boss.get("phaseName", "normal")),
                }
        self._bosses = next_bosses
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
        except Exception:
            currentDimension = None
        try:
            localPlayerId = clientApi.GetLocalPlayerId()
            playerPosition = (
                CF.CreatePos(localPlayerId).GetFootPos()
                if localPlayerId is not None
                else None
            )
        except Exception:
            playerPosition = None
        visibleLiches = boss_hud_logic.visible_bosses(
            self._bosses.values(),
            "lich",
            currentDimension,
            playerPosition,
            config.BOSS_HUD_RANGE,
        )
        visibleNagas = boss_hud_logic.visible_bosses(
            self._bosses.values(),
            "naga",
            currentDimension,
            playerPosition,
            config.BOSS_HUD_RANGE,
        )
        visibleMinoshrooms = boss_hud_logic.visible_bosses(
            self._bosses.values(),
            "minoshroom",
            currentDimension,
            playerPosition,
            config.BOSS_HUD_RANGE,
        )
        visibleHydras = boss_hud_logic.visible_bosses(
            self._bosses.values(),
            "hydra",
            currentDimension,
            playerPosition,
            config.BOSS_HUD_RANGE,
        )
        visibleKnightPhantoms = boss_hud_logic.visible_bosses(
            self._bosses.values(),
            "knight_phantoms",
            currentDimension,
            playerPosition,
            config.BOSS_HUD_RANGE,
        )
        visibleUrGhasts = boss_hud_logic.visible_bosses(
            self._bosses.values(),
            "ur_ghast",
            currentDimension,
            playerPosition,
            config.BOSS_HUD_RANGE,
        )
        stackSlots = boss_hud_logic.boss_bar_stack_slots((
            ("lich", visibleLiches),
            ("naga", visibleNagas),
            ("minoshroom", visibleMinoshrooms),
            ("hydra", visibleHydras),
            ("knight_phantoms", visibleKnightPhantoms),
            ("ur_ghast", visibleUrGhasts),
        ))
        if visibleLiches:
            self._ensure_lich_boss_hud()
        lichBossHudUI.set_bosses(
            visibleLiches,
            stackSlots.get("lich", 0),
        )
        if visibleNagas:
            self._ensure_naga_boss_hud()
        nagaBossHudUI.set_bosses(
            visibleNagas,
            stackSlots.get("naga", 0),
        )
        if visibleMinoshrooms:
            self._ensure_route_boss_hud("minoshroom")
        routeBossHudUI.set_minoshrooms(
            visibleMinoshrooms,
            stackSlots.get("minoshroom", 0),
        )
        if visibleHydras:
            self._ensure_route_boss_hud("hydra")
        routeBossHudUI.set_hydras(
            visibleHydras,
            stackSlots.get("hydra", 0),
        )
        if visibleKnightPhantoms:
            self._ensure_route_boss_hud("knight_phantoms")
        routeBossHudUI.set_knight_phantoms(
            visibleKnightPhantoms,
            stackSlots.get("knight_phantoms", 0),
        )
        if visibleUrGhasts:
            self._ensure_route_boss_hud("ur_ghast")
        routeBossHudUI.set_ur_ghasts(
            visibleUrGhasts,
            stackSlots.get("ur_ghast", 0),
        )
        # One ACK per 2.5 seconds at the default 10-tick sync interval.
        if self._received_packets % 5 == 0:
            self.NotifyToServer("BossSyncAck", {
                "seq": sequence,
                "serverTick": int(args.get("serverTick", 0)),
                "sequenceGaps": self._sequence_gaps
            })
            print (
                "[TwilightBossSlice] sync seq=%d bosses=%d gaps=%d"
                % (sequence, len(self._bosses), self._sequence_gaps)
            )

    @staticmethod
    def _restore_hydra_actor_visual(record):
        entityId = record.get("entityId")
        if entityId is None:
            return
        try:
            CF.CreateModel(entityId).SetModelOffset((0.0, 0.0, 0.0))
        except Exception:
            pass
        try:
            CF.CreateRot(entityId).SetRot(record.get("targetRotation"))
        except Exception:
            pass

    def _clear_hydra_actor_visuals(self, force=False):
        staleAfter = 6
        for key, record in list(self._hydra_actor_visuals.items()):
            if (
                not force
                and self._route_effect_tick
                - int(record.get("lastSeen", -1000))
                <= staleAfter
            ):
                continue
            self._restore_hydra_actor_visual(record)
            self._hydra_actor_visuals.pop(key, None)

    def _sample_hydra_actor_visual(self, record):
        return hydra_logic.interpolated_actor_transform(
            record.get("previousPosition"),
            record.get("targetPosition"),
            record.get("previousRotation"),
            record.get("targetRotation"),
            self._route_effect_tick - int(record.get("startTick", 0)),
        )

    def OnHydraActorFrame(self, args):
        try:
            dimensionId = int(args.get("dimensionId", -1))
            if dimensionId != int(
                CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            ):
                return
            parts = list(args.get("parts") or ())
        except (AttributeError, TypeError, ValueError):
            return
        for rawPart in parts:
            try:
                entityId = rawPart.get("entityId")
                targetPosition = tuple(
                    float(value)
                    for value in rawPart.get("position", ())[:3]
                )
                targetRotation = tuple(
                    float(value)
                    for value in rawPart.get("rotation", ())[:2]
                )
                if entityId is None or len(targetPosition) != 3 or len(
                    targetRotation
                ) != 2:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            key = str(entityId)
            record = self._hydra_actor_visuals.get(key)
            if record is not None:
                sample = self._sample_hydra_actor_visual(record)
                previousPosition = sample["position"]
                previousRotation = sample["rotation"]
            else:
                try:
                    previousPosition = CF.CreatePos(entityId).GetPos()
                except Exception:
                    previousPosition = None
                try:
                    previousRotation = CF.CreateRot(entityId).GetRot()
                except Exception:
                    previousRotation = None
                if previousPosition is None:
                    previousPosition = targetPosition
                if previousRotation is None:
                    previousRotation = targetRotation
            self._hydra_actor_visuals[key] = {
                "entityId": entityId,
                "previousPosition": tuple(previousPosition),
                "targetPosition": targetPosition,
                "previousRotation": tuple(previousRotation),
                "targetRotation": targetRotation,
                "startTick": self._route_effect_tick,
                "lastSeen": self._route_effect_tick,
            }

    def _update_hydra_actor_visuals(self):
        self._clear_hydra_actor_visuals(False)
        for record in list(self._hydra_actor_visuals.values()):
            entityId = record.get("entityId")
            try:
                actorPosition = CF.CreatePos(entityId).GetPos()
            except Exception:
                actorPosition = None
            if actorPosition is None:
                continue
            sample = self._sample_hydra_actor_visual(record)
            worldOffset = tuple(
                float(sample["position"][axis])
                - float(actorPosition[axis])
                for axis in range(3)
            )
            localOffset = hydra_logic.world_offset_to_local(
                worldOffset, sample["rotation"][1]
            )
            try:
                CF.CreateModel(entityId).SetModelOffset(localOffset)
                CF.CreateRot(entityId).SetRot(sample["rotation"])
            except Exception:
                continue

    def OnHydraHeadSync(self, args):
        boss = self._bosses.get(str(args.get("id", "")))
        if boss is None or boss.get("kind") != "hydra":
            return
        try:
            index = int(args.get("index"))
        except (TypeError, ValueError):
            return
        if not (0 <= index < 7):
            return
        heads = list(boss.get("heads", ()))
        while len(heads) < 7:
            heads.append({"state": "dead", "ticks": 0, "yaw": 0.0, "pitch": 0.0, "alive": False})
        heads[index] = dict(args.get("head") or {})
        boss["heads"] = heads
        if boss.get("hudVisible") is not None:
            routeBossHudUI.set_hydras(
                [boss] if boss.get("hudVisible") else []
            )

    def OnHydraRouteEffect(self, args):
        position = args.get("position")
        if position is None:
            return
        try:
            if int(args.get("dimensionId", -1)) != int(
                CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            ):
                return
        except (TypeError, ValueError):
            return
        except Exception:
            return
        kind = str(args.get("kind", ""))
        if kind == "hydra_hurt":
            self._spawn_naga_state_particle(
                "minecraft:critical_hit_emitter",
                (
                    float(position[0]),
                    float(position[1]) + 0.75,
                    float(position[2]),
                ),
            )
            return
        if kind in (
            "hydra_flame_charge",
            "hydra_flame",
            "hydra_mortar_charge",
            "hydra_bite_charge",
        ):
            rawDirection = args.get("direction") or (0.0, 0.0, 1.0)
            length = max(
                0.0001,
                sum(float(value) * float(value) for value in rawDirection) ** 0.5,
            )
            direction = tuple(float(value) / length for value in rawDirection)
            mouth = (
                float(position[0]) + direction[0] * 3.5,
                float(position[1]) + 1.0 + direction[1] * 3.5,
                float(position[2]) + direction[2] * 3.5,
            )
            if kind == "hydra_flame_charge":
                self._spawn_naga_state_particle(
                    "minecraft:basic_smoke_particle",
                    (
                        mouth[0] + random.uniform(-0.35, 0.35),
                        mouth[1] + random.uniform(-0.35, 0.35),
                        mouth[2] + random.uniform(-0.35, 0.35),
                    ),
                )
                return
            if kind == "hydra_mortar_charge":
                self._spawn_naga_state_particle(
                    "minecraft:basic_smoke_particle",
                    (
                        mouth[0] + random.uniform(-0.4, 0.4),
                        mouth[1] + random.uniform(-0.4, 0.4),
                        mouth[2] + random.uniform(-0.4, 0.4),
                    ),
                )
                return
            if kind == "hydra_bite_charge":
                self._spawn_naga_state_particle(
                    "minecraft:water_splash_particle_manual",
                    (
                        mouth[0] + random.uniform(-0.35, 0.35),
                        mouth[1] + random.uniform(-0.35, 0.35),
                        mouth[2] + random.uniform(-0.35, 0.35),
                    ),
                )
                return
            # NetEase retains local-space emitters on the actor transform,
            # which made the original moving flames pile up at the mouth.
            # Render the source's moving flame population as detached,
            # world-space samples spanning its visible lifetime.
            sampleAges = hydra_logic.flame_visual_sample_ages(
                5, phase=random.random()
            )
            for sampleAge in sampleAges:
                samplePosition = hydra_logic.flame_particle_position(
                    mouth=mouth,
                    direction=direction,
                    gaussian_noise=(
                        random.gauss(0.0, 1.0),
                        random.gauss(0.0, 1.0),
                        random.gauss(0.0, 1.0),
                    ),
                    spread=random.uniform(5.0, 7.5),
                    speed=random.uniform(1.0, 2.0),
                    age=sampleAge,
                )
                self._spawn_naga_state_particle(
                    "tf_slice:hydra_flame",
                    samplePosition,
                )
            return
        if kind == "hydra_death_body":
            for unusedIndex in range(3):
                self._spawn_naga_state_particle(
                    (
                        "minecraft:large_explosion"
                        if random.randrange(2) == 0
                        else "minecraft:basic_smoke_particle"
                    ),
                    (
                        float(position[0]) + random.uniform(-6.0, 6.0),
                        float(position[1]) + random.uniform(0.0, 6.0),
                        float(position[2]) + random.uniform(-6.0, 6.0),
                    ),
                )
            return
        if kind == "hydra_part_death":
            rawSize = args.get("size") or (2.0, 2.0)
            try:
                width = max(0.25, float(rawSize[0]))
                height = max(0.25, float(rawSize[1]))
            except (TypeError, ValueError, IndexError):
                width, height = 2.0, 2.0
            for index in range(10):
                particle = (
                    "minecraft:large_explosion"
                    if index < 2
                    else "minecraft:basic_smoke_particle"
                )
                self._spawn_naga_state_particle(
                    particle,
                    (
                        float(position[0]) + random.uniform(-width * 0.5, width * 0.5),
                        float(position[1]) + random.uniform(0.0, height),
                        float(position[2]) + random.uniform(-width * 0.5, width * 0.5),
                    ),
                )
            return
        particle = (
            "minecraft:critical_hit_emitter"
            if kind == "minoshroom_slam"
            else "minecraft:basic_flame_particle"
        )
        count = 24 if kind == "minoshroom_slam" else 8
        for _index in range(count):
            self._spawn_naga_state_particle(
                particle,
                (
                    float(position[0]) + random.uniform(-7.0, 7.0),
                    float(position[1]) + random.uniform(0.0, 1.5),
                    float(position[2]) + random.uniform(-7.0, 7.0),
                ),
            )

    def OnPerfSync(self, args):
        self._perf = dict(args)
        print (
            "[TwilightBossSlice] perf avgMs=%s p95Ms=%s p99Ms=%s "
            "maxMs=%s bosses=%s urGhasts=%s bossMiniGhasts=%s"
            % (
                args.get("avgMs", 0.0),
                args.get("p95Ms", 0.0),
                args.get("p99Ms", 0.0),
                args.get("maxMs", 0.0),
                args.get("activeBosses", 0),
                args.get("urGhastCount", 0),
                args.get("bossMiniGhastCount", 0),
            )
        )

    def OnLichCombatEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if currentDimension != eventDimension:
            return
        kind = str(args.get("kind", ""))
        positions = []
        for rawPos in args.get("positions", ()):
            try:
                positions.append(
                    tuple(float(rawPos[index]) for index in range(3))
                )
            except (TypeError, ValueError, IndexError):
                continue
        if kind == "fortification_visual_sync":
            ownerId = str(args.get("entityId", ""))
            try:
                shieldCount = max(0, min(5, int(args.get("style", 0))))
            except (TypeError, ValueError):
                shieldCount = 0
            if not ownerId or shieldCount <= 0:
                self._destroy_fortification_client_visual(ownerId)
                return
            visual = self._fortification_visuals.get(ownerId) or {
                "entityId": None,
            }
            # A fresh authoritative positive state supersedes a failed hide
            # from the previous cast; otherwise retries would hide the recast.
            visual.pop("removing", None)
            visual.update(
                {
                    "count": shieldCount,
                    "dimensionId": eventDimension,
                }
            )
            self._fortification_visuals[ownerId] = visual
            return
        if kind == "fortification_visual_remove":
            ownerId = str(args.get("entityId", ""))
            self._destroy_fortification_client_visual(ownerId)
            return
        if kind == "projectile_launch":
            entityId = str(args.get("entityId", ""))
            style = str(args.get("style", ""))
            if entityId:
                self._lich_projectile_trails[entityId] = {
                    "expires": self._lich_effect_tick + 1800,
                    "missing": 0,
                    "style": str(args.get("style", "")),
                }
            if style == "tf_slice:twilight_wand_bolt":
                for position in positions:
                    self._spawn_naga_state_particle(
                        "tf_slice:twilight_scepter_trail", position
                    )
                return
        if kind == "lifedrain_link" and len(positions) >= 2:
            source, destination = positions[0], positions[1]
            for index in range(12):
                fraction = index / 11.0
                self._spawn_naga_state_particle(
                    "tf_slice:lifedrain_beam",
                    tuple(
                        source[axis]
                        + (destination[axis] - source[axis]) * fraction
                        for axis in range(3)
                    ),
                )
            return
        if kind == "fortification_expire":
            for origin in positions:
                for index in range(4):
                    angle = index * math.pi * 0.5
                    self._spawn_naga_state_particle(
                        "tf_slice:fortification_shield",
                        (origin[0] + math.cos(angle) * 0.6,
                         origin[1] + 1.0,
                         origin[2] + math.sin(angle) * 0.6),
                    )
            return
        if kind in ("fortification_activate", "fortification_block"):
            count = 24 if kind == "fortification_activate" else 10
            radius = 1.15 if kind == "fortification_activate" else 0.7
            for origin in positions:
                for index in range(count):
                    angle = index * math.pi * 2.0 / count
                    self._spawn_naga_state_particle(
                        "tf_slice:fortification_shield",
                        (
                            origin[0] + math.cos(angle) * radius,
                            origin[1]
                            + 0.45
                            + (index % 3) * 0.45,
                            origin[2] + math.sin(angle) * radius,
                        ),
                    )
            return
        if kind == "teleport" and len(positions) >= 2:
            source, destination = positions[0], positions[1]
            for index in range(128):
                fraction = index / 127.0
                position = (
                    source[0] + (destination[0] - source[0]) * fraction
                    + random.uniform(-0.12, 0.12),
                    source[1] + 1.0
                    + (destination[1] - source[1]) * fraction
                    + random.uniform(-0.35, 0.35),
                    source[2] + (destination[2] - source[2]) * fraction
                    + random.uniform(-0.12, 0.12),
                )
                self._spawn_naga_state_particle(
                    "tf_slice:lich_ominous_flame", position
                )
            return
        if kind in (
            "clone_spawn", "minion_summon", "pop_mob", "absorb_minion"
        ) and len(positions) >= 2:
            trails = []
            if kind == "pop_mob":
                trails = [(source, positions[-1]) for source in positions[:-1]]
            else:
                trails = [(positions[0], positions[1])]
            for source, destination in trails:
                for index in range(64):
                    fraction = index / 63.0
                    self._spawn_naga_state_particle(
                        "tf_slice:lich_ominous_flame",
                        (
                            source[0]
                            + (destination[0] - source[0]) * fraction
                            + random.uniform(-0.10, 0.10),
                            source[1]
                            + 0.8
                            + (destination[1] - source[1]) * fraction
                            + random.uniform(-0.25, 0.25),
                            source[2]
                            + (destination[2] - source[2]) * fraction
                            + random.uniform(-0.10, 0.10),
                        ),
                    )
            return
        count = {
            "scepter_charge": 12,
            "pop_mob": 16,
            "absorb_minion": 16,
            "shield_break": 12,
            "clone_hurt": 12,
            "death_start": 16,
            "death_smoke": 3,
            "death_bone_burst": 12,
            "death_first_burst": 32,
            "death_mid_burst": 3,
            "death_flame": 5,
            "death_burst": 48,
            "extinguish_candles": 20,
        }.get(kind, 1)
        particleName = "tf_slice:lich_ominous_flame"
        if kind == "death_smoke":
            particleName = "minecraft:basic_smoke_particle"
        elif kind in (
            "shield_break", "death_burst", "death_mid_burst"
        ):
            particleName = "minecraft:large_explosion"
        for origin in positions:
            for _index in range(count):
                position = (
                    origin[0] + random.uniform(-0.9, 0.9),
                    origin[1] + random.uniform(0.35, 2.2),
                    origin[2] + random.uniform(-0.9, 0.9),
                )
                self._spawn_naga_state_particle(
                    particleName, position
                )

    def OnTorchberryGlow(self, args):
        try:
            if CF.CreateGame(LEVEL_ID).GetCurrentDimension() != args.get("dimensionId"):
                return
            x, y, z = args["position"]
            comp = CF.CreateParticleSystem(None)
            comp.Create("minecraft:totem_particle", (x, y + 1.0, z), (0.0, 0.0, 0.0))
        except Exception:
            return

    def OnNagaSegmentBurst(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if currentDimension != eventDimension:
            return
        particleComp = CF.CreateParticleSystem(None)
        positions = args.get("positions", [])
        for rawPos in positions:
            try:
                position = (
                    float(rawPos[0]),
                    float(rawPos[1]) + 0.8,
                    float(rawPos[2]),
                )
            except (TypeError, ValueError, IndexError):
                continue
            particleId = particleComp.Create(
                "minecraft:large_explosion",
                position,
                (0.0, 0.0, 0.0),
            )
            if particleId:
                particleComp.SetPos(particleId, position)
            try:
                CF.CreateCustomAudio(LEVEL_ID).PlayCustomMusic(
                    "random.explode",
                    position,
                    0.65,
                    1.15,
                    False,
                    ""
                )
            except Exception:
                pass

    def OnKnightPhantomEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if currentDimension != eventDimension:
            return
        positions = []
        for rawPosition in args.get("positions", ()):
            try:
                positions.append(tuple(
                    float(rawPosition[index]) for index in range(3)
                ))
            except (TypeError, ValueError, IndexError):
                continue
        if not positions:
            return
        kind = str(args.get("kind", ""))
        origin = positions[0]
        particleName = {
            "charge_smoke": "minecraft:basic_smoke_particle",
            "throw_axe": "minecraft:critical_hit_emitter",
            "throw_pick": "minecraft:critical_hit_emitter",
            "shield_block": "minecraft:critical_hit_emitter",
            "death_start": "tf_slice:knight_phantom_smoke",
            "death_poof": "tf_slice:knight_phantom_smoke",
            "death_hold": "tf_slice:knight_phantom_smoke",
        }.get(kind)
        count = {
            "charge_smoke": 1,
            "throw_axe": 0,
            "throw_pick": 0,
            "shield_block": 4,
            "death_start": 10,
            "death_poof": 20,
            "death_hold": 1,
        }.get(kind, 0)
        if kind == "death_trail" and len(positions) >= 2:
            fraction = max(0.0, min(1.0, float(args.get("fraction", 0.0))))
            destination = positions[1]
            center = tuple(
                origin[axis]
                + (destination[axis] - origin[axis]) * fraction
                for axis in range(3)
            )
            for index in range(3):
                self._spawn_naga_state_particle(
                    "tf_slice:knight_phantom_smoke",
                    (
                        center[0] + random.uniform(-0.12, 0.12) * index,
                        center[1] + 1.0 + random.uniform(-0.12, 0.12) * index,
                        center[2] + random.uniform(-0.12, 0.12) * index,
                    ),
                )
            return
        if particleName is None:
            return
        for _index in range(count):
            self._spawn_naga_state_particle(
                particleName,
                (
                    origin[0] + random.uniform(-0.75, 0.75),
                    origin[1] + random.uniform(0.4, 2.2),
                    origin[2] + random.uniform(-0.75, 0.75),
                ),
            )
        soundName = {
            "throw_axe": "random.bow",
            "throw_pick": "random.bow",
            "shield_block": "item.shield.block",
            "death_start": "mob.skeleton.death",
        }.get(kind)
        if soundName is None:
            return
        try:
            CF.CreateCustomAudio(LEVEL_ID).PlayCustomMusic(
                soundName,
                origin,
                1.0,
                0.45 if kind.startswith("throw_") else 1.0,
                False,
                "",
            )
        except Exception:
            pass

    def _tick_ur_ghast_storm_presentation(self):
        self._ur_ghast_effect_tick += 1
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
        except Exception:
            currentDimension = -1
        for stormKey, storm in list(self._ur_ghast_storms.items()):
            if not ur_ghast_effect_logic.storm_keepalive_active(
                self._ur_ghast_effect_tick, storm.get("expires", -1)
            ):
                self._ur_ghast_storms.pop(stormKey, None)
        step = ur_ghast_effect_logic.storm_presentation_step(
            self._ur_ghast_storms,
            self._ur_ghast_effect_tick,
            currentDimension,
            self._ur_ghast_storm_intensity,
        )
        self._ur_ghast_storm_intensity = float(step["intensity"])
        particleBudget = int(step.get("particleBudget", 0))
        if particleBudget <= 0 or currentDimension != config.DIMENSION_ID:
            return
        try:
            playerId = clientApi.GetLocalPlayerId()
            playerPosition = CF.CreatePos(playerId).GetFootPos()
        except Exception:
            playerPosition = None
        if playerPosition is None:
            return
        particleCount = max(1, min(4, particleBudget // 20 or 1))
        for unusedIndex in range(particleCount):
            self._spawn_naga_state_particle(
                "minecraft:water_splash_particle_manual",
                (
                    float(playerPosition[0]) + random.uniform(-10.0, 10.0),
                    float(playerPosition[1]) + random.uniform(7.0, 14.0),
                    float(playerPosition[2]) + random.uniform(-10.0, 10.0),
                ),
                manual=True,
            )

    def OnUrGhastEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if currentDimension != eventDimension:
            return
        positions = []
        for rawPosition in args.get("positions", ()):
            try:
                positions.append(tuple(
                    float(rawPosition[index]) for index in range(3)
                ))
            except (TypeError, ValueError, IndexError):
                continue
        if not positions:
            return
        kind = str(args.get("kind", ""))
        stormKey = str(
            args.get("bossId", "%.2f:%.2f:%.2f" % positions[0])
        )
        if kind in ("tantrum_start", "storm_keepalive"):
            self._ur_ghast_storms[stormKey] = {
                "expires": (
                    self._ur_ghast_effect_tick
                    + ur_ghast_effect_logic.STORM_KEEPALIVE_TICKS
                ),
                "dimensionId": eventDimension,
                "position": positions[0],
            }
            if kind == "storm_keepalive":
                return
        elif kind == "storm_stop":
            self._ur_ghast_storms.pop(stormKey, None)
            return
        if kind == "tear":
            origin = positions[0]
            samples = tuple(
                (random.random(), random.random(), random.random())
                for unusedIndex in range(
                    ur_ghast_effect_logic.TEAR_PARTICLES_PER_PULSE
                )
            )
            for tearPosition in ur_ghast_effect_logic.tear_column_positions(
                origin, samples
            ):
                self._spawn_naga_state_particle(
                    "tf_slice:ur_ghast_tear",
                    tearPosition,
                )
            return
        if kind == "fireball_launch":
            for origin in positions:
                for unusedIndex in range(8):
                    self._spawn_naga_state_particle(
                        "minecraft:basic_flame_particle",
                        (
                            origin[0] + random.uniform(-0.35, 0.35),
                            origin[1] + random.uniform(-0.35, 0.35),
                            origin[2] + random.uniform(-0.35, 0.35),
                        ),
                    )
            return
        if kind == "fireball_impact":
            for origin in positions:
                self._spawn_naga_state_particle(
                    "minecraft:large_explosion", origin
                )
            return
        if kind == "death_burst":
            origin = positions[0]
            particleNames = (
                "minecraft:large_explosion",
                "minecraft:basic_smoke_particle",
                "minecraft:redstone_wire_dust_particle",
            )
            for index in range(12):
                self._spawn_naga_state_particle(
                    particleNames[index % len(particleNames)],
                    (
                        origin[0] + random.uniform(-7.0, 7.0),
                        origin[1] + random.uniform(0.0, 18.0),
                        origin[2] + random.uniform(-7.0, 7.0),
                    ),
                )
            return
        if kind == "death_trail":
            origin = positions[0]
            for unusedIndex in range(40):
                self._spawn_naga_state_particle(
                    "minecraft:redstone_wire_dust_particle",
                    (
                        origin[0] + random.uniform(-1.0, 1.0),
                        origin[1] + random.uniform(-1.0, 1.0),
                        origin[2] + random.uniform(-1.0, 1.0),
                    ),
                )
            return
        if kind == "death_poof":
            origin = positions[0]
            for unusedIndex in range(8):
                self._spawn_naga_state_particle(
                    "minecraft:large_explosion",
                    (
                        origin[0] + random.uniform(-4.0, 4.0),
                        origin[1] + random.uniform(2.0, 12.0),
                        origin[2] + random.uniform(-4.0, 4.0),
                    ),
                )
            return
        if kind in ("tantrum_start", "minion_spawn"):
            for origin in positions:
                self._spawn_naga_state_particle(
                    "tf_slice:ur_ghast_lightning",
                    (origin[0], origin[1] + 4.0, origin[2]),
                )
            return
        if kind == "absorb_minion":
            destination = positions[-1]
            for source in positions[:-1]:
                for index in range(12):
                    factor = index / 11.0
                    self._spawn_naga_state_particle(
                        "tf_slice:ghast_trap_mote",
                        tuple(
                            source[axis]
                            + (destination[axis] - source[axis]) * factor
                            for axis in range(3)
                        ),
                    )

    def OnDarkTowerMechanismEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
            rawPosition = args.get("position", ())
            position = (
                float(rawPosition[0]) + 0.5,
                float(rawPosition[1]) + 0.7,
                float(rawPosition[2]) + 0.5,
            )
        except (TypeError, ValueError, IndexError):
            return
        if currentDimension != eventDimension:
            return
        kind = str(args.get("kind", ""))
        rawCount = max(1, int(args.get("count", 1)))
        count = min(16, rawCount)
        particleName = {
            "builder_start": "minecraft:critical_hit_emitter",
            "builder_path": "minecraft:critical_hit_emitter",
            "builder_stop": "minecraft:basic_smoke_particle",
            "builder_remove": "minecraft:basic_smoke_particle",
            "antibuilder_restore": "minecraft:basic_smoke_particle",
            "reactor_start": "minecraft:lava_particle",
            "reactor_transform": "minecraft:basic_smoke_particle",
            "reactor_burst": "minecraft:large_explosion",
        }.get(kind)
        if particleName is None and kind != "reactor_ambient":
            return
        if particleName is not None:
            for index in range(count):
                self._spawn_naga_state_particle(
                    particleName,
                    (
                        position[0] + random.uniform(-0.45, 0.45),
                        position[1] + (index % 5) * 0.25,
                        position[2] + random.uniform(-0.45, 0.45),
                    ),
                )
        soundName = {
            "builder_start": "beacon.activate",
            "builder_path": "random.orb",
            "builder_stop": "random.fizz",
            "builder_remove": "random.break",
            "antibuilder_restore": "random.break",
            "reactor_start": "beacon.activate",
            "reactor_transform": "random.break",
            "reactor_ambient": "portal.trigger",
            "reactor_burst": "random.explode",
        }[kind]
        volume = 0.8
        pitch = 1.0
        if kind == "reactor_ambient":
            volume = min(2.5, rawCount / 100.0)
            pitch = min(2.5, rawCount / 100.0)
        try:
            CF.CreateCustomAudio(LEVEL_ID).PlayCustomMusic(
                soundName, position, volume, pitch, False, ""
            )
        except Exception:
            pass

    def OnGhastTrapEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
            rawTrap = args.get("position", ())
            trapPosition = (
                float(rawTrap[0]) + 0.5,
                float(rawTrap[1]) + 1.0,
                float(rawTrap[2]) + 0.5,
            )
        except (TypeError, ValueError, IndexError):
            return
        if currentDimension != eventDimension:
            return
        kind = str(args.get("kind", ""))
        if kind == "charged":
            charge = max(1, min(3, int(args.get("charge", 1))))
            moteCount = 2 + charge * 2
            for index in range(moteCount):
                angle = math.radians(index * 360.0 / moteCount)
                self._spawn_naga_state_particle(
                    "tf_slice:ghast_trap_mote",
                    (
                        trapPosition[0] + math.cos(angle) * 0.6,
                        trapPosition[1] + 0.15,
                        trapPosition[2] + math.sin(angle) * 0.6,
                    ),
                )
            if charge >= 2:
                self._spawn_naga_state_particle(
                    (
                        "minecraft:campfire_smoke_particle"
                        if charge >= 3
                        else "minecraft:basic_smoke_particle"
                    ),
                    trapPosition,
                )
            return
        if kind == "charge":
            rawGhast = args.get("ghastPosition", ())
            try:
                ghastPosition = (
                    float(rawGhast[0]),
                    float(rawGhast[1]) + 0.8,
                    float(rawGhast[2]),
                )
            except (TypeError, ValueError, IndexError):
                ghastPosition = trapPosition
            for index in range(12):
                factor = index / 11.0
                position = tuple(
                    ghastPosition[axis]
                    + (trapPosition[axis] - ghastPosition[axis]) * factor
                    for axis in range(3)
                )
                self._spawn_naga_state_particle(
                    "tf_slice:ghast_trap_mote", position
                )
            soundName = "random.orb"
        elif kind in ("warmup", "active", "spindown"):
            activeTicks = int(args.get("activeTicks", 0))
            beamHeight = 10.0 if kind != "spindown" else 6.0
            self._spawn_naga_state_particle(
                "tf_slice:ghast_trap_beam",
                (
                    trapPosition[0],
                    trapPosition[1] + beamHeight,
                    trapPosition[2],
                ),
            )
            for vector in ur_ghast_effect_logic.trap_spiral_vectors(
                activeTicks
            ):
                scale = 1.0 if kind != "spindown" else 0.55
                self._spawn_naga_state_particle(
                    "tf_slice:ghast_trap_mote",
                    (
                        trapPosition[0] + vector[0] * scale,
                        trapPosition[1] + vector[1] * scale,
                        trapPosition[2] + vector[2] * scale,
                    ),
                )
            for rawTarget in list(args.get("targetPositions", ()) or ())[:13]:
                try:
                    targetPosition = tuple(
                        float(rawTarget[axis]) for axis in range(3)
                    )
                except (TypeError, ValueError, IndexError):
                    continue
                for index in range(6):
                    factor = (index + 1) / 6.0
                    self._spawn_naga_state_particle(
                        "tf_slice:ghast_trap_mote",
                        tuple(
                            targetPosition[axis]
                            + (trapPosition[axis] - targetPosition[axis])
                            * factor
                            for axis in range(3)
                        ),
                    )
            return
        elif kind == "stop":
            for unusedIndex in range(6):
                self._spawn_naga_state_particle(
                    "tf_slice:ghast_trap_mote",
                    (
                        trapPosition[0] + random.uniform(-0.5, 0.5),
                        trapPosition[1] + random.uniform(0.0, 2.0),
                        trapPosition[2] + random.uniform(-0.5, 0.5),
                    ),
                )
            return
        else:
            return
        try:
            CF.CreateCustomAudio(LEVEL_ID).PlayCustomMusic(
                soundName,
                trapPosition,
                0.8,
                0.8 + min(3, int(args.get("charge", 0))) * 0.2,
                False,
                "",
            )
        except Exception:
            pass

    def OnNagaDeathEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if currentDimension != eventDimension:
            return
        kind = str(args.get("kind", ""))
        particleName = {
            "trail": "tf_slice:naga_composter_single",
            "burst": "tf_slice:naga_death_burst_single",
            "start": "minecraft:large_explosion",
        }.get(kind)
        validPositions = []
        for rawPos in args.get("positions", ()):
            try:
                position = (
                    float(rawPos[0]),
                    float(rawPos[1]),
                    float(rawPos[2]),
                )
            except (TypeError, ValueError, IndexError):
                continue
            validPositions.append(position)
            if particleName is not None:
                self._spawn_naga_state_particle(particleName, position)
        if kind not in ("start", "finish") or not validPositions:
            return
        try:
            soundName = (
                "tf_slice.naga.death"
                if kind == "start"
                else "random.levelup"
            )
            CF.CreateCustomAudio(LEVEL_ID).PlayCustomMusic(
                soundName,
                validPositions[0],
                4.0 if kind == "start" else 1.0,
                1.0,
                False,
                "",
            )
        except Exception:
            pass

    def OnNagaCombatEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
            rawPos = args.get("position", ())
            position = (
                float(rawPos[0]),
                float(rawPos[1]) + 0.9,
                float(rawPos[2]),
            )
        except (TypeError, ValueError, IndexError):
            return
        if currentDimension != eventDimension:
            return
        kind = str(args.get("kind", ""))
        particleName = "minecraft:critical_hit_emitter"
        if kind == "shield_break":
            particleName = "minecraft:large_explosion"
        elif kind == "shield_daze":
            particleName = "minecraft:critical_hit_emitter"
        elif kind == "stunless_charge":
            particleName = "minecraft:villager_angry"
        try:
            particleComp = CF.CreateParticleSystem(None)
            particleId = particleComp.Create(
                particleName,
                position,
                (0.0, 0.0, 0.0),
            )
            if particleId:
                particleComp.SetPos(particleId, position)
        except Exception:
            pass
        soundName = None
        if kind in ("rattle", "stunless_charge"):
            soundName = "tf_slice.naga.rattle"
        elif kind == "shield_daze":
            soundName = "random.anvil_land"
        elif kind == "shield_break":
            soundName = "random.break"
        if soundName is not None:
            try:
                soundVolume = (
                    4.0
                    if soundName == "tf_slice.naga.rattle"
                    else 0.9
                )
                CF.CreateCustomAudio(LEVEL_ID).PlayCustomMusic(
                    soundName,
                    position,
                    soundVolume,
                    1.0,
                    False,
                    ""
                )
            except Exception:
                pass

    def OnBeetleCombatEffect(self, args):
        try:
            currentDimension = CF.CreateGame(LEVEL_ID).GetCurrentDimension()
            eventDimension = int(args.get("dimensionId", -1))
        except (TypeError, ValueError):
            return
        if currentDimension != eventDimension:
            return
        kind = str(args.get("kind", ""))
        particleName = (
            "tf_slice:hydra_flame"
            if kind == "fire_breath"
            else "tf_slice:slime_splash"
        )
        try:
            particleComp = CF.CreateParticleSystem(None)
            for rawPos in args.get("positions", []):
                position = (
                    float(rawPos[0]),
                    float(rawPos[1]),
                    float(rawPos[2]),
                )
                particleId = particleComp.Create(
                    particleName, position, (0.0, 0.0, 0.0)
                )
                if particleId:
                    particleComp.SetPos(particleId, position)
                    if kind != "fire_breath":
                        particleComp.EmitManually(particleId)
        except (TypeError, ValueError, IndexError):
            return
        except Exception:
            pass
