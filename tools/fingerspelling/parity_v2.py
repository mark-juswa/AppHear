"""Isolated Kotlin canonical-hand reference parity; never changes Android."""

from __future__ import annotations

import json
import os
import struct
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from model.fingerspelling_baseline2 import DEFAULT_DATA, dataset, policy
from pipeline.fingerspelling.adapter import sha256, subset
from pipeline.fingerspelling.adapter_v2 import WIDTH, derive, identity
from pipeline.fingerspelling.canonical_hand import CONFIG
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from pipeline.fingerspelling.temporal_views import selected_indices
from tools.fingerspelling import parity


def run() -> dict[str, Any]:
    out = REPO / "artifacts/fingerspelling_baseline3/parity"
    out.mkdir(parents=True, exist_ok=True)
    modules = Path.home() / ".gradle/caches/modules-2/files-2.1"
    jars = []
    for group, name in [
        ("org.jetbrains.kotlin", x)
        for x in [
            "kotlin-compiler-embeddable",
            "kotlin-stdlib",
            "kotlin-script-runtime",
            "kotlin-reflect",
        ]
    ] + [
        ("org.jetbrains.intellij.deps", "trove4j"),
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm"),
        ("org.jetbrains", "annotations"),
    ]:
        choices = sorted(
            p
            for p in (modules / group / name).rglob("*.jar")
            if not p.name.endswith(("-sources.jar", "-javadoc.jar"))
        )
        pinned = [p for p in choices if "/2.0.21/" in p.as_posix()]
        jars.append((pinned or choices)[-1])
    cp = os.pathsep.join(str(p) for p in jars)
    classes = out / "classes"
    classes.mkdir(exist_ok=True)
    sources = [
        REPO / "tools/fingerspelling/FoundationParity.kt",
        REPO / "tools/fingerspelling/CanonicalParity.kt",
    ]
    compiled = subprocess.run(
        [
            "java",
            "-cp",
            cp,
            "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
            "-no-stdlib",
            "-no-reflect",
            "-classpath",
            cp,
            "-d",
            str(classes),
            *map(str, sources),
        ],
        capture_output=True,
        text=True,
    )
    if compiled.returncode:
        raise RuntimeError("[fingerspelling/v2-parity] " + compiled.stderr)
    with (out / "policy.bin").open("wb") as f:
        header = b"SigningHandCanonicalizer.v1"
        f.write(struct.pack(">H", len(header)) + header)
        f.write(
            struct.pack(
                ">i8f",
                CONFIG["minimum_valid_joints"],
                CONFIG["maximum_association_gap_seconds"],
                CONFIG["maximum_association_distance_short_side"],
                CONFIG["association_margin_short_side"],
                CONFIG["duplicate_roi_iou"],
                CONFIG["duplicate_wrist_distance_short_side"],
                *CONFIG["quality_weights"],
            )
        )
    fixtures = []
    raw = parity.fixture()
    # Explicit slot-switch fixture; synthesized only for parity, never training.
    raw.hand_observed[0:2, 1] = False
    raw.hand_joint_valid[0:2, 1] = False
    raw.hand_observed[2, 0] = False
    raw.hand_joint_valid[2, 0] = False
    raw.hand_observed[2, 1] = True
    raw.hand_joint_valid[2, 1] = True
    raw.hand_xy[2, 1] = raw.hand_xy[0, 0]
    fixtures.append(("edge_cases", raw))
    distinct = parity.fixture()
    # Spatially distinct two-candidate case, followed by continuity and reacquisition.
    for i in [0, 1, 4, 8, 9]:
        distinct.hand_xy[i, 1] = distinct.hand_xy[i, 0] + np.float32(250)
        distinct.hand_joint_valid[i, 1] = distinct.hand_joint_valid[i, 0]
        distinct.hand_observed[i, 1] = distinct.hand_observed[i, 0]
        distinct.hand_roi_center_side[i, 1] = distinct.hand_roi_center_side[i, 0]
        distinct.hand_roi_center_side[i, 1, :2] += np.float32(250)
    fixtures.append(("distinct_hand_ambiguity", distinct))
    tied = parity.fixture()
    for field in [
        "hand_xy",
        "hand_joint_valid",
        "hand_observed",
        "hand_presence",
        "hand_proposal_support",
        "hand_proposal_present",
        "hand_roi_center_side",
    ]:
        a = getattr(tied, field)
        a[:, 1] = a[:, 0]
    tied.hand_xy[:, 0, 4, 0] += np.float32(12)
    fixtures.append(("equal_quality_wrist_tie", tied))
    rows = dataset(DEFAULT_DATA)
    p, _ = policy()
    for role, stratum in [("TRAIN", "DAUN"), ("TRAIN", "MacKenzie"), ("DEV", "DAUN")]:
        r = next(x for x in rows if x["split_role"] == role and x["source_stratum"] == stratum)
        original = verify_raw(
            REPO / r["raw_path"], REPO / r["raw_receipt_path"], r, r["source_sha256"]
        )
        fixtures.append((r["sample_id"], original))
    comparisons = []
    for name, raw in fixtures:
        for view in p["temporal_views"]:
            chosen = subset(raw, selected_indices(raw, view, p))
            parity.serialize(out / "input.bin", chosen)
            subprocess.run(
                [
                    "java",
                    "-cp",
                    str(classes) + os.pathsep + cp,
                    "apphear.canonical.CanonicalParityKt",
                    str(out / "input.bin"),
                    str(out / "output.bin"),
                    str(out / "policy.bin"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            actual = (
                np.frombuffer((out / "output.bin").read_bytes(), dtype=">f4")
                .astype(np.float32)
                .reshape(-1, WIDTH)
            )
            expected, _ = derive(chosen)
            np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)
            comparisons.append(
                {
                    "sample_id": name,
                    "view": view,
                    "frames": len(expected),
                    "maximum_absolute_error": float(np.max(abs(actual - expected))),
                    "byte_equal": bool(
                        np.array_equal(actual.view(np.uint32), expected.view(np.uint32))
                    ),
                }
            )
    result = {
        "status": "CANONICAL_V2_JVM_PARITY_PASS",
        "adapter": identity(),
        "kotlin_sha256": sha256(sources[1]),
        "comparisons": comparisons,
        "frames": sum(x["frames"] for x in comparisons),
        "compiler_sha256": sha256(jars[0]),
        "scope": "UNUSED_JVM_REFERENCE_NOT_INSTALLED_ANDROID",
        "test_accessed": False,
    }
    write_json_atomic(out / "parity.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
