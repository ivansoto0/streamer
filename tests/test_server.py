import pytest

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
