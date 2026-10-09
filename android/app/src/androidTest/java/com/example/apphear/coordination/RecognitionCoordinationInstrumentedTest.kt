package com.example.apphear.coordination

import android.content.Intent
import android.view.View
import android.widget.TextView
import androidx.camera.core.ImageAnalysis
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.contextassist.*
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.fingerspelling.*
import com.example.apphear.perceptionvnext.PhoneProductionSession
import com.example.apphear.pipeline.recognition.SentenceBuilder
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/** Deterministic routing/confirmation on the actual phone; not signing accuracy. No provider calls. */
class RecognitionCoordinationInstrumentedTest {
    private val instrumentation get()=InstrumentationRegistry.getInstrumentation()
    private fun field(target:Any,name:String):Any?=target.javaClass.getDeclaredField(name).apply{isAccessible=true}.get(target)
    @Suppress("UNCHECKED_CAST")
    private fun hearing(text:String):Long {
        var id=0L
        instrumentation.runOnMainSync {
            val context=field(ConversationPhraseAssist,"context") as ConversationContext
            val turn=context.add(ConversationSpeaker.HEARING,ConversationSource.TYPED_TEXT,text,1000)
            id=turn.id
            val flow=field(ConversationPhraseAssist,"presentation") as MutableStateFlow<PhraseAssistUiState>
            flow.value=PhraseAssistUiState(turn.id,turn.text)
        }
        instrumentation.waitForIdleSync()
        return id
    }
    private fun manual(bridge:RecognitionCoordinationBridge,mode:RecognitionMode) {
        bridge.javaClass.getDeclaredMethod("manual",RecognitionMode::class.java).apply{isAccessible=true}.invoke(bridge,mode)
    }
    private fun await(condition:()->Boolean) {
        val end=System.nanoTime()+TimeUnit.SECONDS.toNanos(45)
        while(!condition() && System.nanoTime()<end) Thread.sleep(50)
        assertTrue("Timed out waiting for coordinator",condition())
    }
    private fun common(t:Double,hand:Boolean)=CommonObservation(t,480,640,
        Array(2){FloatArray(42){100f}},Array(2){BooleanArray(21){hand}},Array(2){FloatArray(21){1f}},
        floatArrayOf(if(hand)1f else 0f,0f),booleanArrayOf(hand,false),BooleanArray(2),Array(2){FloatArray(3)},
        FloatArray(16),FloatArray(8),BooleanArray(8),false)

