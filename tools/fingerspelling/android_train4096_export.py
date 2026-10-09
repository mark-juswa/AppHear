"""Separate, pinned FP32 epoch038 geometry export. Inference/fixtures only, no training."""
from __future__ import annotations

import json
import os
import shutil
import struct
from pathlib import Path

import numpy as np

from model.fingerspelling_fast_execution import FeatureCache
from model.fingerspelling_prefix_beam import decode_beam, decode_greedy
from pipeline.fingerspelling.adapter import CONFIG, derive, identity, phone_indices, sha256, subset
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from tools.fingerspelling.android_export import convert, invoke, write_json
from tools.fingerspelling.parity import fixture, serialize

OUT = REPO / "artifacts/fingerspelling_train4096_android_01"
CHECKPOINT = REPO / "runs/fingerspelling_train4096_01/best_candidates/epoch_038.keras"
CHECKPOINT_SHA = "b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886"
SCHEMA = "apphear.fingerspelling.android.geometry.v1"


def selected_rows(samples: list[dict]) -> list[dict]:
    """Metadata-only deterministic fixture selection, not model-selection data."""
    rows = sorted(samples, key=lambda r: r["sample_id"])
    tests = [
        ("short_train_daun", lambda r: r["split_role"] == "TRAIN" and r["source_stratum"] == "DAUN"),
        ("train_mackenzie_space", lambda r: r["split_role"] == "TRAIN" and r["source_stratum"] == "MacKenzie" and " " in r["normalized_transcript"]),
        ("dev_repeat", lambda r: r["split_role"] == "DEV" and any(a == b for a, b in zip(r["normalized_transcript"], r["normalized_transcript"][1:]))),
        ("dev_j", lambda r: r["split_role"] == "DEV" and "J" in r["normalized_transcript"]),
        ("dev_z", lambda r: r["split_role"] == "DEV" and "Z" in r["normalized_transcript"]),
        ("dev_long", lambda r: r["split_role"] == "DEV"),
    ]
    result = []
    used = set()
    for category, predicate in tests:
        eligible = [r for r in rows if predicate(r) and r["sample_id"] not in used]
        if not eligible:
            raise ValueError(f"No governed fixture for {category}")
        if category == "short_train_daun":
            eligible.sort(key=lambda r: (len(r["normalized_transcript"]), r["sample_id"]))
        elif category == "dev_long":
            eligible.sort(key=lambda r: (-len(r["normalized_transcript"]), r["sample_id"]))
        row = dict(eligible[0], fixture_category=category)
        used.add(row["sample_id"])
        result.append(row)
    return result


