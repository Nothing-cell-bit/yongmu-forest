# -*- coding: utf-8 -*-
"""Pure progression and item contracts for the two post-Lich routes.

This module deliberately has no ModSDK imports so migration, restriction and
death-inventory semantics can be validated outside the game client.
"""


PROGRESS_VERSION = 3
PROGRESS_FIELDS = (
    "naga_defeated",
    "lich_defeated",
    "minoshroom_defeated",
    "meef_stroganoff_eaten",
    "hydra_defeated",
    "trophy_pedestal_activated",
    "knight_phantoms_defeated",
    "ghast_trap_activated",
    "ur_ghast_defeated",
)


def default_progress():
    result = dict((name, False) for name in PROGRESS_FIELDS)
    result["version"] = PROGRESS_VERSION
    return result


def migrate_progress(value):
    source = value if isinstance(value, dict) else {}
    result = default_progress()
    aliases = {
        "naga_defeated": ("naga_defeated", "tf_naga_defeated"),
        "lich_defeated": ("lich_defeated", "tf_lich_defeated"),
        "minoshroom_defeated": (
            "minoshroom_defeated",
            "tf_minoshroom_defeated",
        ),
        "meef_stroganoff_eaten": (
            "meef_stroganoff_eaten",
            "tf_meef_stroganoff_eaten",
        ),
        "hydra_defeated": ("hydra_defeated", "tf_hydra_defeated"),
        "trophy_pedestal_activated": (
            "trophy_pedestal_activated",
            "tf_trophy_pedestal_activated",
        ),
        "knight_phantoms_defeated": (
            "knight_phantoms_defeated",
            "tf_knight_phantoms_defeated",
        ),
        "ghast_trap_activated": (
            "ghast_trap_activated",
            "tf_ghast_trap_activated",
        ),
        "ur_ghast_defeated": (
            "ur_ghast_defeated",
            "tf_ur_ghast_defeated",
        ),
    }
    for target, names in aliases.items():
        result[target] = any(bool(source.get(name, False)) for name in names)
    return result


def can_enter_swamp(progress):
    return bool(migrate_progress(progress)["lich_defeated"])


def can_enter_fire_swamp(progress):
    migrated = migrate_progress(progress)
    return bool(
        migrated["lich_defeated"]
        and migrated["meef_stroganoff_eaten"]
    )


def can_enter_dark_forest(progress):
    """Dark Forest is the parallel post-Lich branch entrance."""
    return bool(migrate_progress(progress)["lich_defeated"])


def can_enter_knight_stronghold(progress):
    """The shielded stronghold interior opens only after its pedestal."""
    migrated = migrate_progress(progress)
    return bool(
        migrated["lich_defeated"]
        and migrated["trophy_pedestal_activated"]
    )


def can_enter_dark_forest_center(progress):
    migrated = migrate_progress(progress)
    # Restrictions.java binds the center directly to progress_knights. The
    # Lich prerequisite belongs to the outer Dark Forest route, not this
    # restriction's own advancement list.
    return bool(migrated["knight_phantoms_defeated"])


def can_enter_dark_tower(progress):
    return can_enter_dark_forest_center(progress)


def can_credit_ur_ghast(progress):
    """Trap activation is evidence/mechanics, never a death-credit gate."""
    return can_enter_dark_tower(progress)


def biome_penalty(biome_key, progress, current_hunger_amplifier=0):
    if biome_key == "swamp" and not can_enter_swamp(progress):
        return {
            "effect": "hunger",
            "duration": 100,
            "amplifier": max(0, int(current_hunger_amplifier)) + 1,
        }
    if biome_key == "fire_swamp" and not can_enter_fire_swamp(progress):
        return {"effect": "fire", "seconds": 8}
    if biome_key == "dark_forest" and not can_enter_dark_forest(progress):
        return {"effect": "darkness", "duration": 100, "amplifier": 0}
    if biome_key == "dark_forest_center" and not can_enter_dark_forest_center(
        progress
    ):
        return {"effect": "darkness", "duration": 100, "amplifier": 0}
    return None


def highest_keeping_charm(charm_counts):
    counts = charm_counts if isinstance(charm_counts, dict) else {}
    for tier in (3, 2, 1):
        if int(counts.get(tier, counts.get(str(tier), 0)) or 0) > 0:
            return tier
    return 0


def keeping_charm_snapshot(
    inventory,
    armor,
    offhand,
    selected_hotbar_slot,
    charm_counts,
):
    tier = highest_keeping_charm(charm_counts)
    if tier <= 0:
        return 0, None
    inventory = list(inventory or [])
    if tier == 1:
        selected = max(0, min(8, int(selected_hotbar_slot)))
        inventory_slots = [selected]
    elif tier == 2:
        inventory_slots = list(range(min(9, len(inventory))))
    else:
        inventory_slots = list(range(len(inventory)))
    return tier, {
        "version": 1,
        "tier": tier,
        "inventory_slots": inventory_slots,
        "inventory": dict(
            (slot, inventory[slot]) for slot in inventory_slots
        ),
        "armor": list(armor or []),
        "offhand": offhand,
        "restored": False,
    }


def should_consume_keeping_charm(
    tier,
    keep_inventory=False,
    creative=False,
    spectator=False,
):
    return bool(
        int(tier) > 0
        and not keep_inventory
        and not creative
        and not spectator
    )


def fire_react_chance(level):
    return 0.15 * max(0, min(3, int(level)))


def fire_react_seconds(level, random_roll):
    level = max(1, min(3, int(level)))
    roll = max(0, min(level - 1, int(random_roll)))
    return 2 + roll * 3


def can_apply_fire_react(enchantments):
    values = enchantments if isinstance(enchantments, dict) else {}
    return not bool(
        values.get("minecraft:thorns")
        or values.get("thorns")
        or values.get("twilightforest:chill_aura")
        or values.get("tf_slice:chill_aura")
    )
