package com.example.apphear.fingerspelling

import org.junit.Assert.*
import org.junit.Test

class FingerspellSessionTest {
    @Test fun geometryOnlySessionPreservesRepeatedCharactersAndRefusesVisualWidth() {
        val session=FingerspellSession(10,2.0,405)
        session.start(); session.consume(0.0,FloatArray(405))
        try { session.consume(100.0,FloatArray(1559)); fail("Wrong package width") }
        catch(_:IllegalArgumentException) {}
        val (token,frames)=session.finish()
        assertEquals(405,frames.single().size)
        assertTrue(session.complete(token,"BELLA"))
        assertEquals("BELLA",session.buffer.confirm())
    }
    @Test fun blankSeparatesRepeatedLettersAndConfirmationIsExplicit() {
        val ids=intArrayOf(12,12,27,12,26,4,27,4)
        val logits=Array(ids.size){t -> FloatArray(28){c -> if(c==ids[t]) 3f else -3f}}
        assertEquals("MM EE",FingerspellCtcDecoder.decode(logits,.5f))
        val session=FingerspellSession(10,2.0)
        session.start(); session.consume(0.0,FloatArray(1559))
        val (token, _)=session.finish()
        assertTrue(session.complete(token,"BELLA"))
        assertEquals("", session.buffer.confirmed)
        assertEquals("BELLA", session.buffer.confirm())
    }
    @Test fun ownerResetsWordWithoutChangingSentenceAndRejectsStaleDecode() {
        var resets=0; val owner=RecognitionModeController{resets++}
        owner.select(RecognitionMode.FINGERSPELL); owner.select(RecognitionMode.FINGERSPELL)
        assertEquals(1,resets); assertEquals(RecognitionMode.FINGERSPELL,owner.mode)
        val session=FingerspellSession(10,2.0); session.start(); session.consume(0.0,FloatArray(1559))
        val (token,_)=session.finish(); session.cancel()
        assertFalse(session.complete(token,"STALE"))
        owner.select(RecognitionMode.WORD); assertEquals(2,resets)
    }
    @Test fun resourceCapDoesNotSilentlyDecodeTruncatedAttempt() {
        val session=FingerspellSession(1,2.0); session.start(); session.consume(0.0,FloatArray(1559))
        try { session.consume(100.0,FloatArray(1559)); fail("Must refuse limit") } catch(_:IllegalStateException) {}
        assertEquals(FingerspellPhase.ERROR,session.phase); assertEquals(0,session.count)
    }
}
