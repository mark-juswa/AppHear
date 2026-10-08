package com.example.apphear.camera

import android.content.Intent
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.fingerspelling.FingerspellRuntime
import com.example.apphear.fingerspelling.RecognitionMode
import com.example.apphear.perceptionvnext.PhoneProductionSession
import com.example.apphear.pipeline.recognition.SentenceBuilder
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/** Physical CameraX front/back/front engineering transfer, never an accuracy benchmark. */
class CameraSwitchInstrumentedTest {
    @Test fun bothLensesUseSameOwnerAndResetTemporalWindows() {
        assertTrue(BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED)
        val i=InstrumentationRegistry.getInstrumentation()
        val settings=RecognitionModeSettings(i.targetContext)
        settings.select(RecognitionMode.FINGERSPELL)
        val a=i.startActivitySync(Intent(i.targetContext,RecognitionActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        fun field(name:String)=RecognitionActivity::class.java.getDeclaredField(name).apply { isAccessible=true }.get(a)
        fun waitUntil(message:String,condition:()->Boolean) {
            val end=System.nanoTime()+TimeUnit.SECONDS.toNanos(45)
            while(!condition() && System.nanoTime()<end) Thread.sleep(100)
            assertTrue(message,condition())
        }
        try {
            waitUntil("front delivers frames") { (field("cameraInputFrames") as Int)>=12 && field("fingerspellRuntime")!=null }
            val runtime=field("fingerspellRuntime") as FingerspellRuntime
            val word=field("phoneSession") as PhoneProductionSession
            val executor=field("cameraExecutor") as ExecutorService
            executor.submit {
                val sentenceBuffer=PhoneProductionSession::class.java.getDeclaredField("sentence")
                    .apply { isAccessible=true }.get(word) as SentenceBuilder
                sentenceBuffer.add("CAMERA CHECK")
            }.get(10,TimeUnit.SECONDS)
            val sentence=word.sentenceText
            assertEquals("CAMERA CHECK",sentence)
            fun switch(front:Boolean) {
                val old=field("cameraGeneration") as Int
                i.runOnMainSync {
                    assertTrue(a.findViewById<TextView>(R.id.cameraToggle).isEnabled)
                    a.findViewById<TextView>(R.id.cameraToggle).performClick()
                }
                waitUntil("new lens delivers observations") {
                    (field("cameraGeneration") as Int)>old && (field("cameraInputFrames") as Int)>=12 &&
                        !(field("cameraSwitching") as Boolean)
                }
                assertEquals(front,field("frontCamera"))
                assertEquals(front,field("processingFrontCamera"))
            }
            assertTrue(runtime.fingerspellOwnsFrames)
            switch(false); assertTrue(runtime.fingerspellOwnsFrames)
            assertEquals(sentence,word.sentenceText)
            switch(true); assertTrue(runtime.fingerspellOwnsFrames)
            assertEquals(sentence,word.sentenceText)
            settings.select(RecognitionMode.WORD)
            RecognitionActivity::class.java.getDeclaredField("selectedRecognitionMode").apply { isAccessible=true }
                .set(a,RecognitionMode.WORD)
            executor.submit { runtime.select(RecognitionMode.WORD) }.get(10,TimeUnit.SECONDS)
            switch(false); assertFalse(runtime.fingerspellOwnsFrames)
            switch(true); assertFalse(runtime.fingerspellOwnsFrames)
            assertEquals(sentence,word.sentenceText)
            i.targetContext.filesDir.resolve("camera_switch_result.json").writeText(JSONObject()
                .put("status","PASS").put("fingerspell_front_back_front",true)
                .put("word_front_back_front",true).put("word_sentence_preserved",true)
                .put("accuracy_claim","NONE").toString(2))
        } finally {
            settings.select(RecognitionMode.WORD)
            i.runOnMainSync { a.finish() }; i.waitForIdleSync()
        }
    }
}
