# Streaming Server Design

A local network audio streaming server that continuously broadcasts audio files as a radio-style OGG Vorbis stream, with a web control panel for playback control, queue management, and file browsing.

## Goals

- Stream audio from `D:\entertainment` and `D:\Podcast` folders as a single continuous 128kbps OGG Vorbis stream
- Radio-style: all listeners hear the same audio at the same point
- Web control panel for playback control, queue management, and file browsing
- Accessible to screen readers — semantic HTML, proper ARIA, keyboard navigation
- No public endpoint — local network and Tailscale only
- No persistence — state resets on restart
- AI DJ mode that inserts spoken commentary between tracks

## Architecture Overview

Single Python process with three concerns:

1. **Audio pipeline** — Background daemon thread managing FFmpeg. Decodes audio files to raw PCM, pipes into a long-running FFmpeg encoder that outputs continuous OGG Vorbis.
2. **Client distributor** — Shared ring buffer between encoder output and connected clients. New clients join mid-stream.
3. **Web control panel** — Flask serves the landing page and API endpoints. Reads and mutates shared state that the audio pipeline uses.

### Shared State

All state is in-memory, protected by a threading lock:

- `current_track` — path of the file currently streaming
- `queue` — ordered list of file paths to play next
- `history` — circular buffer of the last 100 played file paths
- `dj_enabled` — boolean toggle for AI DJ

## Audio Pipeline

### Decoder

Takes the current audio file, outputs raw PCM (signed 16-bit little-endian, 44100 Hz, stereo) to stdout. When a track ends, the decoder process exits. The pipeline thread detects this, picks the next track, and spawns a new decoder.

### Encoder

A single long-running FFmpeg process that reads raw PCM from stdin and writes OGG Vorbis 128kbps to stdout. Started once when the server starts. The pipeline thread feeds PCM from successive decoder processes into the encoder's stdin for seamless transitions.

### Ring Buffer

The encoder's stdout (OGG data) is read in chunks and written into a ~512KB ring buffer. Each connected client maintains its own read position. Clients that fall behind and get lapped are disconnected.

### Track Transitions

When the decoder exits (track finished):

1. Check queue — if non-empty, pop the first entry
2. If queue is empty, scan both media folders for audio files and pick one at random
3. Push the just-finished track onto the history ring (max 100)
4. Update `current_track`
5. If DJ is enabled, generate and stream a DJ clip before the next track
6. Spawn a new decoder and resume feeding PCM into the encoder

### Supported Audio Extensions

`.mp3`, `.ogg`, `.wav`, `.flac`, `.m4a`, `.wma`, `.aac`, `.opus`, `.m4r`

### File Scanning

Media folder scan happens at each random selection — not cached. Adding or removing files takes effect immediately.

## Web Control Panel

All pages use semantic HTML with proper headings, landmarks, labels, and link text for screen reader accessibility. No JavaScript required for core functionality.

### Landing Page (`/`)

Sections in order:

1. **Now Playing** — `<h1>` showing file name and full path. Example: `10.mp3 — D:\entertainment\Family Guy\season 03\10.mp3`
2. **Playback Controls** — Previous and Next buttons as POST forms. Previous loads the last track from history and pushes the interrupted track to the top of the queue. Next plays the top of the queue or picks random.
3. **Queue** — If non-empty, a numbered `<ol>` listing each queued file as "name — path" with a Remove button per entry. If empty, a message that the queue is empty and next track will be random.
4. **AI DJ** — Toggle form showing current state (on/off) with a button to flip it.
5. **Browse Files** — Link to `/browse`
6. **Listen** — Link to `/stream.ogg`

### File Browser (`/browse`, `/browse/<path>`)

Directory listing rooted at two top-level entries: `entertainment` and `Podcast`. Only audio files are shown. Clicking a folder navigates deeper. Clicking a file goes to the action page.

### File Action Page (`/browse/play?file=<path>`)

Shows the file name with two buttons: "Play Now" (switches immediately) and "Add to Queue" (appends). Both redirect to `/` after action.

### Endpoints

| Method | Path | Action |
|--------|------|--------|
| GET | `/` | Landing page |
| POST | `/next` | Skip to next track |
| POST | `/previous` | Go to previous track |
| POST | `/queue/remove` | Remove item from queue by index |
| POST | `/dj/toggle` | Toggle AI DJ on/off |
| GET | `/browse` | File browser root |
| GET | `/browse/<path>` | File browser subdirectory |
| GET | `/browse/play` | File action confirmation page |
| POST | `/play` | Play a file immediately |
| POST | `/queue/add` | Add a file to queue |
| GET | `/stream.ogg` | The audio stream |

