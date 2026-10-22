package com.example.apphear.llm

import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Real-time but short: the hedge fires at 200 ms; "slow" calls take 1-2 s. */
class HedgedCallTest {
    private val hedge = HedgedCall(hedgeAfterMs = 200, clockMs = System::currentTimeMillis)

    private fun attempt(source: String, delayMs: Long, value: String?, calls: AtomicInteger = AtomicInteger()) =
        HedgedCall.Attempt(source) {
            calls.incrementAndGet()
            delay(delayMs)
            value
        }

    @Test
    fun fastPrimaryWinsAndBackupNeverStarts() = runBlocking {
        val backupCalls = AtomicInteger()
        val answer = hedge.run(attempt("gemini", 20, "a"), attempt("fallback", 20, "b", backupCalls))
        assertEquals("gemini", answer?.source)
        assertEquals("a", answer?.value)
        assertEquals(0, backupCalls.get())
    }

    @Test
    fun slowPrimaryLosesToBackupStartedAtTheHedge() = runBlocking {
        val answer = hedge.run(attempt("gemini", 2_000, "a"), attempt("fallback", 50, "b"))
        assertEquals("fallback", answer?.source)
        assertEquals("b", answer?.value)
        // Answered around 250 ms, long before the slow primary would have.
        assert(answer!!.latencyMs < 1_000) { "latency ${answer.latencyMs}" }
    }

    @Test
    fun primaryFailingEarlyStartsBackupAtOnce() = runBlocking {
        val answer = hedge.run(attempt("gemini", 10, null), attempt("fallback", 30, "b"))
        assertEquals("fallback", answer?.source)
        assert(answer!!.latencyMs < 200) { "latency ${answer.latencyMs}" }
    }

    @Test
    fun slowPrimaryStillWinsWhenBackupFails() = runBlocking {
        val answer = hedge.run(attempt("gemini", 600, "a"), attempt("fallback", 10, null))
        assertEquals("gemini", answer?.source)
    }

    @Test
    fun exceptionsCountAsNoAnswer() = runBlocking {
        val failing = HedgedCall.Attempt<String>("gemini") { error("network") }
        val answer = hedge.run(failing, attempt("fallback", 10, "b"))
        assertEquals("fallback", answer?.source)
    }

    @Test
    fun bothFailingGivesNull() = runBlocking {
        assertNull(hedge.run(attempt("gemini", 300, null), attempt("fallback", 10, null)))
        assertNull(hedge.run(attempt("gemini", 10, null), null))
    }

    @Test
    fun withoutBackupASlowPrimaryIsStillAwaited() = runBlocking {
        val answer = hedge.run(attempt("gemini", 400, "a"), null)
        assertEquals("gemini", answer?.source)
    }
}
