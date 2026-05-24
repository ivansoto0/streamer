from streamer.context import format_track_context, parse_track_context


class TestParseTrackContext:
    def test_entertainment_full_path(self):
        ctx = parse_track_context(
            r"D:\entertainment\Family Guy\season 09\04.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "entertainment"
        assert ctx["show"] == "Family Guy"
        assert ctx["season"] == 9
        assert ctx["episode"] == "04"
        assert ctx["filename"] == "04.mp3"

    def test_entertainment_no_season_number(self):
        ctx = parse_track_context(
            r"D:\entertainment\Misc Show\bonus\track.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "entertainment"
        assert ctx["show"] == "Misc Show"
        assert "season" not in ctx

    def test_podcast_path(self):
        ctx = parse_track_context(
            r"D:\Podcast\My Favorite Murder\287.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "podcast"
        assert ctx["podcast"] == "My Favorite Murder"
        assert ctx["episode"] == "287"

    def test_unknown_path(self):
        ctx = parse_track_context(
            r"C:\other\file.mp3",
            entertainment_root=r"D:\entertainment",
            podcast_root=r"D:\Podcast",
        )
        assert ctx["source"] == "unknown"
        assert ctx["filename"] == "file.mp3"


class TestFormatTrackContext:
    def test_entertainment_format(self):
        ctx = {
            "source": "entertainment",
            "show": "Family Guy",
            "season": 9,
            "episode": "04",
            "filename": "04.mp3",
        }
        result = format_track_context(ctx)
        assert "Family Guy" in result
        assert "Season 9" in result
        assert "Episode 04" in result

    def test_podcast_format(self):
        ctx = {
            "source": "podcast",
            "podcast": "My Favorite Murder",
            "episode": "287",
            "filename": "287.mp3",
        }
        result = format_track_context(ctx)
        assert "My Favorite Murder" in result
        assert "287" in result

    def test_unknown_format(self):
        ctx = {"source": "unknown", "filename": "random.mp3"}
        result = format_track_context(ctx)
        assert "random.mp3" in result
