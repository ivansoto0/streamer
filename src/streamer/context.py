import re
from pathlib import Path, PurePath


def _normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r"^(the|a|an)\s+", "", name)
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def load_notes(ctx: dict, notes_dir: str | None) -> str | None:
    if not notes_dir:
        return None

    notes_path = Path(notes_dir)
    if not notes_path.is_dir():
        return None

    show_name = ctx.get("show") or ctx.get("podcast")
    if not show_name:
        return None

    show_folder = None
    normalized_show = _normalize(show_name)
    for d in notes_path.iterdir():
        if d.is_dir() and _normalize(d.name) == normalized_show:
            show_folder = d
            break

    if not show_folder:
        return None

    parts = []

    show_note = show_folder / "show.md"
    if show_note.is_file():
        parts.append(
            f"[Show context]\n{show_note.read_text(encoding='utf-8').strip()}"
        )

    episode = ctx.get("episode")
    if episode:
        episode_note = None
        normalized_ep = _normalize(episode)

        season = ctx.get("season")
        if season is not None:
            for d in show_folder.iterdir():
                if d.is_dir():
                    m = re.search(r"(\d+)", d.name)
                    if m and int(m.group(1)) == season:
                        for f in d.iterdir():
                            if f.is_file() and _normalize(f.stem) == normalized_ep:
                                episode_note = f
                                break
                        break

        if episode_note is None:
            for f in show_folder.iterdir():
                if (
                    f.is_file()
                    and f.name != "show.md"
                    and _normalize(f.stem) == normalized_ep
                ):
                    episode_note = f
                    break

        if episode_note is not None:
            parts.append(
                f"[Episode context]\n"
                f"{episode_note.read_text(encoding='utf-8').strip()}"
            )

    return "\n\n".join(parts) if parts else None


def parse_track_context(file_path: str, *roots: str) -> dict:
    path = PurePath(file_path)

    for root in roots:
        try:
            rel = path.relative_to(root)
            parts = rel.parts
            root_name = PurePath(root).name.lower()

            if "podcast" in root_name:
                ctx: dict = {"source": "podcast", "filename": path.name}
                if len(parts) >= 1:
                    ctx["podcast"] = parts[0]
                ctx["episode"] = path.stem
                return ctx

            ctx = {"source": "entertainment", "filename": path.name}
            if len(parts) >= 1:
                ctx["show"] = parts[0]
            if len(parts) >= 2:
                season_match = re.search(r"(\d+)", parts[1])
                if season_match:
                    ctx["season"] = int(season_match.group(1))
            if len(parts) >= 3:
                ctx["episode"] = path.stem
            return ctx
        except ValueError:
            continue

    return {"source": "unknown", "filename": path.name}


def format_track_context(ctx: dict) -> str:
    if ctx["source"] == "entertainment":
        parts = [ctx.get("show", "Unknown Show")]
        if "season" in ctx:
            parts.append(f"Season {ctx['season']}")
        if "episode" in ctx:
            parts.append(f"Episode {ctx['episode']}")
        return ", ".join(parts) + " (from entertainment)"

    if ctx["source"] == "podcast":
        name = ctx.get("podcast", "Unknown Podcast")
        ep = ctx.get("episode", "unknown")
        return f"{name}, episode {ep} (from podcast)"

    return ctx.get("filename", "Unknown file")
