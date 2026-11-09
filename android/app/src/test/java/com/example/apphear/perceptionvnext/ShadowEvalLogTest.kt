package com.example.apphear.perceptionvnext

import com.example.apphear.pipeline.recognition.SentenceBuilder
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch

/**
 * Phase 1.1 shadow log: observe-only, non-blocking, bounded, private, failure-isolated. These tests prove
 * those PROPERTIES. They say nothing about recognition accuracy.
 */
class ShadowEvalLogTest {
    private fun record(
        id: Int = 1,
        outcome: CommitOutcome = CommitOutcome.ACCEPT,
        committed: Boolean = true,
        p1: Float = 0.97f,
        lag: Double? = 120.0,
    ) = ShadowEventRecord(
        wallClockUtcMs = 1_700_000_000_000L + id, configuration = "STABLE", s2Package = "S2_R2_CANDIDATE",
        fallback = false, gateEnabled = true, floor = 0.55, handRule = true, eventId = id,
        top5Glosses = listOf("HELLO", "HOME", "THINK", "TABLE", "ON"), top1Probability = p1, top2Probability = 0.01f,
        handSpanFraction = 1.0, spanObservations = 8, windowObservations = 14, spanStartAgoMs = 1200.0,
        spanEndAgoMs = 400.0, s2InvocationMs = 4.2, recognitionInvocationMs = 3.1, captureToDecisionMs = lag,
        gatedOutcome = outcome, gatedReason = outcome.name, actuallyCommitted = committed,
    )

    private class ListSink : ShadowSink {
        val lines = CopyOnWriteArrayList<String>()
        @Volatile var closed = false
        override fun append(line: String) { lines.add(line) }
        override fun close() { closed = true }
    }

    private class FlakySink(@Volatile var failing: Boolean) : ShadowSink {
        val lines = CopyOnWriteArrayList<String>()
        override fun append(line: String) { if (failing) throw IOException("disk full") else lines.add(line) }
        override fun close() = Unit
    }

    private class StalledSink(private val gate: CountDownLatch) : ShadowSink {
        @Volatile var appended = 0
        override fun append(line: String) { gate.await(); appended++ }
        override fun close() = Unit
    }

    private fun log(sink: ShadowSink, capacity: Int = 64, failures: Int = 5, label: String = "S03_dim_far") =
        ShadowEvalLog(sink, sessionId = "0123456789abcdef", runLabelProvider = { label },
            sessionMeta = mapOf("configuration" to "STABLE"), capacity = capacity, maxConsecutiveFailures = failures)

    private fun parse(line: String) = JsonParser.parseString(line).asJsonObject

    // ---- content and privacy ----------------------------------------------------------------------

    @Test fun eventLinesAreValidJsonWithExactlyTheAllowedKeysAndBothDecisions() {
        val sink = ListSink()
        val l = log(sink)
        l.record(record(1, CommitOutcome.ACCEPT, committed = true))
        l.record(record(2, CommitOutcome.UNCERTAIN, committed = false, p1 = 0.31f))
        assertTrue(l.flush(2_000)); l.close()
        val events = sink.lines.map(::parse).filter { it["type"].asString == "event" }
        assertEquals(2, events.size)
        for (e in events) {
            assertEquals("every event line may only contain allow-listed keys",
                emptySet<String>(), e.keySet() - ShadowEvalLog.ALLOWED_EVENT_KEYS)
            assertEquals("COMMIT", e["legacy"].asString) // A: original behaviour commits every usable top-1
            assertEquals("S03_dim_far", e["run"].asString)
        }
        assertEquals("ACCEPT", events[0]["gated"].asString)
        assertEquals("COMMIT", events[0]["actual"].asString)
        assertEquals("UNCERTAIN", events[1]["gated"].asString)
        assertEquals("WITHHELD", events[1]["actual"].asString)
        assertEquals("HELLO", events[0]["top1"].asString)
        assertEquals(5, events[0]["top5"].asJsonArray.size())
        assertEquals(0.96, events[0]["margin"].asDouble, 1e-3)
    }

