import time

import pytest

from streamer.pipeline import AudioPipeline
from streamer.scanner import Scanner
from streamer.server import create_app
from streamer.state import ServerState


@pytest.fixture
def app(test_media_dir):
    state = ServerState()
    scanner = Scanner(roots=[
        test_media_dir / "entertainment",
        test_media_dir / "Podcast",
    ])
    state.current_track = str(
        test_media_dir / "entertainment" / "Test Show" / "season 01" / "01.mp3"
    )
    return create_app(state=state, scanner=scanner)


@pytest.fixture
def client(app):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestLandingPage:
    def test_shows_current_track(self, client, app):
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "01.mp3" in html
        assert app.state.current_track in html

    def test_shows_empty_queue_message(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "empty" in html.lower()

    def test_shows_queue_items(self, client, app):
        app.state.queue_add(r"D:\entertainment\test\02.mp3")
        resp = client.get("/")
        html = resp.data.decode()
        assert "02.mp3" in html

    def test_has_navigation_links(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "/browse" in html
        assert "/stream.ogg" in html

    def test_has_accessible_structure(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "<h1" in html
        assert "<main" in html


class TestControls:
    def test_next_redirects(self, client):
        resp = client.post("/next")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/"

    def test_previous_redirects(self, client):
        resp = client.post("/previous")
        assert resp.status_code == 302

    def test_queue_add(self, client, app, test_media_dir):
        file_path = "entertainment/Test Show/season 01/01.mp3"
        resp = client.post("/queue/add", data={"file": file_path})
        assert resp.status_code == 302
        assert len(app.state.queue) == 1

    def test_queue_remove(self, client, app):
        app.state.queue_add("a.mp3")
        app.state.queue_add("b.mp3")
        resp = client.post("/queue/remove", data={"index": "0"})
        assert resp.status_code == 302
        assert app.state.queue == ["b.mp3"]

    def test_dj_toggle(self, client, app):
        assert app.state.dj_enabled is False
        resp = client.post("/dj/toggle")
        assert resp.status_code == 302
        assert app.state.dj_enabled is True


class TestFileBrowser:
    def test_browse_root_shows_media_folders(self, client):
        resp = client.get("/browse/")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "entertainment" in html
        assert "Podcast" in html

    def test_browse_subfolder(self, client):
        resp = client.get("/browse/entertainment")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Test Show" in html

    def test_browse_audio_files(self, client):
        resp = client.get("/browse/entertainment/Test Show/season 01")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "01.mp3" in html
        assert "02.mp3" in html
        assert "notes.txt" not in html

    def test_browse_nonexistent_returns_404(self, client):
        resp = client.get("/browse/nonexistent")
        assert resp.status_code == 404

    def test_play_action_page(self, client):
        resp = client.get(
            "/browse/play?file=entertainment/Test Show/season 01/01.mp3"
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "01.mp3" in html
        assert "Play Now" in html
        assert "Add to Queue" in html

    def test_play_action_nonexistent_returns_404(self, client):
        resp = client.get("/browse/play?file=nope/nope.mp3")
        assert resp.status_code == 404

    def test_play_now_via_post(self, client, app, test_media_dir):
        resp = client.post(
            "/play",
            data={"file": "entertainment/Test Show/season 01/01.mp3"},
        )
        assert resp.status_code == 302

    def test_queue_add_via_browse(self, client, app):
        resp = client.post(
            "/queue/add",
            data={"file": "entertainment/Test Show/season 01/02.mp3"},
        )
        assert resp.status_code == 302
        assert len(app.state.queue) == 1
        assert "02.mp3" in app.state.queue[0]


class TestAuth:
    def test_no_auth_required_when_unconfigured(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_auth_required_when_configured(self, app):
        import bcrypt

        password = "testpass"
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        app.config["TESTING"] = True
        import streamer.server as srv
        original_username = srv.AUTH_USERNAME
        original_hash = srv.AUTH_PASSWORD_HASH
        srv.AUTH_USERNAME = "admin"
        srv.AUTH_PASSWORD_HASH = hashed.decode("utf-8")
        try:
            with app.test_client() as c:
                resp = c.get("/")
                assert resp.status_code == 401

                from base64 import b64encode
                creds = b64encode(b"admin:testpass").decode("utf-8")
                resp = c.get("/", headers={"Authorization": f"Basic {creds}"})
                assert resp.status_code == 200

                creds = b64encode(b"admin:wrongpass").decode("utf-8")
                resp = c.get("/", headers={"Authorization": f"Basic {creds}"})
                assert resp.status_code == 401
        finally:
            srv.AUTH_USERNAME = original_username
            srv.AUTH_PASSWORD_HASH = original_hash

    def test_stream_open_when_auth_configured(self, app):
        import bcrypt

        hashed = bcrypt.hashpw(b"testpass", bcrypt.gensalt())

        app.config["TESTING"] = True
        import streamer.server as srv
        original_username = srv.AUTH_USERNAME
        original_hash = srv.AUTH_PASSWORD_HASH
        srv.AUTH_USERNAME = "admin"
        srv.AUTH_PASSWORD_HASH = hashed.decode("utf-8")
        try:
            with app.test_client() as c:
                resp = c.get("/stream.ogg")
                assert resp.status_code == 200
                resp.close()

                resp = c.get("/stream.mp3")
                assert resp.status_code == 200
                resp.close()
        finally:
            srv.AUTH_USERNAME = original_username
            srv.AUTH_PASSWORD_HASH = original_hash


class TestStreamEndpoint:
    def test_stream_returns_ogg(self, test_media_dir):
        state = ServerState()
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        pipeline = AudioPipeline(state, scanner)
        app = create_app(state=state, scanner=scanner, pipeline=pipeline)
        app.config["TESTING"] = True

        pipeline.start()
        try:
            time.sleep(2)
            with app.test_client() as client:
                resp = client.get("/stream.ogg")
                assert resp.status_code == 200
                assert resp.content_type == "audio/ogg"
                first_chunk = next(iter(resp.response))
                assert first_chunk[:4] == b"OggS"
                resp.close()
        finally:
            pipeline.stop()
