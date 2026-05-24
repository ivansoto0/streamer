# Streaming Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local network audio streaming server that broadcasts a continuous 128kbps OGG Vorbis stream from local media folders, with a web control panel for playback/queue management, file browsing, and an AI DJ mode.

**Architecture:** Single Python process. A background daemon thread runs two FFmpeg subprocesses (decoder per track, one long-running encoder). Decoded PCM from successive tracks feeds seamlessly into the encoder. Encoded OGG data flows into a ring buffer. Connected clients read from the ring buffer. Flask serves the control panel and stream endpoint in the main thread with threaded request handling.

**Tech Stack:** Python 3.13, uv, Flask, FFmpeg (subprocess), pytest, google-generativeai, google-cloud-texttospeech

**Spec:** `docs/superpowers/specs/2026-05-23-streaming-server-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml` (via `uv init`)
- Create: `src/streamer/__init__.py`
- Create: `src/streamer/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Initialize uv project**

Run:
```powershell
cd D:\streamer
uv init --name streamer --package --python 3.13
```

If `uv init` generates a `src/streamer/__init__.py` or `pyproject.toml` with defaults, keep them. If it creates a `hello.py` or sample file, delete it.

- [ ] **Step 2: Add dependencies**

Run:
```powershell
uv add flask
uv add google-generativeai google-cloud-texttospeech
uv add --dev pytest
```

- [ ] **Step 3: Create .gitignore**

Create `.gitignore`:
```
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.pytest_cache/
```

- [ ] **Step 4: Create test fixtures**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:
```python
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def test_media_dir(tmp_path):
    ent_dir = tmp_path / "entertainment" / "Test Show" / "season 01"
    ent_dir.mkdir(parents=True)
    pod_dir = tmp_path / "Podcast" / "Test Podcast"
    pod_dir.mkdir(parents=True)

    for i in range(3):
        filepath = ent_dir / f"{i + 1:02d}.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"sine=frequency={440 + i * 100}:duration=1",
                "-acodec", "libmp3lame", "-b:a", "128k",
                str(filepath),
            ],
            capture_output=True,
            check=True,
        )

    pod_file = pod_dir / "episode_01.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "sine=frequency=300:duration=1",
            "-acodec", "libmp3lame", "-b:a", "128k",
            str(pod_file),
        ],
        capture_output=True,
        check=True,
    )

    txt_file = ent_dir / "notes.txt"
    txt_file.write_text("not audio")

    return tmp_path
```

- [ ] **Step 5: Create entry point stub**

Create `src/streamer/__main__.py`:
```python
def main():
    print("Streamer server starting...")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Verify setup**

Run:
```powershell
uv run pytest --co -q
uv run python -m streamer
```

Expected: pytest finds no tests, exits 0. The streamer command prints the starting message.

- [ ] **Step 7: Create GitHub repo and commit**

Run:
```powershell
git add .
git commit -m "feat: project scaffolding with uv, Flask, pytest, and test fixtures"
gh repo create streamer --private --source=. --push
```

---

### Task 2: State Module

**Files:**
- Create: `src/streamer/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests for queue operations**

Create `tests/test_state.py`:
```python
from streamer.state import ServerState


class TestQueue:
    def test_queue_starts_empty(self):
        state = ServerState()
        assert state.queue == []

    def test_queue_add_appends(self):
        state = ServerState()
        state.queue_add("a.mp3")
        state.queue_add("b.mp3")
        assert state.queue == ["a.mp3", "b.mp3"]

    def test_queue_remove_by_index(self):
        state = ServerState()
        state.queue_add("a.mp3")
        state.queue_add("b.mp3")
        state.queue_add("c.mp3")
        assert state.queue_remove(1) is True
        assert state.queue == ["a.mp3", "c.mp3"]

    def test_queue_remove_invalid_index(self):
        state = ServerState()
        state.queue_add("a.mp3")
        assert state.queue_remove(5) is False
        assert state.queue == ["a.mp3"]

    def test_queue_remove_negative_index(self):
        state = ServerState()
        state.queue_add("a.mp3")
        assert state.queue_remove(-1) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`

Expected: `ModuleNotFoundError: No module named 'streamer.state'`

- [ ] **Step 3: Implement queue operations**

Create `src/streamer/state.py`:
```python
import threading
from collections import deque


class ServerState:
    def __init__(self):
        self._lock = threading.Lock()
        self._current_track: str | None = None
        self._queue: list[str] = []
        self._history: deque[str] = deque(maxlen=100)
        self._dj_enabled: bool = False

    @property
    def queue(self) -> list[str]:
        with self._lock:
            return list(self._queue)

    def queue_add(self, path: str) -> None:
        with self._lock:
            self._queue.append(path)

    def queue_remove(self, index: int) -> bool:
        with self._lock:
            if 0 <= index < len(self._queue):
                self._queue.pop(index)
                return True
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py::TestQueue -v`

Expected: 5 tests PASS.

- [ ] **Step 5: Write failing tests for history, current_track, dj_enabled**

Append to `tests/test_state.py`:
```python
class TestHistory:
    def test_history_starts_empty(self):
        state = ServerState()
        assert state.history == []

    def test_history_push(self):
        state = ServerState()
        state.history_push("a.mp3")
        state.history_push("b.mp3")
        assert state.history == ["a.mp3", "b.mp3"]

    def test_history_max_100(self):
        state = ServerState()
        for i in range(150):
            state.history_push(f"{i}.mp3")
        assert len(state.history) == 100
        assert state.history[0] == "50.mp3"
        assert state.history[-1] == "149.mp3"


class TestCurrentTrack:
    def test_starts_none(self):
        state = ServerState()
        assert state.current_track is None

    def test_set_and_get(self):
        state = ServerState()
        state.current_track = "test.mp3"
        assert state.current_track == "test.mp3"


