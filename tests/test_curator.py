import json
from unittest.mock import MagicMock, patch

import pytest

from streamer.curator import Curator
from streamer.state import ServerState


def _make_curator(state=None, scanner=None):
    state = state or ServerState()
    scanner = scanner or MagicMock()
    scanner.roots = []
    return Curator(state, scanner)


class TestHandleResponse:
    def test_pass_response(self):
        curator = _make_curator()
        path_lookup = {"Show/season 01/01": "/path/to/01.mp3"}
        curator._handle_response({"action": "pass"}, path_lookup)
        assert curator.state.queue == []

    def test_queue_response(self):
        curator = _make_curator()
        path_lookup = {
            "Show/season 01/01": "/path/to/01.mp3",
            "Show/season 01/02": "/path/to/02.mp3",
        }
        response = {
            "action": "queue",
            "tracks": ["Show/season 01/01", "Show/season 01/02"],
            "reason": "Marathon: Show Season 1",
        }
        curator._handle_response(response, path_lookup)
        assert len(curator.state.queue) == 2
        assert curator.state.queue[0] == "/path/to/01.mp3"
        assert curator.state.curator_reason == "Marathon: Show Season 1"

    def test_unresolved_tracks_skipped(self):
        curator = _make_curator()
        path_lookup = {"Show/season 01/01": "/path/to/01.mp3"}
        response = {
            "action": "queue",
            "tracks": ["Show/season 01/01", "Nonexistent/season 01/99"],
            "reason": "Test",
        }
        curator._handle_response(response, path_lookup)
        assert len(curator.state.queue) == 1

    def test_invalid_response_ignored(self):
        curator = _make_curator()
        curator._handle_response({"garbage": True}, {})
        assert curator.state.queue == []

    def test_empty_tracks_no_reason_set(self):
        curator = _make_curator()
        response = {"action": "queue", "tracks": ["bogus/path"], "reason": "Test"}
        curator._handle_response(response, {})
        assert curator.state.curator_reason is None


class TestCheck:
    @patch("streamer.curator.build_catalog")
    @patch.object(Curator, "_ask_ollama")
    def test_skips_when_disabled(self, mock_ollama, mock_catalog):
        curator = _make_curator()
        curator.state.curator_enabled = False
        curator._check()
        mock_ollama.assert_not_called()
        mock_catalog.assert_not_called()

    @patch("streamer.curator.build_catalog")
    @patch.object(Curator, "_ask_ollama")
    def test_skips_when_queue_nonempty(self, mock_ollama, mock_catalog):
        curator = _make_curator()
        curator.state.curator_enabled = True
        curator.state.queue_add("something.mp3")
        curator._check()
        mock_ollama.assert_not_called()

    @patch("streamer.curator.build_catalog")
    @patch.object(Curator, "_ask_ollama")
    def test_calls_ollama_when_enabled(self, mock_ollama, mock_catalog):
        mock_catalog.return_value = ("catalog text", {})
        mock_ollama.return_value = {"action": "pass"}
        curator = _make_curator()
        curator.state.curator_enabled = True
        curator._check()
        mock_ollama.assert_called_once()

    @patch("streamer.curator.build_catalog")
    @patch.object(Curator, "_ask_ollama")
    def test_handles_ollama_failure(self, mock_ollama, mock_catalog):
        mock_catalog.return_value = ("catalog text", {})
        mock_ollama.return_value = None
        curator = _make_curator()
        curator.state.curator_enabled = True
        curator._check()
        assert curator.state.queue == []

    @patch("streamer.curator.build_catalog")
    @patch.object(Curator, "_ask_ollama")
    def test_handles_invalid_json(self, mock_ollama, mock_catalog):
        mock_catalog.return_value = ("catalog text", {})
        mock_ollama.return_value = "not a dict"
        curator = _make_curator()
        curator.state.curator_enabled = True
        curator._check()
        assert curator.state.queue == []


class TestAskOllama:
    @patch("streamer.curator.OLLAMA_URL", "")
    def test_returns_none_without_url(self):
        curator = _make_curator()
        result = curator._ask_ollama("catalog", "history")
        assert result is None

    @patch("streamer.curator.OLLAMA_URL", "http://localhost:11434")
    @patch("streamer.curator.urllib.request.urlopen")
    def test_returns_parsed_json(self, mock_urlopen):
        response_body = json.dumps({
            "message": {"content": json.dumps({"action": "pass"})}
        }).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        curator = _make_curator()
        result = curator._ask_ollama("catalog", "history")
        assert result == {"action": "pass"}

    @patch("streamer.curator.OLLAMA_URL", "http://localhost:11434")
    @patch("streamer.curator.urllib.request.urlopen")
    def test_returns_none_on_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        curator = _make_curator()
        result = curator._ask_ollama("catalog", "history")
        assert result is None
