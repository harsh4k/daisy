"""Bounded transport commands tied to the exact selected session and track."""
import asyncio
import math
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status


def session_capabilities(session):
    result = dict.fromkeys(('previous', 'play_pause', 'next', 'seek'), False)
    try:
        info = session.get_playback_info()
        controls = info.controls
        for action, field in (('previous', 'is_previous_enabled'),
                              ('play_pause', 'is_play_pause_toggle_enabled'),
                              ('next', 'is_next_enabled'), ('seek', 'is_playback_position_enabled')):
            result[action] = getattr(controls, field, False) is True
        fallback = 'is_pause_enabled' if info.playback_status == Status.PLAYING else 'is_play_enabled'
        result['play_pause'] |= getattr(controls, fallback, False) is True
    except Exception:
        pass
    return result


def seek_ticks(session, seconds):
    """GSMTC accepts Int64 ticks (100 ns), including the timeline's start offset.

    Microsoft: GlobalSystemMediaTransportControlsSession.TryChangePlaybackPositionAsync;
    Windows.Foundation.TimeSpan.Duration defines each tick as 100 nanoseconds.
    """
    timeline = session.get_timeline_properties()
    start = timeline.start_time.total_seconds()
    end = timeline.end_time.total_seconds()
    seconds = float(seconds)
    if not all(math.isfinite(value) for value in (start, end, seconds)) or end <= start:
        raise ValueError('No seekable timeline')
    ticks = round((start + min(end - start, max(0., seconds))) * 10_000_000)
    if not -(2 ** 63) <= ticks < 2 ** 63:
        raise ValueError('Position outside WinRT bounds')
    return ticks


class MediaTransport:
    """Mixin: the monitor owns the Qt signals, loop and session generation."""

    def _transport(self, method, *args):
        actions = {'try_toggle_play_pause_async': 'play_pause',
                   'try_skip_next_async': 'next', 'try_skip_previous_async': 'previous',
                   'try_change_playback_position_async': 'seek'}
        action = actions[method]
        session, generation, loop = self.current_session, self._generation, self.loop
        preference = self.preferred_source
        def current():
            return (self._is_running and session is self.current_session
                    and generation == self._generation and preference == self.preferred_source)
        if session is None or loop is None or loop.is_closed() or not self._is_running:
            self.transport_result.emit(action, False)
            return
        async def perform():
            if not current():
                return
            if (self._metadata_pending or getattr(self, '_command_pending', False)
                    or not session_capabilities(session)[action]):
                self.transport_result.emit(action, False)
                return
            self._command_pending = True
            try:
                arguments = (seek_ticks(session, args[0]),) if action == 'seek' else ()
                selected_method = method
                if action == 'play_pause':
                    info = session.get_playback_info()
                    if not getattr(info.controls, 'is_play_pause_toggle_enabled', False):
                        selected_method = 'try_pause_async' if info.playback_status == Status.PLAYING else 'try_play_async'
                result = await asyncio.wait_for(getattr(session, selected_method)(*arguments), timeout=4.)
                success = result is True
            except asyncio.CancelledError:
                raise
            except Exception:
                success = False
            finally:
                self._command_pending = False
            if current():
                self.transport_result.emit(action, success)
                self._request_refresh()
        try:
            loop.call_soon_threadsafe(lambda: asyncio.create_task(perform()) if current() else None)
        except RuntimeError:
            if current():
                self.transport_result.emit(action, False)

    def toggle_play_pause(self):
        self._transport('try_toggle_play_pause_async')

    def next_track(self):
        self._transport('try_skip_next_async')

    def prev_track(self):
        self._transport('try_skip_previous_async')

    def seek_to(self, seconds):
        self._transport('try_change_playback_position_async', seconds)

    def set_preferred_source(self, source_id):
        self.preferred_source = str(source_id or '')
        self._request_refresh()
