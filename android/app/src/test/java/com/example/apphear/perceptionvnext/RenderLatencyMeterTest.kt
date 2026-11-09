package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Capture-to-render latency accounting for the overlay (bug: overlay lags the preview). */
class RenderLatencyMeterTest {
    private fun ms(v: Long) = v * 1_000_000L

    @Test fun recordsUiHopAndEndToEndAge() {
        val m = DetectionMetrics()
        val meter = RenderLatencyMeter(m)
        // captured at t=1000ms, delivered by analyzer at 1230ms, drawn at 1245ms
        meter.rendered(sequence = 0, sourceTimestampNs = ms(1000), deliveredNs = ms(1230), renderedNs = ms(1245))
        val s = m.snapshot().stages
        assertEquals(15.0, s.getValue(DetectionStage.UI_HOP).p50!!, 1e-9)
        assertEquals(245.0, s.getValue(DetectionStage.END_TO_END).p50!!, 1e-9)
    }

    @Test fun redrawOfTheSameFrameIsNotCountedAgain() {
        val m = DetectionMetrics()
        val meter = RenderLatencyMeter(m)
        repeat(5) { meter.rendered(3, ms(1000), ms(1200), ms(1210L + it)) }
        assertEquals(1, m.snapshot().stages.getValue(DetectionStage.END_TO_END).n)
        assertEquals(4L, meter.snapshot().redraws)
    }

    @Test fun gapsInSequenceAreCountedAsAnalyzedButNeverRendered() {
        val meter = RenderLatencyMeter(DetectionMetrics())
        meter.rendered(0, ms(0), ms(10), ms(12))
        meter.rendered(1, ms(70), ms(80), ms(82))
        meter.rendered(5, ms(350), ms(360), ms(362))   // 2,3,4 never drawn
        val s = meter.snapshot()
        assertEquals(3L, s.rendered)
        assertEquals(3L, s.skippedBeforeRender)
        assertEquals(0L, s.outOfOrder)
    }

    @Test fun olderFrameRenderedAfterANewerOneIsOutOfOrderAndNotRecorded() {
        val m = DetectionMetrics()
        val meter = RenderLatencyMeter(m)
        meter.rendered(7, ms(700), ms(710), ms(712))
        meter.rendered(6, ms(630), ms(640), ms(713))
        assertEquals(1L, meter.snapshot().outOfOrder)
        assertEquals(1, m.snapshot().stages.getValue(DetectionStage.END_TO_END).n)
    }

    @Test fun implausibleCameraClockIsNotRecordedButHopStillIs() {
        val m = DetectionMetrics()
        val meter = RenderLatencyMeter(m)
        // sensor clock unrelated to elapsed-realtime: the age would be 100 s
        meter.rendered(0, ms(1), ms(100_000), ms(100_010))
        val s = m.snapshot().stages
        assertEquals(0, s.getValue(DetectionStage.END_TO_END).n)
        assertEquals(10.0, s.getValue(DetectionStage.UI_HOP).p50!!, 1e-9)
    }

    @Test fun framesWithoutTimingAreIgnored() {
        val m = DetectionMetrics()
        val meter = RenderLatencyMeter(m)
        meter.rendered(-1, 0L, 0L, ms(5))
        assertEquals(0L, meter.snapshot().rendered)
        assertEquals(0, m.snapshot().stages.getValue(DetectionStage.UI_HOP).n)
    }

    @Test fun logFragmentIsNumbersOnly() {
        val meter = RenderLatencyMeter(DetectionMetrics())
        meter.rendered(0, ms(0), ms(10), ms(12))
        meter.rendered(2, ms(100), ms(110), ms(112))
        assertEquals("render[n=2 skipped=1 stale=0 redraw=0]", meter.snapshot().toLogFragment())
    }

    @Test fun probeIsNoOpWithoutAMeter() {
        RenderLatencyProbe.meter = null
        RenderLatencyProbe.rendered(0, ms(0), ms(1), ms(2))   // must not throw
        assertNull(RenderLatencyProbe.meter)
        val meter = RenderLatencyMeter(DetectionMetrics())
        RenderLatencyProbe.meter = meter
        RenderLatencyProbe.rendered(0, ms(0), ms(1), ms(2))
        assertEquals(1L, meter.snapshot().rendered)
        RenderLatencyProbe.meter = null
    }
}
