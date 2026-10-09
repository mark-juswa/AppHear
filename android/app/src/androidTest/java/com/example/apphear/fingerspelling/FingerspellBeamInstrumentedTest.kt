package com.example.apphear.fingerspelling

import android.content.Intent
import android.os.SystemClock
import android.util.Log
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

class FingerspellBeamInstrumentedTest {
    @Test fun fullFrozenPythonBeamParityAndDeviceCost() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val records = JSONArray(); val timings = linkedMapOf<String, MutableList<Double>>()
        var maxError = 0.0; var differences = 0
        val beforeHeap = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory()
        val started = SystemClock.elapsedRealtimeNanos()
        DataInputStream(instrumentation.context.assets.open("fingerspell_beam/fixtures.bin").buffered()).use { input ->
            assertEquals("apphear.fingerspelling.beam_fixture.v1", input.readUTF())
            assertEquals(10, input.readInt()); val penalty = input.readFloat(); assertEquals(.5f, penalty, 0f)
            val count = input.readInt(); assertEquals(523, count)
            repeat(count) { index ->
                val name = input.readUTF(); val view = input.readUTF()
                val logits = Array(input.readInt()) { FloatArray(28) { input.readFloat() } }
                val expected = input.readUTF(); val greedy = input.readUTF(); val score = input.readDouble()
                val begin = SystemClock.elapsedRealtimeNanos()
                val actual = FingerspellPrefixBeamDecoder.decode(logits, penalty)
                val ms = (SystemClock.elapsedRealtimeNanos() - begin) / 1e6
                assertEquals(name, expected, actual.text)
                assertEquals(name, greedy, FingerspellCtcDecoder.decode(logits, penalty))
                val error = abs(score - actual.logCtcMassPruned); maxError = maxOf(maxError, error)
                assertEquals(name, score, actual.logCtcMassPruned, 1e-8)
                if (expected != greedy) differences++
                timings.getOrPut(view) { mutableListOf() }.add(ms)
                records.put(JSONObject().put("id",name).put("view",view).put("timesteps",logits.size)
                    .put("beamRaw",actual.text).put("greedyRaw",greedy).put("beam_ms",ms).put("score_error",error))
                if ((index+1)%32==0) Log.i("AppHearBeamParity","completed=${index+1}/$count")
            }
            assertEquals(-1,input.read())
        }
        assertEquals(416,differences)
        val groups = JSONObject()
        for ((name, values) in timings) {
            val sorted=values.sorted()
            groups.put(name,JSONObject().put("count",sorted.size).put("p50_ms",sorted[(sorted.size-1)/2])
                .put("p95_ms",sorted[((sorted.size-1)*.95).toInt()]).put("max_ms",sorted.last())
                .put("total_ms",sorted.sum()))
        }
        val report=JSONObject().put("status","ANDROID_BEAM_PARITY_PASS").put("fixture_count",523)
            .put("dev_views",512).put("synthetic_cases",11).put("beam_width",10).put("blank_penalty",.5)
            .put("text_mismatches",0).put("beam_differs_from_greedy",differences).put("maximum_score_error",maxError)
            .put("decoder_runtime",groups).put("seconds",(SystemClock.elapsedRealtimeNanos()-started)/1e9)
            .put("java_heap_before_bytes",beforeHeap)
            .put("java_heap_after_bytes",Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory())
            .put("heap_interpretation","SNAPSHOT_NOT_PEAK_OR_ALLOCATED_BYTES")
            .put("rows",records).put("training",false).put("test_accessed",false)
        instrumentation.targetContext.filesDir.resolve("fingerspell_beam_parity.json").writeText(report.toString(2))
    }

    @Test fun wordModeCannotInvokeEitherSpellingDecoderEvenWithCaptureState() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val activity=instrumentation.startActivitySync(Intent(instrumentation.targetContext,
            RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as RecognitionActivity
        fun field(name:String):Any? = RecognitionActivity::class.java.getDeclaredField(name).apply { isAccessible=true }.get(activity)
        try {
            val deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(20)
            while(field("fingerspellRuntime")==null && System.nanoTime()<deadline) Thread.sleep(100)
            val runtime=checkNotNull(field("fingerspellRuntime") as? FingerspellRuntime)
            val executor=field("cameraExecutor") as ExecutorService
            val word=field("phoneSession") as PhoneProductionSession
            executor.submit {
                runtime.select(RecognitionMode.WORD)
                fun readInt(name:String)=FingerspellRuntime::class.java.getDeclaredField(name).apply { isAccessible=true }.getInt(runtime)
                val beforeBeam=readInt("beamDecodeCalls"); val beforeGreedy=readInt("greedyDecodeCalls")
                val beforeSentence=word.sentenceText
                val session=FingerspellRuntime::class.java.getDeclaredField("session").apply { isAccessible=true }.get(runtime) as FingerspellSession
                // Deliberately inject otherwise impossible capture state. Ownership
                // must still guard Done before model or decoder invocation.
                session.start(); session.consume(0.0,FloatArray(session.inputWidth)); runtime.finish()
                assertEquals(FingerspellPhase.CAPTURING,session.phase)
                assertEquals(beforeBeam,readInt("beamDecodeCalls")); assertEquals(beforeGreedy,readInt("greedyDecodeCalls"))
                assertEquals(beforeSentence,word.sentenceText)
                session.cancel()
                assertEquals(RecognitionMode.WORD,runtime.snapshot.mode)
            }.get(10,TimeUnit.SECONDS)
        } finally {
            instrumentation.runOnMainSync { activity.finish() }; instrumentation.waitForIdleSync()
        }
    }
}
