"""Fetch the pinned MediaPipe model bundles. Assets are not committed (see .gitignore).

Run:  python -m pipeline.extract.assets
Downloads the LITE pose model + the hand model into assets/mediapipe/ (locked decision:
Pose Lite for mobile-realistic parity)."""

from __future__ import annotations

import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = REPO_ROOT / "assets" / "mediapipe"

MODELS: dict[str, str] = {
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task"
    ),
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    ),
}


def fetch(force: bool = False) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        dest = ASSETS_DIR / name
        if dest.exists() and not force:
            print(f"[assets] {name} already present ({dest.stat().st_size} bytes)")
            continue
        print(f"[assets] downloading {name} ...")
        urllib.request.urlretrieve(url, dest)  # noqa: S310 — trusted Google Storage URL
        print(f"[assets] saved {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    fetch()
