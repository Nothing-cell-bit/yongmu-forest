"""Exercise the server click handler with the actual registered trophy items."""

import json
import math
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace

import pytest


BP = Path(__file__).resolve().parents[1] / "TwilightBossSliceB"
PACKAGE = BP / "TwilightBossSlice"
sys.path.insert(0, str(PACKAGE))

import knight_route_logic
import portal_logic
import public_block_logic


def server_handler(name):
    source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
    start = source.index("    def " + name + "(")
    end = source.index("\n    def ", start + 1)
    namespace = {
        "knight_route_logic": knight_route_logic,
        "portal_logic": portal_logic,
        "public_block_logic": public_block_logic,
        "math": math,
        "config": SimpleNamespace(DIMENSION_ID=7),
    }
    exec(textwrap.dedent(source[start:end]), namespace)
    return namespace[name]


@pytest.mark.parametrize("variant", public_block_logic.TROPHY_VARIANTS)
@pytest.mark.parametrize("legacy", [False, True])
def test_trophy_click_opens_gate_and_grants_progress(variant, legacy):
    document = json.loads(
        (BP / "items" / (variant + "_trophy.item.json")).read_text(encoding="utf-8")
    )["minecraft:item"]
    item_name = document["description"]["identifier"]
    if legacy:
        item_name = document["components"]["minecraft:block_placer"]["block"]
    opened = []
    credited = []
    server = SimpleNamespace(
        _ruin_worldgen=SimpleNamespace(
            activate_trophy_pedestal=lambda position: opened.append(position) or True
        ),
        _get_online_players=lambda: ["builder"],
        _get_foot_pos=lambda player: (10, 65, 10),
        _get_dimension=lambda player: 7,
        _route_progress_value=lambda player: {},
        _is_creative=lambda player: True,
        _grant_progress=lambda player, objective: credited.append((player, objective)),
    )
    activate = server_handler("_activate_stronghold_pedestal_at")
    server._activate_stronghold_pedestal_at = lambda *args: activate(server, *args)
    args = {
        "blockName": "tf_slice:trophy_pedestal",
        "playerId": "builder",
        "itemDict": {"newItemName": item_name, "count": 1},
        "x": 10,
        "y": 64,
        "z": 10,
    }

    assert server_handler("_activate_stronghold_pedestal")(server, args)
    assert args["ret"] is True
    assert opened == [(10, 64, 10)]
    assert credited == [("builder", "tf_trophy_pedestal_activated")]
    assert args["itemDict"]["count"] == 1


def test_unrelated_item_does_not_activate_pedestal():
    server = SimpleNamespace(_ruin_worldgen=object())
    args = {
        "blockName": "tf_slice:trophy_pedestal",
        "itemDict": {"newItemName": "minecraft:stone"},
    }
    assert server_handler("_activate_stronghold_pedestal")(server, args) is False
    assert "cancel" not in args
