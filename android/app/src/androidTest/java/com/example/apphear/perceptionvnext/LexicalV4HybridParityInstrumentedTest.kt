package com.example.apphear.perceptionvnext

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

/**
 * V4 continuous hybrid, lexical side on the phone: for 6 TRAIN-signer fixture streams, every per-observation
 * window is built and featurized by RecognitionV2.deriveSelectedFeatures, run through the production
 * LexicalV4Runner (1 thread, XNNPACK) and decoded by LexicalMarkerDecoder. Logits must match the host
 * TFLite and the committed markers must equal Python's. Also reports the per-observation cost
 * (features + model + decode) on this device.
 */
@RunWith(AndroidJUnit4::class)
class LexicalV4HybridParityInstrumentedTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun lexicalC2MatchesHostAndPythonMarkersOnDevice() {
        val fixture = JSONObject(context.assets.open("lexical_v4_candidate_01/stream_fixture.json").bufferedReader().readText())
        val expectedLogits = context.assets.open("lexical_v4_candidate_01/stream_fixture_logits.f32").use { it.readBytes() }
            .let { ByteBuffer.wrap(it).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer() }
        val stride = HybridConstants.W * HybridConstants.CLASSES
        System.gc()
        val heapBefore = android.os.Debug.getNativeHeapAllocatedSize()
        LexicalV4Runner(context, PhoneRecognitionConfiguration.LEXICAL_C2).use { runner ->
            val loadHeapKb = (android.os.Debug.getNativeHeapAllocatedSize() - heapBefore) / 1024
            var maxAbs = 0.0
            var argmaxRows = 0
            var argmaxSame = 0
            var windows = 0
            var markers = 0
            val totalMs = mutableListOf<Double>()
            val modelMs = mutableListOf<Double>()
            val streams = fixture.getJSONArray("streams")
            for (s in 0 until streams.length()) {
                val stream = streams.getJSONObject(s)
                val raw = parseRaw(stream.getJSONObject("raw"))
                val decoder = LexicalMarkerDecoder()
                val actual = ArrayList<LexicalMarker>()
                for (t in 0 until raw.length) {
                    val started = System.nanoTime()
                    val start = maxOf(0, t - HybridConstants.W + 1)
                    val rows = t - start + 1
                    val features = RecognitionV2.deriveSelectedFeatures(slice(raw, start, t), IntArray(rows) { it })
                    val modelStarted = System.nanoTime()
                    val logits = runner.logits(features, rows)
                    val modelElapsed = (System.nanoTime() - modelStarted) / 1_000_000.0
                    val (argmax, prob) = LexicalMarkerDecoder.rowArgmax(logits, rows)
                    actual += decoder.consume(t, start, argmax, prob)
                    totalMs += (System.nanoTime() - started) / 1_000_000.0
                    modelMs += modelElapsed
                    val expected = FloatArray(stride).also { expectedLogits.get(it) }
                    for (r in 0 until rows) {
                        var hostTop = 0
                        for (c in 0 until HybridConstants.CLASSES) {
                            maxAbs = maxOf(maxAbs, abs(logits[r * HybridConstants.CLASSES + c] - expected[r * HybridConstants.CLASSES + c]).toDouble())
                            if (expected[r * HybridConstants.CLASSES + c] > expected[r * HybridConstants.CLASSES + hostTop]) hostTop = c
                        }
                        argmaxRows++
                        if (argmax[r] == hostTop) argmaxSame++
                    }
                    windows++
                }
                assertEquals(stream.getInt("windows"), raw.length)
                val expected = stream.getJSONArray("markers")
                val expectedKeys = (0 until expected.length()).map { expected.getJSONObject(it) }
                    .map { listOf(it.getInt("token"), it.getInt("pos"), it.getInt("start"), it.getInt("end"), it.getInt("commit")) }
                assertEquals("stream $s", expectedKeys, actual.map { listOf(it.token, it.pos, it.start, it.end, it.commit) })
                markers += actual.size
            }
            assertEquals(0, expectedLogits.remaining())
            assertTrue("max_abs=$maxAbs", maxAbs <= 1e-3)
            assertEquals(argmaxRows, argmaxSame)
            // first windows include interpreter warm-up; time the rest
            val total = totalMs.drop(10).sorted()
            val model = modelMs.drop(10).sorted()
            android.util.Log.i(
                "AppHearPhone",
                "lexical_v4_parity windows=$windows markers=$markers max_abs_logit=$maxAbs argmax_rows=$argmaxSame/$argmaxRows " +
                    "per_observation_ms_median=${total[total.size / 2]} per_observation_ms_p95=${total[(total.size * 95) / 100]} " +
                    "model_ms_median=${model[model.size / 2]} model_ms_p95=${model[(model.size * 95) / 100]} " +
                    "load_native_heap_kb=$loadHeapKb",
            )
        }
    }

    /** Observations [from, to] of [raw], as eval/runtime_diagnostics.s2_r3_context_suite.slice_raw. */
    private fun slice(raw: RecognitionV2.RawSequence, from: Int, to: Int): RecognitionV2.RawSequence {
        fun <T> rows(per: Int, take: (Int, Int) -> T) = take(from * per, (to + 1) * per)
        return RecognitionV2.RawSequence(
            schema = raw.schema, imageSemantics = raw.imageSemantics,
            frameIndex = raw.frameIndex.copyOfRange(from, to + 1),
            timestampMs = raw.timestampMs.copyOfRange(from, to + 1),
            sourceSize = rows(2) { a, b -> raw.sourceSize.copyOfRange(a, b) },
            handXy = rows(2 * 21 * 2) { a, b -> raw.handXy.copyOfRange(a, b) },
            handProposalSupport = rows(2 * 21) { a, b -> raw.handProposalSupport.copyOfRange(a, b) },
            handJointValid = rows(2 * 21) { a, b -> raw.handJointValid.copyOfRange(a, b) },
            handPresence = rows(2) { a, b -> raw.handPresence.copyOfRange(a, b) },
            handObserved = rows(2) { a, b -> raw.handObserved.copyOfRange(a, b) },
            bodyXy = rows(8 * 2) { a, b -> raw.bodyXy.copyOfRange(a, b) },
            bodySupport = rows(8) { a, b -> raw.bodySupport.copyOfRange(a, b) },
            bodyValid = rows(8) { a, b -> raw.bodyValid.copyOfRange(a, b) },
            bodyAvailable = raw.bodyAvailable.copyOfRange(from, to + 1),
        )
    }

    private fun parseRaw(o: JSONObject) = RecognitionV2.RawSequence(
        schema = o.getString("schema"), imageSemantics = o.getString("image_semantics"),
        frameIndex = o.getJSONArray("frame_index").ints(), timestampMs = o.getJSONArray("timestamp_ms").doubles(),
        sourceSize = o.getJSONArray("source_size").ints(), handXy = o.getJSONArray("hand_xy").floats(),
        handProposalSupport = o.getJSONArray("hand_proposal_support").floats(),
        handJointValid = o.getJSONArray("hand_joint_valid").booleans(), handPresence = o.getJSONArray("hand_presence").floats(),
        handObserved = o.getJSONArray("hand_observed").booleans(), bodyXy = o.getJSONArray("body_xy").floats(),
        bodySupport = o.getJSONArray("body_support").floats(), bodyValid = o.getJSONArray("body_valid").booleans(),
        bodyAvailable = o.getJSONArray("body_available").booleans(),
    )

    private fun JSONArray.ints() = IntArray(length()) { getInt(it) }
    private fun JSONArray.doubles() = DoubleArray(length()) { getDouble(it) }
    private fun JSONArray.floats() = FloatArray(length()) { getDouble(it).toFloat() }
    private fun JSONArray.booleans() = BooleanArray(length()) { getBoolean(it) }
}
