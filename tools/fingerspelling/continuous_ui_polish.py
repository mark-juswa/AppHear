"""Small presentation-only change; preserve frozen runtime, models and WORD branch."""
# Exact Kotlin migration literals keep the original source layout.
# ruff: noqa: E501

import json

from tools.fingerspelling.continuous_stage import NEW, OUT, sha


def main() -> None:
    src = NEW / "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt"
    test = (
        NEW
        / "android/app/src/androidTest/java/com/example/apphear/fingerspelling/ContinuousFingerspellInstrumentedTest.kt"
    )
    if (OUT / "ui_polish_before.json").exists():
        raise RuntimeError("UI change already applied; use the build wrapper.")
    before = {
        str(p.relative_to(NEW)): sha(p) for p in (NEW / "android/app/src").rglob("*") if p.is_file()
    }
    (OUT / "ui_polish_before.json").write_text(json.dumps(before, indent=2))
    text = src.read_text(encoding="utf-8")
    old = "private fun installFingerspellControls() {\n        val container"
    assert old in text
    text = text.replace(
        old,
        """private fun installFingerspellControls() {
        if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) {
            fingerspellRuntime?.snapshot?.let(::renderFingerspell)
            return
        }
        val container""",
        1,
    )
    old = """        if (active) {
            binding.glossText.text = s.preview.ifBlank"""
    assert old in text
    text = text.replace(
        old,
        """        if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) {
            // Hide only CURRENT SIGN's column in Fingerspell; restore it verbatim for WORD.
            (binding.glossText.parent as View).visibility = if (active) View.GONE else View.VISIBLE
            if (active) {
                binding.altText.visibility = View.GONE
                val spelling = s.confirmed + s.preview
                binding.sentenceText.text = spelling.ifBlank { getString(R.string.sentence_placeholder) }
                binding.sentenceText.contentDescription = if (s.preview.isNotEmpty())
                    "Detected spelling: $spelling. Tap Hear to review and confirm." else spelling
                updateSentenceCardVisibility()
            }
            return
        }
        if (active) {
            binding.glossText.text = s.preview.ifBlank""",
        1,
    )
    old = """            if (it.confirmed.isBlank()) Toast.makeText(this, "Confirm a spelling before speaking", Toast.LENGTH_SHORT).show()
            else speechPlayer.speak(it.confirmed)"""
    assert old in text
    text = text.replace(
        old,
        """            if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED && it.preview.isNotBlank()) {
                val draft = it.preview
                androidx.appcompat.app.AlertDialog.Builder(this)
                    .setTitle("Confirm spelling")
                    .setMessage(it.confirmed + draft)
                    .setPositiveButton("Confirm and hear") { _, _ ->
                        cameraExecutor.execute {
                            val runtime = fingerspellRuntime ?: return@execute
                            val current = runtime.snapshot
                            if (current.mode == RecognitionMode.FINGERSPELL && current.preview == draft && current.confirmed == it.confirmed) {
                                runtime.confirm()
                                val confirmed = runtime.snapshot.confirmed
                                runOnUiThread { if (!isFinishing && !isDestroyed) speechPlayer.speak(confirmed) }
                            } else runOnUiThread {
                                Toast.makeText(this, "Spelling changed. Tap Hear to review again.", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                    .setNegativeButton(android.R.string.cancel, null).show()
            } else if (it.confirmed.isBlank()) Toast.makeText(this, "No spelling to speak", Toast.LENGTH_SHORT).show()
            else speechPlayer.speak(it.confirmed)""",
        1,
    )
    src.write_text(text, encoding="utf-8", newline="\n")
    s = test.read_text()
    s = s.replace(
        'assertEquals("AMY",activity.findViewById<TextView>(R.id.glossText).text.toString())',
        """assertEquals("AMY",activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals(View.VISIBLE,activity.findViewById<View>(R.id.sentenceCard).visibility)
                assertEquals(View.GONE,(activity.findViewById<TextView>(R.id.glossText).parent as View).visibility)""",
    )
    s = s.replace(
        'assertFalse(buttons.containsKey("Start")); assertFalse(buttons.containsKey("Done"))',
        'assertTrue("No experimental controls on detection screen",buttons.isEmpty())',
    )
    s = s.replace(
        "assertEquals(before,word.sentenceText)\n            }.get",
        """assertEquals(before,word.sentenceText)
            }.get""",
    )
    s = s.replace(
        """            instrumentation.targetContext.filesDir.resolve("fingerspell_continuous_flow.json").writeText(""",
        """            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals(View.VISIBLE,(activity.findViewById<TextView>(R.id.glossText).parent as View).visibility)
            }
            instrumentation.targetContext.filesDir.resolve("fingerspell_continuous_flow.json").writeText(""",
    )
    test.write_text(s, encoding="utf-8", newline="\n")
    print(
        "Controls hidden; draft shown in RECOGNIZED; confirmation retained through Hear; WORD branch untouched."
    )


if __name__ == "__main__":
    main()