## Previous Button Behavior

The server keeps the last 100 played file paths in a history ring.

- Pressing Previous loads the previous file from history and inserts the current (interrupted) file at the top of the queue.
- Pressing Previous multiple times stacks interrupted files at the top of the queue in order.
- Example: listening to `10.mp3`, hit previous → loads `09.mp3`, queue becomes `[10.mp3]`. Hit previous again → loads `08.mp3`, queue becomes `[09.mp3, 10.mp3]`.

## AI DJ Feature

When enabled, inserts a short spoken audio clip between tracks.

### Flow

1. Track finishes, pipeline picks the next track
2. The DJ generates a clip before the next track starts
3. Gemini receives a prompt with context about the track that just played and the track about to play
4. Gemini returns a short text script (1-3 sentences)
5. Text is sent to a TTS API which returns audio
6. Audio is decoded to PCM and fed into the encoder before the next track
7. Next track plays normally

### Context Extraction

File paths are parsed for context:

- Entertainment: `D:\entertainment\Family Guy\season 09\04.mp3` → show: "Family Guy", season: 9, episode: 4
- Podcast: `D:\Podcast\My Favorite Murder\287.mp3` → podcast: "My Favorite Murder", episode: "287"

Structured context is sent to the LLM, not raw paths.

### Persona

The DJ is aware it plays TV show audio and podcast episodes (not "songs"). Style: witty, dry, sarcastic, somewhat cynical. Comments on the specific episode/show/podcast when possible. Keeps it vague if it doesn't recognize the content. Never mean-spirited, just amusingly jaded. 1-3 sentences max.

### Configuration

- `GEMINI_API_KEY` and TTS API key read from environment variables
- If DJ is toggled on but keys aren't set, toggle fails with an error on the landing page
- If LLM or TTS call fails at runtime, the DJ clip is silently skipped — stream never stalls

### TTS Provider

Google Cloud Text-to-Speech initially, behind a simple function for easy swapping.

## Random Selection

Purely random — flat random across every audio file in both `entertainment` and `Podcast` folders. No weighting or alternation.

## Browse Scope

File browser is locked to `D:\entertainment` and `D:\Podcast` only. No access to other paths.

## Persistence

None. Server restart means fresh random file, empty queue, empty history.

## Testing Strategy

### Unit Tests (pytest)

- Queue management: add, remove, ordering, empty behavior
- History ring buffer: push, previous navigation, 100-item limit
- File scanner: filter audio extensions, skip non-audio, handle empty folders
- Path context parser: extract show/season/episode from entertainment paths, podcast name from podcast paths
- Track transition logic: queue priority over random, history updates
- Previous button behavior: interrupted track queuing, multiple previous stacking

### Integration Tests

- Audio pipeline: decoder→encoder chain produces valid OGG output
- Stream endpoint: client connects and receives OGG data
- Control panel endpoints: POST actions mutate state and redirect correctly

### E2E Tests

- Start server with test media folder containing short audio files
- Verify stream plays, next/previous work, queue operations, file browser correctness

### Test Fixtures

Short (1-2 second) audio files generated at test setup using FFmpeg. No real media files in the repo.

## Project Structure

```
D:\streamer\
├── pyproject.toml
├── uv.lock
├── src/
│   └── streamer/
│       ├── __init__.py
│       ├── server.py       # Entry point, Flask app, route handlers
│       ├── pipeline.py     # Audio pipeline thread, FFmpeg management, ring buffer
│       ├── state.py        # Shared state (queue, history, DJ toggle, lock)
│       ├── scanner.py      # Media folder scanning, audio file filtering
│       ├── context.py      # Path parser for DJ context extraction
│       ├── dj.py           # AI DJ: LLM call, TTS call, audio clip generation
│       └── templates/
│           ├── index.html
│           ├── browse.html
│           └── play.html
├── tests/
│   ├── conftest.py
│   ├── test_state.py
│   ├── test_scanner.py
│   ├── test_context.py
│   ├── test_pipeline.py
│   └── test_e2e.py
└── README.md
```

## Tech Stack

- **Python 3.13** with **uv** for project management
- **Flask** — HTTP server and templating
- **FFmpeg** — audio decoding and OGG Vorbis encoding
- **Google Generative AI (Gemini)** — DJ commentary generation
- **Google Cloud TTS** — text-to-speech for DJ clips
- **pytest** — testing

## Network Access

- Binds to `0.0.0.0:8054` for local network access
- Accessible via Tailscale IP as well
- No public endpoint, no authentication needed (private network only)
