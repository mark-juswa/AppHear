package com.example.apphear.pipeline.recognition

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class RuD1WindowSourcesTest {
    @Test
    fun sourceMapPreservesPreOnsetOrderAndPadding() {
        val sources = RuD1WindowSources(5)
        sources.set(0, 40)
        sources.set(1, 41)
        sources.set(2, 44)

        assertArrayEquals(longArrayOf(40, 41, 44, -1, -1), sources.copy())
    }

    @Test
    fun clearRestoresPaddingSentinel() {
        val sources = RuD1WindowSources(3)
        sources.set(0, 12)
        sources.clear()

        assertArrayEquals(longArrayOf(-1, -1, -1), sources.copy())
        assertEquals(-1L, RuD1WindowSources.PAD_FRAME)
    }
}
