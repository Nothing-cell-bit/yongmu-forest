# -*- coding: utf-8 -*-
"""Pure source-locked rules shared by Twilight Forest spider variants."""

from __future__ import absolute_import


KING_SPIDER = "tf_slice:king_spider"
HEDGE_SPIDER = "tf_slice:hedge_spider"
SWARM_SPIDER = "tf_slice:swarm_spider"
TOWER_BROODLING = "tf_slice:tower_broodling"

SWARM_ATTACK_TYPES = frozenset((SWARM_SPIDER, TOWER_BROODLING))


def swarm_attack_is_allowed(entity_type, random_roll):
    """SwarmSpider.doHurtTarget succeeds only when nextInt(4) is zero."""
    if str(entity_type) not in SWARM_ATTACK_TYPES:
        return True
    return int(random_roll) % 4 == 0


def druid_jockey_is_allowed(entity_type, difficulty_id, random_roll):
    """Return whether this spider spawn receives a Skeleton Druid rider."""
    entity_type = str(entity_type)
    if entity_type == KING_SPIDER:
        return True
    if entity_type != SWARM_SPIDER:
        return False
    return int(random_roll) % 20 <= max(0, int(difficulty_id))


def druid_jockey_is_baby(entity_type):
    """Only the SwarmSpider jockey explicitly calls setBaby(true)."""
    return str(entity_type) == SWARM_SPIDER
