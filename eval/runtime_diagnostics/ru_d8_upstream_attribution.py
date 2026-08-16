"""Build bounded RU-D8 failure attribution from frozen RU-D7 phone evidence."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d7/phone_bc_01"
DEFAULT_DECISIONS = ROOT / "context/recognition_upgrade/ru_d8_attribution_decisions.csv"
OUTCOMES = (
    "HEALTHY",
    "SIGN_FORM_UNCERTAIN",
    "PERCEPTION_FAILURE",
    "S5_GATE_FAILURE",
    "S6_CLASSIFIER_FAILURE",
)
B_BRANCH = "B_ru_d3_cleanup_seed_303"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def as_rank(value: str) -> str | int:
    rank = int(value)
    return rank if rank > 0 else ""


def s5_status(row: dict[str, str]) -> str:
    onset = int(row["s5_onset_frame"])
    release = int(row["s5_release_frame"])
    if onset < 0:
        return "NO_ONSET"
    if release < 0:
        return "ONSET_NO_RELEASE"
    return "ONSET_RELEASE_RECORDED"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    args = parser.parse_args()

    diagnostics = read_csv(args.run_dir / "reports/ru_d7_capture_diagnostics.csv")
    comparisons = read_csv(args.run_dir / "reports/ru_d7_attempt_bc.csv")
    decisions = {int(row["capture_order"]): row for row in read_csv(args.decisions)}
    retained = [row for row in diagnostics if row["attempts_valid"].lower() == "true"]
    if len(retained) != 24 or len(decisions) != 24:
        raise ValueError(
            f"RU-D8 requires 24 retained attempts, got {len(retained)}/{len(decisions)}"
        )
    if {int(row["capture_order"]) for row in retained} != set(decisions):
        raise ValueError("decision rows do not match retained RU-D7 capture orders")
    if any(row["primary_outcome"] not in OUTCOMES for row in decisions.values()):
        raise ValueError("unknown RU-D8 primary outcome")

    predictions: dict[tuple[str, str], dict[str, str]] = {}
    for row in comparisons:
        if row["branch"] == B_BRANCH:
            predictions[(row["attempt_id"], row["span_type"])] = row

    attempts: list[dict[str, Any]] = []
    for base in sorted(retained, key=lambda row: int(row["capture_order"])):
        order = int(base["capture_order"])
        decision = decisions[order]
        actual = predictions[(base["attempt_id"], "ACTUAL_RUNTIME_WINDOW")]
        oracle = predictions[(base["attempt_id"], "ORACLE_MANUAL_SPAN")]
        status = s5_status(base)
        no_s5 = status == "NO_ONSET"
        required_coverage = (
            base["two_hand_coverage"] if base["expected_hands"] == "two" else base["hand_coverage"]
        )
        if no_s5 and decision["necessary_landmarks_present"] == "N/A":
            raise ValueError(f"order {order}: no-S5 landmark answer missing")
        if not no_s5 and decision["no_s5_conclusion"] != "N/A":
            raise ValueError(f"order {order}: unexpected no-S5 conclusion")
        attempts.append(
            {
                "capture_order": order,
                "target_sign": base["ground_truth"],
                "attempt_number": base["repetition_id"],
                "attempt_id": base["attempt_id"],
                "visual_form_confidence": decision["visual_form_confidence"],
                "required_hand_coverage": required_coverage,
                "any_hand_coverage": base["hand_coverage"],
                "two_hand_coverage": (
                    base["two_hand_coverage"] if base["expected_hands"] == "two" else ""
                ),
                "expected_hands": base["expected_hands"],
                "actual_s5_status": status,
                "actual_s5_onset_frame": (
                    base["s5_onset_frame"] if int(base["s5_onset_frame"]) >= 0 else ""
                ),
                "actual_s5_release_frame": (
                    base["s5_release_frame"] if int(base["s5_release_frame"]) >= 0 else ""
                ),
                "actual_target_rank_b": as_rank(actual["target_rank"]),
                "actual_top5_b": actual["top5"],
                "oracle_target_rank_b": as_rank(oracle["target_rank"]),
                "oracle_top5_b": oracle["top5"],
                "no_s5_necessary_landmarks_present": (
                    decision["necessary_landmarks_present"] if no_s5 else ""
                ),
                "no_s5_oracle_ranked_target_well": (
                    decision["no_s5_oracle_ranked_well"] if no_s5 else ""
                ),
                "no_s5_conclusion": decision["no_s5_conclusion"] if no_s5 else "",
                "primary_failure_attribution": decision["primary_outcome"],
                "reason": decision["reason"],
            }
        )

    report_dir = args.run_dir / "reports/ru_d8"
    write_csv(report_dir / "ru_d8_attempt_attribution.csv", attempts)

    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attempts:
        by_class[str(row["target_sign"])].append(row)
    class_rows: list[dict[str, Any]] = []
    for gloss in sorted(by_class):
        rows = by_class[gloss]
        counts = Counter(row["primary_failure_attribution"] for row in rows)
        two_hand = [float(row["two_hand_coverage"]) for row in rows if row["two_hand_coverage"]]
        class_rows.append(
            {
                "target_sign": gloss,
                "retained_attempts": len(rows),
                "healthy": counts["HEALTHY"],
                "sign_form_uncertain": counts["SIGN_FORM_UNCERTAIN"],
                "perception_failure": counts["PERCEPTION_FAILURE"],
                "s5_gate_failure": counts["S5_GATE_FAILURE"],
                "s6_classifier_failure": counts["S6_CLASSIFIER_FAILURE"],
                "mean_required_hand_coverage": sum(
                    float(row["required_hand_coverage"]) for row in rows
                )
                / len(rows),
                "mean_two_hand_coverage": sum(two_hand) / len(two_hand) if two_hand else "",
                "class_reading": "|".join(
                    f"{outcome}:{counts[outcome]}" for outcome in OUTCOMES if counts[outcome]
                ),
            }
        )
    write_csv(report_dir / "ru_d8_class_summary.csv", class_rows)

    overall = Counter(row["primary_failure_attribution"] for row in attempts)
    overall_rows = [
        {
            "primary_outcome": outcome,
            "attempt_count": overall[outcome],
            "share_of_retained": overall[outcome] / len(attempts),
            "counted_as_system_failure": outcome not in {"HEALTHY", "SIGN_FORM_UNCERTAIN"},
        }
        for outcome in OUTCOMES
    ]
    write_csv(report_dir / "ru_d8_overall_failure_counts.csv", overall_rows)

    no_s5_rows = [row for row in attempts if row["actual_s5_status"] == "NO_ONSET"]
    if len(no_s5_rows) != 8:
        raise ValueError(f"expected eight no-S5 retained attempts, got {len(no_s5_rows)}")
    write_csv(report_dir / "ru_d8_no_s5_attribution.csv", no_s5_rows)

    recommendation = f"""# RU-D8 Upstream Failure Attribution

