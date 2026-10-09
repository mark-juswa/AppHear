"""Validate AZ intake and report AZ-2 blockers without opening protected payloads.

Run with the project Python: -m pipeline.fingerspelling.validate PACKAGE [--stage az2].
No extraction, label inference, split assignment, training, or runtime imports occur here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import string
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypeGuard

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "pipeline/config/fingerspelling_dataset_v1.json"
CLASS_ORDER = list(string.ascii_uppercase) + ["OTHER"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_hash(value: Any) -> TypeGuard[str]:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in string.hexdigits for char in value)
    )


def path_key(path: Path) -> str:
    return path.resolve().as_posix().casefold()


def valid_text(value: Any) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())


def finite_number(value: Any) -> TypeGuard[int | float]:
    return type(value) in (int, float) and math.isfinite(value)


class Audit:
    """One explicitly named package; never discover datasets or protected videos."""

    def __init__(self, package_path: Path, policy: dict[str, Any]) -> None:
        self.path = package_path.resolve()
        self.base = self.path.parent
        self.policy = policy
        self.errors: list[str] = []
        self.blockers: list[str] = []
        self.not_opened: list[str] = []
        self.raw_stats: dict[str, Any] = {}

    def error(self, context: str, message: str) -> None:
        self.errors.append(f"{context}: {message}")

    def block(self, message: str) -> None:
        self.blockers.append(message)

    def resolve(self, value: Any) -> Path | None:
        if not valid_text(value):
            return None
        path = Path(value)
        return (path if path.is_absolute() else self.base / path).resolve()

    def denied(self, path: Path) -> bool:
        # Check both lexical and resolved paths before stat/hash/load, including linked roots.
        return any(
            fragment.casefold() in text
            for fragment in self.policy["denied_path_fragments"]
            for text in (path.as_posix().casefold(), path_key(path))
        )

    def checked_file(self, ref: Any, context: str, *, metadata: bool = False) -> Path | None:
        if not isinstance(ref, dict):
            self.error(context, "missing file reference")
            return None
        path = self.resolve(ref.get("path"))
        if path is None or not is_hash(ref.get("sha256")):
            self.error(context, "path and SHA-256 are required")
            return None
        if self.denied(path):
            self.error(context, "protected/historical source denied before payload read")
            return None
        if metadata and not path.is_relative_to(self.base / "evidence"):
            self.error(context, "review evidence must be under package evidence/")
            return None
        if not path.is_file():
            self.error(context, f"missing file {path}")
            return None
        if sha256(path) != ref["sha256"].lower():
            self.error(context, "SHA-256 mismatch")
            return None
        return path

    def records(self, data: dict[str, Any], key: str) -> list[dict[str, Any]]:
        value = data.get(key)
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            self.error(key, "expected a list of objects")
            return []
        return value

    def index(self, rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            identity = row.get(key)
            if not valid_text(identity):
                self.error(key, "missing identity")
            elif identity in result:
                self.error(key, f"duplicate identity {identity}")
            else:
                result[identity] = row
        return result

    def annotation(self, sample: dict[str, Any], duration: Any) -> list[dict[str, Any]]:
        identity = sample.get("sample_id", "sample")
        annotation = sample.get("annotation", {})
        if not isinstance(annotation, dict):
            self.error(identity, "annotation must be an object")
            return []
        status = annotation.get("state")
        if status not in ("PENDING", "REVIEWED", "QUARANTINED"):
            self.error(identity, "invalid annotation state")
        transcript = annotation.get("verified_transcript")
        if transcript is not None and (
            not isinstance(transcript, str)
            or any(letter not in string.ascii_uppercase for letter in transcript)
        ):
            self.error(
                identity, "verified transcript must contain A-Z only; OTHER uses empty string"
            )
        quality = annotation.get("observation_quality")
        if (
            not isinstance(quality, list)
            or not quality
            or any(tag not in self.policy["quality_tags"] for tag in quality)
        ):
            self.error(identity, "missing/invalid observation quality")
        if status == "REVIEWED" and (
            not valid_text(annotation.get("annotator_id"))
            or not valid_text(annotation.get("reviewer_id"))
            or annotation.get("annotator_id") == annotation.get("reviewer_id")
            or transcript is None
            or annotation.get("video_reviewed") is not True
        ):
            self.error(
                identity, "review needs independent identities, video review, verified transcript"
            )
        segments = annotation.get("segments", [])
        if not isinstance(segments, list):
            self.error(identity, "segments must be a list")
            return []
        last_end = -math.inf
        letter_indices: list[int] = []
        approved: list[dict[str, Any]] = []
        for segment in segments:
            if not isinstance(segment, dict):
                self.error(identity, "segment must be an object")
                continue
            start, end = segment.get("start_ms"), segment.get("end_ms")
            target = segment.get("model_target")
            if target not in CLASS_ORDER:
                self.error(identity, "invalid model target/class order")
                continue
            if (
                not finite_number(start)
                or not finite_number(end)
                or not finite_number(duration)
                or not 0 <= start < end <= duration
                or start < last_end
            ):
                self.error(
                    identity, "segments must be ordered, non-overlapping, within source duration"
                )
                continue
            last_end = end
            uncertainty = segment.get("boundary_uncertainty_ms")
            if not finite_number(uncertainty) or uncertainty < 0:
                self.error(identity, "missing/non-finite boundary uncertainty")
            if target == "OTHER":
                if (
                    segment.get("letter_index") is not None
                    or segment.get("other_subtype") not in self.policy["other_subtypes"]
                    or not valid_text(segment.get("non_letter_reason"))
                ):
                    self.error(
                        identity, "OTHER needs non-letter review reason/subtype; no letter index"
                    )
            else:
                index = segment.get("letter_index")
                if (
                    type(index) is not int
                    or not isinstance(transcript, str)
                    or index < 0
                    or index >= len(transcript)
                    or transcript[index] != target
                ):
                    self.error(
                        identity, "letter target must match reviewed transcript at letter_index"
                    )
                else:
                    letter_indices.append(index)
                if segment.get("other_subtype") is not None:
                    self.error(identity, "letter cannot have an OTHER subtype")
                if target in ("J", "Z") and segment.get("motion_confirmed") is not True:
                    self.block(f"{identity}: moving {target} lacks full-motion review")
            approved.append(segment)
        if status == "REVIEWED" and isinstance(transcript, str):
            if letter_indices != list(range(len(transcript))):
                self.error(
                    identity, "each reviewed letter occurrence needs its own ordered segment"
                )
            if not segments:
                self.error(identity, "reviewed sample needs at least one target segment")
        if sample.get("training_use") == "QUARANTINE":
            return []
        if status != "REVIEWED":
            self.block(f"{identity}: annotation/use unresolved or quarantined")
            return []
        return approved

    def raw_lineage(self, sample: dict[str, Any], protected: bool) -> None:
        identity = sample["sample_id"]
        extraction = sample.get("extraction")
        if not isinstance(extraction, dict):
            self.block(f"{identity}: missing Candidate01 observation/receipt lineage")
            return
        for key in ("raw", "receipt"):
            ref = extraction.get(key)
            if not isinstance(ref, dict) or not is_hash(ref.get("sha256")):
                self.error(identity, f"missing {key} hash/reference")
                return
            path = self.resolve(ref.get("path"))
            if path is None or self.denied(path):
                self.error(identity, f"invalid/denied {key} path")
                return
        if protected:
            self.not_opened.append(f"{identity}: raw/receipt protected payloads")
            return
        receipt_path = self.checked_file(extraction["receipt"], f"{identity}/receipt")
        raw_path = self.checked_file(extraction["raw"], f"{identity}/raw")
        if receipt_path is None or raw_path is None:
            return
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
            expected = {
                "schema_version": self.policy["observation_receipt_version"],
                "raw_schema": self.policy["raw_schema"],
                "image_semantics": self.policy["image_semantics"],
                "candidate_id": self.policy["candidate_id"],
                "candidate01_assets": self.policy["candidate01_assets"],
                "sample_id": identity,
                "signer_id": sample["signer_id"],
                "split_role": sample["split_role"],
                "source_sha256": sample["source"]["sha256"].lower(),
                "raw_sha256": extraction["raw"]["sha256"].lower(),
                "whole_source_video": True,
            }
            for key, value in expected.items():
                if receipt.get(key) != value:
                    self.error(identity, f"receipt {key} mismatch")
            for key in (
                "extraction_version",
                "code_revision",
                "decoder_version",
                "timestamp_policy",
            ):
                if not valid_text(receipt.get(key)):
                    self.error(identity, f"receipt missing {key}")
            code = receipt.get("preprocessing_source_sha256")
            required_code = (
                "pipeline/perception_vnext/offline_candidate01.py",
                "pipeline/perception_vnext/hand_roi.py",
                "pipeline/perception_vnext/hand_refiner.py",
                "pipeline/perception_vnext/recognition_schema.py",
            )
            if not isinstance(code, dict) or any(
                code.get(path) != sha256(ROOT / path) for path in required_code
            ):
                self.error(identity, "preprocessing source identities missing/drifted")
            # Lazy reuse of the canonical raw reader; never run Candidate01 or feature builders.
            import numpy as np

            from pipeline.perception_vnext.recognition_schema import (
                HAND_PRESENCE_THRESHOLD,
                MINIMUM_REFINED_VALID_POINTS,
                body_point_valid,
                load_raw_sequence,
            )

            raw = load_raw_sequence(raw_path)
            metadata = raw.metadata
            for key, value in (
                ("sample_id", identity),
                ("signer_id", sample["signer_id"]),
                ("split", sample["split_role"]),
                ("candidate_id", self.policy["candidate_id"]),
                ("source_video_sha256", sample["source"]["sha256"].lower()),
                ("current_frame_only", True),
                ("carry_forward", False),
                ("synthetic_depth", False),
            ):
                if metadata.get(key) != value:
                    self.error(identity, f"raw metadata {key} mismatch")
            if not metadata.get("timestamp_sources") or metadata.get("span_sha256") is not None:
                self.error(identity, "raw needs timestamp provenance and whole-source extraction")
            if (
                not np.all(np.isfinite(raw.timestamp_ms))
                or raw.timestamp_ms[0] < 0
                or not np.all(raw.source_size > 0)
                or raw.frame_index[0] != 0
                or not np.all(np.diff(raw.frame_index) == 1)
            ):
                self.error(identity, "raw timing/dimensions/full-frame lineage invalid")
            for key in (
                "hand_joint_valid",
                "hand_observed",
                "hand_proposal_present",
                "body_valid",
                "body_available",
            ):
                if getattr(raw, key).dtype != np.dtype(bool):
                    self.error(identity, f"{key} must be an explicit boolean mask")
            observed_supported = (
                raw.hand_proposal_present
                & np.isfinite(raw.hand_presence)
                & (raw.hand_presence >= HAND_PRESENCE_THRESHOLD)
                & (raw.hand_joint_valid.sum(axis=-1) >= MINIMUM_REFINED_VALID_POINTS)
                & np.all(np.isfinite(raw.hand_roi_center_side), axis=-1)
                & (raw.hand_roi_center_side[..., 2] > 0)
            )
            if np.any(raw.hand_observed & ~observed_supported):
                self.error(
                    identity, "observed hand lacks Candidate01 proposal/presence/joint/ROI support"
                )
            for index, (width, height) in enumerate(raw.source_size):
                expected_valid = body_point_valid(
                    raw.body_xy[index], raw.body_support[index], int(width), int(height)
                )
                if not np.array_equal(raw.body_valid[index], expected_valid):
                    self.error(identity, "body masks disagree with Candidate01 current-frame rules")
                    break
            body_minimum = self.policy["candidate01_body_available_minimum_valid_points"]
            if np.any(raw.body_available != (raw.body_valid.sum(axis=-1) >= body_minimum)):
                self.error(identity, "body availability disagrees with Candidate01 masks")
            if receipt.get("frame_count") != len(raw.frame_index):
                self.error(identity, "receipt frame count mismatch")
            timing = [float(raw.timestamp_ms[0]), float(raw.timestamp_ms[-1])]
            if receipt.get("timestamp_range_ms") != timing:
                self.error(identity, "receipt timestamp range mismatch")
            observed_frames = int(np.count_nonzero(np.any(raw.hand_observed, axis=-1)))
            deltas = np.diff(raw.timestamp_ms)
            self.raw_stats[identity] = {
                "frames": len(raw.frame_index),
                "frames_with_any_observed_hand": observed_frames,
                "frames_with_body_available": int(np.count_nonzero(raw.body_available)),
                "timestamp_sources": metadata.get("timestamp_sources"),
                "delta_ms_min": float(deltas.min()) if len(deltas) else None,
                "delta_ms_max": float(deltas.max()) if len(deltas) else None,
            }
            annotation = sample.get("annotation", {})
            if (
                sample.get("training_use") == "INCLUDE"
                and isinstance(annotation, dict)
                and annotation.get("verified_transcript")
                and not observed_frames
            ):
                self.block(f"{identity}: no observed hand; retain letter target; review/quarantine")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self.error(identity, f"invalid raw/receipt package: {type(exc).__name__}: {exc}")

    def run(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            self.error("package", str(exc))
            return self.report({})
        if not isinstance(data, dict):
            self.error("package", "expected an object")
            return self.report({})
        if data.get("schema_version") != self.policy["schema_version"]:
            self.error("package", "schema_version mismatch")
        if data.get("class_order") != CLASS_ORDER or self.policy["class_order"] != CLASS_ORDER:
            self.error("package", "class order must be A-Z, then OTHER")
        if not valid_text(data.get("dataset_id")) or type(data.get("fixture")) is not bool:
            self.error("package", "dataset_id and explicit fixture boolean required")
        if data.get("fixture") is True:
            self.block("Synthetic fixture cannot establish real AZ-2 readiness")
        signers = self.index(self.records(data, "signers"), "signer_id")
        sessions = self.index(self.records(data, "sessions"), "session_id")
        samples = self.index(self.records(data, "samples"), "sample_id")
        roots = self.records(data, "source_roots")
        people: dict[str, str] = {}
        aliases: dict[str, str] = {}
        for identity, person in signers.items():
            key = person.get("person_key")
            if not valid_text(key) or key in people:
                self.error(
                    identity, "missing/duplicate human person_key (aliases are not extra people)"
                )
            else:
                people[key] = identity
            if person.get("split_role") not in self.policy["roles"]:
                self.error(identity, "invalid signer split role")
            alias_list = person.get("aliases")
            if (
                not isinstance(alias_list, list)
                or not alias_list
                or any(not valid_text(alias) for alias in alias_list)
            ):
                self.error(identity, "source-namespaced signer aliases required")
                alias_list = []
            for alias in alias_list:
                normalized = alias.casefold()
                if normalized in aliases:
                    self.error(identity, "signer alias repeated across roster")
                aliases[normalized] = identity
            if (
                person.get("identity_review") != "RESOLVED"
                or not valid_text(person.get("identity_evidence_ref"))
                or person.get("rights") != "APPROVED"
                or not valid_text(person.get("consent_or_license_ref"))
                or person.get("historical_role_review") != "CLEARED"
            ):
                self.block(f"{identity}: identity/consent/historical exposure unresolved")
            if person.get("word_role") not in ("NONE", "TRAIN", "DEV", "PROTECTED"):
                self.error(identity, "word_role must be explicit, UNKNOWN is quarantined")
            elif person.get("word_role") == "PROTECTED":
                self.error(identity, "protected word/phone human cannot enter AZ development")
            elif (
                person.get("word_role") in ("TRAIN", "DEV") and person.get("split_role") != "TRAIN"
            ):
                self.error(
                    identity, "historically development-exposed human cannot be unseen AZ eval"
                )
            if (
                person.get("split_role") != "TRAIN"
                and person.get("perception_exposure") != "UNEXPOSED"
            ):
                self.block(f"{identity}: upstream perception exposure prevents unseen-signer claim")
        session_keys: set[tuple[str, str]] = set()
        for identity, session in sessions.items():
            signer = session.get("signer_id")
            if signer not in signers:
                self.error(identity, "session has unknown signer")
            if not valid_text(session.get("device_id")) or not valid_text(
                session.get("session_key")
            ):
                self.error(identity, "device_id/stable session_key required")
            for key in ("capture_conditions", "camera"):
                if not isinstance(session.get(key), dict):
                    self.error(identity, f"{key} object required (unknown values may be null)")
            camera = session.get("camera", {})
            if isinstance(camera, dict) and (
                camera.get("lens") != "front" or camera.get("saved_video_mirrored") is not False
            ):
                self.block(f"{identity}: front-camera/unmirrored saved-video semantics unverified")
            key = (str(session.get("device_id")), str(session.get("session_key")))
            if key in session_keys:
                self.error(identity, "duplicate device/session key is not a second session")
            session_keys.add(key)
        hashes: dict[str, str] = {}
        counts: Counter[tuple[str, str, str]] = Counter()
        sequence_counts: Counter[str] = Counter()
        repeated: dict[tuple[str, str], set[str]] = defaultdict(set)
        transitions: dict[tuple[str, str], set[str]] = defaultdict(set)
        word_sequences: set[str] = set()
        used_sessions: dict[str, set[str]] = defaultdict(set)
        letter_sessions: dict[tuple[str, str], set[str]] = defaultdict(set)
        other: dict[tuple[str, str], set[str]] = defaultdict(set)
        quality_counts: Counter[str] = Counter()
        for identity, sample in samples.items():
            signer, role = sample.get("signer_id"), sample.get("split_role")
            session = sessions.get(str(sample.get("session_id")), {})
            if (
                not valid_text(signer)
                or signer not in signers
                or session.get("signer_id") != signer
            ):
                self.error(identity, "missing/mismatched signer/session identity")
                continue
            if (
                not valid_text(role)
                or role not in self.policy["roles"]
                or role != signers[signer].get("split_role")
            ):
                self.error(identity, "signer leakage or invalid sample role")
                continue
            person = signers[signer]
            if person.get("word_role") not in ("NONE", "TRAIN", "DEV"):
                self.error(identity, "unresolved/protected human source; payload not read")
                continue
            if any(
                person.get(key) != expected
                for key, expected in (
                    ("identity_review", "RESOLVED"),
                    ("rights", "APPROVED"),
                    ("historical_role_review", "CLEARED"),
                )
            ):
                self.block(f"{identity}: unresolved identity/rights; payload not read")
                continue
            alias = sample.get("source_signer_alias")
            if not valid_text(alias) or aliases.get(alias.casefold()) != signer:
                self.error(identity, "source signer alias not reconciled to this human")
                continue
            if sample.get("training_use") not in ("INCLUDE", "QUARANTINE"):
                self.error(identity, "training_use must be INCLUDE or QUARANTINE")
            if sample.get("kind") not in ("ISOLATED", "SEQUENCE", "NEGATIVE"):
                self.error(identity, "invalid sample kind")
            if not valid_text(sample.get("intended")) or not valid_text(sample.get("prompt_id")):
                self.error(identity, "intended content and repeatable prompt_id required")
            if type(sample.get("attempt_index")) is not int or sample["attempt_index"] < 1:
                self.error(identity, "attempt_index must be a positive integer")
            source = sample.get("source")
            if not isinstance(source, dict):
                self.error(identity, "missing source")
                continue
            source_path = self.resolve(source.get("path"))
            source_hash = source.get("sha256")
            if source_path is None or not is_hash(source_hash):
                self.error(identity, "missing source path/hash")
                continue
            source_hash = source_hash.lower()
            if source_hash in hashes:
                self.error(identity, f"copied/duplicate source bytes of {hashes[source_hash]}")
            hashes[source_hash] = identity
            matching = []
            for root in roots:
                root_path = self.resolve(root.get("path"))
                if root_path is not None and source_path.is_relative_to(root_path):
                    matching.append(root)
            eligible = len(matching) == 1 and (
                matching[0].get("source_id") == source.get("source_id")
                and matching[0].get("review_state") == "APPROVED"
                and valid_text(matching[0].get("rights_ref"))
                and matching[0].get("origin_role") == source.get("origin_role")
                and source.get("origin_role") in ("NEW_AZ_CAPTURE", "EXTERNAL_TRAIN")
            )
            if (
                not eligible
                or self.denied(source_path)
                or role == "PROTECTED_TEST"
                and source.get("origin_role") != "NEW_AZ_CAPTURE"
            ):
                self.error(identity, "unapproved/protected source; payload not read")
                continue
            protected = role == "PROTECTED_TEST"
            if protected:
                self.not_opened.append(f"{identity}: source video PROTECTED_TEST")
            else:
                self.checked_file(source, f"{identity}/source")
            duration = source.get("duration_ms")
            if not finite_number(duration) or duration <= 0:
                self.error(identity, "decoded source duration required")
            if source.get("original_video") is not True:
                self.block(f"{identity}: original-video provenance unverified")
            for technical in ("native_fps", "width", "height"):
                if not finite_number(source.get(technical)) or source[technical] <= 0:
                    self.block(f"{identity}: missing decoded {technical}")
            segments = self.annotation(sample, duration)
            if sample.get("training_use") == "INCLUDE" or sample.get("extraction") is not None:
                self.raw_lineage(sample, protected)
            annotation = sample.get("annotation", {})
            if isinstance(annotation, dict):
                quality_counts.update(annotation.get("observation_quality", []))
            transcript = (
                annotation.get("verified_transcript") if isinstance(annotation, dict) else None
            )
            if (
                sample.get("training_use") == "INCLUDE"
                and sample.get("kind") == "ISOLATED"
                and (not isinstance(transcript, str) or len(transcript) != 1)
            ):
                self.block(f"{identity}: isolated clip lacks a single reviewed letter")
            if sample.get("kind") == "NEGATIVE" and transcript:
                self.error(identity, "genuine letter transcript cannot be a NEGATIVE")
            if segments:
                used_sessions[signer].add(sample["session_id"])
            if segments and sample.get("kind") == "SEQUENCE":
                purpose = sample.get("sequence_purpose")
                if purpose not in ("repeated", "transition", "spelled_word"):
                    self.error(identity, "sequence_purpose required")
                if purpose == "spelled_word":
                    word_sequences.add(signer)
                sequence_counts[signer] += 1
                for pair in self.policy["coverage_gate"]["repeated_sequences"]:
                    if isinstance(transcript, str) and pair in transcript:
                        repeated[(role, pair)].add(signer)
                for pair in self.policy["coverage_gate"]["transition_sequences"]:
                    if isinstance(transcript, str) and pair in transcript:
                        transitions[(role, pair)].add(signer)
            for segment in segments:
                target = segment["model_target"]
                if target == "OTHER":
                    other[(role, str(segment.get("other_subtype")))].add(signer)
                elif sample.get("kind") == "ISOLATED":
                    counts[(role, signer, target)] += 1
                    letter_sessions[(signer, target)].add(sample["session_id"])
        gate = self.policy["coverage_gate"]
        for role in self.policy["roles"]:
            members = [key for key, person in signers.items() if person.get("split_role") == role]
            if len(members) < gate["signers_per_role"][role]:
                self.block(f"{role}: {len(members)} humans; need {gate['signers_per_role'][role]}")
            for signer in members:
                if len(used_sessions[signer]) < gate["sessions_per_signer"]:
                    self.block(f"{signer}: needs {gate['sessions_per_signer']} sessions")
                for letter in string.ascii_uppercase:
                    if (
                        counts[(role, signer, letter)]
                        < gate["isolated_clips_per_letter_per_signer"]
                    ):
                        self.block(
                            f"{role}/{signer}/{letter}: insufficient independent isolated clips"
                        )
                    if len(letter_sessions[(signer, letter)]) < gate["sessions_per_signer"]:
                        self.block(f"{role}/{signer}/{letter}: needs distinct capture sessions")
                if sequence_counts[signer] < gate["sequence_clips_per_signer"]:
                    self.block(f"{signer}: insufficient reviewed sequence clips")
                if signer not in word_sequences:
                    self.block(f"{signer}: no reviewed short spelled word/name sequence")
            for pair in gate["repeated_sequences"]:
                if len(repeated[(role, pair)]) < gate["other_signers_per_subtype"][role]:
                    self.block(f"{role}: missing signer coverage for repeated {pair}")
            for pair in gate["transition_sequences"]:
                if len(transitions[(role, pair)]) < gate["other_signers_per_subtype"][role]:
                    self.block(f"{role}: missing signer coverage for transition {pair}")
            for subtype in gate["other_subtypes_per_role"]:
                if len(other[(role, subtype)]) < gate["other_signers_per_subtype"][role]:
                    self.block(f"{role}: insufficient reviewed OTHER/{subtype} signer coverage")
            for letter in ("J", "Z"):
                if not any(key[0] == role and key[2] == letter for key in counts):
                    self.block(f"{role}: missing moving-letter {letter} coverage")
        approvals: dict[str, Any] = {}
        approval_path = self.resolve(data.get("approvals_path"))
        if approval_path is not None and approval_path.is_relative_to(self.base / "evidence"):
            if not self.denied(approval_path) and approval_path.is_file():
                approvals = json.loads(approval_path.read_text(encoding="utf-8-sig"))
        for name in self.policy["readiness_approvals"]:
            approval = approvals.get(name, {}) if isinstance(approvals, dict) else {}
            if (
                approval.get("state") != "APPROVED"
                or not valid_text(approval.get("reviewer_id"))
                or approval.get("package_sha256") != sha256(self.path)
                or approval.get("policy_sha256") != sha256(POLICY_PATH)
            ):
                self.block(f"{name}: missing approval bound to this exact package SHA-256")
            elif self.checked_file(approval.get("evidence"), name, metadata=True) is None:
                self.block(f"{name}: approval evidence is not verifiable")
        return self.report(
            {
                "samples": len(samples),
                "humans": len(people),
                "sessions": len(sessions),
                "isolated_letter_counts": {
                    "/".join(key): value for key, value in sorted(counts.items())
                },
                "quality_counts": dict(quality_counts),
                "other_signers": {
                    "/".join(key): len(value) for key, value in sorted(other.items())
                },
            }
        )

    def report(self, counts: dict[str, Any]) -> dict[str, Any]:
        return {
            "package": str(self.path),
            "package_sha256": sha256(self.path) if self.path.is_file() else None,
            "validator_sha256": sha256(Path(__file__)),
            "policy_sha256": sha256(POLICY_PATH),
            "intake_valid": not self.errors,
            "az2_data_gates_satisfied": not self.errors and not self.blockers,
            "errors": self.errors,
            "az2_blockers": self.blockers,
            "protected_payloads_not_opened": self.not_opened,
            "raw_observation_summary": self.raw_stats,
            "counts": counts,
        }


def validate_package(path: Path) -> dict[str, Any]:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    audit = Audit(path, policy)
    try:
        return audit.run()
    except (TypeError, KeyError, ValueError, OSError) as exc:
        audit.error("package", f"malformed/unreadable record: {type(exc).__name__}: {exc}")
        return audit.report({})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--stage", choices=("intake", "az2"), default="intake")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_package(args.package)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        if args.report.exists() or args.report.resolve() == args.package.resolve():
            parser.error(
                "--report must name a new file; existing evidence/manifests are never overwritten"
            )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    passed = (
        report["intake_valid"] if args.stage == "intake" else report["az2_data_gates_satisfied"]
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
