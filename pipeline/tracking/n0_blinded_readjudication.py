"""Blinded semantic re-adjudication of the governed N0 RGB fixture."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "model/config/recognition_upgrade/n0_blinded_readjudication.json"
PROTOCOL = ROOT / "context/recognition_upgrade/N0_BLINDED_READJUDICATION_PROTOCOL.md"
SEMANTIC_CLASSES = (
    "ZERO_HAND",
    "VISIBLE_IDLE_HAND",
    "VISIBLE_SIGNING_HAND",
    "TRANSITION",
    "UNCERTAIN",
)
QUEUE_FIELDS = (
    "review_id",
    "center_image_path",
    "context_panel_path",
    "review_status",
    "semantic_class",
    "notes",
)
CANDIDATE_FIELDS = (
    "review_id",
    "candidate_id",
    "source_sample_id",
    "canonical_review_id",
    "is_qc_repeat",
    "clip_id",
    "participant_id",
    "device_id",
    "environment_id",
    "camera_facing",
    "timestamp_ms",
    "frame_index",
    "source_center_image_path",
    "source_context_panel_path",
    "source_image_sha256",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if tuple(config["semantic_classes"]) != SEMANTIC_CLASSES:
        raise ValueError("semantic classes drifted from the frozen protocol")
    return config


def _git(command: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *command], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        return f"UNAVAILABLE: {error}"


def _eligible_unique_rows(source: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index_rows = _read_csv(source / "internal_index.csv")
    captures = {row["clip_id"]: row for row in _read_csv(source / "capture_manifest.csv")}
    hashes: dict[str, list[str]] = defaultdict(list)
    enriched: list[dict[str, Any]] = []
    for row in index_rows:
        center = Path(row["center_image_path"])
        context = Path(row["context_panel_path"])
        if not center.is_file() or not context.is_file():
            raise FileNotFoundError(f"missing source review asset for {row['sample_id']}")
        image_hash = _sha256(center)
        hashes[image_hash].append(row["sample_id"])
        capture = captures[row["clip_id"]]
        enriched.append(
            {
                **row,
                "device_id": capture["device_id"],
                "environment_id": capture["environment_id"],
                "camera_facing": capture["camera_facing"],
                "source_image_sha256": image_hash,
            }
        )
    canonical = {digest: min(ids) for digest, ids in hashes.items()}
    unique = [row for row in enriched if row["sample_id"] == canonical[row["source_image_sha256"]]]
    duplicate_groups = [
        {"sha256": digest, "sample_ids": sorted(ids)}
        for digest, ids in sorted(hashes.items())
        if len(ids) > 1
    ]
    return unique, duplicate_groups


def _select_candidates(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    rng = random.Random(int(config["selection_seed"]))
    spacing = int(config["minimum_timestamp_spacing_ms"])
    cap = int(config["candidate_max_per_clip"])
    target = int(config["candidate_count"])
    by_clip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_clip[row["clip_id"]].append(row)
    available: dict[str, list[dict[str, Any]]] = {}
    tie_order = list(by_clip)
    rng.shuffle(tie_order)
    tie_rank = {clip: rank for rank, clip in enumerate(tie_order)}
    for clip, clip_rows in by_clip.items():
        shuffled = sorted(clip_rows, key=lambda row: int(row["timestamp_ms"]))
        rng.shuffle(shuffled)
        kept: list[dict[str, Any]] = []
        for row in shuffled:
            timestamp = int(row["timestamp_ms"])
            if all(abs(timestamp - int(prior["timestamp_ms"])) >= spacing for prior in kept):
                kept.append(row)
            if len(kept) == cap:
                break
        available[clip] = kept

    selected: list[dict[str, Any]] = []
    counts: dict[str, Counter[str]] = {
        "participant_id": Counter(),
        "device_id": Counter(),
        "environment_id": Counter(),
        "clip_id": Counter(),
    }
    while len(selected) < target:
        clips = [clip for clip, values in available.items() if values]
        if not clips:
            raise ValueError(
                f"only {len(selected)} candidates satisfy frozen constraints; need {target}"
            )
        clip = min(
            clips,
            key=lambda key: (
                counts["participant_id"][available[key][-1]["participant_id"]],
                counts["device_id"][available[key][-1]["device_id"]],
                counts["environment_id"][available[key][-1]["environment_id"]],
                counts["clip_id"][key],
                tie_rank[key],
            ),
        )
        row = available[clip].pop()
        selected.append(row)
        for field in counts:
            counts[field][row[field]] += 1
    return selected


def _make_review_order(
    selected: list[dict[str, Any]], config: dict[str, Any]
) -> list[tuple[dict[str, Any], bool]]:
    rng = random.Random(int(config["qc_seed"]))
    primaries = list(selected)
    rng.shuffle(primaries)
    repeats = rng.sample(primaries, int(config["qc_repeat_count"]))
    combined = [(row, False) for row in primaries] + [(row, True) for row in repeats]
    for _ in range(10000):
        rng.shuffle(combined)
        positions: dict[str, list[int]] = defaultdict(list)
        for index, (row, _) in enumerate(combined):
            positions[row["sample_id"]].append(index)
        if all(
            len(values) == 1 or abs(values[0] - values[1]) >= 25 for values in positions.values()
        ):
            return combined
    raise ValueError("could not distribute hidden QC repeats with the frozen spacing")


def prepare(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    source = _resolve(config["source_run"])
    output = _resolve(config["output_run"])
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing package: {output}")
    if not PROTOCOL.is_file():
        raise FileNotFoundError(PROTOCOL)

    capture_rows = _read_csv(source / "capture_manifest.csv")
    video_hashes = []
    for row in capture_rows:
        video = Path(row["video_path"])
        if not video.is_file():
            raise FileNotFoundError(video)
        actual = _sha256(video)
        if actual.lower() != row["sha256"].lower():
            raise ValueError(f"source video hash mismatch: {video}")
        video_hashes.append({"clip_id": row["clip_id"], "path": str(video), "sha256": actual})

    unique, duplicate_groups = _eligible_unique_rows(source)
    selected = _select_candidates(unique, config)
    review_order = _make_review_order(selected, config)

    output.mkdir(parents=True)
    center_dir = output / "center_images"
    context_dir = output / "context_panels"
    center_dir.mkdir()
    context_dir.mkdir()
    canonical_ids: dict[str, str] = {}
    queue_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    candidate_number = {row["sample_id"]: i for i, row in enumerate(selected, start=1)}
    for number, (row, is_repeat) in enumerate(review_order, start=1):
        review_id = f"review_{number:04d}"
        if not is_repeat:
            canonical_ids[row["sample_id"]] = review_id
        center_target = center_dir / f"{review_id}.png"
        context_target = context_dir / f"{review_id}.jpg"
        shutil.copy2(Path(row["center_image_path"]), center_target)
        shutil.copy2(Path(row["context_panel_path"]), context_target)
        queue_rows.append(
            {
                "review_id": review_id,
                "center_image_path": str(center_target.resolve()),
                "context_panel_path": str(context_target.resolve()),
                "review_status": "unreviewed",
                "semantic_class": "",
                "notes": "",
            }
        )
        candidate_rows.append(
            {
                "review_id": review_id,
                "candidate_id": f"candidate_{candidate_number[row['sample_id']]:04d}",
                "source_sample_id": row["sample_id"],
                "canonical_review_id": "" if is_repeat else review_id,
                "is_qc_repeat": str(is_repeat).lower(),
                "clip_id": row["clip_id"],
                "participant_id": row["participant_id"],
                "device_id": row["device_id"],
                "environment_id": row["environment_id"],
                "camera_facing": row["camera_facing"],
                "timestamp_ms": row["timestamp_ms"],
                "frame_index": row["frame_index"],
                "source_center_image_path": row["center_image_path"],
                "source_context_panel_path": row["context_panel_path"],
                "source_image_sha256": row["source_image_sha256"],
            }
        )
    for row in candidate_rows:
        if row["is_qc_repeat"] == "true":
            row["canonical_review_id"] = canonical_ids[row["source_sample_id"]]

    _write_csv(output / "review_queue.csv", QUEUE_FIELDS, queue_rows)
    _write_csv(output / "candidate_manifest.csv", CANDIDATE_FIELDS, candidate_rows)
    hash_manifest = {
        "source_videos": video_hashes,
        "source_center_images": [
            {
                "sample_id": row["sample_id"],
                "path": row["center_image_path"],
                "sha256": row["source_image_sha256"],
            }
            for row in sorted(unique, key=lambda value: value["sample_id"])
        ],
        "exact_duplicate_groups": duplicate_groups,
    }
    (output / "source_hash_manifest.json").write_text(
        json.dumps(hash_manifest, indent=2), encoding="utf-8"
    )
    provenance = {
        "protocol_version": config["protocol_version"],
        "prepared_before_human_review": True,
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "working_tree_status": _git(["status", "--short"]),
        "python": sys.version,
        "platform": platform.platform(),
        "opencv": cv2.__version__,
        "source_run": str(source.resolve()),
        "trusted_gold_run": str(_resolve(config["trusted_gold_run"]).resolve()),
        "output_run": str(output.resolve()),
        "source_rows": len(_read_csv(source / "internal_index.csv")),
        "exact_unique_source_images": len(unique),
        "candidate_count": len(selected),
        "review_rows": len(review_order),
        "qc_repeat_count": sum(is_repeat for _, is_repeat in review_order),
        "selection_seed": config["selection_seed"],
        "qc_seed": config["qc_seed"],
        "config_sha256": _sha256(config_path),
        "protocol_sha256": _sha256(PROTOCOL),
        "runner_sha256": _sha256(Path(__file__)),
        "source_index_sha256": _sha256(source / "internal_index.csv"),
        "source_capture_manifest_sha256": _sha256(source / "capture_manifest.csv"),
        "source_old_labels_not_read_for_selection": True,
        "model_output_not_read_for_selection": True,
        "semantic_classes": list(SEMANTIC_CLASSES),
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return provenance


def _load_package(output: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return _read_csv(output / "review_queue.csv"), _read_csv(output / "candidate_manifest.csv")


def check(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    output = _resolve(config["output_run"])
    queue, manifest = _load_package(output)
    errors: list[str] = []
    if len(queue) != int(config["candidate_count"]) + int(config["qc_repeat_count"]):
        errors.append("review queue count drift")
    if len(manifest) != len(queue):
        errors.append("candidate/review row count mismatch")
    seen: set[str] = set()
    counts = Counter()
    for row in queue:
        review_id = row["review_id"]
        if review_id in seen:
            errors.append(f"duplicate review_id: {review_id}")
        seen.add(review_id)
        if (
            not Path(row["center_image_path"]).is_file()
            or not Path(row["context_panel_path"]).is_file()
        ):
            errors.append(f"missing review asset: {review_id}")
        if row["review_status"] == "accepted":
            if row["semantic_class"] not in SEMANTIC_CLASSES:
                errors.append(f"invalid semantic class: {review_id}")
            else:
                counts[row["semantic_class"]] += 1
        elif row["review_status"] == "unreviewed":
            if row["semantic_class"]:
                errors.append(f"unreviewed row has a semantic class: {review_id}")
        else:
            errors.append(f"invalid review status: {review_id}")
    completed = sum(row["review_status"] == "accepted" for row in queue)
    result = {
        "rows": len(queue),
        "unique_candidates": int(config["candidate_count"]),
        "qc_repeats": int(config["qc_repeat_count"]),
        "completed": completed,
        "remaining": len(queue) - completed,
        "semantic_counts_including_hidden_repeats": dict(sorted(counts.items())),
        "errors": errors,
        "passed": not errors and completed == len(queue),
    }
    (output / "review_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _dhash(path: Path) -> int:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"cannot read image: {path}")
    resized = cv2.resize(image, (9, 8), interpolation=cv2.INTER_AREA)
    return sum(
        int(value) << index for index, value in enumerate((resized[:, 1:] > resized[:, :-1]).flat)
    )


def _balanced_pick(rows: list[dict[str, Any]], target: int, cap: int) -> list[dict[str, Any]]:
    remaining = list(rows)
    selected: list[dict[str, Any]] = []
    counts = {
        field: Counter() for field in ("participant_id", "device_id", "environment_id", "clip_id")
    }
    while remaining and len(selected) < target:
        row = min(
            remaining,
            key=lambda value: (
                counts["participant_id"][value["participant_id"]],
                counts["device_id"][value["device_id"]],
                counts["environment_id"][value["environment_id"]],
                counts["clip_id"][value["clip_id"]],
                value.get("source_sample_id", value.get("sample_id", "")),
            ),
        )
        remaining.remove(row)
        if counts["clip_id"][row["clip_id"]] >= cap:
            continue
        selected.append(row)
        for field in counts:
            counts[field][row[field]] += 1
    return selected


def finalize(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    output = _resolve(config["output_run"])
    check_result = check(config_path)
    if not check_result["passed"]:
        raise ValueError("review is incomplete or invalid; run Check for details")
    queue, manifest = _load_package(output)
    labels = {row["review_id"]: row["semantic_class"] for row in queue}
    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in manifest:
        by_source[row["source_sample_id"]].append(row)
    agreements = 0
    critical: list[str] = []
    disagreements: list[dict[str, Any]] = []
    for source_id, rows in by_source.items():
        if len(rows) == 1:
            continue
        values = [labels[row["review_id"]] for row in rows]
        if len(set(values)) == 1:
            agreements += 1
        else:
            entry = {
                "source_sample_id": source_id,
                "review_ids": [row["review_id"] for row in rows],
                "labels": values,
            }
            disagreements.append(entry)
            if "ZERO_HAND" in values:
                critical.append(source_id)
    repeat_count = int(config["qc_repeat_count"])
    agreement = agreements / repeat_count
    qc = {
        "repeat_count": repeat_count,
        "exact_agreements": agreements,
        "exact_agreement_fraction": agreement,
        "minimum_required": config["qc_minimum_exact_agreement"],
        "critical_zero_vs_nonzero_disagreements": critical,
        "all_disagreements": disagreements,
        "passed": agreement >= float(config["qc_minimum_exact_agreement"]) and not critical,
    }
    (output / "qc_result.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
    if not qc["passed"]:
        raise ValueError("hidden repeat QC failed; adjudication is required")

    canonical_rows = [row for row in manifest if row["is_qc_repeat"] == "false"]
    zeros = [dict(row) for row in canonical_rows if labels[row["review_id"]] == "ZERO_HAND"]
    zeros.sort(key=lambda row: row["source_sample_id"])
    deduped: list[dict[str, Any]] = []
    threshold = int(config["near_duplicate_dhash_hamming_max"])
    fingerprints: list[int] = []
    queue_by_id = {row["review_id"]: row for row in queue}
    for row in zeros:
        fingerprint = _dhash(Path(queue_by_id[row["review_id"]]["center_image_path"]))
        if any((fingerprint ^ prior).bit_count() <= threshold for prior in fingerprints):
            continue
        row["dhash64"] = f"{fingerprint:016x}"
        deduped.append(row)
        fingerprints.append(fingerprint)

    target = int(config["new_zero_hand_target"])
    selected = _balanced_pick(deduped, target, int(config["benchmark_first_pass_max_per_clip"]))
    used_fallback = False
    if len(selected) < target:
        selected = _balanced_pick(deduped, target, int(config["benchmark_fallback_max_per_clip"]))
        used_fallback = True
    diversity = {
        field: sorted({row[field] for row in selected})
        for field in ("clip_id", "participant_id", "device_id", "environment_id")
    }
    final_errors = []
    if len(selected) < target:
        final_errors.append(f"only {len(selected)} new zeros survived; need {target}")
    if len(diversity["clip_id"]) < int(config["minimum_unique_clips"]):
        final_errors.append("unique-clip diversity gate failed")
    expected = {
        "participant_id": {"P01", "P02", "P03", "P04", "P05", "P06"},
        "device_id": {"phoneA", "phoneB", "phoneC", "phoneE", "phoneF"},
        "environment_id": {"DirtyRoom", "OUTDOOR", "indoor", "kitchen", "room"},
    }
    for field, values in expected.items():
        if set(diversity[field]) != values:
            final_errors.append(f"{field} diversity gate failed")
    result = {
        "human_zero_candidates": len(zeros),
        "near_duplicate_clean_zero_candidates": len(deduped),
        "new_zero_selected": len(selected),
        "new_zero_required": target,
        "used_fourth_frame_per_clip_fallback": used_fallback,
        "diversity": {field: len(values) for field, values in diversity.items()},
        "errors": final_errors,
        "passed": not final_errors,
    }
    if final_errors:
        (output / "finalize_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        raise ValueError("final benchmark gates failed; see finalize_result.json")

    new_fields = tuple(CANDIDATE_FIELDS) + ("dhash64", "semantic_class")
    new_rows = [{**row, "semantic_class": "ZERO_HAND"} for row in selected]
    _write_csv(output / "new_zero_hand_167.csv", new_fields, new_rows)

    gold = _resolve(config["trusted_gold_run"])
    gold_reviews = {row["sample_id"]: row for row in _read_csv(gold / "gold_review.csv")}
    gold_index = {row["sample_id"]: row for row in _read_csv(gold / "internal_index.csv")}
    trusted = [
        {
            "benchmark_id": f"trusted_{number:03d}",
            "source_group": "corrected_all_hand_gold",
            "source_sample_id": sample_id,
            "image_path": gold_index[sample_id]["center_image_path"],
            "image_sha256": _sha256(Path(gold_index[sample_id]["center_image_path"])),
            "participant_id": gold_index[sample_id]["participant_id"],
            "clip_id": gold_index[sample_id]["video_file"],
            "semantic_class": "ZERO_HAND",
        }
        for number, (sample_id, review) in enumerate(sorted(gold_reviews.items()), start=1)
        if review["review_status"] == "accepted" and review["visible_hand_count"] == "0"
    ]
    if len(trusted) != 33:
        raise ValueError(f"trusted corrected-gold zero count drifted: {len(trusted)}")
    repaired = [
        {
            "benchmark_id": f"repaired_{number:03d}",
            "source_group": "n0_blinded_readjudication_01",
            "source_sample_id": row["source_sample_id"],
            "image_path": row["source_center_image_path"],
            "image_sha256": row["source_image_sha256"],
            "participant_id": row["participant_id"],
            "clip_id": row["clip_id"],
            "semantic_class": "ZERO_HAND",
        }
        for number, row in enumerate(selected, start=1)
    ]
    frozen_fields = (
        "benchmark_id",
        "source_group",
        "source_sample_id",
        "image_path",
        "image_sha256",
        "participant_id",
        "clip_id",
        "semantic_class",
    )
    frozen = trusted + repaired
    if len(frozen) != int(config["frozen_benchmark_target"]):
        raise ValueError("frozen benchmark count drift")
    _write_csv(output / "frozen_zero_hand_200.csv", frozen_fields, frozen)
    result["frozen_benchmark_rows"] = len(frozen)
    result["qc"] = qc
    (output / "finalize_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


class ReviewApp:
    def __init__(self, queue_path: Path) -> None:
        import tkinter as tk

        self.tk = tk
        self.queue_path = queue_path
        self.rows = _read_csv(queue_path)
        self.index = next(
            (i for i, row in enumerate(self.rows) if row["review_status"] != "accepted"), 0
        )
        self.root = tk.Tk()
        self.root.title("AppHear Zero-Hand Semantic Review")
        self.root.geometry("1500x900")
        self.root.configure(bg="#f4f5f7")
        self.status = tk.StringVar()
        self.choice = tk.StringVar()
        self.notes = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.status, font=("Segoe UI", 15, "bold"), bg="#f4f5f7"
        ).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Judge the CENTER frame. Any visible fingertip, lap hand, blurred hand, "
                "crossed-arm hand, or edge hand means NOT ZERO_HAND."
            ),
            font=("Segoe UI", 11, "bold"),
            fg="#9a3412",
            bg="#f4f5f7",
            wraplength=1400,
        ).pack(pady=(0, 8))
        images = tk.Frame(self.root, bg="#f4f5f7")
        images.pack(fill="both", expand=True)
        self.center_label = tk.Label(images, bg="#111111")
        self.center_label.pack(side="left", fill="both", expand=True, padx=(12, 6))
        self.context_label = tk.Label(images, bg="#111111")
        self.context_label.pack(side="right", fill="both", expand=True, padx=(6, 12))
        choices = tk.Frame(self.root, bg="#f4f5f7")
        choices.pack(pady=8)
        labels = {
            "ZERO_HAND": "1 — No hand pixels",
            "VISIBLE_IDLE_HAND": "2 — Visible idle hand",
            "VISIBLE_SIGNING_HAND": "3 — Visible signing hand",
            "TRANSITION": "4 — Entering/leaving",
            "UNCERTAIN": "5 — Uncertain",
        }
        for value in SEMANTIC_CLASSES:
            tk.Radiobutton(
                choices,
                text=labels[value],
                variable=self.choice,
                value=value,
                font=("Segoe UI", 10),
                bg="#f4f5f7",
                indicatoron=False,
                selectcolor="#bfdbfe",
                padx=10,
                pady=7,
            ).pack(side="left", padx=3)
        note_frame = tk.Frame(self.root, bg="#f4f5f7")
        note_frame.pack(fill="x", padx=12)
        tk.Label(note_frame, text="Optional note:", bg="#f4f5f7").pack(side="left")
        tk.Entry(note_frame, textvariable=self.notes).pack(
            side="left", fill="x", expand=True, padx=8
        )
        buttons = tk.Frame(self.root, bg="#f4f5f7")
        buttons.pack(pady=(8, 14))
        tk.Button(buttons, text="Previous", command=lambda: self.move(-1), width=14).pack(
            side="left", padx=6
        )
        tk.Button(
            buttons,
            text="Accept + Next (Ctrl+S)",
            command=self.accept,
            width=24,
            bg="#2563eb",
            fg="white",
        ).pack(side="left", padx=6)
        tk.Button(buttons, text="Next", command=lambda: self.move(1), width=14).pack(
            side="left", padx=6
        )
        for number, value in enumerate(SEMANTIC_CLASSES, start=1):
            self.root.bind(str(number), lambda _event, item=value: self.choice.set(item))
        self.root.bind("<Control-s>", lambda _event: self.accept())
        self.root.bind("<Left>", lambda _event: self.move(-1))
        self.root.bind("<Right>", lambda _event: self.move(1))
        self.refresh()

    def _photo(self, path: Path, max_width: int, max_height: int) -> Any:
        image = cv2.imread(str(path))
        if image is None:
            raise OSError(path)
        scale = min(max_width / image.shape[1], max_height / image.shape[0], 1.5)
        resized = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
        ok, encoded = cv2.imencode(".png", resized)
        if not ok:
            raise OSError(path)
        import base64

        return self.tk.PhotoImage(data=base64.b64encode(encoded.tobytes()).decode("ascii"))

    def refresh(self) -> None:
        row = self.rows[self.index]
        completed = sum(item["review_status"] == "accepted" for item in self.rows)
        position = f"Frame {self.index + 1}/{len(self.rows)}"
        self.status.set(f"{position} | accepted {completed} | status={row['review_status']}")
        self.choice.set(row["semantic_class"])
        self.notes.set(row["notes"])
        self.center_photo = self._photo(Path(row["center_image_path"]), 680, 570)
        self.context_photo = self._photo(Path(row["context_panel_path"]), 720, 570)
        self.center_label.configure(image=self.center_photo)
        self.context_label.configure(image=self.context_photo)

    def accept(self) -> None:
        if self.choice.get() not in SEMANTIC_CLASSES:
            from tkinter import messagebox

            messagebox.showerror("Choose a class", "Select one of the five semantic classes first.")
            return
        row = self.rows[self.index]
        row["semantic_class"] = self.choice.get()
        row["notes"] = self.notes.get().strip()
        row["review_status"] = "accepted"
        _write_csv(self.queue_path, QUEUE_FIELDS, self.rows)
        self.index = min(self.index + 1, len(self.rows) - 1)
        self.refresh()

    def move(self, delta: int) -> None:
        self.index = min(max(self.index + delta, 0), len(self.rows) - 1)
        self.refresh()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "review", "check", "finalize", "status"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    output = _resolve(config["output_run"])
    if args.command == "prepare":
        result = prepare(args.config)
    elif args.command == "review":
        ReviewApp(output / "review_queue.csv").run()
        return 0
    elif args.command in {"check", "status"}:
        result = check(args.config)
    else:
        result = finalize(args.config)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
