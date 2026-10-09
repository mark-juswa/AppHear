"""Scoped V2.1 package admission in the authoritative October4 worktree.

Requires completed host parity; changes only the isolated model loader and adds
one candidate-specific instrumentation test. Never changes the old exporters/tests.
"""

# Ruff E501: literal Kotlin patch blocks preserve the reviewed source verbatim.
# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO

APP = Path(r"C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3")
OUT = REPO / "artifacts/fingerspelling_sequence_v2_1_android_01"


def port() -> None:
    report = json.loads((OUT / "export_parity.json").read_text())
    assert report["status"] == "V2_1_HOST_EXPORT_PARITY_PASS"
    manifest = OUT / "android_assets/fingerspelling/model_manifest.json"
    assert sha256(manifest) == report["manifest_sha256"]
    path = APP / "android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellModels.kt"
    text = path.read_text(encoding="utf-8")
    candidate = "SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY"
    if candidate not in text:
        before = json.loads((OUT / "preservation_before.json").read_text())
        assert sha256(path) == before[str(path)], "Loader changed since transfer snapshot"
        (OUT / "FingerspellModels.before.kt").write_bytes(path.read_bytes())
        text = text.replace(
            '            else -> error("Frozen model/config manifest changed")',
            f'            "{report["manifest_sha256"]}" -> false\n'
            '            else -> error("Frozen model/config manifest changed")',
        )
        old = """            require(manifest.getString("candidate_id") == "TRAIN4096_EPOCH038_GEOMETRY_ONLY")
            require(manifest.getInt("checkpoint_epoch") == 38)
            require(manifest.getString("checkpoint_sha256") == "b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886")"""
        new = """            when (manifest.getString("candidate_id")) {
                "TRAIN4096_EPOCH038_GEOMETRY_ONLY" -> {
                    require(manifest.getInt("checkpoint_epoch") == 38)
                    require(manifest.getString("checkpoint_sha256") == "b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886")
                }
                "SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY" -> {
                    require(manifest.getInt("checkpoint_epoch") == 34)
                    require(manifest.getString("checkpoint_sha256") == "3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638")
                    require(!manifest.getBoolean("causal") && !manifest.getBoolean("auxiliary_head_exported"))
                    require(manifest.getInt("parameter_count") == 292956)
                }
                else -> error("Unknown pinned geometry candidate")
            }"""
        assert old in text
        text = text.replace(old, new).replace(
            "Dynamic causal Conv1D output", "Dynamic Conv1D output"
        )
        path.write_text(text, encoding="utf-8")
    assert report["manifest_sha256"] in path.read_text(encoding="utf-8")
    test_dir = APP / "android/app/src/androidTest/java/com/example/apphear/fingerspelling"
    old_test_path = test_dir / "Train4096ParityInstrumentedTest.kt"
    test = old_test_path.read_text(encoding="utf-8")
    guard = '            org.junit.Assume.assumeTrue(models.manifest.optString("candidate_id") == "TRAIN4096_EPOCH038_GEOMETRY_ONLY")'
    if guard not in test:
        before = json.loads((OUT / "preservation_before.json").read_text())
        assert sha256(old_test_path) == before[str(old_test_path)]
        (OUT / "Train4096ParityInstrumentedTest.before.kt").write_bytes(old_test_path.read_bytes())
        test = test.replace(
            "            assumeFalse(models.visualEnabled)",
            "            assumeFalse(models.visualEnabled)\n" + guard,
        )
        old_test_path.write_text(test, encoding="utf-8")
    test = test.replace("Train4096ParityInstrumentedTest", "SequenceV21ParityInstrumentedTest")
    test = test.replace("TRAIN4096_EPOCH038_GEOMETRY_ONLY", candidate)
    test = test.replace("Frozen epoch038", "Frozen non-causal V2.1 epoch034").replace(
        "train4096_geometry", "sequence_v2_1_geometry"
    )
    test = test.replace(
        "b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886",
        "3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638",
    )
    old = """                    val prefix=models.logits(frames.take(maxOf(1,n/2)),mask.copyOf(maxOf(1,n/2)))
                    for(t in prefix.indices) for(c in 0..27) assertEquals(actual[t][c],prefix[t][c],2e-4f)"""
    new = """                    // Future context is intentional. Verify masked padding, not causal prefix invariance.
                    val padded=models.logits(frames+List(11){FloatArray(405){17f}},mask.copyOf(n+11))
                    for(t in actual.indices) for(c in 0..27) {
                        paddingError=maxOf(paddingError,abs(actual[t][c]-padded[t][c]))
                        assertEquals("$id padding $t,$c",actual[t][c],padded[t][c],2e-4f)
                    }
                    assertEquals(greedy,FingerspellCtcDecoder.decode(padded.take(n).toTypedArray(),models.blankPenalty))
                    assertEquals(beam,FingerspellPrefixBeamDecoder.decode(padded.take(n).toTypedArray(),models.blankPenalty).text)"""
    assert old in test
    test = test.replace(old, new).replace(
        "var featureCount=0", "var featureCount=0; var paddingError=0f"
    )
    # Padding is not an observation. Fixture decoding must exclude masked test-only rows.
    test = (
        test.replace(
            "val greedy=FingerspellCtcDecoder.decode(actual,models.blankPenalty)",
            "val real=actual.filterIndexed { t,_ -> mask[t]==1f }.toTypedArray()\n"
            "                    val greedy=FingerspellCtcDecoder.decode(real,models.blankPenalty)",
        )
        .replace(
            "FingerspellPrefixBeamDecoder.decode(actual,models.blankPenalty)",
            "FingerspellPrefixBeamDecoder.decode(real,models.blankPenalty)",
        )
        .replace(
            "padded.take(n).toTypedArray()",
            "padded.take(n).filterIndexed { t,_ -> mask[t]==1f }.toTypedArray()",
        )
    )
    test = test.replace(
        "TRAIN4096_ANDROID_NUMERICAL_PARITY_PASS", "V2_1_ANDROID_NUMERICAL_PARITY_PASS"
    )
    test = test.replace(
        '.put("causal_prefix_cases",14)',
        '.put("masked_padding_cases",14).put("padding_max_error",paddingError)',
    )
    test = test.replace(
        "fingerspell_train4096_parity.json", "fingerspell_sequence_v2_1_parity.json"
    )
    (test_dir / "SequenceV21ParityInstrumentedTest.kt").write_text(test, encoding="utf-8")
    print(
        json.dumps(
            {
                "loader": str(path),
                "test": str(test_dir / "SequenceV21ParityInstrumentedTest.kt"),
                "candidate": candidate,
                "manifest_sha256": report["manifest_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    port()
