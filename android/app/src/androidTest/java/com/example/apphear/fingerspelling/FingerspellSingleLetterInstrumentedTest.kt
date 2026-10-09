package com.example.apphear.fingerspelling

import android.content.Intent
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.RecognitionActivity
import com.example.apphear.perceptionvnext.PhoneProductionSession
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.DataInputStream
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit
import kotlin.math.abs

class FingerspellSingleLetterInstrumentedTest {
    @Test fun exactPythonParity() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val records=JSONArray(); var maximum=0.0
        DataInputStream(instrumentation.context.assets.open("fingerspell_single_letter/fixtures.bin").buffered()).use { input ->
            assertEquals(FingerspellSingleLetterDecoder.VERSION,input.readUTF())
            val count=input.readInt()
            repeat(count) {
                val name=input.readUTF(); val logits=Array(input.readInt()) { FloatArray(28) { input.readFloat() } }
                val text=input.readUTF(); val best=input.readUTF()
                val scores=DoubleArray(26) { input.readDouble() }
                val empty=input.readDouble(); val space=input.readDouble()
                val start=SystemClock.elapsedRealtimeNanos()
                val actual=FingerspellSingleLetterDecoder.decode(logits)
                val ms=(SystemClock.elapsedRealtimeNanos()-start)/1e6
                assertEquals(name,text,actual.text); assertEquals(name,best,actual.bestLetter)
                for(c in 0..25) {
                    assertEquals(name,scores[c],actual.letterLogMasses[c],1e-8)
                    if(scores[c].isFinite()) maximum=maxOf(maximum,abs(scores[c]-actual.letterLogMasses[c]))
                }
                assertEquals(name,empty,actual.emptyLogMass,1e-8)
                assertEquals(name,space,actual.spaceLogMass,1e-8)
                records.put(JSONObject().put("id",name).put("timesteps",logits.size).put("text",actual.text).put("decoder_ms",ms))
            }
            assertEquals(-1,input.read())
            instrumentation.targetContext.filesDir.resolve("fingerspell_single_letter_parity.json").writeText(
                JSONObject().put("status","SINGLE_LETTER_CTC_PARITY_PASS").put("fixtures",count)
                    .put("maximum_score_error",maximum).put("rows",records).put("accuracy_claim",false).toString(2))
        }
    }
    @Test fun confirmationRefusalAndWordIsolation() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val activity=instrumentation.startActivitySync(Intent(instrumentation.targetContext,
            RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        fun field(name:String):Any?=RecognitionActivity::class.java.getDeclaredField(name).apply {isAccessible=true}.get(activity)
        try {
            val deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(20)
            while(field("fingerspellRuntime")==null && System.nanoTime()<deadline) Thread.sleep(100)
            val runtime=checkNotNull(field("fingerspellRuntime") as? FingerspellRuntime)
            val executor=field("cameraExecutor") as ExecutorService
            val word=field("phoneSession") as PhoneProductionSession
            executor.submit {
                assertTrue(runtime.singleLetterMode)
                val before=word.sentenceText
                val session=FingerspellRuntime::class.java.getDeclaredField("session").apply {isAccessible=true}.get(runtime) as FingerspellSession
                fun readCalls()=FingerspellRuntime::class.java.getDeclaredField("singleLetterDecodeCalls").apply {isAccessible=true}.getInt(runtime)
                runtime.select(RecognitionMode.FINGERSPELL)
                for(letter in "AMYLL") {
                    runtime.start(); session.consume(0.0,FloatArray(405))
                    val (token,_)=session.finish(); assertTrue(session.complete(token,letter.toString()))
                    runtime.confirm()
                }
                assertEquals("AMYLL",runtime.snapshot.confirmed)
                runtime.retry(); assertEquals("AMYLL",runtime.snapshot.confirmed)
                runtime.clear(); assertEquals("",runtime.snapshot.confirmed)
                val beforeCalls=readCalls()
                runtime.start(); session.consume(0.0,FloatArray(405)); runtime.finish()
                assertEquals(FingerspellPhase.ERROR,runtime.snapshot.phase)
                assertEquals(beforeCalls,readCalls()) // no-input capture never reaches model/decoder
                runtime.select(RecognitionMode.WORD)
                session.start(); session.consume(0.0,FloatArray(405)); runtime.finish()
                assertEquals(beforeCalls,readCalls())
                assertEquals(before,word.sentenceText); session.cancel()
            }.get(10,TimeUnit.SECONDS)
        } finally {instrumentation.runOnMainSync {activity.finish()}; instrumentation.waitForIdleSync()}
    }
}
