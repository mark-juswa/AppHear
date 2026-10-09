package com.example.apphear.pipeline.diagnostics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RollingEvidenceBufferTest {
    @Test
    fun rollsUntilReleaseThenFreezesAfterPostReleaseFrames() {
        val disposed = mutableListOf<Int>()
        val buffer = RollingEvidenceBuffer(5, 2, disposed::add)

        (1L..6L).forEach { buffer.observe(it, releaseObserved = it == 4L, payload = it.toInt()) }
        buffer.observe(7L, releaseObserved = false, payload = 7)

        assertTrue(buffer.frozen)
        assertEquals(listOf(2L, 3L, 4L, 5L, 6L), buffer.drain().map { it.frameId })
        assertEquals(listOf(1, 7), disposed)
    }

    @Test
    fun remainsRollingWhenS5NeverReleases() {
        val buffer = RollingEvidenceBuffer<Int>(3, 2) {}

        (1L..5L).forEach { buffer.observe(it, releaseObserved = false, payload = it.toInt()) }

        assertFalse(buffer.frozen)
        assertEquals(listOf(3L, 4L, 5L), buffer.drain().map { it.frameId })
    }

    @Test
    fun retainsCompleteSignContextWhenAttemptStartsAtRest() {
        val buffer = RollingEvidenceBuffer<String>(10, 2) {}
        val phases = listOf(
            "rest", "rest", "preparation", "onset", "sign", "sign", "sign", "release", "return", "rest",
        )

        phases.forEachIndexed { index, phase ->
            buffer.observe((index + 1).toLong(), releaseObserved = phase == "release", payload = phase)
        }

        assertTrue(buffer.frozen)
        assertEquals(phases, buffer.drain().map { it.payload })
    }
}
