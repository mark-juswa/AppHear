package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.atomic.AtomicInteger

/**
 * Phase 2: one bad frame must not end recognition, a broken model/resource must, and recovery must be bounded.
 * These tests prove the RECOVERY LOGIC. They say nothing about frame rate or accuracy.
 */
class AnalyzerFaultSupervisorTest {
    private var now = 0L
    private var resets = 0
    private val notified = mutableListOf<FaultReport>()
    private val metrics = DetectionMetrics()

    private fun supervisor(
        config: SupervisorConfig = SupervisorConfig(),
        reset: () -> Unit = { resets++ },
        onFault: (FaultReport) -> Unit = { notified.add(it) },
    ) = AnalyzerSupervisor(config, { now }, reset, metrics, onFault)

    private fun fail(code: String) = IllegalArgumentException(code)

    // ---- classification --------------------------------------------------------------------------------

    @Test fun knownFrameGuardCodesAreRecoverable() {
        for (code in AnalyzerFaultClassifier.KNOWN_FRAME_CODES) {
            assertEquals(code, FaultClass.RECOVERABLE_FRAME, AnalyzerFaultClassifier.classify(fail(code)))
            assertEquals(code, AnalyzerFaultClassifier.code(fail(code)))
        }
    }

    @Test fun modelContractAssetAndClosedResourceFailuresAreFatal() {
        listOf(
            "VNEXT_DWPOSE_T_ASSET_DRIFT", "VNEXT_HAND_REFINER_ASSET_DRIFT", "GATE4A1_MODEL_DRIFT",
            "GATE4A1_GATE2_MANIFEST_DRIFT", "VNEXT_DWPOSE_T_INPUT_CONTRACT", "VNEXT_DWPOSE_T_OUTPUT_CONTRACT",
            "APP_PHONE_MATERIALIZER_CONTRACT_DRIFT", "V3_HAND_PAIR_CLOSED", "VNEXT_NATIVE_CLOSED_HANDLE",
        ).forEach { assertEquals(it, FaultClass.FATAL, AnalyzerFaultClassifier.classify(IllegalStateException(it))) }
    }

    @Test fun errorsAndInterruptsAreFatalNeverRecovered() {
        listOf(OutOfMemoryError(), UnsatisfiedLinkError("x"), StackOverflowError(), AssertionError("x"), InterruptedException())
            .forEach { assertEquals(it.javaClass.simpleName, FaultClass.FATAL, AnalyzerFaultClassifier.classify(it)) }
    }

    @Test fun unknownRuntimeExceptionsAreRecoverableButBudgeted() {
        assertEquals(FaultClass.RECOVERABLE_FRAME, AnalyzerFaultClassifier.classify(RuntimeException("something odd happened")))
        assertFalse(AnalyzerFaultClassifier.isKnown(AnalyzerFaultClassifier.code(RuntimeException("something odd"))))
    }

    @Test fun faultCodesNeverCarryMessageTextOrUserData() {
        val code = AnalyzerFaultClassifier.code(IllegalStateException("failed for user alice@example.com at /home/alice"))
        assertEquals("IllegalStateException", code)
        assertEquals("APP_PHONE_SOURCE_INDEX_DISCONTINUITY",
            AnalyzerFaultClassifier.code(IllegalArgumentException("APP_PHONE_SOURCE_INDEX_DISCONTINUITY: expected 7 got 9")))
        assertTrue(AnalyzerFaultClassifier.code(RuntimeException("X".repeat(500) + "_" + "Y".repeat(500))).length <= 80)
    }

    // ---- recovery ----------------------------------------------------------------------------------------------

    @Test fun aPerceptionFaultSkipsTheFrameKeepsTemporalStateAndTheNextFrameRuns() {
        val s = supervisor()
        var ran = 0
        val first = s.runFrame { throw fail("VNEXT_NATIVE_DIRECT_BUFFER_BOUNDS") }
        assertTrue(first is FrameOutcome.Recovered)
        assertEquals(RecoveryAction.SKIP_FRAME, (first as FrameOutcome.Recovered).report.action)
        assertEquals("no temporal reset for a frame that never became an observation", 0, resets)
        assertEquals(FrameOutcome.Ok, s.runFrame { ran++ })
        assertEquals(1, ran)
        assertFalse(s.isFatal)
    }

