"""Apply only isolated continuous fingerspell/UI settings changes to the new worktree."""
# Exact Kotlin migration literals intentionally retain their original line layout.
# ruff: noqa: E501

import json
import shutil

from tools.fingerspelling.continuous_stage import NEW, OUT, ROOT


def change(relative, old, new):
    p = NEW / relative
    s = p.read_text(encoding="utf-8")
    assert old in s, (relative, old[:100])
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline="\n")


def main():
    kotlin = "android/app/src/main/java/com/example/apphear/"
    if "continuousEnabled:" in (NEW / kotlin / "fingerspelling/FingerspellRuntime.kt").read_text():
        raise RuntimeError(
            "Already ported: use android_continuous_build.ps1; do not restage existing work."
        )
    for name in ("HeldLetterPolicy", "ContinuousFingerspell"):
        shutil.copy2(
            ROOT / f"tools/fingerspelling/continuous_android/{name}.kt",
            NEW / kotlin / f"fingerspelling/{name}.kt",
        )
    shutil.copy2(
        ROOT / "tools/fingerspelling/continuous_android/RecognitionModeSettings.kt",
        NEW / kotlin / "data/settings/RecognitionModeSettings.kt",
    )
    shutil.copy2(
        ROOT / "tools/fingerspelling/continuous_android/HeldLetterPolicyTest.kt",
        NEW
        / "android/app/src/test/java/com/example/apphear/fingerspelling/HeldLetterPolicyTest.kt",
    )
    policy = {
        "schema_version": "apphear.fingerspelling.held_letter_policy.v1",
        "window_ms": 4000,
        "minimum_span_ms": 1000,
        "minimum_usable": 4,
        "inference_interval_ms": 500,
        "stable_decodes": 3,
        "stable_span_ms": 1000,
        "rearm_missing_ms": 800,
        "rearm_missing_observations": 3,
        "maximum_observations": 64,
        "timing_status": "ENGINEERING_DEFAULTS_NOT_ACCURACY_CALIBRATED",
        "capture": "AUTOMATIC_HELD_LETTER",
        "confirmation": "REQUIRED",
    }
    (OUT / "android_assets/fingerspelling/continuous_policy.json").write_text(
        json.dumps(policy, indent=2)
    )
    runtime = kotlin + "fingerspelling/FingerspellRuntime.kt"
    change(
        runtime,
        "resetWord: () -> Unit, private val publish: (FingerspellSnapshot) -> Unit,",
        "resetWord: () -> Unit, private val publish: (FingerspellSnapshot) -> Unit,\n    continuousEnabled: Boolean = false, dispatch: ((() -> Unit) -> Unit) = { it() },",
    )
    change(
        runtime,
        "val fingerspellOwnsFrames get() = owner.mode == RecognitionMode.FINGERSPELL",
        "private val continuous = if (continuousEnabled) ContinuousFingerspell(context,models,resetWord,dispatch) {\n        snapshot = it; publish(it)\n    } else null\n    val continuousMode get() = continuous != null\n    val fingerspellOwnsFrames get() = continuous?.ownsFrames ?: (owner.mode == RecognitionMode.FINGERSPELL)",
    )
    for signature, action in (
        ("fun select(mode: RecognitionMode) {", "select(mode)"),
        ("fun confirm() {", "confirm()"),
        ("fun retry() {", "retry()"),
        ("fun clear() {", "clear()"),
        ("fun pause() {", "pause()"),
    ):
        change(
            runtime,
            signature,
            signature + f"\n        continuous?.let {{ it.{action}; return }}\n       ",
        )
    change(
        runtime,
        "fun consume(observation: PhoneRawObservation, image: ImageProxy) {",
        "fun consume(observation: PhoneRawObservation, image: ImageProxy) {\n        continuous?.let { it.consume(observation); return }",
    )
    change(runtime, "fun start() {", "fun start() {\n        if (continuousMode) return")
    change(runtime, "fun finish() {", "fun finish() {\n        if (continuousMode) return")
    change(
        runtime, "if(owner.mode!=RecognitionMode.WORD) return", "if(fingerspellOwnsFrames) return"
    )
    change(
        runtime,
        "override fun close() { session.cancel(); models.close() }",
        "override fun close() { if (continuous != null) continuous.close() else { session.cancel(); models.close() } }",
    )
    activity = kotlin + "RecognitionActivity.kt"
    change(
        activity,
        "import com.example.apphear.fingerspelling.RecognitionMode",
        "import com.example.apphear.data.settings.RecognitionModeSettings\nimport com.example.apphear.fingerspelling.RecognitionMode",
    )
    change(
        activity,
        "private var fingerspellRuntime: FingerspellRuntime? = null",
        "@Volatile private var fingerspellRuntime: FingerspellRuntime? = null\n    private val recognitionSettings by lazy { RecognitionModeSettings(this) }\n    @Volatile private var selectedRecognitionMode = RecognitionMode.WORD",
    )
    change(
        activity,
        "setContentView(binding.root)",
        "setContentView(binding.root)\n        selectedRecognitionMode = recognitionSettings.current()",
    )
    change(
        activity,
        "spelling?.recordWordCadence(observation)\n                                    false",
        "if (spelling == null && selectedRecognitionMode == RecognitionMode.FINGERSPELL) true\n                                    else { spelling?.recordWordCadence(observation); false }",
    )
    change(
        activity,
        "{ frameAnalyzer.resetTemporalSession() }, ::onFingerspell)",
        "{ frameAnalyzer.resetTemporalSession() }, ::onFingerspell,\n                        continuousEnabled = BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED,\n                        dispatch = { task -> if (!cameraExecutor.isShutdown) cameraExecutor.execute { task() } })",
    )
    change(
        activity,
        "installFingerspellControls()\n                }",
        'installFingerspellControls()\n                    cameraExecutor.execute { fingerspellRuntime?.select(selectedRecognitionMode) }\n                } else if (selectedRecognitionMode == RecognitionMode.FINGERSPELL) {\n                    renderRuntimeError("Fingerspell unavailable", "Select WORD in Settings to use word recognition.")\n                }',
    )
    change(
        activity,
        'text = "One attempt: Start → spell → Done → review → Use"',
        'text = if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) "Hold one letter until it appears. Lower your hand to repeat a letter. Review, then Use." else "One attempt: Start → spell → Done → review → Use"',
    )
    change(
        activity,
        '"WORD" -> runtime.select(RecognitionMode.WORD)\n                            "FINGERSPELL" -> runtime.select(RecognitionMode.FINGERSPELL)',
        '"WORD", "FINGERSPELL" -> {\n                                val mode = RecognitionMode.valueOf(label)\n                                runtime.select(mode)\n                                selectedRecognitionMode = mode\n                                recognitionSettings.select(mode)\n                            }',
    )
    change(
        activity,
        'row("WORD", "FINGERSPELL"); row("Start", "Done"); row("Use", "Retry", "Clear")',
        'row("WORD", "FINGERSPELL")\n        if (!BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) row("Start", "Done")\n        row("Use", "Retry", "Clear")',
    )
    change(
        activity,
        'fingerspellButtons["WORD"]?.isEnabled = active && !busy',
        'fingerspellButtons["WORD"]?.isEnabled = active && (!busy || BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED)',
    )
    change(
        activity,
        "super.onStart()\n        if (a1Active",
        "super.onStart()\n        selectedRecognitionMode = recognitionSettings.current()\n        if (::cameraExecutor.isInitialized && fingerspellRuntime != null && !cameraExecutor.isShutdown) {\n            cameraExecutor.execute { fingerspellRuntime?.select(selectedRecognitionMode) }\n        }\n        if (a1Active",
    )
    gradle = "android/app/build.gradle.kts"
    change(
        gradle,
        'val fingerspellDebug = providers.gradleProperty("fingerspell")',
        'val fingerspellContinuous = providers.gradleProperty("fingerspellContinuous").map { it.equals("true",ignoreCase=true) }.getOrElse(false)\n    val fingerspellDebug = providers.gradleProperty("fingerspell")',
    )
    change(
        gradle,
        'buildConfigField("boolean", "FINGERSPELL_EXPERIMENT_ENABLED", fingerspellDebug.toString())',
        'buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", (fingerspellDebug && fingerspellContinuous).toString())\n            buildConfigField("boolean", "FINGERSPELL_EXPERIMENT_ENABLED", fingerspellDebug.toString())',
    )
    change(
        gradle,
        'buildConfigField("boolean", "FINGERSPELL_EXPERIMENT_ENABLED", "false")',
        'buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", "false")\n            buildConfigField("boolean", "FINGERSPELL_EXPERIMENT_ENABLED", "false")',
    )
    settings = kotlin + "ui/settings/SettingsContent.kt"
    change(
        settings,
        "private var characterDialog: AlertDialog? = null",
        "private var characterDialog: AlertDialog? = null\n    private var recognitionDialog: AlertDialog? = null",
    )
    change(
        settings,
        "setupCharacterChoice(view)",
        "setupCharacterChoice(view)\n        setupRecognitionChoice()",
    )
    change(
        settings,
        "private fun renderSettings(view: View) {",
        """private fun setupRecognitionChoice() {
        val settings = com.example.apphear.data.settings.RecognitionModeSettings(context)
        val row = view.findViewById<View>(R.id.recognitionModeRow)
        row.isVisible = settings.selectionAvailable
        if (!settings.selectionAvailable) return
        val choices = com.example.apphear.fingerspelling.RecognitionMode.entries
        val labels = arrayOf(context.getString(R.string.recognition_mode_word), context.getString(R.string.recognition_mode_fingerspell))
        val value = view.findViewById<TextView>(R.id.recognitionModeValue)
        fun renderChoice() {
            value.text = labels[choices.indexOf(settings.current())]
            row.contentDescription = context.getString(R.string.recognition_mode_accessibility, value.text)
        }
        renderChoice()
        row.setOnClickListener {
            recognitionDialog?.dismiss()
            recognitionDialog = AlertDialog.Builder(context).setTitle(R.string.recognition_mode_title)
                .setSingleChoiceItems(labels, choices.indexOf(settings.current())) { dialog,index ->
                    settings.select(choices[index]); renderChoice(); dialog.dismiss()
                }.setNegativeButton(android.R.string.cancel,null).show()
        }
    }

    private fun renderSettings(view: View) {""",
    )
    change(
        settings,
        "characterDialog = null",
        "characterDialog = null\n        recognitionDialog?.dismiss(); recognitionDialog = null",
    )
    row = NEW / "android/app/src/main/res/layout/row_setting_asl_character.xml"
    content = (
        row.read_text()
        .replace("aslCharacter", "recognitionMode")
        .replace("asl_character_title", "recognition_mode_title")
        .replace("asl_character_coverage", "recognition_mode_body")
        .replace("asl_character_original", "recognition_mode_word")
    )
    (row.parent / "row_setting_recognition_mode.xml").write_text(content)
    change(
        "android/app/src/main/res/layout/fragment_settings.xml",
        '<include layout="@layout/row_setting_asl_character"',
        '<include layout="@layout/row_setting_recognition_mode" />\n            <include layout="@layout/row_setting_asl_character"',
    )
    change(
        "android/app/src/main/res/layout/fragment_profile.xml",
        '<include layout="@layout/row_setting_asl_character"',
        '<include layout="@layout/row_setting_recognition_mode" />\n                <include layout="@layout/row_setting_asl_character"',
    )
    change(
        kotlin + "ui/profile/ProfileFragment.kt",
        "if (AslCharacterSettings(requireContext()).selectionAvailable || AccountServices.enabled) {",
        "if (AslCharacterSettings(requireContext()).selectionAvailable || AccountServices.enabled ||\n            com.example.apphear.data.settings.RecognitionModeSettings(requireContext()).selectionAvailable) {",
    )
    change(
        "android/app/src/main/res/values/strings.xml",
        "</resources>",
        """    <string name="recognition_mode_title">Recognition mode</string>
    <string name="recognition_mode_body">Only the selected mode recognizes signs. Fingerspell uses automatic held letters with confirmation.</string>
    <string name="recognition_mode_word">WORD</string>
    <string name="recognition_mode_fingerspell">FINGERSPELL · experimental</string>
    <string name="recognition_mode_accessibility">Recognition mode: %1$s</string>
</resources>""",
    )
    print(
        "Continuous runtime, isolated Settings choice and debug flag installed; frozen math and models unchanged."
    )


if __name__ == "__main__":
    main()
