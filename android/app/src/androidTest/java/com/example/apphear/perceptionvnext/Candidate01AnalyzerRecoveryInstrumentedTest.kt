package com.example.apphear.perceptionvnext

import android.annotation.SuppressLint
import android.graphics.Matrix
import android.graphics.PixelFormat
import android.graphics.Rect
import android.media.Image
import android.util.Log
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageInfo
import androidx.camera.core.ImageProxy
import androidx.camera.core.impl.TagBundle
import androidx.camera.core.impl.utils.ExifData
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.pipeline.FrameResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.util.concurrent.atomic.AtomicInteger

/**
 * Phase 2 on the REAL runtime: the real Candidate01FrameAnalyzer, native preprocessor, DWPose-t, hand refiner,
 * S2-R2 and decoder, fed synthetic gray frames through a fake ImageProxy. Faults are injected through the
 * analyzer's genuine failure paths. Frames contain no person, so no hands/signs are detected: this verifies
 * RECOVERY, CLEANUP and METRICS WIRING, not detection quality or representative speed.
 */
@RunWith(AndroidJUnit4::class)
class Candidate01AnalyzerRecoveryInstrumentedTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val frameNs = 66_666_667L

    @SuppressLint("RestrictedApi")
    private class FakeImage(
        private val w: Int, private val h: Int, private val timestampNs: Long, private val bytes: Int = w * h * 4,
        shared: ByteBuffer? = null,
    ) : ImageProxy {
        val closes = AtomicInteger(0)
        private val pixels: ByteBuffer = shared ?: ByteBuffer.allocateDirect(bytes).also { b -> repeat(bytes) { b.put((120 + it % 7).toByte()) }; b.rewind() }
        private val plane = object : ImageProxy.PlaneProxy {
            override fun getRowStride() = w * 4
            override fun getPixelStride() = 4
            override fun getBuffer(): ByteBuffer = pixels
        }
        private val info = object : ImageInfo {
            override fun getTagBundle(): TagBundle = TagBundle.emptyBundle()
            override fun getTimestamp() = timestampNs
            override fun getRotationDegrees() = 0
            override fun populateExifData(exifBuilder: ExifData.Builder) = Unit
            override fun getSensorToBufferTransformMatrix() = Matrix()
        }
        override fun close() { closes.incrementAndGet() }
        override fun getCropRect() = Rect(0, 0, w, h)
        override fun setCropRect(rect: Rect?) = Unit
        override fun getFormat() = PixelFormat.RGBA_8888
        override fun getHeight() = h
        override fun getWidth() = w
        override fun getPlanes(): Array<ImageProxy.PlaneProxy> = arrayOf(plane)
        override fun getImageInfo(): ImageInfo = info
        @ExperimentalGetImage override fun getImage(): Image? = null
    }

    private class Harness(context: android.content.Context, ownsObservation: ((PhoneRawObservation, ImageProxy) -> Boolean)? = null) {
        val results = AtomicInteger(0)
        val failures = mutableListOf<Throwable>()
        private val t0 = System.nanoTime()
        val session = PhoneProductionSession.load(context)
        private val sessionLoadedNs = System.nanoTime()
        val analyzer = Candidate01FrameAnalyzer(context, session, { _: FrameResult -> results.incrementAndGet() }, ownsObservation) { failures.add(it) }
        val sessionLoadMs = (sessionLoadedNs - t0) / 1e6
        val analyzerInitMs = (System.nanoTime() - sessionLoadedNs) / 1e6
        /** Only the per-frame close counters are kept; the images themselves are NOT retained (they hold 691 KB each). */
        private val closeCounters = mutableListOf<AtomicInteger>()
        private val standardPixels: ByteBuffer = ByteBuffer.allocateDirect(480 * 360 * 4)
            .also { b -> repeat(480 * 360 * 4) { b.put((120 + it % 7).toByte()) }; b.rewind() }
        fun feed(timestampNs: Long, w: Int = 480, h: Int = 360, bytes: Int = w * h * 4): FakeImage {
            val image = FakeImage(w, h, timestampNs, bytes, if (w == 480 && h == 360 && bytes == w * h * 4) standardPixels else null)
            closeCounters.add(image.closes)
            analyzer.analyze(image)
            return image
        }
        fun closeAll() { analyzer.close(); session.close() }
        fun everyFrameWasClosedExactlyOnce() = closeCounters.all { it.get() == 1 }
    }

    private fun <T> withHarness(owns: ((PhoneRawObservation, ImageProxy) -> Boolean)? = null, body: (Harness) -> T): T {
        val h = Harness(context, owns)
        try { return body(h) } finally { h.closeAll() }
    }

    private fun log(label: String, h: Harness) = Log.i("Phase2Instrumented", "$label ${h.analyzer.metrics.snapshot().toLogLine()}")

    @Test fun initializationAndPerFrameAllocationAreMeasured() = withHarness { h ->
        // Measurements, not assertions of speed: ART's own cumulative allocation counter is independent of CPU
        // speed, so bytes per frame is meaningful on any device; the init times are this device only.
        var t = 1_000_000_000L
        repeat(30) { h.feed(t); t += frameNs }  // warm-up
        val before = android.os.Debug.getRuntimeStat("art.gc.bytes-allocated")?.toLongOrNull()
        val frames = 200
        repeat(frames) { h.feed(t); t += frameNs }
        val after = android.os.Debug.getRuntimeStat("art.gc.bytes-allocated")?.toLongOrNull()
        Log.i("Phase2Instrumented", "init sessionLoadMs=${"%.0f".format(h.sessionLoadMs)} analyzerInitMs=${"%.0f".format(h.analyzerInitMs)} " +
            "javaAllocBytesPerFrame=${if (before != null && after != null) (after - before) / frames else -1}")
        assertTrue(h.failures.isEmpty())
    }

    @Test fun blankFramesAreProcessedAndTheMetricsAreWired() = withHarness { h ->
        var t = 1_000_000_000L
        repeat(12) { h.feed(t); t += frameNs }
        val s = h.analyzer.metrics.snapshot()
        log("blank_frames", h)
        assertEquals(12, h.results.get())
        assertEquals(12L, s.inputFrames)
        assertEquals(12L, s.processedFrames)
        assertEquals(0L, s.faults)
        assertTrue(h.failures.isEmpty())
        for (stage in listOf(DetectionStage.PREPROCESS, DetectionStage.POSE, DetectionStage.POSE_DECODE, DetectionStage.HANDS_WALL,
            DetectionStage.SEGMENTER, DetectionStage.FRAME_TOTAL)) assertEquals(stage.name, 12, s.stages.getValue(stage).n)
        assertEquals("no person, so no hand proposals and no per-hand samples", 0, s.stages.getValue(DetectionStage.LEFT_HAND).n)
        assertTrue(h.everyFrameWasClosedExactlyOnce())
    }

    @Test fun aNonChronologicalTimestampIsRecoveredAndLaterFramesRun() = withHarness { h ->
        var t = 1_000_000_000L
        repeat(5) { h.feed(t); t += frameNs }
        h.feed(t - 10 * frameNs)           // camera glitch: timestamp goes backwards
        repeat(5) { h.feed(t); t += frameNs }
        val s = h.analyzer.metrics.snapshot()
        log("nonchronological", h)
        assertEquals(10, h.results.get())  // the bad frame published nothing; every other frame did
        assertEquals(1L, s.faults)
        assertEquals(1L, s.recoverySuccesses)
        assertTrue("recovered, so the screen was NOT told recognition stopped", h.failures.isEmpty())
        assertEquals(1L, s.faultCodes["APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP"])
        assertTrue(h.everyFrameWasClosedExactlyOnce())
    }

    @Test fun anUndersizedBufferIsAPerceptionFaultAndTheNextGoodFrameRecreatesThePreprocessor() = withHarness { h ->
        var t = 1_000_000_000L
        repeat(3) { h.feed(t); t += frameNs }
        h.feed(t, bytes = 1_000); t += frameNs
        repeat(3) { h.feed(t); t += frameNs }
        val s = h.analyzer.metrics.snapshot()
        log("undersized_buffer", h)
        assertEquals(6, h.results.get())
        assertEquals(1L, s.faults)
        assertEquals(1L, s.faultCodes["VNEXT_NATIVE_DIRECT_BUFFER_BOUNDS"])
        assertTrue(h.failures.isEmpty())
        assertTrue(h.everyFrameWasClosedExactlyOnce())
    }

    @Test fun aSessionPhaseFaultResetsTheTemporalSessionAndRecognitionResumes() {
        val calls = AtomicInteger(0)
        withHarness(owns = { _, _ -> if (calls.incrementAndGet() == 4) throw IllegalStateException("PHONE_SEGMENTATION_NONFINITE_FEATURE") else false }) { h ->
            var t = 1_000_000_000L
            repeat(10) { h.feed(t); t += frameNs }
            val s = h.analyzer.metrics.snapshot()
            log("session_phase_fault", h)
            // Without the reset the analyzer's sourceIndex would be ahead of the session's and every later frame
            // would fail APP_PHONE_SOURCE_INDEX_DISCONTINUITY (the pre-Phase-2 permanent stop).
            assertEquals("only the injected frame failed", 1L, s.faults)
            assertEquals(9, h.results.get())
            assertTrue(h.failures.isEmpty())
            assertEquals(9L, s.processedFrames)
            assertTrue(h.everyFrameWasClosedExactlyOnce())
        }
    }

    @Test fun aRepeatingFaultEndsInOneFatalReportAndLaterFramesAreIgnoredButStillClosed() = withHarness { h ->
        var t = 1_000_000_000L
        repeat(3) { h.feed(t); t += frameNs }
        repeat(10) { h.feed(t, bytes = 1_000); t += frameNs }   // persistent fault
        h.feed(t)                                                  // a good frame after the fatal stop is ignored
        val s = h.analyzer.metrics.snapshot()
        log("repeating_fault", h)
        assertEquals("recovery is bounded: exactly one fatal report", 1, h.failures.size)
        val failure = h.failures.single()
        assertTrue(failure is AnalyzerFatalException)
        assertEquals("FAULT_BUDGET_EXHAUSTED", (failure as AnalyzerFatalException).report.escalation)
        assertEquals(1L, s.fatalStops)
        assertTrue("frames after the fatal stop are counted", s.framesAfterFatal >= 1)
        assertTrue(h.everyFrameWasClosedExactlyOnce())
    }

    @Test fun aCameraGenerationChangeMayRestartTimestampsWithoutAFault() = withHarness { h ->
        var t = 9_000_000_000L
        repeat(5) { h.feed(t); t += frameNs }
        h.analyzer.resetTemporalSession()          // what RecognitionActivity does on a camera switch / stop
        var t2 = 100_000_000L                       // a new camera session restarts its clock below the old one
        repeat(5) { h.feed(t2); t2 += frameNs }
        val s = h.analyzer.metrics.snapshot()
        assertEquals(10, h.results.get())
        assertEquals(0L, s.faults)
        assertTrue(h.failures.isEmpty())
    }

    @Test fun closeIsIdempotentAndFramesAfterCloseAreIgnoredAndClosed() {
        val h = Harness(context)
        var t = 1_000_000_000L
        repeat(3) { h.feed(t); t += frameNs }
        h.closeAll(); h.analyzer.close()
        val late = h.feed(t)
        assertEquals(3, h.results.get())
        assertEquals(1, late.closes.get())
        assertNull(h.failures.firstOrNull())
    }

    /**
     * Leak vs churn. The analyzer allocates short-lived garbage on every frame (the DWPose output is converted to
     * nested arrays), so ONE before/after sample after 200 frames mixes uncollected garbage with a real leak. A
     * leak keeps raising the post-GC level round after round; churn plateaus. Rounds 2..N must not keep rising.
     */
    @Test fun heapLevelAfterGcPlateausAcrossRoundsOfFrames() = withHarness { h ->
        var t = 1_000_000_000L
        val javaLevels = mutableListOf<Long>()
        val nativeLevels = mutableListOf<Long>()
        repeat(6) { round ->
            repeat(100) { h.feed(t); t += frameNs }
            repeat(3) { System.gc(); Runtime.getRuntime().runFinalization(); Thread.sleep(300) }
            javaLevels.add(Runtime.getRuntime().let { it.totalMemory() - it.freeMemory() })
            nativeLevels.add(android.os.Debug.getNativeHeapAllocatedSize())
            Log.i("Phase2Instrumented", "heap_round=$round frames=${(round + 1) * 100} javaMB=${javaLevels.last() / 1048576.0} nativeMB=${nativeLevels.last() / 1048576.0}")
        }
        val javaRise = javaLevels.last() - javaLevels[1]
        val nativeRise = nativeLevels.last() - nativeLevels[1]
        assertTrue("post-GC java level kept rising: ${javaLevels.map { it / 1048576 }} MB", javaRise < 24L * 1048576)
        assertTrue("post-GC native level kept rising: ${nativeLevels.map { it / 1048576 }} MB", nativeRise < 24L * 1048576)
        assertTrue(h.failures.isEmpty())
    }
}
