from streamer.context import _normalize, format_track_context, load_notes, parse_track_context


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


class TestLoadNotes:
    def test_show_level_note(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("This show is about testing.")
        ctx = {"source": "entertainment", "show": "Some Show"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nThis show is about testing."

    def test_episode_with_season(self, tmp_path):
        season_dir = tmp_path / "Some Show" / "season 09"
        season_dir.mkdir(parents=True)
        (season_dir / "02.md").write_text("The one about tests.")
        ctx = {"source": "entertainment", "show": "Some Show", "season": 9, "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nThe one about tests."

    def test_episode_flat_fallback(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "02.md").write_text("Flat episode note.")
        ctx = {"source": "entertainment", "show": "Some Show", "season": 9, "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nFlat episode note."

    def test_season_preferred_over_flat(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        season_dir = show_dir / "season 09"
        season_dir.mkdir(parents=True)
        (show_dir / "02.md").write_text("Flat note.")
        (season_dir / "02.md").write_text("Season note.")
        ctx = {"source": "entertainment", "show": "Some Show", "season": 9, "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nSeason note."

    def test_combines_show_and_episode(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Show info.")
        (show_dir / "02.md").write_text("Episode info.")
        ctx = {"source": "entertainment", "show": "Some Show", "episode": "02"}
        result = load_notes(ctx, str(tmp_path))
        assert "[Show context]\nShow info." in result
        assert "[Episode context]\nEpisode info." in result

    def test_podcast_uses_podcast_key(self, tmp_path):
        show_dir = tmp_path / "Example Podcast"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("A podcast about examples.")
        ctx = {"source": "podcast", "podcast": "Example Podcast", "episode": "287"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nA podcast about examples."

    def test_fuzzy_match_case(self, tmp_path):
        show_dir = tmp_path / "some show"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Found it.")
        ctx = {"source": "entertainment", "show": "Some Show"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nFound it."

    def test_fuzzy_match_article(self, tmp_path):
        show_dir = tmp_path / "blind geek zone"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Found via article strip.")
        ctx = {"source": "podcast", "podcast": "The Blind Geek Zone"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nFound via article strip."

    def test_fuzzy_match_hyphens(self, tmp_path):
        show_dir = tmp_path / "blind-geek-zone"
        show_dir.mkdir()
        (show_dir / "show.md").write_text("Found via hyphens.")
        ctx = {"source": "podcast", "podcast": "Blind Geek Zone"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Show context]\nFound via hyphens."

    def test_no_match_returns_none(self, tmp_path):
        ctx = {"source": "entertainment", "show": "Nonexistent Show"}
        result = load_notes(ctx, str(tmp_path))
        assert result is None

    def test_no_dir_returns_none(self):
        ctx = {"source": "entertainment", "show": "Some Show"}
        assert load_notes(ctx, None) is None
        assert load_notes(ctx, "") is None

    def test_nonexistent_dir_returns_none(self):
        ctx = {"source": "entertainment", "show": "Some Show"}
        result = load_notes(ctx, r"C:\nonexistent\path\that\does\not\exist")
        assert result is None

    def test_unknown_source_returns_none(self, tmp_path):
        ctx = {"source": "unknown", "filename": "file.mp3"}
        result = load_notes(ctx, str(tmp_path))
        assert result is None

    def test_episode_normalize_match(self, tmp_path):
        show_dir = tmp_path / "Some Show"
        show_dir.mkdir()
        (show_dir / "Episode 5.md").write_text("Matched via normalize.")
        ctx = {"source": "entertainment", "show": "Some Show", "episode": "episode 5"}
        result = load_notes(ctx, str(tmp_path))
        assert result == "[Episode context]\nMatched via normalize."
