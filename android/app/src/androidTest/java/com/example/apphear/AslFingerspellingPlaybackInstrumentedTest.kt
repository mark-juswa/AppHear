package com.example.apphear

import android.os.SystemClock
import android.view.View
import android.widget.EditText
import android.widget.TextView
import androidx.navigation.fragment.NavHostFragment
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Exercises normal input/buttons; pose/weight inspection uses the separate debug CDP tool. */
class AslFingerspellingPlaybackInstrumentedTest {
    @Test fun normalInputCompletesSpellingMixedWordsAndCancellationOnOneViewer() {
        assumeTrue(BuildConfig.ASL_ASSET_PILOT_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED)
        val i = InstrumentationRegistry.getInstrumentation()
        val context = i.targetContext
        // Avoid startActivitySync's global-idle gate: an animated WebView and
        // the device's speech-service activity need not make the main queue idle.
        val monitor = i.addMonitor(MainActivity::class.java.name, null, false)
        // Use the exported launcher as a foreground shell request. Some phones
        // deny background startActivity from an instrumentation-owned process.
        i.uiAutomation.executeShellCommand("am start -n com.example.apphear/.SplashActivity").close()
        val activity = i.waitForMonitorWithTimeout(monitor, 20_000) as? MainActivity
            ?: throw AssertionError("MainActivity did not open")
        i.removeMonitor(monitor)
        val evidence = JSONArray()
        try {
            i.runOnMainSync {
                (activity.supportFragmentManager.findFragmentById(R.id.app_shell_nav_host) as NavHostFragment)
                    .navController.navigate(R.id.textToAslFragment)
            }
            fun status(): String {
                var value = ""
                i.runOnMainSync { value = activity.findViewById<TextView>(R.id.current_progress_text).text.toString() }
                return value
            }
            fun await(label: String, predicate: (String) -> Boolean): String {
                val deadline = SystemClock.uptimeMillis() + 90_000
                while (SystemClock.uptimeMillis() < deadline) {
                    val value = status()
                    if (predicate(value)) return value
                    SystemClock.sleep(50) // Test polling; production uses completion callbacks.
                }
                throw AssertionError("$label: ${status()}")
            }
            await("Viewer ready") { it == "Ready" }
            var viewer: View? = null
            i.runOnMainSync { viewer = activity.findViewById(R.id.avatarWebView) }
            fun submit(text: String) = i.runOnMainSync {
                activity.findViewById<EditText>(R.id.input_text).setText(text)
                assertTrue(activity.findViewById<View>(R.id.sign_it_button).performClick())
                assertSame(viewer, activity.findViewById(R.id.avatarWebView))
            }
            for (text in listOf("NICOLE", "NAME", "YOU", "YOU ALL", "ALL OF YOU", "MOM", "DAD", "OKAY", "ANNA", "JAZZ", "HELLO NICOLE", "LOVE", "HELP")) {
                val start = SystemClock.uptimeMillis()
                submit(text)
                val result = await("$text completes") { it.contains("Complete") }
                if (text in listOf("NICOLE", "ANNA", "JAZZ", "HELLO NICOLE")) assertTrue(result.contains("fingerspelling"))
                evidence.put(JSONObject().put("input", text).put("status", result)
                    .put("elapsedMs", SystemClock.uptimeMillis() - start))
            }
            submit("NICOLE")
            await("First request active") { it.contains("1 / 6") }
            submit("ANNA")
            await("Replacement complete") { it.contains("Complete") && it.contains("anna") }
            i.runOnMainSync { assertSame(viewer, activity.findViewById(R.id.avatarWebView)) }
            File(context.filesDir, "fingerspelling_playback_device.json").writeText(evidence.toString(2))
        } finally {
            i.runOnMainSync { activity.finish() }
        }
    }
}