    @Test fun theEventLineMatchesTheSharedGoldenFixtureThatThePythonReportParses() {
        // Contract with eval/shadow_validation/shadow_report.py (tests/test_shadow_report.py reads the same file).
        val golden = checkNotNull(javaClass.classLoader?.getResourceAsStream("shadow_eval/golden_event_line.json"))
            .bufferedReader().readText().trim()
        val sink = ListSink()
        val l = ShadowEvalLog(sink, "0123456789abcdef", { "E01_dim_far_slow_r1" }, mapOf("configuration" to "STABLE"))
        l.record(ShadowEventRecord(
            wallClockUtcMs = 1_700_000_011_300L, configuration = "STABLE", s2Package = "S2_R2_CANDIDATE",
            fallback = false, gateEnabled = true, floor = 0.55, handRule = true, eventId = 1,
            top5Glosses = listOf("HELLO", "HOME", "THINK", "TABLE", "ON"), top1Probability = 0.97f,
            top2Probability = 0.01f, handSpanFraction = 1.0, spanObservations = 8, windowObservations = 14,
            spanStartAgoMs = 1100.0, spanEndAgoMs = 500.0, s2InvocationMs = 4.2, recognitionInvocationMs = 3.1,
            captureToDecisionMs = 120.0, gatedOutcome = CommitOutcome.ACCEPT, gatedReason = "ACCEPT",
            actuallyCommitted = true,
        ))
        assertTrue(l.flush(2_000)); l.close()
        assertEquals(golden, sink.lines.first { parse(it)["type"].asString == "event" })
    }

    @Test fun noImageLandmarkTensorOrIdentifierFieldCanBeEmitted() {
        val forbidden = listOf("image", "frame", "pixel", "landmark", "tensor", "video", "xy", "user", "device_id", "imei", "email", "name")
        for (key in ShadowEvalLog.ALLOWED_EVENT_KEYS) {
            for (f in forbidden) assertFalse("allowed key '$key' looks sensitive ($f)", key == f || key.contains(f))
        }
    }

    @Test fun runLabelCanNeverCarryFreeTextOrAPath() {
        assertEquals("S03_dim-far_2", ShadowEvalLog.sanitizeRunLabel("  S03_dim-far_2 \n"))
        assertEquals("etcpasswd", ShadowEvalLog.sanitizeRunLabel("../../etc/passwd"))
        assertEquals("", ShadowEvalLog.sanitizeRunLabel("éè \"{}"))
        assertEquals(64, ShadowEvalLog.sanitizeRunLabel("a".repeat(500)).length)
    }

    @Test fun nonFiniteNumbersSerializeAsNullAndStayValidJson() {
        val sink = ListSink()
        val l = log(sink)
        l.record(record().copy(spanStartAgoMs = Double.NaN, spanEndAgoMs = Double.POSITIVE_INFINITY, captureToDecisionMs = null, floor = null))
        assertTrue(l.flush(2_000)); l.close()
        val e = sink.lines.map(::parse).first { it["type"].asString == "event" }
        assertTrue(e["start_ago_ms"].isJsonNull)
        assertTrue(e["end_ago_ms"].isJsonNull)
        assertTrue(e["lag_ms"].isJsonNull)
        assertTrue(e["floor"].isJsonNull)
    }

    @Test fun sessionMarkersCarryMetadataAndAFinalSummaryWithDropCounters() {
        val sink = ListSink()
        val l = log(sink)
        l.record(record())
        l.generationReset()
        l.record(record(1))
        assertTrue(l.flush(2_000)); l.close()
        val types = sink.lines.map { parse(it)["type"].asString }
        assertEquals(listOf("session_start", "event", "generation_reset", "event", "session_end"), types)
        val start = parse(sink.lines.first())
        assertEquals("STABLE", start["meta_configuration"].asString)
        val gens = sink.lines.map(::parse).filter { it["type"].asString == "event" }.map { it["gen"].asInt }
        assertEquals(listOf(0, 1), gens)
        val end = parse(sink.lines.last())
        assertEquals(0L, end["dropped"].asLong)
    }

    @Test fun sessionIdsAreRandomPerSessionAndCarryNoIdentifier() {
        // The production factory uses 8 SecureRandom bytes; the format must be fixed-length lowercase hex.
        val ids = (1..50).map { java.security.SecureRandom().let { r -> ByteArray(8).also(r::nextBytes) }.joinToString("") { "%02x".format(it) } }
        assertEquals(50, ids.toSet().size)
        assertTrue(ids.all { it.matches(Regex("[0-9a-f]{16}")) })
    }

    // ---- never blocks, bounded -------------------------------------------------------------------------------

    @Test fun recordNeverBlocksWhenTheSinkIsStalledAndTheQueueStaysBounded() {
        val gate = CountDownLatch(1)
        val sink = StalledSink(gate)
        val l = log(sink, capacity = 32)
        val started = System.nanoTime()
        repeat(5_000) { l.record(record(it + 1)) }
        val elapsedMs = (System.nanoTime() - started) / 1e6
        assertTrue("5000 records took ${elapsedMs}ms with a stalled sink", elapsedMs < 1_000)
        assertTrue("excess records must be dropped, not queued", l.dropped.get() >= 5_000 - 32 - 4)
        gate.countDown()
        assertTrue(l.flush(5_000))
        assertTrue("at most capacity + in-flight + markers can ever be written", sink.appended <= 32 + 4)
        l.close()
    }

