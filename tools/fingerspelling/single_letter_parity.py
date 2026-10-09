"""Compile the actual Android decoder source for bounded Python/JVM parity."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pipeline.fingerspelling.adapter import sha256
from tools.fingerspelling.android_export import write_json
from tools.fingerspelling.single_letter_port import MAIN, OUT, TEMPLATES


def run() -> None:
    modules = Path(r"C:\Users\Gigabyte\.gradle\caches\modules-2\files-2.1")
    jars = []
    for group, name in [
        ("org.jetbrains.kotlin", "kotlin-compiler-embeddable"),
        ("org.jetbrains.kotlin", "kotlin-stdlib"),
        ("org.jetbrains.kotlin", "kotlin-script-runtime"),
        ("org.jetbrains.kotlin", "kotlin-reflect"),
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
    java = r"C:\Program Files\Java\jdk-17\bin\java.exe"
    classes = OUT / "jvm_classes"
    classes.mkdir(exist_ok=True)
    sources = [
        MAIN / "FeatureAdapterV1.kt",
        MAIN / "FingerspellSingleLetterDecoder.kt",
        TEMPLATES / "SingleLetterParity.kt",
    ]
    compiled = subprocess.run(
        [
            java,
            "-cp",
            cp,
            "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
            "-no-stdlib",
            "-no-reflect",
            "-classpath",
            cp,
            "-d",
            str(classes),
            *(str(p) for p in sources),
        ],
        capture_output=True,
        text=True,
    )
    if compiled.returncode:
        raise RuntimeError(compiled.stderr)
    fixture = OUT / "parity_assets/fingerspell_single_letter/fixtures.bin"
    result = subprocess.run(
        [
            java,
            "-cp",
            str(classes) + os.pathsep + cp,
            "apphear.singleletter.SingleLetterParityKt",
            str(fixture),
            str(OUT / "jvm_strings.bin"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    write_json(
        OUT / "jvm_parity.json",
        {
            "status": "SINGLE_LETTER_JVM_PARITY_PASS",
            "output": result.stdout.strip(),
            "fixture_sha256": sha256(fixture),
            "actual_android_source_sha256": sha256(sources[1]),
            "accuracy_claim": False,
            "training": False,
        },
    )
    print(result.stdout.strip())


if __name__ == "__main__":
    run()
