import subprocess
import threading


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
        self.ring_buffer = RingBuffer()
        self._running = False
        self._current_decoder = None
        self._encoder = None
        self._pending_action: tuple[str, str | None] | None = None
        self._action_lock = threading.Lock()
        self._track_changed = threading.Event()
        self._last_track: str | None = None

    def start(self):
        self._running = True
        self._encoder = self._start_encoder()
        threading.Thread(target=self._read_encoder, daemon=True).start()
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False
        if self._current_decoder:
            self._current_decoder.kill()
            self._current_decoder.wait()
        if self._encoder:
            try:
                self._encoder.stdin.close()
            except OSError:
                pass
            self._encoder.kill()
            self._encoder.wait()

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
        picked = self.scanner.pick_random()
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

            while self._running:
                chunk = decoder.stdout.read(4096)
                if not chunk:
                    break
                try:
                    self._encoder.stdin.write(chunk)
                    self._encoder.stdin.flush()
                except (BrokenPipeError, OSError):
                    return

            decoder.wait()
            self._current_decoder = None
            self._last_track = track

    def _play_dj_clip(self, prev_track: str, next_track: str):
        try:
            from streamer.dj import generate_dj_clip
            pcm = generate_dj_clip(prev_track, next_track)
            if pcm:
                self._encoder.stdin.write(pcm)
                self._encoder.stdin.flush()
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

    def _start_encoder(self) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "ffmpeg", "-v", "error",
                "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", "pipe:0",
                "-f", "ogg", "-acodec", "libvorbis", "-b:a", "128k",
                "-flush_packets", "1", "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _read_encoder(self):
        headers = self._capture_ogg_headers()
        self.ring_buffer.set_headers(headers)
        while self._running:
            chunk = self._encoder.stdout.read(4096)
            if not chunk:
                break
            self.ring_buffer.write(chunk)

    def _capture_ogg_headers(self) -> bytes:
        data = b""
        pages_found = 0
        last_page_end = 0
        while pages_found < 3:
            chunk = self._encoder.stdout.read(4096)
            if not chunk:
                break
            data += chunk
            pages_found = 0
            offset = 0
            last_page_end = 0
            while offset < len(data) - 27:
                if data[offset:offset + 4] != b"OggS":
                    break
                if offset + 27 > len(data):
                    break
                num_segments = data[offset + 26]
                header_size = 27 + num_segments
                if offset + header_size > len(data):
                    break
                body_size = sum(data[offset + 27:offset + header_size])
                page_end = offset + header_size + body_size
                if page_end > len(data):
                    break
                pages_found += 1
                last_page_end = page_end
                offset = page_end

        header_bytes = data[:last_page_end]
        remainder = data[last_page_end:]
        if remainder:
            self.ring_buffer.write(remainder)
        return header_bytes