class TestDJToggle:
    def test_starts_disabled(self):
        state = ServerState()
        assert state.dj_enabled is False

    def test_toggle_on(self):
        state = ServerState()
        state.dj_enabled = True
        assert state.dj_enabled is True

    def test_toggle_off(self):
        state = ServerState()
        state.dj_enabled = True
        state.dj_enabled = False
        assert state.dj_enabled is False
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`

Expected: `AttributeError` — `history`, `history_push`, `current_track`, `dj_enabled` not defined.

- [ ] **Step 7: Implement history, current_track, dj_enabled**

Add to `ServerState` class in `src/streamer/state.py`:
```python
    @property
    def current_track(self) -> str | None:
        with self._lock:
            return self._current_track

    @current_track.setter
    def current_track(self, path: str) -> None:
        with self._lock:
            self._current_track = path

    @property
    def history(self) -> list[str]:
        with self._lock:
            return list(self._history)

    def history_push(self, path: str) -> None:
        with self._lock:
            self._history.append(path)

    @property
    def dj_enabled(self) -> bool:
        with self._lock:
            return self._dj_enabled

    @dj_enabled.setter
    def dj_enabled(self, value: bool) -> None:
        with self._lock:
            self._dj_enabled = value
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`

Expected: All 13 tests PASS.

- [ ] **Step 9: Write failing tests for transition methods**

Append to `tests/test_state.py`:
```python
class TestAdvance:
    def test_advance_pops_queue(self):
        state = ServerState()
        state.current_track = "current.mp3"
        state.queue_add("next.mp3")
        result = state.advance()
        assert result == "next.mp3"
        assert state.current_track == "next.mp3"
        assert state.history == ["current.mp3"]

    def test_advance_empty_queue_returns_none(self):
        state = ServerState()
        state.current_track = "current.mp3"
        result = state.advance()
        assert result is None
        assert state.current_track is None
        assert state.history == ["current.mp3"]

    def test_advance_no_current_track(self):
        state = ServerState()
        state.queue_add("next.mp3")
        result = state.advance()
        assert result == "next.mp3"
        assert state.history == []


class TestGoPrevious:
    def test_go_previous_basic(self):
        state = ServerState()
        state.history_push("prev.mp3")
        state.current_track = "current.mp3"
        result = state.go_previous()
        assert result == "prev.mp3"
        assert state.current_track == "prev.mp3"
        assert state.queue == ["current.mp3"]

    def test_go_previous_stacks_queue(self):
        state = ServerState()
        state.history_push("08.mp3")
        state.history_push("09.mp3")
        state.current_track = "10.mp3"

        state.go_previous()
        assert state.current_track == "09.mp3"
        assert state.queue == ["10.mp3"]

        state.go_previous()
        assert state.current_track == "08.mp3"
        assert state.queue == ["09.mp3", "10.mp3"]

    def test_go_previous_no_history_returns_none(self):
        state = ServerState()
        state.current_track = "current.mp3"
        result = state.go_previous()
        assert result is None
        assert state.current_track == "current.mp3"
        assert state.queue == []

    def test_go_previous_preserves_existing_queue(self):
        state = ServerState()
        state.history_push("prev.mp3")
        state.current_track = "current.mp3"
        state.queue_add("queued.mp3")
        state.go_previous()
        assert state.queue == ["current.mp3", "queued.mp3"]


class TestPlayNow:
    def test_play_now_pushes_current_to_history(self):
        state = ServerState()
        state.current_track = "current.mp3"
        state.play_now("new.mp3")
        assert state.current_track == "new.mp3"
        assert state.history == ["current.mp3"]

    def test_play_now_no_current(self):
        state = ServerState()
        state.play_now("new.mp3")
        assert state.current_track == "new.mp3"
        assert state.history == []

    def test_play_now_does_not_affect_queue(self):
        state = ServerState()
        state.current_track = "current.mp3"
        state.queue_add("queued.mp3")
        state.play_now("new.mp3")
        assert state.queue == ["queued.mp3"]
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v -k "Advance or Previous or PlayNow"`

Expected: `AttributeError` — `advance`, `go_previous`, `play_now` not defined.

- [ ] **Step 11: Implement transition methods**

Add to `ServerState` class in `src/streamer/state.py`:
```python
    def advance(self) -> str | None:
        with self._lock:
            if self._current_track:
                self._history.append(self._current_track)
            if self._queue:
                self._current_track = self._queue.pop(0)
                return self._current_track
            self._current_track = None
            return None

    def go_previous(self) -> str | None:
        with self._lock:
            if not self._history:
                return None
            if self._current_track:
                self._queue.insert(0, self._current_track)
            self._current_track = self._history.pop()
            return self._current_track

    def play_now(self, path: str) -> None:
        with self._lock:
            if self._current_track:
                self._history.append(self._current_track)
            self._current_track = path
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`

Expected: All 24 tests PASS.

- [ ] **Step 13: Commit**

```bash
git add src/streamer/state.py tests/test_state.py
git commit -m "feat: state module with queue, history, and track transitions"
```

---

### Task 3: Scanner Module

**Files:**
- Create: `src/streamer/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write failing tests for scan and pick_random**

