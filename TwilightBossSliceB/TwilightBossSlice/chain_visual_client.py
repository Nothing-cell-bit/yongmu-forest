# -*- coding: utf-8 -*-
"""Client-owned chain endpoints sampled at render callbacks.

Links live on a stationary client-only carrier, never the moving projectile.
Both endpoints are transformed through a fixed carrier basis. Where client-only
bone readback is unavailable, initialize from its authored zero-yaw spawn frame.
Readback is optional diagnostics, not a visibility prerequisite.
"""
from __future__ import division
import math
import time

# Fractions measured from head toward hand; Java's hand-to-head positions are
# 5%, 25%, 45%, 65%, 85%. The hand anchor itself remains unchanged.
LINK_FRACTIONS = (0.95, 0.75, 0.55, 0.35, 0.15)
PREFIX = 'query.mod.tf_chain_'
PROBES = ('chain_basis_x', 'chain_basis_y', 'chain_basis_z')
VISUAL_IDENTIFIER = 'tf_slice:block_chain_link'
HEAD_CENTER_HEIGHT = 0.25


def spawn_frame(position):
    """Zero-yaw, unit-scale BB frame, matching the recorded zero-yaw probes.

    Only valid for this unbound carrier, created at rotation (0, 0), whose
    geometry has no root offsets/rotations. Never use for the moving head.
    """
    axes = ((1, 0, 0), (0, 1, 0), (0, 0, -1))
    return (position, [tuple(position[i]+axis[i] for i in range(3)) for axis in axes])


