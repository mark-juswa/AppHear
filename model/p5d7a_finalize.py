"""Finalize P5-D7A after the project-lead archive index; never extracts video."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d7a_semlex_extraction_prep_01"
PROGRESS = ROOT / "context/progress-tracker.md"
EXPECTED_PROGRESS = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
CONFIG = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
CONTRACT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p5a_dwpose_representation_v2_01/p5a_representation_contract.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(name: str) -> list[dict[str, str]]:
    with (OUT / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(name: str, value: object) -> None:
    path = OUT / name
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_text(name: str, value: str) -> None:
    path = OUT / name
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    accepted_classes = rows("p5d7a_human_accepted_class_set.csv")
    manifest = rows("semlex_accepted_raw_manifest.csv")
    join = rows("semlex_raw_join_audit.csv")
    duplicates = rows("semlex_duplicate_audit.csv")
    overlaps = rows("semlex_apphear_lineage_overlap_audit.csv")
    smoke = json.loads((OUT / "p5d7a_smoke_test_result.json").read_text(encoding="utf-8"))
    index = json.loads((OUT / "p5d7a_archive_index_summary.json").read_text(encoding="utf-8"))
    decisions = Counter(row["human_decision"] for row in accepted_classes)
    excluded = [row for row in join if row["status"] == "EXCLUDED"]
    reasons = Counter(row["reason"] for row in excluded)
    metadata_duplicate_rows = index["duplicate_metadata_rows_excluded"]
    if not (
        len(accepted_classes) == 65 and decisions == Counter({"ACCEPT_EXACT_FORM": 45, "ACCEPT_COMPATIBLE_VARIANT": 18, "ACCEPT_METADATA_EXACT": 2})
        and len(manifest) == 2425 and len({r["apphear_class_id"] for r in manifest}) == 65
        and len(excluded) == 161 and reasons == Counter({"MISSING_RAW_ARCHIVE_MEMBER": 161})
        and metadata_duplicate_rows == 80 and not overlaps and smoke["classification"] == "SMOKE_TEST_PASS"
        and sha(PROGRESS) == EXPECTED_PROGRESS
    ):
        raise RuntimeError("P5-D7A final integrity condition failed")

    raw_bytes = sum(int(row["raw_bytes"]) for row in manifest)
    durations = sorted(float(row["duration_ms"]) for row in manifest)
    median_duration = durations[len(durations) // 2]
    total_duration_hours = sum(durations) / 3_600_000
    smoke_seconds = smoke["elapsed_seconds_per_video"]
    # Three clips are deliberately a small smoke sample; include archive traversal overhead.
    runtime = {
        "candidate_videos": len(manifest), "accepted_classes": 65,
        "total_raw_bytes": raw_bytes, "total_raw_gib": raw_bytes / 1024**3,
        "median_video_duration_ms": median_duration,
        "total_source_video_duration_hours": total_duration_hours,
        "smoke_seconds_per_video": smoke_seconds,
        "smoke_median_seconds_per_video": smoke["median_elapsed_seconds_per_video"],
        "estimated_full_runtime_range_hours": [4.0, 7.0],
        "runtime_estimate_confidence": "LOW",
        "runtime_estimate_note": "Three CPU smoke clips plus one compressed-archive traversal; not a throughput benchmark.",
        "estimated_native_output_bytes": 114_000_000,
        "estimated_v2_output_bytes": 52_000_000,
        "estimated_logs_and_manifests_bytes": 5_000_000,
        "estimated_total_output_range_gib": [0.16, 0.35],
        "recommended_free_output_space_gib": 1.0,
        "maximum_single_temporary_raw_bytes": max(int(row["raw_bytes"]) for row in manifest),
        "storage_estimate_confidence": "MODERATE",
    }
    write_json("p5d7a_workload_estimate.json", runtime)

    manifest_wsl = "/mnt/f/ASL DATASET/5. Apphear3/artifacts/recognition_upgrade/p5_representation_v2/p5d7a_semlex_extraction_prep_01/semlex_accepted_raw_manifest.csv"
    output_wsl = "/mnt/g/SEM LEX/AppHear_P5D7_candidate/full"
    archive_wsl = "/mnt/g/SEM LEX/train.tar.gz"
    full_inner = f"cd '/mnt/f/ASL DATASET/5. Apphear3' && ~/apphear_p2a_dwpose/env/bin/python -m model.p5d7_semlex_extract_v2 extract-archive --manifest '{manifest_wsl}' --archive '{archive_wsl}' --output-root '{output_wsl}'"
    verify_inner = f"cd '/mnt/f/ASL DATASET/5. Apphear3' && ~/apphear_p2a_dwpose/env/bin/python -m model.p5d7_verify_full_extraction --manifest '{manifest_wsl}' --output-root '{output_wsl}'"
    full_command = f'wsl.exe bash -lc "{full_inner}"'
    verify_command = f'wsl.exe bash -lc "{verify_inner}"'
    runbook = f"""# Run full accepted Sem-Lex extraction

