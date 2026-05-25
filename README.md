# Streamer

A local network audio streaming server that continuously broadcasts audio files from local folders as OGG Vorbis radio-style stream. All connected clients hear the same audio at the same point.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [FFmpeg](https://ffmpeg.org/) on PATH

## Setup

```
uv sync
```

## Usage

```
uv run streamer
```

The server starts on `0.0.0.0:8054`:

- Control panel: `http://localhost:8054`
- Stream: `http://localhost:8054/stream.ogg`

Configure your media folders in `.env` (see `.env.sample`).

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

To listen from other devices on your local network, you need to allow port 8054 through Windows Firewall. Run this in an elevated PowerShell (Run as Administrator):

```powershell
New-NetFirewallRule -DisplayName "Streamer" -Direction Inbound -LocalPort 8054 -Protocol TCP -Action Allow
```

Then connect from other devices at `http://<your-ip>:8054/stream.ogg`.

## AI DJ

The DJ generates witty commentary between tracks using Google Gemini and speaks it via Google Cloud Text-to-Speech. Enable it from the control panel.

### Setup

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) and set it before starting the server:

   ```
   set GEMINI_API_KEY=your-key-here
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
