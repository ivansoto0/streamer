import subprocess
import threading
import time

from streamer.curator import Curator

BYTES_PER_SECOND = 44100 * 2 * 2


class RingBuffer:
    def __init__(self, size: int = 512 * 1024):
        self._buffer = bytearray(size)
        self._size = size
        self._write_pos = 0
        self._lock = threading.Lock()
        self._headers = b""

    def write(self, data: bytes) -> None:
        with self._lock:
            dlen = len(data)
            start = self._write_pos % self._size
            end = start + dlen
            if end <= self._size:
                self._buffer[start:end] = data
            else:
                first = self._size - start
                self._buffer[start:self._size] = data[:first]
                self._buffer[0:dlen - first] = data[first:]
            self._write_pos += dlen

    def read(self, read_pos: int, max_bytes: int = 65536) -> tuple[bytes | None, int]:
        with self._lock:
            earliest = max(0, self._write_pos - self._size)
            if read_pos < earliest:
                return None, earliest

            available = self._write_pos - read_pos
            if available <= 0:
                return b"", read_pos

            to_read = min(available, max_bytes)
            start = read_pos % self._size
            end = start + to_read
            if end <= self._size:
                result = bytes(self._buffer[start:end])
            else:
                first = self._size - start
                result = bytes(self._buffer[start:self._size]) + bytes(self._buffer[0:to_read - first])
            return result, read_pos + to_read

    def get_current_position(self) -> int:
        with self._lock:
            return self._write_pos

    def set_headers(self, headers: bytes) -> None:
        with self._lock:
            self._headers = headers

    def get_headers(self) -> bytes:
        with self._lock:
            return self._headers


class AudioPipeline:
    def __init__(self, state, scanner):
        self.state = state
        self.scanner = scanner
        self.pcm_buffer = RingBuffer(size=2 * 1024 * 1024)
        self._running = False
        self._current_decoder = None
        self._pending_action: tuple[str, str | None] | None = None
        self._action_lock = threading.Lock()
        self._track_changed = threading.Event()
        self._last_track: str | None = None
        self._curator = Curator(state, scanner)

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()
        self._curator.start()

    def stop(self):
        self._running = False
        self._curator.stop()
        if self._current_decoder:
            self._current_decoder.kill()
            self._current_decoder.wait()

    def request_next(self):
        with self._action_lock:
            self._pending_action = ("next", None)
        self._track_changed.clear()
        if self._current_decoder:
            self._current_decoder.kill()
        self._track_changed.wait(timeout=2.0)

    def request_previous(self) -> bool:
        if not self.state.history:
            return False
        with self._action_lock:
            self._pending_action = ("previous", None)
        self._track_changed.clear()
        if self._current_decoder:
            self._current_decoder.kill()
        self._track_changed.wait(timeout=2.0)
        return True

    def request_play(self, path: str):
        with self._action_lock:
            self._pending_action = ("play", path)
        self._track_changed.clear()
        if self._current_decoder:
            self._current_decoder.kill()
        self._track_changed.wait(timeout=2.0)

    def _consume_action(self) -> tuple[str, str | None] | None:
        with self._action_lock:
            action = self._pending_action
            self._pending_action = None
            return action

    def _get_next_track(self) -> str:
        action = self._consume_action()

        if action:
            kind, target = action
            if kind == "previous":
                track = self.state.go_previous()
                if track:
                    return track
            elif kind == "play":
                self.state.play_now(target)
                return target

        track = self.state.advance()
        if track:
            return track
        picked = self.scanner.pick_random(
            recent=self.state.history,
            last_track=self._last_track,
        )
        self.state.current_track = str(picked)
        return str(picked)

    def _run(self):
        while self._running:
            track = self._get_next_track()
            self._track_changed.set()

            if self.state.dj_enabled and self._last_track:
                self._play_dj_clip(self._last_track, track)

            decoder = self._start_decoder(track)
            self._current_decoder = decoder

            track_start = time.monotonic()
            bytes_written = 0

            while self._running:
                chunk = decoder.stdout.read(4096)
                if not chunk:
                    break
                self.pcm_buffer.write(chunk)
                bytes_written += len(chunk)

                expected = bytes_written / BYTES_PER_SECOND
                elapsed = time.monotonic() - track_start
                ahead = expected - elapsed
                if ahead > 0.01:
                    time.sleep(ahead)

            decoder.wait()
            self._current_decoder = None
            self._last_track = track

    def _play_dj_clip(self, prev_track: str, next_track: str):
        try:
            from streamer.dj import generate_dj_clip
            pcm = generate_dj_clip(prev_track, next_track)
            if pcm:
                start = time.monotonic()
                written = 0
                for i in range(0, len(pcm), 4096):
                    chunk = pcm[i:i + 4096]
                    self.pcm_buffer.write(chunk)
                    written += len(chunk)
                    expected = written / BYTES_PER_SECOND
                    elapsed = time.monotonic() - start
                    ahead = expected - elapsed
                    if ahead > 0.01:
                        time.sleep(ahead)
        except Exception:
            pass

    def _start_decoder(self, path: str) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "ffmpeg", "-v", "error", "-i", path,
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "44100", "-ac", "2", "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
