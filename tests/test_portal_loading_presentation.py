import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import build_portal_loading_presentation as builder


def test_presentation_preserves_live_overlay_path_and_input_contract():
    doc = builder.document()
    main = doc["main"]
    assert main["absorbs_input"] is False and main["is_showing_menu"] is False
    overlay = main["controls"][0]["overlay"]
    assert overlay["visible"] is False
    assert overlay["size"] == ["100%", "100%"]
    assert len(overlay["controls"]) < 100
    labels = [c[next(iter(c))] for c in overlay["controls"] if c[next(iter(c))]["type"] == "label"]
    assert any(c["text"] == "暮色森林" for c in labels)
    assert any("正在进入" in c["text"] for c in labels)
    assert not any("%" in c["text"] or "返程门" in c["text"] for c in labels)


def test_ui_uses_existing_native_texture_and_responsive_background():
    overlay = builder.document()["main"]["controls"][0]["overlay"]
    images = [c[next(iter(c))] for c in overlay["controls"] if c[next(iter(c))]["type"] == "image"]
    assert all(c["texture"] == "textures/ui/white" for c in images)
    assert len(images) > 20
    assert any(c["anchor_from"] == "bottom_left" for c in images)
