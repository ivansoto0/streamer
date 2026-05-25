# Content Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to write free-form notes about shows and episodes that get injected into the DJ's Gemini prompt at commentary time.

**Architecture:** A `_normalize()` helper and `load_notes()` function are added to the existing `context.py` module. The DJ module passes parsed track context through `load_notes()` to find matching note files, then appends the note text to the Gemini prompt. Configuration is a single optional `NOTES_DIR` in `.env`.

**Tech Stack:** Python 3.13, pathlib, re, pytest

---

## File Map

- Modify: `src/streamer/config.py` — add `NOTES_DIR` setting
- Modify: `src/streamer/context.py` — add `_normalize()` and `load_notes()`
- Modify: `src/streamer/dj.py` — pass notes into prompt, update system prompt
- Modify: `.env.sample` — add `NOTES_DIR` field
- Modify: `tests/test_context.py` — normalization and note lookup tests
- Modify: `tests/test_dj.py` — integration test verifying notes reach the prompt

---

### Task 1: _normalize() helper function

**Files:**
- Modify: `tests/test_context.py`
- Modify: `src/streamer/context.py`

- [ ] **Step 1: Write the failing tests for _normalize**

Add to the end of `tests/test_context.py`:

```python
from streamer.context import _normalize


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Family Guy") == "family guy"

    def test_strip_leading_the(self):
        assert _normalize("The Blind Geek Zone") == "blind geek zone"

    def test_strip_leading_a(self):
        assert _normalize("A Cool Show") == "cool show"

    def test_strip_leading_an(self):
        assert _normalize("An Example") == "example"

    def test_hyphens_to_spaces(self):
        assert _normalize("blind-geek-zone") == "blind geek zone"

    def test_underscores_to_spaces(self):
        assert _normalize("blind_geek_zone") == "blind geek zone"

    def test_collapse_whitespace(self):
        assert _normalize("  blind   geek   zone  ") == "blind geek zone"

    def test_combined(self):
        assert _normalize("The  Blind-Geek_Zone") == "blind geek zone"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context.py::TestNormalize -v`
Expected: FAIL with `ImportError: cannot import name '_normalize'`

- [ ] **Step 3: Implement _normalize**

Add to `src/streamer/context.py` after the existing imports (line 2):

```python
def _normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r"^(the|a|an)\s+", "", name)
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name)
    return name.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context.py::TestNormalize -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/streamer/context.py tests/test_context.py
git commit -m "feat: add _normalize() for fuzzy name matching"
```

---

### Task 2: load_notes() function

**Files:**
- Modify: `tests/test_context.py`
- Modify: `src/streamer/context.py`

- [ ] **Step 1: Write the failing tests for load_notes**

Add to the end of `tests/test_context.py`:

```python
from streamer.context import load_notes


class TestLoadNotes:
    def test_show_level_note(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("This show is about testing.")
        ctx = {"source": "entertainment", "show": "Some Show"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nThis show is about testing."

    def test_episode_with_season(self, tmp_path):
        season_dir = tmp_path / "Some Show" / "season 09"
        season_dir.mkdir(parents=True)
        (season_dir / "02.md").write_text("The one about tests.")
        ctx = {"source": "entertainment", "show": "Some Show", "season": 9, "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nThe one about tests."

    def test_episode_flat_fallback(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "02.md").write_text("Flat episode note.")
        ctx = {"source": "entertainment", "show": "Some Show", "season": 9, "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nFlat episode note."

    def test_season_preferred_over_flat(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        season_dir = show_dir / "season 09"
        season_dir.mkdir(parents=True)
        (show_dir / "02.md").write_text("Flat note.")
        (season_dir / "02.md").write_text("Season note.")
        ctx = {"source": "entertainment", "show": "Some Show", "season": 9, "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nSeason note."

    def test_combines_show_and_episode(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Show info.")
        (show_dir / "02.md").write_text("Episode info.")
        ctx = {"source": "entertainment", "show": "Some Show", "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert "[Show context]\nShow info." in result
        assert "[Episode context]\nEpisode info." in result

    def test_podcast_uses_podcast_key(self, tmp_path):
        show_dir = tmp_path / "Example Podcast"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("A podcast about examples.")
        ctx = {"source": "podcast", "podcast": "Example Podcast", "episode": "287"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nA podcast about examples."

    def test_fuzzy_match_case(self, tmp_path):
        show_dir = tmp_path / "some show"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Found it.")
        ctx = {"source": "entertainment", "show": "Some Show"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nFound it."

    def test_fuzzy_match_article(self, tmp_path):
        show_dir = tmp_path / "blind geek zone"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Found via article strip.")
        ctx = {"source": "podcast", "podcast": "The Blind Geek Zone"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nFound via article strip."

    def test_fuzzy_match_hyphens(self, tmp_path):
        show_dir = tmp_path / "blind-geek-zone"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Found via hyphens.")
        ctx = {"source": "podcast", "podcast": "Blind Geek Zone"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nFound via hyphens."

    def test_no_match_returns_none(self, tmp_path):
        ctx = {"source": "entertainment", "show": "Nonexistent Show"}
        result = load_notes(ctx, str(tmp_path))
        assert result is None

    def test_no_dir_returns_none(self):
        ctx = {"source": "entertainment", "show": "Some Show"}
        assert load_notes(ctx, None) is None
        assert load_notes(ctx, "") is None

    def test_nonexistent_dir_returns_none(self):
        ctx = {"source": "entertainment", "show": "Some Show"}
        result = load_notes(ctx, r"C:\nonexistent\path\that\does\not\exist")
        assert result is None

    def test_unknown_source_returns_none(self, tmp_path):
        ctx = {"source": "unknown", "filename": "file.mp3"}
        result = load_notes(ctx, str(tmp_path))
        assert result is None

    def test_episode_normalize_match(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "Episode 5.md").write_text("Matched via normalize.")
        ctx = {"source": "entertainment", "show": "Some Show", "episode": "episode 5"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nMatched via normalize."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context.py::TestLoadNotes -v`
