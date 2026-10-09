"""Reproduce the bounded v13 TRAIN manifest from pinned local metadata only."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

SCHEMA = "apphear.fsboard.admission_download_manifest.v1"
NAME = "fsboard_candidate01_admission_download_manifest"
REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO / "datasets/fingerspelling/fsboard_candidate01_admission_20261002"


def repeated_pairs(phrase: str) -> list[str]:
    return sorted({a + b for a, b in zip(phrase, phrase[1:], strict=False) if a == b and a != " "})


def source_path(group: str, filename: str) -> str:
    return f"{group}/video_clips/{group}-train/{filename}"


def sample_id(relative_path: str) -> str:
    digest = hashlib.sha256(f"googleai/fsboard\nv13\n{relative_path}".encode()).hexdigest()
    return f"fsboard-v13-train-{digest[:20]}"


def download_url(relative_path: str) -> str:
    return (
        "https://www.kaggle.com/api/v1/datasets/download/googleai/fsboard/"
        + quote(relative_path, safe="")
        + "?datasetVersionNumber=13"
    )


def duration(row: dict[str, Any]) -> float:
    return float(row["clipEndTimeS"] - row["clipStartTimeS"])


def matches_tag(row: dict[str, Any], tag: str) -> bool:
    phrase = row["phrase"].upper()
    if tag == "NO_J_Z_REPEAT":
        return "J" not in phrase and "Z" not in phrase and not repeated_pairs(phrase)
    return tag in phrase


def select(
    policy: dict[str, Any], repo: Path = REPO
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Only the two explicit TRAIN JSONs are opened; no payload/DEV/TEST glob."""
    groups: dict[str, list[dict[str, Any]]] = {}
    metadata = []
    for spec in policy["metadata"]:
        path = repo / spec["path"]
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != spec["sha256"]:
            raise ValueError(f"[fsboard/selection] Metadata hash mismatch: {path}")
        all_rows = json.loads(content)
        rows = [
            r
            for r in all_rows
            if re.fullmatch(r"[A-Za-z ]+", r["phrase"]) and re.search(r"[A-Za-z]", r["phrase"])
        ]
        groups[spec["group"]] = rows
        metadata.append(
            dict(spec, bytes=len(content), records=len(all_rows), alphabet_space_records=len(rows))
        )
    excluded = set(policy["previously_downloaded_clips_excluded"])
    used_signers: set[str] = set()
    used_full: set[tuple[str, str, str]] = set()
    used_phrases: set[str] = set()
    used_md5: set[str] = set()
    selected = []
    for index, slot in enumerate(policy["slots"], 1):
        group = slot["group"]
        band = [
            r for r in groups[group] if slot["min_chars"] <= len(r["phrase"]) <= slot["max_chars"]
        ]
        values = sorted(duration(r) for r in band)
        q = policy["duration_quantiles"][slot["duration_tail"]]
        threshold = values[round((len(values) - 1) * q)]
        candidates = [
            r
            for r in band
            if matches_tag(r, slot["tag"])
            and r["clipFilename"] not in excluded
            and (
                duration(r) <= threshold
                if slot["duration_tail"] == "lower"
                else duration(r) >= threshold
            )
        ]
        candidates.sort(
            key=lambda r: (
                hashlib.sha256(
                    (
                        policy["ordering_salt"] + "\n" + source_path(group, r["clipFilename"])
                    ).encode()
                ).hexdigest(),
                source_path(group, r["clipFilename"]),
            )
        )
        independent = [
            r
            for r in candidates
            if r["signerId"] not in used_signers
            and (r["collectionId"], r["signerId"], r["fullVideoFilename"]) not in used_full
            and r["phrase"].upper() not in used_phrases
            and r["clipFileMd5"] not in used_md5
        ]
        if not independent:
            raise ValueError(
                f"[fsboard/selection] No independent candidate for slot {index}: {slot}"
            )
        row = independent[0]
        phrase = row["phrase"].upper()
        relative = source_path(group, row["clipFilename"])
        spec = next(s for s in policy["metadata"] if s["group"] == group)
        pairs = repeated_pairs(phrase)
        selected.append(
            {
                "selection_index": index,
                "sample_id": sample_id(relative),
                "fsboard_version": policy["dataset_version"],
                "source_stratum": spec["stratum"],
                "source_group": group,
                "official_split": "train",
                "signer_id": row["signerId"],
                "collection_id": row["collectionId"],
                "official_session_id": None,
                "full_video_provenance_key": (
                    f'{row["collectionId"]}:{row["signerId"]}:' f'{row["fullVideoFilename"]}'
                ),
                "phrase": row["phrase"],
                "normalized_phrase": phrase,
                "clip_filename": row["clipFilename"],
                "kaggle_relative_path": relative,
                "download_relative_path": row["clipFilename"],
                "direct_download_url": download_url(relative),
                "full_video_filename": row["fullVideoFilename"],
                "full_video_first_pts_time_s": row["fullVideoFirstPtsTimeS"],
                "annotation_start_time_s": row["annotationStartTimeS"],
                "annotation_end_time_s": row["annotationEndTimeS"],
                "clip_start_time_s": row["clipStartTimeS"],
                "clip_end_time_s": row["clipEndTimeS"],
                "source_duration_metadata_s": duration(row),
                "file_size_bytes": row["clipFileSize"],
                "official_md5": row["clipFileMd5"],
                "clip_start_packet_md5": row["clipStartPacketMd5"],
                "clip_end_packet_md5": row["clipEndPacketMd5"],
                "clip_creation_time": row["clipCreationTime"],
                "sensitive_content": row.get("sensitiveContent"),
                "j_present": "yes" if "J" in phrase else "no",
                "z_present": "yes" if "Z" in phrase else "no",
                "repeated_letter_present": "yes" if pairs else "no",
                "repeated_letter_examples": ";".join(pairs),
                "transcript_length": len(phrase),
                "letter_count": sum(c != " " for c in phrase),
                "length_band": slot["length_band"],
                "duration_tail": slot["duration_tail"],
                "duration_quantile_threshold_s": threshold,
                "selection_category": slot["tag"],
                "selection_reason": (
                    f'{spec["stratum"]}; {slot["length_band"]} '
                    f'({slot["min_chars"]}-{slot["max_chars"]} characters including spaces); '
                    f'{slot["duration_tail"]}-duration quartile within band; '
                    f'{slot["tag"]}; distinct TRAIN signer'
                ),
                "eligible_candidates_before_diversity": len(candidates),
                "eligible_candidates_after_diversity": len(independent),
                "source_width": None,
                "source_height": None,
                "source_fps": None,
                "source_orientation": None,
                "saved_pixel_reflection": None,
                "official_metadata": row,
            }
        )
        used_signers.add(row["signerId"])
        used_full.add((row["collectionId"], row["signerId"], row["fullVideoFilename"]))
        used_phrases.add(phrase)
        used_md5.add(row["clipFileMd5"])
    return selected, metadata


