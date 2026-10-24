import asyncio
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
from media_sessions import playback_state, select_session, timeline_seconds, read_artwork, DaemonMediaRequest, available_sources
from media_transport import MediaTransport, session_capabilities


class MediaMonitor(QThread, MediaTransport):
    media_updated = pyqtSignal(str, str, str, str)
    lyrics_updated = pyqtSignal(str)
    artwork_updated = pyqtSignal(bytes)
    timeline_updated = pyqtSignal(float, float)
    source_updated = pyqtSignal(str)
    capabilities_updated = pyqtSignal(dict)
    sources_updated = pyqtSignal(list)
    transport_result = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True
        self.loop = self.manager = self.current_session = None
        self.lyrics = []
        self.last_lyric_sent = self.current_title = self.current_artist = self.last_state = ""
        self._tokens = []
        self._manager_tokens = []
        self._generation = 0
        self._lyric_task = None
        self._lyric_job = None
        self._main_task = None
        self._refresh_pending = False
        self._session_refresh_pending = False
        self._wake = None
        self._artwork = b""
        self._accent = "#000000"
        self.preferred_source = ''
        self._sources = []
        self._capabilities = session_capabilities(None)
        self._metadata_pending = False

    def run(self):
        if not self._is_running:
            return
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self._main_task = self.loop.create_task(self.monitor_media())
            self.loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            pass
        except Exception as error:
            print("MediaMonitor error:", error)
        finally:
            self._detach_session()
            self._unsubscribe(self._manager_tokens)
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
            self.loop = None

    async def monitor_media(self):
        if not self._is_running:
            return
        self._wake = asyncio.Event()
        self.manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        for name in ("sessions_changed", "current_session_changed"):
            try:
                token = getattr(self.manager, "add_" + name)(self.on_sessions_changed)
                self._manager_tokens.append((self.manager, name, token))
            except Exception:
                pass
        while self._is_running:
            await self.update_media_info()
            await self.check_lyric_sync()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=1.)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    @staticmethod
    def _unsubscribe(tokens):
        for owner, name, token in tokens:
            try:
                getattr(owner, "remove_" + name)(token)
            except Exception:
                pass
        tokens.clear()

    def _detach_session(self):
        self._unsubscribe(self._tokens)
        self.current_session = None
        self._clear_state()

    def _clear_state(self):
        self._generation += 1
        self._metadata_pending = False
        if self._lyric_task:
            self._lyric_task.cancel()
            self._lyric_task = None
        self.lyrics = []
        self.last_lyric_sent = self.current_title = self.current_artist = ""
        self.last_state = "Idle"
        self._artwork, self._accent = b"", "#000000"
        self.media_updated.emit("Idle", "", "", self._accent)
        self.lyrics_updated.emit("")
        self.artwork_updated.emit(b"")
        self.timeline_updated.emit(0., 0.)
        self.source_updated.emit("")
        self._capabilities = session_capabilities(None)
        self.capabilities_updated.emit(self._capabilities)

    def subscribe_to_current_session(self):
        try:
            sources = available_sources(self.manager)
            if sources != self._sources:
                self._sources = sources
                self.sources_updated.emit(sources)
            session = select_session(self.manager, self.preferred_source)
            rebind = self._session_refresh_pending
            self._session_refresh_pending = False
            # WinRT returns fresh unequal Python wrappers on every manager read.
            # Keep the subscribed wrapper until selection or the manager changes.
            same_source = (session is not None and self.current_session is not None
                           and session.source_app_user_model_id == self.current_session.source_app_user_model_id)
            if not rebind and (session is self.current_session or same_source):
                return
            self._detach_session()
            self.current_session = session
            if session is None:
                return
            self.source_updated.emit(session.source_app_user_model_id)
            for name in ("media_properties_changed", "playback_info_changed", "timeline_properties_changed"):
                try:
                    token = getattr(session, "add_" + name)(self.on_properties_changed)
                    self._tokens.append((session, name, token))
                except Exception:
                    pass
        except Exception:
            self._detach_session()

    def _request_refresh(self, session_changed=False):
        if not self._is_running or not self.loop or self.loop.is_closed():
            return
        def schedule():
            self._refresh_pending = True
            self._session_refresh_pending |= session_changed
            if self._wake:
                self._wake.set()
        try:
            self.loop.call_soon_threadsafe(schedule)
        except RuntimeError:
            pass

    def on_sessions_changed(self, sender, args):
        self._request_refresh(session_changed=True)

    def on_properties_changed(self, sender, args):
        self._request_refresh()

    def on_playback_changed(self, sender, args):
        self._request_refresh()

    async def update_media_info(self):
        self.subscribe_to_current_session()
        session = self.current_session
        if session is None:
            return
        generation = self._generation
        try:
            state = playback_state(session)
            capabilities = session_capabilities(session)
            if capabilities != self._capabilities:
                self._capabilities = capabilities
                self.capabilities_updated.emit(capabilities)
            props = await session.try_get_media_properties_async()
            if session != self.current_session or generation != self._generation:
                return
            title = (props.title or "Unknown Title") if props else "Unknown Title"
            artist = (props.artist or "") if props else ""
            if state == "Idle":
                self._detach_session()
                return
            song_changed = (title, artist) != (self.current_title, self.current_artist)
            if song_changed:
                self._generation += 1
                generation = self._generation
                self._metadata_pending = True
                self._capabilities = session_capabilities(None)
                self.capabilities_updated.emit(self._capabilities)
                self.timeline_updated.emit(0., 0.)
                if self._lyric_task:
                    self._lyric_task.cancel()
                self._artwork = b''
                self.artwork_updated.emit(b'')
            if song_changed or self._refresh_pending:
                self._refresh_pending = False
                artwork, accent = await read_artwork(props.thumbnail if props else None)
                if session != self.current_session or generation != self._generation:
                    return
                self._artwork, self._accent = artwork, accent
                self.artwork_updated.emit(artwork)
            if song_changed:
                self.current_title, self.current_artist = title, artist
                self.lyrics, self.last_lyric_sent = [], ""
                self.lyrics_updated.emit("")
                self._lyric_task = asyncio.create_task(self.fetch_lyrics(artist, title))
            if song_changed or state != self.last_state:
                self.last_state = state
                self.media_updated.emit(state, title, artist, self._accent)
            self._metadata_pending = False
            if capabilities != self._capabilities:
                self._capabilities = capabilities
                self.capabilities_updated.emit(capabilities)
        except Exception:
            self._detach_session()

    async def check_lyric_sync(self):
        session = self.current_session
        if session is None:
            return
        try:
            position, duration = timeline_seconds(session.get_timeline_properties(), self.last_state == "Playing")
            self.timeline_updated.emit(position, duration)
            line = ""
            for timestamp, text in self.lyrics:
                if timestamp > position:
                    break
                line = text
            if line != self.last_lyric_sent:
                self.last_lyric_sent = line
                self.lyrics_updated.emit(line)
        except Exception:
            self._detach_session()

    async def fetch_lyrics(self, artist, title):
        if not artist or not title or title == "Unknown Title":
            return
        generation, session = self._generation, self.current_session
        previous = self._lyric_job
        # Keep only one HTTP job alive; waiting remains cancellable on skips
        # and shutdown, even if the old job is stuck in DNS.
        while previous and previous.thread.is_alive():
            await asyncio.sleep(.025)
        if (not self._is_running or generation != self._generation or session != self.current_session
                or (title, artist) != (self.current_title, self.current_artist)):
            return
        def do_fetch():
            response = None
            try:
                response = requests.get("https://lrclib.net/api/get", params={"artist_name": artist, "track_name": title}, timeout=(2, 3))
                if response.status_code == 200:
                    return response.json()
            except Exception:
                pass
            finally:
                if response is not None and callable(getattr(response, "close", None)):
                    response.close()
            return {}
        self._lyric_job = DaemonMediaRequest(do_fetch)
        try:
            data = await self._lyric_job.result()
        except TimeoutError:
            return
        lyrics = self.parse_lrc(data["syncedLyrics"]) if data.get("syncedLyrics") else []
        if not lyrics and data.get("plainLyrics"):
            lyrics = [(0., data["plainLyrics"].splitlines()[0])]
        if (self._is_running and generation == self._generation and session == self.current_session
                and (title, artist) == (self.current_title, self.current_artist)):
            self.lyrics = lyrics

    def parse_lrc(self, lrc_text):
        lyrics = []
        for line in lrc_text.splitlines():
            match = re.search(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)', line)
            if match:
                minutes, seconds, text = match.groups()
                lyrics.append((int(minutes) * 60 + float(seconds), text.strip()))
        return sorted(lyrics)

    def stop(self):
        self._is_running = False
        loop = self.loop
        if loop and not loop.is_closed() and self._main_task:
            try:
                loop.call_soon_threadsafe(self._main_task.cancel)
            except RuntimeError:
                pass
        return self.wait(1000)

