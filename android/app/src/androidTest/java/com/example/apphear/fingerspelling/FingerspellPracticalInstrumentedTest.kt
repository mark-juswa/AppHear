package com.example.apphear.fingerspelling

import android.content.Intent
import android.view.View
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.perceptionvnext.PhoneProductionSession
import com.example.apphear.perceptionvnext.PhoneRawObservation
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/**
 * FINGERSPELL practical v1 on the real activity (debug build with -PfingerspellPractical=true).
 * Synthetic decisions drive ownership/lifecycle/UI only; no signing accuracy is claimed.
 * Run with `adb shell am instrument` (never connectedDebugAndroidTest, which uninstalls).
 */
class FingerspellPracticalInstrumentedTest {
    private fun observation(t: Double, hand: Boolean) = PhoneRawObservation(t.toInt(), t, 480, 640,
        Array(2) { FloatArray(42) { 100f } }, Array(2) { BooleanArray(21) { hand } }, Array(2) { FloatArray(21) { 1f } },
        floatArrayOf(if (hand) 1f else 0f, 0f), booleanArrayOf(hand, false), BooleanArray(2), Array(2) { FloatArray(3) },
        FloatArray(16), FloatArray(8), BooleanArray(8), false)

    @Test fun deleteRepeatReviewHoldLifecycleAndWordExclusivity() {
        assumeTrue("Practical flag off: locked baseline build", BuildConfig.FINGERSPELL_PRACTICAL_ENABLED)
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val settings = RecognitionModeSettings(instrumentation.targetContext)
        settings.select(RecognitionMode.FINGERSPELL)
        val activity = instrumentation.startActivitySync(Intent(instrumentation.targetContext,
            RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        fun field(name: String) = RecognitionActivity::class.java.getDeclaredField(name).apply { isAccessible = true }.get(activity)
        try {
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(45)
            while (field("fingerspellRuntime") == null && System.nanoTime() < deadline) Thread.sleep(100)
            val runtime = checkNotNull(field("fingerspellRuntime") as? FingerspellRuntime)
            while (runtime.snapshot.mode != RecognitionMode.FINGERSPELL && System.nanoTime() < deadline) Thread.sleep(50)
            while (((field("cameraSwitching") as Boolean) || (field("cameraInputFrames") as Int) < 1) &&
                System.nanoTime() < deadline) Thread.sleep(50)
            assertTrue(runtime.practicalMode)
            val executor = field("cameraExecutor") as ExecutorService
            val word = field("phoneSession") as PhoneProductionSession
            val wordBefore = word.sentenceText
            val engine = FingerspellRuntime::class.java.getDeclaredField("continuous").apply { isAccessible = true }.get(runtime) as ContinuousFingerspell
            val policy = ContinuousFingerspell::class.java.getDeclaredField("policy").apply { isAccessible = true }.get(engine) as HeldLetterPolicy
            fun calls() = ContinuousFingerspell::class.java.getDeclaredField("inferenceCalls").apply { isAccessible = true }.getInt(engine)
            fun emit() = ContinuousFingerspell::class.java.getDeclaredMethod("emit", String::class.java).apply { isAccessible = true }.invoke(engine, null)
            fun hold(letter: String, t: Double) {
                val e = policy.epoch
                policy.accept(e, t, letter); policy.accept(e, t + 500, letter); assertTrue(policy.accept(e, t + 1000, letter))
            }
            fun onCamera(block: () -> Unit) { executor.submit(block).get(10, TimeUnit.SECONDS); instrumentation.waitForIdleSync() }
            fun text(id: Int) = activity.findViewById<TextView>(id).text.toString()
            fun visible(id: Int) = activity.findViewById<View>(id).visibility

            onCamera { runtime.pause(); policy.reset(); hold("M", 0.0); hold("A", 2000.0); hold("X", 4000.0); emit() }
            instrumentation.runOnMainSync {
                assertEquals("MAX", text(R.id.sentenceText))
                assertEquals(View.VISIBLE, visible(R.id.fingerspellPracticalPanel))
                assertEquals("Repeat X", text(R.id.fingerspellRepeat))
                assertTrue(activity.findViewById<View>(R.id.fingerspellDone).isEnabled)
                assertEquals("Delete lives in the pull-up panel", View.VISIBLE, visible(R.id.fingerspellDelete))
                assertTrue(activity.findViewById<View>(R.id.fingerspellDelete).isEnabled)
            }
            // One wrong letter: one tap, no re-spelling.
            onCamera { runtime.deleteLast() }
            instrumentation.runOnMainSync { assertEquals("MA", text(R.id.sentenceText)) }
            // Explicit double letter.
            onCamera { runtime.repeatLast() }
            instrumentation.runOnMainSync { assertEquals("MAA", text(R.id.sentenceText)) }
            // Interruption keeps the draft; same-owner reselect keeps it too. Then the review hold:
            // frames cannot reach the model and the draft cannot change. One executor block, so no
            // real camera frame can interleave.
            onCamera {
                runtime.pause(); assertEquals("MAA", runtime.snapshot.preview)
                runtime.select(RecognitionMode.FINGERSPELL); assertEquals("MAA", runtime.snapshot.preview)
                runtime.holdForReview(); assertTrue(runtime.snapshot.reviewing)
                val before = calls()
                repeat(20) { engine.consume(observation(50000.0 + it * 150.0, true)) }
                assertEquals(before, calls()); assertEquals("MAA", runtime.snapshot.preview)
                runtime.deleteLast(); assertEquals("Delete is disabled while reviewing", "MAA", runtime.snapshot.preview)
                runtime.resumeAfterReview(); assertFalse(runtime.snapshot.reviewing)
            }
            instrumentation.runOnMainSync { assertTrue(activity.findViewById<View>(R.id.fingerspellDone).isEnabled) }
            // WORD owner: panel gone, no fingerspell inference, WORD sentence untouched.
            onCamera {
                runtime.select(RecognitionMode.WORD)
                val n = calls()
                repeat(15) { engine.consume(observation(60000.0 + it * 200.0, true)) }
                assertEquals(n, calls()); assertFalse(runtime.fingerspellOwnsFrames)
                assertEquals(wordBefore, word.sentenceText)
            }
            instrumentation.runOnMainSync {
                assertEquals(View.GONE, visible(R.id.fingerspellPracticalPanel))
                assertEquals(View.GONE, visible(R.id.fingerspellDelete))
                assertEquals(View.VISIBLE, visible(R.id.clearButton))
            }
            // Re-entering FINGERSPELL starts a fresh word (no stale confirmed text).
            onCamera {
                runtime.select(RecognitionMode.FINGERSPELL)
                assertEquals("", runtime.snapshot.preview); assertEquals("", runtime.snapshot.confirmed)
            }
            instrumentation.targetContext.filesDir.resolve("fingerspell_practical_flow.json").writeText(
                JSONObject().put("status", "PRACTICAL_V1_FLOW_PASS").put("delete", true).put("repeat", true)
                    .put("draft_survives_pause", true).put("review_hold_blocks_inference", true)
                    .put("word_sentence_preserved", true).put("word_mode_fingerspell_calls", 0)
                    .put("fresh_word_on_reentry", true).put("synthetic", true).put("accuracy_claim", "NONE").toString(2))
        } finally {
            settings.select(RecognitionMode.WORD)
            instrumentation.runOnMainSync { activity.finish() }; instrumentation.waitForIdleSync()
        }
    }
}
