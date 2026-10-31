# -*- coding: utf-8 -*-
"""Post-entry cubemap candidate with no native calls from lifecycle events.

Sky textures are dimension-local in ModSDK. With fixed transparent stars,
palette steps change sky color only and restore its previous owner on exit.
No star brightness, overworld texture, or block/grass color is changed.
Runtime visual and crash acceptance on the target client remains required.
"""


class InitialSkyPresentation(object):
    """Bound the existing entry cover around the first cubemap publication.

    Observed frames are a presentation grace, not a GPU-completion assertion.
    No native renderer or UI calls occur in this state machine.
    """
    def __init__(self, settle_frames=12, max_ticks=180):
        self.settle_frames = max(1, int(settle_frames))
        self.max_ticks = max(1, int(max_ticks))
        self.cancel()

    def cancel(self):
        self.requested = False
        self.active = False
        self.frames = 0
        self.ticks = 0
        self.reason = 'cancelled'

    def request(self):
        if not self.requested:
            self.requested = True
            self.active = True
            self.frames = 0
            self.ticks = 0
            self.reason = 'preparing'

    def frame(self, sky_active):
        if self.active:
            self.frames = self.frames + 1 if sky_active else 0

    def tick(self, loading):
        if self.active:
            self.ticks += 1
            if not loading and self.frames >= self.settle_frames:
                self.active = False
                self.reason = 'settled'
            elif self.ticks >= self.max_ticks:
                self.active = False
                self.reason = 'timeout'
        return self.active


