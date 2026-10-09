"""Bounded, pinned FP32 mobile export and host numerical parity. Never trains."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.sequence_manifest import REPO

OUT = REPO / "artifacts/fingerspelling_android_01"
RESIDUAL = REPO / "runs/fingerspelling_residual_visual_01/best_candidates/epoch_035.keras"
RESIDUAL_SHA = "f87be3236196c8ab8321a3b6f7bb9d6398d048e257630a38546e8a8d00143251"


def preserve() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "preservation.json"
    if path.exists():
        return
    roots = [REPO / "android/app/src", REPO / "pipeline/perception_vnext"]
    paths = [p for root in roots for p in root.rglob("*") if p.is_file()]
    paths += [
        RESIDUAL,
        REPO / "runs/fingerspelling_ctc_baseline_02/best_candidates/epoch_076.keras",
    ]
    path.write_text(json.dumps({str(p.relative_to(REPO)): sha256(p) for p in paths}, indent=2))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def decode(logits: np.ndarray) -> str:
    x = logits.copy()
    x[:, 27] -= 0.5
    last, text = -1, []
    for token in x.argmax(-1):
        if token != last and token != 27:
            text.append(" " if token == 26 else chr(65 + int(token)))
        last = token
    return "".join(text)


def convert(tf: Any, model: Any, specs: list[Any], path: Path) -> None:
    # Freeze variables first, avoiding Keras resource-variable export ambiguity.
    from tensorflow.python.framework.convert_to_constants import convert_variables_to_constants_v2

    @tf.function(input_signature=specs, autograph=False)
    def serve(*inputs: Any) -> Any:
        return model(inputs[0] if len(inputs) == 1 else list(inputs), training=False)

    concrete = convert_variables_to_constants_v2(serve.get_concrete_function())
    converter = tf.lite.TFLiteConverter.from_concrete_functions([concrete])
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    path.write_bytes(converter.convert())


def invoke(tf: Any, path: Path, values: list[np.ndarray]) -> np.ndarray:
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=2)
    details = interpreter.get_input_details()
    # Map by final width rather than converter-generated tensor order.
    used = set()
    pairs = []
    for value in values:
        matches = [
            d for d in details if int(d["shape"][-1]) == value.shape[-1] and d["index"] not in used
        ]
        if len(matches) != 1:
            raise ValueError("Ambiguous exported input mapping")
        d = matches[0]
        used.add(d["index"])
        interpreter.resize_tensor_input(d["index"], value.shape, strict=True)
        pairs.append((d["index"], value))
    interpreter.allocate_tensors()
    for index, value in pairs:
        interpreter.set_tensor(index, value)
    interpreter.invoke()
    result: np.ndarray = np.asarray(
        interpreter.get_tensor(interpreter.get_output_details()[0]["index"])
    )
    return result


def export() -> None:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf

    from model.fingerspelling_appearance import build_encoder, encoder_identity
    from model.fingerspelling_residual_execution import ResidualCache, base_model

    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    preserve()
    if sha256(RESIDUAL) != RESIDUAL_SHA:
        raise ValueError("Selected residual checkpoint changed")
    residual = tf.keras.models.load_model(RESIDUAL, compile=False)
    appearance = build_encoder(tf)
    seq_path, app_path = OUT / "residual_sequence.tflite", OUT / "appearance.tflite"
    convert(
        tf,
        residual,
        [
            tf.TensorSpec([1, None, 1559], tf.float32, "packed"),
            tf.TensorSpec([1, None, 1], tf.float32, "mask"),
        ],
        seq_path,
    )
    convert(tf, appearance, [tf.TensorSpec([1, 128, 128, 3], tf.float32, "crop")], app_path)
    manifest = json.loads(
        (REPO / "datasets/fingerspelling/foundation_01/tranche_manifest.json").read_text()
    )
    rows = []
    for role, stratum in [("TRAIN", "DAUN"), ("TRAIN", "MacKenzie"), ("DEV", "DAUN")]:
        sample = next(
            x
            for x in manifest["samples"]
            if x["split_role"] == role and x["source_stratum"] == stratum
        )
        rec = json.loads(
            (
                REPO
                / "datasets/fingerspelling/foundation_01/features"
                / f"{sample['sample_id']}.receipt.json"
            ).read_text()
        )
        rows.append(rec)
    cache, b2 = ResidualCache(), base_model(tf)
    results = []
    for rec in rows:
        for view in ["native", "phone"]:
            packed, _ = cache.load(rec, view)
            x = packed[None].copy()
            mask: np.ndarray = np.ones((1, len(packed), 1), np.float32)
            reference = residual([x, mask], training=False).numpy()
            actual = invoke(tf, seq_path, [x, mask])
            error = float(np.max(np.abs(reference - actual)))
            np.testing.assert_allclose(actual, reference, atol=2e-4, rtol=2e-4)
            if decode(actual[0]) != decode(reference[0]):
                raise ValueError("Export changed decoded sequence")
            x[:, :, 405:] = 0
            fallback = invoke(tf, seq_path, [x, mask])
            base = b2([x[:, :, :405], mask], training=False).numpy()
            np.testing.assert_allclose(fallback, base, atol=2e-4, rtol=2e-4)
            filename = f"{rec['sample_id']}-{view}.npz"
            np.savez_compressed(OUT / filename, packed=packed, mask=mask[0], logits=reference[0])
            results.append(
                {
                    "sample_id": rec["sample_id"],
                    "role": rec["split_role"],
                    "view": view,
                    "timesteps": len(packed),
                    "max_absolute_error": error,
                    "decoded": decode(actual[0]),
                    "zero_visual_b2_pass": True,
                    "fixture": filename,
                }
            )
    # One real retained crop; use existing original RGB, no new extraction.
    from pipeline.fingerspelling.sequence_package import verify_raw
    from pipeline.fingerspelling.visual_crop import hand_crop
    from pipeline.fingerspelling.visual_quality import quality
    from pipeline.perception_vnext.offline_candidate01 import iter_video_frames

    rec = rows[0]
    raw = verify_raw(
        REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"]
    )
    quality_values = quality(raw)
    frame, slot = np.argwhere(quality_values["quality"] > 0)[0]
    # Existing source decoding conventions, including verified orientation.
    from pipeline.fingerspelling.visual_package import verified_orientation

    receipt = json.loads((REPO / rec["raw_receipt_path"]).read_text())
    orientation = verified_orientation(receipt, rec)
    iterator, decoder = iter_video_frames(REPO / rec["source_path"], None)
    if decoder["orientation_degrees_clockwise"] != orientation:
        raise ValueError("Verified source orientation changed")
    for i, (_, _, _, rgb) in enumerate(iterator):
        if i == frame:
            pixels, _ = hand_crop(rgb, raw.hand_roi_center_side[i, slot], True)
            break
    else:
        raise ValueError("Retained source frame missing")
    reference_emb = appearance(pixels[None], training=False).numpy()
    actual_emb = invoke(tf, app_path, [pixels[None]])
    np.testing.assert_allclose(actual_emb, reference_emb, atol=2e-4, rtol=2e-4)
    np.savez_compressed(
        OUT / "crop_fixture.npz",
        rgb=rgb,
        crop=pixels,
        roi=raw.hand_roi_center_side[frame, slot],
        embedding=reference_emb[0],
    )
    write_json(
        OUT / "export_parity.json",
        {
            "status": "HOST_EXPORT_PARITY_PASS",
            "sequence_cases": results,
            "embedding_max_absolute_error": float(np.max(np.abs(actual_emb - reference_emb))),
            "tensorflow": tf.__version__,
            "android_parity": "PENDING",
            "test_accessed": False,
        },
    )
    write_json(
        OUT / "model_manifest.json",
        {
            "schema_version": "apphear.fingerspelling.android.v1",
            "adapter": identity(),
            "residual_checkpoint_sha256": RESIDUAL_SHA,
            "appearance_encoder": encoder_identity(),
            "packed_width": 1559,
            "blank_penalty": 0.5,
            "vocabulary": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["SPACE", "BLANK"],
            "models": {
                p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
                for p in [seq_path, app_path]
            },
            "training": False,
            "test_accessed": False,
        },
    )
    print((OUT / "export_parity.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export", "snapshot"])
    args = parser.parse_args()
    preserve() if args.action == "snapshot" else export()
