package com.example.apphear.perceptionvnext

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class PhoneRecognitionRawSequenceTest {
    @Test
    fun genuinePhoneObservationsKeepIdentityChronologyAndValidity() {
        val first = observation(7, 1000.0, true)
        val second = observation(8, 1133.308, false)
        val raw = phoneRecognitionRawSequence(listOf(first, second))

        assertEquals(RecognitionV2.RAW_SCHEMA, raw.schema)
        assertEquals("UPRIGHT_UNMIRRORED_SOURCE_RGB", raw.imageSemantics)
        assertArrayEquals(intArrayOf(7, 8), raw.frameIndex)
        assertArrayEquals(doubleArrayOf(1000.0, 1133.308), raw.timestampMs, 0.0)
        assertArrayEquals(intArrayOf(360, 480, 360, 480), raw.sourceSize)
        assertEquals(0.75f, raw.handXy[0])
        assertEquals(0.75f, raw.handXy[84])
        assertArrayEquals(booleanArrayOf(true, false, false, false), raw.handObserved)
        assertArrayEquals(booleanArrayOf(true, false), raw.bodyAvailable)
        assertEquals(true, raw.handJointValid[0])
        assertEquals(false, raw.handJointValid[42])
    }

    private fun observation(index: Int, timestamp: Double, observed: Boolean) = PhoneRawObservation(
        sourceIndex = index,
        timestampMs = timestamp,
        sourceWidth = 360,
        sourceHeight = 480,
        handXy = arrayOf(FloatArray(42) { 0.75f }, FloatArray(42)),
        handJointValid = arrayOf(BooleanArray(21) { observed }, BooleanArray(21)),
        handProposalSupport = arrayOf(FloatArray(21) { 0.8f }, FloatArray(21)),
        handPresence = floatArrayOf(if (observed) 0.95f else Float.NaN, Float.NaN),
        handObserved = booleanArrayOf(observed, false),
        handProposalPresent = booleanArrayOf(true, false),
        handRoiCenterSide = arrayOf(floatArrayOf(10f, 20f, 30f), FloatArray(3)),
        bodyXy = FloatArray(16),
        bodySupport = FloatArray(8),
        bodyValid = BooleanArray(8),
        bodyAvailable = observed,
    )
}
