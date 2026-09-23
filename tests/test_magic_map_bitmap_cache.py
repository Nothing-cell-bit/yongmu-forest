# -*- coding: utf-8 -*-
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import unittest

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
BEHAVIOR_ROOT = ROOT / "TwilightBossSliceB"
MODULE_PATH = MODULE_ROOT / "magic_map_bitmap_cache.py"


def load_module():
    sys.path.insert(0, str(BEHAVIOR_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "magic_map_bitmap_cache_under_test",
            str(MODULE_PATH),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class MagicMapBitmapEncodingTests(unittest.TestCase):
    def test_full_checkerboard_uses_engine_safe_rgba_pixels(self):
        bitmap = load_module()
        grid_size = 128
        cells = {
            row * grid_size + column: (
                "forest" if (row + column) % 2 else "lake"
            )
            for row in range(grid_size)
            for column in range(grid_size)
        }

        encoded = bitmap.encode_magic_map_png(cells)

        with Image.open(io.BytesIO(encoded)) as image:
            self.assertEqual((128, 128), image.size)
            self.assertEqual("RGBA", image.mode)
            pixels = list(image.getdata())
        forest = bitmap.MAGIC_MAP_BIOME_RGBA["forest"]
        lake = bitmap.MAGIC_MAP_BIOME_RGBA["lake"]
        self.assertEqual([lake, forest, lake, forest], pixels[:4])
        self.assertEqual(grid_size * grid_size, len(pixels))

    def test_unexplored_is_transparent_and_active_palette_is_exact(self):
        bitmap = load_module()
        self.assertEqual(
            set(bitmap.magic_map_logic.TWILIGHT_BIOME_KEYS),
            set(bitmap.MAGIC_MAP_BIOME_RGBA),
        )
        cells = {
            index: biome_key
            for index, biome_key in enumerate(
                bitmap.magic_map_logic.TWILIGHT_BIOME_PALETTE[1:]
            )
        }

        encoded = bitmap.encode_magic_map_png(cells)

        with Image.open(io.BytesIO(encoded)) as image:
            rgba = image.convert("RGBA")
            self.assertEqual((0, 0, 0, 0), rgba.getpixel((127, 127)))
            for index, biome_key in enumerate(
                bitmap.magic_map_logic.TWILIGHT_BIOME_PALETTE[1:]
            ):
                self.assertEqual(
                    bitmap.MAGIC_MAP_BIOME_RGBA[biome_key],
                    rgba.getpixel((index, 0)),
                    biome_key,
                )
                palette_path = (
                    ROOT
                    / "TwilightBossSliceR"
                    / "textures"
                    / "ui"
                    / "tf_slice"
                    / "magic_map_palette"
                    / (biome_key + ".png")
                )
                with Image.open(palette_path) as palette_image:
                    self.assertEqual(
                        {bitmap.MAGIC_MAP_BIOME_RGBA[biome_key]},
                        set(palette_image.convert("RGBA").getdata()),
                        biome_key,
                    )


class MagicMapBitmapCacheTests(unittest.TestCase):
    def test_cache_instances_use_distinct_session_paths_without_process_ids(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            first = bitmap.MagicMapBitmapCache(directory)
            second = bitmap.MagicMapBitmapCache(directory)
            self.assertNotEqual(first.session_token, second.session_token)
            first_path = first.render(7, {0: "forest"})
            second_path = second.render(7, {0: "lake"})
            self.assertNotEqual(first_path, second_path)
            with Image.open(first_path) as image:
                self.assertEqual(bitmap.MAGIC_MAP_BIOME_RGBA["forest"], image.getpixel((0, 0)))

    def test_slot_reuse_never_overwrites_the_three_most_recent_images(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            cache = bitmap.MagicMapBitmapCache(directory, max_retained=1)
            self.assertEqual(4, cache.max_retained)
            recent = []
            for index in range(12):
                saved = {path: pathlib.Path(path).read_bytes() for path in recent[-3:]}
                path = cache.render(7, {index: "forest"})
                self.assertNotIn(path, recent[-3:])
                for old_path, payload in saved.items():
                    self.assertEqual(payload, pathlib.Path(old_path).read_bytes())
                recent.append(path)
            self.assertEqual(4, len(list(pathlib.Path(directory).glob("*.png"))))

    def test_missing_cache_directory_fails_without_creating_directories(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "missing"
            cache = bitmap.MagicMapBitmapCache(str(root))
            self.assertIsNone(cache.render(7, {0: "forest"}))
            self.assertTrue(cache.last_error)
            self.assertFalse(root.exists())

    def test_ephemeral_texture_write_does_not_force_durable_disk_flush(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            cache = bitmap.MagicMapBitmapCache(
                directory,
                session_token="no-fsync",
            )
            original_fsync = os.fsync

            def fail_fsync(_descriptor):
                raise AssertionError("temporary texture must not call fsync")

            os.fsync = fail_fsync
            try:
                path = cache.render(7, {0: "forest"})
            finally:
                os.fsync = original_fsync

            self.assertTrue(pathlib.Path(path).is_file())

    def test_unchanged_cells_reuse_path_and_changes_get_unique_revisions(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            cache = bitmap.MagicMapBitmapCache(
                directory,
                session_token="unit",
            )
            cells = {0: "forest"}

            first = cache.render(7, cells)
            first_time = pathlib.Path(first).stat().st_mtime_ns
            unchanged = cache.render(7, dict(cells))
            changed = cache.render(7, {0: "lake"})

            self.assertEqual(first, unchanged)
            self.assertEqual(first_time, pathlib.Path(first).stat().st_mtime_ns)
            self.assertNotEqual(first, changed)
            self.assertTrue(pathlib.Path(first).is_file())
            self.assertTrue(pathlib.Path(changed).is_file())
            self.assertTrue(first.endswith("_unit_00000001.png"))
            self.assertTrue(changed.endswith("_unit_00000002.png"))

    def test_bounded_slots_reuse_only_retired_paths_and_preserve_exact_pixels(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            cache = bitmap.MagicMapBitmapCache(
                directory,
                session_token="cleanup",
                max_retained=4,
            )

            paths = [
                cache.render(7, {index: "forest"})
                for index in range(6)
            ]

            self.assertEqual(4, len(set(paths)))
            self.assertEqual(paths[0], paths[4])
            self.assertEqual(paths[1], paths[5])
            with Image.open(paths[5]) as image:
                self.assertEqual(bitmap.MAGIC_MAP_BIOME_RGBA["forest"], image.getpixel((5, 0)))
                self.assertEqual((0, 0, 0, 0), image.getpixel((1, 0)))
            self.assertTrue(all(pathlib.Path(path).exists() for path in paths[2:]))
            self.assertEqual(
                4,
                len(list(pathlib.Path(directory).glob("*.png"))),
            )

    def test_failed_write_keeps_the_last_valid_bitmap(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            cache = bitmap.MagicMapBitmapCache(
                directory,
                session_token="failure",
            )
            valid = cache.render(9, {0: "forest"})

            def fail_write(_path, _payload):
                raise IOError("disk unavailable")

            cache._write_bitmap = fail_write
            retained = cache.render(9, {0: "lake"})

            self.assertEqual(valid, retained)
            self.assertIn("disk unavailable", cache.last_error)
            self.assertTrue(pathlib.Path(valid).is_file())

    def test_invalid_map_identity_never_creates_a_cache_file(self):
        bitmap = load_module()
        with tempfile.TemporaryDirectory() as directory:
            cache = bitmap.MagicMapBitmapCache(
                directory,
                session_token="invalid",
            )

            self.assertIsNone(cache.render(None, {0: "forest"}))
            self.assertIsNone(cache.render(-1, {0: "forest"}))
            self.assertEqual([], list(pathlib.Path(directory).iterdir()))


if __name__ == "__main__":
    unittest.main()
