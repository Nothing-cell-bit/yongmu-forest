"""Lightweight forest silhouettes using native UI geometry; no image asset load."""
import argparse
import json
from pathlib import Path


def document():
    controls = []

    def image(name, size, offset, color, anchor="center", layer=401):
        controls.append({name: {"type": "image", "texture": "textures/ui/white",
            "keep_ratio": False, "anchor_from": anchor, "anchor_to": anchor,
            "size": list(size), "offset": list(offset), "color": list(color),
            "layer": layer}})

    def label(name, text, y, scale, color, width="90%"):
        controls.append({name: {"type": "label", "text": text,
            "anchor_from": "center", "anchor_to": "center",
            "offset": [0, y], "size": [width, 24 if scale > 1 else 16],
            "font_scale_factor": scale, "color": list(color),
            "text_alignment": "center", "layer": 410}})

    # Quiet layered forest. Percentage positions keep both edges framed on
    # 16:9, ultrawide and narrow GUI canvases without stretching artwork.
    for i, (h, shade) in enumerate(((100, (0.025, .070, .068)),
                                   (65, (.026, .085, .073)),
                                   (30, (.035, .100, .078)))):
        image("mist_%d" % i, ("100%", h), (0, 0), shade, "bottom_left")
    for i, (x, height, wide) in enumerate(((-2, 250, 21), (5, 210, 13),
            (12, 165, 10), (20, 120, 7), (77, 132, 7), (85, 180, 11),
            (92, 220, 16), (99, 270, 24))):
        shade = (.014, .040, .034) if i % 2 else (.018, .050, .043)
        image("trunk_%d" % i, (wide, height), ("%d%%" % x, 0), shade, "bottom_left", 402)
        image("crown_%d" % i, (wide * 5, height * .32),
              ("%d%%" % (x - 4), -height * .60), shade, "bottom_left", 402)
        image("branch_%d" % i, (wide * 3, 6),
              ("%d%%" % (x - 2), -height * .45), shade, "bottom_left", 402)
    for i, (x, y) in enumerate(((25, 26), (31, 72), (72, 23), (67, 65),
                               (17, 48), (80, 80), (38, 15), (59, 87))):
        image("firefly_%d" % i, (2, 2), ("%d%%" % x, "%d%%" % y),
              (.36, .58, .31), "top_left", 403)
    image("portal_halo", (36, 42), (0, -64), (.035, .100, .080), layer=405)
    image("portal_frame", (26, 32), (0, -64), (.35, .52, .34), layer=406)
    image("portal_inside", (20, 26), (0, -64), (.08, .10, .17), layer=407)
    image("portal_light", (10, 18), (0, -64), (.17, .22, .29), layer=408)
    image("spark_v", (1, 7), (0, -65), (.76, .85, .59), layer=409)
    image("spark_h", (7, 1), (0, -65), (.76, .85, .59), layer=409)
    label("title", "暮色森林", -27, 1.7, (.84, .91, .75))
    label("subtitle", "T W I L I G H T   F O R E S T", -5, .6, (.45, .62, .53))
    image("divider_left", (44, 1), (-36, 12), (.19, .33, .26), layer=409)
    image("divider_right", (44, 1), (36, 12), (.19, .33, .26), layer=409)
    image("divider_seed", (3, 3), (0, 12), (.57, .68, .40), layer=409)
    label("status", "正在进入暮色森林", 33, .85, (.65, .77, .66))
    for i, x in enumerate((-8, 0, 8)):
        image("waiting_dot_%d" % i, (2, 2), (x, 53),
              (.34 + i * .1, .49 + i * .1, .34 + i * .1), layer=409)
    label("hint", "循着萤火，走入无尽林海", 83, .65, (.44, .59, .50))
    overlay = {"type": "image", "texture": "textures/ui/white", "keep_ratio": False,
               "anchor_from": "center", "anchor_to": "center",
               "size": ["100%", "100%"], "color": [.016, .034, .035],
               "alpha": 1.0, "visible": False, "layer": 400, "controls": controls}
    return {"namespace": "portal_loading", "main": {"type": "screen",
            "size": ["100%", "100%"], "render_game_behind": True,
            "is_showing_menu": False, "absorbs_input": False,
            "controls": [{"overlay": overlay}]}}


def preview(doc, path, width=1280, height=720):
    # Static layout illustration from the same JSON. This is not an engine screenshot.
    from PIL import Image, ImageDraw, ImageFont
    root = doc["main"]["controls"][0]["overlay"]
    scale = 2
    w, h = width / scale, height / scale
    rgb = lambda c: tuple(round(v * 255) for v in c)
    img = Image.new("RGB", (width, height), rgb(root["color"]))
    draw = ImageDraw.Draw(img)
    def unit(v, total):
        return float(v[:-1]) * total / 100 if isinstance(v, str) and v.endswith("%") else float(v)
    for wrapped in sorted(root["controls"], key=lambda n: next(iter(n.values()))["layer"]):
        node = next(iter(wrapped.values()))
        nw, nh = unit(node["size"][0], w), unit(node["size"][1], h)
        x, y = unit(node["offset"][0], w), unit(node["offset"][1], h)
        anchor = node["anchor_from"]
        if anchor == "center":
            x, y = x + (w - nw) / 2, y + (h - nh) / 2
        elif anchor == "bottom_left":
            y += h - nh
        if node["type"] == "image":
            draw.rectangle((x * scale, y * scale, (x + nw) * scale, (y + nh) * scale),
                           fill=rgb(node["color"]))
        else:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",
                                     max(8, int(10 * scale * node["font_scale_factor"])))
            draw.text(((x + nw / 2) * scale, (y + nh / 2) * scale),
                      node["text"], font=font, fill=rgb(node["color"]), anchor="mm")
    img.save(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    doc = document()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.preview:
        preview(doc, args.preview)
