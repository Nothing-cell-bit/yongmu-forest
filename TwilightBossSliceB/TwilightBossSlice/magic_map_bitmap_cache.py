# -*- coding: utf-8 -*-
import binascii
import io
import posixpath
import random
import struct
import zlib

import TwilightBossSlice.biome_catalog as biome_catalog
import TwilightBossSlice.magic_map_logic as magic_map_logic
import TwilightBossSlice.maze_map_logic as maze_map_logic


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CACHE_SEQUENCE = 0
MAGIC_MAP_BIOME_RGBA = {
    "forest": (0, 107, 0, 255),
    "dense_forest": (0, 87, 0, 255),
    "oak_savannah": (89, 125, 38, 255),
    "mushroom_forest": (153, 89, 36, 255),
    "firefly_forest": (0, 186, 51, 255),
    "stream": (56, 56, 219, 255),
    "dense_mushroom_forest": (171, 89, 115, 255),
    "lake": (33, 33, 135, 255),
    "enchanted_forest": (76, 128, 153, 255),
    "clearing": (128, 178, 56, 255),
    "spooky_forest": (89, 43, 125, 255),
    "unknown": (197, 109, 186, 255),
}
for _territory_profile in biome_catalog.ACTIVE_TERRITORY_CONTENT_PROFILES:
    MAGIC_MAP_BIOME_RGBA[_territory_profile["companionBiome"]] = tuple(
        int(value) for value in _territory_profile["companionMapColor"]
    )
    MAGIC_MAP_BIOME_RGBA[_territory_profile["coreBiome"]] = tuple(
        int(value) for value in _territory_profile["coreMapColor"]
    )


def _byte_string(values):
    value = bytearray(values)
    return struct.pack("%dB" % len(value), *value)


def _png_chunk(chunk_type, payload):
    checksum = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", checksum)
    )


def _normalized_cells(cells):
    normalized = {}
    if not isinstance(cells, dict):
        return normalized
    maximum = magic_map_logic.MAP_GRID_SIZE * magic_map_logic.MAP_GRID_SIZE
    for raw_index, raw_key in cells.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        biome_key = str(raw_key)
        if (
            0 <= index < maximum
            and biome_key in magic_map_logic.TWILIGHT_BIOME_INDEXES
        ):
            normalized[index] = biome_key
    return normalized


def _cell_fingerprint(cells):
    return tuple(sorted(_normalized_cells(cells).items()))


def encode_magic_map_png(cells, palette=None):
    """Encode exact map cells as an engine-safe transparent RGBA PNG."""
    grid_size = magic_map_logic.MAP_GRID_SIZE
    palette = MAGIC_MAP_BIOME_RGBA if palette is None else palette
    normalized = _normalized_cells(cells)
    scanlines = []
    for row in range(grid_size):
        scanlines.append(0)
        row_start = row * grid_size
        for column in range(grid_size):
            biome_key = normalized.get(row_start + column)
            scanlines.extend(
                palette.get(biome_key, (0, 0, 0, 0))
            )
    raw_pixels = _byte_string(scanlines)
    header = struct.pack(
        ">IIBBBBB",
        grid_size,
        grid_size,
        8,
        6,
        0,
        0,
        0,
    )
    return b"".join(
        (
            PNG_SIGNATURE,
            _png_chunk(b"IHDR", header),
            _png_chunk(b"IDAT", zlib.compress(raw_pixels, 1)),
            _png_chunk(b"IEND", b""),
        )
    )


class MagicMapBitmapCache(object):
    def __init__(
        self,
        root=None,
        session_token=None,
        max_retained=32,
    ):
        global _CACHE_SEQUENCE
        _CACHE_SEQUENCE += 1
        self._instance_id = _CACHE_SEQUENCE
        self._maze_file_ids = {}
        # Reuse the already-existing script directory. No OS-dependent temp
        # directory, directory creation, process ID, or file deletion is needed.
        path = root or posixpath.dirname(__file__.replace("\\", "/"))
        path = path.replace("\\", "/")
        if not (path.startswith("/") or (len(path) > 2 and path[1:3] == ":/")):
            path = posixpath.abspath(path).replace("\\", "/")
        self.root = posixpath.normpath(path)
        if session_token is None:
            # Isolate concurrent clients/worlds without the forbidden getpid.
            session_token = "%x%x" % (random.getrandbits(64), self._instance_id)
        session_token = "".join(
            character
            for character in str(session_token).lower()
            if character.isalnum()
        )
        self.session_token = session_token or "session"
        try:
            self.max_retained = max(4, min(32, int(max_retained)))
        except (TypeError, ValueError):
            self.max_retained = 32
        self._states = {}
        self.last_error = ""

    def trace(self, stage, map_id, **fields):
        # Kept for UI call compatibility; submission packs never write traces.
        return None

    def _write_bitmap(self, target_path, payload):
        # The slot is outside the three visible buffers. Publish its path only
        # after close succeeds; a failed write leaves the current image intact.
        with io.open(target_path, "wb") as handle:
            handle.write(payload)

    def render(self, map_id, cells):
        palette = None
        if maze_map_logic.decode_identity(map_id) is not None:
            map_id = str(map_id)
            # Cache paths only need process-local identity, not cryptography.
            # Keep distinct cache instances/floors separate with short SDK-safe names.
            file_id = self._maze_file_ids.setdefault(map_id, len(self._maze_file_ids) + 1)
            filename_id = "maze_%d_%d" % (self._instance_id, file_id)
            palette = {"unknown": (67, 61, 53, 255), "clearing": (220, 207, 168, 255)}
            self.trace("bitmap_request", map_id, cellCount=len(cells or {}))
        else:
            try:
                map_id = int(map_id)
            except (TypeError, ValueError):
                return None
            if map_id <= 0:
                return None
            filename_id = str(map_id)
        fingerprint = _cell_fingerprint(cells)
        state = self._states.get(map_id)
        if state is not None and state.get("fingerprint") == fingerprint:
            return state.get("path")
        revision = 1 if state is None else int(state.get("revision", 0)) + 1
        filename = "tf_magic_map_%s_%s_%08d.png" % (
            filename_id,
            self.session_token,
            (revision - 1) % self.max_retained + 1,
        )
        target_path = posixpath.join(self.root, filename)
        try:
            self._write_bitmap(
                target_path,
                encode_magic_map_png(dict(fingerprint), palette),
            )
        except Exception as error:
            self.last_error = repr(error)
            self.trace("bitmap_error", map_id, error=repr(error))
            return state.get("path") if state is not None else None
        raw_path = target_path
        self._states[map_id] = {
            "fingerprint": fingerprint,
            "path": raw_path,
            "revision": revision,
        }
        self.last_error = ""
        return raw_path


_SHARED_CACHE = MagicMapBitmapCache()


def render_magic_map_bitmap(map_id, cells):
    return _SHARED_CACHE.render(map_id, cells)


def trace_maze_snapshot(stage, snapshot, **fields):
    return None
