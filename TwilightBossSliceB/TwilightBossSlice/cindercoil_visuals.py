# -*- coding: utf-8 -*-
"""Visual-only body/taper/tail selection; never changes movement or damage."""


def refresh_segments(entity_ids, active_count, cache, trigger):
    alive = set(entity for entity in entity_ids if entity)
    for entity in list(cache):
        if entity not in alive:
            cache.pop(entity, None)
    for index, entity in enumerate(entity_ids):
        if not entity:
            continue
        role = 'body'
        if active_count > 0 and index == active_count - 1:
            role = 'tail'
        elif active_count > 1 and index == active_count - 2:
            role = 'taper'
        if cache.get(entity) == role:
            continue
        try:
            success = trigger(entity, 'tf_slice:visual_' + role)
        except Exception:
            success = False
        if success:
            cache[entity] = role
