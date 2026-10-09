"""Compile cached Kotlin reference and compare raw-derived JVM/Python fixture outputs."""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
from pathlib import Path

import numpy as np

from pipeline.fingerspelling.adapter import CONFIG, VERSION, WIDTH, derive, identity, sha256, subset
from pipeline.fingerspelling.sequence_manifest import ADMISSION, REPO
from pipeline.perception_vnext.recognition_schema import (
    RawSequence,
    load_raw_sequence,
    save_raw_sequence,
)


def fixture() -> RawSequence:
    results = json.loads(
        (ADMISSION / "admission_closure_01/evidence/candidate01_results.json").read_text()
    )
    raw = load_raw_sequence(REPO / results[0]["raw_path"])
    good = np.flatnonzero(raw.hand_observed.all(axis=1) & raw.hand_joint_valid.all(axis=(1, 2)))[0]
    f = subset(raw, np.repeat(good, 10))
    f.metadata["sample_id"] = "parity-fixture-not-training"
    f.metadata["synthetic_test_fixture_not_training"] = True
    # These mutations are test fixtures, never source samples or training examples.
    f.frame_index[:] = np.arange(10)
    f.timestamp_ms[:] = [0, 160, 320, 480, 640, 800, 960, 1120, 2400, 2560]
    f.hand_xy[1] += np.float32(8)
    f.hand_observed[2, 1] = False
    f.hand_joint_valid[2, 1] = False
    f.hand_xy[2, 1] = np.nan
    f.hand_observed[3] = False
    f.hand_joint_valid[3] = False
    f.hand_xy[3] = np.nan
    for name in [
        "hand_xy",
        "hand_observed",
        "hand_joint_valid",
        "hand_proposal_support",
        "hand_presence",
        "hand_proposal_present",
        "hand_roi_center_side",
    ]:
        a = getattr(f, name)
        a[4, 1] = a[4, 0]
    f.hand_joint_valid[5, :, [2, 3]] = False
    f.hand_xy[5, :, [2, 3]] = np.nan
    f.body_available[:] = False
    f.body_valid[6] = False
    f.body_xy[6] = np.nan
    f.hand_proposal_support[6, 0, 4] = np.nan
    f.hand_presence[6, 1] = np.nan
    f.hand_roi_center_side[6, 0] = np.nan
    f.hand_joint_valid[7, :, 0] = False
    f.hand_xy[7, :, 0] = np.nan
    f.source_size[9] += 1
    f.validate()
    return f


def serialize(path: Path, raw: RawSequence) -> None:
    with path.open("wb") as stream:
        version = VERSION.encode()
        stream.write(struct.pack(">H", len(version)) + version)
        stream.write(
            struct.pack(
                ">ffi",
                CONFIG["minimum_scale_short_side_ratio"],
                CONFIG["maximum_motion_gap_seconds"],
                len(raw.frame_index),
            )
        )
        for i in range(len(raw.frame_index)):
            stream.write(struct.pack(">dii", raw.timestamp_ms[i], *raw.source_size[i]))
            for s in range(2):
                for j in range(21):
                    stream.write(
                        struct.pack(
                            ">ff?f",
                            *raw.hand_xy[i, s, j],
                            raw.hand_joint_valid[i, s, j],
                            raw.hand_proposal_support[i, s, j],
                        )
                    )
                stream.write(
                    struct.pack(
                        ">f??fff",
                        raw.hand_presence[i, s],
                        raw.hand_observed[i, s],
                        raw.hand_proposal_present[i, s],
                        *raw.hand_roi_center_side[i, s],
                    )
                )
            for p in range(8):
                stream.write(
                    struct.pack(
                        ">fff?", *raw.body_xy[i, p], raw.body_support[i, p], raw.body_valid[i, p]
                    )
                )
            stream.write(struct.pack(">?", raw.body_available[i]))


