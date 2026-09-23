# -*- coding: utf-8 -*-
"""Pure selection rules for the client-side custom boss HUDs."""


_SOURCE_BOSS_BAR_STYLES = {
    "naga": ((0.0, 1.0, 0.0), 10),
    "minoshroom": ((1.0, 0.0, 0.0), 0),
    "hydra": ((0.0, 0.35, 1.0), 0),
    "knight_phantoms": ((1.0, 1.0, 1.0), 0),
    "ur_ghast": ((1.0, 0.0, 0.0), 0),
}


def source_boss_bar_style(kind, phase=1):
    """Return the locked 1.20.1-4.3.2508 color and overlay contract."""
    kind = str(kind or "")
    try:
        phase = int(phase)
    except (TypeError, ValueError):
        phase = 1
    if kind == "lich":
        if phase <= 1:
            color, segments = (1.0, 1.0, 0.0), 6
        elif phase == 2:
            color, segments = (0.65, 0.0, 0.8), 0
        else:
            color, segments = (1.0, 0.0, 0.0), 0
    else:
        color, segments = _SOURCE_BOSS_BAR_STYLES.get(
            kind,
            ((1.0, 1.0, 1.0), 0),
        )
    return {"color": tuple(color), "segments": int(segments)}


def boss_bar_stack_slots(visible_groups):
    """Compact non-empty boss groups into vanilla-style vertical slots."""
    slots = {}
    slot = 0
    for kind, bosses in visible_groups or ():
        if not bosses:
            continue
        slots[str(kind)] = slot
        slot += 1
    return slots


def progress_clip_ratio(progress):
    """Translate visible progress into ModSDK's inverse clipped fraction."""
    try:
        progress = float(progress)
    except (TypeError, ValueError):
        progress = 0.0
    progress = max(0.0, min(1.0, progress))
    return 1.0 - progress


def precise_fill_width(progress, width=182.0):
    """Return geometry width for a non-quantized boss-bar fill mask."""
    try:
        progress = float(progress)
    except (TypeError, ValueError):
        progress = 0.0
    try:
        width = max(0.0, float(width))
    except (TypeError, ValueError):
        width = 182.0
    return width * max(0.0, min(1.0, progress))


def _position(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return tuple(float(value[index]) for index in range(3))
    except (TypeError, ValueError):
        return None


def server_visibility_decision(
    boss_position,
    boss_dimension,
    viewer_position,
    viewer_dimension,
    max_distance,
):
    """Return ``(visible, distance_squared)`` for a player-specific packet.

    ``visible`` is deliberately tri-state.  ``None`` means the server could
    not obtain enough viewer context and the client must use the synced boss
    position as a fallback.  A known dimension mismatch remains an explicit
    ``False`` so a transient position failure cannot leak a cross-dimension
    boss bar.
    """
    try:
        boss_dimension = int(boss_dimension)
        viewer_dimension = int(viewer_dimension)
    except (TypeError, ValueError):
        return None, None
    if boss_dimension != viewer_dimension:
        return False, None

    boss = _position(boss_position)
    viewer = _position(viewer_position)
    try:
        range_squared = max(0.0, float(max_distance)) ** 2
    except (TypeError, ValueError):
        return None, None
    if boss is None or viewer is None:
        return None, None

    distance_squared = sum(
        (boss[index] - viewer[index]) ** 2 for index in range(3)
    )
    return distance_squared <= range_squared, distance_squared


def visible_bosses(
    bosses,
    kind,
    current_dimension,
    player_position,
    max_distance,
):
    """Return visible bosses nearest-first.

    New sync packets contain a server-authoritative ``hudVisible`` decision
    for the receiving player.  That decision must not depend on client actor
    lookup because NetEase clients do not always expose server entity ids to
    ``CreatePos``.  Packets from older servers still use the local position
    calculation below.
    """
    viewer = _position(player_position)
    try:
        range_squared = max(0.0, float(max_distance)) ** 2
    except (TypeError, ValueError):
        range_squared = None

    candidates = []
    for boss in bosses or ():
        if not isinstance(boss, dict):
            continue
        if str(boss.get("kind", "")) != str(kind):
            continue
        if str(kind) == "knight_phantoms":
            try:
                health = float(boss.get("health", 0.0))
                members_alive = int(boss.get("membersAlive", 0))
            except (TypeError, ValueError):
                continue
            if health <= 0.0 or members_alive <= 0:
                continue
        server_visible = boss.get("hudVisible")
        if server_visible is not None:
            if not bool(server_visible):
                continue
            try:
                distance_squared = float(
                    boss.get("hudDistanceSquared", float("inf"))
                )
            except (TypeError, ValueError):
                distance_squared = float("inf")
            candidates.append(
                (distance_squared, str(boss.get("id", "")), boss)
            )
            continue
        if (
            current_dimension is None
            or viewer is None
            or range_squared is None
        ):
            continue
        if boss.get("dimensionId") != current_dimension:
            continue
        position = _position(boss.get("position"))
        if position is None:
            continue
        distance_squared = sum(
            (position[index] - viewer[index]) ** 2
            for index in range(3)
        )
        if distance_squared <= range_squared:
            candidates.append(
                (distance_squared, str(boss.get("id", "")), boss)
            )
    candidates.sort(key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in candidates]