**Project-lead action only. Coding AI did not execute this command.**

## Frozen inputs

- Working directory: `F:\\ASL DATASET\\5. Apphear3`
- Windows interpreter for preparation only: `.\\.venv\\Scripts\\python.exe`
- Extraction interpreter: `~/apphear_p2a_dwpose/env/bin/python` in WSL
- Manifest: `{manifest_wsl}`
- Raw archive/root: `{archive_wsl}` / `G:\\SEM LEX`
- Native output: `{output_wsl}/native`
- V2 output: `{output_wsl}/v2`
- Status/log output: `{output_wsl}/completed`, `{output_wsl}/failures`, and `run_summary.json`
- Expected clips: **2,425** across **65 accepted classes**
- DWPose config: `rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py`
- DWPose checkpoint: `dw-ll_ucoco.pth` (`e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7`)

## Full extraction / resume command

```powershell
Set-Location 'F:\\ASL DATASET\\5. Apphear3'
{full_command}
```

The same command is the resume command. It verifies and skips successful outputs,
retains completed native/V2 pairs, and records per-sample failures without
corrupting manifest state. One failed clip does not erase successful clips. The
terminal reports archive percentage, completed, failed, and pending counts.

Estimated runtime: **4–7 hours (low confidence)**. Estimated retained outputs:
**0.16–0.35 GiB**; keep at least **1 GiB free** on G: for outputs and temporary work.

Success means the extraction exits successfully and the verification command
reports 2,425 completed pairs, zero missing/corrupt/shape/lineage failures, and
100% completion.

## Completion verification

```powershell
{verify_command}
```

If failures are reported, preserve the failure JSON files and return their output
for audit. Do not repair, merge, or train automatically.

**DO NOT START TRAINING AFTER THIS COMMAND FINISHES.**
"""
    write_text("RUN_FULL_SEMLEX_EXTRACTION.md", runbook)

    write_json("p5d7a_post_extraction_audit_contract.json", {
        "status": "PREPARED_NOT_EXECUTED", "next_stage": "P5D7B_SEMLEX_FULL_EXTRACTION_INTEGRITY_AUDIT",
        "required_checks": ["valid_v2_clip_count", "usable_classes", "signer_count", "signer_class_slots", "class_wise_retention", "coverage_loss_reasons", "dwpose_failures", "missingness", "two_hand_usability", "body_normalization_fallback_rates", "exact_duplicates", "apphear_lineage_overlap", "apphear_vs_semlex_v2_source_differences"],
        "training_authorized": False, "merge_authorized": False,
    })
    write_json("p5d7a_decision.json", {
        "classification": "P5D7A_READY_WITH_LINEAGE_EXCLUSIONS", "confidence": "HIGH",
        "accepted_raw_rows": 2425, "pre_extraction_exclusions": 241,
        "exclusion_breakdown": {"duplicate_metadata_rows": 80, "missing_raw_archive_members": 161},
        "exact_raw_duplicate_exclusions": 0, "apphear_train_overlaps": 0,
        "smoke_test": "PASS", "full_extraction_executed": False,
    })
    write_json("p5d7a_next_gate.json", {
        "selected_next_action": "PROJECT_LEAD_RUNS_FULL_SEMLEX_EXTRACTION",
        "recommended_computational_gate_after_run": "P5D7B_SEMLEX_FULL_EXTRACTION_INTEGRITY_AUDIT",
        "next_gate_executed": False,
    })
    write_json("p5d7a_integrity.json", {
        "passed": True, "accepted_classes": 65, "exact_form_classes": 47,
        "compatible_variant_classes": 18, "unresolved_excluded": ["IF", "OLD", "GET", "TURN", "ANY"],
        "review_provenance": "REVIEW_PROVENANCE_METADATA_INCOMPLETE",
        "raw_root": "G:\\SEM LEX", "archive_used_read_only": True,
        "archive_members_hashed": 51443, "raw_video_downloaded": False,
        "full_dwpose_extraction_executed": False, "full_v2_generation_executed": False,
        "smoke_videos_processed": 3, "dwpose_contract_verified": True,
        "v2_contract_verified": True, "temporal_contract_verified": True,
        "training_performed": False, "external_merge_performed": False,
        "protected_test_accessed": False, "p4_reopened": False,
        "android_modified": False, "popsign_used": False,
        "progress_tracker_sha256": sha(PROGRESS), "progress_tracker_untouched": True,
        "checkpoint_sha256": sha(CHECKPOINT), "config_sha256": sha(CONFIG),
        "v2_contract_sha256": sha(CONTRACT),
    })
    result = f"""# P5-D7A Sem-Lex extraction preparation result

