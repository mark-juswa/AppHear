package com.example.apphear.conversation

import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class AutoReplyCountdownTest {
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

    private fun countdown(delayMs: Long, clock: FakeScheduler, ticks: MutableList<Int>, fired: MutableList<Long>) =
        AutoReplyCountdown(delayMs, clock::schedule, clock::unschedule, { ticks += it }, { fired += clock.now })

    @Test
    fun countsDownEverySecondThenFiresOnce() {
        val clock = FakeScheduler(); val ticks = mutableListOf<Int>(); val fired = mutableListOf<Long>()
        val countdown = countdown(3_000, clock, ticks, fired)
        countdown.start()
        assertTrue(countdown.running)
        clock.advance(10_000)
        assertEquals(listOf(3, 2, 1), ticks)
        assertEquals(listOf(3_000L), fired)
        assertFalse(countdown.running)
    }

    @Test
    fun fractionalDelayStillShowsWholeSecondsAndFiresOnTime() {
        val clock = FakeScheduler(); val ticks = mutableListOf<Int>(); val fired = mutableListOf<Long>()
        countdown(2_500, clock, ticks, fired).start()
        clock.advance(10_000)
        assertEquals(listOf(3, 2, 1), ticks)
        assertEquals(listOf(2_500L), fired)
    }

    @Test
    fun cancelStopsFiringAndReportsWhetherItWasRunning() {
        val clock = FakeScheduler(); val ticks = mutableListOf<Int>(); val fired = mutableListOf<Long>()
        val countdown = countdown(3_000, clock, ticks, fired)
        countdown.start()
        clock.advance(1_500)
        assertTrue(countdown.cancel())
        clock.advance(10_000)
        assertTrue(fired.isEmpty())
        assertFalse(countdown.cancel())
        assertTrue(clock.tasks.isEmpty())
    }

    @Test
    fun restartBeginsAgainFromTheFullDelay() {
        val clock = FakeScheduler(); val ticks = mutableListOf<Int>(); val fired = mutableListOf<Long>()
        val countdown = countdown(3_000, clock, ticks, fired)
        countdown.start()
        clock.advance(2_000)
        countdown.start()
        clock.advance(10_000)
        assertEquals(listOf(5_000L), fired)
    }

    @Test
    fun shippedPolicyParsesWithinBounds() {
        val json = JsonParser.parseString(String(Files.readAllBytes(
            Path.of("src/main/assets").resolve(ConversationFlowPolicy.ASSET)), Charsets.UTF_8)).asJsonObject
        val policy = ConversationFlowPolicy.parse(json["schemaVersion"].asInt, json["autoReplyDelayMs"].asLong)
        assertEquals(3_000L, policy.autoReplyDelayMs)
    }

    @Test
    fun policyRejectsWrongSchemaAndOutOfRangeDelay() {
        assertThrows(IllegalArgumentException::class.java) { ConversationFlowPolicy.parse(2, 3_000) }
        assertThrows(IllegalArgumentException::class.java) { ConversationFlowPolicy.parse(1, 500) }
        assertThrows(IllegalArgumentException::class.java) { ConversationFlowPolicy.parse(1, 20_000) }
    }
}
