package com.example.apphear

import android.os.SystemClock
import android.content.Intent
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
        // Splash can route a fresh emulator to onboarding/login, not MainActivity.
        // Launch inside the instrumented app on its main thread; this tests the
        // existing Text-to-Sign screen without changing the production launcher.
        i.runOnMainSync {
            context.startActivity(Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
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
                // The collapsed/Text/Talk controls are part of normal input.
                // A hidden Sign It in Talk mode replays the previous plan.
                val textMode=activity.findViewById<View>(R.id.mode_text_button)
                val shortcut=activity.findViewById<View>(R.id.mode_text_shortcut)
                if(textMode.isShown) assertTrue(textMode.performClick())
                else if(shortcut.isShown) assertTrue(shortcut.performClick())
                val input=activity.findViewById<EditText>(R.id.input_text)
                assertTrue("Text input is visible before submitting",input.isShown)
                input.setText(text)
                assertTrue(activity.findViewById<View>(R.id.sign_it_button).performClick())
                assertSame(viewer, activity.findViewById(R.id.avatarWebView))
            }
            for (text in listOf("NICOLE", "NAME", "YOU", "ANNA", "JAZZ", "ACTION", "HELLO NICOLE",
                    "ME", "YES", "LOVE", "HELP", "COOK", "BECOME", "MONEY", "NEW", "SOME", "DAY",
                    "HELLO LOVE", "MY NAME", "YOUR NAME", "I LOVE YOU", "I", "ME YOU", "YOU ME",
                    "YOU NICOLE", "ME NICOLE", "BEST", "BETTER", "DIVORCE", "FROM", "GRANDMA",
                    "GRANDPA", "HERE", "PARENTS", "PREFER", "SINGLE", "HELLO GRANDMA NICOLE") +
                    ('A'..'Z').map { it.toString() }) {
                val start = SystemClock.uptimeMillis()
                submit(text)
                val result = await("$text completes") { it.contains("Complete") }
                i.runOnMainSync { assertEquals(text,activity.findViewById<TextView>(R.id.signed_text).text.toString()) }
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
