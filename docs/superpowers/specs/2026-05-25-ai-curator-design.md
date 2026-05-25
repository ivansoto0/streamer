# AI Curator Design

## Goal

An AI-powered curator that uses a local Ollama model to occasionally override normal shuffle behavior — running marathons, favoring genres/moods, or mixing things up. The curator observes playback history, builds a catalog of available media, and pushes tracks into the existing queue when it decides to intervene.

## Architecture

The curator is a background thread that periodically consults a local Ollama model. It operates entirely through the existing queue mechanism — when it decides to intervene, it calls `state.queue_add()` for each track. The pipeline is unchanged; it already plays queued tracks before falling back to shuffle.

Three new modules:
- `catalog.py` — builds a compact text representation of the media library
- `curator.py` — background thread that talks to Ollama and manages intervention logic
- Additions to `state.py`, `server.py`, and templates for the toggle

The chat interface for conversational requests ("find me the episode where...") is out of scope for this spec and will be a follow-up.

## Configuration

New settings in `.env` and `config.py`:

```
OLLAMA_MODEL=llama3.1
OLLAMA_URL=http://localhost:11434
```

Both optional. If `OLLAMA_URL` is not set or Ollama is unreachable, the curator silently does nothing.

## Media Catalog

A new `catalog.py` module with a `build_catalog(scanner, notes_dir)` function. It scans the media roots and produces a compact text listing of every show, its seasons, episode counts, and any matching content notes from the notes system.

Example output:

```
[Entertainment]
Family Guy (seasons: 01, 02, 09)
  season 01: 01, 02, 03, 04, 05 (5 episodes)
  season 09: 01, 02, 03 (3 episodes)
  [Show notes: An animated sitcom about the Griffin family...]

Futurama (seasons: 01, 02)
  season 01: 01, 02, 03 (3 episodes)
  season 02: 01, 02 (2 episodes)

[Podcasts]
Blind Geek Zone (12 episodes)
  [Show notes: A podcast about assistive technology...]

Main Menu (8 episodes)
```

The catalog also builds and returns a path lookup — a dict mapping `(show_name, season, episode)` tuples to actual file paths. This is what the curator uses to convert the model's choices into real queue entries.

The catalog is rebuilt on each curator check. The scan is fast (just `iterdir` calls) and avoids stale data.

## Curator Engine

A new `curator.py` module with a `Curator` class.

### Lifecycle

- Started as a daemon thread by the pipeline when the server starts
- Runs independently from the pipeline — no shared locks, no pipeline code changes
- Respects `state.curator_enabled` toggle — when off, the thread idles
- Stops when the pipeline stops

### Check Interval

After each curator check, a random interval of 3-10 tracks is chosen before the next check. The curator tracks a `_tracks_since_check` counter that increments each time `state.history` grows (detected by comparing the last-seen history length snapshot). When the counter reaches the chosen interval, a check triggers and the counter resets. This avoids issues with `history`'s `maxlen=100` cap.

### Check Logic

On each check:

1. If `curator_enabled` is False, skip
2. If `state.queue` is non-empty (user queued tracks or previous curator plan still playing), skip
3. Build the media catalog via `build_catalog()`
4. Gather recent history (last 20 tracks from `state.history`)
5. Send catalog + history to Ollama with the curator system prompt
6. Parse the JSON response
7. If `"action": "queue"`, resolve track paths and call `state.queue_add()` for each
8. If `"action": "pass"` or parse fails, do nothing

### Ollama Communication

