"""Stage only the context/mode orchestration seams in the approved Android checkout."""
# ruff: noqa: E501
import json
import shutil

from tools.fingerspelling.camera_input_port import APP, JAVA, ROOT, sha

OUT = ROOT / "artifacts/recognition_coordination_01"


def replace(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Ambiguous migration seam: {old[:100]}")
    return text.replace(old, new, 1)


def main() -> None:
    if (OUT / "before.json").exists():
        raise RuntimeError("Orchestration already staged; do not reapply")
    inventory = {
        str(p.relative_to(APP)).replace("\\", "/"): sha(p)
        for p in (APP / "android/app/src").rglob("*") if p.is_file()
    }
    inventory["android/app/build.gradle.kts"] = sha(APP / "android/app/build.gradle.kts")
    (OUT / "before.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    for name, target in {
        "RecognitionCoordinator.kt": JAVA + "coordination/RecognitionCoordinator.kt",
        "RecognitionCoordinationBridge.kt": JAVA + "coordination/RecognitionCoordinationBridge.kt",
        "RecognitionCoordinatorTest.kt": "android/app/src/test/java/com/example/apphear/coordination/RecognitionCoordinatorTest.kt",
        "RecognitionCoordinationInstrumentedTest.kt": "android/app/src/androidTest/java/com/example/apphear/coordination/RecognitionCoordinationInstrumentedTest.kt",
        "ContextAssistCameraReadyRegression.kt": "android/app/src/androidTest/java/com/example/apphear/coordination/ContextAssistCameraReadyRegression.kt",
        "recognition_coordination_policy.json": "android/app/src/main/assets/recognition_coordination_policy.json",
        "recognition_coordination.xml": "android/app/src/main/res/values/recognition_coordination.xml",
    }.items():
        path = APP / target
        assert not path.exists(), target
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUT / "sources" / name, path)
    path = APP / "android/app/build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    text = replace(text, "    val fingerspellContinuous =", '    val recognitionCoordination = providers.gradleProperty("recognitionCoordination").map { it.equals("true",ignoreCase=true) }.getOrElse(false)\n    val fingerspellContinuous =')
    text = replace(text, '            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", (', '            buildConfigField("boolean", "RECOGNITION_COORDINATION_ENABLED", (recognitionCoordination && fingerspellDebug && fingerspellContinuous && contextPhraseAssistDebug).toString())\n            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", (')
    text = replace(text, '            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", "false")', '            buildConfigField("boolean", "RECOGNITION_COORDINATION_ENABLED", "false")\n            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", "false")')
    path.write_text(text, encoding="utf-8")
    path = APP / JAVA / "contextassist/ConversationPhraseAssist.kt"
    text = path.read_text(encoding="utf-8")
    text = replace(text, "    fun recentTurns(): List<ConversationTurn>", '''    /** Read-only context identity for exclusive recognition routing; never a predicted reply. */
    fun activeHearingTurnId(): Long? = if(enabled) context.latestHearingTurnId() else null

    /** Called only after explicit spelling review. No WORD matcher or recognition mutation. */
    fun recordConfirmedSpelling(actualText: String, expectedHearingTurnId: Long?): Boolean {
        if(!enabled || actualText.isBlank() || actualText.any { it !in 'A'..'Z' && it!=' ' } ||
            context.latestHearingTurnId()!=expectedHearingTurnId) return false
        context.finishReplyWindow()
        context.add(ConversationSpeaker.DEAF,ConversationSource.SIGN_TO_TEXT,actualText,System.currentTimeMillis())
        presentation.value=PhraseAssistUiState()
        return true
    }

    fun recentTurns(): List<ConversationTurn>''')
    path.write_text(text, encoding="utf-8")
    path = APP / JAVA / "RecognitionActivity.kt"
    # Preserve historical non-UTF8 bytes outside the deliberately ASCII-only integration edits.
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    text = replace(text, '    private val recognitionSettings by lazy', '    private var coordination: com.example.apphear.coordination.RecognitionCoordinationBridge? = null\n    private val recognitionSettings by lazy')
    text = replace(text, '''        a1ShutdownExecutor = Executors.newSingleThreadExecutor { runnable ->''', '''        if(BuildConfig.RECOGNITION_COORDINATION_ENABLED) {
            coordination = runCatching {
                com.example.apphear.coordination.RecognitionCoordinationBridge(this,binding.root,
                    runtime={fingerspellRuntime},
                    dispatch={task -> if(!cameraExecutor.isShutdown) cameraExecutor.execute { task() }},
                    main={task -> runOnUiThread { if(!isFinishing && !isDestroyed) task() }},
                    selected={mode ->
                        selectedRecognitionMode=mode
                        runOnUiThread {
                            if(!isFinishing && !isDestroyed) {
                                if(mode==RecognitionMode.FINGERSPELL && signingTurn.snapshot().isNotEmpty()) evidenceInterrupted=true
                                if(mode==RecognitionMode.WORD) renderRecognitionSnapshot(RecognitionUiSnapshot.from(
                                    com.example.apphear.pipeline.recognition.RecognitionState.Idle,
                                    phoneSession?.sentenceText.orEmpty(),getString(R.string.gloss_placeholder),
                                    getString(R.string.signing),getString(R.string.sentence_placeholder)))
                            }
                        }
                    }, speak={speechPlayer.speak(it)}, initial=selectedRecognitionMode)
            }.onFailure { Log.w(TAG,"Context routing unavailable; existing manual recognition preserved",it) }.getOrNull()
        }
        a1ShutdownExecutor = Executors.newSingleThreadExecutor { runnable ->''')
    text = replace(text, '    private fun speakRecognizedSentence() {', '    private fun speakRecognizedSentence() {\n        if(coordination?.hear()==true) return')
    text = replace(text, '    private fun renderPhraseAssist(state: PhraseAssistUiState) {', '    private fun renderPhraseAssist(state: PhraseAssistUiState) {\n        coordination?.context(state)')
    text = replace(text, '''                                val spelling = fingerspellRuntime
                                if (spelling?.fingerspellOwnsFrames == true)''', '''                                // Routing policy reads current visibility/idle only; Candidate01 and WORD are unchanged.
                                coordination?.observation(session.isReady,(0..1).any { s ->
                                    observation.handObserved[s] && observation.handJointValid[s].any { it } })
                                val spelling = fingerspellRuntime
                                if (spelling?.fingerspellOwnsFrames == true)''')
    text = replace(text, '''            val spelling = fingerspellRuntime?.snapshot
            if (spelling?.mode''', '''            if(r.recognitionEvidence!=null || r.recognition is com.example.apphear.pipeline.recognition.RecognitionState.Signing)
                coordination?.wordActivity(committed = r.recognitionEvidence != null)
            val spelling = fingerspellRuntime?.snapshot
            if (spelling?.mode''')
    text = replace(text, '    private fun renderFingerspell(s: FingerspellSnapshot) {', '    private fun renderFingerspell(s: FingerspellSnapshot) {\n        coordination?.recognitionChanged()')
    text = replace(text, '    override fun onStop() {', '    override fun onStop() {\n        coordination?.stopped()')
    text = replace(text, '''        selectedRecognitionMode = recognitionSettings.current()
        if (::cameraExecutor''', '''        selectedRecognitionMode = recognitionSettings.current()
        coordination?.started(selectedRecognitionMode)
        if (::cameraExecutor''')
    path.write_text(text, encoding="utf-8", errors="surrogateescape")
    print(json.dumps({"changed": [p for p,h in inventory.items() if sha(APP/p)!=h], "new_components": 7},indent=2))


if __name__ == "__main__":
    main()
