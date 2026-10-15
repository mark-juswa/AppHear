"""Immutable navigation/review profiles; they never set decoder/model parameters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ASSET = (
    ROOT
    / "android/app/src/debug/assets/phone_causal_recognition_01/stage2_transition_protocol.json"
)
PROTECTED_BASELINE = "76d93cecd85bf9f76064d320aa4a5791b5f0704a"


@dataclass(frozen=True)
class TransitionProtocol:
    profile_id: str
    milestone: str
    label_schema: str
    blocks: tuple[str, ...]
    positive_sequences: tuple[tuple[str, tuple[str, ...]], ...]
    negative_blocks: tuple[str, ...]
    sha256: str = ""

    def metadata(self) -> dict[str, str]:
        if self.profile_id == "LEGACY_7_BLOCKS":
            return {}
        return {
            "transition_protocol_id": self.profile_id,
            "transition_protocol_sha256": self.sha256,
        }


LEGACY = TransitionProtocol(
    "LEGACY_7_BLOCKS",
    "APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01",
    "apphear.continuous_transition.human_boundaries.v1",
    (
        "A_HANDS_DOWN",
        "B_HANDS_UP",
        "NEG_OPEN_HAND_HOLD",
        "NEG_SEAT_BODY_REPOSITION",
        "NEG_STANDING_MOVING",
        "NEG_GROOMING_ADJUSTMENT",
        "NEG_PHONE_INTERACTION",
    ),
    (
        ("A_HANDS_DOWN", ("HELLO", "HOME", "TABLE", "HELLO")),
        ("B_HANDS_UP", ("HELLO", "HOME", "TABLE", "HELLO")),
    ),
    (
        "NEG_OPEN_HAND_HOLD",
        "NEG_SEAT_BODY_REPOSITION",
        "NEG_STANDING_MOVING",
        "NEG_GROOMING_ADJUSTMENT",
        "NEG_PHONE_INTERACTION",
    ),
)


def compact_protocol() -> TransitionProtocol:
    content = ASSET.read_bytes()
    spec = json.loads(content)
    if (
        spec["schema"] != "apphear.word_transition_protocol.v1"
        or spec["profile_id"] != "V3_STAGE2_COMPACT_01"
        or spec["protected_baseline_sha"] != PROTECTED_BASELINE
        or spec["comparison_baseline_sha"] != "e196a8d501386091eae52f59df0fa349e26b43e2"
    ):
        raise ValueError("INVALID_COMPACT_PROTOCOL_CONTRACT")
    blocks = spec["blocks"]
    expected_ids = (
        "A_HANDS_DOWN",
        "B_HANDS_UP",
        "C_REPEAT_HANDS_UP",
        "D_SIGN_THEN_HOLD",
        "E_ORDINARY_MOVEMENT",
    )
    expected_glosses = (("HELLO", "HOME"), ("HELLO", "HOME"), ("HELLO", "HELLO"), ("HELLO",), ())
    if (
        tuple(b["id"] for b in blocks) != expected_ids
        or tuple(tuple(b["glosses"]) for b in blocks) != expected_glosses
        or tuple(b["review_negative"] for b in blocks) != (False, False, False, True, True)
        or any(not b["instruction"].strip() for b in blocks)
        or spec["label_schema"] != "apphear.continuous_transition.human_boundaries.v2"
        or spec["milestone"] != "RECOGNITION_V3_STAGE2_TRANSITION_CAPTURE_01"
    ):
        raise ValueError("COMPACT_PROTOCOL_CONTENT_DRIFT")
    return TransitionProtocol(
        spec["profile_id"],
        spec["milestone"],
        spec["label_schema"],
        expected_ids,
        tuple((b["id"], tuple(b["glosses"])) for b in blocks if b["glosses"]),
        tuple(b["id"] for b in blocks if b["review_negative"]),
        hashlib.sha256(content).hexdigest(),
    )


def from_identity(declared: dict[str, Any]) -> TransitionProtocol:
    if "transition_protocol_id" not in declared:
        return LEGACY
    profile = compact_protocol()
    if (
        declared.get("transition_protocol_id") != profile.profile_id
        or declared.get("transition_protocol_sha256") != profile.sha256
        or declared.get("comparison_baseline_sha") != "e196a8d501386091eae52f59df0fa349e26b43e2"
        or declared.get("transition_label_schema") != profile.label_schema
        or declared.get("stage1_parallel_hands_enabled") is not False
        or declared.get("declared_signer_proficiency")
        not in {"UNKNOWN", "NONEXPERT_ENGINEERING_SMOKE", "ASL_PROFICIENT"}
    ):
        raise ValueError("COMPACT_CAPTURE_IDENTITY_MISMATCH")
    return profile


def from_integrity(integrity: dict[str, Any]) -> TransitionProtocol:
    if "transition_protocol_id" not in integrity:
        return LEGACY
    profile = compact_protocol()
    if any(integrity.get(k) != v for k, v in profile.metadata().items()):
        raise ValueError("COMPACT_REVIEW_PROTOCOL_MISMATCH")
    return profile
