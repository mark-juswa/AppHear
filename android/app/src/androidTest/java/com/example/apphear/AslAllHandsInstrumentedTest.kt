package com.example.apphear

import android.content.Intent
import android.graphics.Bitmap
import android.os.SystemClock
import android.view.ViewGroup
import android.webkit.WebView
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.ui.texttoasl.AndroidAssetAslCatalogLoader
import com.example.apphear.ui.texttoasl.TextToAslPlaybackController
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Development-only real WebView sampling; never a linguistic accuracy test. */
class AslAllHandsInstrumentedTest {
    @Test fun everyCurrentWordAndLetterReachesItsNamedPoseAndCompletesOnOneHuman() {
        assumeTrue(BuildConfig.ASL_ORIGINAL_WORDS_ENABLED && BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED)
        val i=InstrumentationRegistry.getInstrumentation();val context=i.targetContext
        val catalog=AndroidAssetAslCatalogLoader(context,false).load()
        val allClips=catalog.getAssets().filter {
            it.type==AslAnimationAsset.Type.WORD || it.type==AslAnimationAsset.Type.PHRASE
        }
            .distinctBy { it.replacement!!.animationName }+('a'..'z').map { catalog.findLetter(it)!! }
        assertEquals(231,allClips.size)
        val requested=InstrumentationRegistry.getArguments().getString("actions")?.split(',')?.toSet()
        val clips=if(requested==null)allClips else allClips.filter { it.replacement!!.animationName in requested }
        if(requested!=null)assertEquals(requested,clips.map {it.replacement!!.animationName}.toSet())
        assertEquals(1,clips.map { it.assetPath }.distinct().size)
        val monitor=i.addMonitor(MainActivity::class.java.name,null,false)
        i.runOnMainSync { context.startActivity(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
        val activity=i.waitForMonitorWithTimeout(monitor,20_000) as? MainActivity ?: throw AssertionError("MainActivity did not open")
        i.removeMonitor(monitor)
        lateinit var web:WebView;lateinit var controller:TextToAslPlaybackController
        val ready=CountDownLatch(1);val evidence=JSONArray()
        val output=File(context.filesDir,"text_to_sign_all_hands_audit").apply { mkdirs() }
        fun evaluate(expression:String):JSONObject {
            val done=CountDownLatch(1);var value="null"
            i.runOnMainSync { web.evaluateJavascript(expression) { value=it;done.countDown() } }
            assertTrue("Diagnostic JavaScript response",done.await(15,TimeUnit.SECONDS))
            return JSONObject(JSONTokener(value).nextValue() as String)
        }
        try {
            i.runOnMainSync {
                web=WebView(activity)
                activity.addContentView(web,ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT))
                controller=TextToAslPlaybackController(activity,web)
                controller.setReadyCallback(object:TextToAslPlaybackController.ReadyCallback { override fun onReady(){ready.countDown()} })
            }
            assertTrue("Offline viewer initializes",ready.await(30,TimeUnit.SECONDS))
            for((index,clip) in clips.withIndex()) {
                val started=CountDownLatch(1);val finished=CountDownLatch(1);var failed=false
                i.runOnMainSync {
                    controller.setPlaybackCallback(object:TextToAslPlaybackController.PlaybackCallback {
                        override fun onStarted(asset:AslAnimationAsset){started.countDown()}
                        override fun onFinished(asset:AslAnimationAsset){finished.countDown()}
                        override fun onFailed(asset:AslAnimationAsset){failed=true;started.countDown();finished.countDown()}
                    })
                    controller.play(clip)
                }
                assertTrue("${clip.id}: starts",started.await(40,TimeUnit.SECONDS));assertFalse("${clip.id}: load failure",failed)
                val deadline=SystemClock.uptimeMillis()+30_000
                var snapshot=JSONObject()
                while(SystemClock.uptimeMillis()<deadline) {
                    snapshot=evaluate("""JSON.stringify((()=>{const v=viewers[activeIndex];return {name:v.animationName,time:v.currentTime,duration:v.duration,src:v.src,loaded:v.loaded};})())""")
                    if(snapshot.optDouble("duration")>0 && snapshot.optDouble("time")>=snapshot.optDouble("duration")*.65)break
                    SystemClock.sleep(50) // Diagnostic polling only; queue advancement uses completion callbacks.
                }
                assertEquals(clip.replacement!!.animationName,snapshot.getString("name"))
                assertTrue("${clip.id}: reaches pose",snapshot.getDouble("time")>=snapshot.getDouble("duration")*.65)
                val pose=evaluate("""JSON.stringify((()=>{const v=viewers[activeIndex],s=v[Object.getOwnPropertySymbols(v).find(k=>k.description==='scene')],bones=[];s.traverse(o=>{if(/^(Left|Right)Hand/.test(o.name))bones.push({name:o.name,q:o.quaternion.toArray()});});return {name:v.animationName,time:v.currentTime,bones,actions:s.mixers.flatMap(m=>m._actions.filter(a=>a.isScheduled()).map(a=>({name:a._clip.name,weight:a.getEffectiveWeight(),enabled:a.enabled}))),visibleViewers:viewers.filter(x=>x.classList.contains('active')).length};})())""")
                assertEquals(1,pose.getInt("visibleViewers"))
                assertTrue("${clip.id}: finger bones present",pose.getJSONArray("bones").length()>=32)
                val actions=pose.getJSONArray("actions")
                assertTrue("${clip.id}: requested clip controls pose",(0 until actions.length()).any {
                    val a=actions.getJSONObject(it);a.getString("name")==clip.replacement.animationName && a.getDouble("weight")>.99
                })
                val bitmap=i.uiAutomation.takeScreenshot()
                if(bitmap!=null) {File(output,"pose_${index}_${clip.id}.png").outputStream().use {bitmap.compress(Bitmap.CompressFormat.PNG,100,it)};bitmap.recycle()}
                evidence.put(pose.put("id",clip.id).put("qualifiedAslValidation",false))
                File(output,"runtime-poses.json").writeText(JSONObject().put("renderer","Android emulator WebView").put("samples",evidence).toString(2))
                assertTrue("${clip.id}: real completion callback",finished.await(30,TimeUnit.SECONDS));assertFalse(failed)
            }
        }finally {i.runOnMainSync {
            controller.destroy()
            if(InstrumentationRegistry.getArguments().getString("leaveOpen")=="true") {
                (web.parent as? ViewGroup)?.removeView(web)
                (activity.supportFragmentManager.findFragmentById(R.id.app_shell_nav_host) as androidx.navigation.fragment.NavHostFragment)
                    .navController.navigate(R.id.textToAslFragment)
            }else activity.finish()
        }}
    }
}