## Overall outcome

| Primary outcome | Attempts |
|---|---:|
| HEALTHY | {overall["HEALTHY"]} |
| SIGN_FORM_UNCERTAIN | {overall["SIGN_FORM_UNCERTAIN"]} |
| PERCEPTION_FAILURE | {overall["PERCEPTION_FAILURE"]} |
| S5_GATE_FAILURE | {overall["S5_GATE_FAILURE"]} |
| S6_CLASSIFIER_FAILURE | {overall["S6_CLASSIFIER_FAILURE"]} |

The eight no-S5 attempts are not one failure type: four are S5-primary, three are
perception-primary, and one is excluded for sign-form uncertainty.

## Ranked next engineering effort

1. **MediaPipe/perception reliability.** Five direct failures occur before S5/S6, including
   repeated loss of visually present two-hand evidence. This stage also constrains what S5 and
   S6 can possibly recover.
2. **S5 onset behavior on adequate one-hand evidence.** Four direct failures remain after visual
   and frame-level landmark review: KNOW R1, WHO R1/R2, and WE R2. WHO also has a secondary S6
   problem, so an S5-only change would not make WHO recognizable.
3. **S6 classifier/domain generalization.** Three direct failures have adequate perception and a
   usable S5 span: SISTER R1, NOW R1, and KNOW R2. WHO R1/R2 additionally remain extremely poor
   under oracle replay, but S5 is their earlier primary failure.

The eight form-uncertain controls are not counted as system failures. No fix is authorized by
RU-D8, and oracle replay remains diagnostic only.
"""
    (report_dir / "RU_D8_ATTRIBUTION_RESULT.md").write_text(recommendation, encoding="utf-8")
    print(
        f"RU-D8 complete: retained={len(attempts)} no_s5={len(no_s5_rows)} "
        f"counts={dict(overall)} output={report_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
