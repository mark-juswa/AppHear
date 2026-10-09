"""Scoped one-letter inference port; never changes WORD/model/adapter assets."""

# ruff: noqa: E501 -- reviewed Kotlin replacement blocks are deliberately literal.
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path

import numpy as np

from model.fingerspelling_single_letter import VERSION, decode_single_letter
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.android_beam_fixtures import peaked, text
from tools.fingerspelling.android_export import write_json
from tools.fingerspelling.android_sequence_v2_1_port import APP

OUT = REPO / "artifacts/fingerspelling_single_letter_01"
OLD = REPO / "artifacts/fingerspelling_sequence_v2_1_android_01"
TEMPLATES = Path(__file__).with_name("single_letter_android")
MAIN = APP / "android/app/src/main/java/com/example/apphear/fingerspelling"
UNIT = APP / "android/app/src/test/java/com/example/apphear/fingerspelling"
DEVICE = APP / "android/app/src/androidTest/java/com/example/apphear/fingerspelling"


def snapshot() -> None:
    OUT.mkdir(exist_ok=True)
    path = OUT / "preservation_before.json"
    if path.exists():
        return
    inherited = json.loads((OLD / "preservation_before.json").read_text(encoding="utf-8"))
    paths = set(inherited)
    for root in [APP / "android/app/src", REPO / "pipeline/fingerspelling", REPO / "model"]:
        paths.update(str(p) for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    paths.update(str(p) for p in OLD.rglob("*") if p.is_file())
    write_json(path, {p: sha256(Path(p)) for p in sorted(paths) if Path(p).is_file()})


def replace_once(value: str, before: str, after: str) -> str:
    if after in value:
        return value
    if value.count(before) != 1:
        raise ValueError(f"[single-letter/port] Missing/ambiguous reviewed anchor: {before[:65]}")
    return value.replace(before, after, 1)


def port() -> None:
    snapshot()
    copies = {
        "FingerspellSingleLetterDecoder.kt": MAIN,
        "FingerspellSingleLetterTest.kt": UNIT,
        "FingerspellSingleLetterInstrumentedTest.kt": DEVICE,
    }
    for name, target in copies.items():
        shutil.copyfile(TEMPLATES / name, target / name)
    core_path = MAIN / "FingerspellCore.kt"
    core = core_path.read_text(encoding="utf-8")
    core = replace_once(core, '    fun confirm(): String {', '''    fun confirmLetter(): String {
        require(preview.length==1 && preview[0] in 'A'..'Z') { "One letter required" }
        confirmed += preview
        preview = ""
        return confirmed
    }
    fun confirm(): String {''')
    core_path.write_text(core, encoding="utf-8")
    runtime_path = MAIN / "FingerspellRuntime.kt"
    value = runtime_path.read_text(encoding="utf-8")
    patches = [
        ('import org.json.JSONObject', 'import org.json.JSONArray\nimport org.json.JSONObject'),
        ('    private val owner=RecognitionModeController(resetWord)', '''    val singleLetterMode = FingerspellCapturePolicy.SINGLE_LETTER_ENABLED &&
        models.manifest.optString("candidate_id")==FingerspellCapturePolicy.CANDIDATE
    private val inputEvidence=FingerspellInputEvidence()
    private val usableEvidence=mutableListOf<Boolean>()
    private val captureTimestamps=mutableListOf<Double>()
    private var singleLetterDecodeCalls=0
    private fun readyMessage()=if(singleLetterMode) "One letter at a time: Start, show the letter, Done" else "Ready to fingerspell"
    private val owner=RecognitionModeController(resetWord)'''),
        ('        acceptedObservations=0', '        acceptedObservations=0\n        inputEvidence.reset(); usableEvidence.clear(); captureTimestamps.clear()'),
        ('\n        emit("Fingerspelling…")', '\n        emit(if(singleLetterMode) "Show ONE letter, then tap Done" else "Fingerspelling…")'),
        ('            if(common.observed.any { it }) observedFrames++', '''            if(common.observed.any { it }) observedFrames++
            val usable=inputEvidence.record(common)
            usableEvidence.add(usable); captureTimestamps.add(common.timestampMs)'''),
        ('            emit("Fingerspelling…")', '''            emit(if(!singleLetterMode) "Fingerspelling…" else if(usable)
                "Hand evidence present. Show ONE letter, then Done"
                else "Hand not detected. Bring your full hand into view")'''),
        ('            val (token,frames)=session.finish(); emit("Decoding…")', '''            if(singleLetterMode) inputEvidence.refusal()?.let { reason ->
                writeFailure("INPUT_EVIDENCE",IllegalStateException(reason))
                session.fail(); emit("No usable hand detected. Retry with your full hand visible.")
                return
            }
            val (token,frames)=session.finish(); emit("Decoding…")'''),
        ('            val text=if(decoderMode==FingerspellDecoderMode.PREFIX_BEAM_TOP1) beamRaw else greedyRaw', '''            val letterStart=SystemClock.elapsedRealtimeNanos()
            val letterResult=if(singleLetterMode) {
                singleLetterDecodeCalls++
                FingerspellSingleLetterDecoder.decode(logits,models.blankPenalty)
            } else null
            val letterMs=(SystemClock.elapsedRealtimeNanos()-letterStart)/1e6
            val text=letterResult?.text ?: if(decoderMode==FingerspellDecoderMode.PREFIX_BEAM_TOP1) beamRaw else greedyRaw'''),
        ('                writeProfile(frames.size,elapsed,text,greedyRaw,beamRaw,modelMs,greedyMs,beamMs)', '                writeProfile(frames.size,elapsed,text,greedyRaw,beamRaw,modelMs,greedyMs,beamMs,letterResult,letterMs,logits)'),
        ('                emit(if(text.isBlank()) "No spelling recognized. Retry." else "Review spelling before using it")', '''                emit(if(text.isBlank()) "No letter recognized. Retry." else if(singleLetterMode)
                    "Check the letter. Use adds it; Retry captures again."
                    else "Review spelling before using it")'''),
        ('            session.buffer.confirm(); session.cancel(); emit("Spelling confirmed")', '''            if(singleLetterMode) session.buffer.confirmLetter() else session.buffer.confirm()
            session.cancel(); emit(if(singleLetterMode) "Letter added. Start for the next letter." else "Spelling confirmed")'''),
        ('    private fun writeProfile(n:Int,finishMs:Double,text:String,greedyRaw:String,beamRaw:String,modelMs:Double,greedyMs:Double,beamMs:Double) {', '''    private fun writeProfile(n:Int,finishMs:Double,text:String,greedyRaw:String,beamRaw:String,modelMs:Double,greedyMs:Double,beamMs:Double,
                             letterResult:FingerspellSingleLetterDecoder.Result?,letterMs:Double,logits:Array<FloatArray>) {'''),
        ('                .put("accepted_observations",acceptedObservations)', '''                .put("accepted_observations",acceptedObservations)
                .put("usable_hand_observations",inputEvidence.usable)
                .put("input_refusal",inputEvidence.refusal() ?: JSONObject.NULL)
                .put("single_letter_mode",singleLetterMode)'''),
        ('            .put("decoder",decoderMode.name).put("beam_width",FingerspellPrefixBeamDecoder.BEAM_WIDTH)', '            .put("decoder",if(singleLetterMode) "SINGLE_LETTER_CTC_V1" else decoderMode.name).put("beam_width",FingerspellPrefixBeamDecoder.BEAM_WIDTH)'),
        ('            .put("beam_decode_calls",beamDecodeCalls).put("greedy_decode_calls",greedyDecodeCalls)', '''            .put("beam_decode_calls",beamDecodeCalls).put("greedy_decode_calls",greedyDecodeCalls)
            .put("single_letter_decode_calls",singleLetterDecodeCalls)
            .put("single_letter_decode_ms",letterMs).put("usable_hand_observations",inputEvidence.usable)
            .put("single_letter_mode",singleLetterMode)'''),
        ('        val dir=File(context.filesDir,"fingerspelling_sessions").apply { mkdirs() }\n        File(dir,"session_', '''        if(letterResult!=null) {
            report.put("single_letter_ctc",JSONObject().put("schema_version",FingerspellSingleLetterDecoder.VERSION)
                .put("text",letterResult.text).put("best_letter",letterResult.bestLetter)
                .put("letter_log_masses",JSONArray(letterResult.letterLogMasses.toList()))
                .put("empty_log_mass",letterResult.emptyLogMass).put("space_log_mass",letterResult.spaceLogMass)
                .put("correctness_confidence","NOT_CALIBRATED_OR_ESTIMATED"))
                .put("logits_unadjusted",JSONArray(logits.map { row -> JSONArray(row.map { it.toDouble() }) }))
                .put("usable_hand_evidence",JSONArray(usableEvidence))
                .put("timestamp_ms",JSONArray(captureTimestamps))
                .put("retained_rgb_or_landmarks",false)
        }
        val dir=File(context.filesDir,"fingerspelling_sessions").apply { mkdirs() }
        File(dir,"session_'''),
    ]
    for before, after in patches:
        value = replace_once(value, before, after)
    value = value.replace('emit("Ready to fingerspell")', 'emit(readyMessage())')
    runtime_path.write_text(value, encoding="utf-8")
    ownership_path = DEVICE / "FingerspellOwnershipInstrumentedTest.kt"
    value = ownership_path.read_text(encoding="utf-8")
    value = replace_once(value, '            val before=word.sentenceText', '            val before=word.sentenceText\n            val syntheticPreview=if(runtime.singleLetterMode) "B" else "BELLA"')
    # Existing ownership assertions unchanged; fixture respects the selected grammar.
    value = value.replace('session.complete(token,"BELLA")', 'session.complete(token,syntheticPreview)')
    value = value.replace('assertEquals("BELLA",', 'assertEquals(syntheticPreview,')
    ownership_path.write_text(value, encoding="utf-8")
    print(json.dumps({"port": "ISOLATED_FINGERSPELL_ONLY", "artifact_directory": str(OUT)}))


def fixtures() -> None:
    snapshot()
    for sub in ["android_assets", "parity_assets"]:
        shutil.copytree(OLD / sub, OUT / sub, dirs_exist_ok=True)
    rows = [(f"letter_{chr(65 + c)}", peaked([27, c, c, 27])) for c in range(26)]
    rows.extend([
        ("empty", peaked([])), ("all_blank", peaked([27] * 12)),
        ("space_refusal", peaked([26] * 4)), ("separated_LL", peaked([11, 27, 11])),
        ("AMY_not_single_letter", peaked([0, 12, 24])),
        ("long_letter", peaked([12] * 512)), ("stable_tie", np.zeros((3, 28), np.float32)),
    ])
    rng = np.random.default_rng(20261008)
    rows.extend((f"random_{t}", rng.normal(size=(t, 28)).astype(np.float32)) for t in [1, 2, 3, 7, 40, 150, 512])
    for path in sorted(OLD.glob("*.npz")):
        with np.load(path) as archive:
            if "tflite_logits" in archive:
                rows.append((path.stem, archive["tflite_logits"]))
    destination = OUT / "parity_assets/fingerspell_single_letter"
    destination.mkdir(exist_ok=True)
    records = []
    with (destination / "fixtures.bin").open("wb") as output:
        text(output, VERSION)
        output.write(struct.pack(">i", len(rows)))
        for name, logits in rows:
            result = decode_single_letter(logits)
            text(output, name)
            output.write(struct.pack(">i", len(logits)))
            output.write(logits.astype(">f4").tobytes())
            text(output, result.text)
            text(output, result.best_letter)
            output.write(struct.pack(">28d", *result.letter_log_masses, result.empty_log_mass, result.space_log_mass))
            records.append({"id": name, "timesteps": len(logits), "text": result.text, "diagnostic_not_accuracy": True})
    write_json(OUT / "fixture_manifest.json", {
        "schema_version": VERSION, "count": len(rows), "rows": records,
        "sha256": sha256(destination / "fixtures.bin"), "blank_penalty": 0.5,
        "model_manifest_sha256": sha256(OUT / "android_assets/fingerspelling/model_manifest.json"),
        "accuracy_claim": False, "test_accessed": False, "training": False,
    })
    print(json.dumps({"fixtures": len(rows), "model_package": "UNCHANGED_COPY", "accuracy_claim": False}))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["snapshot", "fixtures", "port"])
    args = parser.parse_args()
    {"snapshot": snapshot, "fixtures": fixtures, "port": port}[args.action]()
