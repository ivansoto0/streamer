from streamer.context import _normalize, format_track_context, parse_track_context


class TestParseTrackContext:
    def test_entertainment_full_path(self):
        ctx = parse_track_context(
            r"C:\media\entertainment\Some Show\season 09\04.mp3",
            r"C:\media\entertainment", r"C:\media\podcasts",
        )
        assert ctx["source"] == "entertainment"
        assert ctx["show"] == "Some Show"
        assert ctx["season"] == 9
        assert ctx["episode"] == "04"
        assert ctx["filename"] == "04.mp3"

    def test_entertainment_no_season_number(self):
        ctx = parse_track_context(
            r"C:\media\entertainment\Misc Show\bonus\track.mp3",
            r"C:\media\entertainment", r"C:\media\podcasts",
        )
        assert ctx["source"] == "entertainment"
        assert ctx["show"] == "Misc Show"
        assert "season" not in ctx

    def test_podcast_path(self):
        ctx = parse_track_context(
            r"C:\media\podcasts\Example Podcast\287.mp3",
            r"C:\media\entertainment", r"C:\media\podcasts",
        )
        assert ctx["source"] == "podcast"
        assert ctx["podcast"] == "Example Podcast"
        assert ctx["episode"] == "287"

    def test_unknown_path(self):
        ctx = parse_track_context(
            r"C:\other\file.mp3",
            r"C:\media\entertainment", r"C:\media\podcasts",
        )
        assert ctx["source"] == "unknown"
        assert ctx["filename"] == "file.mp3"


class TestFormatTrackContext:
    def test_entertainment_format(self):
        ctx = {
            "source": "entertainment",
            "show": "Some Show",
            "season": 9,
            "episode": "04",
            "filename": "04.mp3",
        }
        result = format_track_context(ctx)
        assert "Some Show" in result
        assert "Season 9" in result
        assert "Episode 04" in result

    def test_podcast_format(self):
        ctx = {
            "source": "podcast",
            "podcast": "Example Podcast",
            "episode": "287",
            "filename": "287.mp3",
        }
        result = format_track_context(ctx)
        assert "Example Podcast" in result
        assert "287" in result

    def test_unknown_format(self):
        ctx = {"source": "unknown", "filename": "random.mp3"}
        result = format_track_context(ctx)
        assert "random.mp3" in result


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Family Guy") == "family guy"

    def test_strip_leading_the(self):
        assert _normalize("The Blind Geek Zone") == "blind geek zone"

    def test_strip_leading_a(self):
        assert _normalize("A Cool Show") == "cool show"

    def test_strip_leading_an(self):
        assert _normalize("An Example") == "example"

    def test_hyphens_to_spaces(self):
        assert _normalize("blind-geek-zone") == "blind geek zone"

    def test_underscores_to_spaces(self):
        assert _normalize("blind_geek_zone") == "blind geek zone"

    def test_collapse_whitespace(self):
        assert _normalize("  blind   geek   zone  ") == "blind geek zone"

    def test_combined(self):
        assert _normalize("The  Blind-Geek_Zone") == "blind geek zone"
