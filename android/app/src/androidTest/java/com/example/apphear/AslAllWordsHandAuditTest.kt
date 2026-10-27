package com.example.apphear

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import android.os.SystemClock
import android.view.View
import android.webkit.WebView
import android.widget.EditText
import android.widget.TextView
import androidx.navigation.fragment.NavHostFragment
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslIntegratedVocabulary
import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.example.apphear.domain.texttoasl.AslTranslationPlanner
import com.example.apphear.ui.texttoasl.AndroidAssetAslCatalogLoader
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Every catalog entry, actual native selection and six rendered movement phases.
 * Contact sheets are development evidence, never a claim of ASL correctness. */
class AslAllWordsHandAuditTest {
    @Test fun everyLexicalEntryRendersOnOneHuman() {
        assumeTrue(BuildConfig.ASL_ASSET_PILOT_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED)
        val i = InstrumentationRegistry.getInstrumentation()
        val context = i.targetContext
        val label = InstrumentationRegistry.getArguments().getString("auditLabel") ?: "current"
        val output = File(context.filesDir, "hand-audit-$label").apply { mkdirs() }
        val catalog = AndroidAssetAslCatalogLoader(context, useNewCharacter = false).load()
        val planner = AslTranslationPlanner(catalog)
        val entries = catalog.getAssets().filter { it.type == AslAnimationAsset.Type.WORD || it.type == AslAnimationAsset.Type.PHRASE }
        assertEquals("Complete active lexical inventory", AslIntegratedVocabulary.ENTRIES, entries.size)
        val monitor = i.addMonitor(MainActivity::class.java.name, null, false)
        i.runOnMainSync { context.startActivity(Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
        val activity = i.waitForMonitorWithTimeout(monitor, 30_000) as? MainActivity ?: error("MainActivity unavailable")
        i.removeMonitor(monitor)
        val evidence = JSONArray()
        try {
            i.runOnMainSync { (activity.supportFragmentManager.findFragmentById(R.id.app_shell_nav_host) as NavHostFragment).navController.navigate(R.id.textToAslFragment) }
            lateinit var viewer: WebView
            fun status(): String { var s = ""; i.runOnMainSync { s = activity.findViewById<TextView>(R.id.current_progress_text)?.text?.toString().orEmpty() }; return s }
            fun waitFor(labelText: String, limit: Long = 120_000, condition: () -> Boolean) {
                val end = SystemClock.uptimeMillis() + limit
                while (SystemClock.uptimeMillis() < end) { if (condition()) return; SystemClock.sleep(40) }
                error("$labelText: ${status()}")
            }
            fun js(script: String): String {
                val latch = CountDownLatch(1); var result = "null"
                i.runOnMainSync { viewer.evaluateJavascript(script) { result = it; latch.countDown() } }
                assertTrue("WebView callback", latch.await(30, TimeUnit.SECONDS)); return result
            }
            waitFor("Ready") { status() == "Ready" }
            viewer = activity.findViewById<WebView>(R.id.avatarWebView) ?: error("Ready without avatar WebView")
            waitFor("Resident model") { js("(()=>{const v=typeof viewers==='undefined'?null:viewers[activeIndex];return !!(v?.loaded&&v.availableAnimations.length===${AslFingerspellingBundle.ACTION_COUNT})})()") == "true" }
            val camera = JSONObject(js("(()=>{const v=viewers[activeIndex];return {target:v.cameraTarget,orbit:v.cameraOrbit,fov:v.fieldOfView,min:v.minCameraOrbit,max:v.maxCameraOrbit}})()"))
            val start = InstrumentationRegistry.getArguments().getString("start")?.toInt() ?: 0
            val requestedIds = InstrumentationRegistry.getArguments().getString("words")?.split(',')?.toSet()
            require(requestedIds == null || entries.map { it.id }.containsAll(requestedIds)) { "Unknown audit ID" }
            val requested = entries.withIndex().filter { requestedIds == null || it.value.id in requestedIds }
            val count = InstrumentationRegistry.getArguments().getString("count")?.toInt() ?: requested.size
            val fixedCamera = InstrumentationRegistry.getArguments().getString("fixedCamera") == "true"
            // Pose inspection deliberately seeks/pauses the clip. Do not claim
            // that resuming this diagnostic timeline tests production replay.
            val posesOnly = InstrumentationRegistry.getArguments().getString("posesOnly") == "true"
            // Observe requests made by the real button, including short clips
            // that may complete before the instrumentation thread can pause.
            if (posesOnly) js("""
                (()=>{if(!window.__handAuditOriginalPlay){window.__handAuditOriginalPlay=window.playSign;
                window.__handAuditGeneration=0;window.playSign=function(url,options){
                if(options?.neutralFrame==null && !options?.loop){window.__handAuditLast={url,options};window.__handAuditGeneration++}
                return window.__handAuditOriginalPlay.apply(this,arguments)}}return true})()
            """.trimIndent())
            val azimuth = InstrumentationRegistry.getArguments().getString("azimuth")?.toDouble() ?: 0.0
            require(azimuth in -45.0..45.0)
            val cameraDistance = InstrumentationRegistry.getArguments().getString("cameraDistance")?.toDouble() ?: 1.45
            require(cameraDistance in .8..3.0)
            for ((index, entry) in requested.drop(start).take(count)) {
                val input = (listOf(entry.displayText) + entry.aliases + entry.id).firstOrNull { text -> planner.plan(text).queue.map { it.id } == listOf(entry.id) }
                assertNotNull("Single-entry input mapping ${entry.id}", input)
                val action = entry.replacement?.animationName ?: error("Missing lexical action ${entry.id}")
                val previousGeneration = if(posesOnly) js("window.__handAuditGeneration").toInt() else 0
                i.runOnMainSync {
                    val mode = activity.findViewById<View>(R.id.mode_text_button)
                    val shortcut = activity.findViewById<View>(R.id.mode_text_shortcut)
                    if (mode.isShown) mode.performClick() else if (shortcut.isShown) shortcut.performClick()
                    activity.findViewById<EditText>(R.id.input_text).setText(input)
                    assertTrue(activity.findViewById<View>(R.id.sign_it_button).performClick())
                }
                var diagnosticReplay = false
                waitFor("Selected ${entry.id}") {
                    if(posesOnly && js("window.__handAuditGeneration>$previousGeneration") != "true") false
                    else {
                        val selected = js("(()=>{const v=viewers[activeIndex];if(v.animationName!==${JSONObject.quote(action)}||v.playRequest==null)return false;v.pause();return true})()") == "true"
                        if(!selected && posesOnly && !diagnosticReplay) {
                            // Still capture only: replay the observed native request.
                            // Normal uninterrupted completion is tested separately.
                            diagnosticReplay = true
                            js("(()=>{const r=window.__handAuditLast;window.__handAuditOriginalPlay(r.url,r.options);return true})()")
                        }
                        selected
                    }
                }
                // Include squeeze extrema and alternate-depth extrema: evenly spaced
                // midpoint-only samples previously hid the opposed EXPLAIN motion.
                val fractions = if (fixedCamera) listOf(.03, .22, .29, .36, .43, .50, .64, .71, .78, .97)
                    else listOf(.03, .20, .40, .60, .80, .97)
                // Fix one camera for the entire word, covering all moving hand
                // bounds. It must not track the hand and hide a full rotation.
                if (!fixedCamera) js("""
                    (()=>{const v=viewers[activeIndex],s=v[Object.getOwnPropertySymbols(v).find(k=>k.description==='scene')];
                    const sets={Left:[],Right:[]};for(const f of [.03,.2,.4,.6,.8,.92]){v.currentTime=v.duration*f;s.updateMatrixWorld(true);s.traverse(o=>{for(const side of ['Left','Right'])if(o.isBone&&o.name.startsWith(side+'Hand')){const p=o.position.clone();o.getWorldPosition(p);s.target.worldToLocal(p);sets[side].push(p.toArray())}})}
                    const spans={};for(const side of ['Left','Right']){const pts=sets[side];spans[side]=Math.max(...[0,1,2].map(k=>Math.max(...pts.map(p=>p[k]))-Math.min(...pts.map(p=>p[k]))))}
                    const sides=['Left','Right'].filter(side=>spans[side]>.03),pts=(sides.length?sides:['Left','Right']).flatMap(side=>sets[side]),lo=[0,1,2].map(k=>Math.min(...pts.map(p=>p[k]))),hi=[0,1,2].map(k=>Math.max(...pts.map(p=>p[k])));
                    const radius=Math.max(.70,(hi[0]-lo[0]+.10)*2.6,(hi[1]-lo[1]+.12)*1.9);v.minCameraOrbit='auto auto .1m';v.maxCameraOrbit='auto auto 20m';v.cameraTarget=lo.map((x,k)=>(x+hi[k])/2+'m').join(' ');v.cameraOrbit='0deg 85deg '+radius+'m';v.fieldOfView='40deg';v.jumpCameraToGoal?.();return true})()
                """.trimIndent())
                if (fixedCamera) js("""
                    (()=>{const v=viewers[activeIndex];v.minCameraOrbit='auto auto .1m';v.maxCameraOrbit='auto auto 20m';
                    v.cameraTarget='0m 1.43m .05m';v.cameraOrbit='${azimuth}deg 85deg ${cameraDistance}m';v.fieldOfView='40deg';v.jumpCameraToGoal?.();return true})()
                """.trimIndent())
                val frames = JSONArray()
                val sheet = Bitmap.createBitmap(480 * fractions.size, 600, Bitmap.Config.ARGB_8888)
                val canvas = Canvas(sheet); canvas.drawColor(android.graphics.Color.WHITE)
                for ((phase, fraction) in fractions.withIndex()) {
                    val frame = JSONObject(js("""
                        (()=>{const v=viewers[activeIndex];v.currentTime=v.duration*$fraction;
                        const s=v[Object.getOwnPropertySymbols(v).find(k=>k.description==='scene')],bones=[];
                        s.traverse(o=>{if(o.isBone&&(o.name.includes('Hand')||o.name.endsWith('ForeArm')))bones.push({name:o.name,q:o.quaternion.toArray()})});
                        window.__handAuditFrame=false;let mesh;s.traverse(o=>{if(o.isSkinnedMesh)mesh=o});if(!mesh)throw Error('No renderable signing mesh');
                        const previous=mesh.onAfterRender;mesh.onAfterRender=function(...args){previous.apply(this,args);mesh.onAfterRender=previous;window.__handAuditDrawnTime=v.currentTime;window.__handAuditFrame=true};s.queueRender();
                        return {time:v.currentTime,action:v.animationName,source:v.src,bones,modelCount:[...document.querySelectorAll('model-viewer')].filter(m=>m.src).length,
                        actions:s.mixers.flatMap(m=>m._actions.filter(a=>a.isScheduled()&&a.getEffectiveWeight()>.001).map(a=>({name:a._clip.name,weight:a.getEffectiveWeight()})))};})()
                    """.trimIndent()))
                    assertEquals(action, frame.getString("action")); assertEquals(1, frame.getInt("modelCount"))
                    frames.put(frame)
                    waitFor("Rendered ${entry.id} phase $phase", 30_000) { js("window.__handAuditFrame===true") == "true" }
                    AslVisualTestGuard.awaitVisualCommit(i, viewer)
                    AslVisualTestGuard.requireUnobscuredApp(i)
                    val screen = i.uiAutomation.takeScreenshot() ?: error("Screenshot unavailable")
                    val location = IntArray(2); var bounds = Rect()
                    i.runOnMainSync { viewer.getLocationOnScreen(location); bounds = Rect(location[0], location[1], location[0] + viewer.width, location[1] + viewer.height) }
                    assertTrue("Avatar viewport visible", bounds.intersect(0, 0, screen.width, screen.height))
                    canvas.drawBitmap(screen, bounds, Rect(phase * 480, 30, (phase + 1) * 480, 600), null)
                    canvas.drawText("${entry.id} @ ${"%.2f".format(fraction)}", phase * 480f + 8, 22f, Paint().apply { color = android.graphics.Color.BLACK; textSize = 18f })
                    screen.recycle()
                }
                File(output, "${entry.id}.jpg").outputStream().use { sheet.compress(Bitmap.CompressFormat.JPEG, 85, it) }; sheet.recycle()
                val continuous = InstrumentationRegistry.getArguments().getString("continuous") == "true"
                if (posesOnly) {
                    // The next native Sign It request cancels this paused one.
                    // Only selection/rendered pose evidence is recorded here.
                    js("(()=>{viewers[activeIndex].pause();return true})()")
                } else if (continuous) {
                    // Complete the paused pose inspection first, then submit a
                    // fresh native request. Rewinding an already-sought mixer
                    // bypasses production replay's cached-action reset.
                    js("(()=>{viewers[activeIndex].play({repetitions:1});return true})()")
                    waitFor("Pose completion ${entry.id}") { status().contains("Complete") }
                    js("""
                        (()=>{const v=viewers[activeIndex];window.__wristFrames=[];window.__wristRecording=true;
                        const scene=v[Object.getOwnPropertySymbols(v).find(k=>k.description==='scene')];
                        function sample(){if(!window.__wristRecording)return;scene.updateMatrixWorld(true);const bones=[];
                        scene.traverse(o=>{if(o.isBone&&['LeftArm','RightArm','LeftForeArm','RightForeArm','LeftHand','RightHand'].includes(o.name)){
                        const q=o.quaternion.clone();o.getWorldQuaternion(q);bones.push({name:o.name,q:o.quaternion.toArray(),world:q.toArray()})}});
                        window.__wristFrames.push({time:v.currentTime,action:v.animationName,bones});requestAnimationFrame(sample)}
                        requestAnimationFrame(sample);return true})()
                    """.trimIndent())
                    i.runOnMainSync {
                        activity.findViewById<EditText>(R.id.input_text).setText(input)
                        assertTrue(activity.findViewById<View>(R.id.sign_it_button).performClick())
                    }
                    waitFor("Fresh continuous request ${entry.id}") { js("(()=>{const v=viewers[activeIndex];return v.playRequest!=null&&v.animationName===${JSONObject.quote(action)}})()") == "true" }
                    waitFor("Continuous completion ${entry.id}") { status().contains("Complete") }
                    val motion = JSONArray(js("(()=>{window.__wristRecording=false;return window.__wristFrames})()"))
                    assertTrue("Continuous rendered movement samples", motion.length()>=8)
                    File(output,"${entry.id}-continuous.json").writeText(motion.toString())
                    js("(()=>{const v=viewers[activeIndex],c=$camera;v.cameraTarget=c.target;v.cameraOrbit=c.orbit;v.fieldOfView=c.fov;v.minCameraOrbit=c.min;v.maxCameraOrbit=c.max;v.jumpCameraToGoal?.();return true})()")
                } else {
                js("(()=>{const v=viewers[activeIndex],c=$camera;v.cameraTarget=c.target;v.cameraOrbit=c.orbit;v.fieldOfView=c.fov;v.minCameraOrbit=c.min;v.maxCameraOrbit=c.max;v.jumpCameraToGoal?.();v.play({repetitions:1});return true})()")
                waitFor("Completion ${entry.id}") { status().contains("Complete") }
                }
                evidence.put(JSONObject().put("id", entry.id).put("input", input).put("action", action).put("frames", frames)
                    .put("diagnosticReplay", diagnosticReplay)
                    .put("completion", if(posesOnly) "POSE_CAPTURE_ONLY; continuous completion not assessed" else status()))
                File(output, "progress.json").writeText(JSONObject().put("completed", evidence.length()).put("total", count).put("last", entry.id).put("index", index).toString())
                File(output, "evidence.json").writeText(evidence.toString())
                assertSame(viewer, activity.findViewById(R.id.avatarWebView))
            }
        } finally {
            File(output, "evidence.json").writeText(evidence.toString())
            i.runOnMainSync { activity.finish() }
        }
    }
}
