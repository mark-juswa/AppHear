package com.example.apphear.p8b

import com.example.apphear.p7d.P7dMath
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import kotlin.math.abs

class P8bMathTest {
    @Test
    fun heatmapOnlyDecoderMatchesFrozenP7cDecoder() {
        val transform = P7dMath.Transform(720, 1280)
        val heat = FloatArray(P7dMath.GRID * P7dMath.GRID * P7dMath.POINTS) { index ->
            val cell = index / P7dMath.POINTS
            val point = index % P7dMath.POINTS
            val x = cell % P7dMath.GRID
            val y = cell / P7dMath.GRID
            val targetX = 28 + point % 31
            val targetY = 4 + point % 87
            -(abs(x - targetX) + abs(y - targetY)).toFloat()
        }
        val expected = P7dMath.decode(heat, floatArrayOf(0f, 0f), transform)
        val expectedSource = P7dMath.restore(expected, transform)
        val actual = P8bDecoder(transform)

        actual.decode(heat)

        assertArrayEquals(expected.inputXY, actual.inputXY, 1e-6f)
        assertArrayEquals(expectedSource, actual.sourceXY, 1e-5f)
    }

    @Test
    fun summaryUsesInterpolatedP95() {
        val summary = P8bStats.summarize(doubleArrayOf(4.0, 1.0, 3.0, 2.0))
        assertEquals(4, summary.count)
        assertEquals(2.5, summary.mean, 0.0)
        assertEquals(2.5, summary.p50, 0.0)
        assertEquals(3.85, summary.p95, 1e-12)
        assertEquals(4.0, summary.maximum, 0.0)
    }
}
