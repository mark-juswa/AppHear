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
 * The WORD v2 shadow package, loaded through the same RecognitionV2LiveRecognizer path the shadow
 * uses, reproduces its Keras outputs on the 20 pinned Gate-1 fixture views (Gate-2 tolerances).
 * The frozen package keeps loading unchanged with the default spec.
 */
@RunWith(AndroidJUnit4::class)
class WordV2ShadowParityInstrumentedTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    private fun floats(asset: String): FloatArray {
        val bytes = context.assets.open(asset).use { it.readBytes() }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    @Test
    fun wordV2ShadowMatchesKerasOnDevice() {
        val spec = WordShadowPackages.WORD_V2_CANDIDATE
        val manifest = JSONObject(context.assets.open(spec.manifestAsset).bufferedReader().readText())
        RecognitionV2LiveRecognizer(context, spec).use { recognizer ->
            val views = manifest.getJSONArray("views")
            assertEquals(20, views.length())
            var maxAbs = 0.0
            for (i in 0 until views.length()) {
                val view = views.getJSONObject(i)
                val maskJson = view.getJSONArray("mask")
                val mask = BooleanArray(maskJson.length()) { maskJson.getBoolean(it) }
                val features = floats(view.getString("feature_asset"))
                val expected = floats(view.getString("keras_output_asset"))
                val prediction = recognizer.invoke(
                    RecognitionV2.TemporalView(features, mask, IntArray(0), DoubleArray(0), mask.count { it }),
                    RecognitionV2.FEATURE_SCHEMA,
                )
                for (c in expected.indices) maxAbs = maxOf(maxAbs, abs(prediction.probabilities[c] - expected[c]).toDouble())
                assertEquals(view.getJSONArray("keras_top5_indices").getInt(0), prediction.top5.first())
            }
            assertTrue("max_abs=$maxAbs", maxAbs <= 1e-4)
            assertEquals("WORD_V2_CANDIDATE", recognizer.identityJson().getString("package_id"))
        }
        RecognitionV2LiveRecognizer(context).use { frozen ->
            assertTrue(!frozen.identityJson().has("package_id"))
            assertEquals(RecognitionV2LiveRecognizer.MODEL_SHA, frozen.identityJson().getString("model_sha256"))
        }
    }
}