def run(output: Path, cache: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    modules = cache / "modules-2/files-2.1"
    jars = []
    for name in (
        "kotlin-compiler-embeddable",
        "kotlin-stdlib",
        "kotlin-script-runtime",
        "kotlin-reflect",
    ):
        choices = sorted(
            p
            for p in (modules / "org.jetbrains.kotlin" / name).rglob("*.jar")
            if not p.name.endswith(("-sources.jar", "-javadoc.jar"))
        )
        pinned = [p for p in choices if "/2.0.21/" in p.as_posix()]
        jars.append((pinned or choices)[-1])
    for group, name in [
        ("org.jetbrains.intellij.deps", "trove4j"),
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm"),
        ("org.jetbrains", "annotations"),
    ]:
        jars.append(
            sorted(
                p
                for p in (modules / group / name).rglob("*.jar")
                if not p.name.endswith(("-sources.jar", "-javadoc.jar"))
            )[-1]
        )
    cp = os.pathsep.join(str(p) for p in jars)
    kotlin = REPO / "tools/fingerspelling/FoundationParity.kt"
    classes = output / "classes"
    classes.mkdir(exist_ok=True)
    compile_cmd = [
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
        str(kotlin),
    ]
    compiled = subprocess.run(compile_cmd, capture_output=True, text=True)
    if compiled.returncode:
        raise RuntimeError("[fingerspelling/parity] Kotlin compilation failed: " + compiled.stderr)
    raw = fixture()
    save_raw_sequence(output / "edge_cases.raw-v1.npz", raw)
    serialize(output / "fixture.bin", raw)
    subprocess.run(
        [
            "java",
            "-cp",
            str(classes) + os.pathsep + cp,
            "apphear.foundation.FoundationParityKt",
            str(output / "fixture.bin"),
            str(output / "kotlin.bin"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    expected = derive(raw)
    actual = (
        np.frombuffer((output / "kotlin.bin").read_bytes(), dtype=">f4")
        .astype(np.float32)
        .reshape(-1, WIDTH)
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)
    result = {
        "adapter": identity(),
        "kotlin_reference_sha256": sha256(kotlin),
        "fixture_sha256": sha256(output / "edge_cases.raw-v1.npz"),
        "fixture_frames": len(expected),
        "values_compared": int(expected.size),
        "maximum_absolute_error": float(np.max(np.abs(actual - expected))),
        "byte_equal_float32": bool(
            np.array_equal(actual.view(np.uint32), expected.view(np.uint32))
        ),
        "tolerance": {"atol": 1e-6, "rtol": 1e-6},
        "pass": True,
        "scope": "Isolated JVM common-fields math; NOT installed Android adapter/runtime parity",
        "cases": [
            "normal",
            "consecutive_motion",
            "one_missing",
            "both_missing",
            "duplicate_slots",
            "partial_joint_validity",
            "body_absent",
            "nonfinite_support_presence_roi",
            "wrist_missing",
            "long_gap",
            "resolution_change",
        ],
        "compiler_jar": str(jars[0]),
        "compiler_sha256": sha256(jars[0]),
    }
    comparisons = []
    sources = json.loads(
        (ADMISSION / "admission_closure_01/evidence/candidate01_results.json").read_text()
    )
    for source in sources:
        original = load_raw_sequence(REPO / source["raw_path"])
        from pipeline.fingerspelling.adapter import phone_indices

        for name, view in [
            ("native", original),
            ("phone", subset(original, phone_indices(original.timestamp_ms))),
        ]:
            serialize(output / "real-input.bin", view)
            subprocess.run(
                [
                    "java",
                    "-cp",
                    str(classes) + os.pathsep + cp,
                    "apphear.foundation.FoundationParityKt",
                    str(output / "real-input.bin"),
                    str(output / "real-output.bin"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            expected_real = derive(view)
            actual_real = (
                np.frombuffer((output / "real-output.bin").read_bytes(), dtype=">f4")
                .astype(np.float32)
                .reshape(-1, WIDTH)
            )
            np.testing.assert_allclose(actual_real, expected_real, rtol=1e-6, atol=1e-6)
            comparisons.append(
                {
                    "sample_id": source["sample_id"],
                    "raw_sha256": source["raw_sha256"],
                    "view": name,
                    "frames": len(view.frame_index),
                    "byte_equal_float32": bool(
                        np.array_equal(actual_real.view(np.uint32), expected_real.view(np.uint32))
                    ),
                    "maximum_absolute_error": float(np.max(np.abs(actual_real - expected_real))),
                }
            )
    result["real_sequence_comparisons"] = comparisons
    result["real_frames_compared"] = sum(r["frames"] for r in comparisons)
    result["all_real_byte_equal"] = all(r["byte_equal_float32"] for r in comparisons)
    (output / "parity.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gradle-cache", type=Path, default=Path.home() / ".gradle/caches")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.gradle_cache), indent=2))
