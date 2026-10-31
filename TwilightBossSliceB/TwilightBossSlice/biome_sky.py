# -*- coding: utf-8 -*-
"""Dimension-local star palettes matching each biome's air environment color.

The builder and regression contract check these against the resource fogs.
Unknown/unloaded biomes return None so a transient chunk miss keeps the last sky.
"""
from TwilightBossSlice.biome_catalog import BIOMES_BY_IDENTIFIER

DEFAULT_COLOR = '#20224A'
ENVIRONMENT_COLORS = {
    'dm33027004_swampland': '#003F21',
    'dm33027004_swampland_mutated': '#380A00',
    'dm33027004_roofed_forest': '#AAA0C8',
    'dm33027004_birch_forest_mutated': '#C0FFD8',
    'dm33027004_roofed_forest_mutated': '#000000',
    'dm33027004_redwood_taiga_mutated': '#493000',
}
FACE_NAMES = ('negative_z', 'positive_x', 'positive_z',
              'negative_x', 'positive_y', 'negative_y')
STAR_TEXTURES = ['textures/environment/twilight_stars_alpha/' + name
                 for name in FACE_NAMES]


def rgba_from_textures(textures):
    """Decode the logical palette key; these paths need not be loaded."""
    color = color_from_textures(textures)
    if color is None:
        raise ValueError('Unknown sky palette')
    return tuple(int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)) + (1.0,)


def color_for_biome(identifier):
    identifier = str(identifier).split(':')[-1]
    if identifier not in BIOMES_BY_IDENTIFIER:
        return None
    return ENVIRONMENT_COLORS.get(identifier, DEFAULT_COLOR)


def textures_for_color(color):
    if color == DEFAULT_COLOR:
        directory = 'textures/environment/twilight_sky_small'
    else:
        directory = 'textures/environment/twilight_sky_biomes/' + color[1:].lower()
    return [directory + '/' + name for name in FACE_NAMES]


def textures_for_biome(identifier):
    color = color_for_biome(identifier)
    return textures_for_color(color) if color is not None else None


def color_from_textures(textures):
    if not textures or len(textures) != 6:
        return None
    if list(textures) == textures_for_color(DEFAULT_COLOR):
        return DEFAULT_COLOR
    prefix = 'textures/environment/twilight_sky_biomes/'
    if not textures[0].startswith(prefix):
        return None
    color = '#' + textures[0][len(prefix):].split('/')[0].upper()
    if len(color) != 7 or any(c not in '0123456789ABCDEF' for c in color[1:]):
        return None
    return color if list(textures) == textures_for_color(color) else None


def transition_colors(start, end):
    # Use one canonical path in either direction, including rounding. All
    # channels change by at most eight byte levels per displayed step.
    if start == end:
        return [start]
    left, right = sorted((start, end))
    a = [int(left[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(right[i:i + 2], 16) for i in (1, 3, 5)]
    # Every pair takes about two seconds (32 steps at 15 Hz), including the
    # subtle forest/swamp change. A distance-only count would finish that
    # common boundary in six steps and still look like a quick color jump.
    count = 32
    colors = ['#' + ''.join('%02X' % ((x * (count - step) + y * step + count // 2) // count)
                           for x, y in zip(a, b)) for step in range(count + 1)]
    return colors if start == left else list(reversed(colors))


class SkyTransition(object):
    """Acknowledged small palette steps, two-sample border debounce.

    No timer or native API runs here. The guarded 30 Hz client tick proposes
    a step at most every two ticks, and commits only after native readback.
    A third destination finishes to the nearer endpoint before a new path;
    it never snaps back to the old biome's full color.
    """
    def __init__(self, textures):
        self.base = color_from_textures(textures)
        if self.base is None:
            raise ValueError('Unknown initial sky palette')
        self.reset()

    def reset(self):
        self.current = None
        self.goal = self.base
        self.candidate = None
        self.samples = 0
        self.path = None
        self.index = 0
        self.pending = None
        self.pending_index = 0
        self.cooldown = 0

    def set_target(self, textures):
        color = color_from_textures(textures)
        endpoints = set(ENVIRONMENT_COLORS.values()) | set([DEFAULT_COLOR])
        if color not in endpoints:
            return
        if self.candidate == color:
            self.samples = min(2, self.samples + 1)
        else:
            self.candidate, self.samples = color, 1
        if self.samples >= 2:
            if color != self.goal:
                self.pending = None
            self.goal = color

    def miss_target(self):
        if self.current is None:
            self.candidate = None
            self.samples = 0
            self.pending = None

    def next_textures(self):
        if self.pending is not None:
            return textures_for_color(self.pending)
        if self.current is None:
            if self.samples < 2:
                return None
            self.pending = self.goal
            return textures_for_color(self.pending)
        if self.cooldown:
            self.cooldown -= 1
            return textures_for_color(self.current)
        if self.goal == self.current:
            self.path = None
            return textures_for_color(self.current)
        if self.path is None or self.index in (0, len(self.path) - 1):
            self.path = transition_colors(self.current, self.goal)
            self.index = 0
        if self.goal == self.path[0]:
            direction = -1
        elif self.goal == self.path[-1]:
            direction = 1
        else:
            direction = -1 if self.index <= (len(self.path) - 1) / 2.0 else 1
        self.pending_index = self.index + direction
        self.pending = self.path[self.pending_index]
        return textures_for_color(self.pending)

    def applied(self, textures):
        color = color_from_textures(textures)
        if self.pending is not None and color == self.pending:
            self.current = self.pending
            self.index = self.pending_index
            self.pending = None
            self.cooldown = 1
