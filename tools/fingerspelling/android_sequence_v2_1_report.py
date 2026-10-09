"""Recompute V2.1 engineering summaries from retained evidence, never inference/training."""

from __future__ import annotations

import json
from typing import Any

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.android_export import write_json
from tools.fingerspelling.android_sequence_v2_1_port import APP, OUT


def read(name: str) -> Any:
    return json.loads((OUT / name).read_text())


def summarize(values: list[float]) -> dict[str, float | int]:
    s = sorted(values)
    return {
        "count": len(s),
        "p50_ms": s[(len(s) - 1) // 2],
        "p95_ms": s[int((len(s) - 1) * 0.95)],
        "max_ms": s[-1],
    }


def report() -> None:
    host = read("export_parity.json")
    phone = read("xiaomi_fingerspell_sequence_v2_1_parity.json")
    beam = read("xiaomi_fingerspell_beam_parity.json")
    assert host["checkpoint_sha256"] == phone["model_manifest"]["checkpoint_sha256"]
    assert host["greedy_mismatches"] == host["beam_mismatches"] == 0
    assert phone["greedy_mismatches"] == phone["beam_mismatches"] == beam["text_mismatches"] == 0
    runtime = {}
    for view in ("native", "phone", "synthetic_parity_only"):
        rows = [r for r in phone["cases"] if r["view"] == view]
        runtime[view] = {
            "timesteps": [r["timesteps"] for r in rows],
            "model_last_invocation": summarize([r["model_ms"][-1] for r in rows]),
            "model_all_invocations": summarize([v for r in rows for v in r["model_ms"]]),
            "beam": summarize([r["beam_ms"] for r in rows]),
            "model_plus_both_decoders": summarize([r["warm_model_plus_decoders_ms"] for r in rows]),
            "scope": "SAVED_FIXTURES_CPU2; NOT_BUTTON_QUEUE_OR_UI_RENDER; SMALL_N_ORDER_STATISTICS",
        }
    write_json(OUT / "runtime_summary.json", runtime)
    changed = [
        REPO / f"tools/fingerspelling/android_sequence_v2_1_{name}.py"
        for name in ("export", "port", "evidence", "report")
    ]
    changed += [
        APP / "android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellModels.kt",
        APP
        / "android/app/src/androidTest/java/com/example/apphear/fingerspelling"
        / "SequenceV21ParityInstrumentedTest.kt",
        APP
        / "android/app/src/androidTest/java/com/example/apphear/fingerspelling"
        / "Train4096ParityInstrumentedTest.kt",
    ]
    write_json(
        OUT / "source_identity.json",
        {str(p): {"sha256": sha256(p), "bytes": p.stat().st_size} for p in changed},
    )
    write_json(
        OUT / "engineering_decision.json",
        {
            "status": "FINGERSPELL_V2_1_ANDROID_PASS"
            if (OUT / "physical_smoke.json").is_file()
            else "V2_1_ANDROID_ENGINEERING_PARITY_PASS",
            "candidate": phone["model_manifest"],
            "host_cases": 14,
            "android_cases": 14,
            "beam_cases": 523,
            "protected_inventory": read("preservation.json"),
            "unit_tests": read("unit_validation.json")["totals"],
            "runtime": runtime,
            "accuracy_claim": "NONE_NEW; EXISTING_OFFLINE_V2_1_REVIEW_ONLY",
            "production_promoted": False,
            "test_accessed": False,
            "live_smoke": read("physical_smoke.json")
            if (OUT / "physical_smoke.json").is_file()
            else "NOT_PERFORMED",
            "new_phone_accuracy_improvement_claim": "NONE; AMY_RETRIES_INACCURATE",
            "no_input_guard_added": False,
            "rollback": read("apk_identities.json")["rollback_apk"],
        },
    )
    print(json.dumps(runtime, indent=2))


if __name__ == "__main__":
    report()
