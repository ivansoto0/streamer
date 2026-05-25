# Content Notes for DJ Commentary

## Goal

Allow users to write free-form notes about shows and episodes that get injected into the DJ's Gemini prompt, giving it richer context for commentary.

## Architecture

The notes system is a read-only lookup integrated into the existing `context.py` module. A configured directory contains markdown files organized by show. When the DJ prepares commentary, it loads any matching notes and appends them to the prompt alongside the track context that `format_track_context` already produces.

No changes to the web UI, pipeline, scanner, or server. The only modules affected are `config.py` (new setting), `context.py` (new function), and `dj.py` (passes notes into the prompt).

## Configuration

A new optional `NOTES_DIR` setting in `.env` and `config.py`. When not set, notes are not loaded and the DJ works exactly as it does today.

```
NOTES_DIR=D:\streamer-notes
```

## Notes Directory Structure

Notes mirror the show folder names from the media roots. Each show gets a subfolder. Inside, `show.md` provides show-level context. Episode notes use the audio filename stem (e.g., `05.md` for `05.mp3`). An optional season subfolder disambiguates when the same episode number exists across seasons.

```
NOTES_DIR/
  Blind Geek Zone/
    show.md              <- show-level context
    05.md                <- episode note (flat)
  Family Guy/
    show.md
    season 09/
      02.md              <- episode note (season-specific)
```

## File Lookup

`load_notes(ctx: dict, notes_dir: str) -> str | None` in `context.py`.

Input: the parsed track context dict (from `parse_track_context`, contains `show` or `podcast`, optionally `season` and `episode`) and the notes directory path.

Lookup order:

1. **Show note**: `NOTES_DIR/{matched_show_folder}/show.md`
2. **Episode note with season**: `NOTES_DIR/{matched_show_folder}/season {NN}/{episode}.md`
3. **Episode note flat fallback**: `NOTES_DIR/{matched_show_folder}/{episode}.md`

For podcasts, the show name comes from `ctx["podcast"]`. For entertainment, from `ctx["show"]`.

If both show and episode notes are found, they are concatenated:

```
[Show context]
The Blind Geek Zone is a podcast about assistive technology...

[Episode context]
This episode covers Jaws 5.2, a screen reader update...
```

If only one is found, just that one is returned. If neither is found, `None` is returned. If the notes directory itself doesn't exist on disk, `load_notes` returns `None` immediately without error.

## Fuzzy Matching

Show folder names are matched using normalization rather than exact string comparison. A `_normalize(name: str) -> str` helper function applies these transformations:

1. Lowercase
2. Strip leading articles ("the", "a", "an")
3. Replace hyphens and underscores with spaces
4. Collapse multiple spaces into one
5. Strip leading/trailing whitespace

This normalization is applied to both the show name from the media path and the folder names found in the notes directory. The first folder whose normalized name matches wins.

Examples:
- Media: "The Blind Geek Zone" -> normalized: "blind geek zone"
- Notes folder: "blind geek zone" -> normalized: "blind geek zone" -> MATCH
- Notes folder: "blind-geek-zone" -> normalized: "blind geek zone" -> MATCH
- Notes folder: "Blind Geek Zone" -> normalized: "blind geek zone" -> MATCH

The same normalization applies to episode filenames for consistency.

## DJ Integration

In `dj.py`, `generate_dj_clip` changes to:

1. After calling `parse_track_context` for both tracks, call `load_notes()` for each
2. Pass notes into `generate_commentary` as additional parameters
3. The prompt to Gemini becomes:

```
Just finished: Some Show, Season 1, Episode 5 (from entertainment)
[Notes: This show is about... This episode covers...]
Coming up: Example Podcast, episode 287 (from podcast)
[Notes: This podcast focuses on...]
```

Notes are only appended when they exist. When there are no notes for a track, the prompt looks exactly as it does today.

The DJ system prompt gets a small addition instructing it to use provided notes as context when available.

## Testing

All in existing test files:

**In `test_context.py`:**
- `test_load_notes_show_level` — finds and returns show.md content
- `test_load_notes_episode_with_season` — finds season subfolder episode note first
- `test_load_notes_episode_flat_fallback` — falls back to flat episode note when no season subfolder
- `test_load_notes_combines_show_and_episode` — concatenates both when both exist
- `test_load_notes_no_match` — returns None when no notes match
- `test_load_notes_no_dir` — returns None when notes_dir is None or empty
- `test_normalize_case_and_articles` — "The Blind Geek Zone" matches "blind geek zone"
- `test_normalize_hyphens_underscores` — "blind-geek-zone" matches "blind geek zone"

**In `test_dj.py`:**
- `test_commentary_includes_notes` — verifies notes text appears in the prompt sent to Gemini

## Files Changed

- `src/streamer/config.py` — add `NOTES_DIR`
- `src/streamer/context.py` — add `_normalize()` and `load_notes()`
- `src/streamer/dj.py` — pass notes into `generate_commentary`, update DJ system prompt
- `.env.sample` — add `NOTES_DIR` example
- `tests/test_context.py` — note lookup and normalization tests
- `tests/test_dj.py` — integration test for notes in prompt
