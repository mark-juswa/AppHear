"""RU-D7: replay identical RU-D1 phone windows through frozen B and C checkpoints.

This module never changes Android assets or model weights. The captured production-model replay
is used only as a parity gate; B and C receive the same reconstructed actual/oracle windows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics import ru_d1

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d7/phone_bc_01"
DEFAULT_QUEUE = ROOT / "context/recognition_upgrade/ru_d7_phone_bc_queue.csv"
RU_D6_RUN = ROOT / "artifacts/recognition_upgrade/ru_d6/controlled_abc_01"
DEFAULT_B = RU_D6_RUN / "models/B_ru_d3_cleanup/seed_303/best.keras"
DEFAULT_C = RU_D6_RUN / "models/C_ru_d5_semlex/seed_202/best.keras"
ASSETS = ROOT / "android/app/src/main/assets"
PRIMARY_TARGETS = ("KNOW", "WHO", "WE", "COME", "LEAVE")
PANEL = PRIMARY_TARGETS + ("HELLO", "SISTER", "KEEP", "MOVE", "PUT", "GOOD", "NOW", "HAVE")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_queue(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 26:
        raise ValueError(f"RU-D7 queue must contain 26 rows, got {len(rows)}")
    orders = [int(row["capture_order"]) for row in rows]
    if sorted(orders) != list(range(1, 27)) or len(set(orders)) != 26:
        raise ValueError("RU-D7 capture_order must be unique and contiguous 1..26")
    counts = Counter(row["gloss"] for row in rows)
    expected = Counter({gloss: 2 for gloss in PANEL})
    if counts != expected:
        raise ValueError(f"RU-D7 panel mismatch: {dict(counts)}")
    if any(row["repetition_id"] not in {"R1", "R2"} for row in rows):
        raise ValueError("RU-D7 repetitions must be R1/R2")
    return sorted(rows, key=lambda row: int(row["capture_order"]))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def model_contract(path: Path) -> dict[str, Any]:
    import tensorflow as tf

    model = tf.keras.models.load_model(path, compile=False, safe_mode=False)
    if tuple(model.input_shape) != (None, 96, 258):
        raise ValueError(f"unexpected model input for {path}: {model.input_shape}")
    output = np.asarray(model(np.zeros((1, 96, 258), np.float32), training=False))
    if output.shape != (1, 96, 236) or not np.isfinite(output).all():
        raise ValueError(f"unexpected/non-finite model output for {path}: {output.shape}")
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "input_shape": [96, 258],
        "output_shape": [96, 236],
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    rows = read_queue(args.queue)
    ru_d6 = json.loads((RU_D6_RUN / "config/experiment.json").read_text(encoding="utf-8"))
    vocab_path = Path(ru_d6["vocabulary"]["path"])
    if sha256(vocab_path) != str(ru_d6["vocabulary"]["sha256"]).upper():
        raise ValueError("RU-D6 vocabulary hash changed")
    config = {
        "experiment": "ru_d7_bounded_fresh_phone_bc_v1",
        "scope": "withheld-phone diagnostic replay only; no training or deployment",
        "session_id": args.session_id,
        "queue": {
            "path": str(args.queue.resolve()),
            "sha256": sha256(args.queue),
            "attempts": len(rows),
            "attempts_per_gloss": 2,
            "panel": list(PANEL),
        },
        "models": {
            "B_ru_d3_cleanup_seed_303": model_contract(args.b_model),
            "C_ru_d5_semlex_seed_202": model_contract(args.c_model),
        },
        "selection_basis": "best overall shared-validation checkpoints registered after RU-D6",
        "vocabulary": {"path": str(vocab_path.resolve()), "sha256": sha256(vocab_path)},
        "capture_assets": {
            name: {"path": str((ASSETS / name).resolve()), "sha256": sha256(ASSETS / name)}
            for name in (
                "streaming.tflite",
                "model_manifest.json",
                "recognition_config.json",
                "vocab.json",
            )
        },
        "schema_version": "3.0",
        "input_shape": [96, 258],
        "actual_window_definition": (
            "exact Android S6 window_source_frames with recorded order/padding/stale holds"
        ),
        "oracle_window_definition": (
            "manual onset-release plus unchanged configured pre-onset frames"
        ),
        "production_behavior_changed": False,
        "phone_rows_allowed_for_training": False,
        "protected_test_accessed": False,
        "production_authorized": False,
    }
    write_json(args.run_dir / "config/experiment.json", config)
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "session_id": args.session_id,
        "attempts": len(rows),
        "model_smoke_passed": True,
        "protected_test_accessed": False,
        "passed": True,
    }
    write_json(args.run_dir / "logs/prepare_summary.json", result)
    return result


def attempt_directories(root: Path, session_id: str) -> list[Path]:
    directories = []
    for metadata_path in root.rglob("metadata.json"):
        metadata = ru_d1.read_json(metadata_path)
        if str(metadata.get("session_id", "")) == session_id:
            directories.append(metadata_path.parent)
    return sorted(
        directories,
        key=lambda path: int(ru_d1.read_json(path / "metadata.json").get("capture_order", 0)),
    )


def annotations(args: argparse.Namespace) -> dict[str, Any]:
    config = json.loads((args.run_dir / "config/experiment.json").read_text(encoding="utf-8"))
    directories = attempt_directories(args.attempt_root, config["session_id"])
    rows = []
    for directory in directories:
        metadata = ru_d1.read_json(directory / "metadata.json")
        complete = ru_d1.read_json(directory / "capture_complete.json")
        rows.append(
            {
                "attempt_id": metadata["attempt_id"],
                "capture_order": metadata.get("capture_order", 0),
                "ground_truth": metadata["ground_truth"],
                "repetition_id": metadata.get("repetition_id", ""),
                "onset_frame": "",
                "release_frame": "",
                "performance_valid": "",
                "required_hand_visible_when_missed": "unknown",
                "evidence_first_frame": complete.get("evidence_first_frame", -1),
                "evidence_last_frame": complete.get("evidence_last_frame", -1),
                "evidence_directory": str((directory / "evidence").resolve()),
                "notes": "",
            }
        )
    if len(rows) != 26:
        raise ValueError(
            f"expected 26 captured attempts for {config['session_id']}, found {len(rows)}"
        )
    write_csv(args.output, rows)
    result = {
        "attempts": len(rows),
        "annotation_template": str(args.output.resolve()),
        "passed": True,
    }
    write_json(args.run_dir / "logs/annotation_template_summary.json", result)
    return result


class KerasSequenceRunner:
    def __init__(self, path: Path) -> None:
        import tensorflow as tf

        self.model = tf.keras.models.load_model(path, compile=False, safe_mode=False)

    def infer(self, window: np.ndarray, index: int) -> np.ndarray:
        output = np.asarray(
            self.model(window[None].astype(np.float32), training=False), dtype=np.float32
        )
        return output[0, index]


def rows_for_attempt(directory: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def actual_probabilities(
    rows: list[dict[str, Any]], runner: KerasSequenceRunner, time_window: int
) -> tuple[tuple[np.ndarray, ...], tuple[bool, ...], tuple[bool, ...]]:
    features = {int(row["frame_id"]): np.asarray(row["feature"], np.float32) for row in rows}
    probabilities, low_fps, resets = [], [], []
    for row in rows:
        s6 = row.get("s6")
        if not isinstance(s6, dict):
            continue
        window = ru_d1.reconstruct_window(s6["window_source_frames"], features, time_window)
        if ru_d1.window_sha256(window) != s6["window_sha256"]:
            raise ValueError(f"{row['attempt_id']}: actual window hash mismatch")
        probabilities.append(runner.infer(window, int(s6["inference_index"])))
        low_fps.append(bool(row["low_fps"]))
        resets.append(row["s5"]["event"] == "ONSET")
    return tuple(probabilities), tuple(low_fps), tuple(resets)


def oracle_probabilities(
    rows: list[dict[str, Any]],
    annotation: ru_d1.Annotation,
    runner: KerasSequenceRunner,
    time_window: int,
    pre_onset: int,
) -> tuple[tuple[np.ndarray, ...], tuple[bool, ...]]:
    ordered = sorted(rows, key=lambda row: int(row["frame_id"]))
    by_id = {int(row["frame_id"]): row for row in ordered}
    span = [
        frame_id
        for frame_id in sorted(by_id)
        if annotation.onset_frame <= frame_id <= annotation.release_frame
    ]
    if not span:
        raise ValueError(f"{annotation.attempt_id}: oracle span has no traced frames")
    prior = [frame_id for frame_id in sorted(by_id) if frame_id < span[0]][-pre_onset:]
    source_ids = (prior + span)[:time_window]
    probabilities, low_fps = [], []
    for index in range(len(source_ids)):
        window = np.zeros((time_window, ru_d1.FEATURE_DIM), np.float32)
        for row_index, frame_id in enumerate(source_ids[: index + 1]):
            window[row_index] = np.asarray(by_id[frame_id]["feature"], np.float32)
        probabilities.append(runner.infer(window, index))
        low_fps.append(bool(by_id[source_ids[index]]["low_fps"]))
    return tuple(probabilities), tuple(low_fps)


def prediction_row(
    probabilities: tuple[np.ndarray, ...],
    low_fps: tuple[bool, ...],
    resets: tuple[bool, ...] | None,
    ground_truth_id: int,
    vocab_by_id: dict[int, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    if not probabilities:
        return {
            "top1": "",
            "target_rank": -1,
            "top5": "",
            "top1_confidence": "",
            "target_confidence": "",
            "raw_margin": "",
            "s7_commit": "",
            "s7_commit_frame": -1,
            "s7_final_evidence": "",
            "s7_final_margin": "",
        }
    final = probabilities[-1]
    order = np.argsort(final)[::-1]
    confirmation = ru_d1.confirm(probabilities, low_fps, config, reset_before=resets)
    return {
        "top1": vocab_by_id[int(order[0])],
        "target_rank": int(np.where(order == ground_truth_id)[0][0]) + 1,
        "top5": "|".join(vocab_by_id[int(class_id)] for class_id in order[:5]),
        "top1_confidence": float(final[order[0]]),
        "target_confidence": float(final[ground_truth_id]),
        "raw_margin": float(final[order[0]] - final[order[1]]),
        "s7_commit": vocab_by_id.get(confirmation.commit_class, ""),
        "s7_commit_frame": confirmation.commit_frame,
        "s7_final_evidence": confirmation.final_evidence,
        "s7_final_margin": confirmation.final_margin,
    }


def replay(args: argparse.Namespace) -> dict[str, Any]:
    experiment = json.loads((args.run_dir / "config/experiment.json").read_text(encoding="utf-8"))
    for model in experiment["models"].values():
        if sha256(Path(model["path"])) != model["sha256"]:
            raise ValueError(f"model hash changed: {model['path']}")
    annotations_by_id = ru_d1.read_annotations(args.annotations)
    directories = attempt_directories(args.attempt_root, experiment["session_id"])
    if len(directories) != 26:
        raise ValueError(f"expected 26 attempts, found {len(directories)}")
    manifest = ru_d1.read_json(ASSETS / "model_manifest.json")
    runtime_config = ru_d1.read_json(ASSETS / "recognition_config.json")
    vocab = ru_d1.read_json(ASSETS / "vocab.json")
    id_to_gloss = {int(class_id): gloss for gloss, class_id in vocab.items()}
    production = ru_d1.TFLiteRunner(ASSETS / "streaming.tflite")
    runners = {
        name: KerasSequenceRunner(Path(item["path"])) for name, item in experiment["models"].items()
    }
    comparison_rows: list[dict[str, Any]] = []
    base_rows: list[dict[str, Any]] = []
    invalid = 0
    cross_runtime_argmax_warnings = 0
    for directory in directories:
        metadata = ru_d1.read_json(directory / "metadata.json")
        attempt_id = str(metadata["attempt_id"])
        annotation = annotations_by_id.get(attempt_id)
        base = ru_d1.analyze_attempt(
            directory, annotation, production, manifest, runtime_config, vocab, ASSETS
        )
        base_rows.append(vars(base))
        # B and C are Keras checkpoints replayed on the same host from the same exact Android
        # source-window hashes.  A production TFLite ARM-vs-x86 argmax mismatch is retained as
        # a parity warning, but it must not discard an otherwise valid B-vs-C comparison.  RU-D1
        # already established this permitted cross-runtime sensitivity; hash or S7 mismatches
        # remain fatal because those indicate evidence reconstruction/confirmation drift.
        parity_warning = bool(not base.replay_argmax_match)
        cross_runtime_argmax_warnings += int(base.attempts_valid and parity_warning)
        trusted = bool(base.attempts_valid and base.replay_hash_match and base.replay_s7_match)
        if not trusted:
            invalid += 1
            continue
        trace = rows_for_attempt(directory)
        ground_truth_id = int(vocab[base.ground_truth])
        assert annotation is not None
        for branch, runner in runners.items():
            actual_probs, actual_low, resets = actual_probabilities(
                trace, runner, int(manifest["time_window"])
            )
            oracle_probs, oracle_low = oracle_probabilities(
                trace,
                annotation,
                runner,
                int(manifest["time_window"]),
                int(runtime_config.get("pre_onset", {}).get("frames", 0)),
            )
            for span_type, probabilities, low_fps, reset_flags in (
                ("ACTUAL_RUNTIME_WINDOW", actual_probs, actual_low, resets),
                ("ORACLE_MANUAL_SPAN", oracle_probs, oracle_low, None),
            ):
                item = prediction_row(
                    probabilities,
                    low_fps,
                    reset_flags,
                    ground_truth_id,
                    id_to_gloss,
                    runtime_config,
                )
                comparison_rows.append(
                    {
                        "attempt_id": attempt_id,
                        "capture_order": base.capture_order,
                        "ground_truth": base.ground_truth,
                        "repetition_id": base.repetition_id,
                        "branch": branch,
                        "span_type": span_type,
                        "trusted_attempt": True,
                        "upstream_diagnostic": base.primary_failure,
                        "cross_runtime_argmax_warning": parity_warning,
                        "recorded_runtime_top1": base.actual_top1,
                        "recorded_runtime_commit": base.final_output,
                        "hand_coverage": base.hand_coverage,
                        "two_hand_coverage": base.two_hand_coverage,
                        "pose_coverage": base.pose_coverage,
                        "s5_onset_frame": base.s5_onset_frame,
                        "s5_release_frame": base.s5_release_frame,
                        **item,
                    }
                )
    if not comparison_rows:
        raise ValueError("no trusted phone attempts available for B/C replay")
    write_csv(args.run_dir / "reports/ru_d7_attempt_bc.csv", comparison_rows)
    write_csv(args.run_dir / "reports/ru_d7_capture_diagnostics.csv", base_rows)
    summary_rows = []
    for gloss in PANEL:
        for branch in experiment["models"]:
            for span_type in ("ACTUAL_RUNTIME_WINDOW", "ORACLE_MANUAL_SPAN"):
                rows = [
                    row
                    for row in comparison_rows
                    if row["ground_truth"] == gloss
                    and row["branch"] == branch
                    and row["span_type"] == span_type
                ]
                ranked_rows = [row for row in rows if int(row["target_rank"]) > 0]
                summary_rows.append(
                    {
                        "gloss": gloss,
                        "branch": branch,
                        "span_type": span_type,
                        "trusted_attempts": len(rows),
                        "prediction_windows": len(ranked_rows),
                        "top1_correct": sum(row["top1"] == gloss for row in rows),
                        "s7_target_commits": sum(
                            row["s7_commit"] == gloss for row in rows
                        ),
                        "mean_target_rank": (
                            float(np.mean([row["target_rank"] for row in ranked_rows]))
                            if ranked_rows
                            else ""
                        ),
                        "predicted_as_who": sum(row["top1"] == "WHO" for row in rows),
                    }
                )
    write_csv(args.run_dir / "reports/ru_d7_class_summary.csv", summary_rows)
    report = {
        "experiment": experiment["experiment"],
        "session_id": experiment["session_id"],
        "captured_attempts": len(directories),
        "trusted_attempts": len(directories) - invalid,
        "rejected_attempts": invalid,
        "cross_runtime_argmax_warnings": cross_runtime_argmax_warnings,
        "comparison_rows": len(comparison_rows),
        "outcome": "REQUIRES_CONSOLIDATED_EVIDENCE_REVIEW",
        "come_stop_rule": (
            "If both B and C remain poor with oracle spans, close Sem-Lex COME repair."
        ),
        "production_authorized": False,
        "phone_rows_allowed_for_training": False,
        "protected_test_accessed": False,
        "passed": True,
    }
    write_json(args.run_dir / "reports/ru_d7_phone_bc_report.json", report)
    return report


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors = []
    config_path = args.run_dir / "config/experiment.json"
    if not config_path.is_file():
        errors.append("missing experiment config")
    else:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        try:
            if sha256(Path(config["queue"]["path"])) != config["queue"]["sha256"]:
                errors.append("queue hash changed")
            for model in config["models"].values():
                if sha256(Path(model["path"])) != model["sha256"]:
                    errors.append(f"model hash changed: {model['path']}")
        except (KeyError, FileNotFoundError) as exc:
            errors.append(str(exc))
        if config.get("protected_test_accessed") or config.get("production_authorized"):
            errors.append("safety policy changed")
    if args.require_results:
        for name in (
            "ru_d7_attempt_bc.csv",
            "ru_d7_class_summary.csv",
            "ru_d7_phone_bc_report.json",
        ):
            if not (args.run_dir / "reports" / name).is_file():
                errors.append(f"missing result: {name}")
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "errors": errors,
        "protected_test_accessed": False,
        "passed": not errors,
    }
    write_json(args.run_dir / "logs/check_report.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    prep.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    prep.add_argument("--b-model", type=Path, default=DEFAULT_B)
    prep.add_argument("--c-model", type=Path, default=DEFAULT_C)
    prep.add_argument("--session-id", default="ru_d7_phone_bc_01")
    annotate = commands.add_parser("annotations")
    annotate.add_argument("attempt_root", type=Path)
    annotate.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    annotate.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("replay")
    run.add_argument("attempt_root", type=Path)
    run.add_argument("annotations", type=Path)
    run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    verify = commands.add_parser("check")
    verify.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    verify.add_argument("--require-results", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    result = {"prepare": prepare, "annotations": annotations, "replay": replay, "check": check}[
        args.command
    ](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
