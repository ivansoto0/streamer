from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, redirect, render_template, request

from streamer.scanner import Scanner
from streamer.state import ServerState


def create_app(state=None, scanner=None, pipeline=None):
    app = Flask(__name__)
    app.state = state or ServerState()
    app.scanner = scanner or Scanner()
    app.pipeline = pipeline

    @app.route("/")
    def index():
        current = app.state.current_track
        track_name = Path(current).name if current else "Nothing playing"
        track_path = current or ""
        queue_items = [
            {"name": Path(p).name, "path": p} for p in app.state.queue
        ]
        return render_template(
            "index.html",
            track_name=track_name,
            track_path=track_path,
            queue=queue_items,
            dj_enabled=app.state.dj_enabled,
        )

    @app.route("/next", methods=["POST"])
    def next_track():
        if app.pipeline:
            app.pipeline.request_next()
        return redirect("/")

    @app.route("/previous", methods=["POST"])
    def previous_track():
        if app.pipeline:
            app.pipeline.request_previous()
        return redirect("/")

    @app.route("/queue/add", methods=["POST"])
    def queue_add():
        browse_path = request.form.get("file", "")
        resolved = app.scanner.resolve_browse_path(browse_path)
        if resolved and resolved.is_file():
            app.state.queue_add(str(resolved))
        return redirect("/")

    @app.route("/queue/remove", methods=["POST"])
    def queue_remove():
        index = request.form.get("index", type=int)
        if index is not None:
            app.state.queue_remove(index)
        return redirect("/")

    @app.route("/dj/toggle", methods=["POST"])
    def dj_toggle():
        app.state.dj_enabled = not app.state.dj_enabled
        return redirect("/")

    @app.route("/play", methods=["POST"])
    def play():
        browse_path = request.form.get("file", "")
        resolved = app.scanner.resolve_browse_path(browse_path)
        if resolved and resolved.is_file():
            if app.pipeline:
                app.pipeline.request_play(str(resolved))
        return redirect("/")

    @app.route("/stream.ogg")
    def stream():
        import time as _time

        from flask import Response

        def generate():
            if not app.pipeline:
                return
            headers = app.pipeline.ring_buffer.get_headers()
            if headers:
                yield headers
            pos = app.pipeline.ring_buffer.get_current_position()
            while True:
                data, new_pos = app.pipeline.ring_buffer.read(pos)
                if data is None:
                    break
                if not data:
                    _time.sleep(0.05)
                    continue
                pos = new_pos
                yield data

        return Response(
            generate(),
            mimetype="audio/ogg",
            headers={"Cache-Control": "no-cache"},
        )

    return app
