# -*- coding: utf-8 -*-
"""Pure helpers for reconciling ModSDK entity-id representations."""


def matching_entity_key(registry, entity_id):
    """Return the stored key for an engine actor even if its id type changed."""
    if entity_id in registry:
        return entity_id
    candidate = str(entity_id)
    for stored_id in registry:
        if str(stored_id) == candidate:
            return stored_id
    return None
