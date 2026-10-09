package com.example.apphear

import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.widget.EditText
import android.widget.TextView
import android.view.View
import androidx.navigation.fragment.NavHostFragment
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.data.settings.AslCharacterSettings
import com.example.apphear.domain.texttoasl.AslCharacterChoice
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Real screen/engine regression; requires a device with working WebGL. */
class TextToAslSequenceInstrumentedTest {
    @Test fun existingButtonsSequenceRepeatAndReportUnknownWithoutReplacingWebView() {
        assumeTrue(BuildConfig.ASL_ASSET_PILOT_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED)
        val i = InstrumentationRegistry.getInstrumentation()
        val context = i.targetContext
        val prefs = context.getSharedPreferences("text_to_asl", Context.MODE_PRIVATE)
        val previous = prefs.getString("character", null)
        AslCharacterSettings(context).select(AslCharacterChoice.ORIGINAL)
        val activity = i.startActivitySync(Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        try {
            i.runOnMainSync {
                (activity.supportFragmentManager.findFragmentById(R.id.app_shell_nav_host) as NavHostFragment)
                    .navController.navigate(R.id.textToAslFragment)
            }
            fun status(): String {
                var text = ""
                i.runOnMainSync { text = activity.findViewById<TextView>(R.id.current_progress_text)?.text?.toString().orEmpty() }
                return text
            }
            fun awaitStatus(label: String, predicate: (String) -> Boolean) {
                val deadline = SystemClock.uptimeMillis() + 60_000
                while (SystemClock.uptimeMillis() < deadline) {
                    if (predicate(status())) return
                    SystemClock.sleep(50) // Test polling only; production sequencing uses completion callbacks.
                }
                fail("$label: ${status()}")
            }
            awaitStatus("Existing screen ready") { it == "Ready" }
            var originalView: View? = null
            i.runOnMainSync { originalView = activity.findViewById(R.id.avatarWebView) }
            fun submit(text: String) = i.runOnMainSync {
                activity.findViewById<EditText>(R.id.input_text).setText(text)
                assertTrue(activity.findViewById<View>(R.id.sign_it_button).performClick())
                assertSame(originalView, activity.findViewById(R.id.avatarWebView))
            }
            for (text in listOf("hello beautiful", "HELLO BEAUTIFUL", "hello, beautiful!")) {
                submit(text)
                awaitStatus("HELLO first") { it.contains("1 / 2") }
                awaitStatus("BEAUTIFUL second") { it.contains("2 / 2") }
                awaitStatus("Queue complete") { it.contains("Complete") && !it.contains("Unsupported") }
            }
            i.runOnMainSync { assertTrue(activity.findViewById<View>(R.id.replay_button).performClick()) }
            awaitStatus("Repeat complete") { it.contains("Complete") }
            submit("hello unknownword")
            awaitStatus("Individual unknown reported") { it.contains("Complete") && it.contains("unknownword") }
            submit("What is your name?")
            awaitStatus("Incomplete name question stops signing") {
                it.contains("Unavailable") && it.contains("NAME")
            }
            for (text in listOf("It is hot today.", "IT IS HOT TODAY", "It's hot today!", "Today is hot.")) {
                submit(text)
                awaitStatus("Weather expression requires reviewed phrase motion") { it.contains("phrase order") }
                i.runOnMainSync { assertSame(originalView, activity.findViewById(R.id.avatarWebView)) }
            }
            submit("I am not a student")
            awaitStatus("Missing negation stops incomplete meaning") { it.contains("preserve negation") }
            submit("hello beautiful")
            submit("beautiful") // Supersede an active request through the same existing input/button.
            awaitStatus("Replacement request complete") { it.contains("Complete") && !it.contains("Unsupported") }
            i.runOnMainSync { assertSame(originalView, activity.findViewById(R.id.avatarWebView)) }
        } finally {
            i.runOnMainSync { activity.finish() }
            prefs.edit().apply { if (previous == null) remove("character") else putString("character", previous) }.commit()
        }
    }
}