Expected: FAIL with `ImportError: cannot import name 'load_notes'`

- [ ] **Step 3: Implement load_notes**

Add to `src/streamer/context.py` after the `_normalize` function, before `parse_track_context`:

```python
from pathlib import Path, PurePath


def load_notes(ctx: dict, notes_dir: str | None) -> str | None:
    if not notes_dir:
        return None

    notes_path = Path(notes_dir)
    if not notes_path.is_dir():
        return None

    show_name = ctx.get("show") or ctx.get("podcast")
    if not show_name:
        return None

    show_folder = None
    normalized_show = _normalize(show_name)
    for d in notes_path.iterdir():
        if d.is_dir() and _normalize(d.name) == normalized_show:
            show_folder = d
            break

    if not show_folder:
        return None

    parts = []

    show_note = show_folder / "show.md"
    if show_note.is_file():
        parts.append(
            f"[Show context]\n{show_note.read_text(encoding='utf-8').strip()}"
        )

    episode = ctx.get("episode")
    if episode:
        episode_note = None
        normalized_ep = _normalize(episode)

        season = ctx.get("season")
        if season is not None:
            for d in show_folder.iterdir():
                if d.is_dir():
                    m = re.search(r"(\d+)", d.name)
                    if m and int(m.group(1)) == season:
                        for f in d.iterdir():
                            if f.is_file() and _normalize(f.stem) == normalized_ep:
                                episode_note = f
                                break
                        break

        if episode_note is None:
            for f in show_folder.iterdir():
                if (
                    f.is_file()
                    and f.name != "show.md"
                    and _normalize(f.stem) == normalized_ep
                ):
                    episode_note = f
                    break

        if episode_note is not None:
            parts.append(
                f"[Episode context]\n"
                f"{episode_note.read_text(encoding='utf-8').strip()}"
            )

    return "\n\n".join(parts) if parts else None
```

