import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def test_media_dir(tmp_path):
    ent_dir = tmp_path / "entertainment" / "Test Show" / "season 01"
    ent_dir.mkdir(parents=True)
    pod_dir = tmp_path / "Podcast" / "Test Podcast"
    pod_dir.mkdir(parents=True)

    for i in range(3):
        filepath = ent_dir / f"{i + 1:02d}.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"sine=frequency={440 + i * 100}:duration=1",
                "-acodec", "libmp3lame", "-b:a", "128k",
                str(filepath),
            ],
            capture_output=True,
            check=True,
        )

    pod_file = pod_dir / "episode_01.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "sine=frequency=300:duration=1",
            "-acodec", "libmp3lame", "-b:a", "128k",
            str(pod_file),
        ],
        capture_output=True,
        check=True,
    )

    txt_file = ent_dir / "notes.txt"
    txt_file.write_text("not audio")

    return tmp_path
