import time

from streamer.pipeline import AudioPipeline, RingBuffer
from streamer.scanner import Scanner
from streamer.state import ServerState


class TestRingBuffer:
    def test_write_and_read(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello")
        pos = 0
        data, new_pos = buf.read(pos)
        assert data == b"hello"
        assert new_pos == 5

    def test_read_at_current_position_returns_empty(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello")
        data, pos = buf.read(5)
        assert data == b""
        assert pos == 5

    def test_read_with_max_bytes(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello world")
        data, pos = buf.read(0, max_bytes=5)
        assert data == b"hello"
        assert pos == 5

    def test_wraparound_write(self):
        buf = RingBuffer(size=16)
        buf.write(b"A" * 12)
        buf.write(b"B" * 8)
        data, pos = buf.read(4)
        assert len(data) == 16
        assert data == b"A" * 8 + b"B" * 8

    def test_lapped_reader_returns_none(self):
        buf = RingBuffer(size=16)
        buf.write(b"A" * 20)
        data, pos = buf.read(0)
        assert data is None

    def test_multiple_readers(self):
        buf = RingBuffer(size=1024)
        buf.write(b"hello")
        data1, pos1 = buf.read(0)
        data2, pos2 = buf.read(0)
        assert data1 == data2 == b"hello"
        assert pos1 == pos2 == 5

    def test_get_current_position(self):
        buf = RingBuffer(size=1024)
        assert buf.get_current_position() == 0
        buf.write(b"hello")
        assert buf.get_current_position() == 5

    def test_headers(self):
        buf = RingBuffer(size=1024)
        assert buf.get_headers() == b""
        buf.set_headers(b"OggS_header_data")
        assert buf.get_headers() == b"OggS_header_data"


class TestAudioPipeline:
    def test_pipeline_produces_ogg_data(self, test_media_dir):
        state = ServerState()
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        pipeline = AudioPipeline(state, scanner)
        try:
            pipeline.start()
            time.sleep(2)

            assert state.current_track is not None
            headers = pipeline.ring_buffer.get_headers()
            assert headers[:4] == b"OggS"

            pos = pipeline.ring_buffer.get_current_position()
            assert pos > 0
        finally:
            pipeline.stop()

    def test_pipeline_request_next(self, test_media_dir):
        state = ServerState()
        scanner = Scanner(roots=[
            test_media_dir / "entertainment",
            test_media_dir / "Podcast",
        ])
        pipeline = AudioPipeline(state, scanner)
        try:
            pipeline.start()
            time.sleep(1)

            first_track = state.current_track
            pipeline.request_next()
            assert state.current_track is not None
            assert first_track in state.history
        finally:
            pipeline.stop()