def trace_value(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return [trace_value(v) for v in value]
    return value


def first_person_grip(camera, forward, fov=70.0, main_hand=True, yaw=0.0):
    """Source virtual grip from eye position and look vector, in any view.

    Keep the old call signature for callers/tests; FOV and camera yaw no
    longer affect the anchor. Java rotates the look by +/-0.4 radians.
    """
    length = math.sqrt(sum(float(v)**2 for v in forward))
    if length < 0.000001:
        return None
    forward = tuple(float(v)/length for v in forward)
    angle = -0.4 if main_hand else 0.4
    c, s = math.cos(angle), math.sin(angle)
    return (float(camera[0]) + forward[0]*c + forward[2]*s,
            float(camera[1]) + forward[1] - 0.4,
            float(camera[2]) + forward[2]*c - forward[0]*s)


def head_center(model):
    """Named visible head center, with a matching fallback in the yaw-only root."""
    center = model.GetBonePositionFromMinecraftObject('chain_head')
    if center is not None:
        return center
    origin = model.GetBonePositionFromMinecraftObject('chain_origin')
    if origin is None:
        origin = model.GetBonePositionFromMinecraftObject('block')
    if origin is None:
        return None
    return (origin[0], origin[1] + HEAD_CENTER_HEIGHT, origin[2])


def diagnostic_path():
    """File diagnostics are disabled in the submitted runtime pack."""
    return None


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def local_endpoint(origin, probes, hand):
    """Invert measured 16-model-unit basis using Cramer's rule.

    Return model units, or None for unavailable/degenerate/nonfinite samples.
    """
    try:
        a, b, c = [_sub(point, origin) for point in probes]
        delta = _sub(hand, origin)
        values = a + b + c + delta
        if any(math.isnan(v) or math.isinf(v) for v in values):
            return None
        determinant = _dot(a, _cross(b, c))
        if abs(determinant) < 0.000001 or _dot(delta, delta) > 1024:
            return None
        return tuple(16.0 * value / determinant for value in (
            _dot(delta, _cross(b, c)),
            _dot(a, _cross(delta, c)),
            _dot(a, _cross(b, delta)),
        ))
    except (TypeError, ValueError, IndexError):
        return None


class ChainVisuals(object):
    def __init__(self, factory, level_id, clock=None, local_player=None, trace_path=None,
                 create_visual=None, destroy_visual=None):
        self.factory = factory
        self.level_id = level_id
        self.local_player = local_player
        self.trace_path = trace_path
        self.create_visual = create_visual
        self.destroy_visual = destroy_visual
        self.retired = set()
        self.trace_records = []
        self.trace_count = 0
        self.stage_count = 0
        self.next_trace = 0
        self.clock = clock or time.time
        self.entries = {}
        self.active_owners = set()
        self.reported = set()
        query = factory.CreateQueryVariable(level_id)
        for key in ('hand_x', 'hand_y', 'hand_z', 'head_x', 'head_y', 'head_z',
                    'ready', 'active'):
            query.Register(PREFIX + key, 0.0)

    def receive(self, data):
        projectile = data.get('projectileId')
        if not projectile:
            return
        projectile = str(projectile)
        if data.get('removed'):
            self._release(self.entries.get(projectile, {}))
            self.entries.pop(projectile, None)
            self._refresh_owners()
            self.flush_trace()
            return
        owner = data.get('ownerId')
        if not owner:
            return
        state = self.entries.setdefault(projectile, {})
        state.update({'projectile': projectile, 'owner': str(owner), 'main': bool(data.get('mainHand', True)),
                      'expires': self.clock() + 2.0})

    def flush_trace(self):
        # Retain optional bounded in-memory samples for adapter tests only.
        self.trace_records = []

    def _hand(self, state, owner_model):
        owner = state['owner']
        eye = self.factory.CreatePos(owner).GetPos()
        rotation = self.factory.CreateRot(owner).GetRot()
        if eye is None or rotation is None:
            return None
        # NetEase GetPos reports feet+1.62 even when crouching/swimming.
        # Match the Java player's eye heights instead of adding eye height twice.
        query = self.factory.CreateQueryVariable(owner)
        def flag(name):
            try:
                return query.GetMolangValue('query.' + name) == 1
            except Exception:
                return False
        correction = 0.0
        if not flag('is_sleeping'):
            if flag('is_swimming') or flag('is_gliding'):
                correction = 0.4 - 1.62
            elif flag('is_sneaking'):
                correction = 1.27 - 1.62
        eye = (float(eye[0]), float(eye[1]) + correction, float(eye[2]))
        pitch, yaw = [math.radians(float(v)) for v in rotation]
        forward = (-math.sin(yaw)*math.cos(pitch), -math.sin(pitch),
                   math.cos(yaw)*math.cos(pitch))
        state['eye'] = eye
        state['forward'] = forward
        if self.local_player and str(self.local_player()) == state['owner']:
            perspective = self.factory.CreatePlayerView(state['owner']).GetPerspective()
            state['perspective'] = perspective
        else:
            state['perspective'] = 'observer'
        state.pop('camera', None)
        return first_person_grip(eye, forward, main_hand=state['main'])

    def _report_once(self, reason):
        if reason not in self.reported:
            self.reported.add(reason)
            if self.trace_path:
                self.trace_records.append({'event': 'status', 'time': self.clock(), 'reason': reason})

    def _stage(self, state, stage, **details):
        if state.get('stage') == stage:
            return
        state['stage'] = stage
        self._report_once('startup v4: ' + stage)
        if self.trace_path and self.stage_count < 180:
            record = {'event': 'stage', 'stage': stage, 'time': self.clock(),
                      'projectile': state.get('projectile'), 'owner': state.get('owner'),
                      'carrier': state.get('carrier')}
            record.update((key, trace_value(value)) for key, value in details.items())
            self.trace_records.append(record)
            self.stage_count += 1

    def _carrier_frame(self, state):
        # Older bone-position APIs are not guaranteed to find client-only
        # actors. A missing readback must not hold ready=0 indefinitely.
        try:
            model = self.factory.CreateModel(state['carrier'])
            anchor = model.GetBonePositionFromMinecraftObject('chain_origin')
            probes = [model.GetBonePositionFromMinecraftObject(name) for name in PROBES]
            if local_endpoint(anchor, probes, anchor) is not None:
                return (anchor, probes), 'measured'
        except Exception:
            pass
        return state.get('basis') or spawn_frame(state['spawn']), state.get('basisSource', 'authored_spawn')

    def _client_matrix_sample(self, carrier):
        # Keep raw matrices: the API does not document matrix layout/world
        # origin conventions sufficiently to treat translations as world XYZ.
        try:
            actor = self.factory.CreateActorRender(carrier)
            return dict((bone, actor.GetQueryableBoneOrientation(bone, True))
                        for bone in ('chain_origin', 'chain_0') + PROBES)
        except Exception as error:
            return {'error': repr(error)}

    def _hide(self, projectile):
        if not projectile:
            return
        try:
            self.factory.CreateQueryVariable(projectile).Set(PREFIX + 'ready', 0.0)
        except Exception:
            pass

    def _release(self, state):
        carrier = state.pop('carrier', None)
        if carrier:
            self._hide(carrier)
            self.retired.add(carrier)
        state.pop('basis', None)
        state.pop('basisSource', None)
        state.pop('spawn', None)
        state.pop('lastHand', None)
        state.pop('lastTail', None)
        self._collect()

    def _collect(self):
        for carrier in list(self.retired):
            self._hide(carrier)
            try:
                if self.destroy_visual and self.destroy_visual(carrier) is True:
                    self.retired.discard(carrier)
            except Exception:
                self._report_once('client carrier removal pending')

    def _ensure_carrier(self, state, hand, now):
        if state.get('carrier'):
            return True
        if not self.create_visual:
            self._stage(state, 'create_api_missing')
            return False
        if now < state.get('nextCreate', 0):
            return False
        state['nextCreate'] = now + 1.0
        try:
            carrier = self.create_visual(VISUAL_IDENTIFIER, tuple(hand), (0.0, 0.0))
        except Exception as error:
            self._stage(state, 'create_failed', error=repr(error), spawn=hand)
            return False
        if carrier:
            # Never move, rotate, bind, or impart velocity to this actor.
            # Its default ready=0 keeps every link hidden until matrix readback.
            if str(carrier) == state['owner'] or str(carrier) in self.entries:
                self._report_once('refusing non-visual entity id')
                return False
            state['carrier'] = str(carrier)
            state['spawn'] = tuple(hand)
            self._hide(str(carrier))
            self._stage(state, 'created_hidden', spawn=hand)
        else:
            self._stage(state, 'create_failed', result=carrier, spawn=hand)
        return False

    def _refresh_owners(self):
        owners = set(value['owner'] for value in self.entries.values())
        for owner in owners | self.active_owners:
            try:
                self.factory.CreateQueryVariable(owner).Set(
                    PREFIX + 'active', 1.0 if owner in owners else 0.0)
            except Exception:
                pass
        self.active_owners = owners

    def clear(self):
        for state in self.entries.values():
            self._release(state)
        self.entries.clear()
        self._refresh_owners()
        self.flush_trace()

    def render(self):
        now = self.clock()
        self._collect()
        for projectile, state in list(self.entries.items()):
            if now > state['expires']:
                self._release(state)
                self.entries.pop(projectile, None)
                continue
            try:
                model = self.factory.CreateModel(projectile)
                origin = head_center(model)
                owner_model = self.factory.CreateModel(state['owner'])
                hand = self._hand(state, owner_model)
                if (origin is None or hand is None or
                        any(math.isnan(v) or math.isinf(v) for v in tuple(origin)+tuple(hand)) or
                        _dot(_sub(hand, origin), _sub(hand, origin)) > 1024):
                    self._stage(state, 'endpoints_unavailable', head=origin, hand=hand)
                    self._hide(state.get('carrier'))
                    continue
                if not self._ensure_carrier(state, hand, now):
                    continue
                carrier = state['carrier']
                carrier_model = self.factory.CreateModel(carrier)
                basis, basis_source = self._carrier_frame(state)
                anchor, probes = basis
                hand_local = local_endpoint(anchor, probes, hand)
                head_local = local_endpoint(anchor, probes, origin)
                if hand_local is None or head_local is None:
                    self._stage(state, 'frame_invalid', head=origin, hand=hand, anchor=anchor)
                    self._hide(carrier)
                    # Re-anchor only after long travel; missing bones just wait.
                    if anchor is not None and any(
                            _dot(_sub(point, anchor), _sub(point, anchor)) > 1024
                            for point in (hand, origin)):
                        self._release(state)
                    continue
                if (state.get('basisSource') == 'measured' and basis_source == 'measured'
                        and basis != state['basis']):
                    self._report_once('stationary carrier moved; rebuilding hidden')
                    self._release(state)
                    continue
                state['basis'] = basis
                state['basisSource'] = basis_source
                try:
                    tail = carrier_model.GetBonePositionFromMinecraftObject('chain_0')
                except Exception:
                    tail = None
                query = self.factory.CreateQueryVariable(carrier)
                # Hide before the six-value transaction; a failed write must not
                # display a mix of the old head and the new hand.
                if query.Set(PREFIX + 'ready', 0.0) is False:
                    self._stage(state, 'ready_write_failed')
                    self._release(state)
                    continue
                applied = True
                for endpoint, local in (('hand', hand_local), ('head', head_local)):
                    for axis, value in zip('xyz', local):
                        if query.Set(PREFIX + endpoint + '_' + axis, value) is False:
                            applied = False
                applied = query.Set(PREFIX + 'ready', 1.0 if applied else 0.0) is not False and applied
                if applied:
                    self._stage(state, 'coordinates_enabled', basisSource=basis_source)
                else:
                    self._stage(state, 'coordinate_write_failed', handLocal=hand_local, headLocal=head_local)
                expected_tail = tuple(origin[i] + (hand[i]-origin[i])*LINK_FRACTIONS[0]
                                      for i in range(3))
                # Read back the nearest link, not the hand anchor: the source
                # intentionally leaves 5% of the span between hand and link 0.
                # Compare against the previous request as well: the callback starts
                # a frame and native bone matrices may still describe its predecessor.
                if self.trace_path and self.trace_count < 120 and now >= self.next_trace:
                    previous = state.get('lastHand')
                    previous_tail = state.get('lastTail')
                    self.trace_records.append({
                        'time': now, 'projectile': projectile,
                        'perspective': state.get('perspective'),
                        'camera': state.get('camera'), 'eye': state.get('eye'),
                        'forward': state.get('forward'),
                        'origin': origin, 'carrier': carrier, 'carrierOrigin': anchor,
                        'probes': probes, 'targetHand': hand,
                        'pipeline': 'client_carrier_source_alignment_v6', 'applied': applied,
                        'basisSource': basis_source,
                        'clientBoneMatrices': self._client_matrix_sample(carrier),
                        'requestedHand': hand,
                        'previousHand': previous, 'actualTail': tail,
                        'targetTail': expected_tail, 'previousTail': previous_tail,
                        'handLocal': hand_local, 'headLocal': head_local,
                        'errorToCurrent': math.sqrt(_dot(_sub(tail,expected_tail),_sub(tail,expected_tail))) if tail else None,
                        'errorToPrevious': math.sqrt(_dot(_sub(tail,previous_tail),_sub(tail,previous_tail))) if tail and previous_tail else None,
                    })
                    self.trace_count += 1
                    self.next_trace = now + 0.1
                if applied:
                    state['lastHand'] = hand
                    state['lastTail'] = expected_tail
            except Exception as error:
                self._stage(state, 'render_api_error', error=repr(error))
                self._hide(state.get('carrier'))
        self._refresh_owners()
        if not self.entries:
            self.flush_trace()
