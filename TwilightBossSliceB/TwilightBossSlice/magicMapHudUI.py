# -*- coding: utf-8 -*-
import math
import client.extraClientApi as clientApi
import TwilightBossSlice.magic_map_bitmap_cache as magic_map_bitmap_cache
import TwilightBossSlice.magic_map_logic as magic_map_logic
import TwilightBossSlice.maze_map_logic as maze_map_logic


ScreenNode = clientApi.GetScreenNodeCls()
CustomUIScreenProxy = clientApi.GetUIScreenProxyCls()
ViewBinder = clientApi.GetViewBinderCls()
CF = clientApi.GetEngineCompFactory()
_PENDING_SNAPSHOT = {}
_ACTIVE_UI = None
_HELD_VISIBLE = False
NATIVE_HUD_CONTENT_PATH = "/variables_button_mappings_and_controls"
NATIVE_HUD_BIND_DELAY_TICKS = 10
NATIVE_HUD_MAGIC_MAP_PATH = (
    "/variables_button_mappings_and_controls/safezone_screen_matrix/"
    "inner_matrix/safezone_screen_panel/root_screen_panel/tf_magic_map"
)
# Reuse native-HUD controls that already exist in the JSON definition.  Adding
# a forced-update child here triggers a complete HUD layout on this engine,
# once per biome rectangle, and can stall the client for many seconds.
BITMAP_RENDER_INTERVAL_TICKS = 6
BITMAP_RETENTION_TICKS = 120
BITMAP_BUFFER_SLOTS = ("a", "b", "c")
LANDMARK_POOL_SIZE = 128
CONQUERED_POOL_SIZE = 64
OTHER_PLAYER_POOL_SIZE = 64

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
LOCAL_PLAYER_ARROW_COLOR = (1.0, 1.0, 1.0)
OTHER_PLAYER_COLOR = (1.0, 1.0, 1.0)

BIOME_KEYS = magic_map_logic.TWILIGHT_BIOME_KEYS


def set_snapshot(snapshot):
    global _PENDING_SNAPSHOT, _ACTIVE_UI
    magic_map_bitmap_cache.trace_maze_snapshot("hud_snapshot", snapshot)
    _PENDING_SNAPSHOT = dict(snapshot or {})
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.ApplySnapshot(_PENDING_SNAPSHOT)


def apply_delta(delta):
    global _ACTIVE_UI, _PENDING_SNAPSHOT
    if not isinstance(delta, dict):
        return
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.ApplyDelta(delta)
        return
    _PENDING_SNAPSHOT = magic_map_logic.merge_map_delta(
        _PENDING_SNAPSHOT,
        delta,
    )


def set_held_visible(visible):
    global _HELD_VISIBLE, _ACTIVE_UI
    _HELD_VISIBLE = bool(visible)
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.SetHeldVisible(_HELD_VISIBLE)


def is_active():
    return _ACTIVE_UI is not None


