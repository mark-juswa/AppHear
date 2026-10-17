"""Debug-only FP32 TFLite package for the WORD v2 candidate recognizer (shadow evaluation).

Source: artifacts/.../word_track_robust_aug_02/best.keras (recognition-v2 TCN, same architecture
and I/O to the frozen Gate-2 recognizer; only the training views differ). The package mirrors the
Gate-2 manifest schema so the existing Android parity tooling can consume it, and is written to the
DEBUG asset source set only: release builds cannot load it, and the frozen Gate-2 recognizer stays
the primary/default and rollback model.

Host parity: Keras vs TFLite on the 20 pinned Gate-1 fixture views (same tolerances as Gate 2:
max abs <= 1e-5, zero top-1 / top-5 membership mismatches), mask-padding invariance on the Gate-2
padding fixtures, and top-1 agreement on all 816 signer-disjoint DEV clips at phone cadence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy import export_v2_tcn_gate2 as gate2  # noqa: E402

RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
CHECKPOINT = RU / "word_track_robust_aug_02/best.keras"
CHECKPOINT_SHA = "4f56ce612ca5b40c4073c07670c9e46e9de9ba5f31736b5f0615154a984673bf"
VOCAB = Path("artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json")
ASSET_DIR = "word_v2_candidate"
ANDROID_ASSETS = ROOT / "android/app/src/debug/assets" / ASSET_DIR
MODEL_NAME = "word_v2_fp32.tflite"
FROZEN_MANIFEST = ROOT / "android/app/src/main/assets/phase4a_gate2_recognizer_parity/manifest.json"
DATASET_INDEX = RU / "dataset/index.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root
    import tensorflow as tf

    checkpoint = root / CHECKPOINT
    if sha256(checkpoint) != CHECKPOINT_SHA:
        raise RuntimeError("WORD_V2_CHECKPOINT_IDENTITY")
    frozen = json.loads(FROZEN_MANIFEST.read_text(encoding="utf-8"))
    vocab = json.loads((root / VOCAB).read_text(encoding="utf-8"))
    glosses = [g for g, _ in sorted(vocab.items(), key=lambda item: item[1])]
    if (
        sha256(root / VOCAB) != frozen["vocabulary_sha256"]
        or glosses != frozen["class_index_to_gloss"]
    ):
        raise RuntimeError("WORD_V2_VOCABULARY_DRIFT")
    model = tf.keras.models.load_model(checkpoint, compile=False, safe_mode=True)
    if model.count_params() != 192556:
        raise RuntimeError("WORD_V2_PARAMETER_COUNT")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = []
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    model_bytes = converter.convert()
    ANDROID_ASSETS.mkdir(parents=True, exist_ok=True)
    model_path = ANDROID_ASSETS / MODEL_NAME
    model_path.write_bytes(model_bytes)
    interpreter = tf.lite.Interpreter(model_content=model_bytes, num_threads=4)
    interpreter.allocate_tensors()
    feature_in, mask_in, output = gate2.tflite_io(interpreter)
    if any(op["op_name"].upper().startswith("FLEX") for op in interpreter._get_ops_details()):
        raise RuntimeError("WORD_V2_SELECT_TF_OPS")

    def keras(x: np.ndarray, m: np.ndarray) -> np.ndarray:
        return model([x[None], m[None]], training=False).numpy()[0].astype(np.float32)

    errors, views, top1_mismatch, top5_mismatch = [], [], 0, 0
    for item in frozen["views"]:
        x = np.fromfile(gate2.GATE1_ASSETS / item["feature_asset"], dtype="<f4").reshape(96, 350)
        if sha256(gate2.GATE1_ASSETS / item["feature_asset"]) != item["feature_sha256"]:
            raise RuntimeError("WORD_V2_FIXTURE_HASH")
        m = np.asarray(item["mask"], bool)
        k = keras(x, m)
        lite = gate2.invoke(interpreter, feature_in, mask_in, output, x, m)
        errors.append(np.abs(k.astype(np.float64) - lite.astype(np.float64)))
        kt, lt = gate2.topk(k), gate2.topk(lite)
        top1_mismatch += int(kt[0] != lt[0])
        top5_mismatch += int(set(kt) != set(lt))
        name = f"{item['fixture_id']}_{item['condition']}_keras_output.f32"
        k.astype("<f4").tofile(ANDROID_ASSETS / name)
        views.append(
            {
                **{
                    key: item[key]
                    for key in (
                        "fixture_id",
                        "condition",
                        "feature_asset",
                        "feature_sha256",
                        "mask",
                    )
                },
                "keras_output_asset": f"{ASSET_DIR}/{name}",
                "keras_output_sha256": sha256(ANDROID_ASSETS / name),
                "keras_top5_indices": kt,
                "keras_top5_glosses": [glosses[i] for i in kt],
            }
        )
    padding = []
    for item in frozen["mask_padding_views"]:
        x = np.fromfile(gate2.GATE1_ASSETS / item["feature_asset"], dtype="<f4").reshape(96, 350)
        m = np.asarray(item["mask"], bool)
        garbage = gate2.garbage_padding(x, m)
        delta_k = float(np.max(np.abs(keras(x, m) - keras(garbage, m))))
        delta_l = float(
            np.max(
                np.abs(
                    gate2.invoke(interpreter, feature_in, mask_in, output, x, m)
                    - gate2.invoke(interpreter, feature_in, mask_in, output, garbage, m)
                )
            )
        )
        padding.append(
            {
                "fixture_id": item["fixture_id"],
                "condition": item["condition"],
                "keras_max_abs": delta_k,
                "tflite_max_abs": delta_l,
                "pass": delta_k <= 1e-6 and delta_l <= 1e-6,
            }
        )
    # population agreement: every signer-disjoint DEV clip at phone cadence (3.75 fps)
    from pipeline.perception_vnext.recognition_schema import load_raw_sequence
    from pipeline.perception_vnext.recognition_schema_v2 import temporal_view_v2

    dev = [
        json.loads(line)
        for line in (root / DATASET_INDEX).open(encoding="utf-8")
        if '"split":"dev"' in line
    ]
    agree, dev_max = 0, 0.0
    for row in dev:
        view = temporal_view_v2(
            load_raw_sequence(Path(row["raw_path"])),
            condition="phone_01_sparse",
            phone_completed_fps=3.75,
        )
        k = keras(view["features"].astype(np.float32), view["mask"])
        lite = gate2.invoke(
            interpreter,
            feature_in,
            mask_in,
            output,
            view["features"].astype(np.float32),
            view["mask"],
        )
        agree += int(np.argmax(k) == np.argmax(lite))
        dev_max = max(dev_max, float(np.max(np.abs(k - lite))))
    global_max = float(np.max(np.concatenate(errors)))
    passed = (
        global_max <= 1e-5
        and top1_mismatch == 0
        and top5_mismatch == 0
        and all(p["pass"] for p in padding)
        and agree == len(dev)
    )
    manifest = {
        "milestone": "WORD_V2_SHADOW_CANDIDATE_01",
        "package_id": "WORD_V2_CANDIDATE",
        "role": "DEBUG_SHADOW_ONLY",
        "feature_schema": frozen["feature_schema"],
        "source_checkpoint_sha256": CHECKPOINT_SHA,
        "model_asset": f"{ASSET_DIR}/{MODEL_NAME}",
        "model_sha256": sha256(model_path),
        "vocabulary_sha256": frozen["vocabulary_sha256"],
        "class_index_to_gloss": glosses,
        "input_shape": [1, 96, 350],
        "mask_shape": [1, 96],
        "output_shape": [1, 236],
        "output_semantics": "probabilities_softmax",
        "runtime": frozen["runtime"],
        "tolerances": frozen["tolerances"],
        "views": views,
        "host_parity": {
            "fixture_views": len(views),
            "max_abs": global_max,
            "top1_mismatches": top1_mismatch,
            "top5_membership_mismatches": top5_mismatch,
            "mask_padding": padding,
            "dev_phone_cadence_top1_agreement": f"{agree}/{len(dev)}",
            "dev_phone_cadence_max_abs": dev_max,
            "pass": passed,
        },
        "frozen_reference_model_sha256": frozen["model_sha256"],
        "protected_test_accessed": False,
    }
    (ANDROID_ASSETS / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({"model_sha256": manifest["model_sha256"], **manifest["host_parity"]}, indent=1)
    )
    if not passed:
        raise SystemExit("WORD_V2_HOST_PARITY_FAILED")


if __name__ == "__main__":
    main()
