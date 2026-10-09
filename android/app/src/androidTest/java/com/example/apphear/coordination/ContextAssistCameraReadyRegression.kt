package com.example.apphear.coordination

import android.content.Intent
import android.view.View
import android.widget.TextView
import androidx.camera.core.ImageAnalysis
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.BuildConfig
import com.example.apphear.MainActivity
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.contextassist.*
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.fingerspelling.RecognitionMode
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.pipeline.recognition.RecognitionState
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.TimeUnit

/** Existing WORD context behavior, with the actual asynchronous camera seam ready first. */
class ContextAssistCameraReadyRegression {
    private val i get()=InstrumentationRegistry.getInstrumentation()
    private fun field(a:RecognitionActivity,n:String)=a.javaClass.getDeclaredField(n).apply{isAccessible=true}.get(a)
    private fun frame(id:Int,word:String,alternative:SignScore?=null,sentence:String=word)=FrameResult(
        hands=null,pose=null,imageWidth=480,imageHeight=360,fps=5.0,isFrontCamera=true,
        qualityLabel="TEST",poseEveryN=1,
        recognition=RecognitionState.Committed(word,0,listOf(word)),phoneReady=true,phoneSentence=sentence,
        recognitionEvidence=RecognitionEvidence(id,id.toLong(),word,
            listOf(SignScore(word,if(word=="THINK")0.35f else 0.72f))+listOfNotNull(alternative)))

    private fun runReady(name:String,check:(RecognitionActivity)->Unit)=runBlocking {
        assumeTrue(BuildConfig.CONTEXT_PHRASE_ASSIST_ENABLED && BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER=="fake")
        RecognitionModeSettings(i.targetContext).select(RecognitionMode.WORD)
        i.runOnMainSync {ConversationPhraseAssist.appBackgrounded()}
        val hearing=i.startActivitySync(Intent(i.targetContext,MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        try {
            checkNotNull(ConversationPhraseAssist.recordHearingMessage(i.targetContext,"Where are you going?",
                ConversationSource.TYPED_TEXT)).join()
            val a=i.startActivitySync(Intent(i.targetContext,RecognitionActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
            try {
                val initial=JSONObject().put("initial_camera_generation",field(a,"cameraGeneration"))
                    .put("initial_processing_generation",field(a,"processingCameraGeneration"))
                    .put("initial_camera_switching",field(a,"cameraSwitching"))
                    .put("initial_input_frames",field(a,"cameraInputFrames"))
                val end=System.nanoTime()+TimeUnit.SECONDS.toNanos(45)
                while((field(a,"fingerspellRuntime")==null || (field(a,"cameraSwitching") as Boolean) ||
                    (field(a,"cameraInputFrames") as Int)<1) && System.nanoTime()<end) Thread.sleep(50)
                assertFalse("Camera binding ready before saved-frame replay",field(a,"cameraSwitching") as Boolean)
                assertTrue((field(a,"cameraInputFrames") as Int)>0)
                assertEquals(field(a,"cameraGeneration"),field(a,"processingCameraGeneration"))
                i.runOnMainSync {(field(a,"phoneAnalysis") as ImageAnalysis).clearAnalyzer()}
                i.waitForIdleSync()
                check(a)
                initial.put("status","WORD_CONTEXT_READY_REPLAY_PASS").put("coordination_enabled",BuildConfig.RECOGNITION_COORDINATION_ENABLED)
                    .put("accuracy_claim","NONE")
                i.targetContext.filesDir.resolve("context_ready_${name}.json").writeText(initial.toString(2))
            } finally {i.runOnMainSync {a.finish()};i.waitForIdleSync()}
        } finally {i.runOnMainSync {hearing.finish();ConversationPhraseAssist.appBackgrounded()};i.waitForIdleSync()}
    }

    @Test fun rawWordHearAndAdvisoryRemainUnchanged()=runReady("hear") {a->
        val onFrame=a.javaClass.getDeclaredMethod("onFrame",FrameResult::class.java).apply{isAccessible=true}
        val speaker=a.javaClass.getDeclaredField("speakSentence").apply{isAccessible=true}
        val spoken=mutableListOf<String>()
        i.runOnMainSync {
            speaker.set(a,{text:String->spoken.add(text);Unit})
            onFrame.invoke(a,frame(1,"GO"))
            assertEquals(View.VISIBLE,a.findViewById<View>(R.id.possibleRepliesGroup).visibility)
            onFrame.invoke(a,frame(2,"THINK",SignScore("HOME",0.33f),"GO THINK"))
            assertEquals(View.VISIBLE,a.findViewById<View>(R.id.contextSupportedGroup).visibility)
            assertEquals("I'm going home.",a.findViewById<TextView>(R.id.contextSupportedText).text.toString())
            a.findViewById<View>(R.id.hearButton).performClick()
            assertEquals(listOf("GO THINK"),spoken)
            assertEquals("GO THINK",a.findViewById<TextView>(R.id.sentenceText).text.toString())
            val evaluation=ConversationPhraseAssist.recentShadowEvaluations().last()
            assertEquals(ShadowReason.MATCH,evaluation.reason)
            assertEquals(listOf("GO","THINK"),evaluation.rawEventGlosses)
            assertEquals(listOf("GO","HOME"),evaluation.assistedCandidate?.assistedGlosses)
            assertEquals("GO THINK",ConversationPhraseAssist.recentTurns().last().text)
        }
    }

    @Test fun stoppingWordReplyStillClosesHintsAndPreservesRawUi()=runReady("stop") {a->
        val onFrame=a.javaClass.getDeclaredMethod("onFrame",FrameResult::class.java).apply{isAccessible=true}
        i.runOnMainSync {
            onFrame.invoke(a,frame(1,"GO"))
            assertEquals(View.VISIBLE,a.findViewById<View>(R.id.possibleRepliesGroup).visibility)
            i.callActivityOnStop(a)
            assertEquals(View.GONE,a.findViewById<View>(R.id.possibleRepliesGroup).visibility)
            assertEquals("GO",a.findViewById<TextView>(R.id.sentenceText).text.toString())
            assertTrue(ConversationPhraseAssist.visibleRepliesForEvidence(emptyList()).isEmpty())
        }
    }
}
