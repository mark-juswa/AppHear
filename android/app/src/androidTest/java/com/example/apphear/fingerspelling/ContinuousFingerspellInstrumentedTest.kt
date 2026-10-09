package com.example.apphear.fingerspelling

import android.content.Intent
import android.view.View
import android.view.LayoutInflater
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.ui.settings.SettingsContent
import com.example.apphear.perceptionvnext.PhoneProductionSession
import com.example.apphear.perceptionvnext.PhoneRawObservation
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/** Synthetic engineering inputs verify ownership/lifecycle, never signing accuracy. */
class ContinuousFingerspellInstrumentedTest {
    private fun observation(t:Double, hand:Boolean) = PhoneRawObservation(t.toInt(),t,480,640,
        Array(2){FloatArray(42){100f}},Array(2){BooleanArray(21){hand}},Array(2){FloatArray(21){1f}},
        floatArrayOf(if(hand)1f else 0f,0f),booleanArrayOf(hand,false),BooleanArray(2),Array(2){FloatArray(3)},
        FloatArray(16),FloatArray(8),BooleanArray(8),false)

    @Test fun settingsAutomaticConfirmationRepeatsAndExclusiveOwner() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val settings=RecognitionModeSettings(instrumentation.targetContext)
        settings.select(RecognitionMode.FINGERSPELL)
        assertEquals(RecognitionMode.FINGERSPELL,RecognitionModeSettings(instrumentation.targetContext).current())
        val activity=instrumentation.startActivitySync(Intent(instrumentation.targetContext,
            RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        fun field(name:String)=RecognitionActivity::class.java.getDeclaredField(name).apply{isAccessible=true}.get(activity)
        try {
            val deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(45)
            while(field("fingerspellRuntime")==null && System.nanoTime()<deadline) Thread.sleep(100)
            val runtime=checkNotNull(field("fingerspellRuntime") as? FingerspellRuntime)
            while(runtime.snapshot.mode != RecognitionMode.FINGERSPELL && System.nanoTime()<deadline) Thread.sleep(50)
            assertEquals("Persisted owner must activate after asynchronous load",RecognitionMode.FINGERSPELL,runtime.snapshot.mode)
            while (((field("cameraSwitching") as Boolean) || (field("cameraInputFrames") as Int)<1) &&
                System.nanoTime()<deadline) Thread.sleep(50)
            assertFalse("Camera binding completed before synthetic pause",field("cameraSwitching") as Boolean)
            val executor=field("cameraExecutor") as ExecutorService
            val word=field("phoneSession") as PhoneProductionSession
            val before=word.sentenceText
            val engine=FingerspellRuntime::class.java.getDeclaredField("continuous").apply{isAccessible=true}.get(runtime) as ContinuousFingerspell
            val policy=ContinuousFingerspell::class.java.getDeclaredField("policy").apply{isAccessible=true}.get(engine) as HeldLetterPolicy
            fun calls()=ContinuousFingerspell::class.java.getDeclaredField("inferenceCalls").apply{isAccessible=true}.getInt(engine)
            fun emit()=ContinuousFingerspell::class.java.getDeclaredMethod("emit",String::class.java).apply{isAccessible=true}.invoke(engine,null)
            executor.submit { runtime.pause(); policy.reset(); emit() }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals("",runtime.snapshot.preview)
                assertEquals(View.VISIBLE,activity.findViewById<View>(R.id.sentenceCard).visibility)
                assertEquals(activity.getString(R.string.sentence_placeholder),activity.findViewById<TextView>(R.id.sentenceText).text.toString())
            }
            executor.submit {
                assertTrue(runtime.continuousMode); assertTrue(runtime.fingerspellOwnsFrames)
                runtime.pause() // Keep exclusive F owner while stopping real camera callbacks during synthetic assertions.
                for ((index,letter) in "AMY".withIndex()) {
                    val e=policy.epoch; val t=index*2000.0
                    policy.accept(e,t,letter.toString()); policy.accept(e,t+500,letter.toString())
                    assertTrue(policy.accept(e,t+1000,letter.toString()))
                }
                emit(); assertEquals("AMY",runtime.snapshot.preview); assertEquals("",runtime.snapshot.confirmed)
                assertEquals("Y",runtime.snapshot.currentLetter)
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals("AMY",activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals(View.VISIBLE,activity.findViewById<View>(R.id.sentenceCard).visibility)
                assertEquals(View.VISIBLE,(activity.findViewById<TextView>(R.id.glossText).parent as View).visibility)
                assertEquals("Y",activity.findViewById<TextView>(R.id.glossText).text.toString())
                assertEquals(View.GONE,activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                val buttons=field("fingerspellButtons") as Map<*,*>
                assertTrue("No experimental controls on detection screen",buttons.isEmpty())
            }
            executor.submit {
                assertFalse(policy.accept(policy.epoch,6500.0,"B")); emit()
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals("B",activity.findViewById<TextView>(R.id.glossText).text.toString())
                assertEquals("AMY",activity.findViewById<TextView>(R.id.sentenceText).text.toString())
            }
            val longText="ABCDEFGHIJKLMNOPQRSTUVWXYZ".repeat(4)
            executor.submit {
                policy.reset()
                for((index,c) in longText.withIndex()) {
                    val e=policy.epoch; val t=10000.0+index*2000.0
                    policy.accept(e,t,c.toString()); policy.accept(e,t+500,c.toString())
                    assertTrue(policy.accept(e,t+1000,c.toString()))
                }
                emit(); assertEquals(longText,runtime.snapshot.preview)
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                val text=activity.findViewById<TextView>(R.id.sentenceText)
                val layout=checkNotNull(text.layout)
                val report=JSONObject().put("text",text.text.toString()).put("length",text.length())
                    .put("lines",layout.lineCount).put("width",text.width).put("height",text.height)
                    .put("layout_height",layout.height).put("last_line_end",layout.getLineEnd(layout.lineCount-1))
                    .put("max_lines",text.maxLines).put("accuracy_claim","NONE")
                instrumentation.targetContext.filesDir.resolve("fingerspell_long_text.json").writeText(report.toString(2))
                assertEquals(longText,text.text.toString())
                assertEquals(longText.length,layout.getLineEnd(layout.lineCount-1))
                assertTrue("No text ellipsized",(0 until layout.lineCount).all{layout.getEllipsisCount(it)==0})
                assertTrue("All lines fit the recognized view",layout.height<=text.height-text.compoundPaddingTop-text.compoundPaddingBottom)
                assertEquals("Z",activity.findViewById<TextView>(R.id.glossText).text.toString())
            }
            executor.submit {
                policy.reset()
                for((index,c) in "AMY".withIndex()) {
                    val e=policy.epoch; val t=300000.0+index*2000.0
                    policy.accept(e,t,c.toString()); policy.accept(e,t+500,c.toString()); policy.accept(e,t+1000,c.toString())
                }
                emit()
            }.get(10,TimeUnit.SECONDS)
            executor.submit {
                runtime.confirm(); assertEquals("AMY",runtime.snapshot.confirmed)
                runtime.retry(); assertEquals("AMY",runtime.snapshot.confirmed)
                runtime.clear(); assertEquals("",runtime.snapshot.confirmed)
                runtime.select(RecognitionMode.FINGERSPELL)
                val beforeMissing=calls()
                repeat(15){engine.consume(observation(10000.0+it*200.0,false))}
                assertEquals("",runtime.snapshot.preview)
                assertEquals(beforeMissing,calls()) // Missing input adds no inference calls; live startup may already have calls.
                runtime.select(RecognitionMode.WORD)
                val n=calls()
                repeat(15){engine.consume(observation(20000.0+it*200.0,true))}
                assertEquals(n,calls()); assertFalse(runtime.fingerspellOwnsFrames)
                assertEquals(before,word.sentenceText)
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals(View.VISIBLE,(activity.findViewById<TextView>(R.id.glossText).parent as View).visibility)
            }
            instrumentation.targetContext.filesDir.resolve("fingerspell_continuous_flow.json").writeText(
                JSONObject().put("status","CONTINUOUS_OWNER_SETTINGS_CONFIRMATION_PASS")
                    .put("empty_recognized_card_visible",true).put("start_done_absent",true).put("word_sentence_preserved",true)
                    .put("word_mode_fingerspell_calls",0).put("no_hand_inference_calls",0)
                    .put("synthetic",true).put("accuracy_claim","NONE").toString(2))
        } finally {
            settings.select(RecognitionMode.WORD)
            instrumentation.runOnMainSync {activity.finish()}; instrumentation.waitForIdleSync()
        }
    }

    @Test fun bothSettingsHostsRenderAndPersistChoice() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val activity=instrumentation.startActivitySync(Intent(instrumentation.targetContext,
            RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        val settings=RecognitionModeSettings(instrumentation.targetContext)
        try {
            instrumentation.runOnMainSync {
                for(layout in intArrayOf(R.layout.fragment_settings,R.layout.fragment_profile)) {
                    settings.select(RecognitionMode.WORD)
                    val view=LayoutInflater.from(activity).inflate(layout,null,false)
                    val content=SettingsContent(activity,view)
                    content.render()
                    val row=view.findViewById<View>(R.id.recognitionModeRow)
                    assertNotNull(row); assertEquals(View.VISIBLE,row.visibility)
                    assertEquals("WORD",view.findViewById<TextView>(R.id.recognitionModeValue).text.toString())
                    row.performClick()
                    val dialog=SettingsContent::class.java.getDeclaredField("recognitionDialog").apply{isAccessible=true}
                        .get(content) as androidx.appcompat.app.AlertDialog
                    dialog.listView.performItemClick(null,1,1)
                    assertEquals(RecognitionMode.FINGERSPELL,settings.current())
                    assertTrue(view.findViewById<TextView>(R.id.recognitionModeValue).text.toString().contains("FINGERSPELL"))
                    content.close()
                }
            }
        } finally {
            settings.select(RecognitionMode.WORD)
            instrumentation.runOnMainSync{activity.finish()}; instrumentation.waitForIdleSync()
        }
    }
}