    @Test fun eachRecordCallIsCheapEvenWhenEveryWriteFails() {
        val l = log(FlakySink(failing = true), capacity = 64, failures = 3)
        val started = System.nanoTime()
        repeat(2_000) { l.record(record(it + 1)) }
        val perCallUs = (System.nanoTime() - started) / 1e3 / 2_000
        assertTrue("per-call cost ${perCallUs}us", perCallUs < 500)
        l.close()
    }

    // ---- failure isolation and recovery -------------------------------------------------------------------

    @Test fun sinkFailuresNeverReachTheCallerDisableTheLogAndRecoverAtTheNextGeneration() {
        val sink = FlakySink(failing = true)
        val l = log(sink, failures = 3)
        for (i in 1..10) l.record(record(i)) // must not throw
        assertTrue(l.flush(2_000))
        assertTrue("log disables itself after repeated failures", l.isDisabled)
        val droppedWhileDisabled = l.dropped.get()
        l.record(record(11))
        assertEquals(droppedWhileDisabled + 1, l.dropped.get())
        assertTrue(l.writeFailures.get() >= 3)

        sink.failing = false // the disk problem is fixed; a new camera generation is the recovery point
        l.generationReset()
        l.record(record(1))
        assertTrue(l.flush(2_000))
        assertFalse(l.isDisabled)
        val events = sink.lines.map(::parse).filter { it["type"].asString == "event" }
        assertEquals(1, events.size)
        assertEquals(1, events[0]["gen"].asInt)
        l.close()
    }

    @Test fun anIsolatedFailureDoesNotDisableTheLog() {
        val sink = FlakySink(failing = true)
        val l = log(sink, failures = 5)
        l.record(record(1)); assertTrue(l.flush(2_000))
        sink.failing = false
        l.record(record(2)); l.record(record(3)); assertTrue(l.flush(2_000))
        assertFalse(l.isDisabled)
        assertEquals(2, sink.lines.map(::parse).count { it["type"].asString == "event" })
        l.close()
    }

    @Test fun closeStopsTheWriterThreadIsIdempotentAndLaterRecordsAreHarmlessDrops() {
        val sink = ListSink()
        val l = log(sink)
        l.record(record())
        l.close(); l.close()
        assertFalse("writer thread must not outlive the session", l.isWriterAlive())
        assertTrue(sink.closed)
        val before = l.dropped.get()
        l.record(record(2)); l.generationReset()
        assertEquals(before + 1, l.dropped.get())
        assertEquals("session_end", parse(sink.lines.last())["type"].asString)
    }

    @Test fun closeReturnsPromptlyEvenWithAStalledSink() {
        val gate = CountDownLatch(1)
        val l = log(StalledSink(gate), capacity = 8)
        repeat(20) { l.record(record(it + 1)) }
        val started = System.nanoTime()
        l.close()
        assertTrue("close() took ${(System.nanoTime() - started) / 1e6}ms", (System.nanoTime() - started) / 1e6 < 3_000)
        gate.countDown()
    }

    // ---- observe-only: recognition output is unaffected ------------------------------------------------------------

    @Test fun attachingAFailingOrStalledShadowLogDoesNotChangeTheSentenceOrAnyDecision() {
        val glosses = List(236) { "G$it" }.toMutableList().apply { this[0] = "HELLO"; this[1] = "HOME" }
        fun probs(top: Int, p1: Float) = FloatArray(236) { (1f - p1) / 235f }.also { it[top] = p1 }
        val script = listOf(Triple(0, 0.95f, 1.0), Triple(1, 0.30f, 1.0), Triple(1, 0.92f, 0.0), Triple(1, 0.90f, 1.0))

        fun run(shadow: ShadowEvalLog?): Pair<String, List<CommitOutcome>> {
            val sentence = SentenceBuilder()
            val committer = PhoneEventCommitter(PhoneRecognitionConfiguration.STABLE.commitPolicy(), sentence)
            val outcomes = script.mapIndexed { i, (cls, p, hand) ->
                val p1 = probs(cls, p)
                val top5 = p1.indices.sortedByDescending { p1[it] }.take(5).toIntArray()
                val r = committer.decide(i + 1, p1, top5, glosses, hand)
                shadow?.record(record(i + 1, r.decision.outcome, r.committed != null, p))
                r.decision.outcome
            }
            return sentence.text() to outcomes
        }

        val baseline = run(null)
        val gate = CountDownLatch(1)
        val withStalled = run(log(StalledSink(gate), capacity = 2))
        val withFailing = run(log(FlakySink(true), failures = 1))
        gate.countDown()
        assertEquals(baseline, withStalled)
        assertEquals(baseline, withFailing)
        assertEquals("HELLO HOME", baseline.first)
        assertEquals(listOf(CommitOutcome.ACCEPT, CommitOutcome.UNCERTAIN, CommitOutcome.REJECT, CommitOutcome.ACCEPT), baseline.second)
    }

