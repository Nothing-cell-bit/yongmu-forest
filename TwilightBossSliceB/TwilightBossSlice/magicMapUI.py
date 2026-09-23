# -*- coding: utf-8 -*-
import math
import client.extraClientApi as clientApi
import TwilightBossSlice.magic_map_bitmap_cache as magic_map_bitmap_cache
import TwilightBossSlice.magic_map_logic as magic_map_logic
import TwilightBossSlice.maze_map_logic as maze_map_logic


ScreenNode = clientApi.GetScreenNodeCls()
ViewBinder = clientApi.GetViewBinderCls()
CF = clientApi.GetEngineCompFactory()
_PENDING_SNAPSHOT = {}
_ACTIVE_UI = None

ICON_PATHS = {
    "small_hill": "textures/ui/tf_slice/magic_map_icons/small_hill",
    "medium_hill": "textures/ui/tf_slice/magic_map_icons/medium_hill",
    "large_hill": "textures/ui/tf_slice/magic_map_icons/large_hill",
    "hedge_maze": "textures/ui/tf_slice/magic_map_icons/hedge_maze",
    "naga_courtyard": (
        "textures/ui/tf_slice/magic_map_icons/naga_courtyard"
    ),
    "lich_tower": "textures/ui/tf_slice/magic_map_icons/lich_tower",
    "ice_tower": "textures/ui/tf_slice/magic_map_icons/ice_tower",
    "quest_grove": "textures/ui/tf_slice/magic_map_icons/quest_grove",
    "hydra_lair": "textures/ui/tf_slice/magic_map_icons/hydra_lair",
    "labyrinth": "textures/ui/tf_slice/magic_map_icons/labyrinth",
    "dark_tower": "textures/ui/tf_slice/magic_map_icons/dark_tower",
    "knight_stronghold": (
        "textures/ui/tf_slice/magic_map_icons/knight_stronghold"
    ),
    "yeti_cave": "textures/ui/tf_slice/magic_map_icons/yeti_cave",
    "troll_cave": "textures/ui/tf_slice/magic_map_icons/troll_cave",
    "final_castle": "textures/ui/tf_slice/magic_map_icons/final_castle",
}

PLAYER_MARKER_TEXTURE_PATHS = dict(
    (
        direction,
        "textures/ui/tf_slice/magic_map_player/" + direction,
    )
    for direction in ("north", "east", "south", "west", "off_map")
)
LOCAL_PLAYER_COLOR = (0.92, 0.16, 0.12)
OTHER_PLAYER_COLOR = (1.0, 1.0, 1.0)
BITMAP_RENDER_INTERVAL_TICKS = 6
BITMAP_RETENTION_TICKS = 120
BITMAP_BUFFER_SLOTS = ("a", "b", "c")

BIOME_KEYS = magic_map_logic.TWILIGHT_BIOME_KEYS


def set_snapshot(snapshot):
    global _PENDING_SNAPSHOT, _ACTIVE_UI
    magic_map_bitmap_cache.trace_maze_snapshot("screen_snapshot", snapshot)
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.ApplySnapshot(snapshot)
        return
    _PENDING_SNAPSHOT = dict(snapshot or {})


def apply_delta(delta):
    global _ACTIVE_UI
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.ApplyDelta(delta)


def _take_snapshot():
    global _PENDING_SNAPSHOT
    snapshot = _PENDING_SNAPSHOT
    _PENDING_SNAPSHOT = {}
    return snapshot


