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
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=DJ_SYSTEM_PROMPT,
        )
        prompt = f"Just finished: {prev_context}\nComing up: {next_context}"
        response = model.generate_content(
            prompt,
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
