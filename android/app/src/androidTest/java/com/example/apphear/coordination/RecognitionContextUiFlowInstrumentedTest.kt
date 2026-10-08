package com.example.apphear.coordination

import android.content.Intent
import android.view.View
import android.widget.EditText
import android.widget.TextView
import androidx.camera.core.ImageAnalysis
import androidx.navigation.fragment.NavHostFragment
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.BuildConfig
import com.example.apphear.MainActivity
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.contextassist.ConversationPhraseAssist
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.fingerspelling.FingerspellRuntime
import com.example.apphear.fingerspelling.RecognitionMode
import com.example.apphear.ui.texttoasl.TextToAslFragment
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/** Actual typed-context/Reply wiring + controlled pre-signing input; never signing accuracy. */
class RecognitionContextUiFlowInstrumentedTest {
    private val i get()=InstrumentationRegistry.getInstrumentation()
    private fun field(target:Any,name:String)=target.javaClass.getDeclaredField(name).apply{isAccessible=true}.get(target)
    private fun await(message:String,condition:()->Boolean) {
        val end=System.nanoTime()+TimeUnit.SECONDS.toNanos(45)
        while(!condition() && System.nanoTime()<end) Thread.sleep(50)
        assertTrue(message,condition())
    }

    @Test fun typedNameQuestionReplyAutomaticallyRoutesWithoutChooser() {
        assumeTrue(BuildConfig.RECOGNITION_COORDINATION_ENABLED && BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER=="fake")
        val settings=RecognitionModeSettings(i.targetContext)
        val previous=settings.current()
        settings.select(RecognitionMode.WORD)
        i.runOnMainSync {ConversationPhraseAssist.appBackgrounded()}
        val hearing=i.startActivitySync(Intent(i.targetContext,MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        var recognition:RecognitionActivity?=null
        val monitor=i.addMonitor(RecognitionActivity::class.java.name,null,false)
        try {
            i.runOnMainSync {hearing.findViewById<View>(R.id.navAsl).performClick()}
            i.waitForIdleSync()
            val avatarReady=TextToAslFragment::class.java.getDeclaredField("avatarReady").apply{isAccessible=true}
            await("Existing Text-to-ASL must finish asynchronous setup before typing") {
                var ready=false
                i.runOnMainSync {
                    val host=hearing.supportFragmentManager.findFragmentById(R.id.app_shell_nav_host) as NavHostFragment
                    val fragment=host.childFragmentManager.primaryNavigationFragment as? TextToAslFragment
                    ready=fragment!=null && avatarReady.getBoolean(fragment)
                }
                ready
            }
            i.runOnMainSync {
                hearing.findViewById<EditText>(R.id.input_text).setText("What is your name?")
                hearing.findViewById<View>(R.id.sign_it_button).performClick()
            }
            await("Typed input must reach the existing conversation owner") {
                ConversationPhraseAssist.presentationState.value.hearingText=="What is your name?" &&
                    ConversationPhraseAssist.activeHearingTurnId()!=null
            }
            val hearingId=checkNotNull(ConversationPhraseAssist.activeHearingTurnId())
            i.runOnMainSync {hearing.findViewById<View>(R.id.reply_button).performClick()}
            recognition=checkNotNull(monitor.waitForActivityWithTimeout(45_000) as? RecognitionActivity)
            val a=recognition
            await("Recognition camera/model asynchronous load must complete") {
                field(a,"fingerspellRuntime")!=null && (field(a,"cameraInputFrames") as Int)>0 &&
                    !(field(a,"cameraSwitching") as Boolean)
            }
            val runtime=field(a,"fingerspellRuntime") as FingerspellRuntime
            val executor=field(a,"cameraExecutor") as ExecutorService
            val bridge=field(a,"coordination") as RecognitionCoordinationBridge
            // This test controls idle/no-hand evidence. Physical signing is intentionally excluded.
            i.runOnMainSync {(field(a,"phoneAnalysis") as ImageAnalysis).clearAnalyzer()}
            executor.submit {bridge.observation(true,false)}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.FINGERSPELL,runtime.snapshot.mode)
            assertTrue(runtime.fingerspellOwnsFrames)
            assertEquals(hearingId,ConversationPhraseAssist.activeHearingTurnId())
            assertEquals("What is your name?",ConversationPhraseAssist.recentTurns().last().text)
            // Context supplies a mode, never a guessed name or recognized letters.
            assertEquals("",runtime.snapshot.confirmed)
            assertEquals("",runtime.snapshot.preview)
            i.waitForIdleSync()
            i.runOnMainSync {
                assertEquals("Fingerspell",a.findViewById<TextView>(R.id.coordinationStatus).text.toString())
                for(id in intArrayOf(R.id.coordinationFinish,R.id.coordinationWord,R.id.coordinationSpell))
                    assertNull("Context routes without a chooser",a.findViewById<View>(id))
                a.findViewById<View>(R.id.hearButton).performClick() // Empty spelling cannot finish.
            }
            executor.submit {}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.FINGERSPELL,runtime.snapshot.mode)
            executor.submit {bridge.observation(true,false);bridge.observation(true,false)}.get(10,TimeUnit.SECONDS)
            assertEquals(RecognitionMode.FINGERSPELL,runtime.snapshot.mode)
            assertEquals(RecognitionMode.WORD,settings.current())
            i.targetContext.filesDir.resolve("recognition_context_ui_flow.json").writeText(JSONObject()
                .put("status","CONTEXT_TYPED_REPLY_ROUTING_PASS")
                .put("hearing_text","What is your name?").put("hearing_turn_id",hearingId)
                .put("existing_text_to_asl_submit",true).put("existing_reply_navigation",true)
                .put("automatic_owner","FINGERSPELL").put("controlled_idle_no_hand_evidence",true)
                .put("context_generated_letters",false).put("chooser_absent",true).put("empty_speaker_does_not_complete",true)
                .put("settings_preference_unchanged",true).put("provider","fake")
                .put("accuracy_claim","NONE").toString(2))
        } finally {
            i.removeMonitor(monitor)
            settings.select(previous)
            i.runOnMainSync {recognition?.finish();hearing.finish();ConversationPhraseAssist.appBackgrounded()}
            i.waitForIdleSync()
        }
    }
}
