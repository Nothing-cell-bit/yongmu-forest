# -*- coding: utf-8 -*-
"""Append-only native player shield layer candidate. Never owns the player model.

An installed layer is hidden by count zero, not removed. Native first/third
person rendering must be accepted in game; successful API calls are not proof.
"""
from __future__ import print_function

COUNT_QUERY = 'query.mod.tf_fortification_shields'
CONDITION = COUNT_QUERY + ' > 0'
RETRY_TICKS = 30
INSTALL_STEPS = (
    ('AddPlayerGeometry', ('tf_fortification_layer', 'geometry.tf_slice.player_fortification')),
    ('AddPlayerTexture', ('tf_fortification_fill', 'textures/ui/tf_slice/lich_shield_fill')),
    ('AddPlayerTexture', ('tf_fortification_frame', 'textures/ui/tf_slice/lich_shield_frame')),
    ('AddPlayerRenderMaterial', ('tf_fortification_material', 'entity_alphatest')),
    ('AddPlayerAnimation', ('tf_fortification_spin', 'animation.tf_slice.player_fortification')),
    ('AddPlayerRenderController', ('controller.render.tf_slice.player_fortification_fill', CONDITION)),
    ('AddPlayerRenderController', ('controller.render.tf_slice.player_fortification_frame', CONDITION)),
    ('AddPlayerScriptAnimate', ('tf_fortification_spin', CONDITION, False)),
    ('RebuildPlayerRender', ()),
)


class PlayerShieldLayer(object):
    def __init__(self, factory, level_id, logger=None):
        self.factory = factory
        self.level_id = level_id
        self.log = logger or print
        self.registered = False
        self.players = {}

    def set_count(self, owner, count, tick):
        count = max(0, min(5, int(count)))
        state = self.players.get(owner)
        if state is None:
            if count == 0:
                return True
            state = dict(stage=0, applied=None, retry=0, desired=count)
            self.players[owner] = state
        if count == state['applied']:
            return True
        # A stop must not wait on a failed positive-count update's cooldown.
        if count == 0 and state['desired'] != 0:
            state['retry'] = 0
        state['desired'] = count
        if tick < state['retry']:
            return False
        operation = 'Register'
        try:
            if not self.registered:
                if self.factory.CreateQueryVariable(self.level_id).Register(COUNT_QUERY, 0.0) is not True:
                    raise RuntimeError('query registration rejected')
                self.registered = True
            query = self.factory.CreateQueryVariable(owner)
            if state['applied'] is None:
                operation = 'initial hide'
                if query.Set(COUNT_QUERY, 0.0) is not True:
                    raise RuntimeError('initial hide rejected')
                state['applied'] = 0
            if count > 0 and state['stage'] < len(INSTALL_STEPS):
                operation = 'CreateActorRender'
                render = self.factory.CreateActorRender(owner)
                while state['stage'] < len(INSTALL_STEPS):
                    operation, arguments = INSTALL_STEPS[state['stage']]
                    if getattr(render, operation)(*arguments) is not True:
                        raise RuntimeError('render installation rejected')
                    state['stage'] += 1
                self.log('[TwilightBossSlice] player shield layer installed (API only): %s' % owner)
            operation = 'Set count'
            if query.Set(COUNT_QUERY, float(count)) is not True:
                raise RuntimeError('count update rejected')
            state['applied'] = count
            state['retry'] = 0
            state.pop('failure', None)
            self.log('[TwilightBossSlice] player shield layer count: %s %s' % (owner, count))
            return True
        except Exception as exc:
            state['retry'] = tick + RETRY_TICKS
            failure = '%s: %s' % (operation, exc)
            if state.get('failure') != failure:
                self.log('[TwilightBossSlice] player shield layer failed: %s %s' % (owner, failure))
                state['failure'] = failure
            return False