    @Test fun aSessionPhaseFaultResetsTheTemporalSessionOnceAndRecognitionResumes() {
        val s = supervisor()
        val out = s.runFrame { ctx -> ctx.phase = AnalyzerPhase.SESSION; throw fail("PHONE_SEGMENTATION_NONFINITE_FEATURE") }
        assertEquals(RecoveryAction.RESET_TEMPORAL_SESSION, (out as FrameOutcome.Recovered).report.action)
        assertEquals(1, resets)
        assertEquals(FrameOutcome.Ok, s.runFrame { })
        assertEquals(1, resets)
    }

    /**
     * The ROOT CAUSE model. The analyzer increments its own `sourceIndex` while building the observation; the
     * session requires `observation.sourceIndex == nextSourceIndex`. If the session throws after that increment
     * and nothing resets either counter, EVERY later frame fails the continuity check. Before Phase 2 that meant
     * "stop for the rest of the session"; with a naive skip-and-continue it would mean an endless failure loop.
     */
    private class AnalyzerAndSessionCounters {
        var analyzerIndex = 0
        var sessionNext = 0
        var failNextConsume = false
        var consumed = 0
        fun frame(ctx: FrameContext) {
            ctx.phase = AnalyzerPhase.SESSION
            val index = analyzerIndex++
            require(index == sessionNext) { "APP_PHONE_SOURCE_INDEX_DISCONTINUITY" }
            if (failNextConsume) { failNextConsume = false; throw IllegalStateException("PHONE_SEGMENTATION_NONFINITE_FEATURE") }
            sessionNext++
            consumed++
        }
        fun reset() { analyzerIndex = 0; sessionNext = 0 }
    }

    @Test fun withoutAResetOneSessionFaultWouldPoisonEveryLaterFrame_withTheResetRecognitionResumes() {
        // (a) naive "skip and continue": the counters stay out of step, every frame fails until the budget is spent.
        val naive = AnalyzerAndSessionCounters().apply { failNextConsume = true }
        val naiveSupervisor = supervisor(reset = { /* no reset */ })
        var results = (1..10).map { naiveSupervisor.runFrame { c -> naive.frame(c) } }
        assertEquals("naive skip never resumes", 0, naive.consumed)
        assertTrue(results.any { it is FrameOutcome.Fatal })

        // (b) Phase 2: the session-phase fault resets both counters and the very next frame is consumed.
        val fixed = AnalyzerAndSessionCounters().apply { failNextConsume = true }
        val s = AnalyzerSupervisor(SupervisorConfig(), { now }, { fixed.reset() }, DetectionMetrics())
        results = (1..10).map { s.runFrame { c -> fixed.frame(c) } }
        assertEquals(1, results.count { it is FrameOutcome.Recovered })
        assertEquals("every frame after the fault is consumed", 9, fixed.consumed)
        assertFalse(s.isFatal)
    }

    @Test fun recoveryIsBoundedARepeatingFaultBecomesFatalInsteadOfLoopingForever() {
        val s = supervisor(SupervisorConfig(maxFaultsInWindow = 5, windowMs = 10_000))
        var executed = 0
        val outcomes = (1..6).map { s.runFrame { executed++; throw fail("VNEXT_NATIVE_GEOMETRY_INVALID") } }
        assertTrue(outcomes.take(5).all { it is FrameOutcome.Recovered })
        val last = outcomes[5] as FrameOutcome.Fatal
        assertEquals("FAULT_BUDGET_EXHAUSTED", last.report.escalation)
        assertTrue(s.isFatal)
        assertEquals(FrameOutcome.Rejected, s.runFrame { executed++ })
        assertEquals("a fatal supervisor never runs another frame", 6, executed)
    }

    @Test fun theFaultWindowSlidesSoSparseFaultsAreTolerated() {
        val s = supervisor(SupervisorConfig(maxFaultsInWindow = 2, windowMs = 10_000))
        for (t in listOf(0L, 4_000L)) { now = t; assertTrue(s.runFrame { throw fail("VNEXT_NATIVE_ROI_INVALID") } is FrameOutcome.Recovered) }
        now = 12_000 // the t=0 fault has aged out of the 10 s window
        assertTrue(s.runFrame { throw fail("VNEXT_NATIVE_ROI_INVALID") } is FrameOutcome.Recovered)
        now = 13_000 // t=4000, 12000, 13000 are all inside the window now -> 3 > 2
        assertTrue(s.runFrame { throw fail("VNEXT_NATIVE_ROI_INVALID") } is FrameOutcome.Fatal)
    }

