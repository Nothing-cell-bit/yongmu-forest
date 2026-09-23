import json
import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
sys.path.insert(0, str(PACKAGE_ROOT))

import boss_hud_logic


CLIENT_SYSTEM = PACKAGE_ROOT / "clientSystem.py"
SERVER_SYSTEM = PACKAGE_ROOT / "serverSystem.py"
NAGA_HUD = PACKAGE_ROOT / "nagaBossHudUI.py"
LICH_HUD = PACKAGE_ROOT / "lichBossHudUI.py"
ROUTE_HUD = PACKAGE_ROOT / "routeBossHudUI.py"
NAGA_ENTITY = ROOT / "TwilightBossSliceB" / "entities" / "forest_wyrm.entity.json"
LICH_ENTITY = ROOT / "TwilightBossSliceB" / "entities" / "lich.entity.json"


def _boss(entity_id, kind, position, dimension=7):
    return {
        "id": entity_id,
        "kind": kind,
        "position": position,
        "dimensionId": dimension,
    }


class TestBossHudVisibility:
    def test_server_visibility_is_undecided_when_viewer_position_is_missing(self):
        visible, distance_squared = boss_hud_logic.server_visibility_decision(
            [5.0, 0.0, 0.0],
            7,
            None,
            7,
            64.0,
        )

        assert visible is None
        assert distance_squared is None

    def test_server_visibility_is_undecided_when_viewer_dimension_is_missing(self):
        visible, distance_squared = boss_hud_logic.server_visibility_decision(
            [5.0, 0.0, 0.0],
            7,
            [0.0, 0.0, 0.0],
            None,
            64.0,
        )

        assert visible is None
        assert distance_squared is None

    def test_server_visibility_definitively_hides_a_different_dimension(self):
        visible, distance_squared = boss_hud_logic.server_visibility_decision(
            None,
            7,
            None,
            8,
            64.0,
        )

        assert visible is False
        assert distance_squared is None

    def test_server_visibility_includes_the_64_block_boundary(self):
        assert boss_hud_logic.server_visibility_decision(
            [64.0, 0.0, 0.0],
            7,
            [0.0, 0.0, 0.0],
            7,
            64.0,
        ) == (True, 4096.0)
        assert boss_hud_logic.server_visibility_decision(
            [64.01, 0.0, 0.0],
            7,
            [0.0, 0.0, 0.0],
            7,
            64.0,
        )[0] is False

    def test_undecided_server_visibility_falls_back_to_client_context(self):
        boss = _boss("fallback", "naga", [5.0, 0.0, 0.0])
        boss["hudVisible"] = None
        boss["hudDistanceSquared"] = None

        visible = boss_hud_logic.visible_bosses(
            [boss],
            "naga",
            7,
            [0.0, 0.0, 0.0],
            64.0,
        )

        assert [candidate["id"] for candidate in visible] == ["fallback"]

    def test_server_authority_keeps_nearby_boss_visible_without_client_position(self):
        boss = _boss("nearby", "naga", None)
        boss["hudVisible"] = True
        boss["hudDistanceSquared"] = 25.0

        visible = boss_hud_logic.visible_bosses(
            [boss],
            "naga",
            None,
            None,
            64.0,
        )

        assert [candidate["id"] for candidate in visible] == ["nearby"]

    def test_server_authority_hides_out_of_range_boss_despite_stale_client_position(self):
        boss = _boss("far", "lich", [1.0, 0.0, 0.0])
        boss["hudVisible"] = False
        boss["hudDistanceSquared"] = 10000.0

        assert boss_hud_logic.visible_bosses(
            [boss],
            "lich",
            7,
            [0.0, 0.0, 0.0],
            64.0,
        ) == []

    def test_only_same_dimension_bosses_inside_the_64_block_range_are_visible(self):
        bosses = [
            _boss("boundary", "naga", [64.0, 0.0, 0.0]),
            _boss("too_far", "naga", [64.01, 0.0, 0.0]),
            _boss("wrong_dimension", "naga", [1.0, 0.0, 0.0], dimension=8),
            _boss("wrong_kind", "lich", [1.0, 0.0, 0.0]),
        ]

        visible = boss_hud_logic.visible_bosses(
            bosses,
            "naga",
            7,
            [0.0, 0.0, 0.0],
            64.0,
        )

        assert [boss["id"] for boss in visible] == ["boundary"]

    def test_nearest_boss_is_first_with_a_stable_entity_id_tiebreak(self):
        bosses = [
            _boss("far", "lich", [20.0, 0.0, 0.0]),
            _boss("z_tie", "lich", [5.0, 0.0, 0.0]),
            _boss("a_tie", "lich", [-5.0, 0.0, 0.0]),
        ]

        visible = boss_hud_logic.visible_bosses(
            bosses,
            "lich",
            7,
            [0.0, 0.0, 0.0],
            64.0,
        )

        assert [boss["id"] for boss in visible] == ["a_tie", "z_tie", "far"]

    def test_missing_viewer_context_and_invalid_boss_positions_fail_closed(self):
        bosses = [
            _boss("missing", "naga", None),
            _boss("short", "naga", [1.0, 2.0]),
            _boss("invalid", "naga", ["x", 0.0, 0.0]),
        ]

        assert boss_hud_logic.visible_bosses(bosses, "naga", None, [0, 0, 0], 64) == []
        assert boss_hud_logic.visible_bosses(bosses, "naga", 7, None, 64) == []
        assert boss_hud_logic.visible_bosses(bosses, "naga", 7, [0, 0, 0], 64) == []


