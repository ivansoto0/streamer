# Streamer

A local network audio streaming server that continuously broadcasts audio files as a radio-style stream. All connected clients hear the same audio at the same point. Includes a web control panel for queue management and file browsing, plus an optional AI DJ that generates commentary between tracks.

## Features

- Radio-style streaming: all listeners share the same playback position
- OGG Vorbis and MP3 stream endpoints
- Web control panel with file browser, queue management, and playback controls
- Smart shuffle with folder-weighted selection and repeat avoidance
- AI DJ mode with Gemini-generated commentary and Google Cloud TTS
- HTTP Basic Auth for the control panel (streams stay open)
- Screen reader accessible UI

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [FFmpeg](https://ffmpeg.org/) on PATH

## Setup

1. Clone the repo and install dependencies:

   ```
   uv sync
   ```

2. Copy `.env.sample` to `.env` and configure your media folders:

   ```
   cp .env.sample .env
   ```

3. Start the server:

   ```
   uv run streamer
   ```

The server starts on `0.0.0.0:8054` by default:

- Control panel: `http://localhost:8054`
- OGG stream: `http://localhost:8054/stream.ogg`
- MP3 stream: `http://localhost:8054/stream.mp3`

## Configuration

All settings are in `.env` (see `.env.sample` for all options):

| Variable | Description | Default |
|----------|-------------|---------|
| `MEDIA_ROOTS` | Comma-separated paths to media folders | *(required)* |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8054` |
| `GEMINI_API_KEY` | Gemini API key for AI DJ (optional) | |
| `AUTH_USERNAME` | Basic auth username (optional) | |
| `AUTH_PASSWORD_HASH` | bcrypt hash of password (optional) | |

## Authentication

The control panel can be password-protected with HTTP Basic Auth. Stream endpoints (`/stream.ogg`, `/stream.mp3`) remain open so media players can connect without credentials.

1. Generate a password hash:

   ```
   uv run streamer-hashpw
   ```

2. Add the credentials to your `.env`:

   ```
   AUTH_USERNAME=admin
   AUTH_PASSWORD_HASH=$2b$12$...the hash from step 1...
   ```

3. Restart the server. The control panel will now require a username and password.

To disable auth, leave `AUTH_USERNAME` and `AUTH_PASSWORD_HASH` empty or remove them.

## Network Access

To listen from other devices on your local network, allow the server port through your firewall. On Windows, run this in an elevated PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Streamer" -Direction Inbound -LocalPort 8054 -Protocol TCP -Action Allow
```

Then connect from other devices at `http://<your-ip>:8054/stream.ogg`.

## AI DJ

The DJ generates witty commentary between tracks using Google Gemini and speaks it via Google Cloud Text-to-Speech. Enable it from the control panel.

### Setup

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) and add it to your `.env`:

   ```
   GEMINI_API_KEY=your-key-here
   ```

2. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install), then authenticate:

   ```
   gcloud auth application-default login
   ```

   Make sure the Text-to-Speech API is enabled in your GCP project.

3. Start the server and toggle DJ mode on from the control panel.

## Tests

```
uv run pytest
```
