package com.example.apphear

import com.example.apphear.pipeline.recognition.SentenceBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** S8 passthrough+dedup accumulator. Pure JVM. */
class SentenceBuilderTest {
    @Test fun removalRejectsAChangedPhraseAndDoesNotDeleteTheSameIndexTwice() {
        val s = SentenceBuilder()
        listOf("ME", "WANT", "HOT", "WATER").forEach { s.add(it) }
        val reviewed = s.text()
        s.add("NOW")
        assertFalse(s.removeAt(2, reviewed))
        assertEquals("ME WANT HOT WATER NOW", s.text())
        val current = s.text()
        assertTrue(s.removeAt(2, current))
        assertFalse(s.removeAt(2, current))
        assertEquals("ME WANT WATER NOW", s.text())
        s.clear()
        s.add("HELLO")
        assertTrue(s.removeAt(0, "HELLO"))
        assertTrue(s.isEmpty())
    }

    @Test fun removeAtDropsOneWordAndRefusesBadIndexes() {
        val s = SentenceBuilder()
        listOf("ME", "WANT", "HOT", "WATER").forEach { s.add(it) }
        org.junit.Assert.assertTrue(s.removeAt(2))
        org.junit.Assert.assertEquals("ME WANT WATER", s.text())
        org.junit.Assert.assertFalse(s.removeAt(3))
        org.junit.Assert.assertFalse(s.removeAt(-1))
        org.junit.Assert.assertEquals("ME WANT WATER", s.text())
    }


    @Test
    fun appendsInOrderJoinedBySpaces() {
        val s = SentenceBuilder()
        s.add("CUT"); s.add("DOG"); s.add("MILK")
        assertEquals("CUT DOG MILK", s.text())
    }

    @Test
    fun collapsesConsecutiveDuplicatesButKeepsNonConsecutive() {
        val s = SentenceBuilder()
        assertTrue(s.add("CUT"))
        assertFalse("consecutive repeat ignored", s.add("CUT"))
        assertTrue(s.add("DOG"))
        assertTrue("same gloss later (non-consecutive) is kept", s.add("CUT"))
        assertEquals("CUT DOG CUT", s.text())
    }

    @Test
    fun capsLengthDroppingOldest() {
        val s = SentenceBuilder(maxGlosses = 3)
        s.add("A"); s.add("B"); s.add("C"); s.add("D")
        assertEquals("B C D", s.text())
    }

    @Test
    fun clearEmptiesThePhrase() {
        val s = SentenceBuilder()
        s.add("CUT"); s.add("DOG")
        assertFalse(s.isEmpty())
        s.clear()
        assertTrue(s.isEmpty())
        assertEquals("", s.text())
    }
}
