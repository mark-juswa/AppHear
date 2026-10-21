"""Build the androidTest fixtures for the pipelined-pose parity test (scheduling only).

Two recorded inputs, both fed identically to the serial and the pipelined Candidate01 analyzer:
  v3/                  the 51 real phone RGBA frames of the Stage 1 recorded parity test (copied)
  v3_pipeline_stream/  one contiguous signing stream: held-out DEV clips (ASL Citizen signer P12,
                       never in S2 FIT/CAL or recognizer TRAIN), every 4th 30 fps frame (~133 ms),
                       stored as JPEG and decoded on the device. The stream exists to make S2
                       events and WORD commits happen; it is not an accuracy sample.

The output directory is passed to Gradle as -PrecognitionV3FixtureDir. Nothing protected
(TEST, E6, Tier 3) is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

MANIFEST = Path(
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
    "heldout_dev_fullvideo_raw_01/manifest.json"
)
SIGNER = "asl_citizen:P12"
CLIPS = 12
FRAME_STEP = 4
STEP_MS = 1000.0 * FRAME_STEP / 30.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--stage1-fixtures", type=Path, required=True, help="dir holding v3/manifest.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    v3_out = args.out / "v3"
    if v3_out.exists():
        shutil.rmtree(v3_out)
    shutil.copytree(args.stage1_fixtures / "v3", v3_out)
    for row in json.loads((v3_out / "manifest.json").read_text())["fixtures"]:
        assert sha256(v3_out / row["asset"]) == row["sha256"], row["asset"]

    manifest = json.loads((args.data_root / MANIFEST).read_text())
    video_root = Path(manifest["video_root"])
    clips = sorted(
        (c for c in manifest["clips"] if c["signer"] == SIGNER and c["span_valid"]),
        key=lambda c: c["sample_id"],
    )[:CLIPS]
    stream_out = args.out / "v3_pipeline_stream"
    if stream_out.exists():
        shutil.rmtree(stream_out)
    stream_out.mkdir(parents=True)
    frames, spans = [], []
    for k, clip in enumerate(clips):
        video = video_root / (clip["sample_id"].split(":", 2)[2] + ".mp4")
        pattern = stream_out / f"clip{k:02d}_%04d.jpg"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video),
             "-vf", f"select=not(mod(n\\,{FRAME_STEP}))", "-vsync", "0", "-q:v", "2", str(pattern)],
            check=True,
        )
        written = sorted(stream_out.glob(f"clip{k:02d}_*.jpg"))
        first = len(frames)
        for path in written:
            frames.append({"asset": path.name, "sha256": sha256(path), "clip": k})
        spans.append({"clip": k, "gloss": clip["gloss"], "sample_id": clip["sample_id"],
                      "video_sha256": sha256(video), "first_frame": first, "frames": len(written)})
    (stream_out / "manifest.json").write_text(json.dumps({
        "schema": "apphear.v3_pipeline_stream_fixture.v1",
        "source": "held-out DEV clips (ASL Citizen) - parity input only, no accuracy claim",
        "signer": SIGNER,
        "frame_step_at_30fps": FRAME_STEP,
        "timestamp_step_ms": STEP_MS,
        "clips": spans,
        "frames": frames,
    }, indent=1) + "\n")
    print(f"v3 frames copied; stream: {len(clips)} clips, {len(frames)} frames -> {args.out}")


if __name__ == "__main__":
    main()
