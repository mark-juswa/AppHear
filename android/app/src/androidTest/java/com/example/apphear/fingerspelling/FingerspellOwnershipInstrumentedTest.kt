package com.example.apphear.fingerspelling

import android.content.Intent
import android.view.View
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.perceptionvnext.PhoneProductionSession
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.pipeline.recognition.RecognitionState
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/** Engineering-only synthetic preview; never recorded as live recognition evidence. */
class FingerspellOwnershipInstrumentedTest {
    @Test fun explicitOwnerPreviewConfirmationRetryAndWordRestoration() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val activity = instrumentation.startActivitySync(Intent(instrumentation.targetContext,
            RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        fun field(name:String):Any? = RecognitionActivity::class.java.getDeclaredField(name)
            .apply { isAccessible=true }.get(activity)
        try {
            val deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(20)
            while(field("fingerspellRuntime")==null && System.nanoTime()<deadline) Thread.sleep(100)
            val runtime=checkNotNull(field("fingerspellRuntime") as? FingerspellRuntime) { "Camera permission/model loading required" }
            val executor=field("cameraExecutor") as ExecutorService
            val word=field("phoneSession") as PhoneProductionSession
            val before=word.sentenceText
            val syntheticPreview=if(runtime.singleLetterMode) "B" else "BELLA"
            executor.submit {
                runtime.select(RecognitionMode.FINGERSPELL)
                val session=FingerspellRuntime::class.java.getDeclaredField("session")
                    .apply { isAccessible=true }.get(runtime) as FingerspellSession
                session.start(); session.consume(0.0,FloatArray(session.inputWidth))
                val (token,_)=session.finish(); assertTrue(session.complete(token,syntheticPreview))
                FingerspellRuntime::class.java.getDeclaredMethod("emit",String::class.java)
                    .apply { isAccessible=true }.invoke(runtime,"Synthetic engineering preview")
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            val onFrame=RecognitionActivity::class.java.getDeclaredMethod("onFrame",FrameResult::class.java)
                .apply { isAccessible=true }
            instrumentation.runOnMainSync {
                assertEquals(syntheticPreview,activity.findViewById<TextView>(R.id.glossText).text.toString())
                assertEquals("",runtime.snapshot.confirmed)
                assertEquals(View.GONE,activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                onFrame.invoke(activity,FrameResult(null,null,480,640,6.23,true,"S2_R2_CANDIDATE",1,
                    recognition=RecognitionState.Idle,phoneReady=true,phoneSentence="STALE WORD OUTPUT"))
                assertEquals(syntheticPreview,activity.findViewById<TextView>(R.id.glossText).text.toString())
            }
            executor.submit { runtime.confirm() }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals(syntheticPreview,runtime.snapshot.confirmed)
                assertEquals(syntheticPreview,activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals(View.VISIBLE,activity.findViewById<View>(R.id.sentenceCard).visibility)
            }
            executor.submit { runtime.retry(); runtime.clear() }.get(10,TimeUnit.SECONDS)
            assertEquals("",runtime.snapshot.confirmed)
            executor.submit { runtime.select(RecognitionMode.WORD) }.get(10,TimeUnit.SECONDS)
            assertEquals(before,word.sentenceText)
            assertEquals(RecognitionMode.WORD,runtime.snapshot.mode)
        } finally {
            instrumentation.runOnMainSync { activity.finish() }
            instrumentation.waitForIdleSync()
        }
    }
}
