"""IPN Hand feasibility for S2-R3 hands-visible negatives (research only; no training).

Question: do IPN Hand non-gesture (NOG) intervals give AppHear what its S2 training lacks, namely
non-sign rows where Candidate01 ACCEPTS hands, from many people, and does S2-R3 fire on them the
way it fires on phone ordinary movement?

extract  Pinned Candidate01 (the S2-R2/S2-R3 offline path, unchanged) on a small set of IPN Hand
         videos, one per subject, at a 7.5 fps selection (every 4th decoded frame), so the
         133/200/267 ms S2 views can be resampled later. Raw-v1 npz per video.
analyze  Per row, the IPN HandS class at that time. HandS timeline: `ffmpeg -vf fps=30`, 1-based,
         inclusive; a decoded frame at t ms (relative to the first frame) is HandS frame
         round(t * 30 / 1000) + 1. Original Annot_List indices are never used. Rows within
         `--margin-ms` of a gesture segment are TRANSITION (excluded from NOG).
         Reports Candidate01 descriptors per class group, S2-R2 / Arm A e10 peak P(ACTIVE) per
         9-observation NOG chunk (VIEW_B, 200 ms), events per NOG minute through the reference
         lifecycle, and NOG frames for visual review.
Inputs stay under artifacts/external/ipn_hand (untracked); nothing here changes any contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402

IPN = Path("artifacts/external/ipn_hand")
ASSETS = ROOT / "android/app/src/main/assets/perception_vnext"
STEP = 4  # 30 fps -> 7.5 fps
NOG, TRANSITION = 0, -1
CHUNK = 9
WRIST, MCP = 0, 9


def hands_segments(root: Path, video: str) -> list[tuple[int, int, int]]:
    path = root / IPN / "handS_annotations/temporal_annotations" / f"{video}.txt"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c, s, e = (int(x) for x in line.split(","))
            rows.append((c, s, e))
    return rows


def row_classes(
    t_ms: np.ndarray, segments: list[tuple[int, int, int]], margin_ms: float
) -> np.ndarray:
    """HandS class per row (time-mapped); NOG rows near a gesture become TRANSITION."""
    rel = t_ms - t_ms[0]
    frame = np.round(rel * 30.0 / 1000.0).astype(int) + 1
    cls = np.full(len(t_ms), -2, int)
    for c, s, e in segments:
        cls[(frame >= s) & (frame <= e)] = c
    gesture_frames = [(s, e) for c, s, e in segments if c != 0]
    pad = margin_ms * 30.0 / 1000.0
    for i in np.flatnonzero(cls == NOG):
        if any(s - pad <= frame[i] <= e + pad for s, e in gesture_frames):
            cls[i] = TRANSITION
    return cls


def subject_of(video: str) -> str:
    return "_".join(video.split("_")[:2])


def select_videos(root: Path, available: list[str]) -> list[str]:
    """One video per subject (subject = first two name tokens, e.g. 4CM11_19), sorted."""
    by_subject: dict[str, list[str]] = defaultdict(list)
    for v in sorted(available):
        by_subject[subject_of(v)].append(v)
    return [vs[0] for _, vs in sorted(by_subject.items())]


def extract(root: Path, videos_dir: Path, limit: int | None, all_videos: bool = False) -> None:
    from eval.runtime_diagnostics import s2_r2_continuous_domain_correction as r2
    from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline
    from pipeline.perception_vnext.recognition_schema import save_raw_sequence

    out_dir = root / IPN / "raw_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {p.stem: p for p in videos_dir.rglob("*") if p.suffix.lower() in (".avi", ".mp4")}
    chosen = sorted(files) if all_videos else select_videos(root, list(files))[:limit]
    runtime = Candidate01Offline(
        ASSETS / "dwpose_t_singlepass.onnx", ASSETS / "hand_landmarks_detector.tflite"
    )
    try:
        for video in chosen:
            target = out_dir / f"{video.replace('#', '')}.npz"
            if target.exists():
                continue
            t, _, orientation = r2._video_timestamps(files[video])
            selected = np.arange(0, len(t), STEP, dtype=np.int32)
            records = r2._process_video_indices(runtime, files[video], selected, t, orientation)
            raw = r2._raw_from_records(
                f"ipn:{video}", "IPN_HAND_VIDEO", f"ipn:{subject_of(video)}", records
            )
            save_raw_sequence(target, raw)
            print(f"[ipn] {video} rows={len(records)} decoded={len(t)}", flush=True)
    finally:
        close = getattr(runtime, "close", None)
        if close:
            close()


def write_manifest(root: Path) -> dict[str, Any]:
    """Hash-pin every extracted IPN raw, its HandS annotation and source video (suite v04 input)."""
    from eval.runtime_diagnostics.s2_r3_context_suite import sha256, write_json
    from pipeline.perception_vnext.recognition_schema import load_raw_sequence

    videos = {p.stem: p for p in (root / IPN / "videos").rglob("*.avi")}
    clips = []
    for path in sorted((root / IPN / "raw_v1").glob("*.npz")):
        raw = load_raw_sequence(path)
        video = str(raw.metadata["sample_id"]).split(":", 1)[1]
        annotation = root / IPN / "handS_annotations/temporal_annotations" / f"{video}.txt"
        clips.append(
            {
                "video": video,
                "subject": subject_of(video),
                "raw_path": str(path.relative_to(root)).replace("\\", "/"),
                "raw_sha256": sha256(path),
                "observations": int(len(raw.timestamp_ms)),
                "annotation_path": str(annotation.relative_to(root)).replace("\\", "/"),
                "annotation_sha256": sha256(annotation),
                "source_video_sha256": sha256(videos[video]),
            }
        )
    manifest = {
        "schema": "apphear.ipn_hand.raw_manifest.v1",
        "source": "IPN Hand videos05.tgz (CC BY 4.0); IPN HandS temporal annotations",
        "archive_sha256": sha256(root / IPN / "download/videos05.tgz"),
        "selection": "every 4th decoded frame (7.5 fps), pinned Candidate01 offline path",
        "candidate01_assets_sha256": {
            name: sha256(ASSETS / name)
            for name in ("dwpose_t_singlepass.onnx", "hand_landmarks_detector.tflite")
        },
        "clips": clips,
    }
    write_json(root / IPN / "raw_v1/manifest.json", manifest, overwrite=True)
    return manifest


def descriptors(raw: Any, rows: np.ndarray) -> dict[str, float]:
    size = np.max(np.asarray(raw.source_size, np.float64), axis=1)
    obs = np.asarray(raw.hand_observed, bool)[rows]
    scales = []
    for i in rows:
        for side in range(2):
            if raw.hand_observed[i, side]:
                xy = np.asarray(raw.hand_xy[i, side], np.float64)
                scales.append(np.linalg.norm(xy[MCP] - xy[WRIST]) / size[i])
    return {
        "rows": int(len(rows)),
        "any_hand": float(obs.any(axis=1).mean()) if len(rows) else float("nan"),
        "both_hands": float(obs.all(axis=1).mean()) if len(rows) else float("nan"),
        "proposal": (
            float(np.asarray(raw.hand_proposal_present, bool)[rows].any(axis=1).mean())
            if len(rows)
            else float("nan")
        ),
        "body_available": (
            float(np.asarray(raw.body_available, bool)[rows].mean()) if len(rows) else float("nan")
        ),
        "hand_scale_median": float(np.median(scales)) if scales else float("nan"),
    }


def view(raw: Any, interval: float) -> np.ndarray:
    from pipeline.perception_vnext.recognition_schema import select_nearest_unique

    t = np.asarray(raw.timestamp_ms, np.float64)
    return np.asarray(select_nearest_unique(t, np.arange(t[0], t[-1], interval)), np.int32)


def analyze(
    root: Path, margin_ms: float, review_frames: int, videos_dir: Path | None
) -> dict[str, Any]:
    from eval.runtime_diagnostics import event_reliability as er
    from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import subset_raw
    from pipeline.perception_vnext.recognition_schema import load_raw_sequence

    packages = {name: er.load_s2(root, name) for name in ("S2_R2", "ARM_A_E10")}
    rows_by_group: dict[str, list[tuple[Any, np.ndarray]]] = defaultdict(list)
    peaks: dict[str, dict[str, list[float]]] = {n: defaultdict(list) for n in packages}
    events: dict[str, dict[str, float]] = {n: defaultdict(float) for n in packages}
    per_video = {}
    review: list[dict[str, Any]] = []
    for path in sorted((root / IPN / "raw_v1").glob("*.npz")):
        full = load_raw_sequence(path)
        video = str(full.metadata["sample_id"]).split(":", 1)[1]
        idx = view(full, 199.962)
        raw = subset_raw(full, idx)
        t = np.asarray(raw.timestamp_ms, np.float64)
        cls = row_classes(t, hands_segments(root, video), margin_ms)
        groups = {
            "NOG": np.flatnonzero(cls == NOG),
            "TRANSITION": np.flatnonzero(cls == TRANSITION),
            "GESTURE": np.flatnonzero(cls > 0),
        }
        for g, r in groups.items():
            rows_by_group[g].append((raw, r))
        per_video[video] = {g: descriptors(raw, r) for g, r in groups.items()}
        feats = suite.features_for_raw(raw, "v1")
        nog_blocks = (
            np.split(groups["NOG"], np.flatnonzero(np.diff(groups["NOG"]) > 1) + 1)
            if len(groups["NOG"])
            else []
        )
        for name, pkg in packages.items():
            p = pkg.probabilities(feats)
            for block in nog_blocks:
                for a in range(0, len(block), CHUNK):
                    c = block[a : a + CHUNK]
                    if len(c) >= 4:
                        hand = bool(np.asarray(raw.hand_observed, bool)[c].any())
                        peaks[name]["nog_with_hand" if hand else "nog_no_hand"].append(
                            float(p[c, 1].max())
                        )
            for e in er.replay_events(p, t, "BASELINE"):
                s, f = int(e["logical_active_start_index"]), int(e["logical_active_end_index"])
                span = cls[s : f + 1]
                key = (
                    "inside_nog"
                    if np.all(span == NOG)
                    else "touches_gesture" if np.any(span > 0) else "transition_or_mixed"
                )
                events[name][key] += 1
                if name == "ARM_A_E10" and key == "inside_nog" and len(review) < review_frames:
                    review.append(
                        {
                            "video": video,
                            "logical": [s, f],
                            "t_ms": [float(t[s] - t[0]), float(t[f] - t[0])],
                        }
                    )
            events[name]["nog_minutes"] += len(groups["NOG"]) * 0.2 / 60.0
    out: dict[str, Any] = {
        "videos": len(per_video),
        "margin_ms": margin_ms,
        "descriptors": {g: _pool(v) for g, v in rows_by_group.items()},
        "per_video": per_video,
        "nog_chunk_peaks": {
            n: {
                k: {
                    "n": len(v),
                    "fired_at_0.5": float(np.mean(np.asarray(v) >= 0.5)) if v else None,
                    "median": float(np.median(v)) if v else None,
                }
                for k, v in d.items()
            }
            for n, d in peaks.items()
        },
        "events": {
            n: {**d, "inside_nog_per_minute": d["inside_nog"] / max(1e-9, d["nog_minutes"])}
            for n, d in events.items()
        },
        "arm_a_nog_events_for_review": review,
    }
    return out


def _pool(items: list[tuple[Any, np.ndarray]]) -> dict[str, float]:
    parts = [descriptors(raw, r) for raw, r in items if len(r)]
    n = sum(p["rows"] for p in parts)
    keys = ("any_hand", "both_hands", "proposal", "body_available")
    pooled = {k: float(sum(p[k] * p["rows"] for p in parts) / max(1, n)) for k in keys}
    pooled["rows"] = n
    pooled["hand_scale_median_of_videos"] = float(
        np.nanmedian([p["hand_scale_median"] for p in parts])
    )
    return pooled


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["extract", "analyze", "manifest"])
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--videos-dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--all-videos", action="store_true")
    parser.add_argument("--margin-ms", type=float, default=500.0)
    parser.add_argument("--review", type=int, default=12)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "manifest":
        print(len(write_manifest(args.evidence_root)["clips"]), "clips")
    elif args.command == "extract":
        extract(args.evidence_root, args.videos_dir, args.limit, args.all_videos)
    else:
        result = analyze(args.evidence_root, args.margin_ms, args.review, args.videos_dir)
        text = json.dumps(result, indent=1, default=float)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        print(
            json.dumps(
                {k: result[k] for k in ("videos", "descriptors", "nog_chunk_peaks", "events")},
                indent=1,
                default=float,
            )
        )


if __name__ == "__main__":
    main()