def write_package(output: Path, policy_path: Path) -> dict[str, Any]:
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes)
    rows, metadata = select(policy)
    summary = {
        "file_count": len(rows),
        "expected_bytes": sum(r["file_size_bytes"] for r in rows),
        "official_train_signer_count": len({r["signer_id"] for r in rows}),
        "stratum_counts": dict(collections.Counter(r["source_stratum"] for r in rows)),
        "collection_ids": dict(collections.Counter(r["collection_id"] for r in rows)),
        "j_sequences": sum(r["j_present"] == "yes" for r in rows),
        "z_sequences": sum(r["z_present"] == "yes" for r in rows),
        "repeated_sequences": sum(r["repeated_letter_present"] == "yes" for r in rows),
        "repeat_pair_sequence_counts": {
            pair: sum(pair in r["repeated_letter_examples"].split(";") for r in rows)
            for pair in ("LL", "MM", "EE")
        },
        "no_j_z_repeat_sequences": sum(
            r["j_present"] == r["z_present"] == r["repeated_letter_present"] == "no" for r in rows
        ),
        "transcript_length_range": [
            min(r["transcript_length"] for r in rows),
            max(r["transcript_length"] for r in rows),
        ],
        "duration_metadata_range_s": [
            min(r["source_duration_metadata_s"] for r in rows),
            max(r["source_duration_metadata_s"] for r in rows),
        ],
        "total_duration_metadata_s": sum(r["source_duration_metadata_s"] for r in rows),
    }
    manifest = {
        "schema_version": SCHEMA,
        "dataset": "googleai/fsboard",
        "dataset_version": 13,
        "purpose": (
            "TRAIN-only Candidate01 training-admission diagnostic download inventory; NOT_ADMITTED"
        ),
        "download_destination": (DEFAULT_OUTPUT / "videos").as_posix(),
        "selection_policy_path": policy_path.relative_to(REPO).as_posix(),
        "selection_policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "selection_policy": policy,
        "metadata_sources": metadata,
        "summary": summary,
        "unknowns": [
            "Resolution/FPS/rotation/reflection are not supplied in these JSONs",
            "No official session ID; full-video key is provenance, "
            "not a confirmed physical session",
            "Metadata duration is clipEndTimeS minus clipStartTimeS, not decoded duration",
            "No per-letter boundaries or perception quality is inferred",
        ],
        "samples": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{NAME}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    fields = [key for key in rows[0] if key != "official_metadata"]
    with (output / f"{NAME}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: row[k] for k in fields} for row in rows)
    lines = [
        "# FSboard v13 manual download sheet",
        "",
        f'**{len(rows)} MP4s; {summary["expected_bytes"]:,} bytes '
        f'({summary["expected_bytes"] / 1_000_000:.2f} MB / '
        f'{summary["expected_bytes"] / 2**20:.2f} MiB).**',
        "",
        "Save the original, unchanged MP4s with their exact filenames directly in:",
        "",
        f'`{manifest["download_destination"]}/`',
        "",
        "Do not place manifests, ZIPs, renamed browser copies, or earlier diagnostic clips "
        "in this dedicated videos directory.",
        "",
        "Each link is deterministically constructed from the per-file v13 API pattern verified "
        "in the earlier gate. No link was invoked in this preparation. If Kaggle requests "
        "sign-in, sign in through your browser; if the response is HTML/a ZIP rather than "
        "the original MP4, do not rename it to .mp4. Use the official dataset file browser "
        "and check version 13. Do not select Download all.",
        "",
        "| # | Transcript | Exact filename | Bytes | MD5 |",
        "|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f'| {row["selection_index"]} | {row["phrase"]} | '
            f'[{row["clip_filename"]}]({row["direct_download_url"]}) | '
            f'{row["file_size_bytes"]:,} | `{row["official_md5"]}` |'
        )
    lines += [
        "",
        "Exact Kaggle relative paths:",
        "",
        "```text",
        *(r["kaggle_relative_path"] for r in rows),
        "```",
        "",
        "After downloading, run the offline checker from the AppHear repository:",
        "",
        "```powershell",
        ".venv/Scripts/python.exe tools/fsboard_admission/verify_downloads.py --manifest "
        '"datasets/fingerspelling/fsboard_candidate01_admission_20261002/'
        'fsboard_candidate01_admission_download_manifest.json" --sha256 --report '
        '"datasets/fingerspelling/fsboard_candidate01_admission_20261002/'
        'download-integrity-result.json"',
        "```",
        "",
        "`--videos-dir` can override the destination if necessary. Exit 0 means every selected "
        "file and identity check passed. This checks bytes/hashes only, not MP4 decode, "
        "reflection, transcript quality or training admission. Tell the assistant explicitly "
        "when the files are ready; extraction requires that next authorization.",
    ]
    (output / "DOWNLOAD_SHEET.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / ".gitignore").write_text("videos/\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(
        json.dumps(
            write_package(args.output, Path(__file__).with_name("selection_policy.json")), indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