class GuardedEnvironment(object):
    def __init__(self, dimension, textures, factory, wait_frames=60,
                 texture_provider=None, texture_poll_ticks=15,
                 texture_transition=None, star_textures=None, color_decoder=None):
        if len(textures) != 6:
            raise ValueError('A cubemap requires exactly six textures')
        self.target = int(dimension)
        self.textures = list(textures)
        self.base_textures = list(textures)
        self.texture_provider = texture_provider
        self.texture_poll_ticks = max(1, int(texture_poll_ticks))
        self.texture_poll_remaining = 0
        self.biome_error = None
        self.texture_transition = texture_transition
        self.star_textures = list(star_textures) if star_textures is not None else None
        if self.star_textures is not None and (len(self.star_textures) != 6 or color_decoder is None):
            raise ValueError('Fixed stars require six textures and a color decoder')
        self.color_decoder = color_decoder
        self.stars_submitted = False
        self.previous_color = None
        self.last_color = None
        self.restore_attempts = 0
        self.texture_writes = 0
        self.color_writes = 0
        self.factory = factory
        self.wait_frames = max(1, int(wait_frames))
        self.dimension = None
        self.changing = False
        self.ui = False
        self.confirmed = False
        self.frames = 0
        self.attempts = 0
        self.active = False
        self.component = None
        self.last_error = None
        self.observed_textures = None
        self.awaiting_readback = False
        self.readback_ticks = 0
        self.readback_failed = False

    def begin_change(self):
        # The old LevelRenderer may already be detaching. Do not call Reset*
        # on its component here; just release the Python reference.
        self.dimension = None
        self.changing = True
        self.ui = False
        self.confirmed = False
        self.frames = 0
        self.attempts = 0
        self.active = False
        self.component = None
        self.stars_submitted = False
        self.restore_attempts = 0
        self.last_error = None
        self.observed_textures = None
        self.textures = list(self.base_textures)
        self.texture_poll_remaining = 0
        self.biome_error = None
        self.awaiting_readback = False
        self.readback_ticks = 0
        self.readback_failed = False
        if self.texture_transition is not None:
            self.texture_transition.reset()

    def finish_change(self, dimension):
        self.dimension = dimension
        self.changing = False
        self.frames = 0
        if dimension != self.target:
            self.confirmed = False
            self.active = False
            self.component = None

    def ui_ready(self):
        self.ui = True
        self.frames = 0
        self.attempts = 0
        self.active = False
        self.component = None
        self.stars_submitted = False
        self.last_error = None
        self.observed_textures = None
        self.texture_poll_remaining = 0
        self.awaiting_readback = False
        self.readback_ticks = 0
        self.readback_failed = False

        if self.texture_transition is not None:
            self.texture_transition.reset()

    def confirm_arrival(self, success):
        self.confirmed = bool(success)
        if self.confirmed and self.dimension is None and not self.changing:
            # Joining a saved Twilight world has no dimension-change event.
            # The server's verified/reused return portal is the authority.
            self.dimension = self.target
        if not self.confirmed:
            self.active = False
        self.frames = 0

    def _ready(self, loading):
        return bool(not loading and not self.changing and self.ui
                    and self.confirmed and self.dimension == self.target)

    def render_frame(self, loading):
        # GameRenderTickEvent only supplies an observed-frame count. All
        # engine calls happen later on OnScriptTickClient's normal tick.
        if self._ready(loading) or self._restore_ready(loading):
            self.frames = min(self.frames + 1, self.wait_frames * 4)
        else:
            self.frames = 0

    def tick(self, loading):
        if self._restore_ready(loading):
            self._restore_color()
            return False
        if not self._ready(loading):
            return False
        if self.frames < self.wait_frames:
            return False
        if self.awaiting_readback:
            return self._readback_textures()
        self._poll_textures()
        if self.texture_transition is not None:
            textures = self.texture_transition.next_textures()
            if textures is None:
                # Arrival/render gates do not guarantee biome data is ready.
                # Never publish the default cubemap while the first real
                # palette is unknown or still changing beneath the player.
                return False
            self._select_textures(textures)
        if self.active:
            return True
        if self.readback_failed:
            return False
        if self.attempts >= 3 or self.frames < self.wait_frames * (self.attempts + 1):
            return False
        self.attempts += 1
        try:
            component = self.component if self.component is not None else self.factory()
            if component is None:
                self.last_error = 'component_unavailable'
                return False
            result = self._apply(component)
            if result is False:
                self.component = None
                self.last_error = 'apply_rejected'
                return False
            self.component = component
            self.awaiting_readback = True
            self.readback_ticks = 0
            return self._readback_textures()
        except Exception as error:
            self.component = None
            self.last_error = str(error)
            return False

    def _apply(self, component):
        if self.star_textures is None:
            self.texture_writes += 1
            return component.SetSkyTextures(list(self.textures))
        # A palette step only changes the native skyplane color. The fixed
        # transparent star layer is submitted once per renderer lifetime.
        if self.previous_color is None:
            self.previous_color = (component.GetUseSkyColor(), component.GetSkyColor())
        color = self.color_decoder(self.textures)
        self.color_writes += 1
        if component.SetSkyColor(color) is False:
            return False
        self.last_color = color
        if not self.stars_submitted:
            self.texture_writes += 1
            if component.SetSkyTextures(list(self.star_textures)) is False:
                return False
            self.stars_submitted = True
        return True

    def _restore_ready(self, loading):
        return bool(self.last_color is not None and self.previous_color is not None
                    and self.dimension is not None and self.dimension != self.target
                    and self.ui and not self.changing and not loading)

    def _restore_color(self):
        # SetSkyColor has no documented dimension-local guarantee. Restore
        # through a fresh component on the ordinary tick, never during detach.
        if self.restore_attempts >= 3 or self.frames < self.wait_frames * (self.restore_attempts + 1):
            return
        self.restore_attempts += 1
        try:
            component = self.factory()
            observed = component.GetSkyColor()
            if component.GetUseSkyColor() and self._same_color(observed, self.last_color):
                used, color = self.previous_color
                result = component.SetSkyColor(color) if used else component.ResetSkyColor()
                if result is False:
                    return
            # Another owner or the engine already changed/reset it: leave it.
            self.previous_color = None
            self.last_color = None
        except Exception as error:
            self.last_error = 'color_restore: ' + str(error)

    @staticmethod
    def _same_color(left, right):
        return (isinstance(left, (tuple, list)) and len(left) >= 3
                and all(abs(left[i] - right[i]) <= 0.00001 for i in range(3)))

    def _readback_textures(self):
        # SetSkyTextures may be accepted before the native texture state is
        # readable. Poll that request; resubmission can replace an in-flight
        # native load. Readback itself is not proof of GPU presentation.
        self.readback_ticks += 1
        try:
            self.observed_textures = self.component.GetSkyTextures()
            expected = self.star_textures if self.star_textures is not None else self.textures
            matches = self.observed_textures == expected
            if self.star_textures is not None:
                matches = matches and self.component.GetUseSkyColor() and self._same_color(
                    self.component.GetSkyColor(), self.color_decoder(self.textures))
        except Exception as error:
            self.last_error = 'readback_pending: ' + str(error)
            matches = False
        if matches:
            self.awaiting_readback = False
            self.active = True
            self.last_error = None
            if self.texture_transition is not None:
                self.texture_transition.applied(self.textures)
            return True
        if self.readback_ticks >= 90:
            self.awaiting_readback = False
            self.readback_failed = True
            self.last_error = 'readback_timeout'
        elif not self.last_error:
            self.last_error = 'readback_pending'
        return False

    def _poll_textures(self):
        # This method only runs on the ordinary client tick after all entry
        # gates. Do not query chunks or mutate SkyRender from lifecycle events.
        if self.texture_provider is None:
            return
        if self.texture_poll_remaining > 0:
            self.texture_poll_remaining -= 1
            return
        self.texture_poll_remaining = self.texture_poll_ticks - 1
        try:
            textures = self.texture_provider()
            if textures is None:
                if self.texture_transition is not None:
                    self.texture_transition.miss_target()
                return
            if len(textures) != 6 or not all(isinstance(path, str) and path for path in textures):
                self.biome_error = 'invalid_biome_textures'
                return
            self.biome_error = None
            if self.texture_transition is not None:
                self.texture_transition.set_target(textures)
            else:
                self._select_textures(textures)
        except Exception as error:
            if self.texture_transition is not None:
                self.texture_transition.miss_target()
            self.biome_error = str(error)

    def _select_textures(self, textures):
        if list(textures) != self.textures:
            self.textures = list(textures)
            self.active = False
            self.attempts = 0
            self.frames = self.wait_frames
            self.last_error = None
            self.awaiting_readback = False
            self.readback_ticks = 0
            self.readback_failed = False

    def status(self):
        return {'dimension': self.dimension, 'changing': self.changing,
                'uiReady': self.ui, 'serverConfirmed': self.confirmed,
                'frames': self.frames, 'attempts': self.attempts,
                'active': self.active, 'error': self.last_error,
                'observedTextures': self.observed_textures,
                'requestedTextures': list(self.textures),
                'awaitingReadback': self.awaiting_readback,
                'readbackTicks': self.readback_ticks,
                'textureWrites': self.texture_writes, 'colorWrites': self.color_writes,
                'fixedStars': self.star_textures is not None,
                'colorRestoreAttempts': self.restore_attempts,
                'biomeError': self.biome_error}
