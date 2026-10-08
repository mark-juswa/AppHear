package com.example.apphear.fingerspelling

import org.junit.Assert.*
import org.junit.Test
import java.io.DataInputStream
import kotlin.math.abs

class FingerspellBeamDecoderTest {
    @Test fun allFrozenPythonLogitsMatchExactly() {
        val stream = checkNotNull(javaClass.classLoader!!.getResourceAsStream("fingerspell_beam/fixtures.bin"))
        DataInputStream(stream.buffered()).use { input ->
            assertEquals("apphear.fingerspelling.beam_fixture.v1", input.readUTF())
            assertEquals(10, input.readInt()); val penalty = input.readFloat(); assertEquals(.5f, penalty, 0f)
            val count = input.readInt(); assertEquals(523, count)
            var differences = 0; var maxError = 0.0
            repeat(count) {
                val name = input.readUTF(); input.readUTF()
                val logits = Array(input.readInt()) { FloatArray(28) { input.readFloat() } }
                val original = logits.map { it.copyOf() }
                val expectedBeam = input.readUTF(); val expectedGreedy = input.readUTF(); val expectedScore = input.readDouble()
                val actual = FingerspellPrefixBeamDecoder.decode(logits, penalty)
                assertEquals(name, expectedBeam, actual.text)
                assertEquals(name, expectedGreedy, FingerspellCtcDecoder.decode(logits, penalty))
                maxError = maxOf(maxError, abs(expectedScore - actual.logCtcMassPruned))
                assertEquals(name, expectedScore, actual.logCtcMassPruned, 1e-8)
                if (expectedBeam != expectedGreedy) differences++
                logits.indices.forEach { assertArrayEquals(original[it], logits[it], 0f) }
            }
            assertEquals(-1, input.read()); assertEquals(416, differences)
            println("FINGERSPELL_BEAM_JVM_PARITY_PASS fixtures=$count changed=$differences max_score_error=$maxError")
        }
    }

    @Test fun rejectsChangedPenaltyAndNonfiniteLogits() {
        assertThrows(IllegalArgumentException::class.java) {
            FingerspellPrefixBeamDecoder.decode(arrayOf(FloatArray(28)), 1f)
        }
        assertThrows(IllegalArgumentException::class.java) {
            FingerspellPrefixBeamDecoder.decode(arrayOf(FloatArray(28) { Float.NaN }), .5f)
        }
    }
}