class TestRouteBossHudLifecycle:
    def test_recreated_route_hud_keeps_root_when_legacy_fill_path_is_missing(self):
        class FakeLabel:
            def __init__(self):
                self.text = None

            def SetText(self, value):
                self.text = value

        class FakeImage:
            def SetSpriteColor(self, unused_color):
                pass

        class FakeControl:
            def __init__(self, label=None, image=None):
                self.label = label
                self.image = image
                self.visible = False
                self.size = None

            def SetFullPosition(self, unused_axis, unused_value):
                pass

            def SetVisible(self, value):
                self.visible = bool(value)

            def SetSize(self, value):
                self.size = tuple(value)

            def asLabel(self):
                return self.label

            def asImage(self):
                return self.image

        root = FakeControl()
        title_label = FakeLabel()
        controls = {
            "/boss_root": root,
            "/boss_root/title": FakeControl(label=title_label),
            "/boss_root/bar_frame/bar_fill_clip": FakeControl(),
            "/boss_root/bar_frame/bar_fill_clip/bar_fill": FakeControl(
                image=FakeImage()
            ),
        }

        class FakeScreenNode:
            def __init__(self, unused_namespace, unused_name, unused_param):
                pass

            def GetBaseUIControl(self, path):
                if path == "/boss_root/bar_frame/bar_fill":
                    raise RuntimeError("legacy direct fill control does not exist")
                return controls[path]

        client_package = types.ModuleType("client")
        extra_client_api = types.ModuleType("client.extraClientApi")
        extra_client_api.GetScreenNodeCls = lambda: FakeScreenNode
        client_package.extraClientApi = extra_client_api
        previous_client = sys.modules.get("client")
        previous_extra = sys.modules.get("client.extraClientApi")
        sys.modules["client"] = client_package
        sys.modules["client.extraClientApi"] = extra_client_api
        package_parent = str(PACKAGE_ROOT.parent)
        sys.path.insert(0, package_parent)
        try:
            spec = importlib.util.spec_from_file_location(
                "routeBossHudUI_lifecycle_test", ROUTE_HUD
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.set_ur_ghasts(
                [
                    {
                        "kind": "ur_ghast",
                        "name": "Ur-Ghast",
                        "health": 120.0,
                        "maxHealth": 250.0,
                    }
                ]
            )
            node = module.UrGhastBossHudUI("test", "test", {})
            node.Init()
        finally:
            sys.path.remove(package_parent)
            if previous_client is None:
                sys.modules.pop("client", None)
            else:
                sys.modules["client"] = previous_client
            if previous_extra is None:
                sys.modules.pop("client.extraClientApi", None)
            else:
                sys.modules["client.extraClientApi"] = previous_extra

        assert root.visible is True
        assert title_label.text == "Ur-Ghast"
        assert controls["/boss_root/bar_frame/bar_fill_clip"].size == (87.36, 5.0)
        assert module.ur_ghast_active() is True
        node.Destroy()
        assert module.ur_ghast_active() is False

        cases = (
            (
                module.set_minoshrooms,
                module.MinoshroomBossHudUI,
                module.minoshroom_active,
                {
                    "kind": "minoshroom",
                    "name": "Minoshroom",
                    "health": 60.0,
                    "maxHealth": 120.0,
                },
            ),
            (
                module.set_hydras,
                module.HydraBossHudUI,
                module.hydra_active,
                {
                    "kind": "hydra",
                    "name": "Hydra",
                    "health": 180.0,
                    "maxHealth": 360.0,
                },
            ),
            (
                module.set_knight_phantoms,
                module.KnightPhantomsBossHudUI,
                module.knight_phantoms_active,
                {
                    "kind": "knight_phantoms",
                    "name": "Knight Phantoms",
                    "health": 40.0,
                    "maxHealth": 80.0,
                },
            ),
        )
        for setter, node_class, is_active, boss in cases:
            module.invalidate()
            root.visible = False
            setter([boss], 1)
            route_node = node_class("test", "test", {})
            route_node.Create()
            assert is_active() is True
            assert root.visible is True
            setter([], 0)
            assert root.visible is False
            route_node.Destroy()
            assert is_active() is False


class TestBossHudIntegrationContract:
    def test_custom_hud_is_the_only_boss_bar_owner(self):
        for path in (NAGA_ENTITY, LICH_ENTITY):
            components = json.loads(path.read_text(encoding="utf-8"))[
                "minecraft:entity"
            ]["components"]
            assert "minecraft:boss" not in components

    def test_server_sync_includes_authoritative_boss_positions(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        make_packet = source[source.index("    def _make_sync_packet") :]
        make_packet = make_packet[: make_packet.index("    def _broadcast_sync")]

        assert "self._get_foot_pos(bossId)" in make_packet
        assert "boss_hud_logic.server_visibility_decision(" in make_packet
        assert '"position"' in make_packet
        assert '"hudVisible"' in make_packet
        assert '"hudDistanceSquared"' in make_packet

    def test_server_sends_player_specific_boss_hud_visibility(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        broadcast = source[source.index("    def _broadcast_sync") :]
        broadcast = broadcast[: broadcast.index("    def _make_perf_packet")]

        assert "self._get_online_players()" in broadcast
        assert "self.NotifyToClient(" in broadcast
        assert "self._make_sync_packet(playerId)" in broadcast

    def test_client_filters_and_orders_all_custom_huds_with_server_context(self):
        source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def OnBossSync") :]
        handler = handler[: handler.index("    def OnPerfSync")]

        assert '"position": boss.get("position")' in handler
        assert '"hudVisible": boss.get("hudVisible")' in handler
        assert '"hudDistanceSquared": boss.get(' in handler
        assert '"hudDistanceSquared"' in handler
        assert handler.count("boss_hud_logic.visible_bosses(") == 6
        assert "config.BOSS_HUD_RANGE" in handler

    def test_hydra_head_updates_cannot_resurrect_a_server_hidden_hud(self):
        source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def OnHydraHeadSync") :]
        handler = handler[: handler.index("    def OnHydraRouteEffect")]

        assert 'boss.get("hudVisible") is not None' in handler
        assert '[boss] if boss.get("hudVisible") else []' in handler
        assert "routeBossHudUI.set_hydras([boss])" not in handler

    def test_ui_reload_invalidates_both_cached_boss_hud_nodes(self):
        source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def OnUiInitFinished") :]
        handler = handler[: handler.index("    def _ensure_lich_boss_hud")]

        assert "lichBossHudUI.invalidate()" in handler
        assert "nagaBossHudUI.invalidate()" in handler
        assert "def invalidate():" in LICH_HUD.read_text(encoding="utf-8")
        assert "def invalidate():" in NAGA_HUD.read_text(encoding="utf-8")

    def test_boss_huds_are_created_only_when_visible_bosses_need_them(self):
        source = CLIENT_SYSTEM.read_text(encoding="utf-8")
        update = source[source.index("    def Update") :]
        update = update[: update.index("    def OnScriptTickClient")]
        reload_handler = source[source.index("    def OnUiInitFinished") :]
        reload_handler = reload_handler[
            : reload_handler.index("    def _ensure_lich_boss_hud")
        ]
        sync_handler = source[source.index("    def OnBossSync") :]
        sync_handler = sync_handler[: sync_handler.index("    def OnPerfSync")]

        for ensure_call in (
            "self._ensure_lich_boss_hud()",
            "self._ensure_naga_boss_hud()",
            'self._ensure_route_boss_hud("minoshroom")',
            'self._ensure_route_boss_hud("hydra")',
            'self._ensure_route_boss_hud("mosquito")',
        ):
            assert ensure_call not in update
            assert ensure_call not in reload_handler

        expected_lazy_creates = (
            ("visibleLiches", "self._ensure_lich_boss_hud()"),
            ("visibleNagas", "self._ensure_naga_boss_hud()"),
            (
                "visibleMinoshrooms",
                'self._ensure_route_boss_hud("minoshroom")',
            ),
            ("visibleHydras", 'self._ensure_route_boss_hud("hydra")'),
        )
        for visible_name, ensure_call in expected_lazy_creates:
            assert "if %s:" % visible_name in sync_handler
            guarded = sync_handler[sync_handler.index("if %s:" % visible_name) :]
            assert ensure_call in guarded.split("\n", 3)[1]

    def test_live_boss_actor_removal_is_not_treated_as_defeat(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def OnRemoveEntity") :]
        handler = handler[: handler.index("    def _place_knight_group_reward_chest")]

        assert "self._on_boss_actor_removed(" in handler
        assert "self._recover_premature_ur_ghast_death(" not in handler
        assert 'lichState["dead"] = True' not in handler
        assert "self._mark_boss_dead(entityId, state)" not in handler

    def test_unloaded_naga_is_retained_for_actor_reentry(self):
        source = SERVER_SYSTEM.read_text(encoding="utf-8")
        handler = source[source.index("    def _forget_missing_bosses") :]
        handler = handler[: handler.index("    def _discover_bosses")]

        assert "self._on_boss_actor_removed(" in handler
        assert "self._boss_home_is_observed(state)" in handler
        unobserved = handler[handler.index("if not self._boss_home_is_observed(state)") :]
        unobserved = unobserved[: unobserved.index("            missing.append(")]
        assert "self._on_boss_actor_removed(" in unobserved
        assert "continue" in unobserved
        assert "self._bosses.pop(bossId, None)" in handler
        assert "mark_naga_missing" in handler
