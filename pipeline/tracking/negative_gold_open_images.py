"""Prepare and review a bounded Open Images V7 NEGATIVE_GOLD candidate package."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from pipeline.tracking.n0_blinded_readjudication import _dhash

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "model/config/recognition_upgrade/negative_gold_open_images_v7.json"
PROTOCOL = ROOT / "context/recognition_upgrade/NEGATIVE_GOLD_EXTERNAL_OPEN_IMAGES_PROTOCOL.md"
SEMANTIC_CLASSES = ("ZERO_HAND", "HAND_VISIBLE", "UNCERTAIN")
QUEUE_FIELDS = ("review_id", "image_path", "review_status", "semantic_class", "notes")
REVIEW_MAP_FIELDS = (
    "review_id",
    "candidate_id",
    "open_images_id",
    "canonical_review_id",
    "is_qc_repeat",
    "source_image_sha256",
)
CC_BY_2 = "https://creativecommons.org/licenses/by/2.0/"
HUMAN_CLASS_NAMES = {"Person", "Man", "Woman", "Boy", "Girl", "Human body", "Human face"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
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


def _git(command: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *command], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        return f"UNAVAILABLE: {error}"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if tuple(config["semantic_classes"]) != SEMANTIC_CLASSES:
        raise ValueError("semantic classes drifted from the frozen protocol")
    if config["allowed_image_license"] != CC_BY_2:
        raise ValueError("eligible image license drifted")
    if (
        config["person_free_target"] + config["people_present_target"]
        != config["canonical_candidate_count"]
    ):
        raise ValueError("candidate composition does not sum to the canonical target")
    if int(config["dhash_hamming_max"]) != 4:
        raise ValueError("frozen dHash threshold drifted")
    return config


def _scene_bucket(names: set[str]) -> str:
    lowered = " ".join(sorted(names)).lower()
    groups = (
        ("ANIMAL", ("animal", "bird", "dog", "cat", "horse", "fish", "insect")),
        ("FOOD", ("food", "fruit", "vegetable", "dish", "drink", "bread")),
        ("TRANSPORT", ("vehicle", "car", "bus", "train", "aircraft", "boat", "bicycle")),
        ("INDOOR", ("room", "furniture", "kitchen", "bed", "office", "shelf")),
        ("ARCHITECTURE", ("building", "house", "tower", "bridge", "church", "castle")),
        ("NATURE", ("tree", "plant", "flower", "mountain", "water", "sky", "beach")),
        ("URBAN", ("street", "road", "traffic", "city", "sidewalk", "sign")),
        ("OBJECT", ("tool", "device", "instrument", "container", "clock", "book")),
        ("CLOTHING", ("clothing", "dress", "shirt", "shoe", "hat", "jacket")),
    )
    return next(
        (group for group, words in groups if any(word in lowered for word in words)), "MIXED"
    )


def _metadata_state(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cache = _resolve(config["metadata_cache"])
    expected = config["expected_metadata_sha256"]
    actual_hashes = {}
    for name, expected_hash in expected.items():
        path = cache / name
        actual = _sha256(path)
        if actual != expected_hash:
            raise ValueError(f"official metadata hash drifted: {name}")
        actual_hashes[name] = actual

    class_names = {}
    with (cache / "oidv7-class-descriptions.csv").open(encoding="utf-8-sig", newline="") as handle:
        for mid, name in csv.reader(handle):
            class_names[mid] = name
    name_to_mid = {name: mid for mid, name in class_names.items()}
    required = HUMAN_CLASS_NAMES | {"Person", "Human face"}
    missing = sorted(required - name_to_mid.keys())
    if missing:
        raise ValueError(f"missing required Open Images classes: {missing}")

    positives: dict[str, set[str]] = defaultdict(set)
    negatives: dict[str, set[str]] = defaultdict(set)
    label_frequency: Counter[str] = Counter()
    label_path = cache / "validation-annotations-human-imagelabels-boxable.csv"
    for row in _read_csv(label_path):
        if row["Source"] not in {"verification", "crowdsource-verification"}:
            continue
        target = positives if row["Confidence"] == "1" else negatives
        target[row["ImageID"]].add(row["LabelName"])
        if row["Confidence"] == "1":
            label_frequency[row["LabelName"]] += 1

    person_mid = name_to_mid["Person"]
    face_mid = name_to_mid["Human face"]
    human_mids = {name_to_mid[name] for name in HUMAN_CLASS_NAMES}
    eligible = []
    licensing = Counter()
    for row in _read_csv(cache / "validation-images-with-rotation.csv"):
        complete = all(
            row.get(field, "").strip()
            for field in ("OriginalURL", "OriginalLandingURL", "Author", "License")
        )
        if not complete:
            licensing["missing_required_metadata"] += 1
            continue
        if row["License"] != config["allowed_image_license"]:
            licensing["unsuitable_license"] += 1
            continue
        licensing["eligible_cc_by_2"] += 1
        image_id = row["ImageID"]
        positive = positives.get(image_id, set())
        negative = negatives.get(image_id, set())
        category = ""
        if person_mid in negative and not positive.intersection(human_mids):
            category = "PERSON_FREE_DISCOVERY"
        elif person_mid in positive and face_mid in positive:
            category = "PEOPLE_PRESENT_DISCOVERY"
        if not category:
            continue
        positive_names = {class_names.get(mid, mid) for mid in positive}
        nonhuman = [mid for mid in positive if mid not in human_mids]
        primary_mid = min(nonhuman, key=lambda mid: (label_frequency[mid], mid), default="")
        eligible.append(
            {
                **row,
                "discovery_category": category,
                "scene_bucket": _scene_bucket(positive_names),
                "primary_label": class_names.get(primary_mid, "HUMAN_ONLY"),
                "positive_label_names": "|".join(sorted(positive_names)),
            }
        )
    audit = {
        "metadata_hashes": actual_hashes,
        "image_metadata_rows": sum(licensing.values()),
        "licensing": dict(licensing),
        "eligible_discovery_rows": dict(Counter(row["discovery_category"] for row in eligible)),
        "selection_truth_warning": (
            "Open Images labels are discovery metadata only; annotation absence is not "
            "ZERO_HAND truth."
        ),
    }
    return eligible, audit


def _diverse_order(rows: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    shuffled = list(rows)
    rng.shuffle(shuffled)
    rank = {row["ImageID"]: index for index, row in enumerate(shuffled)}
    remaining = list(shuffled)
    selected = []
    authors: set[str] = set()
    bucket_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    while remaining and len(selected) < limit:
        eligible = [row for row in remaining if row["Author"] not in authors]
        if not eligible:
            break
        row = min(
            eligible,
            key=lambda item: (
                bucket_counts[item["scene_bucket"]],
                label_counts[item["primary_label"]],
                rank[item["ImageID"]],
            ),
        )
        selected.append(row)
        authors.add(row["Author"])
        bucket_counts[row["scene_bucket"]] += 1
        label_counts[row["primary_label"]] += 1
        remaining.remove(row)
    if len(selected) < limit:
        raise ValueError(
            f"only {len(selected)} metadata-diverse candidates available; need {limit}"
        )
    return selected


def _interleave(
    free: list[dict[str, Any]],
    present: list[dict[str, Any]],
    total: int,
    free_weight: int,
    present_weight: int,
) -> list[dict[str, Any]]:
    result = []
    positions = {"PERSON_FREE_DISCOVERY": 0, "PEOPLE_PRESENT_DISCOVERY": 0}
    pools = {"PERSON_FREE_DISCOVERY": free, "PEOPLE_PRESENT_DISCOVERY": present}
    weights = {"PERSON_FREE_DISCOVERY": free_weight, "PEOPLE_PRESENT_DISCOVERY": present_weight}
    for _ in range(total):
        category = min(
            pools,
            key=lambda key: (positions[key] / weights[key], key),
        )
        if positions[category] >= len(pools[category]):
            category = next(key for key in pools if positions[key] < len(pools[key]))
        result.append(pools[category][positions[category]])
        positions[category] += 1
    return result


def _download_one(row: dict[str, Any], directory: Path, config: dict[str, Any]) -> dict[str, Any]:
    image_id = row["ImageID"]
    url = config["image_download_url_template"].format(image_id=image_id)
    target = directory / f"{image_id}.jpg"
    timestamp = datetime.now(UTC).isoformat()
    request = urllib.request.Request(
        url, headers={"User-Agent": "AppHear-benchmark-governance/1.0"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=int(config["download_timeout_seconds"])
        ) as response:
            data = response.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise ValueError("image exceeds 20 MiB safety bound")
        temporary = target.with_suffix(".jpg.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, target)
        return {"ok": True, "path": target, "download_url": url, "download_timestamp": timestamp}
    except Exception as error:  # network errors must be preserved in the attempt ledger
        return {
            "ok": False,
            "path": target,
            "download_url": url,
            "download_timestamp": timestamp,
            "error": f"{type(error).__name__}: {error}",
        }


def _review_order(
    selected: list[dict[str, Any]], repeat_count: int, seed: int
) -> list[tuple[dict[str, Any], bool]]:
    rng = random.Random(seed)
    primaries = list(selected)
    rng.shuffle(primaries)
    repeats = rng.sample(primaries, repeat_count)
    combined = [(row, False) for row in primaries] + [(row, True) for row in repeats]
    for _ in range(10000):
        rng.shuffle(combined)
        positions: dict[str, list[int]] = defaultdict(list)
        for index, (row, _repeat) in enumerate(combined):
            positions[row["ImageID"]].append(index)
        if all(
            len(values) == 1 or abs(values[0] - values[1]) >= 20 for values in positions.values()
        ):
            return combined
    raise ValueError("could not distribute hidden repeats with the frozen spacing")


def _rotate_for_display(image: Any, rotation_degrees: str) -> Any:
    normalized = rotation_degrees.strip()
    if normalized in {"90", "90.0"}:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if normalized in {"180", "180.0"}:
        return cv2.rotate(image, cv2.ROTATE_180)
    if normalized in {"270", "270.0"}:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    return image


def prepare(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    output = _resolve(config["output_run"])
    temporary_output = output.with_name(output.name + ".preparing")
    if output.exists() or temporary_output.exists():
        raise FileExistsError(f"refusing to overwrite package or preparation directory: {output}")
    if not PROTOCOL.is_file():
        raise FileNotFoundError(PROTOCOL)
    seed = _read_csv(_resolve(config["seed_manifest"]))
    if len(seed) != 76:
        raise ValueError("frozen NEGATIVE_GOLD seed is not 76 rows")
    seed_hashes = {row["image_sha256"] for row in seed}
    seed_dhashes = [int(row["dhash64"], 16) for row in seed]

    eligible, metadata_audit = _metadata_state(config)
    by_category = defaultdict(list)
    for row in eligible:
        by_category[row["discovery_category"]].append(row)
    max_attempts = int(config["maximum_download_attempts"])
    free_limit = round(
        max_attempts * int(config["person_free_target"]) / int(config["canonical_candidate_count"])
    )
    present_limit = max_attempts - free_limit
    free = _diverse_order(
        by_category["PERSON_FREE_DISCOVERY"], free_limit, int(config["selection_seed"])
    )
    present = _diverse_order(
        by_category["PEOPLE_PRESENT_DISCOVERY"],
        present_limit,
        int(config["selection_seed"]) + 1,
    )
    download_plan = _interleave(
        free,
        present,
        max_attempts,
        int(config["person_free_target"]),
        int(config["people_present_target"]),
    )

    temporary_output.mkdir(parents=True)
    downloads = temporary_output / "download_attempts"
    source_images = temporary_output / "source_images"
    review_dir = temporary_output / "review_package"
    review_images = review_dir / "images"
    for directory in (downloads, source_images, review_images):
        directory.mkdir(parents=True)

    targets = {
        "PERSON_FREE_DISCOVERY": int(config["person_free_target"]),
        "PEOPLE_PRESENT_DISCOVERY": int(config["people_present_target"]),
    }
    selected_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    retained_hashes = set(seed_hashes)
    retained_dhashes = list(seed_dhashes)
    attempts = []
    batch_size = int(config["download_batch_size"])
    cursor = 0
    while cursor < len(download_plan) and any(
        selected_counts[key] < targets[key] for key in targets
    ):
        batch = [
            row
            for row in download_plan[cursor : cursor + batch_size]
            if selected_counts[row["discovery_category"]] < targets[row["discovery_category"]]
        ]
        cursor += batch_size
        with ThreadPoolExecutor(max_workers=int(config["download_workers"])) as executor:
            results = list(executor.map(lambda row: _download_one(row, downloads, config), batch))
        for row, downloaded in zip(batch, results, strict=True):
            category = row["discovery_category"]
            attempt = {
                "open_images_id": row["ImageID"],
                "discovery_category": category,
                "official_download_url": downloaded["download_url"],
                "download_timestamp_utc": downloaded["download_timestamp"],
                "download_path": str(
                    (output / "download_attempts" / f"{row['ImageID']}.jpg").resolve()
                ),
                "selected": False,
                "reason": "",
            }
            if not downloaded["ok"]:
                attempt["reason"] = downloaded["error"]
                attempts.append(attempt)
                continue
            image_path = Path(downloaded["path"])
            image = cv2.imread(str(image_path))
            if image is None:
                attempt["reason"] = "decode_failed"
                attempts.append(attempt)
                continue
            height, width = image.shape[:2]
            image_hash = _sha256(image_path)
            fingerprint = _dhash(image_path)
            reason = ""
            if selected_counts[category] >= targets[category]:
                reason = "category_target_already_filled"
            elif width < int(config["minimum_width"]) or height < int(config["minimum_height"]):
                reason = "below_minimum_dimensions"
            elif image_hash in retained_hashes:
                reason = "exact_duplicate"
            elif any(
                (fingerprint ^ prior).bit_count() <= int(config["dhash_hamming_max"])
                for prior in retained_dhashes
            ):
                reason = "near_duplicate_dhash_le_4"
            if reason:
                attempt["reason"] = reason
                attempts.append(attempt)
                continue
            source_target = source_images / f"{row['ImageID']}.jpg"
            shutil.copy2(image_path, source_target)
            selected_counts[category] += 1
            retained_hashes.add(image_hash)
            retained_dhashes.append(fingerprint)
            selected.append(
                {
                    **row,
                    "candidate_id": f"oi_{len(selected) + 1:04d}",
                    "official_download_url": downloaded["download_url"],
                    "download_timestamp_utc": downloaded["download_timestamp"],
                    "source_image_path": str(
                        (output / "source_images" / source_target.name).resolve()
                    ),
                    "source_image_sha256": image_hash,
                    "dhash64": f"{fingerprint:016x}",
                    "width": width,
                    "height": height,
                }
            )
            attempt["selected"] = True
            attempt["reason"] = "selected"
            attempt["source_image_sha256"] = image_hash
            attempt["dhash64"] = f"{fingerprint:016x}"
            attempts.append(attempt)

    if selected_counts != Counter(targets):
        raise ValueError(f"bounded download could not fill frozen composition: {selected_counts}")
    if len(selected) != int(config["canonical_candidate_count"]):
        raise ValueError("canonical candidate count drifted")

    candidate_fields = tuple(selected[0])
    _write_csv(
        temporary_output / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv", candidate_fields, selected
    )
    (temporary_output / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.json").write_text(
        json.dumps(selected, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    attempt_fields = tuple(dict.fromkeys(key for row in attempts for key in row))
    _write_csv(temporary_output / "download_attempts.csv", attempt_fields, attempts)

    order = _review_order(selected, int(config["qc_repeat_count"]), int(config["qc_seed"]))
    canonical_review_ids = {}
    queue_rows = []
    map_rows = []
    for number, (row, is_repeat) in enumerate(order, start=1):
        review_id = f"external_{number:04d}"
        if not is_repeat:
            canonical_review_ids[row["ImageID"]] = review_id
        target = review_images / f"{review_id}.jpg"
        shutil.copy2(source_images / f"{row['ImageID']}.jpg", target)
        queue_rows.append(
            {
                "review_id": review_id,
                "image_path": str((output / "review_package" / "images" / target.name).resolve()),
                "review_status": "unreviewed",
                "semantic_class": "",
                "notes": "",
            }
        )
        map_rows.append(
            {
                "review_id": review_id,
                "candidate_id": row["candidate_id"],
                "open_images_id": row["ImageID"],
                "canonical_review_id": "" if is_repeat else review_id,
                "is_qc_repeat": str(is_repeat).lower(),
                "source_image_sha256": row["source_image_sha256"],
            }
        )
    for row in map_rows:
        if row["is_qc_repeat"] == "true":
            row["canonical_review_id"] = canonical_review_ids[row["open_images_id"]]
    _write_csv(review_dir / "review_queue.csv", QUEUE_FIELDS, queue_rows)
    _write_csv(review_dir / "internal_repeat_map.csv", REVIEW_MAP_FIELDS, map_rows)

    for row in map_rows:
        review_path = review_images / f"{row['review_id']}.jpg"
        if _sha256(review_path) != row["source_image_sha256"]:
            raise ValueError(f"review copy bytes drifted: {row['review_id']}")

    attribution = [
        "# Open Images Candidate Attribution",
        "",
        "Every image below is listed by Open Images as CC BY 2.0. Preserve this file "
        "with the package.",
        "The review copies preserve the downloaded CVDF bytes unchanged.",
        "",
    ]
    for row in selected:
        title = row["Title"] or "Untitled"
        attribution.append(
            f"- `{row['ImageID']}` — {title} by {row['Author']}; "
            f"[source]({row['OriginalLandingURL']}); [CC BY 2.0]({row['License']})."
        )
    (temporary_output / "ATTRIBUTION.md").write_text(
        "\n".join(attribution) + "\n", encoding="utf-8"
    )

    source_manifest = temporary_output / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv"
    queue_path = review_dir / "review_queue.csv"
    summary = {
        "status": "OPEN_IMAGES_EXTERNAL_CANDIDATE_PACKAGE_FROZEN_UNREVIEWED",
        "dataset": "Open Images V7 validation",
        "canonical_candidates": len(selected),
        "hidden_repeats": int(config["qc_repeat_count"]),
        "review_rows": len(queue_rows),
        "discovery_category_counts": dict(sorted(selected_counts.items())),
        "scene_bucket_counts": dict(
            sorted(Counter(row["scene_bucket"] for row in selected).items())
        ),
        "unique_authors": len({row["Author"] for row in selected}),
        "unique_primary_labels": len({row["primary_label"] for row in selected}),
        "download_attempts": len(attempts),
        "download_rejections": dict(
            sorted(Counter(row["reason"] for row in attempts if not row["selected"]).items())
        ),
        "exact_duplicates_removed": sum(row["reason"] == "exact_duplicate" for row in attempts),
        "near_duplicates_removed": sum(
            row["reason"] == "near_duplicate_dhash_le_4" for row in attempts
        ),
        "near_duplicate_threshold": "64-bit dHash Hamming distance <=4",
        "zero_hand_truth": "UNREVIEWED; no candidate is ZERO_HAND until human review",
    }
    (temporary_output / "prepare_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    provenance = {
        "protocol_version": config["protocol_version"],
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "working_tree_status": _git(["status", "--short"]),
        "python": sys.version,
        "platform": platform.platform(),
        "opencv": cv2.__version__,
        "selection_seed": config["selection_seed"],
        "qc_seed": config["qc_seed"],
        "dhash_hamming_max": config["dhash_hamming_max"],
        "model_outputs_used": False,
        "hand_truth_inferred_from_open_images": False,
        "metadata_audit": metadata_audit,
        "config_sha256": _sha256(config_path),
        "protocol_sha256": _sha256(PROTOCOL),
        "runner_sha256": _sha256(Path(__file__)),
        "seed_manifest_sha256": _sha256(_resolve(config["seed_manifest"])),
        "source_license_manifest_sha256": _sha256(source_manifest),
        "review_queue_sha256": _sha256(queue_path),
        "internal_repeat_map_sha256": _sha256(review_dir / "internal_repeat_map.csv"),
        "official_metadata_urls": config["official_metadata_urls"],
    }
    (temporary_output / "provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    temporary_output.rename(output)
    return summary


def check_review(config: dict[str, Any]) -> dict[str, Any]:
    output = _resolve(config["output_run"])
    queue = _read_csv(output / "review_package/review_queue.csv")
    mapping = _read_csv(output / "review_package/internal_repeat_map.csv")
    errors = []
    counts: Counter[str] = Counter()
    for row in queue:
        if not Path(row["image_path"]).is_file():
            errors.append(f"missing image: {row['review_id']}")
        if row["review_status"] == "accepted" and row["semantic_class"] in SEMANTIC_CLASSES:
            counts[row["semantic_class"]] += 1
        elif row["review_status"] != "unreviewed":
            errors.append(f"invalid review state: {row['review_id']}")
    by_id = {row["review_id"]: row for row in mapping}
    for row in mapping:
        if row["is_qc_repeat"] == "true":
            canonical = by_id.get(row["canonical_review_id"])
            if canonical is None or canonical["source_image_sha256"] != row["source_image_sha256"]:
                errors.append(f"invalid repeat mapping: {row['review_id']}")
    completed = sum(row["review_status"] == "accepted" for row in queue)
    result = {
        "rows": len(queue),
        "canonical_candidates": len(queue) - int(config["qc_repeat_count"]),
        "hidden_repeats": int(config["qc_repeat_count"]),
        "completed": completed,
        "remaining": len(queue) - completed,
        "counts_including_hidden_repeats": dict(sorted(counts.items())),
        "errors": errors,
        "passed": not errors and completed == len(queue),
    }
    (output / "review_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def finalize_review(config: dict[str, Any]) -> dict[str, Any]:
    output = _resolve(config["output_run"])
    check = check_review(config)
    if not check["passed"]:
        raise ValueError("review is incomplete or structurally invalid")
    queue = _read_csv(output / "review_package/review_queue.csv")
    mapping = _read_csv(output / "review_package/internal_repeat_map.csv")
    source = {
        row["ImageID"]: row for row in _read_csv(output / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")
    }
    review_by_id = {row["review_id"]: row for row in queue}
    map_by_id = {row["review_id"]: row for row in mapping}

    canonical = []
    for row in mapping:
        if row["is_qc_repeat"] == "true":
            continue
        review = review_by_id[row["review_id"]]
        metadata = source[row["open_images_id"]]
        canonical.append(
            {
                "review_id": row["review_id"],
                "candidate_id": row["candidate_id"],
                "open_images_id": row["open_images_id"],
                "semantic_class": review["semantic_class"],
                "notes": review["notes"],
                "source_image_path": metadata["source_image_path"],
                "source_image_sha256": metadata["source_image_sha256"],
                "dhash64": metadata["dhash64"],
                "discovery_category": metadata["discovery_category"],
                "scene_bucket": metadata["scene_bucket"],
                "author": metadata["Author"],
                "license": metadata["License"],
                "original_landing_url": metadata["OriginalLandingURL"],
            }
        )
    _write_csv(output / "canonical_human_labels_220.csv", tuple(canonical[0]), canonical)

    qc_rows = []
    for row in mapping:
        if row["is_qc_repeat"] != "true":
            continue
        repeated_label = review_by_id[row["review_id"]]["semantic_class"]
        canonical_label = review_by_id[row["canonical_review_id"]]["semantic_class"]
        exact = repeated_label == canonical_label
        critical = {repeated_label, canonical_label} == {"ZERO_HAND", "HAND_VISIBLE"}
        zero_vs_nonzero = (repeated_label == "ZERO_HAND") != (canonical_label == "ZERO_HAND")
        qc_rows.append(
            {
                "repeat_review_id": row["review_id"],
                "canonical_review_id": row["canonical_review_id"],
                "open_images_id": row["open_images_id"],
                "source_image_sha256": row["source_image_sha256"],
                "canonical_label": canonical_label,
                "repeat_label": repeated_label,
                "exact_agreement": exact,
                "zero_vs_nonzero_disagreement": zero_vs_nonzero,
                "critical_zero_hand_vs_hand_visible": critical,
            }
        )
        canonical_map = map_by_id[row["canonical_review_id"]]
        if canonical_map["source_image_sha256"] != row["source_image_sha256"]:
            raise ValueError(f"repeat mapping hash mismatch: {row['review_id']}")
    _write_csv(output / "hidden_repeat_qc.csv", tuple(qc_rows[0]), qc_rows)
    exact_count = sum(row["exact_agreement"] for row in qc_rows)
    critical_count = sum(row["critical_zero_hand_vs_hand_visible"] for row in qc_rows)
    zero_nonzero_count = sum(row["zero_vs_nonzero_disagreement"] for row in qc_rows)
    discordant_canonical_ids = {
        row["canonical_review_id"] for row in qc_rows if row["zero_vs_nonzero_disagreement"]
    }
    counts = Counter(row["semantic_class"] for row in canonical)
    stable_zero_count = sum(
        row["semantic_class"] == "ZERO_HAND" and row["review_id"] not in discordant_canonical_ids
        for row in canonical
    )
    qc = {
        "repeat_pairs": len(qc_rows),
        "exact_agreements": exact_count,
        "exact_agreement_fraction": exact_count / len(qc_rows),
        "three_class_disagreements": len(qc_rows) - exact_count,
        "zero_vs_nonzero_disagreements": zero_nonzero_count,
        "critical_zero_hand_vs_hand_visible_disagreements": critical_count,
        "all_repeat_source_bytes_identical": True,
        "hard_qc_passed": critical_count == 0,
    }
    (output / "hidden_repeat_qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
    decision = (
        "OPEN_IMAGES_REVIEW_COMPLETE_QC_PASSED"
        if qc["hard_qc_passed"]
        else "OPEN_IMAGES_REVIEW_COMPLETE_QC_FAILED_REPAIR_REQUIRED"
    )
    result = {
        "decision": decision,
        "canonical_rows": len(canonical),
        "canonical_counts": dict(sorted(counts.items())),
        "provisional_canonical_zero_hand": counts["ZERO_HAND"],
        "zero_hand_excluding_repeat_disagreements": stable_zero_count,
        "trusted_negative_gold_before": 76,
        "trusted_negative_gold_after": 76,
        "remaining_trusted_deficit": 124,
        "benchmark_frozen": False,
        "qc": qc,
        "next_action": (
            "Prepare a bounded human repair pass; do not freeze NEGATIVE_GOLD_V1."
            if not qc["hard_qc_passed"]
            else "Eligible for diversity selection and exact-124 finalization."
        ),
    }
    (output / "finalize_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


class ReviewApp:
    def __init__(self, queue_path: Path) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.queue_path = queue_path
        self.rows = _read_csv(queue_path)
        package = queue_path.parents[1]
        source_by_id = {
            row["ImageID"]: row
            for row in _read_csv(package / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")
        }
        self.rotation_by_review = {
            row["review_id"]: source_by_id[row["open_images_id"]]["Rotation"]
            for row in _read_csv(queue_path.parent / "internal_repeat_map.csv")
        }
        self.index = next(
            (index for index, row in enumerate(self.rows) if row["review_status"] != "accepted"),
            0,
        )
        self.zoom = 1.0
        self.root = tk.Tk()
        self.root.title("AppHear External Zero-Hand Review")
        self.root.geometry("1400x920")
        self.root.configure(bg="#f4f5f7")
        self.status = tk.StringVar()
        self.notes = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.status, font=("Segoe UI", 15, "bold"), bg="#f4f5f7"
        ).pack(pady=(10, 4))
        tk.Label(
            self.root,
            text="Is ANY part of a human hand visible anywhere in this image?",
            font=("Segoe UI", 16, "bold"),
            fg="#0f172a",
            bg="#f4f5f7",
        ).pack(pady=4)
        tk.Label(
            self.root,
            text=(
                "ZERO_HAND only when absolutely no fingertip, palm, partial, clipped, blurred, "
                "lap, face/chest-adjacent, or tiny distant hand is visible."
            ),
            font=("Segoe UI", 11, "bold"),
            fg="#9a3412",
            bg="#f4f5f7",
            wraplength=1320,
        ).pack(pady=(0, 8))

        viewer = tk.Frame(self.root, bg="#111827")
        viewer.pack(fill="both", expand=True, padx=12)
        self.canvas = tk.Canvas(viewer, bg="#111827", highlightthickness=0)
        xscroll = ttk.Scrollbar(viewer, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(viewer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        viewer.grid_rowconfigure(0, weight=1)
        viewer.grid_columnconfigure(0, weight=1)

        zoom_frame = tk.Frame(self.root, bg="#f4f5f7")
        zoom_frame.pack(pady=5)
        tk.Button(zoom_frame, text="Zoom −", command=lambda: self.change_zoom(0.8), width=10).pack(
            side="left", padx=3
        )
        tk.Button(zoom_frame, text="Fit", command=self.reset_zoom, width=10).pack(
            side="left", padx=3
        )
        tk.Button(zoom_frame, text="Zoom +", command=lambda: self.change_zoom(1.25), width=10).pack(
            side="left", padx=3
        )

        actions = tk.Frame(self.root, bg="#f4f5f7")
        actions.pack(pady=7)
        action_specs = (
            ("1 — ZERO_HAND", "ZERO_HAND", "#15803d"),
            ("2 — HAND_VISIBLE", "HAND_VISIBLE", "#b91c1c"),
            ("3 — UNCERTAIN", "UNCERTAIN", "#a16207"),
        )
        for text, value, color in action_specs:
            tk.Button(
                actions,
                text=text,
                command=lambda item=value: self.accept(item),
                font=("Segoe UI", 12, "bold"),
                bg=color,
                fg="white",
                width=20,
                pady=8,
            ).pack(side="left", padx=7)
        note_frame = tk.Frame(self.root, bg="#f4f5f7")
        note_frame.pack(fill="x", padx=12)
        tk.Label(note_frame, text="Optional note:", bg="#f4f5f7").pack(side="left")
        tk.Entry(note_frame, textvariable=self.notes).pack(
            side="left", fill="x", expand=True, padx=8
        )
        navigation = tk.Frame(self.root, bg="#f4f5f7")
        navigation.pack(pady=(7, 12))
        tk.Button(navigation, text="Previous", command=lambda: self.move(-1), width=14).pack(
            side="left", padx=6
        )
        tk.Button(navigation, text="Next", command=lambda: self.move(1), width=14).pack(
            side="left", padx=6
        )
        for key, value in zip(("1", "2", "3"), SEMANTIC_CLASSES, strict=True):
            self.root.bind(key, lambda _event, item=value: self.accept(item))
        self.root.bind("<Left>", lambda _event: self.move(-1))
        self.root.bind("<Right>", lambda _event: self.move(1))
        self.root.bind("<Control-MouseWheel>", self.mouse_zoom)
        self.refresh()

    def _render(self) -> None:
        row = self.rows[self.index]
        image = cv2.imread(row["image_path"])
        if image is None:
            raise OSError(row["image_path"])
        image = _rotate_for_display(image, self.rotation_by_review[row["review_id"]])
        canvas_width = max(self.canvas.winfo_width(), 900)
        canvas_height = max(self.canvas.winfo_height(), 560)
        fit = min(canvas_width / image.shape[1], canvas_height / image.shape[0], 2.0)
        scale = fit * self.zoom
        resized = cv2.resize(
            image,
            (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
        )
        ok, encoded = cv2.imencode(".png", resized)
        if not ok:
            raise OSError(row["image_path"])
        self.photo = self.tk.PhotoImage(data=base64.b64encode(encoded.tobytes()).decode("ascii"))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, resized.shape[1], resized.shape[0]))

    def refresh(self) -> None:
        row = self.rows[self.index]
        completed = sum(item["review_status"] == "accepted" for item in self.rows)
        self.status.set(
            f"Frame {self.index + 1}/{len(self.rows)} | accepted {completed} | "
            f"status={row['review_status']}"
        )
        self.notes.set(row["notes"])
        self.root.after_idle(self._render)

    def accept(self, semantic_class: str) -> None:
        if semantic_class not in SEMANTIC_CLASSES:
            raise ValueError(semantic_class)
        row = self.rows[self.index]
        row["semantic_class"] = semantic_class
        row["notes"] = self.notes.get().strip()
        row["review_status"] = "accepted"
        _write_csv(self.queue_path, QUEUE_FIELDS, self.rows)
        self.index = min(self.index + 1, len(self.rows) - 1)
        self.zoom = 1.0
        self.refresh()

    def move(self, delta: int) -> None:
        self.index = min(max(self.index + delta, 0), len(self.rows) - 1)
        self.zoom = 1.0
        self.refresh()

    def change_zoom(self, factor: float) -> None:
        self.zoom = min(max(self.zoom * factor, 0.5), 6.0)
        self._render()

    def reset_zoom(self) -> None:
        self.zoom = 1.0
        self._render()

    def mouse_zoom(self, event: Any) -> None:
        self.change_zoom(1.25 if event.delta > 0 else 0.8)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "review", "check", "status", "finalize"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    output = _resolve(config["output_run"])
    if args.command == "prepare":
        result = prepare(args.config)
    elif args.command == "review":
        ReviewApp(output / "review_package/review_queue.csv").run()
        return 0
    elif args.command == "finalize":
        result = finalize_review(config)
    else:
        result = check_review(config)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