def export() -> None:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf

    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    if sha256(CHECKPOINT) != CHECKPOINT_SHA:
        raise ValueError("Selected epoch038 checkpoint changed")
    OUT.mkdir(parents=True, exist_ok=True)
    model = tf.keras.models.load_model(CHECKPOINT, compile=False)
    assert len(model.inputs) == 2 and model.output_shape[-1] == 28
    assert sorted(int(x.shape[-1]) for x in model.inputs) == [1, 405]
    path = OUT / "geometry_sequence.tflite"
    convert(tf, model, [tf.TensorSpec([1, None, 405], tf.float32, "geometry"),
                        tf.TensorSpec([1, None, 1], tf.float32, "mask")], path)
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=2)
    assert all(d["dtype"] == np.float32 for d in interpreter.get_input_details() + interpreter.get_output_details())
    assert not any(d["dtype"] in (np.int8, np.uint8) for d in interpreter.get_tensor_details())
    foundation = REPO / "datasets/fingerspelling/foundation_01"
    manifest_path = foundation / "tranche_manifest.json"
    rows = selected_rows(json.loads(manifest_path.read_text())["samples"])
    test_assets = OUT / "parity_assets/train4096_geometry"
    test_assets.mkdir(parents=True, exist_ok=True)
    cache = FeatureCache()
    cases = []
    lineage = []
    for row in rows:
        rec_path = foundation / "features" / f"{row['sample_id']}.receipt.json"
        rec = json.loads(rec_path.read_text())
        raw = verify_raw(REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"])
        lineage.append({"receipt_path": str(rec_path.relative_to(REPO)), "receipt_sha256": sha256(rec_path),
                        "source_sha256": rec["source_sha256"], "raw_sha256": rec["raw_sha256"],
                        "feature_sha256": rec["features_sha256"], "role": rec["split_role"]})
        for view in ("native", "phone"):
            chosen = raw if view == "native" else subset(raw, phone_indices(raw.timestamp_ms))
            features, _ = cache.load(rec, view)
            np.testing.assert_array_equal(features, derive(chosen))
            cases.append((row["sample_id"] + "-" + view, chosen, features,
                          np.ones((len(features), 1), np.float32),
                          {"view": view, "role": rec["split_role"], "category": row["fixture_category"],
                           "transcript": rec["normalized_transcript"], "signer": rec["official_signer_id"]}))
    edge = fixture()
    edge_features = derive(edge)
    cases.append(("edge_missing_partial_duplicate_motion", edge, edge_features,
                  np.ones((len(edge_features), 1), np.float32), {"view": "synthetic_parity_only"}))
    # Padding/mask is a test-only model contract check, never a training observation.
    padded = np.pad(edge_features, ((0, 7), (0, 0)))
    padding_mask = np.pad(np.ones((len(edge_features), 1), np.float32), ((0, 7), (0, 0)))
    cases.append(("masked_padding", None, padded, padding_mask, {"view": "synthetic_parity_only"}))
    results = []
    for name, raw, features, mask, meta in cases:
        x, m = features[None], mask[None]
        reference = model([x, m], training=False).numpy()[0]
        actual = invoke(tf, path, [x, m])[0]
        np.testing.assert_allclose(actual, reference, atol=2e-4, rtol=2e-4)
        greedy = decode_greedy(reference, .5)
        beam = decode_beam(reference, .5, 10, 1)[0]["prediction"]
        assert decode_greedy(actual, .5) == greedy
        assert decode_beam(actual, .5, 10, 1)[0]["prediction"] == beam
        n = len(features)
        prefix_n = max(1, n // 2)
        prefix = invoke(tf, path, [x[:, :prefix_n], m[:, :prefix_n]])[0]
        np.testing.assert_allclose(prefix, actual[:prefix_n], atol=2e-4, rtol=2e-4)
        if raw is not None:
            serialize(test_assets / f"{name}.input.bin", raw)
        with (test_assets / f"{name}.bin").open("wb") as out:
            out.write(struct.pack(">i", n))
            for a in (features, mask, reference, actual):
                out.write(np.asarray(a, dtype=">f4").tobytes())
        np.savez_compressed(OUT / f"{name}.npz", features=features, mask=mask,
                            keras_logits=reference, tflite_logits=actual)
        results.append({"id": name, "timesteps": n, **meta, "raw_fixture": raw is not None,
                        "greedy": greedy, "beam": beam, "beam_differs_from_greedy": beam != greedy,
                        "maximum_logit_error": float(np.max(np.abs(reference - actual))),
                        "prefix_maximum_error": float(np.max(np.abs(prefix - actual[:prefix_n]))),
                        "fixture_sha256": sha256(test_assets / f"{name}.bin")})
        print(json.dumps({"fixture": name, "timesteps": n, "parity": "PASS"}), flush=True)
    package = {
        "schema_version": SCHEMA, "candidate_id": "TRAIN4096_EPOCH038_GEOMETRY_ONLY",
        "checkpoint_path": str(CHECKPOINT.relative_to(REPO)), "checkpoint_epoch": 38,
        "checkpoint_sha256": CHECKPOINT_SHA, "adapter": identity(), "packed_width": 405,
        "blank_penalty": .5, "blank_index": 27, "beam_width": 10, "decoder": "PREFIX_BEAM_TOP1",
        "vocabulary": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["SPACE", "BLANK"],
        "models": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}},
        "feature_config": CONFIG, "session_limits": {"maximum_frames": 512, "maximum_seconds": 60.0},
        "visual_branch_enabled": False, "quantized": False, "training": False, "test_accessed": False,
    }
    write_json(OUT / "model_manifest.json", package)
    assets = OUT / "android_assets/fingerspelling"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, assets / path.name)
    shutil.copyfile(OUT / "model_manifest.json", assets / "model_manifest.json")
    beam_assets = OUT / "parity_assets/fingerspell_beam"
    beam_assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "artifacts/fingerspelling_android_beam_01/beam_fixtures.bin", beam_assets / "fixtures.bin")
    write_json(test_assets / "cases.json", {"checkpoint_sha256": CHECKPOINT_SHA, "cases": results})
    report = {"status": "TRAIN4096_HOST_EXPORT_PARITY_PASS", "checkpoint_sha256": CHECKPOINT_SHA,
              "manifest_sha256": sha256(assets / "model_manifest.json"), "models": package["models"],
              "fixture_count": len(results), "maximum_logit_error": max(r["maximum_logit_error"] for r in results),
              "greedy_mismatches": 0, "beam_mismatches": 0, "cases": results,
              "fixture_lineage": lineage, "foundation_manifest_sha256": sha256(manifest_path),
              "tensorflow": tf.__version__, "quantization": "NONE_FP32", "test_accessed": False,
              "android_parity": "PENDING", "training": False}
    write_json(OUT / "export_parity.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("cases", "fixture_lineage")}, indent=2))


if __name__ == "__main__":
    export()
