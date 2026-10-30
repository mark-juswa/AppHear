package com.example.apphear.perceptionvnext

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/**
 * Kotlin V4 continuous hybrid vs its Python spec on TRAIN-signer fixtures (deploy/export_lexical_v4_candidate):
 * the marker decoder vs model/v4/lexical.decode_stream(keep_other=True), and the causal resolver vs
 * eval/v4/hybrid_causal.causal_segments. The fixtures are gitignored (licensed-data derived); a
 * checkout without them skips these tests.
 */
class LexicalV4HybridParityTest {
    private fun fixture(name: String): JsonObject? {
        val file = listOf(
            File("app/src/debug/assets/lexical_v4_candidate_01/$name"),
            File("src/debug/assets/lexical_v4_candidate_01/$name"),
        ).firstOrNull { it.isFile } ?: return null
        return JsonParser.parseString(file.readText()).asJsonObject
    }

    private fun marker(o: JsonObject) = LexicalMarker(
        o["token"].asInt, o["pos"].asInt, o["start"].asInt, o["end"].asInt, o["commit"].asInt, o["peak"].asFloat,
    )

    private fun key(m: LexicalMarker) = listOf(m.token, m.pos, m.start, m.end, m.commit)

    @Test
    fun markerDecoderMatchesPythonDecodeStream() {
        val root = fixture("decoder_fixture.json")
        assumeTrue("lexical V4 fixtures not provisioned", root != null)
        var streams = 0
        var markers = 0
        for (s in checkNotNull(root).getAsJsonArray("streams")) {
            val stream = s.asJsonObject
            val decoder = LexicalMarkerDecoder()
            val actual = ArrayList<LexicalMarker>()
            for (w in stream.getAsJsonArray("windows")) {
                val win = w.asJsonObject
                val argmax = win.getAsJsonArray("argmax").map { it.asInt }.toIntArray()
                val prob = win.getAsJsonArray("max_prob").map { it.asFloat }.toFloatArray()
                actual += decoder.consume(win["t"].asInt, win["start"].asInt, argmax, prob)
            }
            val expected = stream.getAsJsonArray("markers").map { marker(it.asJsonObject) }
            assertEquals("stream $streams", expected.map(::key), actual.map(::key))
            for ((e, a) in expected.zip(actual)) assertEquals(e.peak, a.peak, 1e-6f)
            streams++
            markers += expected.size
        }
        assertEquals(40, streams)
        println("lexical_v4_decoder_parity streams=$streams markers=$markers")
    }

    @Test
    fun causalResolverMatchesPythonCausalSegments() {
        val root = fixture("resolver_fixture.json")
        assumeTrue("lexical V4 fixtures not provisioned", root != null)
        val a = root!!["a"].asInt
        val b = root["b"].asInt
        val d = root["d"].asInt
        assertEquals(HybridConstants.A, a)
        assertEquals(HybridConstants.B, b)
        assertEquals(HybridConstants.D, d)
        var streams = 0
        var segments = 0
        for (s in root.getAsJsonArray("streams")) {
            val stream = s.asJsonObject
            val n = stream["n"].asInt
            val events = stream.getAsJsonArray("events").map {
                val e = it.asJsonObject
                HybridResolver.Event(e["start"].asInt, e["end"].asInt, e["terminal_post"].asInt, e["commit"].asInt)
            }
            val markers = stream.getAsJsonArray("markers").map { marker(it.asJsonObject) }
            val resolver = HybridResolver(a, b, d, streamLength = n)
            val actual = ArrayList<HybridSegment>()
            for (t in 0 until n + 8 * HybridConstants.W) {
                // The phone decoder exposes its open candidate; Python events stand in for it here.
                val open = events.filter { it.start <= t && t < it.commit }.minOfOrNull { it.start }
                val event = events.singleOrNull { it.commit == t }
                actual += resolver.step(t, event, markers.filter { it.commit == t }, open)
            }
            val expected = stream.getAsJsonArray("segments").map {
                val o = it.asJsonObject
                HybridSegment(o["start"].asInt, o["end"].asInt, o["terminal_post"].asInt, o["commit"].asInt, o["emit"].asInt, o["origin"].asString)
            }
            val order = compareBy<HybridSegment>({ it.emit }, { it.start }, { it.end })
            assertEquals("stream $streams", expected.sortedWith(order), actual.sortedWith(order))
            streams++
            segments += expected.size
        }
        assertEquals(324, streams)
        println("lexical_v4_resolver_parity streams=$streams segments=$segments")
    }

    @Test
    fun rowSoftmaxArgmaxIsTheLargestLogitAndItsProbability() {
        val logits = FloatArray(2 * HybridConstants.CLASSES)
        logits[5] = 3f
        logits[HybridConstants.CLASSES + HybridConstants.OTHER] = 1f
        val (idx, prob) = LexicalMarkerDecoder.rowArgmax(logits, 2)
        assertEquals(listOf(5, HybridConstants.OTHER), idx.toList())
        val e3 = kotlin.math.exp(3.0)
        assertEquals((e3 / (e3 + HybridConstants.CLASSES - 1)).toFloat(), prob[0], 1e-6f)
    }
}
