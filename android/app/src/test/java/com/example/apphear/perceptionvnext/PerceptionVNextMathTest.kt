package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class PerceptionVNextMathTest {
    private val transform = PerceptionVNextMath.Transform(360, 480, 180f, 240f, 450f, 600f)

    @Test
    fun rejectsHandWithoutFiveCurrentFrameSupportPoints() {
        val decoded = PerceptionVNextMath.Decoded(
            FloatArray(PerceptionVNextMath.POINTS * 2),
            FloatArray(PerceptionVNextMath.POINTS),
        )
        for (local in 0 until 4) {
            val point = PerceptionVNextMath.LEFT_HAND_START + local
            decoded.xy[point * 2] = 100f + local
            decoded.xy[point * 2 + 1] = 200f + local
            decoded.support[point] = 1f
        }
        assertNull(
            PerceptionVNextMath.handRoi(
                decoded,
                PerceptionVNextMath.LEFT_HAND_START,
                transform,
            ),
        )
    }

    @Test
    fun buildsBoundedRobustCurrentFrameRoi() {
        val decoded = PerceptionVNextMath.Decoded(
            FloatArray(PerceptionVNextMath.POINTS * 2),
            FloatArray(PerceptionVNextMath.POINTS),
        )
        for (local in 0 until 21) {
            val point = PerceptionVNextMath.RIGHT_HAND_START + local
            decoded.xy[point * 2] = 120f + local * 2f
            decoded.xy[point * 2 + 1] = 180f + local * 2f
            decoded.support[point] = 1f
        }
        val roi = PerceptionVNextMath.handRoi(
            decoded,
            PerceptionVNextMath.RIGHT_HAND_START,
            transform,
        )
        assertNotNull(roi)
        val value = requireNotNull(roi)
        assertEquals(140f, value.centerX, 1e-5f)
        assertEquals(200f, value.centerY, 1e-5f)
        assertEquals(64.8f, value.side, 1e-4f)
        assertEquals(21, value.supportCount)
    }

    @Test
    fun bodyPointValidityMakesExistingAvailabilityEvidenceExplicit() {
        assertEquals(true, PerceptionVNextMath.bodyPointValid(10f, 20f, 0.30f, transform))
        assertEquals(false, PerceptionVNextMath.bodyPointValid(10f, 20f, 0.299f, transform))
        assertEquals(false, PerceptionVNextMath.bodyPointValid(-1f, 20f, 0.90f, transform))
        assertEquals(false, PerceptionVNextMath.bodyPointValid(10f, Float.NaN, 0.90f, transform))
    }
}
