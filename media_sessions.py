"""Small Windows media adapters, separated from the monitor lifecycle."""
import datetime
import asyncio
import io
import math
import threading
from PIL import Image
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status
from winsdk.windows.storage.streams import DataReader


class DaemonMediaRequest:
    """One HTTP job whose completion never touches Qt or an asyncio loop."""

    def __init__(self, fetch):
        self.finished = threading.Event()
        self.data = {}

        def run():
            try:
                self.data = fetch()
            except Exception:
                pass
            finally:
                self.finished.set()

        self.thread = threading.Thread(target=run, daemon=True, name="DaisyLyricRequest")
        self.thread.start()

    async def result(self):
        async with asyncio.timeout(8):
            while not self.finished.is_set():
                await asyncio.sleep(.025)
        return self.data


def playback_state(session):
    status = session.get_playback_info().playback_status
    return {Status.PLAYING: "Playing", Status.PAUSED: "Paused"}.get(status, "Idle")


def select_session(manager, preferred_source=''):
    sessions = list(manager.get_sessions())
    current = manager.get_current_session()
    if preferred_source:
        for session in sessions:
            if session.source_app_user_model_id.casefold() == preferred_source.casefold():
                return session
    for session in sessions:
        try:
            if "spotify" in session.source_app_user_model_id.lower() and playback_state(session) == "Playing":
                return session
        except Exception:
            continue
    return current if current is not None else next(iter(sessions), None)


def available_sources(manager):
    names = {'spotify': 'Spotify', 'netflix': 'Netflix', 'chrome': 'Chrome',
             'brave': 'Brave', 'edge': 'Edge', 'firefox': 'Firefox', 'youtube': 'YouTube'}
    sources = {}
    for session in manager.get_sessions():
        source = session.source_app_user_model_id
        name = next((name for key, name in names.items() if key in source.lower()),
                    source.rsplit('!', 1)[-1].removesuffix('.exe'))
        sources[source] = {'id': source, 'name': name}
    return sorted(sources.values(), key=lambda item: (item['name'].casefold(), item['id']))


def timeline_seconds(timeline, playing):
    start = timeline.start_time.total_seconds()
    duration = max(0., timeline.end_time.total_seconds() - start)
    position = timeline.position.total_seconds() - start
    if playing:
        elapsed = (datetime.datetime.now(datetime.timezone.utc) - timeline.last_updated_time).total_seconds()
        position += max(0., elapsed)
    if not math.isfinite(duration) or not math.isfinite(position):
        return 0., 0.
    return min(duration, max(0., position)), duration


async def read_artwork(thumbnail):
    if not thumbnail:
        return b"", "#000000"
    stream = reader = None
    try:
        stream = await thumbnail.open_read_async()
        if not 0 < stream.size <= 10 * 1024 * 1024:
            return b"", "#000000"
        reader = DataReader(stream.get_input_stream_at(0))
        await reader.load_async(stream.size)
        data = bytes(reader.read_buffer(stream.size))
        with Image.open(io.BytesIO(data)) as image:
            rgb = image.convert("RGB").resize((1, 1)).getpixel((0, 0))
        return data, '#{:02x}{:02x}{:02x}'.format(*rgb)
    except Exception:
        return b"", "#000000"
    finally:
        for resource in (reader, stream):
            if resource:
                try:
                    resource.close()
                except Exception:
                    pass
