"""One post-audit phone-grid control: outer trim without changing retained sparse frames."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_emission import collect_logits
from model.fingerspelling_prefix_beam import decode_beam
from model.fingerspelling_residual_execution import ResidualSteps
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.residual_visual_package import load as load_visual
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from tools.fingerspelling.decoder_audit import load_logits, save_logits
from tools.fingerspelling.outer_boundary_oracle import OUT, OracleCache, paired, selected_input


def phase_locked_indices(full_phone: np.ndarray, oracle_native: np.ndarray) -> np.ndarray:
    """Intersection of existing real phone frames and annotation-selected real native frames."""
    if (
        full_phone.ndim != 1
        or oracle_native.ndim != 1
        or np.any(np.diff(full_phone) <= 0)
        or np.any(np.diff(oracle_native) <= 0)
    ):
        raise ValueError("[outer-oracle/phase] Non-chronological indices")
    retained = full_phone[np.isin(full_phone, oracle_native)]
    if not len(retained):
        raise ValueError("[outer-oracle/phase] No real phone observations in window")
    return retained


def run() -> dict[str, Any]:
    target = OUT / "phase_locked_control"
    target.mkdir(exist_ok=True)
    original = json.loads((OUT / "identity.json").read_text())
    windows = json.loads((OUT / "timing_alignment.json").read_text())["windows"]
    if sha256(OUT / "timing_alignment.json") != original["timing_alignment_sha256"]:
        raise ValueError("[outer-oracle/phase] Original alignment changed")
    rows = [r for r in b2.dataset(b2.DEFAULT_DATA) if r["split_role"] == "DEV"]
    if {r["sample_id"] for r in rows} != set(windows) or len(rows) != 256:
        raise ValueError("[outer-oracle/phase] Original DEV IDs changed")
    tensors, alignment_report = {}, []
    for r in rows:
        sid = r["sample_id"]
        raw = verify_raw(REPO / r["raw_path"], REPO / r["raw_receipt_path"], r, r["source_sha256"])
        emb, q = load_visual(r)
        w = windows[sid]
        selected = phase_locked_indices(
            np.asarray(w["full_phone_original_indices"], np.int32),
            np.asarray(w["oracle_native_original_indices"], np.int32),
        )
        # Selection is already sparse; native here performs no second temporal gate.
        packed, actual = selected_input(raw, selected, "native", emb, q, b2.policy()[0])
        if not np.array_equal(actual, selected):
            raise ValueError("[outer-oracle/phase] Frame-grid mutation")
        tensors[sid, "oracle", "phone"] = packed
        alignment_report.append(
            {
                "sample_id": sid,
                "selected_original_indices": selected.tolist(),
                "frame_indices": raw.frame_index[selected].tolist(),
                "timestamp_ms": raw.timestamp_ms[selected].tolist(),
                "input_length": len(selected),
                "ctc_headroom": len(selected) - r["ctc_min_timesteps"],
            }
        )
    write_json_atomic(target / "alignment.json", alignment_report)
    residual_cfg = json.loads(
        (REPO / "model/config/fingerspelling_decoder_audit_01.json").read_text()
    )
    base_cfg = json.loads(
        (REPO / "model/config/fingerspelling_residual_visual_01.json").read_text()
    )
    paths = {
        "b2": REPO / base_cfg["base_checkpoint"],
        "residual": REPO / residual_cfg["model_checkpoint"],
    }
    for arm, path in paths.items():
        if sha256(path) != original[f"{arm}_sha256"]:
            raise ValueError("[outer-oracle/phase] Model hash changed")
    identity = {
        "schema_version": "apphear.fingerspelling.outer_boundary_phase_control.v1",
        "original_identity_sha256": sha256(OUT / "identity.json"),
        "original_evaluation_sha256": sha256(OUT / "paired_evaluation.json"),
        "implementation_sha256": sha256(Path(__file__)),
        "alignment_sha256": sha256(target / "alignment.json"),
        "policy": "FULL_PHONE_GRID_INTERSECT_ORACLE_WINDOW_RECOMPUTE_ADAPTER",
        "blank_penalty": 0.5,
        "beam_width": 10,
        "test_accessed": False,
        "training": False,
    }
    write_json_atomic(target / "identity.json", identity)
    tf = reference.tensorflow(b2.policy()[1])
    report: dict[str, Any] = {"identity": identity, "models": {}}
    for arm, path in paths.items():
        print(json.dumps({"stage": "PHASE_LOCKED_PHONE_CONTROL", "arm": arm}), flush=True)
        model = tf.keras.models.load_model(path, compile=False)

        class Steps:
            def __init__(self, m: Any):
                self.model = m

            def infer(self, x: Any, mask: Any) -> Any:
                return self.model([x, mask], training=False)

        steps: Any = ResidualSteps(tf, model) if arm == "residual" else Steps(model)
        cache = OracleCache(tensors, arm, "oracle")
        start = time.perf_counter()
        full = load_logits(
            OUT / f"{arm}_full_phone_logits.npz",
            {**original, "arm": arm, "condition": "full", "view": "phone"},
        )
        logit_id = {**identity, "arm": arm}
        logit_path = target / f"{arm}_oracle_phone_logits.npz"
        if logit_path.exists():
            oracle = load_logits(logit_path, logit_id)
        else:
            oracle = collect_logits(
                tf, cast(Any, steps), cast(Any, cache), rows, "phone", b2.policy()[1]["batch_size"]
            )
            save_logits(logit_path, oracle, logit_id)
        decoded = []
        for values in [full, oracle]:
            decoded.append(
                [
                    {k: v for k, v in r.items() if k != "logits"}
                    | {"prediction": decode_beam(r["logits"], 0.5, 10, 1)[0]["prediction"]}
                    for r in values
                ]
            )
        report["models"][arm] = paired(decoded[0], decoded[1], windows)
        report["models"][arm]["runtime_seconds"] = time.perf_counter() - start
        write_json_atomic(target / "paired_evaluation.json", report)
        print(
            json.dumps(
                {
                    "arm": arm,
                    "full_cer": report["models"][arm]["full"]["cer"],
                    "oracle_cer": report["models"][arm]["oracle"]["cer"],
                }
            ),
            flush=True,
        )
    return {
        "status": "PHONE_GRID_CONTROL_EVALUATED",
        "report": str(target / "paired_evaluation.json"),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
