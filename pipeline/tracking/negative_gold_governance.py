"""Finalize NEGATIVE_GOLD_V1 seed evidence and prepare a blinded diversity top-up."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2

from pipeline.tracking.n0_blinded_readjudication import (
    QUEUE_FIELDS,
    ReviewApp,
    _dhash,
    _read_csv,
    _resolve,
    _sha256,
    _write_csv,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "model/config/recognition_upgrade/negative_gold_topup.json"
N0_CONFIG = ROOT / "model/config/recognition_upgrade/n0_blinded_readjudication.json"
N0_PROTOCOL = ROOT / "context/recognition_upgrade/N0_BLINDED_READJUDICATION_PROTOCOL.md"
RUNNER_N0 = ROOT / "pipeline/tracking/n0_blinded_readjudication.py"
PAIRWISE = (
    ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p0_rtmdet_detector_02/paired_mediapipe_vs_rtmdet.csv"
)
SEMANTIC_CLASSES = (
    "ZERO_HAND",
    "VISIBLE_IDLE_HAND",
    "VISIBLE_SIGNING_HAND",
    "TRANSITION",
    "UNCERTAIN",
)
TOPUP_FIELDS = (
    "review_id",
    "candidate_id",
    "source_group",
    "source_id",
    "clip_id",
    "participant_id",
    "device_id",
    "environment_id",
    "session_id",
    "source_split",
    "camera_view",
    "source_image_path",
    "source_context_path",
    "source_image_sha256",
    "dhash64",
    "canonical_review_id",
    "is_qc_repeat",
)


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if tuple(config["semantic_classes"]) != SEMANTIC_CLASSES:
        raise ValueError("semantic classes drifted")
    return config


def _n0_state(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    run = _resolve(config["n0_run"])
    queue = {row["review_id"]: row for row in _read_csv(run / "review_queue.csv")}
    manifest = _read_csv(run / "candidate_manifest.csv")
    canonical = [dict(row) for row in manifest if row["is_qc_repeat"] == "false"]
    for row in canonical:
        row["semantic_class"] = queue[row["review_id"]]["semantic_class"]
        row["review_notes"] = queue[row["review_id"]]["notes"]
        row["review_image_path"] = queue[row["review_id"]]["center_image_path"]
    zeros = sorted(
        (dict(row) for row in canonical if row["semantic_class"] == "ZERO_HAND"),
        key=lambda row: row["source_sample_id"],
    )
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    threshold = int(config["dhash_hamming_max"])
    for row in zeros:
        fingerprint = _dhash(Path(row["review_image_path"]))
        matches = [((fingerprint ^ prior["_dhash_int"]).bit_count(), prior) for prior in kept]
        nearest = min(matches, key=lambda item: item[0]) if matches else None
        row["dhash64"] = f"{fingerprint:016x}"
        row["_dhash_int"] = fingerprint
        if nearest and nearest[0] <= threshold:
            row["excluded_nearest_source_id"] = nearest[1]["source_sample_id"]
            row["excluded_dhash_distance"] = nearest[0]
            excluded.append(row)
        else:
            kept.append(row)
    return canonical, kept, excluded


def _trusted_zeros(config: dict[str, Any]) -> list[dict[str, Any]]:
    gold = _resolve(config["trusted_gold_run"])
    reviews = {row["sample_id"]: row for row in _read_csv(gold / "gold_review.csv")}
    index = _read_csv(gold / "internal_index.csv")
    return [
        row
        for row in index
        if reviews[row["sample_id"]]["review_status"] == "accepted"
        and reviews[row["sample_id"]]["visible_hand_count"] == "0"
    ]


def _write_panel(a: Path, b: Path, label: str, output: Path) -> None:
    images = []
    for path in (a, b):
        image = cv2.imread(str(path))
        if image is None:
            raise OSError(path)
        scale = min(540 / image.shape[0], 440 / image.shape[1])
        image = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
        canvas = cv2.copyMakeBorder(
            image,
            0,
            540 - image.shape[0],
            0,
            440 - image.shape[1],
            cv2.BORDER_CONSTANT,
            value=(24, 24, 24),
        )
        images.append(canvas)
    panel = cv2.hconcat(images)
    cv2.putText(panel, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    if not cv2.imwrite(str(output), panel):
        raise OSError(output)


def finalize_n0(config: dict[str, Any], output: Path) -> dict[str, Any]:
    canonical, kept, excluded = _n0_state(config)
    trusted = _trusted_zeros(config)
    if len(canonical) != 250 or len(kept) != 43 or len(excluded) != 195 or len(trusted) != 33:
        raise ValueError("frozen N0 counts drifted")
    output.mkdir(parents=True, exist_ok=False)
    pair_dir = output / "dhash_boundary_pairs"
    pair_dir.mkdir()

    canonical_fields = tuple(key for key in canonical[0] if not key.startswith("_"))
    kept_fields = tuple(key for key in kept[0] if not key.startswith("_"))
    excluded_fields = tuple(key for key in excluded[0] if not key.startswith("_"))
    _write_csv(output / "n0_canonical_human_labels_250.csv", canonical_fields, canonical)
    _write_csv(output / "n0_diversity_clean_zero_hand_43.csv", kept_fields, kept)
    _write_csv(output / "n0_redundant_zero_hand_195.csv", excluded_fields, excluded)

    zeros = sorted(kept + excluded, key=lambda row: row["source_sample_id"])
    buckets = {"d0": {0}, "d1_2": {1, 2}, "d3_4": {3, 4}, "d5_6": {5, 6}}
    pairs: list[dict[str, Any]] = []
    used: set[str] = set()
    for bucket, distances in buckets.items():
        candidates = []
        for index, row in enumerate(zeros):
            for other in zeros[:index]:
                distance = (row["_dhash_int"] ^ other["_dhash_int"]).bit_count()
                if distance in distances:
                    candidates.append(
                        (abs(distance - sum(distances) / len(distances)), row, other, distance)
                    )
        candidates.sort(
            key=lambda item: (item[0], item[1]["source_sample_id"], item[2]["source_sample_id"])
        )
        chosen = next(
            (
                item
                for item in candidates
                if item[1]["source_sample_id"] not in used
                and item[2]["source_sample_id"] not in used
            ),
            candidates[0],
        )
        _, row, other, distance = chosen
        used.update((row["source_sample_id"], other["source_sample_id"]))
        panel = pair_dir / f"{bucket}_{other['source_sample_id']}_{row['source_sample_id']}.jpg"
        _write_panel(
            Path(other["review_image_path"]),
            Path(row["review_image_path"]),
            f"{other['source_sample_id']} vs {row['source_sample_id']} | dHash={distance}",
            panel,
        )
        pairs.append(
            {
                "bucket": bucket,
                "source_a": other["source_sample_id"],
                "source_b": row["source_sample_id"],
                "clip_a": other["clip_id"],
                "clip_b": row["clip_id"],
                "participant_a": other["participant_id"],
                "participant_b": row["participant_id"],
                "environment_a": other["environment_id"],
                "environment_b": row["environment_id"],
                "dhash_distance": distance,
                "image_a": other["review_image_path"],
                "image_b": row["review_image_path"],
                "panel_path": str(panel.resolve()),
            }
        )
    _write_csv(output / "dhash_threshold_sanity_index.csv", tuple(pairs[0]), pairs)

    seed: list[dict[str, Any]] = []
    fingerprints: list[int] = []
    image_hashes: set[str] = set()
    positive_clips = {
        row["clip_id"]
        for row in _read_csv(_resolve(config["trusted_gold_run"]) / "internal_index.csv")
        if row["sample_id"] not in {trusted_row["sample_id"] for trusted_row in trusted}
    }
    for source_group, rows in (("CORRECTED_GOLD", trusted), ("N0_READJUDICATED", kept)):
        for row in rows:
            image_path = Path(row.get("center_image_path", row.get("review_image_path", "")))
            image_hash = _sha256(image_path)
            fingerprint = _dhash(image_path)
            if image_hash in image_hashes:
                raise ValueError("exact duplicate in proposed 76-frame seed")
            if any(
                (fingerprint ^ prior).bit_count() <= int(config["dhash_hamming_max"])
                for prior in fingerprints
            ):
                raise ValueError("near duplicate in proposed 76-frame seed")
            image_hashes.add(image_hash)
            fingerprints.append(fingerprint)
            clip_id = row.get("clip_id", "")
            if source_group == "N0_READJUDICATED" and clip_id in positive_clips:
                raise ValueError("N0 seed row overlaps a positive P0 clip")
            seed.append(
                {
                    "seed_id": f"negative_gold_{len(seed) + 1:03d}",
                    "source_group": source_group,
                    "source_id": row.get("sample_id", row.get("source_sample_id", "")),
                    "clip_id": clip_id,
                    "participant_id": row.get("participant_id", ""),
                    "device_id": row.get("device_id", "unknown"),
                    "environment_id": row.get("environment_id", "unknown"),
                    "source_split": row.get("split", "unassigned"),
                    "image_path": str(image_path),
                    "image_sha256": image_hash,
                    "dhash64": f"{fingerprint:016x}",
                    "semantic_class": "ZERO_HAND",
                }
            )
    if len(seed) != 76 or any(row["source_split"] == "test" for row in seed):
        raise ValueError("seed count or protected split gate failed")
    seed_fields = tuple(seed[0])
    _write_csv(output / "NEGATIVE_GOLD_V1_SEED_MANIFEST.csv", seed_fields, seed)
    seed_json = {
        "status": "NEGATIVE_GOLD_V1_SEED_NOT_COMPLETE",
        "rows": 76,
        "target": 200,
        "remaining": 124,
        "source_composition": dict(Counter(row["source_group"] for row in seed)),
        "manifest_sha256": _sha256(output / "NEGATIVE_GOLD_V1_SEED_MANIFEST.csv"),
        "no_exact_duplicates": True,
        "no_dhash_distance_le_4": True,
        "no_positive_p0_overlap": True,
        "no_protected_test_rows": True,
        "all_images_available": all(Path(row["image_path"]).is_file() for row in seed),
    }
    (output / "NEGATIVE_GOLD_V1_SEED_MANIFEST.json").write_text(
        json.dumps(seed_json, indent=2), encoding="utf-8"
    )

    pairwise_rows = _read_csv(PAIRWISE)
    definitions = {
        "RTMDET_COMPLEMENTARY_16": "MP_MISS_RTMDET_HIT",
        "RTMDET_REGRESSION_25": "MP_HIT_RTMDET_MISS",
        "PERCEPTION_HARD_CORE_46": "BOTH_MISS",
    }
    diagnostics = {}
    for name, value in definitions.items():
        keys = sorted(
            (row["sample_id"], int(row["gold_index"]))
            for row in pairwise_rows
            if row["pairwise_category"] == value
        )
        payload = "".join(f"{sample},{index}\n" for sample, index in keys).encode()
        diagnostics[name] = {
            "instances": len(keys),
            "unique_frames": len({sample for sample, _ in keys}),
            "selection_sha256": hashlib.sha256(payload).hexdigest(),
        }
    diagnostic_registry = {
        "source_path": str(PAIRWISE.resolve()),
        "source_sha256": _sha256(PAIRWISE),
        "sets": diagnostics,
        "not_negative_gold": True,
    }
    (output / "PERCEPTION_DIAGNOSTIC_SET_REGISTRY.json").write_text(
        json.dumps(diagnostic_registry, indent=2), encoding="utf-8"
    )
    return {
        "decision": "N0_BLINDED_READJUDICATION_COMPLETE_DIVERSITY_INSUFFICIENT",
        "canonical_rows": len(canonical),
        "canonical_zero_hand": len(kept) + len(excluded),
        "diversity_clean_zero_hand": len(kept),
        "redundant_zero_hand": len(excluded),
        "seed_rows": len(seed),
        "remaining": 124,
        "seed": seed,
        "canonical": canonical,
    }


def _candidate(
    source_group: str,
    source_id: str,
    clip_id: str,
    participant: str,
    image: Path,
    context: Path | None,
    **metadata: str,
) -> dict[str, Any]:
    if not image.is_file():
        raise FileNotFoundError(image)
    return {
        "source_group": source_group,
        "source_id": source_id,
        "clip_id": clip_id,
        "participant_id": participant or "unknown",
        "device_id": metadata.get("device_id", "unknown"),
        "environment_id": metadata.get("environment_id", "unknown"),
        "session_id": metadata.get("session_id", clip_id),
        "source_split": metadata.get("source_split", "unassigned"),
        "camera_view": metadata.get("camera_view", "unknown"),
        "source_image_path": str(image.resolve()),
        "source_context_path": str(context.resolve()) if context and context.is_file() else "",
        "source_image_sha256": _sha256(image),
        "_dhash_int": _dhash(image),
    }


def _one_per_group(rows: list[dict[str, str]], group: str, seed: int) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[group]].append(row)
    chosen = []
    for key, values in sorted(grouped.items()):
        chosen.append(
            min(
                values,
                key=lambda row: hashlib.sha256(
                    f"{seed}:{key}:{row.get('sample_id','')}".encode()
                ).hexdigest(),
            )
        )
    return chosen


def _existing_image_candidates(
    config: dict[str, Any], reviewed_n0_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []

    c0b_roots = [
        ROOT / "artifacts/recognition_upgrade/e2e_c0/c0b_annotation_smoke_03",
        ROOT / "artifacts/recognition_upgrade/e2e_c0/c0b_training_annotation_pilot_01",
        ROOT / "artifacts/recognition_upgrade/e2e_c0/c0b_condition_topup_01",
    ]
    c0b_rows = []
    for root in c0b_roots:
        for row in _read_csv(root / "internal_index.csv"):
            row["_root"] = str(root)
            c0b_rows.append(row)
    c0b_unique = _one_per_group(c0b_rows, "clip_id", int(config["selection_seed"]))
    for row in c0b_unique:
        candidates.append(
            _candidate(
                "C0B_UNIQUE_VIDEO",
                f"{Path(row['_root']).name}:{row['sample_id']}",
                row["clip_id"],
                row["participant_id"],
                Path(row["center_image_path"]),
                Path(row["context_panel_path"]),
                source_split=row["split"],
            )
        )
    inventory.append(
        {
            "source": "C0B",
            "raw_frames": len(c0b_rows),
            "unique_clips": len(c0b_unique),
            "participants": len({row["participant_id"] for row in c0b_unique}),
            "status": "BLINDED_REVIEW_CANDIDATE",
        }
    )

    p1_root = ROOT / "artifacts/recognition_upgrade/e2e_c0/p1_capture_03"
    p1_rows = _read_csv(p1_root / "internal_index.csv")
    captures = {row["clip_id"]: row for row in _read_csv(p1_root / "capture_manifest.csv")}
    p1_unique = _one_per_group(p1_rows, "clip_id", int(config["selection_seed"]))
    for row in p1_unique:
        capture = captures[row["clip_id"]]
        candidates.append(
            _candidate(
                "P1_CAPTURE",
                row["sample_id"],
                row["clip_id"],
                row["participant_id"],
                Path(row["center_image_path"]),
                Path(row["context_panel_path"]),
                device_id=capture["device_id"],
                environment_id=capture["environment_id"],
                camera_view=capture["camera_facing"],
            )
        )
    inventory.append(
        {
            "source": "P1",
            "raw_frames": len(p1_rows),
            "unique_clips": len(p1_unique),
            "participants": len({row["participant_id"] for row in p1_unique}),
            "status": "BLINDED_REVIEW_CANDIDATE",
        }
    )

    a2_root = ROOT / "artifacts/recognition_upgrade/a2_landmark_continuity/a2_0_identity_01"
    a2_rows = _read_csv(a2_root / "internal_index.csv")
    a2_unique = _one_per_group(a2_rows, "attempt_id", int(config["selection_seed"]))
    for row in a2_unique:
        candidates.append(
            _candidate(
                "A1_A2_PHONE_SEQUENCE",
                row["sample_id"],
                row["attempt_id"],
                "phone_signer_01",
                _resolve(row["image_path"]),
                _resolve(row["panel_path"]),
                device_id="Xiaomi_M2101K7AG",
                environment_id=row["cohort"],
                session_id=row["attempt_id"],
                camera_view="front",
            )
        )
    inventory.append(
        {
            "source": "A1/A2/RU-D",
            "raw_frames": len(a2_rows),
            "unique_clips": len(a2_unique),
            "participants": 1,
            "status": "BLINDED_REVIEW_CANDIDATE",
        }
    )

    n0_source = _resolve(config["n0_source_run"])
    n0_rows = [
        row
        for row in _read_csv(n0_source / "internal_index.csv")
        if row["sample_id"] not in reviewed_n0_ids
    ]
    captures = {row["clip_id"]: row for row in _read_csv(n0_source / "capture_manifest.csv")}
    n0_unique = _one_per_group(n0_rows, "clip_id", int(config["selection_seed"]))
    for row in n0_unique:
        capture = captures[row["clip_id"]]
        candidates.append(
            _candidate(
                "N0_UNREVIEWED_RESIDUAL",
                row["sample_id"],
                row["clip_id"],
                row["participant_id"],
                Path(row["center_image_path"]),
                Path(row["context_panel_path"]),
                device_id=capture["device_id"],
                environment_id=capture["environment_id"],
                camera_view=capture["camera_facing"],
            )
        )
    inventory.append(
        {
            "source": "N0 residual",
            "raw_frames": len(n0_rows),
            "unique_clips": len(n0_unique),
            "participants": len({row["participant_id"] for row in n0_unique}),
            "status": "BLINDED_REVIEW_CANDIDATE",
        }
    )
    return candidates, inventory


def _extract_asl_candidates(
    config: dict[str, Any], output: Path, excluded_clips: set[str], count: int = 260
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    asl = _resolve(config["asl_root"])
    rows = []
    for split in ("train", "val"):
        for row in _read_csv(asl / "splits" / f"{split}.csv"):
            if Path(row["Video file"]).stem in excluded_clips:
                continue
            row["_split"] = split
            rows.append(row)
    rng = random.Random(int(config["selection_seed"]))
    rng.shuffle(rows)
    rows.sort(key=lambda row: (row["_split"], row["Participant ID"]))
    by_signer: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_signer[f"{row['_split']}:{row['Participant ID']}"].append(row)
    signer_keys = sorted(by_signer)
    rng.shuffle(signer_keys)
    chosen = []
    while len(chosen) < count:
        progressed = False
        for key in signer_keys:
            if by_signer[key]:
                chosen.append(by_signer[key].pop())
                progressed = True
                if len(chosen) == count:
                    break
        if not progressed:
            break
    extracted = output / "asl_boundary_source"
    extracted.mkdir()
    candidates = []
    for number, row in enumerate(chosen, start=1):
        video = asl / "videos" / row["Video file"]
        capture = cv2.VideoCapture(str(video))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fraction = 0.05 if number % 2 else 0.95
        frame_index = min(max(round((frame_count - 1) * fraction), 0), frame_count - 1)
        frames = []
        for offset in (-2, -1, 0, 1, 2):
            capture.set(cv2.CAP_PROP_POS_FRAMES, min(max(frame_index + offset, 0), frame_count - 1))
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.release()
                raise OSError(video)
            frames.append(frame)
        capture.release()
        center = extracted / f"asl_boundary_{number:04d}.png"
        context = extracted / f"asl_boundary_{number:04d}_context.jpg"
        cv2.imwrite(str(center), frames[2])
        thumbs = [cv2.resize(frame, (240, 180)) for frame in frames]
        cv2.imwrite(str(context), cv2.hconcat(thumbs))
        candidates.append(
            _candidate(
                "ASL_CITIZEN_BOUNDARY",
                f"{row['_split']}:{Path(row['Video file']).stem}:{frame_index}",
                Path(row["Video file"]).stem,
                row["Participant ID"],
                center,
                context,
                source_split=row["_split"],
                session_id=Path(row["Video file"]).stem,
                device_id="unknown",
                environment_id="unknown",
                camera_view="unknown",
            )
        )
    return candidates, {
        "source": "ASL Citizen train/val boundary",
        "raw_frames": len(rows),
        "unique_clips": len(candidates),
        "participants": len({row["participant_id"] for row in candidates}),
        "status": "BLINDED_REVIEW_CANDIDATE",
    }


def prepare_topup(
    config: dict[str, Any],
    output: Path,
    seed: list[dict[str, Any]],
    canonical: list[dict[str, Any]],
) -> dict[str, Any]:
    seed_fingerprints = [int(row["dhash64"], 16) for row in seed]
    reviewed_n0_ids = {row["source_sample_id"] for row in canonical}
    candidates, inventory = _existing_image_candidates(config, reviewed_n0_ids)
    positive_gold = _resolve(config["trusted_gold_run"])
    excluded_clips = {row["clip_id"] for row in _read_csv(positive_gold / "internal_index.csv")}
    asl_candidates, asl_inventory = _extract_asl_candidates(config, output, excluded_clips)
    candidates.extend(asl_candidates)
    inventory.append(asl_inventory)

    unique_hashes: set[str] = set()
    screened: list[dict[str, Any]] = []
    rejected = Counter()
    for row in sorted(candidates, key=lambda item: (item["source_group"], item["source_id"])):
        if row["source_image_sha256"] in unique_hashes:
            rejected["exact_duplicate"] += 1
            continue
        if any(
            (row["_dhash_int"] ^ prior).bit_count() <= int(config["dhash_hamming_max"])
            for prior in seed_fingerprints
        ):
            rejected["near_duplicate_of_seed"] += 1
            continue
        if any(
            (row["_dhash_int"] ^ prior["_dhash_int"]).bit_count()
            <= int(config["dhash_hamming_max"])
            for prior in screened
        ):
            rejected["near_duplicate_of_candidate"] += 1
            continue
        unique_hashes.add(row["source_image_sha256"])
        screened.append(row)

    target = int(config["queue_unique_candidates"])
    source_counts = Counter()
    participant_counts = Counter()
    selected = []
    remaining = list(screened)
    while remaining and len(selected) < target:
        row = min(
            remaining,
            key=lambda item: (
                source_counts[item["source_group"]],
                participant_counts[item["participant_id"]],
                item["source_group"],
                item["source_id"],
            ),
        )
        remaining.remove(row)
        selected.append(row)
        source_counts[row["source_group"]] += 1
        participant_counts[row["participant_id"]] += 1
    if len(selected) < target:
        raise ValueError(f"only {len(selected)} diversity-screened candidates; need {target}")

    rng = random.Random(int(config["qc_seed"]))
    repeats = rng.sample(selected, int(config["qc_repeat_count"]))
    ordered = [(row, False) for row in selected] + [(row, True) for row in repeats]
    for _ in range(10000):
        rng.shuffle(ordered)
        positions: dict[str, list[int]] = defaultdict(list)
        for index, (row, _) in enumerate(ordered):
            positions[f"{row['source_group']}:{row['source_id']}"].append(index)
        if all(
            len(values) == 1 or abs(values[0] - values[1]) >= 30 for values in positions.values()
        ):
            break
    else:
        raise ValueError("could not space hidden repeats")

    review_dir = output / "review_package"
    review_dir.mkdir()
    center_dir = review_dir / "center_images"
    context_dir = review_dir / "context_panels"
    center_dir.mkdir()
    context_dir.mkdir()
    queue_rows = []
    manifest_rows = []
    canonical_review: dict[str, str] = {}
    for number, (row, repeat) in enumerate(ordered, start=1):
        review_id = f"topup_{number:04d}"
        key = f"{row['source_group']}:{row['source_id']}"
        if not repeat:
            canonical_review[key] = review_id
        center = center_dir / f"{review_id}.png"
        context = context_dir / f"{review_id}.jpg"
        shutil.copy2(Path(row["source_image_path"]), center)
        if row["source_context_path"]:
            shutil.copy2(Path(row["source_context_path"]), context)
        else:
            shutil.copy2(Path(row["source_image_path"]), context)
        queue_rows.append(
            {
                "review_id": review_id,
                "center_image_path": str(center.resolve()),
                "context_panel_path": str(context.resolve()),
                "review_status": "unreviewed",
                "semantic_class": "",
                "notes": "",
            }
        )
        manifest_rows.append(
            {
                "review_id": review_id,
                "candidate_id": f"candidate_{selected.index(row) + 1:04d}",
                **{
                    field: row.get(field, "")
                    for field in TOPUP_FIELDS
                    if field
                    not in {"review_id", "candidate_id", "canonical_review_id", "is_qc_repeat"}
                },
                "dhash64": f"{row['_dhash_int']:016x}",
                "canonical_review_id": "" if repeat else review_id,
                "is_qc_repeat": str(repeat).lower(),
            }
        )
    for row in manifest_rows:
        if row["is_qc_repeat"] == "true":
            source = next(
                item
                for item in selected
                if item["source_id"] == row["source_id"]
                and item["source_group"] == row["source_group"]
            )
            row["canonical_review_id"] = canonical_review[
                f"{source['source_group']}:{source['source_id']}"
            ]
    _write_csv(review_dir / "review_queue.csv", QUEUE_FIELDS, queue_rows)
    _write_csv(review_dir / "candidate_manifest.csv", TOPUP_FIELDS, manifest_rows)
    _write_csv(output / "NEGATIVE_DIVERSITY_TOPUP_REVIEW_QUEUE.csv", TOPUP_FIELDS, manifest_rows)

    source_inventory = inventory + [
        {
            "source": "A1 no-sign benchmark",
            "raw_frames": 0,
            "unique_clips": 4,
            "participants": 1,
            "status": "UNUSABLE_FOR_NEGATIVE_BENCHMARK",
            "reason": "logs only; no RGB",
        },
        {
            "source": "fresh E6 negative recordings",
            "raw_frames": 560,
            "unique_clips": 560,
            "participants": 1,
            "status": "PROTECTED/RESTRICTED",
            "reason": "fresh evaluation lineage; visible-hand contexts by design",
        },
        {
            "source": "ASL Citizen test",
            "raw_frames": 32941,
            "unique_clips": 32941,
            "participants": 11,
            "status": "PROTECTED/RESTRICTED",
            "reason": "protected test split",
        },
        {
            "source": "recorder/product-core positives",
            "raw_frames": 1956,
            "unique_clips": 1956,
            "participants": "mixed",
            "status": "UNUSABLE_FOR_NEGATIVE_BENCHMARK",
            "reason": "positive/signing lineage; no exact zero truth",
        },
    ]
    (output / "source_inventory.json").write_text(
        json.dumps(source_inventory, indent=2), encoding="utf-8"
    )
    summary = {
        "CURRENT_NEGATIVE_GOLD": 76,
        "REMAINING_TARGET": 124,
        "DIVERSE_EXISTING_BLINDED_REVIEW_CANDIDATES": len(screened),
        "queue_unique_candidates": len(selected),
        "hidden_qc_repeats": int(config["qc_repeat_count"]),
        "queue_rows": len(queue_rows),
        "candidate_source_counts": dict(Counter(row["source_group"] for row in screened)),
        "selected_source_counts": dict(source_counts),
        "selected_participants": len({row["participant_id"] for row in selected}),
        "selected_clips": len({row["clip_id"] for row in selected}),
        "selected_devices": sorted({row["device_id"] for row in selected}),
        "selected_environments": sorted({row["environment_id"] for row in selected}),
        "similarity_rejections": dict(rejected),
        "maximum_possible_zero_hand_yield": len(selected),
        "expected_zero_hand_yield": "UNKNOWN; N0 95.2% must not be generalized",
        "decision": "EXISTING_DIVERSE_POOL_SUFFICIENT_FOR_NEXT_REVIEW",
        "new_recording_justified_now": False,
    }
    (output / "topup_prepare_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    provenance = {
        "protocol_version": config["protocol_version"],
        "selection_seed": config["selection_seed"],
        "qc_seed": config["qc_seed"],
        "dhash_hamming_max": config["dhash_hamming_max"],
        "old_semantic_labels_used_for_selection": False,
        "model_outputs_used_for_selection": False,
        "config_sha256": _sha256(DEFAULT_CONFIG),
        "runner_sha256": _sha256(Path(__file__)),
        "n0_config_sha256": _sha256(N0_CONFIG),
        "n0_protocol_sha256": _sha256(N0_PROTOCOL),
        "n0_runner_sha256": _sha256(RUNNER_N0),
        "review_queue_sha256": _sha256(review_dir / "review_queue.csv"),
        "candidate_manifest_sha256": _sha256(review_dir / "candidate_manifest.csv"),
    }
    (output / "topup_provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    return summary


def check_review(config: dict[str, Any]) -> dict[str, Any]:
    review_dir = _resolve(config["output_run"]) / "review_package"
    rows = _read_csv(review_dir / "review_queue.csv")
    errors = []
    counts = Counter()
    for row in rows:
        if (
            not Path(row["center_image_path"]).is_file()
            or not Path(row["context_panel_path"]).is_file()
        ):
            errors.append(f"missing asset: {row['review_id']}")
        if row["review_status"] == "accepted" and row["semantic_class"] in SEMANTIC_CLASSES:
            counts[row["semantic_class"]] += 1
        elif row["review_status"] != "unreviewed":
            errors.append(f"invalid review state: {row['review_id']}")
    completed = sum(row["review_status"] == "accepted" for row in rows)
    return {
        "rows": len(rows),
        "completed": completed,
        "remaining": len(rows) - completed,
        "counts": dict(counts),
        "errors": errors,
        "passed": not errors and completed == len(rows),
    }


def prepare(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    output = _resolve(config["output_run"])
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    n0 = finalize_n0(config, output)
    summary = prepare_topup(config, output, n0["seed"], n0["canonical"])
    return {
        "n0": {key: value for key, value in n0.items() if key not in {"seed", "canonical"}},
        "topup": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "review", "check", "status"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    output = _resolve(config["output_run"])
    if args.command == "prepare":
        result = prepare(args.config)
    elif args.command == "review":
        ReviewApp(output / "review_package/review_queue.csv").run()
        return 0
    else:
        result = check_review(config)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
