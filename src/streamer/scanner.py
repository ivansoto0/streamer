import random
from pathlib import Path

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".ogg", ".wav", ".flac",
    ".m4a", ".wma", ".aac", ".opus", ".m4r",
})

DEFAULT_ROOTS = [Path(r"D:\entertainment"), Path(r"D:\Podcast")]


class Scanner:
    def __init__(self, roots: list[Path] | None = None):
        self.roots = roots if roots is not None else DEFAULT_ROOTS

    def scan(self) -> list[Path]:
        files = []
        for root in self.roots:
            if not root.exists():
                continue
            for f in root.rglob("*"):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(f)
        return files

    def pick_random(self) -> Path:
        files = self.scan()
        if not files:
            raise RuntimeError("No audio files found in media folders")
        return random.choice(files)

    def resolve_browse_path(self, browse_path: str) -> Path | None:
        parts = Path(browse_path).parts
        if not parts:
            return None

        root_name = parts[0]
        for root in self.roots:
            if root.name == root_name:
                result = root
                for part in parts[1:]:
                    if part == "..":
                        return None
                    result = result / part
                try:
                    result.resolve().relative_to(root.resolve())
                except ValueError:
                    return None
                return result if result.exists() else None
        return None

    def list_directory(self, path: Path) -> tuple[list[str], list[str]]:
        dirs = sorted(d.name for d in path.iterdir() if d.is_dir())
        files = sorted(
            f.name for f in path.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        )
        return dirs, files
