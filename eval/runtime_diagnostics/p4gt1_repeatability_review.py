"""Freeze provisional P4-GT1 Pass-1 truth and run the blinded repeatability review."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import tkinter as tk
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageTk

from eval.runtime_diagnostics.p4c2r_truth_review import (
    ALL_FIELDS,
    UNREVIEWED,
    ReviewIntegrityError,
    atomic_csv,
    atomic_json,
    atomic_text,
    dataset_hash,
    read_csv,
    review_row_id,
    sha256,
)
from eval.runtime_diagnostics.p4gt1_pass1_review import (
    C2R_REVIEW,
    EXPECTED_ANNOTATION,
    EXPECTED_C2R_REVIEW,
    EXPECTED_DATASET,
    OUT,
    REPORT,
    ROOT,
    STANDARD,
    V1,
    GT1Store,
    verify_sources,
)
from eval.runtime_diagnostics.p4gt1_pass1_review import (
    QUEUE as PASS1_QUEUE,
)
from eval.runtime_diagnostics.p4gt1_pass1_review import (
    REVIEW as PASS1_REVIEW,
)
from eval.runtime_diagnostics.p4gt1_pass1_review import (
    ReviewApp as Pass1ReviewApp,
)

PASS1_FULL = OUT / "p4gt1_pass1_full.csv"
QUEUE = OUT / "p4gt1_repeatability_queue.csv"
REVIEW = OUT / "p4gt1_repeatability_review.csv"
SAMPLE = OUT / "p4gt1_repeatability_sample_manifest.csv"
BLINDING = OUT / "p4gt1_repeatability_blinding_manifest.json"
PROVENANCE = OUT / "p4gt1_repeatability_provenance.json"
PREPARE_RESULT = OUT / "p4gt1_repeatability_prepare_result.json"
HASH_MANIFEST = OUT / "p4gt1_repeatability_artifact_hash_manifest.json"
PASS1_REPORT_SNAPSHOT = OUT / "P4GT1_PASS1_REVIEW_READY_REPORT.md"
SAMPLE_SEED = "P4GT1_REPEATABILITY_SAMPLE_V1_20260825"
ORDER_SEED = "P4GT1_REPEATABILITY_ORDER_V1_20260825"
UI_VERSION = "P4GT1_REPEATABILITY_VISIBILITY_UI_V1.0.0"


class RepeatabilityStore(GT1Store):
    def __init__(self, path: Path = REVIEW, *, verify_images: bool = True) -> None:
        super().__init__(path, verify_images=verify_images)
        self.journal = path.parent / "p4gt1_repeatability_completed_label_edit_journal.jsonl"
        self.backups = path.parent / "repeatability_review_backups"


def _state(left: str, right: str) -> str:
    if "UNCERTAIN" in (left, right):
        return "UNCERTAIN"
    if left == "NO" and right == "NO":
        return "ZERO"
    if left == "YES" and right == "YES":
        return "TWO"
    return "ONE"


def verify_completed_pass1() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    truth, c2r = verify_sources()
    if sha256(V1) != EXPECTED_ANNOTATION or dataset_hash(truth) != EXPECTED_DATASET:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    if sha256(C2R_REVIEW) != EXPECTED_C2R_REVIEW:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    queue = read_csv(PASS1_QUEUE)
    review = read_csv(PASS1_REVIEW)
    if len(queue) != 310 or len(review) != 310:
        raise ReviewIntegrityError("P4GT1_INCOMPLETE_HUMAN_REVIEW")
    queue_by_id = {row["review_row_id"]: row for row in queue}
    if len(queue_by_id) != 310:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    for row in review:
        if row["reviewer_status"] != "COMPLETE" or row["revision_count"] != "0":
            raise ReviewIntegrityError("P4GT1_INCOMPLETE_HUMAN_REVIEW")
        source = queue_by_id.get(row["review_row_id"])
        if source is None:
            raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        for field in (
            "source_annotation_row_id",
            "sequence_id",
            "frame_index",
            "image_sha256",
            "image_path",
        ):
            if row[field] != source[field]:
                raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        image = Path(row["image_path"])
        if not image.is_file() or sha256(image) != row["image_sha256"]:
            raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    return truth, c2r


def _diverse_sample(
    rows: list[dict[str, str]], count: int, source: str, state: str
) -> list[dict[str, str]]:
    remaining = list(rows)
    selected: list[dict[str, str]] = []
    signer_counts: Counter[str] = Counter()
    sequence_counts: Counter[str] = Counter()
    while remaining and len(selected) < count:
        chosen = min(
            remaining,
            key=lambda row: (
                sequence_counts[row["sequence_id"]],
                signer_counts[row["signer_id"]],
                hashlib.sha256(
                    f"{SAMPLE_SEED}|{source}|{state}|{row['frame_id']}".encode()
                ).hexdigest(),
            ),
        )
        remaining.remove(chosen)
        selected.append(chosen)
        signer_counts[chosen["signer_id"]] += 1
        sequence_counts[chosen["sequence_id"]] += 1
    if len(selected) != count:
        raise ReviewIntegrityError(f"Insufficient {source}/{state} repeatability candidates")
    return selected


def prepare() -> dict[str, Any]:
    if REVIEW.exists() and any(row["reviewer_status"] == "COMPLETE" for row in read_csv(REVIEW)):
        raise ReviewIntegrityError("P4GT1 repeatability review already started; immutable")
    truth, c2r = verify_completed_pass1()
    truth_by_id = {row["annotation_row_id"]: row for row in truth}
    c2r_by_id = {row["source_annotation_row_id"]: row for row in c2r}
    new_by_id = {row["source_annotation_row_id"]: row for row in read_csv(PASS1_REVIEW)}
    reused_ids = set(c2r_by_id)
    if len(reused_ids) != 148 or len(new_by_id) != 310 or reused_ids & set(new_by_id):
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    if reused_ids | set(new_by_id) != set(truth_by_id):
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")

    full: list[dict[str, str]] = []
    for frame_id, source in truth_by_id.items():
        if frame_id in c2r_by_id:
            reviewed = c2r_by_id[frame_id]
            pass1_source = "REUSED_P4C2R_148"
            review_row = reviewed["review_row_id"]
        else:
            reviewed = new_by_id[frame_id]
            pass1_source = "NEW_P4GT1_310"
            review_row = reviewed["review_row_id"]
        full.append(
            {
                "frame_id": frame_id,
                "signer_id": source["signer_id"],
                "sequence_id": source["sequence_id"],
                "frame_index": source["frame_index"],
                "source_sha256": source["image_sha256"],
                "source_image_path": source["review_image_path"],
                "visible_left": reviewed["visible_left"],
                "visible_right": reviewed["visible_right"],
                "frame_state": reviewed["frame_state"],
                "pass1_source": pass1_source,
                "pass1_review_row_id": review_row,
                "pass1_reviewed_utc": reviewed["reviewed_utc"],
                "pass1_review_sha256": (
                    sha256(C2R_REVIEW)
                    if pass1_source == "REUSED_P4C2R_148"
                    else sha256(PASS1_REVIEW)
                ),
            }
        )
    full.sort(key=lambda row: row["frame_id"])
    atomic_csv(PASS1_FULL, full, list(full[0]))

    pools: dict[tuple[str, str], list[dict[str, str]]] = {}
    for source in ("REUSED_P4C2R_148", "NEW_P4GT1_310"):
        for state in ("ZERO", "ONE", "TWO"):
            pools[(source, state)] = [
                row
                for row in full
                if row["pass1_source"] == source
                and _state(row["visible_left"], row["visible_right"]) == state
            ]
    quotas = {
        ("REUSED_P4C2R_148", "ZERO"): 13,
        ("NEW_P4GT1_310", "ZERO"): 27,
        ("REUSED_P4C2R_148", "ONE"): 16,
        ("NEW_P4GT1_310", "ONE"): 24,
        ("REUSED_P4C2R_148", "TWO"): 5,
        ("NEW_P4GT1_310", "TWO"): 15,
    }
    sample: list[dict[str, str]] = []
    for (source, state), count in quotas.items():
        sample.extend(_diverse_sample(pools[(source, state)], count, source, state))
    if len(sample) != 100 or len({row["frame_id"] for row in sample}) != 100:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    sample_rows = [
        {**row, "pass1_stratum": _state(row["visible_left"], row["visible_right"])}
        for row in sample
    ]
    atomic_csv(SAMPLE, sample_rows, list(sample_rows[0]))

    randomized = sample[:]
    random.Random(ORDER_SEED).shuffle(randomized)
    queue_rows: list[dict[str, str]] = []
    for order, source in enumerate(randomized):
        queue_rows.append(
            {
                "review_row_id": review_row_id(
                    source["sequence_id"], source["frame_index"], source["source_sha256"]
                ),
                "source_annotation_row_id": source["frame_id"],
                "sequence_id": source["sequence_id"],
                "frame_index": source["frame_index"],
                "image_sha256": source["source_sha256"],
                "image_path": source["source_image_path"],
                "queue_order": str(order),
            }
        )
    atomic_csv(QUEUE, queue_rows, list(queue_rows[0]))
    atomic_csv(REVIEW, [{**row, **UNREVIEWED} for row in queue_rows], ALL_FIELDS)
    if not PASS1_REPORT_SNAPSHOT.exists():
        atomic_text(PASS1_REPORT_SNAPSHOT, REPORT.read_text(encoding="utf-8"))
    atomic_json(
        BLINDING,
        {
            "status": "FROZEN_BEFORE_REPEATABILITY_REVIEW",
            "ui_version": UI_VERSION,
            "sample_seed": SAMPLE_SEED,
            "review_order_seed": ORDER_SEED,
            "sample_counts": {
                "ZERO": 40,
                "ONE": 40,
                "TWO": 20,
                "REUSED_P4C2R_148": 34,
                "NEW_P4GT1_310": 66,
            },
            "reviewer_hidden": [
                "Pass-1 labels",
                "V1 labels",
                "previous disagreement status",
                "model information",
                "sequence/gloss",
                "Pass-1 source",
                "stratum",
            ],
            "queue_sha256": sha256(QUEUE),
            "review_sha256_at_freeze": sha256(REVIEW),
            "standard_sha256": sha256(STANDARD),
        },
    )
    composition = Counter(_state(row["visible_left"], row["visible_right"]) for row in full)
    result = {
        "status": "P4GT1_REPEATABILITY_REVIEW_READY",
        "complete_pass1_count": 458,
        "reused_pass1_count": 148,
        "new_pass1_count": 310,
        "pass1_composition": dict(sorted(composition.items())),
        "repeatability_review_count": 100,
        "repeatability_review_sides": 200,
        "repeatability_sample_counts": {
            "ZERO": 40,
            "ONE": 40,
            "TWO": 20,
            "REUSED": 34,
            "NEW": 66,
        },
        "pass1_full_sha256": sha256(PASS1_FULL),
        "repeatability_queue_sha256": sha256(QUEUE),
        "repeatability_review_sha256_at_freeze": sha256(REVIEW),
    }
    atomic_json(PREPARE_RESULT, result)
    atomic_json(
        PROVENANCE,
        {
            **result,
            "v1_dataset_sha256": EXPECTED_DATASET,
            "v1_annotation_sha256": EXPECTED_ANNOTATION,
            "c2r_review_sha256": EXPECTED_C2R_REVIEW,
            "new_pass1_review_sha256": sha256(PASS1_REVIEW),
            "annotation_standard_sha256": sha256(STANDARD),
        },
    )
    atomic_text(
        REPORT,
        """# P4-GT1 Eligibility Ground-Truth Rebuild Result

