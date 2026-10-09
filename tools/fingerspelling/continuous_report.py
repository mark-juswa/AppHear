"""Build a compact evidence summary; never treat a supervisor smoke as accuracy."""

import hashlib
import json
import zipfile

import numpy as np

from tools.fingerspelling.continuous_stage import NEW, OUT, ROOT


def read(name):
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None


def summary(values):
    return {
        "n": len(values),
        **(
            {
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
                "max": max(values),
            }
            if values
            else {}
        ),
    }


def main():
    evidence = {
        "baseline": "b48594c4942d9e9ac0d94ff96396e80b9f049c0a",
        "worktree": str(NEW),
        "branch": "codex/fingerspell-continuous-oct05",
        "mode": "AUTOMATIC_HELD_LETTER_EXPERIMENTAL",
        "accuracy_claim": "NONE",
        "training": False,
        "test_payload_accessed": False,
    }
    evidence["preservation"] = read("preservation_after.json")
    for name in (
        "device_single_letter_parity.json",
        "device_model_parity.json",
        "device_flow.json",
    ):
        data = read(name)
        if data:
            evidence[name] = {
                k: v for k, v in data.items() if k not in ("rows", "cases", "model_manifest")
            }
    evidence["private_apks"] = {
        p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
        for p in (OUT / "private_apks").glob("*.apk")
    }
    previous = (
        ROOT
        / "artifacts/fingerspelling_single_letter_01/private_apks"
        / "app-debug-private-single-letter.apk"
    )
    current = OUT / "private_apks/app-debug-private-continuous.apk"
    if previous.exists() and current.exists():
        with zipfile.ZipFile(previous) as old, zipfile.ZipFile(current) as new:
            names = [n for n in old.namelist() if n.startswith("assets/") and not n.endswith("/")]
            changed = [n for n in names if n not in new.namelist() or old.read(n) != new.read(n)]
            evidence["apk_assets"] = {
                "prior_assets_checked": len(names),
                "changed_prior_assets": changed,
                "added_assets": [
                    n for n in new.namelist() if n.startswith("assets/") and n not in old.namelist()
                ],
            }
    device = read("device_camera_smoke.json")
    if device:
        events = device.get("events", [])
        evidence["camera_smoke"] = {
            "mode": device["mode"],
            "preview": device["preview"],
            "confirmed": device["confirmed"],
            "cadence": device["cadence"],
            "event_count": len(events),
            "inference_calls": device["inference_calls"],
            "skipped_busy": device["skipped_busy"],
            "stale_results": device["stale_results"],
            "accepted_letters": [e["raw_letter"] for e in events if e["added_to_preview"]],
            "model_ms": summary([e["model_ms"] for e in events]),
            "decoder_ms": summary([e["decoder_ms"] for e in events]),
            "worker_ms": summary([e["worker_ms"] for e in events]),
            "accuracy_claim": "NONE_NONEXPERT_SUPERVISOR_ENGINEERING_SMOKE",
        }
    evidence["physical_evidence_pending"] = device is None
    evidence["supervisor_confirmation"] = {
        "settings_and_automatic_flow": "Its good and working",
        "return_to_word": "WORD works",
        "exact_preview_not_supplied": True,
        "qualified_signer": False,
    }
    evidence["retention"] = "EXPERIMENTAL_AUTOMATIC_HELD_LETTER_FLOW_ENGINEERING_PASS_ONLY"
    (OUT / "summary.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
