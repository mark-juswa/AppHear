package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Shadow-only echo counterfactual: it must be OFF by default, observe without changing anything, log numbers only, stay bounded, never
 * throw into the analyzer, and report which grid values WOULD have suppressed the weaker group. No threshold is selected by this code.
 */
class HandEchoShadowTest {
    private fun roi(cx: Float, cy: Float, side: Float = 100f) = PerceptionVNextMath.HandRoi(cx, cy, side, 480, 640, 10)

    private fun group(
        support: Float, observed: Boolean = true, roi: PerceptionVNextMath.HandRoi? = roi(200f, 300f),
        presence: Float = 0.98f, handedness: Float = 0.5f, bodyWristSupport: Float = 0.5f,
    ) = EchoGroupInput(
        proposalPresent = roi != null, observed = observed, supportMean = support, pointsGe030 = if (support >= 0.3f) 21 else 0,
        pointsGe010 = 21, presence = presence, handedness = handedness, roi = roi,
        wristXy = floatArrayOf(200f, 300f), bodyWristXy = floatArrayOf(205f, 305f), bodyWristSupport = bodyWristSupport,
        refinedXy = FloatArray(42) { 200f + it }, refinedValid = BooleanArray(21) { true },
    )

    private fun shadow(enabled: Boolean = true, max: Int = 1000, sink: MutableList<String> = mutableListOf()) =
        HandEchoShadow(enabled, max) { sink.add(it) } to sink

    @Test fun disabledShadowObservesNothingAndLogsNothing() {
        val (s, sink) = shadow(enabled = false)
        assertNull(s.observe(0, 1L, group(0.2f), group(0.8f)))
        assertTrue(sink.isEmpty())
    }

    @Test fun clearEchoWouldBeSuppressedAtEveryGridValueAndTheWeakerSideIsReported() {
        val (s, _) = shadow()
        val r = requireNotNull(s.observe(1, 5L, group(support = 0.15f), group(support = 0.60f)))
        assertEquals(0.25, r.ratio!!, 1e-6)
        assertEquals(EchoSide.LEFT, r.weakerSide)
        assertEquals(0b11111, r.wouldSuppressMask)                     // 0.25 < 0.3 .. 0.7
        assertEquals(listOf(0.3f, 0.4f, 0.5f, 0.6f, 0.7f), HandEchoShadow.RATIO_GRID.toList())
    }

    @Test fun midRatioIsSuppressedOnlyByTheLargerGridValues() {
        val r = requireNotNull(shadow().first.observe(1, 5L, group(0.45f), group(1.0f)))   // ratio 0.45
        assertEquals(0b11100, r.wouldSuppressMask)                                         // 0.5, 0.6, 0.7 only
    }

    @Test fun genuinePairWithEqualSupportIsNeverSuppressed() {
        val r = requireNotNull(shadow().first.observe(1, 5L, group(0.79f), group(0.80f)))
        assertEquals(0, r.wouldSuppressMask)
        assertTrue(r.ratio!! > 0.9)
    }

    @Test fun regionsThatDoNotOverlapAreNeverSuppressedWhateverTheRatio() {
        val r = requireNotNull(shadow().first.observe(1, 5L, group(0.1f, roi = roi(80f, 300f)), group(0.9f, roi = roi(400f, 300f))))
        assertEquals(0, r.wouldSuppressMask)
        assertEquals(0.0, r.roiIou!!, 1e-9)
    }

    @Test fun nothingIsSuppressedUnlessBothGroupsAreObserved() {
        val r = requireNotNull(shadow().first.observe(1, 5L, group(0.1f, observed = false), group(0.9f)))
        assertEquals(0, r.wouldSuppressMask)
        assertNull(r.ratio)
    }

    @Test fun observingDoesNotMutateAnyInput() {
        val l = group(0.15f)
        val r = group(0.6f)
        val before = listOf(l.refinedXy.copyOf(), r.refinedXy.copyOf(), l.wristXy.copyOf(), r.bodyWristXy.copyOf())
        shadow().first.observe(1, 5L, l, r)
        assertTrue(before[0].contentEquals(l.refinedXy) && before[1].contentEquals(r.refinedXy))
        assertTrue(before[2].contentEquals(l.wristXy) && before[3].contentEquals(r.bodyWristXy))
    }

    @Test fun logLineIsOneJsonObjectOfNumbersAndFlagsWithoutAnyCoordinates() {
        val (s, sink) = shadow()
        s.observe(7, 1234L, group(0.15f, handedness = 0.9f), group(0.6f, handedness = 0.95f))
        assertEquals(1, sink.size)
        val text = sink.single()
        assertTrue(text.startsWith("{\"schema\":\"apphear.hand_echo_shadow.v1\",\"seq\":7,\"wall_ms\":1234,"))
        assertTrue(text.endsWith("}") && !text.contains("\n"))
        for (k in listOf("\"ratio\":", "\"weaker\":\"LEFT\"", "\"roi_iou\":", "\"skeleton_iou\":", "\"mask\":31", "\"grid\":[0.3000,0.4000,0.5000,0.6000,0.7000]",
            "\"L\":{", "\"R\":{", "\"support\":", "\"pts030\":", "\"presence\":", "\"handedness\":", "\"slot_consistency\":", "\"body_wrist_support\":",
            "\"wrist_agreement\":", "\"observed\":true")) assertTrue(k, text.contains(k))
        assertFalse(text.contains("\"xy\"") || text.contains("landmark") || text.contains("refined"))
        // left slot with handedness 0.9 => consistency 1 - 0.9 = 0.1; right slot with 0.95 => 0.95
        assertTrue(text, text.contains("\"slot_consistency\":0.1000"))
        assertTrue(text, text.contains("\"slot_consistency\":0.9500"))
        // balanced braces: one object per line
        assertEquals(text.count { it == '{' }, text.count { it == '}' })
    }

    @Test fun nonFiniteHandednessIsLoggedAsMissingNotAsANumber() {
        val (s, sink) = shadow()
        s.observe(0, 1L, group(0.5f, handedness = Float.NaN), group(0.5f))
        val text = sink.single()
        assertTrue(text, text.contains("\"handedness\":null"))
        assertTrue(text, text.contains("\"slot_consistency\":null"))
        assertFalse(text.contains("NaN"))
    }

    @Test fun logVolumeIsBounded() {
        val (s, sink) = shadow(max = 5)
        repeat(50) { s.observe(it, it.toLong(), group(0.3f), group(0.6f)) }
        assertEquals(5, sink.size)
    }

    @Test fun aFailingSinkNeverEscapesIntoTheAnalyzer() {
        val s = HandEchoShadow(true, 10) { throw IllegalStateException("log failed") }
        s.observe(0, 1L, group(0.3f), group(0.6f))      // must not throw
    }

    @Test fun missingBodyWristAndRoiAreHandled() {
        val g = group(0.3f, roi = null)
        val r = requireNotNull(shadow().first.observe(0, 1L, g.copy(proposalPresent = false), group(0.6f)))
        assertEquals(0, r.wouldSuppressMask)
    }

    @Test fun shadowIsOffByDefaultInTheBuildConfigContract() {
        // The analyzer constructs the shadow from BuildConfig.HAND_ECHO_SHADOW_ENABLED (gradle -PhandEchoShadow, default false, release false).
        assertFalse(HandEchoShadow.DEFAULT_ENABLED)
    }
}
