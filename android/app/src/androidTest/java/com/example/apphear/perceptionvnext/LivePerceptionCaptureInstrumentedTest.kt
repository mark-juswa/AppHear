package com.example.apphear.perceptionvnext

import android.content.Intent
import android.os.Debug
import android.os.SystemClock
import android.util.Log
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.fingerspelling.FingerspellRuntime
import com.example.apphear.fingerspelling.RecognitionMode
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

/** Drives the existing app only. Real camera observations and human actions, no injected evidence. */
class LivePerceptionCaptureInstrumentedTest {
    @Test fun captureMatchedScene() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val arguments = InstrumentationRegistry.getArguments()
        val mode = RecognitionMode.valueOf(arguments.getString("owner", "WORD"))
        val rear = arguments.getString("lens", "front") == "rear"
        val label = requireNotNull(arguments.getString("label"))
        require(label.matches(Regex("[a-zA-Z0-9_-]+")))
        val settings = RecognitionModeSettings(instrumentation.targetContext)
        val oldMode = settings.current()
        settings.select(mode)
        val samples = JSONArray()
        var activity: RecognitionActivity? = null
        try {
            val running = instrumentation.startActivitySync(Intent(instrumentation.targetContext,
                RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
            activity = running
            fun field(name: String): Any? = RecognitionActivity::class.java.getDeclaredField(name)
                .apply { isAccessible = true }.get(running)
            fun ready(): Boolean = field("fingerspellRuntime") != null &&
                !(field("cameraSwitching") as Boolean) && (field("cameraInputFrames") as Int) >= 8
            val deadline = SystemClock.elapsedRealtime() + 45000
            while (!ready() && SystemClock.elapsedRealtime() < deadline) Thread.sleep(100)
            assertTrue("Camera/model startup", ready())
            if (rear) {
                instrumentation.runOnMainSync { running.findViewById<android.view.View>(R.id.cameraToggle).performClick() }
                while (((field("frontCamera") as Boolean) || !ready()) &&
                    SystemClock.elapsedRealtime() < deadline) Thread.sleep(100)
            }
            assertEquals(!rear, field("frontCamera"))
            val runtime = field("fingerspellRuntime") as FingerspellRuntime
            assertEquals(mode, runtime.snapshot.mode)
            val started = SystemClock.elapsedRealtimeNanos()
            Log.i("AppHearV3Capture", "BEGIN label=$label owner=$mode rear=$rear elapsed_ns=$started")
            repeat(20) {
                Thread.sleep(1000)
                val row = JSONObject().put("elapsed_ns", SystemClock.elapsedRealtimeNanos())
                    .put("pss_kb", Debug.getPss()).put("native_heap_bytes", Debug.getNativeHeapAllocatedSize())
                    .put("java_heap_bytes", Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory())
                    .put("camera_callbacks", field("cameraInputFrames"))
                    .put("owner", runtime.snapshot.mode.name)
                    .put("spelling_preview", runtime.snapshot.preview).put("spelling_confirmed", runtime.snapshot.confirmed)
                    .put("current_letter", runtime.snapshot.currentLetter)
                instrumentation.runOnMainSync {
                    row.put("displayed_gloss", running.findViewById<TextView>(R.id.glossText).text.toString())
                    row.put("displayed_sentence", running.findViewById<TextView>(R.id.sentenceText).text.toString())
                }
                samples.put(row)
            }
            assertEquals("Exclusive owner must stay selected", mode, runtime.snapshot.mode)
            assertEquals("Lens must stay selected", !rear, field("frontCamera"))
            val end = SystemClock.elapsedRealtimeNanos()
            Log.i("AppHearV3Capture", "END label=$label elapsed_ns=$end")
            instrumentation.targetContext.filesDir.resolve("v3_live_$label.json").writeText(JSONObject()
                .put("schema_version", "apphear.v3.live_engineering_capture.v1")
                .put("label", label).put("owner", mode.name).put("rear", rear)
                .put("started_elapsed_ns", started).put("ended_elapsed_ns", end)
                .put("signer_status", "NONEXPERT_ENGINEERING_SMOKE")
                .put("accuracy_claim", "NONE").put("samples", samples).toString(2))
        } finally {
            activity?.let { running -> instrumentation.runOnMainSync { running.finish() } }
            settings.select(oldMode)
            instrumentation.waitForIdleSync()
        }
    }
}
