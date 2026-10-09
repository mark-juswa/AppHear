"""Stage long-spelling regression checks without changing recognition semantics."""
# ruff: noqa: E501
import json

from tools.fingerspelling.camera_input_port import APP, ROOT, sha

OUT = ROOT / "artifacts/fingerspelling_long_spelling_01"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "before.json").exists():
        raise RuntimeError("Checks already staged")
    inventory = {
        str(p.relative_to(APP)).replace("\\", "/"): sha(p)
        for p in (APP / "android/app/src").rglob("*")
        if p.is_file()
    }
    inventory["android/app/build.gradle.kts"] = sha(APP / "android/app/build.gradle.kts")
    (OUT / "before.json").write_text(json.dumps(inventory, indent=2))
    p = APP / "android/app/src/test/java/com/example/apphear/fingerspelling/HeldLetterPolicyTest.kt"
    s = p.read_text()
    needle = '    @Test fun settingsDefaultAndDisabledFallback()'
    assert needle in s
    s = s.replace(needle, '''    @Test fun spellingContinuesBeyondThreeAndObservationWindowSize() {
        val p=HeldLetterPolicy(config)
        val text="ABCDEFGHIJKLMNOPQRSTUVWXYZ".repeat(4)
        for ((index,c) in text.withIndex()) {
            assertTrue(stable(p,c.toString(),index*2000.0))
            assertEquals(text.substring(0,index+1),p.preview)
        }
        assertEquals(104,p.preview.length)
        assertEquals("Z",p.currentLetter)
    }
''' + needle)
    p.write_text(s)
    p = APP / "android/app/src/androidTest/java/com/example/apphear/fingerspelling/ContinuousFingerspellInstrumentedTest.kt"
    s = p.read_text()
    needle = '''            executor.submit {
                runtime.confirm(); assertEquals("AMY",runtime.snapshot.confirmed)'''
    assert needle in s
    s = s.replace(needle, '''            val longText="ABCDEFGHIJKLMNOPQRSTUVWXYZ".repeat(4)
            executor.submit {
                policy.reset()
                for((index,c) in longText.withIndex()) {
                    val e=policy.epoch; val t=10000.0+index*2000.0
                    policy.accept(e,t,c.toString()); policy.accept(e,t+500,c.toString())
                    assertTrue(policy.accept(e,t+1000,c.toString()))
                }
                emit(); assertEquals(longText,runtime.snapshot.preview)
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                val text=activity.findViewById<TextView>(R.id.sentenceText)
                val layout=checkNotNull(text.layout)
                val report=JSONObject().put("text",text.text.toString()).put("length",text.length())
                    .put("lines",layout.lineCount).put("width",text.width).put("height",text.height)
                    .put("layout_height",layout.height).put("last_line_end",layout.getLineEnd(layout.lineCount-1))
                    .put("max_lines",text.maxLines).put("accuracy_claim","NONE")
                instrumentation.targetContext.filesDir.resolve("fingerspell_long_text.json").writeText(report.toString(2))
                assertEquals(longText,text.text.toString())
                assertEquals(longText.length,layout.getLineEnd(layout.lineCount-1))
                assertTrue("No text ellipsized",(0 until layout.lineCount).all{layout.getEllipsisCount(it)==0})
                assertTrue("All lines fit the recognized view",layout.height<=text.height-text.compoundPaddingTop-text.compoundPaddingBottom)
                assertEquals("Z",activity.findViewById<TextView>(R.id.glossText).text.toString())
            }
            executor.submit {
                policy.reset()
                for((index,c) in "AMY".withIndex()) {
                    val e=policy.epoch; val t=300000.0+index*2000.0
                    policy.accept(e,t,c.toString()); policy.accept(e,t+500,c.toString()); policy.accept(e,t+1000,c.toString())
                }
                emit()
            }.get(10,TimeUnit.SECONDS)
''' + needle)
    p.write_text(s)
    print("Long-spelling checks staged; production unchanged")


if __name__ == "__main__":
    main()
