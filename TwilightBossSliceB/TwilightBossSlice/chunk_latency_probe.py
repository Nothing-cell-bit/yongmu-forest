# -*- coding: utf-8 -*-
"""Explicit-command, bounded PC development probe; inert until start()."""
import copy
import io
import json
import time


class Probe(object):
    def __init__(self, side, clock=None, sdk=None):
        self.side = side
        self.clock = clock or time.time
        self.sdk = sdk
        self.active = False
        self.owned_profile = False
        self.events = []
        self.errors = []
        self.path = None

    def start(self, directory, token):
        if self.active or self.owned_profile or not directory:
            return False
        if not isinstance(token, (str, type(u''))) or not 1 <= len(token) <= 64:
            return False
        if any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-' for c in token):
            return False
        self.path = str(directory).replace('\\', '/').rstrip('/') + '/' + token + '-' + self.side
        self.events = []
        self.errors = []
        self.dropped = 0
        self.frame_count = 0
        self.max_frame_gap = 0.0
        self.last_frame = None
        self.started = self.clock()
        self.active = True
        self.profile_started = False
        if self.sdk is not None:
            try:
                self.owned_profile = self.sdk.StartProfile() is True
                self.profile_started = self.owned_profile
                if not self.owned_profile:
                    self.errors.append('profile_start_rejected')
            except Exception as error:
                self.errors.append('profile_start: ' + str(error))
        return True

    def record(self, event, fields):
        if not self.active:
            return
        if len(self.events) >= 4096:
            self.dropped += 1
            return
        try:
            snapshot = copy.deepcopy(fields)
        except Exception:
            self.dropped += 1
            if 'event_snapshot_failed' not in self.errors:
                self.errors.append('event_snapshot_failed')
            return
        self.events.append({'time': self.clock(), 'event': str(event), 'fields': snapshot})

    def frame(self):
        if not self.active:
            return
        now = self.clock()
        self.frame_count += 1
        if self.last_frame is not None:
            self.max_frame_gap = max(self.max_frame_gap, max(0.0, now - self.last_frame))
        self.last_frame = now

    def tick(self):
        if self.active and self.clock() - self.started >= 60.0:
            self.stop('timeout')
            return True
        return False

    def stop(self, reason='manual'):
        if not self.active and not self.owned_profile:
            return False
        self.active = False
        ended = self.clock()
        if self.owned_profile:
            try:
                if self.sdk.StopProfile(self.path + '.svg') is True:
                    self.owned_profile = False
                else:
                    self.errors.append('profile_stop_rejected')
            except Exception as error:
                self.errors.append('profile_stop: ' + str(error))
        data = {'probeVersion': 'chunk-latency-v1', 'side': self.side,
                'startedAt': self.started, 'endedAt': ended,
                'durationSeconds': max(0.0, ended - self.started), 'reason': reason,
                'events': self.events, 'droppedEvents': self.dropped,
                'frameCount': self.frame_count, 'maxFrameGapSeconds': self.max_frame_gap,
                'profileStarted': self.profile_started,
                'profileStopped': self.profile_started and not self.owned_profile,
                'errors': list(self.errors)}
        try:
            text = json.dumps(data, ensure_ascii=True, indent=2, default=repr)
            with io.open(self.path + '.json', 'w', encoding='utf-8') as handle:
                handle.write(text if isinstance(text, type(u'')) else text.decode('utf-8'))
        except Exception as error:
            self.errors.append('export: ' + str(error))
            return False
        return not self.owned_profile
