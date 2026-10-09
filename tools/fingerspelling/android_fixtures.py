"""Generate test-only reference packages from existing governed raw/RGB. No inference/training."""

from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path

import numpy as np

from pipeline.fingerspelling.adapter import derive, sha256
from pipeline.fingerspelling.visual_quality import quality
from pipeline.perception_vnext.recognition_schema import load_raw_sequence
from tools.fingerspelling.android_export import OUT
from tools.fingerspelling.parity import fixture, serialize


def write_floats(path: Path, values: np.ndarray) -> None:
    path.write_bytes(np.asarray(values, dtype=">f4").tobytes())


def main() -> None:
    assets = OUT / "android_assets/fingerspelling"
    assets.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((OUT / "model_manifest.json").read_text())
    for name, key in [
        ("model/config/fingerspelling_residual_visual_01.json", "quality_config"),
        ("pipeline/config/fingerspelling_visual_v1.json", "crop_config"),
        ("pipeline/config/fingerspelling_features_v1.json", "feature_config"),
    ]:
        manifest[key] = json.loads(Path(name).read_text())
    manifest["session_limits"] = {"maximum_frames": 512, "maximum_seconds": 60.0}
    for name in manifest["models"]:
        assert sha256(OUT / name) == manifest["models"][name]["sha256"]
        shutil.copyfile(OUT / name, assets / name)
    (assets / "model_manifest.json").write_text(json.dumps(manifest, indent=2))
    test = OUT / "parity_assets/fingerspelling_fixtures"
    test.mkdir(parents=True, exist_ok=True)
    cases = [("edge_cases", fixture())]
    report = json.loads((OUT / "export_parity.json").read_text())
    for case in report["sequence_cases"]:
        sid = case["sample_id"]
        if case["view"] == "native":
            receipt = json.loads(
                Path(
                    f"datasets/fingerspelling/foundation_01/features/{sid}.receipt.json"
                ).read_text()
            )
            cases.append((sid, load_raw_sequence(Path(receipt["raw_path"]))))
        with np.load(OUT / case["fixture"]) as data:
            p = data["packed"]
            logits = data["logits"]
            with (test / (case["fixture"] + ".bin")).open("wb") as f:
                f.write(struct.pack(">i", len(p)))
                f.write(p.astype(">f4").tobytes())
                f.write(logits.astype(">f4").tobytes())
    for name, raw in cases:
        serialize(test / (name + ".input.bin"), raw)
        write_floats(test / (name + ".features.bin"), derive(raw))
        q = quality(raw)
        write_floats(test / (name + ".quality.bin"), q["quality"])
        (test / (name + ".rejection.bin")).write_bytes(q["rejection_bits"].astype(">i4").tobytes())
        (test / (name + ".duplicate.bin")).write_bytes(q["duplicate"].astype(np.uint8).tobytes())
    with np.load(OUT / "crop_fixture.npz") as data:
        rgb, roi = data["rgb"], data["roi"]
        with (test / "crop.bin").open("wb") as f:
            f.write(struct.pack(">ii", rgb.shape[1], rgb.shape[0]))
            f.write(rgb.tobytes())
            f.write(roi.astype(">f4").tobytes())
            f.write(data["crop"].astype(">f4").tobytes())
            f.write(data["embedding"].astype(">f4").tobytes())
    summary = {
        "observation_cases": [n for n, _ in cases],
        "sequence_cases": report["sequence_cases"],
        "test_accessed": False,
    }
    (test / "cases.json").write_text(json.dumps(summary, indent=2))
    print(
        json.dumps(
            {
                "status": "ANDROID_FIXTURES_READY",
                "observation_frames": sum(len(r.frame_index) for _, r in cases),
                "model_bytes": sum((assets / n).stat().st_size for n in manifest["models"]),
            }
        )
    )


if __name__ == "__main__":
    main()
