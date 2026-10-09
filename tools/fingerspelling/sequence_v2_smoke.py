"""Bounded TRAIN-only learnability, padding, resume and FP32 export gates."""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np

from model import fingerspelling_ctc as reference
from model.fingerspelling_baseline2 import state_digest
from model.fingerspelling_fast_execution import CompiledSteps
from model.fingerspelling_prefix_beam import decode_beam, decode_greedy
from model.fingerspelling_sequence_v2_encoder import (
    CONFIG,
    build_model,
    configuration,
    receptive_field,
)
from model.fingerspelling_sequence_v2_execution import RobustTemporalCache
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.android_export import convert, invoke
from tools.fingerspelling.sequence_v2_evidence import OUTPUT, receipts

RUN = REPO / "runs/fingerspelling_sequence_v2_01_smoke"


def choose_tiny(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Metadata-only deterministic diversity, independent of model performance.

    TRAIN-only engineering overfit; not a held-out accuracy claim. Requires existing
    missingness and adequate native CTC length. No discarded corpus records.
    """
    selected: list[dict[str, Any]] = []
    signers: set[str] = set()
    categories = [
        ("DAUN", "J", lambda s: "J" in s),
        ("MacKenzie", "Z", lambda s: "Z" in s),
        ("DAUN", "repeat", lambda s: any(a == b for a, b in zip(s, s[1:], strict=False))),
        ("MacKenzie", "SPACE", lambda s: " " in s),
        ("DAUN", "short", lambda s: len(s) <= 8),
        ("MacKenzie", "long", lambda s: 20 <= len(s) <= 25),
    ]
    for stratum, category, predicate in categories:
        eligible = [
            r
            for r in rows
            if r["source_stratum"] == stratum
            and r["official_signer_id"] not in signers
            and 0 < r["any_hand_observed_fraction"] < 1
            and r["native_ctc_feasible"]
            and predicate(r["normalized_transcript"])
            and len(r["normalized_transcript"]) <= 25
        ]
        if not eligible:
            raise ValueError("[sequence-v2/smoke] Tiny diversity category unavailable")
        # Prefer bounded engineering duration without using extraction performance or logits.
        rec = min(eligible, key=lambda r: (r["frame_count"], r["sample_id"]))
        selected.append({**rec, "smoke_category": category})
        signers.add(rec["official_signer_id"])
    return selected


def decode_batch(logits: np.ndarray, lengths: np.ndarray, penalty: float = 0.5) -> list[str]:
    return [decode_greedy(a[: int(n)], penalty) for a, n in zip(logits, lengths, strict=True)]


def smoke() -> dict[str, Any]:
    p = configuration()
    tf = reference.tensorflow(p)
    rows = choose_tiny(receipts())
    RUN.mkdir(parents=True, exist_ok=True)
    if (RUN / "smoke.keras").exists():
        raise ValueError(
            "[sequence-v2/smoke] Existing smoke checkpoint retained; choose a new run explicitly"
        )
    write_json_atomic(
        OUTPUT / "tiny_subset.json",
        {
            "selection": "TRAIN_METADATA_DIVERSITY_SHORTEST_VALID_BY_CATEGORY_NO_MODEL_SELECTION",
            "samples": [
                {
                    k: r[k]
                    for k in (
                        "sample_id",
                        "official_signer_id",
                        "source_stratum",
                        "normalized_transcript",
                        "frame_count",
                        "raw_sha256",
                        "features_sha256",
                        "smoke_category",
                    )
                }
                for r in rows
            ],
            "accuracy_claim": "NONE",
            "dev_accessed": False,
            "test_accessed": False,
        },
    )
    model = build_model(tf, p)
    optimizer = tf.keras.optimizers.Adam(p["learning_rate"], clipnorm=p["gradient_clip_norm"])
    optimizer.build(model.trainable_variables)
    steps, cache = CompiledSteps(tf, model, optimizer), RobustTemporalCache(p)
    batch = cache.batch(rows, "native")
    initial_loss, gradients = steps.gradients_without_dropout(*batch)
    gradient_norm = float(tf.linalg.global_norm(gradients).numpy())
    if not np.isfinite(gradient_norm) or gradient_norm <= 0:
        raise ValueError("[sequence-v2/smoke] No finite nonzero gradients")
    refs = [r["normalized_transcript"] for r in rows]
    started = time.perf_counter()
    history = []
    fitted = False
    for update in range(1, p["smoke"]["maximum_updates"] + 1):
        if steps.update is None:
            raise RuntimeError("[sequence-v2/smoke] Optimizer missing")
        loss = float(steps.update(*batch).numpy())
        if update % p["smoke"]["check_interval"] == 0:
            logits = steps.infer(*batch[:2]).numpy()
            eval_loss = float(reference.ctc_loss(tf, logits, *batch[2:]).numpy())
            predictions = decode_batch(logits, batch[3])
            fitted = predictions == refs and eval_loss < p["smoke"]["overfit_mean_ctc_ceiling"]
            item = {
                "updates": update,
                "training_ctc": loss,
                "evaluation_ctc": eval_loss,
                "exact_train_strings": sum(a == b for a, b in zip(predictions, refs, strict=True)),
                "TRAIN_predictions": predictions,
                "seconds": time.perf_counter() - started,
            }
            history.append(item)
            print(json.dumps(item), flush=True)
            write_json_atomic(OUTPUT / "learnability_progress.json", history)
            if fitted:
                break
        if time.perf_counter() - started >= p["smoke"]["maximum_seconds"]:
            break
    final_loss = float(reference.ctc_loss(tf, steps.infer(*batch[:2]), *batch[2:]).numpy())
    model.save(RUN / "smoke.keras")
    # Prove all four train regimes, CTC fallback and independent deterministic stress views.
    augmentation = []
    for epoch in range(4):
        tensors, choices = cache.training_batch(rows, epoch)
        value, g = steps.gradients_without_dropout(*tensors)
        augmentation.append(
            {
                "epoch_index": epoch,
                "ctc_loss": float(value.numpy()),
                "gradient_norm": float(tf.linalg.global_norm(g).numpy()),
                "choices": choices,
            }
        )
        again, choices_again = cache.training_batch(rows, epoch)
        if (
            not all(np.array_equal(a, b) for a, b in zip(tensors, again, strict=True))
            or choices != choices_again
        ):
            raise ValueError("[sequence-v2/smoke] Nondeterministic training robustness")
    # Padding invariance for each separate real sequence, also with arbitrary masked input.
    padding_errors = []
    future_changes = []
    rng = np.random.default_rng(p["seed"])
    for rec in rows:
        x, _ = cache.load(rec, "phone")
        m = np.ones((1, len(x), 1), np.float32)
        plain = model([x[None], m], training=False).numpy()[0]
        padded = np.concatenate([x, rng.normal(size=(37, 405)).astype(np.float32)])
        mask = np.r_[np.ones(len(x)), np.zeros(37)].astype(np.float32)[None, :, None]
        full = model([padded[None], mask], training=False).numpy()[0]
        padding_errors.append(float(np.max(np.abs(plain - full[: len(x)]))))
        if np.any(full[len(x) :] != 0):
            raise ValueError("[sequence-v2/mask] Padded logits not zero")
        half = max(1, len(x) // 2)
        prefix = model([x[None, :half], m[:, :half]], training=False).numpy()[0]
        future_changes.append(float(np.max(np.abs(prefix - plain[:half]))))
        if decode_greedy(plain, 0.5) != decode_greedy(full[: len(x)], 0.5):
            raise ValueError("[sequence-v2/mask] Padding changed decoded content")
    if max(padding_errors) > 1e-4 or max(future_changes) <= 1e-5:
        raise ValueError("[sequence-v2/mask] Padding invariance/future context failed")
    # Exact optimizer/model restore, then equivalent next update (dropout-off gradients).
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer)
    saved = checkpoint.save(str(RUN / "checkpoint"))
    restored = build_model(tf, p)
    opt2 = tf.keras.optimizers.Adam(p["learning_rate"], clipnorm=p["gradient_clip_norm"])
    opt2.build(restored.trainable_variables)
    tf.train.Checkpoint(model=restored, optimizer=opt2).restore(
        saved
    ).assert_existing_objects_matched()
    restore_exact = state_digest(model, optimizer) == state_digest(restored, opt2)
    if not restore_exact:
        raise ValueError("[sequence-v2/resume] Model/optimizer state not exactly restored")
    reload_model = tf.keras.models.load_model(RUN / "smoke.keras", compile=False)
    if not np.array_equal(
        steps.infer(*batch[:2]).numpy(), reload_model(list(batch[:2]), training=False).numpy()
    ):
        # Compiled/eager GEMM can round differently; saved weights must still be exact.
        if any(
            not np.array_equal(a, b)
            for a, b in zip(model.get_weights(), reload_model.get_weights(), strict=True)
        ):
            raise ValueError("[sequence-v2/reload] Saved model weights changed")
    path = OUTPUT / "smoke_sequence_v2_fp32.tflite"
    convert(
        tf,
        model,
        [
            tf.TensorSpec([1, None, 405], tf.float32, "features"),
            tf.TensorSpec([1, None, 1], tf.float32, "time_valid"),
        ],
        path,
    )
    parity = []
    for rec in rows:
        for view in ("native", "phone", "stress_moderate", "stress_heavy", "stress_contiguous"):
            x, _ = cache.load(rec, view)
            values = [x[None], np.ones((1, len(x), 1), np.float32)]
            keras = model(values, training=False).numpy()[0]
            t0 = time.perf_counter()
            lite = invoke(tf, path, values)[0]
            seconds = time.perf_counter() - t0
            greedy = decode_greedy(keras, 0.5)
            beam = decode_beam(keras, 0.5, 10, 1)[0]["prediction"]
            err = float(np.max(np.abs(keras - lite)))
            if (
                err > 1e-3
                or greedy != decode_greedy(lite, 0.5)
                or beam != decode_beam(lite, 0.5, 10, 1)[0]["prediction"]
            ):
                raise ValueError(
                    f"[sequence-v2/export] Logit/text mismatch: {rec['sample_id']} {view} {err}"
                )
            parity.append(
                {
                    "sample_id": rec["sample_id"],
                    "view": view,
                    "timesteps": len(x),
                    "max_logit_error": err,
                    "greedy": greedy,
                    "beam": beam,
                    "exact_greedy_beam_parity": True,
                    "host_allocate_invoke_seconds": seconds,
                }
            )
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=2)
    ops = sorted({d["op_name"] for d in interpreter._get_ops_details()})
    report = {
        "status": "V2_SMOKE_PASS" if fitted else "V2_TINY_OVERFIT_NOT_ESTABLISHED",
        "parameters": model.count_params(),
        "receptive_field": receptive_field(p),
        "initial_ctc": float(initial_loss.numpy()),
        "final_ctc": final_loss,
        "initial_gradient_norm": gradient_norm,
        "tiny_exact_overfit": fitted,
        "updates": update,
        "overfit_seconds": time.perf_counter() - started,
        "learnability_history": history,
        "augmentation": augmentation,
        "maximum_padding_logit_difference": max(padding_errors),
        "future_context_logit_differences": future_changes,
        "checkpoint_optimizer_restore_exact": restore_exact,
        "adapter": identity(),
        "configuration_sha256": sha256(CONFIG),
        "smoke_checkpoint_sha256": sha256(RUN / "smoke.keras"),
        "tflite_sha256": sha256(path),
        "tflite_bytes": path.stat().st_size,
        "tflite_ops": ops,
        "input_signatures": [
            d["shape_signature"].tolist() for d in interpreter.get_input_details()
        ],
        "output_signature": interpreter.get_output_details()[0]["shape_signature"].tolist(),
        "parity_cases": parity,
        "maximum_export_logit_error": max(r["max_logit_error"] for r in parity),
        "float32_no_quantization": True,
        "android_modified": False,
        "accuracy_claim": "NONE",
        "dev_inference": False,
        "test_accessed": False,
    }
    write_json_atomic(OUTPUT / "smoke_gate.json", report)
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("augmentation", "learnability_history", "parity_cases")
            },
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    smoke()
