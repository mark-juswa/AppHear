"""S2-R3 signer-grouped data roles (approved 2026-10-16; docs/audit/S2_R3_EXPERIMENT_PLAN).

Freezes, before any S2-R3 training, which signer/participant supplies FIT, CAL (checkpoint
selection) or HELD_OUT_EVAL data, so that selection is signer-disjoint from fitting and the
new held-out negative participants never influence training. Segmentation DEV, protected TEST,
the E6 signer and Tier-3 data are outside this split and never opened here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.s2_r3_context_suite import read_json, sha256, write_json  # noqa: E402

CONFIG_PATH = ROOT / "model/config/recognition_upgrade/s2_r3_data_split_rules_01.json"
FREEZE_PATH = ROOT / "model/config/recognition_upgrade/s2_r3_data_split_01.json"


def signer_rank(seed: int, signer: str) -> str:
    return hashlib.sha256(f"{seed}:{signer}".encode()).hexdigest()


def assign_positive_signers(
    clips: dict[str, dict[str, Any]], seed: int, cal_fraction: float, min_signers_to_split: int
) -> dict[str, str]:
    """Per source, the lowest-ranked ceil-free round(fraction * signers) signers become CAL;
    sources with too few signers stay wholly FIT (a single signer cannot be split)."""
    by_source: dict[str, set[str]] = defaultdict(set)
    for clip in clips.values():
        by_source[clip["source"]].add(clip["signer"])
    role: dict[str, str] = {}
    for source in sorted(by_source):
        signers = sorted(by_source[source], key=lambda s: signer_rank(seed, s))
        cal_count = 0
        if len(signers) >= min_signers_to_split:
            cal_count = max(1, round(cal_fraction * len(signers)))
        for position, signer in enumerate(signers):
            role[signer] = "CAL" if position < cal_count else "FIT"
    return role


def build(root: Path, rules: dict[str, Any]) -> dict[str, Any]:
    paths = rules["sources"]
    manifest = read_json(root / paths["phase7_sparse_view_manifest"])
    clips: dict[str, dict[str, Any]] = {}
    for row in manifest["rows"]:
        if row["phase7_partition"] in ("FIT", "CAL"):
            clips[row["sample_id"]] = {
                "signer": row["signer_id"],
                "source": row["source"],
                "family": "PHASE7_TRAIN_CLIP",
                "raw_path": row["source_raw_path"],
                "raw_sha256": row["source_raw_sha256"],
            }
        elif row["phase7_partition"] != "DEV":
            raise ValueError(f"[s2_r3/split] UNEXPECTED_PARTITION:{row['phase7_partition']}")
    s2r2 = read_json(root / paths["s2_r2_dataset_manifest"])["rows"]
    for row in s2r2:
        if row["domain"] == "ENRICHMENT_SIGN":
            video = Path(row["source_video_path"])
            clips.setdefault(
                row["sample_id"],
                {
                    "signer": row["signer_id"],
                    "source": row["source"],
                    "family": "ENRICHMENT_CLIP",
                    "video_path": str(video),
                    "video_sha256": row["source_video_sha256"],
                    "video_available": video.is_file()
                    and sha256(video) == row["source_video_sha256"],
                },
            )
    dev_signers = {row["signer_id"] for row in manifest["rows"] if row["phase7_partition"] == "DEV"}
    signer_role = assign_positive_signers(
        clips,
        int(rules["seed"]),
        float(rules["cal_signer_fraction"]),
        int(rules["min_signers_to_split"]),
    )
    if set(signer_role) & dev_signers:
        raise ValueError("[s2_r3/split] DEV_SIGNER_IN_TRAINING_SPLIT")
    positives = [
        {"sample_id": sample, **info, "role": signer_role[info["signer"]]}
        for sample, info in sorted(clips.items())
    ]
    phone = sorted({row["sample_id"] for row in s2r2 if row["domain"] == "PHONE_POSITIVE"})
    p1_intervals = {
        row["interval_id"]: row
        for row in csv.DictReader(open(root / paths["p1_intervals"], encoding="utf-8"))
    }
    participant_role = rules["negative_participant_roles"]
    p1 = []
    for row in s2r2:
        if row["domain"] != "P1_NEGATIVE":
            continue
        interval = p1_intervals[row["row_id"].removeprefix("p1::")]
        p1.append(
            {
                "row_id": row["row_id"],
                "participant": row["signer_id"],
                "role": participant_role[row["signer_id"]],
                "video_path": interval["video_path"],
                "video_sha256": interval["video_sha256"],
                "start_ms": float(interval["start_ms"]),
                "end_ms": float(interval["end_ms"]),
            }
        )
    n0 = []
    for row in csv.DictReader(open(root / paths["n0_capture_manifest"], encoding="utf-8")):
        if row["kind"] != "n0":
            continue
        n0.append(
            {
                "clip_id": row["clip_id"],
                "participant": row["participant_id"],
                "device": row["device_id"],
                "environment": row["environment_id"],
                "role": participant_role[row["participant_id"]],
                "video_path": row["video_path"],
                "video_sha256": row["sha256"],
                "duration_seconds": float(row["duration_seconds"]),
            }
        )
    fit_signers = {s for s, r in signer_role.items() if r == "FIT"}
    cal_signers = {s for s, r in signer_role.items() if r == "CAL"}
    roles_by_participant = defaultdict(set)
    for item in p1 + n0:
        roles_by_participant[item["participant"]].add(item["role"])
    if any(len(roles) != 1 for roles in roles_by_participant.values()):
        raise ValueError("[s2_r3/split] PARTICIPANT_SPANS_ROLES")
    summary = {
        "positive_clips": {
            role: sum(1 for p in positives if p["role"] == role) for role in ("FIT", "CAL")
        },
        "positive_signers": {"FIT": len(fit_signers), "CAL": len(cal_signers)},
        "fit_cal_signer_overlap": sorted(fit_signers & cal_signers),
        "dev_signer_overlap": sorted((fit_signers | cal_signers) & dev_signers),
        "enrichment_clips_video_unavailable": sorted(
            p["sample_id"] for p in positives if p.get("video_available") is False
        ),
        "negatives": {
            role: {
                "p1_rows": sum(1 for x in p1 if x["role"] == role),
                "n0_clips": sum(1 for x in n0 if x["role"] == role),
                "n0_seconds": round(sum(x["duration_seconds"] for x in n0 if x["role"] == role), 3),
                "participants": sorted({x["participant"] for x in p1 + n0 if x["role"] == role}),
            }
            for role in ("FIT", "CAL", "HELD_OUT_EVAL")
        },
    }
    return {
        "schema": "apphear.s2_r3.data_split.v1",
        "rules_sha256": sha256(CONFIG_PATH),
        "source_identity": {key: sha256(root / value) for key, value in paths.items()},
        "positives": positives,
        "phone_positive_design_signer": {
            "sample_ids": phone,
            "role": rules["phone_design_signer_role"],
        },
        "p1_negatives": p1,
        "n0_negatives": n0,
        "summary": summary,
        "outside_this_split": rules["outside_this_split"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze"])
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    record = build(args.evidence_root, read_json(CONFIG_PATH))
    if record["summary"]["fit_cal_signer_overlap"] or record["summary"]["dev_signer_overlap"]:
        raise ValueError("[s2_r3/split] SIGNER_OVERLAP")
    write_json(FREEZE_PATH, record)
    print(json.dumps(record["summary"], indent=2))


if __name__ == "__main__":
    main()
