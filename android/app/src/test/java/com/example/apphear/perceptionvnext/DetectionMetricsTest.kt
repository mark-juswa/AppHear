package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicBoolean

/** Phase 2 observability: correctness of the arithmetic, boundedness and low per-call cost. */
class DetectionMetricsTest {
    private val frameNs = 66_666_667L // 15 fps

    @Test fun percentilesUseNearestRankAndEmptyStagesReportNothing() {
        val m = DetectionMetrics()
        (1..100).forEach { m.record(DetectionStage.POSE, it.toDouble()) }
        val s = m.snapshot().stages.getValue(DetectionStage.POSE)
        assertEquals(100, s.n)
        assertEquals(50.0, s.p50!!, 0.0)
        assertEquals(95.0, s.p95!!, 0.0)
        assertEquals(100.0, s.max!!, 0.0)
        assertNull(m.snapshot().stages.getValue(DetectionStage.RECOGNIZER).p50)
    }

    @Test fun theRingKeepsOnlyTheNewestSamplesAndMemoryDoesNotGrow() {
        val m = DetectionMetrics(ringSize = 8)
        (1..20).forEach { m.record(DetectionStage.PREPROCESS, it.toDouble()) }
        val s = m.snapshot().stages.getValue(DetectionStage.PREPROCESS)
        assertEquals(8, s.n)
        assertEquals(20.0, s.max!!, 0.0)
        assertEquals(16.0, s.p50!!, 0.0) // newest 13..20
        repeat(1_000_000) { m.record(DetectionStage.PREPROCESS, 1.0) }
        assertEquals(8, m.snapshot().stages.getValue(DetectionStage.PREPROCESS).n)
    }

    @Test fun invalidSamplesAreIgnored() {
        val m = DetectionMetrics()
        m.record(DetectionStage.POSE, Double.NaN); m.record(DetectionStage.POSE, -1.0); m.record(DetectionStage.POSE, Double.POSITIVE_INFINITY)
        assertEquals(0, m.snapshot().stages.getValue(DetectionStage.POSE).n)
    }

    @Test fun cameraDropsAreEstimatedFromTimestampGapsWithoutInflatingTheInterval() {
        val m = DetectionMetrics()
        var t = 1_000_000_000L
        repeat(10) { m.inputFrame(t); t += frameNs }
        t += 2 * frameNs                // two frames never delivered
        m.inputFrame(t); t += frameNs
        m.inputFrame(t); t += frameNs
        t += 4 * frameNs                // four more never delivered
        m.inputFrame(t)
        val s = m.snapshot()
        assertEquals(13L, s.inputFrames)
        assertEquals(6L, s.estimatedCameraDrops)
    }

    @Test fun withTheRequestedRateKnownDropsAreStillCountedWhenTheAnalyzerIsSaturated() {
        // Regression for a flaw found on an emulator: a saturated analyzer receives frames spaced by processing time
        // (here 170 ms for a 15 fps camera). A stream-learned interval adapts to 170 ms and sees no drops.
        val saturated = 170_000_000L
        val learned = DetectionMetrics()
        val known = DetectionMetrics(nominalFps = 15.0)
        var t = 1_000_000_000L
        repeat(11) { learned.inputFrame(t); known.inputFrame(t); t += saturated }
        assertEquals("learned interval cannot see saturation drops", 0L, learned.snapshot().estimatedCameraDrops)
        assertEquals("10 gaps of 2.55 frame intervals -> 2 missing frames each", 20L, known.snapshot().estimatedCameraDrops)
    }

    @Test fun deliveredFpsComesFromCameraTimestampsAndProcessedFpsAndBusyRatioFromCompletions() {
        val m = DetectionMetrics()
        var t = 5_000_000_000L
        repeat(30) { m.inputFrame(t); t += frameNs }
        assertEquals(15.0, m.snapshot().deliveredFps!!, 0.05)
        var now = 0L
        repeat(20) { m.frameProcessed(totalMs = 50.0, nowNs = now); now += 100_000_000L } // 10 fps, 50% busy
        val s = m.snapshot()
        assertEquals(10.0, s.processedFps!!, 0.05)
        assertEquals(0.5, s.busyRatio!!, 0.02)
        assertEquals(20L, s.processedFrames)
    }

    @Test fun faultCodeTrackingIsBounded() {
        val m = DetectionMetrics()
        (1..100).forEach { m.fault("CODE_NUMBER_$it", known = false) }
        val codes = m.snapshot().faultCodes
        assertTrue("distinct codes bounded: ${codes.size}", codes.size <= DetectionMetrics.MAX_FAULT_CODES + 1)
        assertEquals(100L, codes.values.sum())
        assertTrue(codes.containsKey("OTHER"))
    }

    @Test fun logLineContainsOnlyNumbersStageNamesAndFaultCodes() {
        val m = DetectionMetrics()
        m.inputFrame(1_000_000_000L); m.inputFrame(1_066_666_667L)
        m.record(DetectionStage.POSE, 88.5); m.fault("APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP", true)
        m.recoveryAttempt(true); m.frameProcessed(120.0, 1L)
        val line = m.snapshot().toLogLine()
        assertTrue(line, line.matches(Regex("[A-Za-z0-9_=/.,:% -]+")))
        assertTrue(line.contains("pose=88.5/88.5"))
        assertTrue(line.contains("APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP:1"))
    }

    @Test fun frameAgeIsOnlyAcceptedWhenTheCameraClockIsPlausiblyComparable() {
        assertEquals(40.0, DetectionMetrics.plausibleAgeMs(40.0)!!, 0.0)
        assertNull(DetectionMetrics.plausibleAgeMs(-1.0))
        assertNull(DetectionMetrics.plausibleAgeMs(1e9))
        assertNull(DetectionMetrics.plausibleAgeMs(Double.NaN))
    }

    @Test fun recordingIsCheapOnTheCallingThread() {
        // JVM estimate on a development machine, NOT a phone measurement: guards against accidental allocation or
        // locking regressions (the budget is deliberately generous).
        val m = DetectionMetrics()
        repeat(50_000) { m.record(DetectionStage.POSE, 1.0) } // warm-up
        val n = 500_000
        val t0 = System.nanoTime()
        for (i in 0 until n) m.record(DetectionStage.POSE, i.toDouble())
        val perCallNs = (System.nanoTime() - t0).toDouble() / n
        assertTrue("record() cost ${perCallNs}ns per call", perCallNs < 5_000)
    }

    @Test fun snapshotsTakenWhileAnotherThreadWritesAreConsistentAndNeverThrow() {
        val m = DetectionMetrics()
        val stop = AtomicBoolean(false)
        val failure = arrayOfNulls<Throwable>(1)
        val writer = Thread {
            try { var i = 0; while (!stop.get()) { m.record(DetectionStage.FRAME_TOTAL, (i++ % 50).toDouble()); m.frameProcessed(1.0) } }
            catch (t: Throwable) { failure[0] = t }
        }.also { it.start() }
        repeat(200) { val s = m.snapshot(); assertTrue(s.stages.getValue(DetectionStage.FRAME_TOTAL).n <= 256) }
        stop.set(true); writer.join(5_000)
        assertFalse(writer.isAlive)
        assertNull(failure[0])
    }
}