    @Test fun actualOwnerAutomaticEntryConfirmedSpellingAndWordPreservation() {
        assumeTrue(BuildConfig.RECOGNITION_COORDINATION_ENABLED)
        val settings=RecognitionModeSettings(instrumentation.targetContext)
        settings.select(RecognitionMode.WORD)
        instrumentation.runOnMainSync {ConversationPhraseAssist.appBackgrounded()}
        val activity=instrumentation.startActivitySync(Intent(instrumentation.targetContext,RecognitionActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        try {
            await {field(activity,"fingerspellRuntime")!=null && !(field(activity,"cameraSwitching") as Boolean) &&
                (field(activity,"cameraInputFrames") as Int)>0}
            val runtime=field(activity,"fingerspellRuntime") as FingerspellRuntime
            val executor=field(activity,"cameraExecutor") as ExecutorService
            val bridge=field(activity,"coordination") as RecognitionCoordinationBridge
            val word=field(activity,"phoneSession") as PhoneProductionSession
            instrumentation.runOnMainSync { (field(activity,"phoneAnalysis") as ImageAnalysis).clearAnalyzer() }
            executor.submit {runtime.pause(); (field(word,"sentence") as SentenceBuilder).add("HELLO")}.get(10,TimeUnit.SECONDS)
            val id=hearing("What is your name?")
            executor.submit {bridge.observation(true,false)}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.FINGERSPELL,runtime.snapshot.mode)
            assertTrue(runtime.fingerspellOwnsFrames); assertEquals("HELLO",word.sentenceText)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals("Fingerspell",activity.findViewById<TextView>(R.id.coordinationStatus).text.toString())
                val header=activity.findViewById<View>(R.id.coordinationPanel)
                val back=activity.findViewById<View>(R.id.btnBack)
                val camera=activity.findViewById<View>(R.id.cameraToggle)
                val params=header.layoutParams as androidx.constraintlayout.widget.ConstraintLayout.LayoutParams
                assertEquals(R.id.btnBack,params.topToTop); assertEquals(R.id.btnBack,params.bottomToBottom)
                assertTrue("Header does not overlap back",header.left>=back.right)
                assertTrue("Header does not overlap camera",header.right<=camera.left)
                assertTrue(header.top>=back.top && header.bottom<=back.bottom)
                for(id in intArrayOf(R.id.coordinationSpell,R.id.coordinationWord,R.id.coordinationFinish))
                    assertNull("No recognition mode chooser",activity.findViewById<View>(id))
                assertTrue((field(activity,"fingerspellButtons") as Map<*,*>).isEmpty())
            }
            val engine=field(runtime,"continuous") as ContinuousFingerspell
            val p=field(engine,"policy") as HeldLetterPolicy
            fun stable(c:String,t:Double) {
                val e=p.epoch; p.accept(e,t,c); p.accept(e,t+500,c); assertTrue(p.accept(e,t+1000,c))
            }
            executor.submit {
                runtime.pause()
                stable("B",0.0); stable("E",2000.0); stable("L",4000.0)
                p.observe(common(6100.0,false)); p.observe(common(6500.0,false)); p.observe(common(7000.0,false))
                p.observe(common(7200.0,true)); stable("L",7300.0); stable("A",9300.0)
                engine.javaClass.getDeclaredMethod("emit",String::class.java).apply{isAccessible=true}.invoke(engine,null)
                assertEquals("BELLA",runtime.snapshot.preview)
            }.get(10,TimeUnit.SECONDS)
            instrumentation.waitForIdleSync()
            val spoken=mutableListOf<String>()
            // Exercise actual speaker button and confirmation without a remote TTS request.
            bridge.javaClass.getDeclaredField("speak").apply{isAccessible=true}.set(bridge,{text:String->spoken.add(text);Unit})
            instrumentation.runOnMainSync {activity.findViewById<View>(R.id.hearButton).performClick()}
            onView(withText("Confirm and hear")).perform(click())
            await {runtime.snapshot.mode==RecognitionMode.WORD && ConversationPhraseAssist.recentTurns().lastOrNull()?.text=="BELLA"}
            assertFalse(runtime.fingerspellOwnsFrames); assertEquals("HELLO",word.sentenceText)
            assertEquals(listOf("BELLA"),spoken)
            assertNull(ConversationPhraseAssist.activeHearingTurnId())
            assertEquals(id,ConversationPhraseAssist.recentTurns().first().id)
            assertEquals(ConversationSpeaker.DEAF,ConversationPhraseAssist.recentTurns().last().speaker)
            instrumentation.waitForIdleSync()
            instrumentation.runOnMainSync {
                assertEquals("HELLO",activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals("Word",activity.findViewById<TextView>(R.id.coordinationStatus).text.toString())
            }
            // Explicit WORD veto persists for same-turn asynchronous context updates.
            hearing("What city are you from?")
            manual(bridge,RecognitionMode.WORD)
            executor.submit {bridge.observation(true,false)}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.WORD,runtime.snapshot.mode)
            // A started response cannot be interrupted, even after returning to idle.
            hearing("Please spell your name")
            executor.submit {bridge.observation(true,true); bridge.observation(false,false); bridge.observation(true,false)}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.WORD,runtime.snapshot.mode)
            // Manual entry remains possible; a newer question cannot inherit an old spelling.
            manual(bridge,RecognitionMode.FINGERSPELL)
            executor.submit {}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.FINGERSPELL,runtime.snapshot.mode)
            val oldBound=(field(bridge,"policy") as RecognitionCoordinator).state.boundHearingTurnId
            val newId=hearing("Where are you going?")
            assertNotEquals(oldBound,newId)
            val count=ConversationPhraseAssist.recentTurns().size
            instrumentation.runOnMainSync {
                assertFalse(ConversationPhraseAssist.recordConfirmedSpelling("AMY",oldBound))
                assertEquals(count,ConversationPhraseAssist.recentTurns().size)
                assertEquals(newId,ConversationPhraseAssist.activeHearingTurnId())
                assertFalse(ConversationPhraseAssist.recordConfirmedSpelling("Invented Name",newId))
            }
            assertEquals(RecognitionMode.FINGERSPELL,runtime.snapshot.mode)
            manual(bridge,RecognitionMode.WORD)
            executor.submit {}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.WORD,runtime.snapshot.mode)
            assertEquals("HELLO",word.sentenceText)
            instrumentation.targetContext.filesDir.resolve("recognition_coordination_smoke.json").writeText(
                JSONObject().put("status","COORDINATION_ENGINEERING_PASS")
                    .put("top_mode_label_only",true).put("automatic_name_entry",true).put("chooser_absent",true).put("speaker_confirms_and_returns_word",true).put("confirmed_raw_spelling","BELLA")
                    .put("word_sentence_preserved","HELLO").put("same_turn_manual_veto",true)
                    .put("no_mid_response_auto",true).put("new_context_does_not_interrupt",true)
                    .put("stale_reply_rejected",true).put("provider_invoked",false)
                    .put("synthetic",true).put("accuracy_claim","NONE").toString(2))
        } finally {
            settings.select(RecognitionMode.WORD)
            instrumentation.runOnMainSync {activity.finish(); ConversationPhraseAssist.appBackgrounded()}
            instrumentation.waitForIdleSync()
        }
    }
}
