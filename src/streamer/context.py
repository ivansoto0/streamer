import re
from pathlib import PurePath


def parse_track_context(
    file_path: str,
    entertainment_root: str = r"D:\entertainment",
    podcast_root: str = r"D:\Podcast",
) -> dict:
    path = PurePath(file_path)

    try:
        rel = path.relative_to(entertainment_root)
        parts = rel.parts
        ctx: dict = {"source": "entertainment", "filename": path.name}
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
        pass

    try:
        rel = path.relative_to(podcast_root)
        parts = rel.parts
        ctx = {"source": "podcast", "filename": path.name}
        if len(parts) >= 1:
            ctx["podcast"] = parts[0]
        ctx["episode"] = path.stem
        return ctx
    except ValueError:
        pass

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
