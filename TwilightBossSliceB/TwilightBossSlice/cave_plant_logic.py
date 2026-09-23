# -*- coding: utf-8 -*-
"""Pure cave-plant interaction decisions shared by runtime and tests."""


RIPE_TORCHBERRY_PLANT = "tf_slice:torchberry_plant"
EMPTY_TORCHBERRY_PLANT = "tf_slice:torchberry_plant_empty"


def torchberry_harvest(block_name):
    if block_name != RIPE_TORCHBERRY_PLANT:
        return None
    return {
        "replacement": EMPTY_TORCHBERRY_PLANT,
        "item": {
            "newItemName": "tf_slice:torchberries",
            "newAuxValue": 0,
            "count": 1,
        },
    }
