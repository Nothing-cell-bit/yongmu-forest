"""Pure locked-source rules for Twilight Forest mosquito swarms."""


MOSQUITO_SWARM_IDENTIFIER = "tf_slice:mosquito_swarm"


def hunger_seconds(difficulty):
    """Match MosquitoSwarm#doHurtTarget from 1.20.1-4.3.2508."""
    try:
        difficulty = int(difficulty)
    except (TypeError, ValueError):
        difficulty = 2
    if difficulty == 1:
        return 7
    if difficulty == 3:
        return 30
    return 15


def should_apply_hunger(attacker_type, damage):
    """Only a successfully settled mosquito melee hit carries Hunger I."""
    try:
        damage = float(damage)
    except (TypeError, ValueError):
        return False
    return attacker_type == MOSQUITO_SWARM_IDENTIFIER and damage > 0.0
