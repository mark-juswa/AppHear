package com.example.apphear.conversation.flow2

import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class AutoSayTest {
    @Test fun `a word edit or lifecycle pause cannot leave a delayed say callback armed`() {
        autoSay.update("ME WANT HOT WATER", canSay = true, ready = false)
        clock.advance(9_000)
        autoSay.update("ME WANT HOT WATER", canSay = false, ready = false)
        autoSay.update("ME WANT WATER", canSay = true, ready = false)
        clock.advance(1_000)
        autoSay.update("ME WANT WATER", canSay = true, ready = true)
        clock.advance(4_499)
        assertEquals(0, fired)
        autoSay.cancel()
        clock.advance(20_000)
        assertEquals(0, fired)
    }

    /** A manual clock standing in for the main-thread Handler. */
    private class FakeScheduler {
        var now = 0L
        val tasks = mutableListOf<Pair<Long, Runnable>>()
        fun schedule(delayMs: Long, task: Runnable) { tasks += (now + delayMs) to task }
        fun unschedule(task: Runnable) { tasks.removeAll { it.second === task } }
        fun advance(ms: Long) {
            val end = now + ms
            while (true) {
                val next = tasks.filter { it.first <= end }.minByOrNull { it.first } ?: break
                tasks.remove(next)
                now = next.first
                next.second.run()
            }
            now = end
        }
    }

    private val clock = FakeScheduler()
    private val ticks = mutableListOf<Int?>()
    private var fired = 0
    private val autoSay = AutoSay(AutoSayPolicy(stillnessMs = 2_500, countdownMs = 3_000, raisedHandMaxY = 0.8f),
        clock::schedule, clock::unschedule, { ticks += it }, { fired++ })

    @Test fun `still signer gets a 3-2-1 countdown and the message is said once`() {
        autoSay.update("HELLO", canSay = true)
        clock.advance(2_499)
        assertTrue(ticks.isEmpty())
        clock.advance(1)
        assertEquals(listOf<Int?>(3), ticks)
        assertTrue(autoSay.counting)
        clock.advance(3_000)
        assertEquals(listOf<Int?>(3, 2, 1, null), ticks)
        assertEquals(1, fired)

        // The same words are never said again automatically, however long the signer waits.
        autoSay.update("HELLO", canSay = true)
        clock.advance(20_000)
        assertEquals(1, fired)
    }

    @Test fun `signing again during the wait or the countdown starts the wait over`() {
        autoSay.update("HELLO", canSay = true)
        clock.advance(2_000)
        autoSay.activity()
        clock.advance(2_000)
        assertTrue(ticks.isEmpty())

        clock.advance(500)
        assertEquals(listOf<Int?>(3), ticks)
        autoSay.activity()
        assertEquals(listOf<Int?>(3, null), ticks)
        assertFalse(autoSay.counting)

        clock.advance(5_500)
        assertEquals(1, fired)
    }

    @Test fun `raised hands keep the signer's turn open across long gaps between words`() {
        autoSay.update("ME", canSay = true)
        // Hands stay up (one activity per camera frame, ~4 per second) for 10 seconds without a new word.
        repeat(40) { clock.advance(250); autoSay.activity() }
        assertTrue(ticks.isEmpty())
        assertEquals(0, fired)
        // Hands down: the wait and the countdown run, then the message is said.
        clock.advance(5_500)
        assertEquals(1, fired)
    }

    @Test fun `the countdown waits for the sentence that is still being built`() {
        autoSay.update("ME WANT WATER", canSay = true, ready = false)
        clock.advance(10_000)
        assertTrue(ticks.isEmpty())
        // The sentence arrives after the signer has long been still: the countdown starts at once.
        autoSay.update("ME WANT WATER", canSay = true, ready = true)
        assertEquals(listOf<Int?>(3), ticks)
        clock.advance(3_000)
        assertEquals(1, fired)
    }

    @Test fun `a new build during the countdown pauses it until the sentence is ready`() {
        autoSay.update("HELLO HOME", canSay = true)
        clock.advance(3_500)
        assertTrue(autoSay.counting)
        autoSay.update("HELLO HOME", canSay = true, ready = false)
        assertFalse(autoSay.counting)
        clock.advance(10_000)
        assertEquals(0, fired)
        autoSay.update("HELLO HOME", canSay = true, ready = true)
        clock.advance(3_000)
        assertEquals(1, fired)
    }

    @Test fun `new words during the countdown restart the wait and say the longer message`() {
        autoSay.update("ME", canSay = true)
        clock.advance(3_000)
        assertTrue(autoSay.counting)
        autoSay.update("ME WANT WATER", canSay = true)
        assertFalse(autoSay.counting)
        clock.advance(5_500)
        assertEquals(1, fired)
    }

    @Test fun `WAIT holds this message until its words change`() {
        autoSay.update("HELLO", canSay = true)
        clock.advance(3_000)
        autoSay.hold()
        assertEquals(listOf<Int?>(3, null), ticks)
        clock.advance(20_000)
        assertEquals(0, fired)

        autoSay.update("HELLO FRIEND", canSay = true)
        clock.advance(5_500)
        assertEquals(1, fired)
    }

    @Test fun `a message already said by hand is not said again`() {
        autoSay.update("HELLO", canSay = true)
        autoSay.hold()
        clock.advance(20_000)
        assertEquals(0, fired)
    }

    @Test fun `nothing happens without a message or when it is not the signer's turn`() {
        autoSay.update(null, canSay = true)
        autoSay.activity()
        clock.advance(10_000)
        autoSay.update("HELLO", canSay = false)
        clock.advance(10_000)
        assertEquals(0, fired)
        assertTrue(ticks.isEmpty())
    }

    @Test fun `losing the turn cancels a running countdown`() {
        autoSay.update("HELLO", canSay = true)
        clock.advance(3_000)
        autoSay.update("HELLO", canSay = false)
        assertEquals(listOf<Int?>(3, null), ticks)
        clock.advance(10_000)
        assertEquals(0, fired)

        // Back on the signer's turn with the same, never-said words: the wait starts again.
        autoSay.update("HELLO", canSay = true)
        clock.advance(5_500)
        assertEquals(1, fired)
    }

    @Test fun `cancel stops without holding the words`() {
        autoSay.update("HELLO", canSay = true)
        clock.advance(3_000)
        autoSay.cancel()
        clock.advance(10_000)
        assertEquals(0, fired)
        autoSay.update("HELLO", canSay = true)
        clock.advance(5_500)
        assertEquals(1, fired)
    }

    @Test fun `policy rejects out-of-range timings and other schema versions`() {
        assertThrows(IllegalArgumentException::class.java) { AutoSayPolicy(500, 3_000, 0.8f) }
        assertThrows(IllegalArgumentException::class.java) { AutoSayPolicy(2_500, 9_000, 0.8f) }
        assertThrows(IllegalArgumentException::class.java) { AutoSayPolicy(2_500, 3_000, 0.1f) }
        assertThrows(IllegalArgumentException::class.java) { AutoSayPolicy.parse(1, 2_500, 3_000, 0.8) }
    }

    @Test fun `shipped policy asset parses`() {
        val json = JsonParser.parseString(
            String(Files.readAllBytes(Path.of("src/main/assets/${AutoSayPolicy.ASSET}")))).asJsonObject
        val policy = AutoSayPolicy.parse(json["schemaVersion"].asInt, json["stillnessMs"].asLong, json["countdownMs"].asLong,
            json["raisedHandMaxY"].asDouble)
        assertEquals(AutoSayPolicy(3_500, 3_000, 0.8f), policy)
    }
}
