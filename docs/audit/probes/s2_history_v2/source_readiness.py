"""S2-R3 build step 2: read-only source-data readiness audit for R3a stitched training.

Inventories every planned FIT/CAL source, verifies hashes and human labels, checks signer
separation against DEV / Tier-2 / reserved populations, and tests whether sources that only
kept derived features can be re-extracted from their original video byte-exactly.
Writes one JSON report; never modifies artifacts.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])

import eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter as p7  # noqa: E402
import eval.runtime_diagnostics.s2_r2_continuous_domain_correction as r2  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    load_capture,
)

# Point the frozen research modules at the research checkout's artifacts (read-only use).
for module in (p7, r2):
    for name, value in list(vars(module).items()):
        if isinstance(value, Path) and str(value).startswith(str(REPO)):
            relative = value.relative_to(REPO)
            if relative.parts and relative.parts[0] == "artifacts":
                setattr(module, name, ROOT / relative)


def main() -> None:
    report: dict[str, Any] = {"schema": "apphear.s2_r3.source_readiness.v1"}
    manifest = suite.read_json(p7.OUT / "sparse_view_manifest.json")
    split = suite.read_json(p7.OUT / "frozen_fit_cal_split.json")
    fit_ids, cal_ids = set(split["fit_sample_ids"]), set(split["cal_sample_ids"])
    annotations = {
        row["sample_id"]: row
        for row in suite.read_json(
            ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/"
            "phase5_1t_2_bounded_segmentation_seed_dataset_01/segmentation_human_annotations.json"
        )["annotations"]
    }

    # 1. Phase-7 complete-source raw (FIT / CAL / DEV)
    phase7: dict[str, Any] = defaultdict(lambda: {"views": 0, "clips": set(), "signers": set(),
                                                  "raw_ok": 0, "raw_bad": [], "active_labels": 0,
                                                  "human_labelled_clips": set()})
    checked_raw: dict[str, bool] = {}
    for item in manifest["rows"]:
        part = item["phase7_partition"]
        entry = phase7[part]
        entry["views"] += 1
        entry["clips"].add(item["sample_id"])
        entry["signers"].add(item["signer_id"])
        raw_path = Path(item["source_raw_path"])
        if str(raw_path) not in checked_raw:
            checked_raw[str(raw_path)] = raw_path.is_file() and suite.sha256(raw_path) == item["source_raw_sha256"]
        if checked_raw[str(raw_path)]:
            entry["raw_ok"] += 1
        else:
            entry["raw_bad"].append(item["view_key"])
        with np.load(item["feature_path"], allow_pickle=False) as data:
            entry["active_labels"] += int(np.sum(np.asarray(data["labels"]) == 1))
        ann = annotations.get(item["sample_id"])
        if ann and not ann["ambiguous_or_unusable"] and ann["human_sign_start_ms"] is not None:
            entry["human_labelled_clips"].add(item["sample_id"])
    assert {k for k in phase7} == {"FIT", "CAL", "DEV"}
    assert all(s in fit_ids for s in phase7["FIT"]["clips"]) and all(s in cal_ids for s in phase7["CAL"]["clips"])
    report["phase7"] = {
        part: {"views": e["views"], "clips": len(e["clips"]), "signers": len(e["signers"]),
               "views_with_verified_raw": e["raw_ok"], "views_missing_or_bad_raw": e["raw_bad"],
               "active_labels": e["active_labels"],
               "human_labelled_clips": len(e["human_labelled_clips"])}
        for part, e in phase7.items()
    }
    signers = {part: set(e["signers"]) for part, e in phase7.items()}

    # 2. S2-R2 enrichment + P1 + exact-phone rows (features only on disk)
    s2rows = suite.read_json(r2.OUT / "main_candidate/dataset_manifest.json")["rows"]
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in s2rows:
        by_domain[row["domain"]].append(row)
    enrichment = by_domain["ENRICHMENT_SIGN"]
    enrich_ids = sorted({row["sample_id"] for row in enrichment})
    video_ok = {
        row["sample_id"]: Path(row["source_video_path"]).is_file()
        and suite.sha256(Path(row["source_video_path"])) == row["source_video_sha256"]
        for row in enrichment
    }
    signers["ENRICHMENT"] = {row["signer_id"] for row in enrichment}
    p1_csv = {row["interval_id"]: row for row in csv.DictReader(open(r2.P1_INTERVALS, encoding="utf-8"))}
    p1_rows = by_domain["P1_NEGATIVE"]
    p1_video_ok = {}
    for row in p1_rows:
        interval = p1_csv[row["row_id"].removeprefix("p1::")]
        path = Path(interval["video_path"])
        p1_video_ok[row["row_id"]] = path.is_file() and suite.sha256(path) == interval["video_sha256"]
    signers["P1_FIT"] = {row["signer_id"] for row in p1_rows if row["role"] == "FIT"}
    signers["P1_DEV"] = {row["signer_id"] for row in p1_rows if row["role"] != "FIT"}
    phone = by_domain["PHONE_POSITIVE"]
    signers["PHONE_DESIGN"] = {row["signer_id"] for row in phone}

    # 3. Byte-exact re-extraction checks (one enrichment clip, one P1 interval)
    from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline

    assets = REPO / "android/app/src/main/assets/perception_vnext"
    runtime = Candidate01Offline(assets / "dwpose_t_singlepass.onnx", assets / "hand_landmarks_detector.tflite")
    available = sorted({row['sample_id'] for row in enrichment if video_ok[row['sample_id']]})
    unavailable = sorted(set(enrich_ids) - set(available))
    probe_enrich = available[0]
    re_rows = r2._extract_enrichment_rows(runtime, {probe_enrich})
    stored = {row["view_key"]: row for row in enrichment if row["sample_id"] == probe_enrich}
    enrich_check = {}
    for new in re_rows:
        old = np.load(stored[new["view_key"]]["feature_path"], allow_pickle=False)
        enrich_check[new["view_key"]] = {
            "shape_equal": old["features"].shape == new["features"].shape,
            "max_abs": float(np.max(np.abs(old["features"] - new["features"]))) if old["features"].shape == new["features"].shape else None,
            "labels_equal": bool(np.array_equal(old["labels"], new["labels"])),
        }
    shortest = min(p1_rows, key=lambda row: row["observation_count"])
    re_p1 = r2._extract_p1_rows(runtime, {shortest["row_id"].removeprefix("p1::")})[0]
    old = np.load(shortest["feature_path"], allow_pickle=False)
    p1_check = {
        "row_id": shortest["row_id"],
        "shape_equal": old["features"].shape == re_p1["features"].shape,
        "max_abs": float(np.max(np.abs(old["features"] - re_p1["features"]))) if old["features"].shape == re_p1["features"].shape else None,
    }
    runtime.close()

    # 4. Exact phone FIT positives (raw kept in capture arrays)
    capture = load_capture(ROOT / "phone_pull_s2_exact_parity/session_20260921T153138Z", require_full_session=False)
    phone_check = {
        "observations": capture.count,
        "raw_to_378_vs_android_max_abs": float(
            np.max(np.abs(suite.features_for_raw(capture.raw, "v1") - capture.android_features))),
        "labelled_rows_fit": sum(row["observation_count"] for row in phone if row["role"] == "FIT"),
        "labelled_rows_internal_dev": sum(row["observation_count"] for row in phone if row["role"] != "FIT"),
    }

    # 5. Signer separation
    tier2 = {
        "SEP27_TRANSITION": "supervisor_transition_design_01 (Xiaomi; design signer, LIKELY same person as PHONE_DESIGN)",
        "OCT15_COMPACT": "stage2_design_signer_01 (Xiaomi; design signer, LIKELY same person as PHONE_DESIGN)",
        "SEP23_INDEPENDENT": "phone_validation_signer_01 (ITEL A665L; declared distinct)",
        "SEP23_REPRESENTATIVE": "representative_phone_signer_01 (Xiaomi; declared distinct)",
    }
    overlap = {
        f"{a}&{b}": sorted(signers[a] & signers[b])
        for a in signers for b in signers if a < b and signers[a] & signers[b]
    }
    report.update({
        "enrichment": {"rows": len(enrichment), "clips": len(enrich_ids),
                       "clips_with_verified_video": len(available), "clips_video_unavailable": unavailable,
                       "raw_on_disk": False,
                       "reextraction_check": {"sample_id": probe_enrich, "views": enrich_check}},
        "p1_negatives": {"rows": len(p1_rows), "fit_rows": sum(r["role"] == "FIT" for r in p1_rows),
                         "videos_verified": sum(p1_video_ok.values()), "raw_on_disk": False,
                         "observations": sum(r["observation_count"] for r in p1_rows),
                         "reextraction_check": p1_check},
        "exact_phone_positive": phone_check,
        "signers": {k: sorted(v) for k, v in signers.items()},
        "signer_overlaps": overlap,
        "tier2_signer_roles": tier2,
        "reserved_never_opened": ["protected TEST", "E6 0F747C-S001", "future independent phone signer",
                                  "P03-P06 / N0 (unused negative participants)"],
    })
    OUT.write_text(json.dumps(report, indent=1, default=list), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("phase7", "enrichment", "p1_negatives", "exact_phone_positive", "signer_overlaps")}, indent=1, default=list))
    print({k: len(v) for k, v in signers.items()})


if __name__ == "__main__":
    main()
