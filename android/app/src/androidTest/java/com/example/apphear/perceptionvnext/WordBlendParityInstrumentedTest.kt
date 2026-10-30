package com.example.apphear.perceptionvnext

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

/**
 * WORD_BLEND_01, WORD_BLEND_02, WORD_MIRROR_BLEND and WORD_V4, each loaded through the production RecognitionV2LiveRecognizer
 * path exactly as the experimental WORD-blend engines load them, reproduce their Keras outputs on
 * the 20 pinned Gate-1 fixture views (Gate-2 tolerances), keep the frozen class order, and report
 * their own identity. Also measures on-device invocation time against the frozen recognizer and the
 * native-heap growth from loading the candidate.
 */
@RunWith(AndroidJUnit4::class)
class WordBlendParityInstrumentedTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    private fun floats(asset: String): FloatArray {
        val bytes = context.assets.open(asset).use { it.readBytes() }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    @Test
    fun wordBlendMatchesKerasOnDeviceAndKeepsTheFrozenVocabulary() =
        checkBlend(PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND)

    @Test
    fun wordBlend02MatchesKerasOnDeviceAndKeepsTheFrozenVocabulary() =
        checkBlend(PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND_02)

    @Test
    fun wordMirrorBlendMatchesKerasOnDeviceAndKeepsTheFrozenVocabulary() =
        checkBlend(PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_MIRROR_BLEND)

    @Test
    fun wordV4MatchesKerasOnDeviceAndKeepsTheFrozenVocabulary() =
        checkBlend(PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_V4)

    private fun checkBlend(configuration: PhoneRecognitionConfiguration) {
        val spec = configuration.wordPackage()
        val manifest = JSONObject(context.assets.open(spec.manifestAsset).bufferedReader().readText())
        RecognitionV2LiveRecognizer(context).use { frozen ->
            System.gc()
            val heapBefore = android.os.Debug.getNativeHeapAllocatedSize()
            RecognitionV2LiveRecognizer(context, spec).use { blend ->
                val loadHeapKb = (android.os.Debug.getNativeHeapAllocatedSize() - heapBefore) / 1024
                assertEquals(frozen.glosses, blend.glosses)
                assertEquals(spec.packageId, blend.identityJson().getString("package_id"))
                assertEquals(spec.modelSha256, blend.identityJson().getString("model_sha256"))
                val views = manifest.getJSONArray("views")
                assertEquals(20, views.length())
                var maxAbs = 0.0
                val blendMs = mutableListOf<Double>()
                val rowsUsed = mutableMapOf<Int, MutableList<Double>>()
                val frozenMs = mutableListOf<Double>()
                repeat(3) { round ->
                    for (i in 0 until views.length()) {
                        val view = views.getJSONObject(i)
                        val maskJson = view.getJSONArray("mask")
                        val mask = BooleanArray(maskJson.length()) { maskJson.getBoolean(it) }
                        val input = RecognitionV2.TemporalView(
                            floats(view.getString("feature_asset")), mask, IntArray(0), DoubleArray(0), mask.count { it },
                        )
                        val prediction = blend.invoke(input, RecognitionV2.FEATURE_SCHEMA)
                        val reference = frozen.invoke(input, RecognitionV2.FEATURE_SCHEMA)
                        if (round > 0) {
                            blendMs += prediction.invocationMs
                            rowsUsed.getOrPut(prediction.modelRows) { mutableListOf() } += prediction.invocationMs
                            frozenMs += reference.invocationMs
                        }
                        val expected = floats(view.getString("keras_output_asset"))
                        for (c in expected.indices) {
                            maxAbs = maxOf(maxAbs, abs(prediction.probabilities[c] - expected[c]).toDouble())
                        }
                        assertEquals(view.getJSONArray("keras_top5_indices").getInt(0), prediction.top5.first())
                    }
                }
                assertTrue("max_abs=$maxAbs", maxAbs <= 1e-4)
                val identity = blend.identityJson()
                if (identity.has("short_model_rows")) {
                    // A package with a short model must actually use it for the fixtures that fit.
                    assertTrue("short model never ran: $rowsUsed", rowsUsed.containsKey(identity.getInt("short_model_rows")))
                }
                blendMs.sort()
                frozenMs.sort()
                android.util.Log.i(
                    "AppHearPhone",
                    "word_blend_parity package=${spec.packageId} max_abs=$maxAbs " +
                        "blend_ms_median=${blendMs[blendMs.size / 2]} " +
                        "blend_ms_p95=${blendMs[(blendMs.size * 95) / 100]} " +
                        "frozen_ms_median=${frozenMs[frozenMs.size / 2]} " +
                        "frozen_ms_p95=${frozenMs[(frozenMs.size * 95) / 100]} " +
                        "load_native_heap_kb=$loadHeapKb " +
                        "by_rows=" + rowsUsed.toSortedMap().entries.joinToString(";") { (rows, ms) ->
                            ms.sort()
                            "rows$rows:n=${ms.size}:median=${ms[ms.size / 2]}"
                        },
                )
            }
        }
    }
}
