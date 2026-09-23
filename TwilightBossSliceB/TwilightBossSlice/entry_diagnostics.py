# -*- coding: utf-8 -*-
"""Disabled file diagnostics; retain the existing gameplay call interface."""


def get_active_diagnostics():
    return None


def write_worldgen_event(event, **fields):
    return False


def default_trace_path(appdata=None):
    return None


class EntryDiagnostics(object):
    """No filesystem, environment lookup, locks, or per-event serialization."""

    def __init__(self, path=None, version="unknown", session=None,
                 activate=None, worldgen_enabled=None):
        self.path = None
        self.version = str(version)
        self.session = session
        self.worldgen_enabled = False

    def activate(self):
        return self

    def deactivate(self):
        return False

    def write(self, event, **fields):
        return False
