import os
from unittest.mock import MagicMock, patch

from streamer.dj import generate_commentary, generate_dj_clip, text_to_speech


class TestGenerateCommentary:
    @patch("streamer.dj.genai")
    def test_returns_text(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text="Great episode!")
        mock_genai.GenerativeModel.return_value = mock_model

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
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

    @patch("streamer.dj.genai")
    def test_returns_none_without_api_key(self, mock_genai):
        with patch.dict("os.environ", {}, clear=True):
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
