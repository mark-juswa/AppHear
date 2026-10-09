"""Restore live Fingerspell CURRENT SIGN separately from accumulated RECOGNIZED text."""
# Kotlin migration literals retain the existing layout.
# ruff: noqa: E501

import json

from tools.fingerspelling.camera_input_port import APP, JAVA, ROOT, sha

OUT = ROOT / "artifacts/fingerspelling_current_sign_01"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "before.json").exists():
        raise RuntimeError("Display correction already staged; do not reapply")
    before = {
        str(p.relative_to(APP)).replace("\\", "/"): sha(p)
        for p in (APP / "android/app/src").rglob("*")
        if p.is_file()
    }
    (OUT / "before.json").write_text(json.dumps(before, indent=2))
    p = APP / JAVA / "fingerspelling/FingerspellRuntime.kt"
    s = p.read_text().replace(
        """val preview: String, val confirmed: String, val observations: Int, val message: String)""",
        """val preview: String, val confirmed: String, val observations: Int, val message: String,
    val currentLetter: String = "")""",
        1,
    )
    p.write_text(s)
    p = APP / JAVA / "fingerspelling/HeldLetterPolicy.kt"
    s = p.read_text().replace(
        """    var preview = ""; private set""",
        """    var preview = ""; private set
    // Presentation-only latest valid decode. This does not control accumulation or acceptance.
    var currentLetter = ""; private set""",
        1,
    )
    s = s.replace(
        """        resetCandidate()
        if (!keepLatch)""",
        """        resetCandidate(); currentLetter = ""
        if (!keepLatch)""",
        1,
    )
    s = s.replace(
        """        val usable = usable(observation)
        if (usable)""",
        """        val usable = usable(observation)
        if (!usable) currentLetter = ""
        if (usable)""",
        1,
    )
    s = s.replace(
        """        lastDecision = timestampMs
        if (letter.isEmpty()""",
        """        lastDecision = timestampMs
        currentLetter = letter
        if (letter.isEmpty()""",
        1,
    )
    p.write_text(s)
    p = APP / JAVA / "fingerspelling/ContinuousFingerspell.kt"
    s = p.read_text().replace(
        """            policy.preview, confirmed, policy.windowCount, text))""",
        """            policy.preview, confirmed, policy.windowCount, text,
            currentLetter = if(ownsFrames) policy.currentLetter else ""))""",
        1,
    )
    p.write_text(s)
    p = APP / JAVA / "RecognitionActivity.kt"
    s = p.read_text().replace(
        """            // Hide only CURRENT SIGN's column in Fingerspell; restore it verbatim for WORD.
            (binding.glossText.parent as View).visibility = if (active) View.GONE else View.VISIBLE
            if (active) {
                binding.altText.visibility = View.GONE""",
        """            // CURRENT SIGN is the live letter; RECOGNIZED is the accumulated spelling.
            (binding.glossText.parent as View).visibility = View.VISIBLE
            if (active) {
                binding.glossText.text = s.currentLetter.ifBlank { getString(R.string.gloss_placeholder) }
                binding.altText.visibility = View.GONE""",
        1,
    )
    p.write_text(s)
    p = APP / "android/app/src/test/java/com/example/apphear/fingerspelling/HeldLetterPolicyTest.kt"
    s = p.read_text().replace(
        """    @Test fun settingsDefaultAndDisabledFallback()""",
        """    @Test fun currentLetterIsSeparateFromConstructedSpelling() {
        val p=HeldLetterPolicy(config)
        val first=p.epoch
        assertFalse(p.accept(first,0.0,"A"))
        assertEquals("A",p.currentLetter); assertEquals("",p.preview)
        p.accept(first,500.0,"A"); assertTrue(p.accept(first,1000.0,"A"))
        assertEquals("A",p.currentLetter); assertEquals("A",p.preview)
        val next=p.epoch
        assertFalse(p.accept(next,1500.0,"M"))
        assertEquals("M",p.currentLetter); assertEquals("A",p.preview)
        assertFalse(p.accept(first,1600.0,"Z")) // stale result must not change either display.
        assertEquals("M",p.currentLetter); assertEquals("A",p.preview)
        p.observe(common(2000.0,false))
        assertEquals("",p.currentLetter); assertEquals("A",p.preview)
        p.observe(common(2200.0))
        assertFalse(p.accept(next,2300.0,""))
        assertEquals("",p.currentLetter); assertEquals("A",p.preview)
        p.reset(); assertEquals("",p.currentLetter); assertEquals("",p.preview)
    }
    @Test fun settingsDefaultAndDisabledFallback()""",
        1,
    )
    p.write_text(s)
    p = (
        APP
        / "android/app/src/androidTest/java/com/example/apphear/fingerspelling/ContinuousFingerspellInstrumentedTest.kt"
    )
    s = p.read_text().replace(
        """                emit(); assertEquals("AMY",runtime.snapshot.preview); assertEquals("",runtime.snapshot.confirmed)""",
        """                emit(); assertEquals("AMY",runtime.snapshot.preview); assertEquals("",runtime.snapshot.confirmed)
                assertEquals("Y",runtime.snapshot.currentLetter)""",
        1,
    )
    s = s.replace(
        """                assertEquals(View.GONE,(activity.findViewById<TextView>(R.id.glossText).parent as View).visibility)""",
        """                assertEquals(View.VISIBLE,(activity.findViewById<TextView>(R.id.glossText).parent as View).visibility)
                assertEquals("Y",activity.findViewById<TextView>(R.id.glossText).text.toString())""",
        1,
    )
    needle = """            executor.submit {
                runtime.confirm(); assertEquals("AMY",runtime.snapshot.confirmed)"""
    assert needle in s
    s = s.replace(
        needle,
        """            executor.submit {
                assertFalse(policy.accept(policy.epoch,6500.0,"B")); emit()
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals("B",activity.findViewById<TextView>(R.id.glossText).text.toString())
                assertEquals("AMY",activity.findViewById<TextView>(R.id.sentenceText).text.toString())
            }
"""
        + needle,
        1,
    )
    p.write_text(s)
    changes = {p: sha(APP / p) for p, h in before.items() if sha(APP / p) != h}
    (OUT / "changes.json").write_text(json.dumps(changes, indent=2))
    print(json.dumps(changes, indent=2))


if __name__ == "__main__":
    main()