class MagicMapUI(ScreenNode):
    """Persistent 128px Twilight map with live delta and player updates."""

    def __init__(self, namespace, name, param):
        super(MagicMapUI, self).__init__(namespace, name, param)
        self._snapshot = _take_snapshot()
        self._dynamic_controls = []
        self._canvas_size = (0.0, 0.0)
        self._canvas = None
        self._cells = {}
        self._biome_bitmap_controls = {
            "a": None,
            "b": None,
            "c": None,
        }
        self._bitmap_dirty = False
        self._bitmap_paths = {"a": "", "b": "", "c": ""}
        self._bitmap_latest_slot = None
        self._bitmap_next_slot_index = 0
        self._bitmap_pending_slot = None
        self._bitmap_retention_ticks = 0
        self._landmark_keys = set()
        self._conquered_keys = set()
        self._player_control = None
        self._other_player_controls = {}
        self._player_marker_state = "inside"
        self._player_direction = None
        self._local_player_position_ready = False
        self._live_tick = 0
        self._control_sequence = 0

    def Create(self):
        global _ACTIVE_UI
        _ACTIVE_UI = self
        self._set_label("/parchment_frame/title", self._title_text())
        self._set_label("/parchment_frame/coordinates", self._coordinate_text())
        close_control = self.GetBaseUIControl(
            "/parchment_frame/close_button"
        )
        if close_control is not None:
            button = close_control.asButton()
            if button is not None:
                button.AddTouchEventParams({"isSwallow": True})
                button.SetButtonTouchUpCallback(self._close)
        canvas = self.GetBaseUIControl("/parchment_frame/map_canvas")
        if canvas is None:
            return
        canvas_size = canvas.GetSize()
        if not canvas_size or len(canvas_size) != 2:
            return
        self._canvas_size = magic_map_logic.resolve_canvas_size(
            canvas_size,
            self._snapshot.get(
                "gridSize",
                magic_map_logic.MAP_GRID_SIZE,
            ),
        )
        self._canvas = canvas
        self._biome_bitmap_controls = {
            "a": self.GetBaseUIControl(
                "/parchment_frame/map_canvas/biome_bitmap_a"
            ),
            "b": self.GetBaseUIControl(
                "/parchment_frame/map_canvas/biome_bitmap_b"
            ),
            "c": self.GetBaseUIControl(
                "/parchment_frame/map_canvas/biome_bitmap_c"
            ),
        }
        for control in self._biome_bitmap_controls.values():
            if control is not None:
                control.SetVisible(True)
                control.SetAlpha(0.0)
        self._draw_biomes(canvas)
        self._draw_landmarks(canvas)
        self._draw_shared_players(canvas)
        self._draw_player(canvas)

    def _set_label(self, path, text):
        control = self.GetBaseUIControl(path)
        if control is None:
            return
        label = control.asLabel()
        if label is not None:
            label.SetText(text)

    def _title_text(self):
        return u"迷宫地图" if self._snapshot.get("mapKind") == "maze" else u"魔法地图"

    def _coordinate_text(self):
        center = self._snapshot.get("center", (0, 0))
        player = self._snapshot.get("player", (0, 0))
        bounds = self._snapshot.get("bounds", ())
        try:
            outside = not (
                int(bounds[0]) <= int(player[0]) <= int(bounds[2])
                and int(bounds[1]) <= int(player[1]) <= int(bounds[3])
            )
            suffix = "  (outside)" if outside else ""
            text = "Center X:%d Z:%d  |  Player X:%d Z:%d%s" % (
                int(center[0]),
                int(center[1]),
                int(player[0]),
                int(player[1]),
                suffix,
            )
            if self._snapshot.get("mapKind") == "maze":
                marker = str(self._snapshot.get("verticalMarker", "same"))
                arrow = {"up": u"↑", "down": u"↓"}.get(marker, u"•")
                text += "  |  Floor Y:%d %s" % (
                    int(self._snapshot.get("yCenter", 0)),
                    arrow,
                )
            return text
        except (IndexError, TypeError, ValueError):
            return ""

    def _clean_cells(self):
        try:
            grid_size = int(self._snapshot.get("gridSize", 0))
        except (TypeError, ValueError):
            return 0, {}
        if grid_size <= 0 or grid_size > 128:
            return grid_size, {}
        cells = {}
        for run in self._snapshot.get("biomeRuns", ()):
            if not isinstance(run, (list, tuple)) or len(run) != 4:
                continue
            try:
                row = int(run[0])
                start = int(run[1])
                end = int(run[2])
            except (TypeError, ValueError):
                continue
            biome_key = str(run[3])
            if (
                biome_key not in BIOME_KEYS
                or not 0 <= row < grid_size
                or not 0 <= start < end <= grid_size
            ):
                continue
            for column in range(start, end):
                cells[row * grid_size + column] = biome_key
        # Schema 2 compatibility is deliberately retained for pending packets.
        for entry in self._snapshot.get("biomeCells", ()):
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                continue
            try:
                index = int(entry[0])
            except (TypeError, ValueError):
                continue
            biome_key = str(entry[1])
            if (
                0 <= index < grid_size * grid_size
                and biome_key in BIOME_KEYS
            ):
                cells[index] = biome_key
        return grid_size, cells

    def _draw_biomes(self, canvas):
        grid_size, cells = self._clean_cells()
        self._cells = dict(cells)
        self._draw_cell_dict(canvas, grid_size, cells, "initial")

    def _draw_cell_dict(self, canvas, grid_size, cells, prefix):
        if grid_size <= 0 or canvas is None:
            return
        self._cells.update(cells or {})
        self._bitmap_dirty = True
        if prefix != "delta":
            self._render_biome_bitmap()

    def _render_biome_bitmap(self):
        magic_map_bitmap_cache.trace_maze_snapshot(
            "screen_render", self._snapshot, cellCount=len(self._cells),
            missingControls=any(control is None for control in self._biome_bitmap_controls.values()),
        )
        if self._bitmap_pending_slot is not None or not self._bitmap_dirty:
            return
        controls = self._biome_bitmap_controls
        if any(control is None for control in controls.values()):
            return
        if not self._cells:
            for control in controls.values():
                control.SetAlpha(0.0)
                control.SetVisible(False)
            self._bitmap_paths = {"a": "", "b": "", "c": ""}
            self._bitmap_latest_slot = None
            self._bitmap_next_slot_index = 0
            self._bitmap_pending_slot = None
            self._bitmap_retention_ticks = 0
            self._bitmap_dirty = False
            return
        path = magic_map_bitmap_cache.render_magic_map_bitmap(
            self._snapshot.get("mapId"),
            self._cells,
        )
        if not path:
            return
        if path in self._bitmap_paths.values():
            self._bitmap_dirty = False
            return
        pending_slot = BITMAP_BUFFER_SLOTS[self._bitmap_next_slot_index]
        self._bitmap_next_slot_index = (
            self._bitmap_next_slot_index + 1
        ) % len(BITMAP_BUFFER_SLOTS)
        control = controls[pending_slot]
        self._bitmap_paths[pending_slot] = path
        control.SetVisible(True)
        control.SetAlpha(1.0)
        self._bitmap_latest_slot = pending_slot
        self._bitmap_pending_slot = pending_slot
        self._bitmap_retention_ticks = BITMAP_RETENTION_TICKS
        self._bitmap_dirty = False

    def _advance_bitmap_retention(self):
        if self._bitmap_pending_slot is None:
            return
        if self._bitmap_retention_ticks > 0:
            self._bitmap_retention_ticks -= 1
        if self._bitmap_retention_ticks > 0:
            return
        latest_slot = self._bitmap_pending_slot
        self._bitmap_pending_slot = None
        self._bitmap_retention_ticks = 0
        for slot, control in self._biome_bitmap_controls.items():
            if control is not None and slot != latest_slot:
                control.SetAlpha(0.0)
                control.SetVisible(False)

    def GetBitmapPath(self, slot):
        return self._bitmap_paths.get(slot, "")

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_a",
    )
    def GetBitmapPathA(self):
        return self.GetBitmapPath("a")

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_b",
    )
    def GetBitmapPathB(self):
        return self.GetBitmapPath("b")

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_c",
    )
    def GetBitmapPathC(self):
        return self.GetBitmapPath("c")

    def _map_position(self, block_x, block_z):
        return magic_map_logic.map_marker_position(
            block_x,
            block_z,
            self._snapshot.get("bounds", ()),
            self._canvas_size[0],
            self._canvas_size[1],
        )

    def _player_map_position(self, block_x, block_z):
        return magic_map_logic.map_marker_position(
            block_x,
            block_z,
            self._snapshot.get("bounds", ()),
            self._canvas_size[0],
            self._canvas_size[1],
            4,
        )

    def _draw_landmarks(self, canvas):
        for marker_index, landmark in enumerate(
            self._snapshot.get("landmarks", ())
        ):
            if not isinstance(landmark, dict):
                continue
            icon = ICON_PATHS.get(str(landmark.get("icon", "")))
            position = landmark.get("position")
            marker_key = str(landmark.get("key", ""))
            if (
                icon is None
                or not position
                or len(position) != 2
            ):
                continue
            pixel = self._map_position(position[0], position[1])
            if pixel is None:
                continue
            if marker_key and marker_key in self._landmark_keys:
                self._draw_conquered_marker(
                    canvas,
                    marker_index,
                    marker_key,
                    pixel,
                    landmark,
                )
                continue
            control = self.CreateChildControl(
                "magic_map.landmark_marker",
                "landmark_%d_%d" % (
                    marker_index,
                    self._control_sequence,
                ),
                canvas,
                True,
            )
            self._control_sequence += 1
            if control is None:
                continue
            image = control.asImage()
            if image is not None:
                image.SetSprite(icon)
            control.SetPosition((pixel[0] - 4, pixel[1] - 4))
            self._dynamic_controls.append(control)
            self._draw_conquered_marker(
                canvas,
                marker_index,
                marker_key,
                pixel,
                landmark,
            )
            if marker_key:
                self._landmark_keys.add(marker_key)

    def _draw_conquered_marker(
        self,
        canvas,
        marker_index,
        marker_key,
        pixel,
        landmark,
    ):
        if (
            not bool(landmark.get("conquered", False))
            or marker_key in self._conquered_keys
        ):
            return
        conquered = self.CreateChildControl(
            "magic_map.conquered_marker",
            "conquered_%d_%d" % (
                marker_index,
                self._control_sequence,
            ),
            canvas,
            True,
        )
        self._control_sequence += 1
        if conquered is not None:
            conquered.SetPosition((pixel[0] - 4, pixel[1] - 4))
            self._dynamic_controls.append(conquered)
            if marker_key:
                self._conquered_keys.add(marker_key)

    def _draw_player(self, canvas):
        player = self._snapshot.get("player", ())
        if not player or len(player) != 2:
            return
        pixel = self._player_map_position(player[0], player[1])
        if pixel is None:
            return
        control = self.CreateChildControl(
            "magic_map.player_marker",
            "player_marker",
            canvas,
            True,
        )
        if control is not None:
            self._player_marker_state = pixel[2]
            control.SetPosition((pixel[0] - 4, pixel[1] - 4))
            control.SetVisible(True)
            self._dynamic_controls.append(control)
            self._player_control = control
            self._set_player_direction(control, 0.0)

    def _draw_shared_players(self, canvas):
        for control in self._other_player_controls.values():
            control.SetVisible(False)
        for marker_index, player in enumerate(
            self._snapshot.get("players", ())
        ):
            if marker_index >= magic_map_logic.MAX_SHARED_PLAYERS:
                break
            if not isinstance(player, dict):
                continue
            player_id = str(player.get("id", ""))
            position = player.get("position")
            if not player_id or not position or len(position) != 2:
                continue
            pixel = self._player_map_position(position[0], position[1])
            if pixel is None:
                continue
            control = self._other_player_controls.get(player_id)
            if control is None:
                control = self.CreateChildControl(
                    "magic_map.other_player_marker",
                    "other_player_%d_%d" % (
                        marker_index,
                        self._control_sequence,
                    ),
                    canvas,
                    True,
                )
                self._control_sequence += 1
                if control is None:
                    continue
                self._other_player_controls[player_id] = control
                self._dynamic_controls.append(control)
            image = control.asImage()
            direction = magic_map_logic.player_marker_direction(
                player.get("yaw", 0.0),
                pixel[2],
            )
            if image is not None and direction is not None:
                image.SetSprite(PLAYER_MARKER_TEXTURE_PATHS[direction])
                image.SetSpriteColor(OTHER_PLAYER_COLOR)
            control.SetPosition((pixel[0] - 4, pixel[1] - 4))
            control.SetVisible(direction is not None)

    def _set_player_direction(self, control, yaw):
        image = control.asImage() if control is not None else None
        direction = magic_map_logic.player_marker_direction(
            yaw,
            self._player_marker_state,
        )
        if image is None or direction is None:
            return
        if direction != self._player_direction:
            image.SetSprite(PLAYER_MARKER_TEXTURE_PATHS[direction])
            image.SetSpriteColor(LOCAL_PLAYER_COLOR)
            self._player_direction = direction

    def ApplySnapshot(self, snapshot):
        if getattr(self, "_destroyed", False):
            return
        if not isinstance(snapshot, dict):
            return
        currentId = self._snapshot.get("mapId")
        nextId = snapshot.get("mapId")
        if currentId is not None and nextId != currentId:
            for control in self._dynamic_controls:
                control.SetVisible(False)
            for control in self._biome_bitmap_controls.values():
                if control is not None:
                    control.SetAlpha(0.0)
                    control.SetVisible(False)
            self._cells = {}
            self._bitmap_paths = {"a": "", "b": "", "c": ""}
            self._bitmap_pending_slot = None
            self._bitmap_retention_ticks = 0
            self._bitmap_latest_slot = None
            self._bitmap_next_slot_index = 0
            self._bitmap_dirty = True
            self._landmark_keys = set()
            self._conquered_keys = set()
            self._player_direction = None
            self._local_player_position_ready = False
            self._snapshot = {}
        self._snapshot.update(snapshot)
        grid_size, cells = self._clean_cells()
        additions = {}
        for index, biome_key in cells.items():
            if self._cells.get(index) != biome_key:
                additions[index] = biome_key
        self._cells.update(additions)
        if additions and self._canvas is not None:
            self._draw_cell_dict(
                self._canvas,
                grid_size,
                additions,
                "delta",
            )
            self._cells.update(additions)
        if self._canvas is not None:
            self._set_label("/parchment_frame/title", self._title_text())
            self._draw_landmarks(self._canvas)
            self._draw_shared_players(self._canvas)
            if self._player_control is None:
                self._draw_player(self._canvas)
        self._update_player_marker()

    def ApplyDelta(self, delta):
        if getattr(self, "_destroyed", False):
            return
        if not isinstance(delta, dict):
            return
        if delta.get("mapId") != self._snapshot.get("mapId"):
            return
        partial = {
            "mapId": delta.get("mapId"),
            "gridSize": self._snapshot.get("gridSize"),
            "biomeRuns": delta.get("biomeRuns", ()),
            "players": delta.get(
                "players",
                self._snapshot.get("players", ()),
            ),
        }
        if not self._local_player_position_ready:
            partial["player"] = delta.get(
                "player",
                self._snapshot.get("player"),
            )
        if "landmarks" in delta:
            partial["landmarks"] = delta.get("landmarks")
        self.ApplySnapshot(partial)

    def _update_player_marker(self):
        if self._player_control is None:
            return
        player = self._snapshot.get("player", ())
        if not player or len(player) != 2:
            return
        pixel = self._player_map_position(player[0], player[1])
        if pixel is not None:
            if self._player_marker_state != pixel[2]:
                self._player_direction = None
            self._player_marker_state = pixel[2]
            self._player_control.SetPosition(
                (pixel[0] - 4, pixel[1] - 4)
            )
            self._player_control.SetVisible(True)
        self._set_label(
            "/parchment_frame/coordinates",
            self._coordinate_text(),
        )

    def Update(self):
        if getattr(self, "_destroyed", False):
            return
        self._live_tick += 1
        self._advance_bitmap_retention()
        if (
            self._bitmap_dirty
            and self._bitmap_pending_slot is None
            and self._live_tick % BITMAP_RENDER_INTERVAL_TICKS == 0
        ):
            self._render_biome_bitmap()
        if self._live_tick % 3:
            return
        try:
            playerId = clientApi.GetLocalPlayerId()
            position = CF.CreatePos(playerId).GetFootPos()
            rotation = CF.CreateRot(playerId).GetRot()
            if position:
                self._local_player_position_ready = True
                maze_map_logic.update_player_height(self._snapshot, position[1])
                self._snapshot["player"] = [
                    int(math.floor(position[0])),
                    int(math.floor(position[2])),
                ]
                self._update_player_marker()
            if rotation:
                self._set_player_direction(
                    self._player_control,
                    rotation[1],
                )
        except Exception:
            return

    def _close(self, args=None):
        clientApi.PopScreen()

    def Destroy(self):
        global _ACTIVE_UI
        if getattr(self, "_destroyed", False):
            return
        self._destroyed = True
        if _ACTIVE_UI is self:
            _ACTIVE_UI = None
        self._dynamic_controls = []
        # The engine owns native UI destruction; these handles may already
        # be invalid when Destroy is delivered. Do not call into them here.
        self._canvas = None
        self._biome_bitmap_controls = {
            "a": None,
            "b": None,
            "c": None,
        }
        self._bitmap_dirty = False
        self._bitmap_paths = {"a": "", "b": "", "c": ""}
        self._bitmap_latest_slot = None
        self._bitmap_next_slot_index = 0
        self._bitmap_pending_slot = None
        self._bitmap_retention_ticks = 0
        self._player_control = None
        self._other_player_controls = {}