Create `tests/test_scanner.py`:
```python
from pathlib import Path

import pytest

from streamer.scanner import Scanner, AUDIO_EXTENSIONS


class TestScan:
    def test_finds_audio_files(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        files = scanner.scan()
        assert len(files) == 4
        assert all(f.suffix.lower() in AUDIO_EXTENSIONS for f in files)

    def test_excludes_non_audio(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        files = scanner.scan()
        names = [f.name for f in files]
        assert "notes.txt" not in names

    def test_handles_missing_root(self, tmp_path):
        scanner = Scanner(roots=[tmp_path / "nonexistent"])
        files = scanner.scan()
        assert files == []

    def test_handles_empty_root(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        scanner = Scanner(roots=[empty])
        files = scanner.scan()
        assert files == []


class TestPickRandom:
    def test_returns_audio_file(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        picked = scanner.pick_random()
        assert picked.exists()
        assert picked.suffix.lower() in AUDIO_EXTENSIONS

    def test_raises_on_no_files(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        scanner = Scanner(roots=[empty])
        with pytest.raises(RuntimeError):
            scanner.pick_random()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scanner.py -v`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement scan and pick_random**

Create `src/streamer/scanner.py`:
```python
import random
from pathlib import Path

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".ogg", ".wav", ".flac",
    ".m4a", ".wma", ".aac", ".opus", ".m4r",
})

DEFAULT_ROOTS = [Path(r"D:\entertainment"), Path(r"D:\Podcast")]


class Scanner:
    def __init__(self, roots: list[Path] | None = None):
        self.roots = roots if roots is not None else DEFAULT_ROOTS

    def scan(self) -> list[Path]:
        files = []
        for root in self.roots:
            if not root.exists():
                continue
            for f in root.rglob("*"):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(f)
        return files

    def pick_random(self) -> Path:
        files = self.scan()
        if not files:
            raise RuntimeError("No audio files found in media folders")
        return random.choice(files)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scanner.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 5: Write failing tests for browse helpers**

Append to `tests/test_scanner.py`:
```python
class TestResolveBrowsePath:
    def test_resolves_root_folder(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        resolved = scanner.resolve_browse_path("entertainment")
        assert resolved == test_media_dir / "entertainment"

    def test_resolves_subfolder(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        resolved = scanner.resolve_browse_path("entertainment/Test Show/season 01")
        assert resolved == test_media_dir / "entertainment" / "Test Show" / "season 01"

    def test_resolves_file(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        resolved = scanner.resolve_browse_path("entertainment/Test Show/season 01/01.mp3")
        assert resolved is not None
        assert resolved.is_file()

    def test_rejects_unknown_root(self, test_media_dir):
        scanner = Scanner(roots=[test_media_dir / "entertainment"])
        assert scanner.resolve_browse_path("unknown/folder") is None

    def test_rejects_path_traversal(self, test_media_dir):
        scanner = Scanner(roots=[test_media_dir / "entertainment"])
        assert scanner.resolve_browse_path("entertainment/../../etc") is None

    def test_rejects_nonexistent_path(self, test_media_dir):
        scanner = Scanner(roots=[test_media_dir / "entertainment"])
        assert scanner.resolve_browse_path("entertainment/no_such_folder") is None


class TestListDirectory:
    def test_lists_dirs_and_audio_files(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        path = test_media_dir / "entertainment" / "Test Show" / "season 01"
        dirs, files = scanner.list_directory(path)
        assert dirs == []
        assert "01.mp3" in files
        assert "02.mp3" in files
        assert "03.mp3" in files
        assert "notes.txt" not in files

    def test_lists_subdirectories(self, test_media_dir):
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
        ])
        path = test_media_dir / "entertainment"
        dirs, files = scanner.list_directory(path)
        assert "Test Show" in dirs
        assert files == []
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_scanner.py -v -k "Resolve or ListDir"`

Expected: `AttributeError` — methods not defined.

- [ ] **Step 7: Implement browse helpers**

Add to `Scanner` class in `src/streamer/scanner.py`:
```python
    def resolve_browse_path(self, browse_path: str) -> Path | None:
        parts = Path(browse_path).parts
        if not parts:
            return None

        root_name = parts[0]
        for root in self.roots:
            if root.name == root_name:
                result = root
                for part in parts[1:]:
                    if part == "..":
                        return None
                    result = result / part
                try:
                    result.resolve().relative_to(root.resolve())
                except ValueError:
                    return None
                return result if result.exists() else None
        return None

    def list_directory(self, path: Path) -> tuple[list[str], list[str]]:
        dirs = sorted(d.name for d in path.iterdir() if d.is_dir())
        files = sorted(
            f.name for f in path.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        )
        return dirs, files
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_scanner.py -v`

Expected: All 14 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/streamer/scanner.py tests/test_scanner.py
git commit -m "feat: scanner module with file discovery and browse path resolution"
```

---

### Task 4: Context Module

**Files:**
- Create: `src/streamer/context.py`
- Create: `tests/test_context.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_context.py`:
```python
from streamer.context import parse_track_context, format_track_context


class TestParseTrackContext:
    def test_entertainment_full_path(self):
        ctx = parse_track_context(
            r"D:\entertainment\Family Guy\season 09\04.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "entertainment"
        assert ctx["show"] == "Family Guy"
        assert ctx["season"] == 9
        assert ctx["episode"] == "04"
        assert ctx["filename"] == "04.mp3"

    def test_entertainment_no_season_number(self):
        ctx = parse_track_context(
            r"D:\entertainment\Misc Show\bonus\track.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "entertainment"
        assert ctx["show"] == "Misc Show"
        assert "season" not in ctx

    def test_podcast_path(self):
        ctx = parse_track_context(
            r"D:\Podcast\My Favorite Murder\287.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "podcast"
        assert ctx["podcast"] == "My Favorite Murder"
        assert ctx["episode"] == "287"

    def test_unknown_path(self):
        ctx = parse_track_context(
            r"C:\other\file.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "unknown"
        assert ctx["filename"] == "file.mp3"


class TestFormatTrackContext:
    def test_entertainment_format(self):
        ctx = {
            "source": "entertainment",
            "show": "Family Guy",
            "season": 9,
            "episode": "04",
            "filename": "04.mp3",
        }
        result = format_track_context(ctx)
        assert "Family Guy" in result
        assert "Season 9" in result
        assert "Episode 04" in result

    def test_podcast_format(self):
        ctx = {
            "source": "podcast",
            "podcast": "My Favorite Murder",
            "episode": "287",
            "filename": "287.mp3",
        }
        result = format_track_context(ctx)
        assert "My Favorite Murder" in result
        assert "287" in result

    def test_unknown_format(self):
        ctx = {"source": "unknown", "filename": "random.mp3"}
        result = format_track_context(ctx)
        assert "random.mp3" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context.py -v`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement context module**

Create `src/streamer/context.py`:
```python
import re
from pathlib import PurePath


def parse_track_context(
    file_path: str,
    entertainment_root: str = r"D:\entertainment",
    podcast_root: str = r"D:\Podcast",
) -> dict:
    path = PurePath(file_path)

    try:
        rel = path.relative_to(entertainment_root)
        parts = rel.parts
        ctx: dict = {"source": "entertainment", "filename": path.name}
        if len(parts) >= 1:
            ctx["show"] = parts[0]
        if len(parts) >= 2:
            season_match = re.search(r"(\d+)", parts[1])
            if season_match:
                ctx["season"] = int(season_match.group(1))
        if len(parts) >= 3:
            ctx["episode"] = path.stem
        return ctx
    except ValueError:
        pass

    try:
        rel = path.relative_to(podcast_root)
        parts = rel.parts
        ctx = {"source": "podcast", "filename": path.name}
        if len(parts) >= 1:
            ctx["podcast"] = parts[0]
        ctx["episode"] = path.stem
        return ctx
    except ValueError:
        pass

    return {"source": "unknown", "filename": path.name}


def format_track_context(ctx: dict) -> str:
    if ctx["source"] == "entertainment":
        parts = [ctx.get("show", "Unknown Show")]
        if "season" in ctx:
            parts.append(f"Season {ctx['season']}")
        if "episode" in ctx:
            parts.append(f"Episode {ctx['episode']}")
        return ", ".join(parts) + " (from entertainment)"

    if ctx["source"] == "podcast":
        name = ctx.get("podcast", "Unknown Podcast")
        ep = ctx.get("episode", "unknown")
        return f"{name}, episode {ep} (from podcast)"

    return ctx.get("filename", "Unknown file")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context.py -v`

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/streamer/context.py tests/test_context.py
git commit -m "feat: context module for parsing track metadata from file paths"
```

---

### Task 5: Ring Buffer

**Files:**
- Create: `src/streamer/pipeline.py` (ring buffer class only; pipeline comes in Task 6)
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for ring buffer**

Create `tests/test_pipeline.py`:
```python
from streamer.pipeline import RingBuffer


class TestRingBuffer:
    def test_write_and_read(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello")
        pos = 0
        data, new_pos = buf.read(pos)
        assert data == b"hello"
        assert new_pos == 5

    def test_read_at_current_position_returns_empty(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello")
        data, pos = buf.read(5)
        assert data == b""
        assert pos == 5

    def test_read_with_max_bytes(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello world")
        data, pos = buf.read(0, max_bytes=5)
        assert data == b"hello"
        assert pos == 5

    def test_wraparound_write(self):
        buf = RingBuffer(size=16)
        buf.write(b"A" * 12)
        buf.write(b"B" * 8)
        # Buffer wrapped: positions 0-19 written, buffer holds last 16 bytes
        # Earliest available = 20 - 16 = 4
        data, pos = buf.read(4)
        assert len(data) == 16
        assert data == b"A" * 8 + b"B" * 8

    def test_lapped_reader_returns_none(self):
        buf = RingBuffer(size=16)
        buf.write(b"A" * 20)
        # Reader at position 0 is lapped (earliest is 4)
        data, pos = buf.read(0)
        assert data is None

    def test_multiple_readers(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello")
        data1, pos1 = buf.read(0)
        data2, pos2 = buf.read(0)
        assert data1 == data2 == b"hello"
        assert pos1 == pos2 == 5

    def test_get_current_position(self):
        buf = RingBuffer(size=1024)
        assert buf.get_current_position() == 0
        buf.write(b"hello")
        assert buf.get_current_position() == 5

    def test_headers(self):
        buf = RingBuffer(size=1024)
        assert buf.get_headers() == b""
        buf.set_headers(b"OggS_header_data")
        assert buf.get_headers() == b"OggS_header_data"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -v`

Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement RingBuffer**

Create `src/streamer/pipeline.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/streamer/pipeline.py tests/test_pipeline.py
git commit -m "feat: ring buffer for distributing OGG stream data to clients"
```

---

### Task 6: Audio Pipeline

**Files:**
- Modify: `src/streamer/pipeline.py` — add `AudioPipeline` class
- Modify: `tests/test_pipeline.py` — add integration tests

- [ ] **Step 1: Write integration test for pipeline**

Append to `tests/test_pipeline.py`:
```python
import time

from streamer.state import ServerState
from streamer.scanner import Scanner


class TestAudioPipeline:
    def test_pipeline_produces_ogg_data(self, test_media_dir):
        from streamer.pipeline import AudioPipeline

        state = ServerState()
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        pipeline = AudioPipeline(state, scanner)
        try:
            pipeline.start()
            time.sleep(2)

            assert state.current_track is not None
            headers = pipeline.ring_buffer.get_headers()
            assert headers[:4] == b"OggS"

            pos = pipeline.ring_buffer.get_current_position()
            assert pos > 0
        finally:
            pipeline.stop()

    def test_pipeline_request_next(self, test_media_dir):
        from streamer.pipeline import AudioPipeline

        state = ServerState()
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        pipeline = AudioPipeline(state, scanner)
        try:
            pipeline.start()
            time.sleep(1)

            first_track = state.current_track
            pipeline.request_next()
            time.sleep(1)

            assert state.current_track is not None
            assert first_track in [h for h in state.history]
        finally:
            pipeline.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py::TestAudioPipeline -v`

Expected: `ImportError` — `AudioPipeline` not defined.

- [ ] **Step 3: Implement AudioPipeline**

Add to `src/streamer/pipeline.py`, after the `RingBuffer` class:
```python
import subprocess
import time


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`

Expected: All 10 tests PASS (8 ring buffer + 2 pipeline integration).

- [ ] **Step 5: Commit**

```bash
git add src/streamer/pipeline.py tests/test_pipeline.py
git commit -m "feat: audio pipeline with FFmpeg decoder/encoder chain and track transitions"
```

---

### Task 7: Flask App, Landing Page, and Controls

**Files:**
- Create: `src/streamer/server.py`
- Create: `src/streamer/templates/index.html`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for landing page and control routes**

Create `tests/test_server.py`:
```python
import pytest

from streamer.state import ServerState
from streamer.scanner import Scanner
from streamer.server import create_app


@pytest.fixture
def app(test_media_dir):
    state = ServerState()
    scanner = Scanner(roots=[
        test_media_dir / "entertainment",
        test_media_dir / "Podcast",
    ])
    state.current_track = str(
        test_media_dir / "entertainment" / "Test Show" / "season 01" / "01.mp3"
    )
    return create_app(state=state, scanner=scanner)


@pytest.fixture
def client(app):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestLandingPage:
    def test_shows_current_track(self, client, app):
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "01.mp3" in html
        assert app.state.current_track in html

    def test_shows_empty_queue_message(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "empty" in html.lower()

    def test_shows_queue_items(self, client, app):
        app.state.queue_add(r"D:\entertainment\test\02.mp3")
        resp = client.get("/")
        html = resp.data.decode()
        assert "02.mp3" in html

    def test_has_navigation_links(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "/browse" in html
        assert "/stream.ogg" in html

    def test_has_accessible_structure(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "<h1" in html
        assert "<main" in html


class TestControls:
    def test_next_redirects(self, client):
        resp = client.post("/next")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/"

    def test_previous_redirects(self, client):
        resp = client.post("/previous")
        assert resp.status_code == 302

    def test_queue_add(self, client, app, test_media_dir):
        file_path = "entertainment/Test Show/season 01/01.mp3"
        resp = client.post("/queue/add", data={"file": file_path})
        assert resp.status_code == 302
        assert len(app.state.queue) == 1

    def test_queue_remove(self, client, app):
        app.state.queue_add("a.mp3")
        app.state.queue_add("b.mp3")
        resp = client.post("/queue/remove", data={"index": "0"})
        assert resp.status_code == 302
        assert app.state.queue == ["b.mp3"]

    def test_dj_toggle(self, client, app):
        assert app.state.dj_enabled is False
        resp = client.post("/dj/toggle")
        assert resp.status_code == 302
        assert app.state.dj_enabled is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -v`

Expected: `ModuleNotFoundError` — `streamer.server` not defined.

- [ ] **Step 3: Implement create_app and routes**

Create `src/streamer/server.py`:
```python
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, redirect, render_template, request

from streamer.scanner import Scanner
from streamer.state import ServerState


def create_app(state=None, scanner=None, pipeline=None):
    app = Flask(__name__)
    app.state = state or ServerState()
    app.scanner = scanner or Scanner()
    app.pipeline = pipeline

    @app.route("/")
    def index():
        current = app.state.current_track
        track_name = Path(current).name if current else "Nothing playing"
        track_path = current or ""
        queue_items = [
            {"name": Path(p).name, "path": p} for p in app.state.queue
        ]
        return render_template(
            "index.html",
            track_name=track_name,
            track_path=track_path,
            queue=queue_items,
            dj_enabled=app.state.dj_enabled,
        )

    @app.route("/next", methods=["POST"])
    def next_track():
        if app.pipeline:
            app.pipeline.request_next()
        return redirect("/")

    @app.route("/previous", methods=["POST"])
    def previous_track():
        if app.pipeline:
            app.pipeline.request_previous()
        return redirect("/")

    @app.route("/queue/add", methods=["POST"])
    def queue_add():
        browse_path = request.form.get("file", "")
        resolved = app.scanner.resolve_browse_path(browse_path)
        if resolved and resolved.is_file():
            app.state.queue_add(str(resolved))
        return redirect("/")

    @app.route("/queue/remove", methods=["POST"])
    def queue_remove():
        index = request.form.get("index", type=int)
        if index is not None:
            app.state.queue_remove(index)
        return redirect("/")

    @app.route("/dj/toggle", methods=["POST"])
    def dj_toggle():
        app.state.dj_enabled = not app.state.dj_enabled
        return redirect("/")

    @app.route("/play", methods=["POST"])
    def play():
        browse_path = request.form.get("file", "")
        resolved = app.scanner.resolve_browse_path(browse_path)
        if resolved and resolved.is_file():
            if app.pipeline:
                app.pipeline.request_play(str(resolved))
        return redirect("/")

    @app.route("/stream.ogg")
    def stream():
        import time as _time

        from flask import Response

        def generate():
            if not app.pipeline:
                return
            headers = app.pipeline.ring_buffer.get_headers()
            if headers:
                yield headers
            pos = app.pipeline.ring_buffer.get_current_position()
            while True:
                data, new_pos = app.pipeline.ring_buffer.read(pos)
                if data is None:
                    break
                if not data:
                    _time.sleep(0.05)
                    continue
                pos = new_pos
                yield data

        return Response(
            generate(),
            mimetype="audio/ogg",
            headers={"Cache-Control": "no-cache"},
        )

    return app
```

- [ ] **Step 4: Create landing page template**

Create `src/streamer/templates/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Streamer</title>
</head>
<body>
<main>
    <h1>Now Playing</h1>
    <p><strong>{{ track_name }}</strong> &mdash; {{ track_path }}</p>

    <section aria-label="Playback controls">
        <h2>Controls</h2>
        <form method="post" action="/previous" style="display:inline">
            <button type="submit">Previous</button>
        </form>
        <form method="post" action="/next" style="display:inline">
            <button type="submit">Next</button>
        </form>
    </section>

    <section aria-label="Queue">
        <h2>Queue</h2>
        {% if queue %}
        <ol>
            {% for item in queue %}
            <li>
                <strong>{{ item.name }}</strong> &mdash; {{ item.path }}
                <form method="post" action="/queue/remove" style="display:inline">
                    <input type="hidden" name="index" value="{{ loop.index0 }}">
                    <button type="submit" aria-label="Remove {{ item.name }} from queue">Remove</button>
                </form>
            </li>
            {% endfor %}
        </ol>
        {% else %}
        <p>Queue is empty. A random file will be chosen next.</p>
        {% endif %}
    </section>

    <section aria-label="AI DJ">
        <h2>AI DJ</h2>
        <p>DJ is currently <strong>{{ "on" if dj_enabled else "off" }}</strong>.</p>
        <form method="post" action="/dj/toggle">
            <button type="submit">Turn {{ "off" if dj_enabled else "on" }}</button>
        </form>
    </section>

    <nav aria-label="Actions">
        <h2>Actions</h2>
        <ul>
            <li><a href="/browse">Browse Files</a></li>
            <li><a href="/stream.ogg">Listen to Stream</a></li>
        </ul>
    </nav>
</main>
</body>
</html>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`

Expected: All 10 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/streamer/server.py src/streamer/templates/index.html tests/test_server.py
git commit -m "feat: Flask app with landing page, playback controls, and queue management"
```

---

### Task 8: File Browser

**Files:**
- Modify: `src/streamer/server.py` — add browse and play-action routes
- Create: `src/streamer/templates/browse.html`
- Create: `src/streamer/templates/play.html`
- Modify: `tests/test_server.py` — add browser tests

- [ ] **Step 1: Write failing tests for file browser**

Append to `tests/test_server.py`:
```python
class TestFileBrowser:
    def test_browse_root_shows_media_folders(self, client):
        resp = client.get("/browse/")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "entertainment" in html
        assert "Podcast" in html

    def test_browse_subfolder(self, client):
        resp = client.get("/browse/entertainment")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Test Show" in html

    def test_browse_audio_files(self, client):
        resp = client.get("/browse/entertainment/Test Show/season 01")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "01.mp3" in html
        assert "02.mp3" in html
        assert "notes.txt" not in html

    def test_browse_nonexistent_returns_404(self, client):
        resp = client.get("/browse/nonexistent")
        assert resp.status_code == 404

    def test_play_action_page(self, client):
        resp = client.get(
            "/browse/play?file=entertainment/Test Show/season 01/01.mp3"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "01.mp3" in html
        assert "Play Now" in html
        assert "Add to Queue" in html

    def test_play_action_nonexistent_returns_404(self, client):
        resp = client.get("/browse/play?file=nope/nope.mp3")
        assert resp.status_code == 404

    def test_play_now_via_post(self, client, app):
        resp = client.post(
            "/play",
            data={"file": "entertainment/Test Show/season 01/01.mp3"},
        )
        assert resp.status_code == 302

    def test_queue_add_via_browse(self, client, app):
        resp = client.post(
            "/queue/add",
            data={"file": "entertainment/Test Show/season 01/02.mp3"},
        )
        assert resp.status_code == 302
        assert len(app.state.queue) == 1
        assert "02.mp3" in app.state.queue[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py::TestFileBrowser -v`

Expected: 404 or template errors — browse routes and templates not yet created.

- [ ] **Step 3: Add browse routes to server.py**

Add the following routes inside `create_app()` in `src/streamer/server.py`, before the `return app` line:
```python
    @app.route("/browse/play")
    def browse_play():
        browse_path = request.args.get("file", "")
        resolved = app.scanner.resolve_browse_path(browse_path)
        if resolved is None or not resolved.is_file():
            abort(404)
        return render_template(
            "play.html",
            file_name=resolved.name,
            file_path=str(resolved),
            browse_path=browse_path,
        )

    @app.route("/browse/")
    @app.route("/browse/<path:subpath>")
    def browse(subpath=""):
        if not subpath:
            dirs = [
                {"name": root.name, "href": f"/browse/{quote(root.name)}"}
                for root in app.scanner.roots
                if root.exists()
            ]
            return render_template(
                "browse.html", dirs=dirs, files=[], breadcrumbs=[]
            )

        resolved = app.scanner.resolve_browse_path(subpath)
        if resolved is None or not resolved.is_dir():
            abort(404)

        dir_names, file_names = app.scanner.list_directory(resolved)
        dirs = [
            {"name": d, "href": f"/browse/{quote(subpath + '/' + d)}"}
            for d in dir_names
        ]
        files = [
            {
                "name": f,
                "href": f"/browse/play?file={quote(subpath + '/' + f)}",
            }
            for f in file_names
        ]

        parts = subpath.split("/")
        breadcrumbs = []
        for i, part in enumerate(parts):
            bc_path = "/".join(parts[: i + 1])
            breadcrumbs.append(
                {"name": part, "href": f"/browse/{quote(bc_path)}"}
            )

        return render_template(
            "browse.html", dirs=dirs, files=files, breadcrumbs=breadcrumbs
        )
```

**Important:** The `browse_play` route must be registered BEFORE the `browse` route with the `<path:subpath>` catch-all, otherwise Flask will match `/browse/play` as a subpath.

- [ ] **Step 4: Create browse template**

Create `src/streamer/templates/browse.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Browse Files - Streamer</title>
</head>
<body>
<main>
    <h1>Browse Files</h1>

    <nav aria-label="Breadcrumb">
        <p>
            <a href="/browse/">Root</a>
            {% for crumb in breadcrumbs %}
            / <a href="{{ crumb.href }}">{{ crumb.name }}</a>
            {% endfor %}
        </p>
    </nav>

    {% if dirs %}
    <section aria-label="Folders">
        <h2>Folders</h2>
        <ul>
            {% for dir in dirs %}
            <li><a href="{{ dir.href }}">{{ dir.name }}</a></li>
            {% endfor %}
        </ul>
    </section>
    {% endif %}

    {% if files %}
    <section aria-label="Audio files">
        <h2>Audio Files</h2>
        <ul>
            {% for file in files %}
            <li><a href="{{ file.href }}">{{ file.name }}</a></li>
            {% endfor %}
        </ul>
    </section>
    {% endif %}

    {% if not dirs and not files %}
    <p>This folder is empty.</p>
    {% endif %}

    <p><a href="/">Back to Control Panel</a></p>
</main>
</body>
</html>
```

- [ ] **Step 5: Create play action template**

Create `src/streamer/templates/play.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ file_name }} - Streamer</title>
</head>
<body>
<main>
    <h1>{{ file_name }}</h1>
    <p>{{ file_path }}</p>

    <section aria-label="Actions for this file">
        <form method="post" action="/play" style="display:inline">
            <input type="hidden" name="file" value="{{ browse_path }}">
            <button type="submit">Play Now</button>
        </form>
        <form method="post" action="/queue/add" style="display:inline">
            <input type="hidden" name="file" value="{{ browse_path }}">
            <button type="submit">Add to Queue</button>
        </form>
    </section>

    <p><a href="/browse/">Back to Browser</a></p>
    <p><a href="/">Back to Control Panel</a></p>
</main>
</body>
</html>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`

Expected: All 18 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/streamer/server.py src/streamer/templates/browse.html src/streamer/templates/play.html tests/test_server.py
git commit -m "feat: file browser with directory listing and play/queue actions"
```

---

### Task 9: Stream Endpoint and Integration Test

**Files:**
- Modify: `tests/test_server.py` — add stream integration test
- Modify: `src/streamer/__main__.py` — wire up full server

- [ ] **Step 1: Write integration test for stream endpoint**

Append to `tests/test_server.py`:
```python
import time

from streamer.pipeline import AudioPipeline


class TestStreamEndpoint:
    def test_stream_returns_ogg(self, test_media_dir):
        state = ServerState()
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        pipeline = AudioPipeline(state, scanner)
        app = create_app(state=state, scanner=scanner, pipeline=pipeline)
        app.config["TESTING"] = True

        pipeline.start()
        try:
            time.sleep(2)
            with app.test_client() as client:
                resp = client.get("/stream.ogg")
                assert resp.status_code == 200
                assert resp.content_type == "audio/ogg"
                data = resp.data
                assert data[:4] == b"OggS"
        finally:
            pipeline.stop()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py::TestStreamEndpoint -v`

Expected: PASS. The pipeline produces OGG data and the stream endpoint serves it with correct headers.

- [ ] **Step 3: Wire up the full server entry point**

Replace `src/streamer/__main__.py`:
```python
from streamer.pipeline import AudioPipeline
from streamer.scanner import Scanner
from streamer.server import create_app
from streamer.state import ServerState


def main():
    state = ServerState()
    scanner = Scanner()
    pipeline = AudioPipeline(state, scanner)

    app = create_app(state=state, scanner=scanner, pipeline=pipeline)
    pipeline.start()

    print("Streaming server running")
    print("  Control panel: http://localhost:8054")
    print("  Stream:        http://localhost:8054/stream.ogg")

    app.run(host="0.0.0.0", port=8054, threaded=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Manual smoke test**

Run:
```powershell
uv run python -m streamer
```

Verify:
1. Server starts without errors
2. Open `http://localhost:8054` in a browser — landing page loads, shows a track name
3. Open `http://localhost:8054/stream.ogg` — audio plays
4. Click Next — track changes
5. Browse files — folders and audio files visible
6. Stop server with Ctrl+C

- [ ] **Step 5: Commit**

```bash
git add src/streamer/__main__.py tests/test_server.py
git commit -m "feat: stream endpoint and full server entry point"
```

---

### Task 10: AI DJ Module

**Files:**
- Create: `src/streamer/dj.py`
- Create: `tests/test_dj.py`
- Modify: `src/streamer/pipeline.py` — integrate DJ into track transitions

- [ ] **Step 1: Write failing tests for DJ module**

Create `tests/test_dj.py`:
```python
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from streamer.dj import DJError, generate_commentary, generate_dj_clip, text_to_speech


class TestGenerateCommentary:
    @patch("streamer.dj.genai")
    def test_returns_text(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text="Great episode!")
        mock_genai.GenerativeModel.return_value = mock_model

        result = generate_commentary(
            "Family Guy, Season 9, Episode 4 (from entertainment)",
            "My Favorite Murder, episode 287 (from podcast)",
        )
        assert result == "Great episode!"

    @patch("streamer.dj.genai")
    def test_returns_none_on_failure(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API error")
        mock_genai.GenerativeModel.return_value = mock_model

        result = generate_commentary("prev", "next")
        assert result is None


class TestTextToSpeech:
    @patch("streamer.dj.texttospeech")
    def test_returns_audio_bytes(self, mock_tts):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.audio_content = b"fake_audio_data"
        mock_client.synthesize_speech.return_value = mock_response
        mock_tts.TextToSpeechClient.return_value = mock_client

        result = text_to_speech("Hello world")
        assert result == b"fake_audio_data"

    @patch("streamer.dj.texttospeech")
    def test_returns_none_on_failure(self, mock_tts):
        mock_client = MagicMock()
        mock_client.synthesize_speech.side_effect = Exception("TTS error")
        mock_tts.TextToSpeechClient.return_value = mock_client

        result = text_to_speech("Hello world")
        assert result is None


class TestGenerateDJClip:
    @patch("streamer.dj.text_to_speech")
    @patch("streamer.dj.generate_commentary")
    def test_returns_none_when_commentary_fails(self, mock_comm, mock_tts):
        mock_comm.return_value = None
        result = generate_dj_clip("prev.mp3", "next.mp3")
        assert result is None
        mock_tts.assert_not_called()

    @patch("streamer.dj.decode_to_pcm")
    @patch("streamer.dj.text_to_speech")
    @patch("streamer.dj.generate_commentary")
    def test_returns_none_when_tts_fails(self, mock_comm, mock_tts, mock_dec):
        mock_comm.return_value = "Nice episode!"
        mock_tts.return_value = None
        result = generate_dj_clip("prev.mp3", "next.mp3")
        assert result is None

    @patch("streamer.dj.decode_to_pcm")
    @patch("streamer.dj.text_to_speech")
    @patch("streamer.dj.generate_commentary")
    def test_returns_pcm_on_success(self, mock_comm, mock_tts, mock_dec):
        mock_comm.return_value = "Nice episode!"
        mock_tts.return_value = b"fake_mp3"
        mock_dec.return_value = b"fake_pcm"
        result = generate_dj_clip("prev.mp3", "next.mp3")
        assert result == b"fake_pcm"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dj.py -v`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement DJ module**

Create `src/streamer/dj.py`:
```python
import os
import subprocess

import google.generativeai as genai
from google.cloud import texttospeech

from streamer.context import format_track_context, parse_track_context

DJ_SYSTEM_PROMPT = (
    "You are a radio DJ on a personal streaming station that plays TV show "
    "audio and podcast episodes. Your style is witty, dry, sarcastic, and "
    "somewhat cynical. You make brief comments between tracks — riffing on "
    "the show, the specific episode, the podcast topic, or the transition "
    "between them. If you recognize the content, comment on it specifically. "
    "If you don't recognize it, keep it brief and vague rather than making "
    "things up. Keep it to 1-3 sentences. Never be mean-spirited, just "
    "amusingly jaded."
)


class DJError(Exception):
    pass


def generate_commentary(prev_context: str, next_context: str) -> str | None:
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"Just finished: {prev_context}\nComing up: {next_context}"
        response = model.generate_content(
            [{"role": "user", "parts": [prompt]}],
            generation_config={"max_output_tokens": 200},
        )
        return response.text.strip() if response.text else None
    except Exception:
        return None


def text_to_speech(text: str) -> bytes | None:
    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config,
        )
        return response.audio_content
    except Exception:
        return None


def decode_to_pcm(audio_bytes: bytes) -> bytes | None:
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-i", "pipe:0",
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "44100", "-ac", "2", "pipe:1",
            ],
            input=audio_bytes,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return proc.stdout if proc.returncode == 0 else None
    except Exception:
        return None


def generate_dj_clip(
    prev_track: str,
    next_track: str,
    entertainment_root: str = r"D:\entertainment",
    podcast_root: str = r"D:\Podcast",
) -> bytes | None:
    try:
        prev_ctx = format_track_context(
            parse_track_context(prev_track, entertainment_root, podcast_root)
        )
        next_ctx = format_track_context(
            parse_track_context(next_track, entertainment_root, podcast_root)
        )

        text = generate_commentary(prev_ctx, next_ctx)
        if not text:
            return None

        audio = text_to_speech(text)
        if not audio:
            return None

        return decode_to_pcm(audio)
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dj.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 5: Integrate DJ into pipeline**

Modify the `_run` method in `AudioPipeline` in `src/streamer/pipeline.py`. Add a `_last_track` attribute to `__init__`:

In `__init__`, add:
```python
        self._last_track: str | None = None
```

Replace the `_run` method:
```python
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
```

Add the DJ helper method:
```python
    def _play_dj_clip(self, prev_track: str, next_track: str):
        try:
            from streamer.dj import generate_dj_clip
            pcm = generate_dj_clip(prev_track, next_track)
            if pcm:
                self._encoder.stdin.write(pcm)
                self._encoder.stdin.flush()
        except Exception:
            pass
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -v`

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/streamer/dj.py src/streamer/pipeline.py tests/test_dj.py
git commit -m "feat: AI DJ module with Gemini commentary and Google Cloud TTS"
```

- [ ] **Step 8: Push to GitHub**

```bash
git push
```

---

## Post-Plan Notes

### Running the server
```powershell
uv run python -m streamer
```

### Running tests
```powershell
uv run pytest -v
```

### AI DJ setup (optional)
1. Set `GEMINI_API_KEY` environment variable
2. Set up Google Cloud credentials (`GOOGLE_APPLICATION_CREDENTIALS`)
3. Enable DJ from the control panel at `http://localhost:8054`

### Accessing from other devices
- Local network: `http://<windows-ip>:8054`
- Tailscale: `http://<tailscale-ip>:8054`