    @Test fun anErrorIsFatalImmediatelyWithoutAResetAndKeepsItsCause() {
        val s = supervisor()
        val oom = OutOfMemoryError("native")
        val out = s.runFrame { ctx -> ctx.phase = AnalyzerPhase.SESSION; throw oom } as FrameOutcome.Fatal
        assertSame(oom, out.cause)
        assertEquals(0, resets)
        assertEquals(FaultClass.FATAL, out.report.faultClass)
        assertTrue(s.isFatal)
    }

    @Test fun aFailedRecoveryEscalatesToFatalAndKeepsBothFailures() {
        val boom = IllegalStateException("reset exploded")
        val s = supervisor(reset = { throw boom })
        val original = fail("PHONE_SEGMENTATION_NONFINITE_FEATURE")
        val out = s.runFrame { ctx -> ctx.phase = AnalyzerPhase.SESSION; throw original } as FrameOutcome.Fatal
        assertEquals("RECOVERY_FAILED", out.report.escalation)
        assertSame(original, out.cause)
        assertTrue(original.suppressed.contains(boom))
        assertEquals(1L, metrics.snapshot().recoveryAttempts)
        assertEquals(0L, metrics.snapshot().recoverySuccesses)
    }

    @Test fun aBrokenDiagnosticsCallbackNeverBreaksRecovery() {
        val s = supervisor(onFault = { throw IllegalStateException("log sink down") })
        assertTrue(s.runFrame { throw fail("VNEXT_NATIVE_ROI_INVALID") } is FrameOutcome.Recovered)
        assertEquals(FrameOutcome.Ok, s.runFrame { })
    }

    @Test fun fatalOutcomeBecomesAnAnalyzerFatalExceptionThatNamesTheCodeAndTruncatesTheMessage() {
        val s = supervisor()
        val out = s.runFrame { throw IllegalStateException("VNEXT_DWPOSE_T_ASSET_DRIFT " + "z".repeat(400)) } as FrameOutcome.Fatal
        val e = AnalyzerFatalException(out.report, out.cause)
        assertTrue(e.message!!.startsWith("ANALYZER_FATAL VNEXT_DWPOSE_T_ASSET_DRIFT (IllegalStateException)"))
        assertTrue(e.message!!.length < 260)
        assertSame(out.cause, e.cause)
    }

    @Test fun metricsReflectFaultsRecoveriesAndFatalStops() {
        val s = supervisor(SupervisorConfig(maxFaultsInWindow = 2, windowMs = 10_000))
        s.runFrame { throw fail("VNEXT_NATIVE_ROI_INVALID") }
        s.runFrame { ctx -> ctx.phase = AnalyzerPhase.SESSION; throw RuntimeException("mystery") }
        s.runFrame { throw fail("VNEXT_NATIVE_ROI_INVALID") } // third within window -> fatal
        val m = metrics.snapshot()
        assertEquals(3L, m.faults)
        assertEquals(2L, m.faultsKnownCode)
        assertEquals(1L, m.faultsUnknownCode)
        assertEquals(2L, m.recoverySuccesses)
        assertEquals(1L, m.fatalStops)
        assertEquals(2L, m.faultCodes["VNEXT_NATIVE_ROI_INVALID"] ?: 0L + 0L)
    }

    // ---- concurrency / lifecycle ---------------------------------------------------------------------------------

    @Test fun framesAreNeverRunConcurrently() {
        val s = supervisor()
        val inside = AtomicInteger(0)
        val maxInside = AtomicInteger(0)
        val start = CountDownLatch(1)
        val threads = (1..4).map {
            Thread {
                start.await()
                repeat(50) {
                    s.runFrame {
                        val n = inside.incrementAndGet()
                        maxInside.updateAndGet { m -> maxOf(m, n) }
                        Thread.yield()
                        inside.decrementAndGet()
                    }
                }
            }.also { it.start() }
        }
        start.countDown()
        threads.forEach { it.join(10_000) }
        assertEquals("model resources must never be entered by two frames at once", 1, maxInside.get())
    }

    @Test fun aNewSupervisorAfterAFatalStopModelsASessionRestartAndWorks() {
        val dead = supervisor()
        dead.runFrame { throw OutOfMemoryError() }
        assertTrue(dead.isFatal)
        val restarted = supervisor()
        assertEquals(FrameOutcome.Ok, restarted.runFrame { })
        assertNotNull(restarted)
    }
}
