from streamer.pipeline import AudioPipeline
from streamer.scanner import Scanner
from streamer.server import create_app
from streamer.state import ServerState


def main():
    state = ServerState()
    scanner = Scanner()
    pipeline = AudioPipeline(state, scanner)

    app = create_app(state=state, scanner=scanner, pipeline=pipeline)
    pipeline.start()

    print("Streaming server running")
    print("  Control panel: http://localhost:8054")
    print("  Stream:        http://localhost:8054/stream.ogg")

    app.run(host="0.0.0.0", port=8054, threaded=True)


if __name__ == "__main__":
    main()