Outcome: `P5D7A_READY_WITH_LINEAGE_EXCLUSIONS` (high confidence).

The 65-class human-accepted set was reconstructed without modifying human
decisions. The 2,666 metadata-row ceiling resolved to 2,586 unique sample IDs.
Eighty duplicate metadata rows and 161 samples absent from the supplied raw
archive were excluded, leaving **2,425 lineage-verified raw clips**. All 65
accepted classes remain represented. No exact raw-SHA duplicates, cross-class
mapping conflicts, AppHear TRAIN overlaps, or missing signer lineage were found.

Frozen DWPose-L, V2 `[96,238]`, normalization, and first-96/zero-tail temporal
contracts were verified. The three-video smoke test (HOT, BUT, YOUR; three
signers; exact and compatible-variant decisions) passed native extraction, V2
invariants, hashes, and lineage.

The full extraction was **not run**. The project lead must use
`RUN_FULL_SEMLEX_EXTRACTION.md`. Successful completion does not establish a
recognition benefit and does not authorize merging or training; it only enables
the governed P5-D7B integrity audit.
"""
    write_text("P5D7A_SEMLEX_EXTRACTION_PREP_RESULT.md", result)

    required = [
        "P5D7A_SEMLEX_EXTRACTION_PREP_RESULT.md", "p5d7a_integrity.json",
        "p5d7a_human_accepted_class_set.csv", "review_provenance_status.json",
        "semlex_raw_inventory.csv", "semlex_accepted_raw_manifest.csv",
        "semlex_raw_join_audit.csv", "semlex_duplicate_audit.csv",
        "semlex_apphear_lineage_overlap_audit.csv", "p5d7a_smoke_test_manifest.csv",
        "p5d7a_smoke_test_result.json", "p5d7a_workload_estimate.json",
        "RUN_FULL_SEMLEX_EXTRACTION.md", "p5d7a_post_extraction_audit_contract.json",
        "p5d7a_decision.json", "p5d7a_next_gate.json",
        "p5d7a_extraction_optimization_benchmark.json", "RUN_FASTER_EXACT_SEMLEX_EXTRACTION.md",
        "p5d7a_extraction_component_imprint.md",
    ]
    manifest_hashes = {name: sha(OUT / name) for name in required}
    for path in [ROOT / "model/p5d7_semlex_extract_v2.py", ROOT / "model/p5d7_verify_full_extraction.py", ROOT / "model/p5d7a_semlex_prepare.py", ROOT / "model/p5d7a_finalize.py", ROOT / "model/p5d7_parallel_extract.py", ROOT / "model/p5d7_compare_extraction_outputs.py"]:
        manifest_hashes[path.relative_to(ROOT).as_posix()] = sha(path)
    write_json("artifact_hash_manifest.json", {"algorithm": "SHA256", "artifacts": manifest_hashes, "self_hash_omitted": True})
    print(json.dumps({"passed": True, "mapped": 2425, "excluded": 241, "classification": "P5D7A_READY_WITH_LINEAGE_EXCLUSIONS", "full_extraction_executed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
