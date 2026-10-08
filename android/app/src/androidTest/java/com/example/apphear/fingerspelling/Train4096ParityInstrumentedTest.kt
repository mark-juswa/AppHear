package com.example.apphear.fingerspelling

import android.os.Debug
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeFalse
import org.junit.Test
import java.io.DataInputStream
import kotlin.math.abs

/** Frozen epoch038 numerical transfer and CPU cost; never recognition-accuracy evidence. */
class Train4096ParityInstrumentedTest {
    @Test fun exactGeometryCheckpointTransferAndDeviceCost() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val context=instrumentation.targetContext
        val assets=instrumentation.context.assets
        fun read(name:String)=DataInputStream(assets.open("train4096_geometry/$name").buffered())
        val records=JSONArray()
        var kerasError=0f; var tfliteError=0f; var featureError=0f; var featureCount=0
        val beforeHeap=Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory()
        val beforeNative=Debug.getNativeHeapAllocatedSize()
        FingerspellModels(context).use { models ->
            assumeFalse(models.visualEnabled)
            org.junit.Assume.assumeTrue(models.manifest.optString("candidate_id") == "TRAIN4096_EPOCH038_GEOMETRY_ONLY")
            val cases=JSONObject(assets.open("train4096_geometry/cases.json").bufferedReader().use { it.readText() })
            assertEquals(405,models.inputWidth)
            assertEquals("b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886",
                models.manifest.getString("checkpoint_sha256"))
            assertEquals(.5f,models.blankPenalty,0f)
            val rows=cases.getJSONArray("cases")
            assertEquals(14,rows.length())
            for(k in 0 until rows.length()) {
                val case=rows.getJSONObject(k); val id=case.getString("id")
                read("$id.bin").use { input ->
                    val n=input.readInt(); val frames=List(n){ FloatArray(405){input.readFloat()} }
                    val mask=FloatArray(n){input.readFloat()}
                    val keras=Array(n){FloatArray(28){input.readFloat()}}
                    val lite=Array(n){FloatArray(28){input.readFloat()}}
                    assertEquals(-1,input.read())
                    if(case.getBoolean("raw_fixture")) read("$id.input.bin").use { raw ->
                        assertEquals("FingerspellingFeatureAdapter.v1",raw.readUTF())
                        val adapter=FingerspellingFeatureAdapterV1(raw.readFloat(),raw.readFloat())
                        assertEquals(n,raw.readInt())
                        repeat(n){ t ->
                            val feature=adapter.derive(FingerspellParityInstrumentedTest().common(raw))
                            for(c in 0 until 405) {
                                featureError=maxOf(featureError,abs(feature[c]-frames[t][c]))
                                assertEquals("$id feature $t,$c",frames[t][c],feature[c],1e-6f)
                            }
                            featureCount++
                        }
                        assertEquals(-1,raw.read())
                    }
                    val modelTimes=mutableListOf<Double>()
                    var actual=emptyArray<FloatArray>()
                    repeat(3) {
                        val started=SystemClock.elapsedRealtimeNanos()
                        actual=models.logits(frames,mask)
                        modelTimes.add((SystemClock.elapsedRealtimeNanos()-started)/1e6)
                    }
                    for(t in 0 until n) for(c in 0..27) {
                        kerasError=maxOf(kerasError,abs(actual[t][c]-keras[t][c]))
                        tfliteError=maxOf(tfliteError,abs(actual[t][c]-lite[t][c]))
                        assertEquals("$id keras $t,$c",keras[t][c],actual[t][c],2e-4f)
                        assertEquals("$id lite $t,$c",lite[t][c],actual[t][c],2e-4f)
                    }
                    val decodeStarted=SystemClock.elapsedRealtimeNanos()
                    val greedy=FingerspellCtcDecoder.decode(actual,models.blankPenalty)
                    val beamStarted=SystemClock.elapsedRealtimeNanos()
                    val greedyMs=(beamStarted-decodeStarted)/1e6
                    val beam=FingerspellPrefixBeamDecoder.decode(actual,models.blankPenalty).text
                    val beamMs=(SystemClock.elapsedRealtimeNanos()-beamStarted)/1e6
                    assertEquals(id,case.getString("greedy"),greedy)
                    assertEquals(id,case.getString("beam"),beam)
                    val prefix=models.logits(frames.take(maxOf(1,n/2)),mask.copyOf(maxOf(1,n/2)))
                    for(t in prefix.indices) for(c in 0..27) assertEquals(actual[t][c],prefix[t][c],2e-4f)
                    records.put(JSONObject().put("id",id).put("view",case.getString("view"))
                        .put("timesteps",n).put("model_ms",JSONArray(modelTimes))
                        .put("greedy_ms",greedyMs).put("beam_ms",beamMs)
                        .put("warm_model_plus_decoders_ms",modelTimes.last()+greedyMs+beamMs)
                        .put("greedyRaw",greedy).put("beamRaw",beam))
                }
            }
            val report=JSONObject().put("status","TRAIN4096_ANDROID_NUMERICAL_PARITY_PASS")
                .put("fixture_count",14).put("observation_count",featureCount).put("adapter_max_error",featureError)
                .put("keras_android_logit_max_error",kerasError).put("tflite_android_logit_max_error",tfliteError)
                .put("greedy_mismatches",0).put("beam_mismatches",0).put("causal_prefix_cases",14)
                .put("backend","CPU_2_THREADS").put("model_manifest",models.manifest)
                .put("java_heap_before_bytes",beforeHeap)
                .put("java_heap_after_bytes",Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory())
                .put("native_heap_before_bytes",beforeNative).put("native_heap_after_bytes",Debug.getNativeHeapAllocatedSize())
                .put("memory_scope","SNAPSHOTS_NOT_PEAK_OR_ISOLATED_MODEL_BYTES")
                .put("cases",records).put("training",false).put("test_accessed",false)
            context.filesDir.resolve("fingerspell_train4096_parity.json").writeText(report.toString(2))
        }
    }
}
