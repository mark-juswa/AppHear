package com.example.apphear

import android.content.Intent
import android.graphics.Bitmap
import android.os.SystemClock
import android.view.View
import android.webkit.WebView
import android.widget.EditText
import android.widget.TextView
import androidx.navigation.fragment.NavHostFragment
import androidx.test.platform.app.InstrumentationRegistry
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

/** Development-only native sequence/pose evidence; never linguistic certification. */
class AslShoulderTransitionInstrumentedTest {
    @Test fun repeatedCrossSourceTransitionsKeepOneHumanAndRecoverNeutral() {
        assumeTrue(BuildConfig.ASL_ASSET_PILOT_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED)
        val i=InstrumentationRegistry.getInstrumentation();val context=i.targetContext
        val phase=InstrumentationRegistry.getArguments().getString("shoulderPhase") ?: "before"
        require(phase in listOf("before","after"))
        val out=File(context.filesDir,"shoulder-$phase").apply { mkdirs() }
        val planner=AslTranslationPlanner(AndroidAssetAslCatalogLoader(context,useNewCharacter=false).load())
        val monitor=i.addMonitor(MainActivity::class.java.name,null,false)
        i.runOnMainSync { context.startActivity(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
        val activity=i.waitForMonitorWithTimeout(monitor,30_000) as? MainActivity ?: error("MainActivity unavailable")
        i.removeMonitor(monitor)
        try {
            i.runOnMainSync { (activity.supportFragmentManager.findFragmentById(R.id.app_shell_nav_host) as NavHostFragment).navController.navigate(R.id.textToAslFragment) }
            fun status():String { var value="";i.runOnMainSync { value=activity.findViewById<TextView>(R.id.current_progress_text).text.toString() };return value }
            fun waitFor(label:String,timeout:Long=120_000,test:()->Boolean) {
                val end=SystemClock.uptimeMillis()+timeout
                while(SystemClock.uptimeMillis()<end) { if(test())return;SystemClock.sleep(40) }
                error("$label: ${status()}")
            }
            waitFor("Ready") { status()=="Ready" }
            val viewer=activity.findViewById<WebView>(R.id.avatarWebView)
            fun js(code:String):String {
                val latch=CountDownLatch(1);var value="null"
                i.runOnMainSync { viewer.evaluateJavascript(code) { value=it;latch.countDown() } }
                assertTrue(latch.await(30,TimeUnit.SECONDS));return value
            }
            waitFor("Loaded resident model") { js("(()=>{const v=viewers[activeIndex];return !!(v.loaded&&v.availableAnimations.length===${AslFingerspellingBundle.ACTION_COUNT})})()") == "true" }
            js("""
                (()=>{const v=viewers[activeIndex];v.minCameraOrbit='auto auto .1m';v.maxCameraOrbit='auto auto 20m';
                v.cameraTarget='0m 1.43m .05m';v.cameraOrbit='0deg 85deg 2.05m';v.fieldOfView='40deg';v.jumpCameraToGoal?.();
                window.__shoulderPose=()=>{const v=viewers[activeIndex],s=v[Object.getOwnPropertySymbols(v).find(k=>k.description==='scene')];s.updateMatrixWorld(true);const bones=[];
                s.traverse(o=>{if(o.isBone&&['Neck','Spine2','LeftShoulder','RightShoulder','LeftArm','RightArm','LeftForeArm','RightForeArm','LeftHand','RightHand'].includes(o.name)){
                const p=o.position.clone(),q=o.quaternion.clone();o.getWorldPosition(p);o.getWorldQuaternion(q);bones.push({name:o.name,p:p.toArray(),q:o.quaternion.toArray(),wq:q.toArray()})}});
                return {action:v.animationName,time:v.currentTime,request:v.playRequest,bones,models:[...document.querySelectorAll('model-viewer')].filter(x=>x.src).length,
                active:s.mixers.flatMap(m=>m._actions.filter(a=>a.isScheduled()&&a.getEffectiveWeight()>.001).map(a=>({name:a._clip.name,weight:a.getEffectiveWeight()})))}};return true})()
            """.trimIndent())
            fun idle():Boolean=js("(()=>{const p=window.__shoulderPose();return p.action==='SIGN_RELAXED_NEUTRAL'&&p.active.length===1})()") == "true"
            waitFor("Single idle owner",10_000) { idle() }
            val neutral=JSONObject(js("window.__shoulderPose()"))
            File(out,"neutral.json").writeText(neutral.toString(2))
            fun screenshot(name:String) {
                AslVisualTestGuard.awaitVisualCommit(i,viewer);AslVisualTestGuard.requireUnobscuredApp(i)
                val bitmap=i.uiAutomation.takeScreenshot() ?: error("Screenshot unavailable")
                File(out,"$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG,100,it) };bitmap.recycle()
            }
            screenshot("neutral")
            fun submit(text:String) {
                i.runOnMainSync {
                    val mode=activity.findViewById<View>(R.id.mode_text_button);val shortcut=activity.findViewById<View>(R.id.mode_text_shortcut)
                    if(mode.isShown)mode.performClick() else if(shortcut.isShown)shortcut.performClick()
                    activity.findViewById<EditText>(R.id.input_text).setText(text)
                    assertTrue(activity.findViewById<View>(R.id.sign_it_button).performClick())
                }
            }
            submit("adult")
            waitFor("ADULT pose") { js("(()=>{const v=viewers[activeIndex];if(v.animationName!=='SIGN_ADULT_3DLEX_ASL_PREVIEW'||v.playRequest==null)return false;v.pause();v.currentTime=.325;return true})()") == "true" }
            File(out,"adult-preroll.json").writeText(JSONObject(js("window.__shoulderPose()")).toString(2));screenshot("adult-preroll")
            js("(()=>{viewers[activeIndex].play({repetitions:1});return true})()")
            waitFor("ADULT completion") { status().contains("Complete") };waitFor("ADULT idle",10_000) { idle() }
            val cases=listOf("YOU LOVE ME","WHAT YOUR NAME","HELLO YOU HELP","WHY TODAY WHERE","LOVE YOUR NAME", "NICOLE LOVE","HELP NICOLE", "HELLO ADULT HELLO","ALREADY ADULT BICYCLE","NICOLE ANNA")
            val evidence=JSONArray()
            repeat(3) { round ->
                for(text in cases) {
                    js("""
                        (()=>{window.__shoulderFrames=[];window.__shoulderRecording=true;let last=-100;
                        function sample(t){if(!window.__shoulderRecording)return;if(t-last>=40){last=t;const p=window.__shoulderPose();p.at=t;window.__shoulderFrames.push(p)}requestAnimationFrame(sample)}requestAnimationFrame(sample);return true})()
                    """.trimIndent())
                    submit(text)
                    waitFor("Started $text") { js("viewers[activeIndex].playRequest!=null") == "true" }
                    waitFor("Completed $text") { status().contains("Complete") };waitFor("Neutral after $text",10_000) { idle() }
                    val frames=JSONArray(js("(()=>{window.__shoulderRecording=false;return window.__shoulderFrames})()"))
                    assertTrue("Rendered sequence samples",frames.length()>8)
                    for(index in 0 until frames.length())assertEquals("Same resident human",1,frames.getJSONObject(index).getInt("models"))
                    val expected=planner.plan(text).queue.map { it.replacement!!.animationName }
                    val requests=linkedMapOf<Long,String>()
                    for(index in 0 until frames.length()) {
                        val frame=frames.getJSONObject(index)
                        if(!frame.isNull("request"))requests[frame.getLong("request")]=frame.getString("action")
                    }
                    assertEquals("Native queue observed in order: $text",expected,requests.values.toList())
                    val recovered=JSONObject(js("window.__shoulderPose()"))
                    val reference=neutral.getJSONArray("bones")
                    val actual=recovered.getJSONArray("bones")
                    for(side in listOf("LeftShoulder","RightShoulder")) {
                        fun q(array:JSONArray):JSONArray=(0 until array.length()).map { array.getJSONObject(it) }.single { it.getString("name")==side }.getJSONArray("q")
                        val a=q(reference);val b=q(actual);val dot=(0..3).sumOf { a.getDouble(it)*b.getDouble(it) }
                        assertTrue("No accumulated clavicle drift $side round $round",kotlin.math.abs(dot)>1.0-1e-6)
                    }
                    val index=evidence.length()
                    File(out,"sequence-$index.json").writeText(frames.toString())
                    evidence.put(JSONObject().put("round",round).put("input",text).put("frames",frames.length()).put("status",status()).put("recovered",recovered))
                    File(out,"progress.json").writeText(JSONObject().put("completed",evidence.length()).put("total",30).put("last",text).toString())
                    File(out,"evidence.json").writeText(evidence.toString())
                }
            }
            assertEquals(30,evidence.length())
        } finally { i.runOnMainSync { activity.finish() } }
    }
}
