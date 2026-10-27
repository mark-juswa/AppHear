package com.example.apphear

import android.os.SystemClock
import android.content.Intent
import android.view.View
import android.widget.EditText
import android.widget.TextView
import android.webkit.WebView
import androidx.navigation.fragment.NavHostFragment
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
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
        val review = InstrumentationRegistry.getArguments().getString("transitionReview") == "true"
        var capture: (() -> Unit)? = null
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
                    capture?.invoke()
                    SystemClock.sleep(50) // Test polling; production uses completion callbacks.
                }
                throw AssertionError("$label: ${status()}")
            }
            await("Viewer ready") { it == "Ready" }
            var viewer: View? = null
            i.runOnMainSync { viewer = activity.findViewById(R.id.avatarWebView) }
            // The page bridge can say Ready before its initial GLB has loaded.
            // Wait on actual model state instead of racing the first input on a cold emulator.
            val modelDeadline=SystemClock.uptimeMillis()+180_000
            var modelLoaded=false
            while(SystemClock.uptimeMillis()<modelDeadline && !modelLoaded) {
                val latch=CountDownLatch(1)
                i.runOnMainSync {
                    (viewer as WebView).evaluateJavascript(
                        "(()=>{if(typeof viewers==='undefined')return false;const v=viewers[activeIndex];return Boolean(v&&v.loaded&&v.src&&v.loadedSource===v.src)})()"
                    ) { value -> modelLoaded=value=="true";latch.countDown() }
                }
                // Use the same overall readiness deadline for a busy renderer;
                // a separate ten-second callback limit raced cold GLB parsing.
                assertTrue("WebView state callback before model deadline",latch.await(
                    (modelDeadline-SystemClock.uptimeMillis()).coerceAtLeast(1),TimeUnit.MILLISECONDS))
                if(!modelLoaded)SystemClock.sleep(100) // Test polling only, not animation sequencing.
            }
            assertTrue("Initial avatar model loaded",modelLoaded)
            fun js(script: String): String {
                val latch=CountDownLatch(1);var result="null"
                i.runOnMainSync { (viewer as WebView).evaluateJavascript(script) { result=it;latch.countDown() } }
                assertTrue("Observer callback",latch.await(30,TimeUnit.SECONDS));return result
            }
            // The primary branch intentionally hides preview notices from its progress pill.
            // Observe real native-to-player requests instead of requiring obsolete UI wording.
            js("""(()=>{const real=window.playSign;window.__integrationRequests=[];
                window.playSign=function(url,options){if(options.neutralFrame==null)
                    window.__integrationRequests.push(options.animationName);return real(url,options)};return true})()""")
            val expectedPlanner=com.example.apphear.domain.texttoasl.AslTranslationPlanner(
                com.example.apphear.ui.texttoasl.AndroidAssetAslCatalogLoader(context,useNewCharacter=false).load())
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
            if (review) js("""(()=>{const real=window.playSign;window.__transitionBaseline=false;
                window.playSign=function(url,options){if(window.__transitionBaseline)options={...options,
                    continuation:false,startAtSeconds:0,endPaddingSeconds:0};return real(url,options)};
                window.__poseFrames=[];function sample(){const v=viewers[activeIndex];
                    if(v?.loaded&&v.playRequest!=null){const s=v[Object.getOwnPropertySymbols(v).find(k=>k.description==='scene')];
                        s.updateMatrixWorld(true);const bones=[];s.traverse(o=>{if(o.isBone&&['LeftHand','RightHand'].includes(o.name))
                            bones.push({name:o.name,p:o.matrixWorld.elements.slice(12,15),q:o.quaternion.toArray()})});
                        window.__poseFrames.push({at:performance.now(),request:v.playRequest,action:v.animationName,
                            time:v.currentTime,end:v.playEndTime,bones});}requestAnimationFrame(sample)}sample();return true})()""")
            val standardInputs = listOf("NICOLE", "NAME", "YOU", "ANNA", "JAZZ", "ACTION", "HELLO NICOLE",
                    "ME", "YES", "LOVE", "HELP", "COOK", "BECOME", "MONEY", "NEW", "SOME", "DAY",
                    "HELLO LOVE", "MY NAME", "YOUR NAME", "I LOVE YOU", "I", "ME YOU", "YOU ME",
                    "YOU NICOLE", "ME NICOLE", "BEST", "BETTER", "DIVORCE", "FROM", "GRANDMA",
                    "GRANDPA", "HERE", "PARENTS", "PREFER", "SINGLE", "HELLO GRANDMA NICOLE",
                    "AGAIN", "CLASS", "MUST", "FINGERSPELL", "SO-SO", "GROW UP", "repeat", "spell",
                    "grow up!", "HELLO CLASS NICOLE", "HELP AGAIN", "GIRL",
                    "STOP", "UNDERSTAND", "HUNGRY", "FINISH", "TIRED", "DEAF", "HEARING", "LEARN", "RAIN", "NOW",
                    "HELLO DEAF NICOLE", "LEARN NOW", "I HUNGRY", "HELP STOP", "Rain!", "  thirsty  ") +
                    ('A'..'Z').map { it.toString() }
            val additionalInputs = InstrumentationRegistry.getArguments().getString("extraInputs")
                ?.split('|')?.also { values -> require(values.size <= 100 && values.all { it.isNotBlank() && it.length <= 100 }) }
                ?: emptyList()
            val inputs = if(review) listOf("apple tea", "adult basement", "HELLO NICOLE", "apple apple").flatMap{listOf(it,it)} else standardInputs + additionalInputs
            for ((caseIndex,text) in inputs.withIndex()) {
                val start = SystemClock.uptimeMillis()
                val baseline = review && caseIndex % 2 == 0
                val sheet = if(review) android.graphics.Bitmap.createBitmap(1920,900,android.graphics.Bitmap.Config.ARGB_8888) else null
                val canvas = sheet?.let{android.graphics.Canvas(it)}
                var captured=0;var nextCapture=0L
                if(review) {
                    js("(()=>{window.__transitionBaseline=$baseline;window.__poseFrames=[];return true})()")
                    capture = {
                        if(captured<24 && SystemClock.uptimeMillis()>=nextCapture) {
                            val image=i.uiAutomation.takeScreenshot() ?: error("Missing actual emulator frame")
                            val location=IntArray(2);var width=0;var height=0
                            i.runOnMainSync { viewer!!.getLocationOnScreen(location);width=viewer!!.width;height=viewer!!.height }
                            canvas!!.drawBitmap(image,android.graphics.Rect(location[0],location[1],location[0]+width,location[1]+height),
                                android.graphics.Rect((captured%8)*240,(captured/8)*300,(captured%8+1)*240,(captured/8+1)*300),null)
                            image.recycle();captured++;nextCapture=SystemClock.uptimeMillis()+200
                        }
                    }
                }
                js("(()=>{window.__integrationRequests=[];return true})()")
                submit(text)
                val result = await("$text completes") { it.contains("Complete") }
                // The existing screen preserves entered English after trimming
                // outer whitespace. Normalization should not fail this assertion.
                i.runOnMainSync { assertEquals(text.trim(),activity.findViewById<TextView>(R.id.signed_text).text.toString()) }
                val selected=JSONArray(js("JSON.stringify(window.__integrationRequests)").let { JSONObject("{\"v\":$it}").getString("v") })
                assertEquals("Native requested actions for $text",expectedPlanner.plan(text).queue.map { it.replacement!!.animationName },
                    (0 until selected.length()).map { selected.getString(it) })
                evidence.put(JSONObject().put("input", text).put("status", result)
                    .put("actions",selected)
                    .put("elapsedMs", SystemClock.uptimeMillis() - start))
                if(review) {
                    capture=null
                    val prefix="transition-${caseIndex}-${if(baseline) "before" else "after"}"
                    File(context.filesDir,"$prefix.jpg").outputStream().use{sheet!!.compress(android.graphics.Bitmap.CompressFormat.JPEG,85,it)}
                    sheet!!.recycle()
                    File(context.filesDir,"$prefix.json").writeText(JSONObject("{\"v\":"+js("JSON.stringify(window.__poseFrames)")+"}").getString("v"))
                }
                // Preserve completed-case evidence if a later case fails.
                File(context.filesDir, "fingerspelling_playback_device.json").writeText(evidence.toString(2))
            }
            submit("NICOLE")
            await("First request active") { it.contains("1 / 6") }
            submit("ANNA")
            await("Replacement complete") { it.contains("Complete") }
            i.runOnMainSync {
                assertSame(viewer, activity.findViewById(R.id.avatarWebView))
                assertEquals("ANNA",activity.findViewById<TextView>(R.id.signed_text).text.toString())
            }
            File(context.filesDir, "fingerspelling_playback_device.json").writeText(evidence.toString(2))
        } finally {
            i.runOnMainSync { activity.finish() }
        }
    }
}
