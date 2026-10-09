package com.example.apphear.fingerspelling

import com.example.apphear.data.settings.RecognitionModeSettings
import org.junit.Assert.*
import org.junit.Test

class HeldLetterPolicyTest {
    private val config = HeldLetterConfig(4000.0,1000.0,4,500.0,3,1000.0,800.0,3,64)
    private fun common(t:Double, hand:Boolean=true) = CommonObservation(t,480,640,
        Array(2){FloatArray(42){100f}},Array(2){BooleanArray(21){hand}},Array(2){FloatArray(21){1f}},
        floatArrayOf(if(hand)1f else 0f,0f),booleanArrayOf(hand,false),BooleanArray(2),Array(2){FloatArray(3)},
        FloatArray(16),FloatArray(8),BooleanArray(8),false)
    private fun stable(p:HeldLetterPolicy, c:String, start:Double):Boolean {
        val e=p.epoch
        assertFalse(p.accept(e,start,c)); assertFalse(p.accept(e,start+500,c))
        return p.accept(e,start+1000,c)
    }
    @Test fun holdOnceChangeAndConfirmBoundary() {
        val p=HeldLetterPolicy(config)
        assertTrue(stable(p,"A",1000.0)); assertEquals("A",p.preview)
        assertFalse(stable(p,"A",2500.0)); assertEquals("A",p.preview)
        assertTrue(stable(p,"M",4000.0)); assertEquals("AM",p.preview)
        p.reset(keepLatch=true); assertEquals("",p.preview)
        assertFalse(stable(p,"M",6000.0)) // Use must not repeat the still-held letter.
    }
    @Test fun sustainedAbsenceAllowsSameLetterButSingleGapDoesNot() {
        val p=HeldLetterPolicy(config); assertTrue(stable(p,"L",0.0))
        p.observe(common(2000.0,false)); p.observe(common(2100.0))
        assertFalse(stable(p,"L",2200.0))
        p.observe(common(4000.0,false)); p.observe(common(4500.0,false)); p.observe(common(4900.0,false))
        assertEquals("",p.latch); assertNull(p.request())
        p.observe(common(5100.0)); assertTrue(stable(p,"L",5200.0)); assertEquals("LL",p.preview)
    }
    @Test fun flickerBlankAndStaleResultsCannotAppend() {
        val p=HeldLetterPolicy(config); val e=p.epoch
        p.accept(e,0.0,"A"); p.accept(e,500.0,"M"); p.accept(e,1000.0,"")
        assertEquals("",p.preview)
        p.reset(); assertFalse(p.accept(e,2000.0,"A"))
        assertFalse(p.accept(p.epoch,3000.0,"A")); assertFalse(p.accept(p.epoch,3000.0,"A"))
        assertFalse(p.accept(p.epoch,3500.0,"A")); assertTrue(p.accept(p.epoch,4000.0,"A"))
    }
    @Test fun emptyInputNeverRequestsInferenceAndChronologyEnforced() {
        val p=HeldLetterPolicy(config)
        repeat(40){p.observe(common(it*200.0,false)); assertNull(p.request())}
        try { p.observe(common(7800.0)); fail("duplicate timestamp") } catch(_:IllegalArgumentException) {}
    }
    @Test fun boundedGenuineWindowWithDetachedArrays() {
        val p=HeldLetterPolicy(config); var source=common(0.0)
        p.observe(source); source.xy[0][0]=999f
        repeat(9){p.observe(common((it+1)*200.0))}
        val selected=p.request()!!
        assertEquals(100f,selected.first().xy[0][0],0f)
        assertEquals((0..9).map{it*200.0},selected.map{it.timestampMs})
        assertNull(p.request())
        repeat(200){p.observe(common(2000.0+it*20.0))}
        assertTrue(p.windowCount<=64)
        val latest=p.request()!!; assertTrue(latest.last().timestampMs-latest.first().timestampMs<=4000.0)
    }
    @Test fun selectedRawFeaturesRestartTimeAndMotionState() {
        val adapter=FingerspellingFeatureAdapterV1(.001f,.5f)
        val frames=listOf(common(1000.0),common(1500.0),common(1700.0))
        val derived=frames.map{adapter.derive(it)}
        assertEquals(0f,derived[0][0],0f); assertEquals(0f,derived[0][1],0f)
        assertEquals(.5f,derived[1][0],0f); assertEquals(.2f,derived[2][0],0f)
        val fresh=FingerspellingFeatureAdapterV1(.001f,.5f)
        frames.forEachIndexed { i,c -> assertArrayEquals(derived[i],fresh.derive(c),0f) }
    }
    @Test fun minimumSpanAndUsableEvidenceAreIndependentOfTranscript() {
        val p=HeldLetterPolicy(config)
        repeat(6){p.observe(common(it*100.0))}; assertNull(p.request())
        p.observe(common(1000.0)); assertNotNull(p.request())
    }
    @Test fun currentLetterIsSeparateFromConstructedSpelling() {
        val p=HeldLetterPolicy(config)
        val first=p.epoch
        assertFalse(p.accept(first,0.0,"A"))
        assertEquals("A",p.currentLetter); assertEquals("",p.preview)
        p.accept(first,500.0,"A"); assertTrue(p.accept(first,1000.0,"A"))
        assertEquals("A",p.currentLetter); assertEquals("A",p.preview)
        val next=p.epoch
        assertFalse(p.accept(next,1500.0,"M"))
        assertEquals("M",p.currentLetter); assertEquals("A",p.preview)
        assertFalse(p.accept(first,1600.0,"Z")) // stale result must not change either display.
        assertEquals("M",p.currentLetter); assertEquals("A",p.preview)
        p.observe(common(2000.0,false))
        assertEquals("",p.currentLetter); assertEquals("A",p.preview)
        p.observe(common(2200.0))
        assertFalse(p.accept(next,2300.0,""))
        assertEquals("",p.currentLetter); assertEquals("A",p.preview)
        p.reset(); assertEquals("",p.currentLetter); assertEquals("",p.preview)
    }
    @Test fun spellingContinuesBeyondThreeAndObservationWindowSize() {
        val p=HeldLetterPolicy(config)
        val text="ABCDEFGHIJKLMNOPQRSTUVWXYZ".repeat(4)
        for ((index,c) in text.withIndex()) {
            assertTrue(stable(p,c.toString(),index*2000.0))
            assertEquals(text.substring(0,index+1),p.preview)
        }
        assertEquals(104,p.preview.length)
        assertEquals("Z",p.currentLetter)
    }
    @Test fun acceptanceEvidenceExplainsRejectionsWithoutChangingTheDraft() {
        val p=HeldLetterPolicy(config)
        val e=p.epoch
        assertFalse(p.accept(e,0.0,"Y"))
        assertEquals(HeldLetterAcceptanceReason.NEED_MORE_MATCHING_DECODES,p.lastAcceptanceReason)
        assertEquals(1,p.acceptanceState(0.0).candidateCount)
        assertFalse(p.accept(e,200.0,"Y"))
        assertFalse(p.accept(e,400.0,"Y"))
        assertEquals(HeldLetterAcceptanceReason.NEED_LONGER_STABLE_SPAN,p.lastAcceptanceReason)
        assertEquals("",p.preview)
        val before=p.acceptanceState(1000.0)
        repeat(3){assertEquals(before,p.acceptanceState(1000.0))}
        assertTrue(p.accept(e,1000.0,"Y"))
        assertEquals(HeldLetterAcceptanceReason.APPENDED,p.lastAcceptanceReason)
        assertFalse(p.accept(e,1500.0,"A"))
        assertEquals(HeldLetterAcceptanceReason.STALE_EPOCH,p.lastAcceptanceReason)
        val next=p.epoch
        assertFalse(p.accept(next,1600.0,"Y"))
        assertEquals(HeldLetterAcceptanceReason.SAME_AS_LATCH,p.lastAcceptanceReason)
        assertFalse(p.accept(next,1600.0,"A"))
        assertEquals(HeldLetterAcceptanceReason.OUT_OF_ORDER_RESULT,p.lastAcceptanceReason)
        assertFalse(p.accept(next,1700.0,""))
        assertEquals(HeldLetterAcceptanceReason.EMPTY_DECODE,p.lastAcceptanceReason)
        p.observe(common(1800.0,false))
        assertFalse(p.accept(next,1800.0,"A"))
        assertEquals(HeldLetterAcceptanceReason.HAND_CURRENTLY_MISSING,p.lastAcceptanceReason)
        assertTrue(p.acceptanceState(1800.0).waitingForHand)
        assertEquals("Y",p.preview)
    }

    @Test fun settingsDefaultAndDisabledFallback() {
        assertEquals(RecognitionMode.WORD,RecognitionModeSettings.resolve(null,true))
        assertEquals(RecognitionMode.WORD,RecognitionModeSettings.resolve("invalid",true))
        assertEquals(RecognitionMode.WORD,RecognitionModeSettings.resolve("FINGERSPELL",false))
        assertEquals(RecognitionMode.FINGERSPELL,RecognitionModeSettings.resolve("FINGERSPELL",true))
    }
}