The curator sends an HTTP POST to `{OLLAMA_URL}/api/chat` with:
- `model`: from `OLLAMA_MODEL` config
- `messages`: system prompt + user message containing catalog and history
- `format`: `"json"` (Ollama's structured output mode)
- `stream`: `false`

### System Prompt

The system prompt tells the model:
- It is a music curator for a personal streaming station
- It should usually pass (most checks result in no intervention)
- When it intervenes, it can: run a marathon (sequential episodes from a season), favor a genre (queue several tracks from related shows), or create a themed mix
- It must respond with JSON: either `{"action": "pass"}` or `{"action": "queue", "tracks": [...], "reason": "..."}`
- Track entries in the `tracks` array use the format `show_name/season NN/episode` to identify files
- The `reason` field is a short human-readable explanation of why it intervened
- It should consider the recent history to avoid repetition and notice gaps

### Error Handling

- Ollama unreachable: log warning, skip this check, try again next interval
- Invalid JSON from model: treat as "pass", log warning
- Track paths that don't resolve: silently skip those tracks, queue the rest
- All errors are non-fatal — the curator never crashes the server

### Curator Reason Display

The `Curator` class stores the most recent `reason` string on state (a new `curator_reason` property on `ServerState`). The control panel template displays this above the queue when non-empty, so the user sees something like "Curator: Marathon — Futurama Season 2". The reason is cleared when the curator plan finishes (queue empties).

## State Changes

`ServerState` gets:
- `curator_enabled: bool` — toggle, same pattern as `dj_enabled`
- `curator_reason: str | None` — the curator's explanation for its current plan, displayed on the control panel

## Web UI Changes

- A curator toggle button on the control panel, same pattern as the DJ toggle
- The existing queue display shows curator-queued tracks naturally
- When `curator_reason` is set, display it above the queue (e.g., "Curator: Marathon — Futurama Season 2")
- A `/curator/toggle` POST endpoint, same pattern as `/dj/toggle`

## Testing

### Unit Tests (mocked Ollama)

**`tests/test_catalog.py`:**
- `test_catalog_entertainment_shows` — produces correct listing with seasons and episodes
- `test_catalog_podcasts` — lists podcast episodes without season structure
- `test_catalog_includes_notes` — show notes appear in catalog output
- `test_catalog_empty_roots` — returns empty catalog gracefully
- `test_catalog_path_lookup` — path lookup dict maps tuples to real file paths

**`tests/test_curator.py`:**
- `test_parse_pass_response` — curator correctly handles `{"action": "pass"}`
- `test_parse_queue_response` — curator parses track list and calls `state.queue_add()`
- `test_skips_when_disabled` — no Ollama call when `curator_enabled` is False
- `test_skips_when_queue_nonempty` — no Ollama call when queue has items
- `test_handles_ollama_failure` — logs warning, doesn't crash
- `test_handles_invalid_json` — treats malformed response as "pass"
- `test_handles_unresolved_tracks` — skips bad paths, queues valid ones

**`tests/test_state.py`:**
- `test_curator_enabled_toggle` — property works like `dj_enabled`
- `test_curator_reason` — set and get reason string

**`tests/test_server.py`:**
- `test_curator_toggle` — POST `/curator/toggle` toggles state

### Integration Test (real Ollama)

**`tests/test_curator.py`:**
- `test_ollama_integration` — marked with `pytest.mark.skipif` when Ollama is unreachable. Sends a real catalog and history to the configured model, asserts the response is valid JSON with either `{"action": "pass"}` or `{"action": "queue", "tracks": [...]}`.

## Files Changed

- Create: `src/streamer/catalog.py` — media catalog builder
- Create: `src/streamer/curator.py` — curator engine
- Create: `tests/test_catalog.py` — catalog tests
- Create: `tests/test_curator.py` — curator tests (unit + integration)
- Modify: `src/streamer/config.py` — add `OLLAMA_MODEL`, `OLLAMA_URL`
- Modify: `src/streamer/state.py` — add `curator_enabled`, `curator_reason`
- Modify: `src/streamer/pipeline.py` — start curator thread
- Modify: `src/streamer/server.py` — add `/curator/toggle` route, pass curator state to template
- Modify: `src/streamer/templates/index.html` — curator toggle button, curator reason display
- Modify: `.env.sample` — add `OLLAMA_MODEL`, `OLLAMA_URL`
- Modify: `tests/test_state.py` — curator state tests
- Modify: `tests/test_server.py` — curator toggle test