    // ---- bounded, rotating file sink ---------------------------------------------------------------------------

    private fun tempDir(): File = Files.createTempDirectory("shadow_eval_test").toFile().also { it.deleteOnExit() }

    @Test fun fileSinkNeverExceedsItsFileCountAndSizeBudget() {
        val dir = tempDir()
        val sink = RotatingFileShadowSink(dir, "sidA", maxFileBytes = 1_000, maxFiles = 3)
        repeat(500) { sink.append("""{"n":$it,"pad":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}""") }
        sink.close()
        val files = dir.listFiles()!!.filter { it.name.endsWith(".jsonl") }
        assertTrue("files=${files.size}", files.size <= 3)
        assertTrue(files.all { it.length() <= 1_000 })
        assertTrue("total bytes ${files.sumOf { it.length() }}", files.sumOf { it.length() } <= 3_000)
        // The newest data survives, the oldest was pruned.
        assertTrue(files.flatMap { it.readLines() }.any { it.contains("\"n\":499") })
        assertFalse(files.flatMap { it.readLines() }.any { it.contains("\"n\":0,") })
    }

    @Test fun fileSinkDeletesFilesOlderThanTheRetentionWindow() {
        val dir = tempDir()
        val old = File(dir, "shadow_oldsid_0.jsonl").apply { writeText("{}\n"); setLastModified(1_000L) }
        val unrelated = File(dir, "run_label.txt").apply { writeText("S03") }
        val sink = RotatingFileShadowSink(dir, "sidB", maxAgeMs = 1_000_000L, nowMs = { 10_000_000L })
        sink.append("{}")
        sink.close()
        assertFalse("aged-out shadow file must be deleted", old.exists())
        assertTrue("files the sink does not own are never touched", unrelated.exists())
    }

    @Test fun fileSinkReportsUnwritableLocationsAndOversizedLinesAsIoErrors() {
        val blocker = File.createTempFile("not_a_dir", ".tmp").also { it.deleteOnExit() }
        val sink = RotatingFileShadowSink(File(blocker, "sub"), "sidC")
        try { sink.append("{}"); fail("expected IOException") } catch (_: IOException) { }
        val sink2 = RotatingFileShadowSink(tempDir(), "sidD", maxLineChars = 10)
        try { sink2.append("x".repeat(11)); fail("expected IOException") } catch (_: IOException) { }
    }

    @Test fun logOverARealFileSinkWritesParseableJsonLinesAndSurvivesAnUnwritableSink() {
        val dir = tempDir()
        val l = ShadowEvalLog(RotatingFileShadowSink(dir, "abc"), "abc", { "run1" })
        l.record(record(1)); l.record(record(2, CommitOutcome.REJECT, committed = false))
        assertTrue(l.flush(2_000)); l.close()
        val lines = dir.listFiles()!!.flatMap { it.readLines() }
        assertEquals(4, lines.size) // start, 2 events, end
        assertTrue(lines.all { parse(it)["schema"].asString == ShadowEvalLog.SCHEMA })

        val blocker = File.createTempFile("blocked", ".tmp").also { it.deleteOnExit() }
        val broken = ShadowEvalLog(RotatingFileShadowSink(File(blocker, "x"), "zzz"), "zzz")
        repeat(20) { broken.record(record(it + 1)) } // must never throw
        assertTrue(broken.flush(2_000))
        assertTrue(broken.writeFailures.get() > 0)
        broken.close()
    }

    @Test fun lagIsOnlyReportedWhenTheCameraClockIsPlausiblyComparable() {
        assertEquals(35.0, ShadowEvalLog.plausibleLagMs(35.0)!!, 0.0)
        assertNull(ShadowEvalLog.plausibleLagMs(-5.0))
        assertNull(ShadowEvalLog.plausibleLagMs(3_600_000.0))
        assertNull(ShadowEvalLog.plausibleLagMs(Double.NaN))
    }

    @Test fun separateLogsNeverShareStateOrWriterThreads() {
        val a = ListSink(); val b = ListSink()
        val la = log(a); val lb = log(b)
        la.record(record(1)); assertTrue(la.flush(2_000)); la.close()
        assertTrue("closing one log must not stop another", lb.isWriterAlive())
        assertEquals(0, b.lines.count { parse(it)["type"].asString == "event" })
        lb.close()
        assertFalse(lb.isWriterAlive())
    }
}
