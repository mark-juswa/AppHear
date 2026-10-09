package com.example.apphear

import android.content.Intent
import android.graphics.Bitmap
import android.view.ViewGroup
import android.webkit.WebView
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.example.apphear.domain.texttoasl.SignDictionaryMetadata
import com.example.apphear.ui.texttoasl.AndroidAssetAslCatalogLoader
import com.example.apphear.ui.texttoasl.TextToAslPlaybackController
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

class OriginalWordBatchInstrumentedTest {
    private val i get()=InstrumentationRegistry.getInstrumentation()

    @Test fun originalExpandsButNewCharacterAndIdleKeepTheirContracts() {
        assumeTrue(BuildConfig.ASL_ORIGINAL_WORDS_ENABLED && BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED)
        val start=System.nanoTime()
        val original=AndroidAssetAslCatalogLoader(i.targetContext,false).load()
        val elapsed=(System.nanoTime()-start)/1e6
        val newCharacter=AndroidAssetAslCatalogLoader(i.targetContext,true).load()
        assertEquals(204,original.getAssets().size)
        assertEquals(28,newCharacter.getAssets().size)
        assertEquals(0.0,original.findByAlias("idle")?.neutralFrameSeconds)
        assertEquals(original.findByAlias("idle"),original.findByAlias("stand"))
        assertTrue(original.getAssets().all { it.metadata.avatarProfile == SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN })
        assertTrue(newCharacter.getAssets().all { it.metadata.avatarProfile == SignDictionaryMetadata.AvatarProfile.NEW_HUMAN })
        assertTrue((original.getAssets()+newCharacter.getAssets()).all { it.replacement?.fallbackAssetPath == null })
        assertNull(newCharacter.findByAlias("hello"))
        assertNull(newCharacter.findByAlias("right direction"))
        assertEquals("SIGN_LETTER_Z_FEMALEASL",newCharacter.findLetter('z')?.replacement?.animationName)
        val planner=AslPhrasePlanner(original,dictionarySequenceMode=true)
        for (input in listOf("hello beautiful", "HELLO BEAUTIFUL", "hello, beautiful!")) {
            assertEquals(listOf("hello","beautiful"),planner.plan(input).queue.map { it.id })
        }
        assertEquals(listOf("thank_you"),planner.plan("thank you").queue.map { it.id })
        assertEquals(listOf("unknownword"),planner.plan("hello unknownword").unsupportedTokens)
        File(i.targetContext.filesDir,"original_word_batch_catalog.json").writeText(
            JSONObject().put("entries",204).put("newCharacterEntries",28).put("catalogLoadMs",elapsed).toString())
    }

    @Test fun representativeOriginalClipsLoadPlayFinishAndRelease() {
        assumeTrue(BuildConfig.ASL_ORIGINAL_WORDS_ENABLED && BuildConfig.ASL_ASSET_PILOT_ENABLED)
        val catalog=AndroidAssetAslCatalogLoader(i.targetContext,false).load()
        val activity=i.startActivitySync(Intent(i.targetContext,MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        lateinit var web:WebView
        lateinit var controller:TextToAslPlaybackController
        val ready=CountDownLatch(1)
        val evidence=JSONArray()
        try {
            i.runOnMainSync {
                web=WebView(activity)
                activity.addContentView(web,ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT))
                controller=TextToAslPlaybackController(activity,web)
                controller.setReadyCallback(object:TextToAslPlaybackController.ReadyCallback {
                    override fun onReady() { ready.countDown() }
                })
            }
            assertTrue("Offline viewer ready",ready.await(30,TimeUnit.SECONDS))
            for(alias in listOf("hello","beautiful","father","right","right direction","baby","what rhetorical")) {
                val clip=requireNotNull(catalog.findByAlias(alias))
                val started=CountDownLatch(1)
                val finished=CountDownLatch(1)
                var failed=false
                val before=System.nanoTime()
                var startedMs=0.0
                i.runOnMainSync {
                    controller.setPlaybackCallback(object:TextToAslPlaybackController.PlaybackCallback {
                        override fun onStarted(asset:AslAnimationAsset) {
                            startedMs=(System.nanoTime()-before)/1e6; started.countDown()
                        }
                        override fun onFinished(asset:AslAnimationAsset) { finished.countDown() }
                        override fun onFailed(asset:AslAnimationAsset) { failed=true; started.countDown(); finished.countDown() }
                    })
                    controller.play(clip)
                }
                assertTrue("$alias loaded",started.await(30,TimeUnit.SECONDS))
                assertFalse("$alias load failed",failed)
                Thread.sleep(300)
                val bitmap=i.uiAutomation.takeScreenshot()
                if(bitmap!=null) {
                    File(i.targetContext.filesDir,"original_word_batch_${clip.id}.png").outputStream().use {
                        bitmap.compress(Bitmap.CompressFormat.PNG,100,it)
                    }
                    bitmap.recycle()
                }
                assertTrue("$alias completion",finished.await(15,TimeUnit.SECONDS))
                assertFalse("$alias playback failed",failed)
                evidence.put(JSONObject().put("alias",alias).put("id",clip.id).put("asset",clip.assetPath)
                    .put("firstPlaybackStartMs",startedMs).put("totalMs",(System.nanoTime()-before)/1e6))
            }
            File(i.targetContext.filesDir,"original_word_batch_playback.json").writeText(evidence.toString(2))
        } finally {
            i.runOnMainSync { controller.destroy(); activity.finish() }
        }
    }
}