class MagicMapHudRenderer(object):
    """Original-style biome magic map shown whenever the item is held."""

    def __init__(
        self,
        host,
        root_control_paths,
        discover_paths=False,
        bind_delay_ticks=0,
    ):
        self._host = host
        self._root_control_paths = tuple(root_control_paths)
        self._discover_paths = bool(discover_paths)
        try:
            self._bind_delay_ticks = max(0, int(bind_delay_ticks))
        except (TypeError, ValueError):
            self._bind_delay_ticks = 0
        self._snapshot = dict(_PENDING_SNAPSHOT)
        self._root = None
        self._root_path = None
        self._canvas = None
        self._canvas_size = (0.0, 0.0)
        self._biome_bitmap_controls = {
            "a": None,
            "b": None,
            "c": None,
        }
        self._landmark_pool = []
        self._conquered_pool = []
        self._other_player_pool = []
        self._cells = {}
        self._bitmap_dirty = False
        self._bitmap_paths = {"a": "", "b": "", "c": ""}
        self._bitmap_latest_slot = None
        self._bitmap_next_slot_index = 0
        self._bitmap_pending_slot = None
        self._bitmap_retention_ticks = 0
        self._landmark_keys = set()
        self._conquered_keys = set()
        self._landmark_count = 0
        self._conquered_count = 0
        self._other_player_count = 0
        self._landmark_signature = None
        self._other_player_signature = None
        self._player_backdrop_control = None
        self._player_control = None
        self._player_marker_state = "inside"
        self._player_marker_position = None
        self._player_direction = None
        self._local_player_position_ready = False
        self._root_visible = None
        self._tick = 0
        self._bind_retry_tick = 0

    def GetBaseUIControl(self, path):
        return self._host.GetBaseUIControl(path)

    def GetAllChildrenPath(self, parent_path):
        return self._host.GetAllChildrenPath(parent_path)

    def Init(self):
        global _ACTIVE_UI
        if getattr(self, "_destroyed", False):
            return
        _ACTIVE_UI = self
        if self._bind_delay_ticks <= 0:
            self._bind_controls()
            self.SetHeldVisible(_HELD_VISIBLE)
        print (
            "[TF_MAGIC_MAP_DIAG] event=hud_create "
            "root=%r canvas=%r held=%r"
            % (
                self._root is not None,
                self._canvas is not None,
                _HELD_VISIBLE,
            )
        )

    def _bind_root_path(self, root_path):
        try:
            root = self.GetBaseUIControl(root_path)
            canvas = self.GetBaseUIControl(
                root_path + "/parchment_frame/map_canvas"
            )
        except Exception:
            return False
        if root is None or canvas is None:
            return False
        self._root = root
        self._root_path = root_path
        self._canvas = canvas
        if not self._bind_pool_controls(root_path):
            self._root = None
            self._root_path = None
            self._canvas = None
            return False
        return True

    def _bind_pool_controls(self, root_path):
        canvas_path = root_path + "/parchment_frame/map_canvas"
        landmark_path = canvas_path + "/landmark_pool"
        conquered_path = canvas_path + "/conquered_pool"
        other_player_path = canvas_path + "/other_player_pool"
        try:
            biome_bitmap_controls = {
                "a": self.GetBaseUIControl(
                    canvas_path + "/biome_bitmap_a"
                ),
                "b": self.GetBaseUIControl(
                    canvas_path + "/biome_bitmap_b"
                ),
                "c": self.GetBaseUIControl(
                    canvas_path + "/biome_bitmap_c"
                ),
            }
            landmark_pool = [
                self.GetBaseUIControl(
                    landmark_path + "/landmark_slot_%03d" % index
                )
                for index in range(LANDMARK_POOL_SIZE)
            ]
            conquered_pool = [
                self.GetBaseUIControl(
                    conquered_path + "/conquered_slot_%03d" % index
                )
                for index in range(CONQUERED_POOL_SIZE)
            ]
            other_player_pool = [
                self.GetBaseUIControl(
                    other_player_path + "/other_player_slot_%03d" % index
                )
                for index in range(OTHER_PLAYER_POOL_SIZE)
            ]
            player_backdrop_control = self.GetBaseUIControl(
                canvas_path
                + "/player_pool/held_player_marker_backdrop"
            )
            player_control = self.GetBaseUIControl(
                canvas_path + "/player_pool/held_player_marker"
            )
        except Exception:
            return False
        if (
            any(
                control is None
                for control in biome_bitmap_controls.values()
            )
            or any(control is None for control in landmark_pool)
            or any(control is None for control in conquered_pool)
            or any(control is None for control in other_player_pool)
            or player_backdrop_control is None
            or player_control is None
        ):
            return False
        self._biome_bitmap_controls = biome_bitmap_controls
        for control in self._biome_bitmap_controls.values():
            control.SetVisible(True)
            control.SetAlpha(0.0)
        self._landmark_pool = landmark_pool
        self._conquered_pool = conquered_pool
        self._other_player_pool = other_player_pool
        self._player_backdrop_control = player_backdrop_control
        self._player_control = player_control
        return True

    def _bind_controls(self):
        if self._root is None or self._canvas is None:
            root_control_paths = list(self._root_control_paths)
            for root_path in root_control_paths:
                if self._bind_root_path(root_path):
                    break
            if self._root is None and self._discover_paths:
                try:
                    children = self.GetAllChildrenPath(
                        NATIVE_HUD_CONTENT_PATH
                    )
                except Exception:
                    children = ()
                for path in children or ():
                    path = str(path)
                    if (
                        path.endswith("/tf_magic_map")
                        and path not in root_control_paths
                    ):
                        root_control_paths.append(path)
                        if self._bind_root_path(path):
                            break
        if self._canvas is not None:
            canvas_size = self._canvas.GetSize()
            if (
                self._canvas_size == (0.0, 0.0)
                and canvas_size
                and len(canvas_size) == 2
            ):
                self._canvas_size = magic_map_logic.resolve_canvas_size(
                    canvas_size,
                    self._snapshot.get(
                        "gridSize",
                        magic_map_logic.MAP_GRID_SIZE,
                    ),
                )
                self._draw_biomes(self._canvas)
                self._draw_landmarks(self._canvas)
                self._draw_shared_players(self._canvas)
                self._draw_player(self._canvas)

    def _clean_cells(self, snapshot=None):
        if snapshot is None:
            snapshot = self._snapshot
        try:
            grid_size = int(snapshot.get("gridSize", 0))
        except (TypeError, ValueError):
            return 0, {}
        if grid_size <= 0 or grid_size > 128:
            return grid_size, {}
        cells = {}
        for run in snapshot.get("biomeRuns", ()):
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
        for entry in snapshot.get("biomeCells", ()):
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
        del canvas
        if grid_size <= 0:
            return
        self._bitmap_dirty = True
        if prefix != "delta":
            self._render_biome_bitmap()

    def _render_biome_bitmap(self):
        magic_map_bitmap_cache.trace_maze_snapshot(
            "hud_render", self._snapshot, cellCount=len(self._cells),
            missingControls=any(control is None for control in self._biome_bitmap_controls.values()),
        )
        if self._bitmap_pending_slot is not None or not self._bitmap_dirty:
            return
        if any(
            control is None
            for control in self._biome_bitmap_controls.values()
        ):
            return
        if not self._cells:
            for control in self._biome_bitmap_controls.values():
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
        self._bitmap_paths[pending_slot] = path
        pending_control = self._biome_bitmap_controls[pending_slot]
        pending_control.SetVisible(True)
        # RawPath loading is asynchronous and fully transparent controls may
        # be culled by the engine.  Keep the new full-map image renderable and
        # retain every older slot as an opaque fallback.  Discovered map cells
        # are immutable, so overlapping full snapshots compose exactly.
        pending_control.SetAlpha(1.0)
        self._bitmap_latest_slot = pending_slot
        self._bitmap_pending_slot = pending_slot
        self._bitmap_retention_ticks = BITMAP_RETENTION_TICKS
        self._bitmap_dirty = False

    def _advance_bitmap_retention(self):
        if self._bitmap_pending_slot is None:
            return
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
        return self._bitmap_paths.get(slot, "") or ""

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
        del canvas
        signature = repr(self._snapshot.get("landmarks", ()))
        if signature == self._landmark_signature:
            return
        self._hide_controls(self._landmark_pool[:self._landmark_count])
        self._hide_controls(self._conquered_pool[:self._conquered_count])
        self._landmark_keys = set()
        self._conquered_keys = set()
        marker_slot = 0
        conquered_slot = 0
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
            if marker_slot >= len(self._landmark_pool):
                continue
            control = self._landmark_pool[marker_slot]
            marker_slot += 1
            image = control.asImage()
            if image is not None:
                image.SetSprite(icon)
            control.SetPosition((pixel[0] - 4, pixel[1] - 4))
            control.SetSize((8, 8))
            control.SetVisible(True)
            if marker_key:
                self._landmark_keys.add(marker_key)
            if (
                bool(landmark.get("conquered", False))
                and conquered_slot < len(self._conquered_pool)
            ):
                conquered = self._conquered_pool[conquered_slot]
                conquered_slot += 1
                conquered.SetPosition((pixel[0] - 4, pixel[1] - 4))
                conquered.SetVisible(True)
                if marker_key:
                    self._conquered_keys.add(marker_key)
        self._landmark_count = marker_slot
        self._conquered_count = conquered_slot
        self._landmark_signature = signature

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
        del canvas, marker_index
        if len(self._conquered_keys) >= len(self._conquered_pool):
            return
        conquered = self._conquered_pool[len(self._conquered_keys)]
        conquered.SetPosition((pixel[0] - 4, pixel[1] - 4))
        conquered.SetVisible(True)
        self._conquered_count = max(
            self._conquered_count,
            len(self._conquered_keys) + 1,
        )
        if marker_key:
            self._conquered_keys.add(marker_key)

    def _draw_player(self, canvas):
        del canvas
        player = self._snapshot.get("player", ())
        if not player or len(player) != 2:
            return
        pixel = self._player_map_position(player[0], player[1])
        if pixel is None:
            return
        control = self._player_control
        if control is not None:
            self._player_marker_state = pixel[2]
            self._set_player_position(control, pixel)
            self._set_player_direction(control, 0.0)

    def _draw_shared_players(self, canvas):
        del canvas
        players = self._snapshot.get("players", ())
        signature = repr(players)
        if signature == self._other_player_signature:
            return
        self._hide_controls(
            self._other_player_pool[:self._other_player_count]
        )
        marker_slot = 0
        for player in players:
            if marker_slot >= len(self._other_player_pool):
                break
            if not isinstance(player, dict):
                continue
            position = player.get("position")
            if not position or len(position) != 2:
                continue
            pixel = self._player_map_position(position[0], position[1])
            direction = magic_map_logic.player_marker_direction(
                player.get("yaw", 0.0),
                pixel[2] if pixel is not None else "off_limits",
            )
            if pixel is None or direction is None:
                continue
            control = self._other_player_pool[marker_slot]
            marker_slot += 1
            image = control.asImage()
            if image is not None:
                image.SetSprite(PLAYER_MARKER_TEXTURE_PATHS[direction])
                image.SetSpriteColor(OTHER_PLAYER_COLOR)
            control.SetPosition((pixel[0] - 3, pixel[1] - 3))
            control.SetVisible(True)
        self._other_player_count = marker_slot
        self._other_player_signature = signature

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
            image.SetSpriteColor(LOCAL_PLAYER_ARROW_COLOR)
            self._player_direction = direction

    def _set_player_position(self, control, pixel):
        position = (pixel[0] - 4, pixel[1] - 4)
        backdrop_position = (pixel[0] - 2, pixel[1] - 2)
        visible = True
        render_state = (position, backdrop_position, visible)
        if render_state == self._player_marker_position:
            return
        control.SetPosition(position)
        control.SetVisible(visible)
        backdrop = self._player_backdrop_control
        if backdrop is not None:
            backdrop.SetPosition(backdrop_position)
            backdrop.SetVisible(visible)
        self._player_marker_position = render_state

    def _hide_controls(self, controls):
        for control in controls:
            try:
                control.SetVisible(False)
            except Exception:
                pass

    def _hide_dynamic_controls(self):
        for control in self._biome_bitmap_controls.values():
            if control is not None:
                control.SetAlpha(0.0)
                control.SetVisible(False)
        self._hide_controls(self._landmark_pool[:self._landmark_count])
        self._hide_controls(self._conquered_pool[:self._conquered_count])
        self._hide_controls(
            self._other_player_pool[:self._other_player_count]
        )
        if self._player_control is not None:
            self._player_control.SetVisible(False)
        if self._player_backdrop_control is not None:
            self._player_backdrop_control.SetVisible(False)
        self._cells = {}
        self._bitmap_dirty = False
        self._bitmap_paths = {"a": "", "b": "", "c": ""}
        self._bitmap_latest_slot = None
        self._bitmap_next_slot_index = 0
        self._bitmap_pending_slot = None
        self._bitmap_retention_ticks = 0
        self._landmark_keys = set()
        self._conquered_keys = set()
        self._landmark_count = 0
        self._conquered_count = 0
        self._other_player_count = 0
        self._landmark_signature = None
        self._other_player_signature = None
        self._player_marker_position = None
        self._player_direction = None

    def ApplySnapshot(self, snapshot):
        if getattr(self, "_destroyed", False):
            return
        if not isinstance(snapshot, dict):
            return
        current_id = self._snapshot.get("mapId")
        next_id = snapshot.get("mapId", current_id)
        if current_id is not None and next_id != current_id:
            self._hide_dynamic_controls()
            self._snapshot = dict(snapshot)
            if self._canvas is not None:
                self._draw_biomes(self._canvas)
                self._draw_landmarks(self._canvas)
                self._draw_shared_players(self._canvas)
                self._draw_player(self._canvas)
            return
        self._snapshot.update(snapshot)
        grid_size, cells = self._clean_cells(self._snapshot)
        cells_changed = cells != self._cells
        if cells_changed:
            self._cells = dict(cells)
        if self._canvas is not None:
            if cells_changed:
                self._draw_cell_dict(
                    self._canvas,
                    grid_size,
                    self._cells,
                    "snapshot",
                )
            self._draw_landmarks(self._canvas)
            self._draw_shared_players(self._canvas)
        self._update_player_marker()

    def ApplyDelta(self, delta):
        if getattr(self, "_destroyed", False):
            return
        if not isinstance(delta, dict):
            return
        if delta.get("mapId") != self._snapshot.get("mapId"):
            return
        partial = dict(self._snapshot)
        partial["biomeRuns"] = delta.get("biomeRuns", ())
        partial["biomeCells"] = delta.get("biomeCells", ())
        grid_size, additions = self._clean_cells(partial)
        changed_cells = {}
        for index, biome_key in additions.items():
            if self._cells.get(index) != biome_key:
                changed_cells[index] = biome_key
        if changed_cells:
            self._cells.update(changed_cells)
        if not self._local_player_position_ready:
            self._snapshot["player"] = delta.get(
                "player",
                self._snapshot.get("player"),
            )
        self._snapshot["players"] = delta.get(
            "players",
            self._snapshot.get("players", ()),
        )
        if "landmarks" in delta:
            self._snapshot["landmarks"] = delta.get("landmarks")
        if changed_cells:
            self._draw_cell_dict(
                self._canvas,
                grid_size,
                self._cells,
                "delta",
            )
        if self._canvas is not None:
            if "landmarks" in delta:
                self._draw_landmarks(self._canvas)
            self._draw_shared_players(self._canvas)
        self._update_player_marker()

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
            self._set_player_position(self._player_control, pixel)

    def SetHeldVisible(self, visible):
        if getattr(self, "_destroyed", False):
            return
        visible = bool(visible)
        if self._root is not None and visible != self._root_visible:
            self._root.SetVisible(visible)
            self._root_visible = visible

    def Update(self):
        if getattr(self, "_destroyed", False):
            return
        self._tick += 1
        if self._root is None or self._canvas is None:
            if self._tick < self._bind_delay_ticks:
                return
            self._bind_retry_tick += 1
            if (
                self._bind_retry_tick == 1
                or self._bind_retry_tick % 20 == 0
            ):
                self._bind_controls()
            self.SetHeldVisible(_HELD_VISIBLE)
            if self._root is None or self._canvas is None:
                return
        if self._root_visible is False:
            return
        self._advance_bitmap_retention()
        if (
            self._bitmap_dirty
            and self._bitmap_pending_slot is None
            and self._tick % BITMAP_RENDER_INTERVAL_TICKS == 0
        ):
            self._render_biome_bitmap()
        if self._tick % 3:
            return
        try:
            player_id = clientApi.GetLocalPlayerId()
            position = CF.CreatePos(player_id).GetFootPos()
            rotation = CF.CreateRot(player_id).GetRot()
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

    def Destroy(self):
        global _ACTIVE_UI, _PENDING_SNAPSHOT
        if getattr(self, "_destroyed", False):
            return
        self._destroyed = True
        if _ACTIVE_UI is self:
            _ACTIVE_UI = None
            pending = dict(self._snapshot)
            pending["gridSize"] = magic_map_logic.MAP_GRID_SIZE
            pending["biomeRuns"] = magic_map_logic.biome_row_runs(self._cells)
            pending.pop("biomeCells", None)
            _PENDING_SNAPSHOT = pending
        print("[TF_MAGIC_MAP_DIAG] event=hud_destroy")
        # OnDestroy may follow native screen destruction. Drop Python handles;
        # visibility/alpha writes here can enter an already destroyed UI tree.
        self._root = None
        self._root_path = None
        self._canvas = None
        self._host = None
        self._biome_bitmap_controls = {
            "a": None,
            "b": None,
            "c": None,
        }
        self._bitmap_paths = {"a": "", "b": "", "c": ""}
        self._bitmap_dirty = False
        self._bitmap_latest_slot = None
        self._bitmap_pending_slot = None
        self._bitmap_retention_ticks = 0
        self._landmark_pool = []
        self._conquered_pool = []
        self._other_player_pool = []
        self._player_control = None
        self._player_backdrop_control = None
        self._cells = {}