## Status

**`P4GT1_REPEATABILITY_REVIEW_READY` — second blinded human pass required.**

The 148 reusable P4-C2R labels and 310 newly completed Pass-1 labels now form provisional
`p4gt1_pass1_full.csv`, covering all 458 governed frames exactly once. Source identities, hashes,
completion status, and zero-edit history passed validation.

A deterministic signer/sequence-aware 100-frame repeatability sample is frozen: 40 Pass-1
zero-hand, 40 one-hand, and 20 two-hand frames, including 34 frames from the reused set and 66 from
the newly reviewed set. The reviewer is blinded to Pass-1, V1, source, strata, disagreements, and
all model information.

V2 has not been created. Repeatability scoring, adjudication, proposal/crop/historical rescoring,
model work, Android, recognition, P4-C2B, P4-D, and P4-B remain unstarted.
""",
    )
    tracked = [
        PASS1_FULL,
        SAMPLE,
        QUEUE,
        REVIEW,
        BLINDING,
        PROVENANCE,
        PREPARE_RESULT,
        REPORT,
        PASS1_REPORT_SNAPSHOT,
    ]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_BEFORE_REPEATABILITY_REVIEW",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    return result


class RepeatabilityApp(Pass1ReviewApp):
    def __init__(self, root: tk.Tk, store: RepeatabilityStore) -> None:
        super().__init__(root, store)
        root.title("P4-GT1 Blinded Repeatability Review")

    def render(self) -> None:
        if self.current is None:
            self.progress.configure(text="ANNOTATION_COMPLETE")
            self.image_label.configure(image="", text="All 100 repeatability frames are complete.")
            return
        complete = sum(row["reviewer_status"] == "COMPLETE" for row in self.store.rows)
        self.progress.configure(
            text=(
                f"Frame {complete + 1}/100 | completed {complete} | "
                f"ID {self.current['review_row_id']}"
            )
        )
        image = Image.open(self.current["image_path"]).convert("RGB")
        fit = min(760 / image.width, 740 / image.height)
        scale = fit * self.zoom
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
        self.photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self.photo, text="")
        self.left.set(self.current.get("visible_left") or "UNCERTAIN")
        self.right.set(self.current.get("visible_right") or "UNCERTAIN")
        self.state.set(self.current.get("frame_state") or "UNCERTAIN")
        self.note.set(self.current.get("reviewer_note") or "")


def check() -> dict[str, Any]:
    store = RepeatabilityStore()
    counts = Counter(row["reviewer_status"] for row in store.rows)
    result = {
        "rows": len(store.rows),
        "completed": counts["COMPLETE"],
        "remaining": counts["UNREVIEWED"],
        "label_patterns": dict(
            sorted(
                Counter(
                    f"L={row['visible_left']}|R={row['visible_right']}|STATE={row['frame_state']}"
                    for row in store.rows
                    if row["reviewer_status"] == "COMPLETE"
                ).items()
            )
        ),
        "errors": [],
        "passed": counts["COMPLETE"] == 100,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "review", "check"))
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2, sort_keys=True))
    elif args.command == "check":
        check()
    else:
        root = tk.Tk()
        RepeatabilityApp(root, RepeatabilityStore())
        root.mainloop()


if __name__ == "__main__":
    main()
