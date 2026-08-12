package com.example.apphear

import com.example.apphear.pipeline.recognition.meanPosteriors
import com.example.apphear.pipeline.recognition.posteriorTop1
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class Phase1ShadowMathTest {
    @Test
    fun ensembleUsesArithmeticMeanWithoutChangingInputs() {
        val first = floatArrayOf(0.8f, 0.2f)
        val second = floatArrayOf(0.4f, 0.6f)

        val result = meanPosteriors(listOf(first, second))

        assertArrayEquals(floatArrayOf(0.6f, 0.4f), result, 1e-6f)
        assertArrayEquals(floatArrayOf(0.8f, 0.2f), first, 0f)
    }

    @Test
    fun top1ReturnsHighestProbabilityClass() {
        assertEquals(2, posteriorTop1(floatArrayOf(0.1f, 0.2f, 0.7f)))
    }
}
