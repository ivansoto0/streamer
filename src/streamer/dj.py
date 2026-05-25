import subprocess

import google.generativeai as genai
from google.cloud import texttospeech

from streamer.config import GEMINI_API_KEY, MEDIA_ROOTS
from streamer.context import format_track_context, parse_track_context

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
    "Keep it to 1-3 sentences. Never be mean-spirited, just amusingly jaded. "
    "If you truly don't recognize the content, keep it brief rather than "
    "making things up."
)


class DJError(Exception):
    pass


def generate_commentary(prev_context: str, next_context: str) -> str | None:
    try:
        if not GEMINI_API_KEY:
            return None
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=DJ_SYSTEM_PROMPT,
        )
        prompt = f"Just finished: {prev_context}\nComing up: {next_context}"
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 1024},
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
    roots: list | None = None,
) -> bytes | None:
    try:
        media_roots = roots if roots is not None else MEDIA_ROOTS
        root_strs = [str(r) for r in media_roots]
        prev_ctx = format_track_context(
            parse_track_context(prev_track, *root_strs)
        )
        next_ctx = format_track_context(
            parse_track_context(next_track, *root_strs)
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
