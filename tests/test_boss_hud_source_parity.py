import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
RESOURCE_UI = ROOT / "TwilightBossSliceR" / "ui"
sys.path.insert(0, str(PACKAGE_ROOT))

import boss_hud_logic


HUD_FILES = {
    "naga": RESOURCE_UI / "naga_boss_hud.json",
    "lich": RESOURCE_UI / "lich_boss_hud.json",
    "minoshroom": RESOURCE_UI / "minoshroom_boss_hud.json",
    "hydra": RESOURCE_UI / "hydra_boss_hud.json",
}


def _hud(kind):
    return json.loads(HUD_FILES[kind].read_text(encoding="utf-8"))


def _root(kind):
    document = _hud(kind)
    return next(
        control["boss_root"]
        for control in document["main"]["controls"]
        if "boss_root" in control
    )


def _named_controls(control):
    return dict((next(iter(row)), next(iter(row.values()))) for row in control)


class TestBossHudSourceStyle:
    def test_progress_converts_to_modsdk_clipped_fraction(self):
        assert boss_hud_logic.progress_clip_ratio(0.0) == 1.0
        assert boss_hud_logic.progress_clip_ratio(0.25) == 0.75
        assert boss_hud_logic.progress_clip_ratio(1.0) == 0.0
        assert boss_hud_logic.progress_clip_ratio(-1.0) == 1.0
        assert boss_hud_logic.progress_clip_ratio(2.0) == 0.0
        assert boss_hud_logic.progress_clip_ratio("invalid") == 1.0

    def test_precise_fill_width_tracks_fraction_without_texture_quantization(self):
        assert boss_hud_logic.precise_fill_width(0.0) == 0.0
        assert boss_hud_logic.precise_fill_width(0.25) == 45.5
        assert boss_hud_logic.precise_fill_width(0.5) == 91.0
        assert boss_hud_logic.precise_fill_width(1.0) == 182.0
        assert boss_hud_logic.precise_fill_width(-1.0) == 0.0
        assert boss_hud_logic.precise_fill_width(2.0) == 182.0
        assert boss_hud_logic.precise_fill_width("invalid") == 0.0

    def test_locked_4302508_style_matrix(self):
        assert boss_hud_logic.source_boss_bar_style("naga", 1) == {
            "color": (0.0, 1.0, 0.0),
            "segments": 10,
        }
        assert boss_hud_logic.source_boss_bar_style("lich", 1) == {
            "color": (1.0, 1.0, 0.0),
            "segments": 6,
        }
        assert boss_hud_logic.source_boss_bar_style("lich", 2) == {
            "color": (0.65, 0.0, 0.8),
            "segments": 0,
        }
        assert boss_hud_logic.source_boss_bar_style("lich", 3) == {
            "color": (1.0, 0.0, 0.0),
            "segments": 0,
        }
        assert boss_hud_logic.source_boss_bar_style("hydra", 1) == {
            "color": (0.0, 0.35, 1.0),
            "segments": 0,
        }
        assert boss_hud_logic.source_boss_bar_style("minoshroom", 1) == {
            "color": (1.0, 0.0, 0.0),
            "segments": 0,
        }
        assert boss_hud_logic.source_boss_bar_style(
            "knight_phantoms", 1
        ) == {"color": (1.0, 1.0, 1.0), "segments": 0}
        assert boss_hud_logic.source_boss_bar_style("ur_ghast", 1) == {
            "color": (1.0, 0.0, 0.0),
            "segments": 0,
        }

    def test_visible_bars_are_compacted_into_vanilla_stack_slots(self):
        slots = boss_hud_logic.boss_bar_stack_slots(
            (
                ("naga", [{"id": "n"}]),
                ("lich", []),
                ("minoshroom", []),
                ("hydra", [{"id": "h"}]),
                ("knight_phantoms", []),
                ("ur_ghast", [{"id": "u"}]),
            )
        )

        assert slots == {"naga": 0, "hydra": 1, "ur_ghast": 2}


