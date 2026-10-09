package com.example.apphear.fingerspelling

import org.junit.Assert.*
import org.junit.Test

class FingerspellSingleLetterTest {
    private fun peaked(vararg ids: Int) = Array(ids.size) { t -> FloatArray(28) { if(it==ids[t]) 30f else -30f } }
    @Test fun everyLetterBlankSpaceAndSingletonConstraint() {
        for(c in 0..25) assertEquals(('A'.code+c).toChar().toString(),
            FingerspellSingleLetterDecoder.decode(peaked(27,c,c,27)).text)
        assertEquals("",FingerspellSingleLetterDecoder.decode(peaked(27,27)).text)
        assertEquals("",FingerspellSingleLetterDecoder.decode(peaked(26,26)).text)
        assertEquals("",FingerspellSingleLetterDecoder.decode(emptyArray()).text)
        assertEquals("L",FingerspellSingleLetterDecoder.decode(peaked(11,27,11)).text)
        assertEquals("LL",FingerspellCtcDecoder.decode(peaked(11,27,11),.5f))
        val one=FingerspellSingleLetterDecoder.decode(peaked(11,11,11))
        val two=FingerspellSingleLetterDecoder.decode(peaked(11,27,11))
        assertTrue(one.letterLogMasses[11]>two.letterLogMasses[11]+40)
    }
    @Test fun penaltyOnceAndStableTie() {
        val row=FloatArray(28) { -30f }; row[0]=0f; row[1]=0f; row[27]=.5f
        val copy=row.copyOf(); val result=FingerspellSingleLetterDecoder.decode(arrayOf(row))
        assertEquals("A",result.bestLetter); assertEquals("",result.text)
        assertArrayEquals(copy,row,0f)
        try { FingerspellSingleLetterDecoder.decode(arrayOf(row),0f); fail("Frozen penalty") }
        catch(_:IllegalArgumentException) {}
    }
    @Test fun confirmedLettersAppendWithoutSpacesAndPreserveRepeats() {
        val buffer=FingerspellBuffer()
        for(c in "BELLA") { buffer.show(c.toString()); buffer.confirmLetter() }
        assertEquals("BELLA",buffer.confirmed)
        buffer.show("Z"); buffer.retry(); assertEquals("BELLA",buffer.confirmed)
        buffer.show("AMY")
        try { buffer.confirmLetter(); fail("Single letter required") } catch(_:IllegalArgumentException) {}
        buffer.clear(); assertEquals("",buffer.confirmed)
        buffer.show("BELLA"); assertEquals("BELLA",buffer.confirm()) // old whole-sequence rollback
    }
    private fun common(observed: Boolean, valid: Boolean) = CommonObservation(0.0,480,640,
        Array(2){FloatArray(42)},Array(2){BooleanArray(21){valid}},Array(2){FloatArray(21)},
        FloatArray(2),booleanArrayOf(observed,false),BooleanArray(2),Array(2){FloatArray(3)},
        FloatArray(8),FloatArray(4),BooleanArray(4),false)
    @Test fun exactNoInputGuardDoesNotRejectPartialEvidence() {
        val evidence=FingerspellInputEvidence()
        evidence.record(common(false,false))
        assertEquals("NO_ACCEPTED_HAND_OBSERVATIONS",evidence.refusal())
        evidence.record(common(true,false))
        assertEquals("NO_VALID_HAND_GEOMETRY",evidence.refusal())
        evidence.record(common(true,true))
        repeat(48) { evidence.record(common(false,false)) }
        assertNull(evidence.refusal()); assertEquals(51,evidence.observations); assertEquals(1,evidence.usable)
        evidence.reset(); assertEquals(0,evidence.usable)
    }
}