class MagicMapHudUI(ScreenNode):
    """Fallback HUD screen for clients without native-screen proxies."""

    def __init__(self, namespace, name, param):
        super(MagicMapHudUI, self).__init__(namespace, name, param)
        self._renderer = MagicMapHudRenderer(
            self,
            ("/held_map_root",),
        )

    def Create(self):
        self.Init()

    def Init(self):
        self._renderer.Init()

    def Update(self):
        self._renderer.Update()

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_a",
    )
    def GetBitmapPathA(self):
        return self._renderer.GetBitmapPath("a")

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_b",
    )
    def GetBitmapPathB(self):
        return self._renderer.GetBitmapPath("b")

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_c",
    )
    def GetBitmapPathC(self):
        return self._renderer.GetBitmapPath("c")

    def Destroy(self):
        self._renderer.Destroy()


class MagicMapHudProxy(CustomUIScreenProxy):
    """Binds the original-style map canvas directly into hud.hud_screen."""

    def __init__(self, screenName, screenNode):
        super(MagicMapHudProxy, self).__init__(screenName, screenNode)
        self._renderer = MagicMapHudRenderer(
            self,
            (
                NATIVE_HUD_MAGIC_MAP_PATH,
            ),
            discover_paths=True,
            bind_delay_ticks=NATIVE_HUD_BIND_DELAY_TICKS,
        )

    def GetBaseUIControl(self, path):
        return self.GetScreenNode().GetBaseUIControl(path)

    def GetAllChildrenPath(self, parent_path):
        return self.GetScreenNode().GetAllChildrenPath(parent_path)

    def OnCreate(self):
        self._renderer.Init()

    def OnTick(self):
        self._renderer.Update()

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_a",
    )
    def GetBitmapPathA(self):
        return self._renderer.GetBitmapPath("a")

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_b",
    )
    def GetBitmapPathB(self):
        return self._renderer.GetBitmapPath("b")

    @ViewBinder.binding(
        ViewBinder.BF_BindString,
        "#tf_magic_map_bitmap_path_c",
    )
    def GetBitmapPathC(self):
        return self._renderer.GetBitmapPath("c")

    def OnDestroy(self):
        self._renderer.Destroy()