class TestBossHudResourceParity:
    def test_all_huds_use_the_native_182_by_5_progress_bar_shape(self):
        for kind in HUD_FILES:
            root = _root(kind)
            controls = _named_controls(root["controls"])
            title = controls["title"]
            frame = controls["bar_frame"]
            frame_controls = _named_controls(frame["controls"])

            assert root["offset"] == [0, 0], kind
            assert root["size"] == [182, 20], kind
            assert title["size"] == [182, 10], kind
            assert title["shadow"] is True, kind
            assert frame["type"] == "panel", kind
            assert frame["offset"] == [0, 10], kind
            assert frame["size"] == [182, 5], kind
            assert frame_controls["bar_empty"]["texture"] == (
                "textures/ui/empty_progress_bar"
            ), kind
            clip = frame_controls["bar_fill_clip"]
            assert clip["type"] == "panel"
            assert clip["anchor_from"] == "left_middle"
            assert clip["anchor_to"] == "left_middle"
            assert clip["size"] == [182, 5]
            assert clip["clips_children"] is True
            fill = _named_controls(clip["controls"])["bar_fill"]
            assert fill["texture"] == "textures/ui/filled_progress_bar"
            assert fill["size"] == [182, 5]
            assert "clip_direction" not in fill
            assert "clip_ratio" not in fill

    def test_only_source_notched_bars_have_segment_overlays(self):
        expectations = {
            "naga": [18, 36, 54, 73, 91, 109, 127, 146, 164],
            "lich": [30, 60, 91, 121, 151],
            "minoshroom": [],
            "hydra": [],
        }
        for kind, expected_offsets in expectations.items():
            controls = _named_controls(_root(kind)["controls"])
            frame_controls = _named_controls(controls["bar_frame"]["controls"])
            actual_offsets = [
                value["offset"][0]
                for name, value in frame_controls.items()
                if name.startswith("notch_")
            ]
            assert actual_offsets == expected_offsets, kind

    def test_hydra_does_not_add_a_non_source_screen_darken_overlay(self):
        assert all(
            "darken" not in control
            for control in _hud("hydra")["main"]["controls"]
        )


class TestBossHudAdapterParity:
    def test_titles_only_show_the_source_boss_display_name(self):
        naga = (PACKAGE_ROOT / "nagaBossHudUI.py").read_text("utf-8")
        lich = (PACKAGE_ROOT / "lichBossHudUI.py").read_text("utf-8")
        route = (PACKAGE_ROOT / "routeBossHudUI.py").read_text("utf-8")

        assert "STATE_NAMES" not in naga
        assert "\\u4f53\\u8282" not in naga
        assert "护盾 %d/6" not in lich
        assert 'u"%s  %d/%d"' not in lich
        assert 'title = u"%s  %d/%d%s"' not in route
        assert "\\u5934 %d/7" not in route
        assert "骑士 %d/6" not in route
        assert "暴怒" not in route

    def test_huds_use_precise_geometry_and_accept_stack_slots(self):
        for filename in (
            "nagaBossHudUI.py",
            "lichBossHudUI.py",
            "routeBossHudUI.py",
        ):
            source = (PACKAGE_ROOT / filename).read_text("utf-8")
            assert '"/boss_root/bar_frame/bar_fill_clip"' in source, filename
            assert "boss_hud_logic.precise_fill_width(" in source, filename
            assert "SetSize((fillWidth, 5.0))" in source, filename
            assert "SetSpriteClipRatio" not in source, filename
            assert "SetFullPosition(" in source, filename
            assert '"y",' in source, filename
            assert "SetPosition(" not in source, filename
            assert "SetSize((self.BAR_WIDTH" not in source, filename

    def test_every_route_boss_uses_geometry_width(self):
        route = (PACKAGE_ROOT / "routeBossHudUI.py").read_text("utf-8")
        assert '"/boss_root/bar_frame/bar_fill_clip"' in route
        assert "boss_hud_logic.precise_fill_width(" in route
        assert "self._fill_clip.SetSize((fillWidth, 5.0))" in route
        for class_name in (
            "MinoshroomBossHudUI",
            "HydraBossHudUI",
            "KnightPhantomsBossHudUI",
            "UrGhastBossHudUI",
        ):
            block = route[route.index("class " + class_name) :]
            next_class = block.find("\n\nclass ", 1)
            if next_class >= 0:
                block = block[:next_class]
            assert "preciseFill=True" in block, class_name

    def test_client_assigns_compact_stack_slots_to_every_visible_hud(self):
        client = (PACKAGE_ROOT / "clientSystem.py").read_text("utf-8")
        handler = client[client.index("    def OnBossSync") :]
        handler = handler[: handler.index("    def OnPerfSync")]

        assert "boss_hud_logic.boss_bar_stack_slots(" in handler
        for kind in (
            "lich",
            "naga",
            "minoshroom",
            "hydra",
            "knight_phantoms",
            "ur_ghast",
        ):
            assert 'stackSlots.get("%s", 0)' % kind in handler

    def test_hydra_generator_preserves_the_source_like_hud_contract(self):
        generator = (ROOT / "tools" / "build_hydra_route_models.py").read_text(
            "utf-8"
        )
        hud_builder = generator[generator.index("def hud(") :]
        hud_builder = hud_builder[: hud_builder.index("\n\ndef main()")]

        assert '"size": [182, 5]' in hud_builder
        assert '"textures/ui/empty_progress_bar"' in hud_builder
        assert '"textures/ui/filled_progress_bar"' in hud_builder
        assert '"darken"' not in hud_builder
        assert (
            'hud("hydra_boss_hud", "九头蛇", [0.0, 0.35, 1.0], '
            'precise_fill=True)'
        ) in generator
        assert (
            'hud("minoshroom_boss_hud", "米诺菇", [1.0, 0.0, 0.0], '
            'precise_fill=True)'
        ) in generator
