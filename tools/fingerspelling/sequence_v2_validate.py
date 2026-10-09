"""TRAIN-only loop resume smoke plus deterministic DEV-A stress-input validation.

No full training, DEV-B inference, RGB reading, Candidate01 execution or Android changes.
"""

from __future__ import annotations

import json
import time
from collections import Counter

import numpy as np

from model import fingerspelling_ctc as reference
from model.fingerspelling_sequence_v2 import RUN, engine
from model.fingerspelling_sequence_v2_encoder import CONFIG, configuration
from model.fingerspelling_sequence_v2_execution import RobustTemporalCache
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.expanded_training import FOUNDATION, manifests, read_json
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.sequence_v2_evidence import OUTPUT, receipts
from tools.fingerspelling.sequence_v2_smoke import choose_tiny
from tools.fingerspelling.tranche import single_writer


def main() -> None:
    p = configuration()
    tf = reference.tensorflow(p)
    rows = choose_tiny(receipts())
    run = RUN.with_name(RUN.name + "_smoke_execution_final")
    with single_writer(run):
        pause = engine(run, rows, tf, smoke=True, stop_after=1)
        complete = engine(run, rows, tf, smoke=True)
    all_choices = [
        c
        for path in sorted((run / "epochs").glob("*.json"))
        for c in read_json(path)["temporal_choices"]
    ]
    for rec in rows:
        if {c["requested"] for c in all_choices if c["sample_id"] == rec["sample_id"]} != set(
            p["train_regimes"]
        ):
            raise ValueError("[sequence-v2/validation] Four-regime cycle not covered")
    frozen_ids = read_json(OUTPUT / "tiny_subset.json")["samples"]
    if {r["sample_id"] for r in rows} != {r["sample_id"] for r in frozen_ids}:
        raise ValueError("[sequence-v2/validation] Tiny subset changed")
    # Validate all DEV-A stress inputs, with no performance scoring or tuning.
    cache = RobustTemporalCache(p)
    manifests_a = [r for r in manifests()["foundation"]["samples"] if r["split_role"] == "DEV"]
    stress_records = []
    for n, row in enumerate(manifests_a):
        rec = read_json(FOUNDATION / "features" / (row["sample_id"] + ".receipt.json"))
        for profile in ("moderate", "heavy", "contiguous"):
            view = "stress_" + profile
            x, y = cache.load(rec, view)
            if (
                not np.isfinite(x).all()
                or len(x) != rec["phone_frame_count"]
                or len(y) != len(row["normalized_transcript"])
            ):
                raise ValueError("[sequence-v2/stress] Input validity/timestep/target mismatch")
            info = cache.stress_info[(rec["sample_id"], view)]
            x2, y2, info2 = cache.augmented(rec, "phone", profile, -1)
            if not np.array_equal(x, x2) or not np.array_equal(y, y2) or info != info2:
                raise ValueError("[sequence-v2/stress] Nondeterministic stress view")
            stress_records.append(
                {
                    "view": view,
                    "raw_sha256": rec["raw_sha256"],
                    "features_sha256": sha256_bytes(x),
                    **info,
                }
            )
        if (n + 1) % 64 == 0:
            print(json.dumps({"event": "DEV_A_STRESS_VALIDATED", "sequences": n + 1}), flush=True)
    write_json_atomic(
        OUTPUT / "dev_a_stress_manifest.json",
        {
            "schema_version": "apphear.fingerspelling.dev_a_stress_manifest.v1",
            "configuration_sha256": sha256(CONFIG),
            "samples": stress_records,
            "dev_b_loaded": False,
            "model_inference": False,
            "test_accessed": False,
        },
    )
    # Host-only timing and dynamic-T/padding checks on smoke export. No Xiaomi claim.
    path = OUTPUT / "smoke_sequence_v2_fp32.tflite"
    model = tf.keras.models.load_model(
        REPO / "runs/fingerspelling_sequence_v2_01_smoke/smoke.keras", compile=False
    )
    # Recheck native/phone/augmented text parity with the frozen tiny-fit checkpoint;
    # this is inference only, including the finalized no-proposal presence mask.
    from model.fingerspelling_prefix_beam import decode_beam, decode_greedy
    from tools.fingerspelling.android_export import invoke

    parity = []
    train_cache = RobustTemporalCache(p)
    for rec in rows:
        for view in ("native", "phone", "stress_moderate", "stress_heavy", "stress_contiguous"):
            x, _ = train_cache.load(rec, view)
            values = [x[None], np.ones((1, len(x), 1), np.float32)]
            keras = model(values, training=False).numpy()[0]
            lite = invoke(tf, path, values)[0]
            error = float(np.max(np.abs(keras - lite)))
            greedy = decode_greedy(keras, 0.5)
            beam = decode_beam(keras, 0.5, 10, 1)[0]["prediction"]
            if (
                error > 1e-3
                or greedy != decode_greedy(lite, 0.5)
                or beam != decode_beam(lite, 0.5, 10, 1)[0]["prediction"]
            ):
                raise ValueError("[sequence-v2/parity] Finalized raw robustness parity failed")
            parity.append(
                {
                    "sample_id": rec["sample_id"],
                    "view": view,
                    "timesteps": len(x),
                    "max_logit_error": error,
                    "greedy": greedy,
                    "beam": beam,
                    "exact_decoded_parity": True,
                }
            )
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=2)
    inputs = interpreter.get_input_details()
    reference_model = tf.lite.Interpreter(
        model_path=str(
            REPO / "artifacts/fingerspelling_train4096_android_01/geometry_sequence.tflite"
        )
    )
    old_ops = {d["op_name"] for d in reference_model._get_ops_details()}
    new_ops = {d["op_name"] for d in interpreter._get_ops_details()}
    timings = []
    rng = np.random.default_rng(p["seed"])
    max_error = 0.0
    for length in (1, 17, 51, 128, 512):
        values = [
            rng.normal(size=(1, length, 405)).astype(np.float32),
            np.ones((1, length, 1), np.float32),
        ]
        pairs = [
            (next(d["index"] for d in inputs if d["shape"][-1] == v.shape[-1]), v) for v in values
        ]
        for idx, value in pairs:
            interpreter.resize_tensor_input(idx, value.shape, strict=True)
        interpreter.allocate_tensors()
        for idx, value in pairs:
            interpreter.set_tensor(idx, value)
        interpreter.invoke()
        duration = []
        for _ in range(12):
            t0 = time.perf_counter()
            interpreter.invoke()
            duration.append((time.perf_counter() - t0) * 1000)
        actual = interpreter.get_tensor(interpreter.get_output_details()[0]["index"])
        expected = model(values, training=False).numpy()
        error = float(np.max(np.abs(actual - expected)))
        max_error = max(max_error, error)
        if error > 1e-3:
            raise ValueError("[sequence-v2/validation] Dynamic T export failed")
        timings.append(
            {
                "timesteps": length,
                "host_cpu2_p50_ms": float(np.median(duration)),
                "host_cpu2_p95_ms": float(np.quantile(duration, 0.95)),
                "max_logit_error": error,
            }
        )
    report = {
        "status": "V2_EXECUTION_STRESS_EXPORT_VALIDATION_PASS",
        "pause": pause,
        "complete": complete["status"],
        "epochs": complete["epoch"],
        "resume": read_json(run / "resume_verification.json"),
        "training_requested_regimes": dict(Counter(c["requested"] for c in all_choices)),
        "ctc_fallback_count": sum(c["fallback"] for c in all_choices),
        "dev_a_sequences_stress_validated": len(manifests_a),
        "stress_artifact_count": len(stress_records),
        "stress_model_inference": False,
        "stress_manifest_sha256": sha256(OUTPUT / "dev_a_stress_manifest.json"),
        "host_cpu_timings_not_xiaomi": timings,
        "dynamic_t_max_logit_error": max_error,
        "finalized_policy_export_parity": parity,
        "finalized_policy_max_logit_error": max(r["max_logit_error"] for r in parity),
        "new_operator_names_vs_deployed": sorted(new_ops - old_ops),
        "deployed_operator_names": sorted(old_ops),
        "v2_operator_names": sorted(new_ops),
        "dev_b_loaded": False,
        "test_accessed": False,
        "accuracy_claim": "NONE_ENGINEERING_ONLY",
    }
    write_json_atomic(OUTPUT / "execution_validation.json", report)
    print(json.dumps(report, indent=2))


def sha256_bytes(array: np.ndarray) -> str:
    import hashlib

    return hashlib.sha256(array.tobytes()).hexdigest()


if __name__ == "__main__":
    main()