Also update the import at the top of `context.py` — change `from pathlib import PurePath` to `from pathlib import Path, PurePath`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context.py -v`
Expected: All tests PASS (existing + 14 new)

- [ ] **Step 5: Commit**

```bash
git add src/streamer/context.py tests/test_context.py
git commit -m "feat: add load_notes() with fuzzy show/episode matching"
```

---

### Task 3: DJ integration

**Files:**
- Modify: `src/streamer/config.py:20`
- Modify: `src/streamer/dj.py:6-7,9-24,31-47,86-111`
- Modify: `tests/test_dj.py`
- Modify: `.env.sample`

- [ ] **Step 1: Write the failing integration test**

Add to the end of `tests/test_dj.py`:

```python
class TestNotesIntegration:
    @patch("streamer.dj.genai")
    @patch("streamer.dj.GEMINI_API_KEY", "test-key")
    def test_commentary_includes_notes(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text="Great!")
        mock_genai.GenerativeModel.return_value = mock_model

        generate_commentary(
            "Some Show, Season 1, Episode 5 (from entertainment)",
            "Example Podcast, episode 287 (from podcast)",
            prev_notes="[Show context]\nA show about testing.",
            next_notes="[Show context]\nA podcast about examples.",
        )

        call_args = mock_model.generate_content.call_args
        prompt = call_args[0][0]
        assert "A show about testing." in prompt
        assert "A podcast about examples." in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dj.py::TestNotesIntegration -v`
Expected: FAIL with `TypeError: generate_commentary() got an unexpected keyword argument 'prev_notes'`

- [ ] **Step 3: Add NOTES_DIR to config.py**

Add to the end of `src/streamer/config.py`:

```python
_notes_dir = os.environ.get("NOTES_DIR", "")
NOTES_DIR = Path(_notes_dir) if _notes_dir.strip() else None
```

- [ ] **Step 4: Update generate_commentary signature and prompt in dj.py**

In `src/streamer/dj.py`, update the import line:

```python
from streamer.config import GEMINI_API_KEY, MEDIA_ROOTS, NOTES_DIR
from streamer.context import format_track_context, load_notes, parse_track_context
```

Update `DJ_SYSTEM_PROMPT` — add before the final "Keep it to 1-3 sentences" paragraph:

```python
DJ_SYSTEM_PROMPT = (
    "You are a radio DJ on a personal streaming station that plays TV show "
    "audio and podcast episodes. Your style is witty, dry, sarcastic, and "
    "somewhat cynical. You make brief comments between tracks.\n\n"
    "You will be given a show name, season number, and episode number. Use "
    "your knowledge to identify the specific episode and comment on its plot, "
    "characters, memorable moments, or themes. If you recognize the episode "
    "from the show name and number, reference it specifically.\n\n"
    "For podcasts, comment on the podcast's style, hosts, or general themes "
    "if you recognize it.\n\n"
    "If transitioning between very different genres, riff on the tonal "
    "whiplash.\n\n"
    "When notes are provided about the content, use them to make your "
    "commentary more specific and informed.\n\n"
    "Keep it to 1-3 sentences. Never be mean-spirited, just amusingly jaded. "
    "If you truly don't recognize the content, keep it brief rather than "
    "making things up."
)
```

Update `generate_commentary` to accept and use notes:

```python
def generate_commentary(
    prev_context: str,
    next_context: str,
    prev_notes: str | None = None,
    next_notes: str | None = None,
) -> str | None:
    try:
        if not GEMINI_API_KEY:
            return None
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=DJ_SYSTEM_PROMPT,
        )
        prompt = f"Just finished: {prev_context}"
        if prev_notes:
            prompt += f"\n{prev_notes}"
        prompt += f"\nComing up: {next_context}"
        if next_notes:
            prompt += f"\n{next_notes}"
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 1024},
        )
        return response.text.strip() if response.text else None
    except Exception:
        return None
```

Update `generate_dj_clip` to call `load_notes` and pass notes through:

```python
def generate_dj_clip(
    prev_track: str,
    next_track: str,
    roots: list | None = None,
) -> bytes | None:
    try:
        media_roots = roots if roots is not None else MEDIA_ROOTS
        root_strs = [str(r) for r in media_roots]
        prev_parsed = parse_track_context(prev_track, *root_strs)
        next_parsed = parse_track_context(next_track, *root_strs)
        prev_ctx = format_track_context(prev_parsed)
        next_ctx = format_track_context(next_parsed)

        notes_dir = str(NOTES_DIR) if NOTES_DIR else None
        prev_notes = load_notes(prev_parsed, notes_dir)
        next_notes = load_notes(next_parsed, notes_dir)

        text = generate_commentary(prev_ctx, next_ctx, prev_notes, next_notes)
        if not text:
            return None

        audio = text_to_speech(text)
        if not audio:
            return None

        return decode_to_pcm(audio)
    except Exception:
        return None
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `uv run pytest tests/test_dj.py tests/test_context.py -v`
Expected: All tests PASS

- [ ] **Step 6: Update .env.sample**

Add to the end of `.env.sample`:

```ini
# Directory containing show/episode notes for DJ commentary (optional)
# See README for structure details
NOTES_DIR=
```

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS (existing 86 + new 23 = 109 total)

- [ ] **Step 8: Commit**

```bash
git add src/streamer/config.py src/streamer/dj.py tests/test_dj.py .env.sample
git commit -m "feat: integrate content notes into DJ commentary prompt"
```
