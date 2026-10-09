package com.example.apphear.perceptionvnext

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.nio.ByteOrder

@RunWith(AndroidJUnit4::class)
class PhoneS2ParityInstrumentedTest {
    @Test
    fun retainingDiagnosticNormalizedRowDoesNotChangeInference() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val rows = context.assets.open(RAW_FEATURE_ASSET).use { it.readBytes() }.floats()
        val first = rows.copyOfRange(0, PhoneS2Runner.FEATURE_WIDTH)
        PhoneS2Runner(context).use { control ->
            PhoneS2Runner(context).use { instrumented ->
                val expected = control.predict(first)
                val actual = instrumented.predict(first, retainNormalizedInputDiagnostic = true)
                assertTrue(actual.normalizedInputDiagnostic?.size == PhoneS2Runner.FEATURE_WIDTH)
                assertEquals(expected.argmaxState, actual.argmaxState)
                expected.probabilities.indices.forEach { state ->
                    assertTrue(kotlin.math.abs(expected.probabilities[state] - actual.probabilities[state]) <= 1e-7f)
                }
            }
        }
    }

    @Test
    fun everyFrozenCalPrefixMatchesExportedTfliteProbabilities() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val features = context.assets.open(FEATURE_ASSET).use { it.readBytes() }.floats()
        val expected = context.assets.open(PROBABILITY_ASSET).use { it.readBytes() }.floats()
        assertEquals(0, features.size % PhoneS2Runner.FEATURE_WIDTH)
        val count = features.size / PhoneS2Runner.FEATURE_WIDTH
        assertEquals(count * PhoneS2Runner.STATE_COUNT, expected.size)
        PhoneS2Runner(context).use { runner ->
            repeat(count) { observation ->
                val row = features.copyOfRange(
                    observation * PhoneS2Runner.FEATURE_WIDTH,
                    (observation + 1) * PhoneS2Runner.FEATURE_WIDTH,
                )
                val actual = runner.predictNormalizedFixture(row)
                repeat(PhoneS2Runner.STATE_COUNT) { state ->
                    val difference = kotlin.math.abs(
                        actual.probabilities[state] - expected[observation * 3 + state],
                    )
                    assertTrue("obs=$observation state=$state diff=$difference", difference <= 1e-4f)
                }
            }
        }
    }

    @Test
    fun candidatePhonePrefixMatchesFrozenKerasExportAndControlRemainsAvailable() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val root = PhoneS2Package.S2_R2_CANDIDATE.assetRoot
        val features = context.assets.open("$root/phone_parity_raw_features.f32")
            .use { it.readBytes() }.floats()
        val normalized = context.assets.open("$root/phone_parity_normalized_features.f32")
            .use { it.readBytes() }.floats()
        val expected = context.assets.open("$root/phone_parity_probabilities.f32")
            .use { it.readBytes() }.floats()
        val count = features.size / PhoneS2Runner.FEATURE_WIDTH
        assertEquals(0, features.size % PhoneS2Runner.FEATURE_WIDTH)
        assertEquals(features.size, normalized.size)
        assertEquals(count * PhoneS2Runner.STATE_COUNT, expected.size)
        PhoneS2Runner(context, PhoneS2Package.S2_R2_CANDIDATE).use { candidate ->
            assertEquals("S2_R2_CANDIDATE", candidate.identityJson().getString("package_id"))
            repeat(count) { observation ->
                val row = features.copyOfRange(
                    observation * PhoneS2Runner.FEATURE_WIDTH,
                    (observation + 1) * PhoneS2Runner.FEATURE_WIDTH,
                )
                val actual = candidate.predict(row, retainNormalizedInputDiagnostic = true)
                val actualNormalized = requireNotNull(actual.normalizedInputDiagnostic)
                repeat(PhoneS2Runner.FEATURE_WIDTH) { feature ->
                    val difference = kotlin.math.abs(
                        actualNormalized[feature] - normalized[observation * PhoneS2Runner.FEATURE_WIDTH + feature],
                    )
                    assertTrue("obs=$observation feature=$feature diff=$difference", difference <= 1e-6f)
                }
                repeat(PhoneS2Runner.STATE_COUNT) { state ->
                    val difference = kotlin.math.abs(
                        actual.probabilities[state] - expected[observation * 3 + state],
                    )
                    assertTrue("obs=$observation state=$state diff=$difference", difference <= 1e-4f)
                }
            }
        }
        PhoneS2Runner(context, PhoneS2Package.PHASE7_CONTROL).use { control ->
            assertEquals("PHASE7_CONTROL", control.identityJson().getString("package_id"))
        }
    }

    private fun ByteArray.floats(): FloatArray {
        require(size % 4 == 0)
        val source = ByteBuffer.wrap(this).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(size / 4).also(source::get)
    }

    companion object {
        private const val ROOT = "phone_causal_recognition_01"
        private const val FEATURE_ASSET = "$ROOT/s2_parity_normalized_features.f32"
        private const val PROBABILITY_ASSET = "$ROOT/s2_parity_probabilities.f32"
        private const val RAW_FEATURE_ASSET = "$ROOT/segmentation_feature_parity_expected.f32"
    }
}
