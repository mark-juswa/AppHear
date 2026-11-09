package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Hand-duplication diagnostics (bug: one physical hand shows two skeletons). The metric must separate
 * "the two slots describe the same hand" (IoU ~ 1) from "two real hands" (IoU ~ 0) without a tuned cutoff.
 */
class HandPairDiagnosticsTest {
    private val all = BooleanArray(21) { true }

    /** 21 points on a [size]-wide square grid whose top-left corner is ([x0], [y0]). */
    private fun hand(x0: Float, y0: Float, size: Float = 100f): FloatArray {
        val xy = FloatArray(42)
        for (i in 0 until 21) {
            xy[i * 2] = x0 + size * (i % 5) / 4f
            xy[i * 2 + 1] = y0 + size * (i / 5) / 4f
        }
        return xy
    }

    @Test fun identicalSkeletonsHaveUnitOverlapAndZeroCentroidDistance() {
        val a = hand(200f, 100f)
        val o = requireNotNull(HandPairDiagnostics.overlap(a, all, a.copyOf(), all))
        assertEquals(1.0, o.iou, 1e-9)
        assertEquals(0.0, o.centroidDistanceOverSize, 1e-9)
    }

    @Test fun slightlyShiftedSkeletonStillCountsAsTheSameHand() {
        val o = requireNotNull(HandPairDiagnostics.overlap(hand(200f, 100f), all, hand(210f, 105f), all))
        assertTrue("iou=${o.iou}", o.iou > 0.7)
        assertTrue(o.centroidDistanceOverSize < 0.2)
    }

    @Test fun twoSeparatedHandsHaveNoOverlap() {
        val o = requireNotNull(HandPairDiagnostics.overlap(hand(50f, 100f), all, hand(400f, 100f), all))
        assertEquals(0.0, o.iou, 1e-9)
        assertTrue(o.centroidDistanceOverSize > 2.0)
    }

    @Test fun invalidPointsAreIgnoredAndTooFewValidPointsYieldNull() {
        val a = hand(200f, 100f)
        val onlyTwo = BooleanArray(21).also { it[0] = true; it[1] = true }
        assertNull(HandPairDiagnostics.overlap(a, all, a, onlyTwo))
        // An invalid point far away must not stretch the box.
        val polluted = a.copyOf().also { it[40] = 9000f; it[41] = 9000f }
        val valid = BooleanArray(21) { it != 20 }
        val o = requireNotNull(HandPairDiagnostics.overlap(polluted, valid, a, valid))
        assertEquals(1.0, o.iou, 1e-9)
    }

    @Test fun nonFinitePointsAreIgnored() {
        val a = hand(200f, 100f)
        val bad = a.copyOf().also { it[0] = Float.NaN }
        assertNotNull(HandPairDiagnostics.overlap(bad, all, a, all))
    }

    private fun sample(roiIou: Double? = null, pl: Float = 0.9f, pr: Float = 0.9f, hl: Float = 0.1f, hr: Float = 0.9f, sl: Float = 0.5f, sr: Float = 0.5f) =
        HandPairSample(roiIou, pl, pr, hl, hr, sl, sr)

    @Test fun roiIouOfIdenticalDisjointAndMissingRois() {
        fun roi(cx: Float, cy: Float, side: Float) = PerceptionVNextMath.HandRoi(cx, cy, side, 480, 360, 10)
        assertEquals(1.0, HandPairDiagnostics.roiIou(roi(100f, 100f, 80f), roi(100f, 100f, 80f))!!, 1e-9)
        assertEquals(0.0, HandPairDiagnostics.roiIou(roi(50f, 50f, 40f), roi(300f, 300f, 40f))!!, 1e-9)
        assertNull(HandPairDiagnostics.roiIou(null, roi(1f, 1f, 5f)))
    }

    @Test fun countersBinByObservedCountAndOverlap() {
        val c = HandPairCounters()
        c.record(false, false, null, null)                                         // no hands
        c.record(true, false, null, null)                                          // one hand (left)
        c.record(false, true, null, null)                                          // one hand (right)
        c.record(true, true, HandPairDiagnostics.Overlap(0.95, 0.02), sample())    // both observed, same place
        c.record(true, true, HandPairDiagnostics.Overlap(0.30, 0.9), sample())     // partial overlap
        c.record(true, true, HandPairDiagnostics.Overlap(0.0, 3.0), sample())      // two real hands
        c.record(true, true, null, sample())                                       // both observed, overlap not computable
        val s = c.snapshot()
        assertEquals(7L, s.frames)
        assertEquals(1L, s.noHand)
        assertEquals(1L, s.leftOnly)
        assertEquals(1L, s.rightOnly)
        assertEquals(4L, s.bothObserved)
        assertEquals(1L, s.bothHighOverlap)
        assertEquals(1L, s.bothPartialOverlap)
        assertEquals(1L, s.bothSeparate)
        assertEquals(1L, s.bothOverlapUnknown)
    }

    @Test fun highOverlapFramesSeparateDwposeDuplicationFromRefinerSnapping() {
        val c = HandPairCounters()
        // DWPose already proposed the same box twice
        c.record(true, true, HandPairDiagnostics.Overlap(0.9, 0.05), sample(roiIou = 0.95))
        // different proposals, refiner moved both onto one hand
        c.record(true, true, HandPairDiagnostics.Overlap(0.9, 0.05), sample(roiIou = 0.1))
        c.record(true, true, HandPairDiagnostics.Overlap(0.9, 0.05), sample(roiIou = null))
        val s = c.snapshot()
        assertEquals(3L, s.bothHighOverlap)
        assertEquals(1L, s.highRoiSame)
        assertEquals(1L, s.highRoiDifferent)
    }

    @Test fun highOverlapMeansReportPresenceHandednessAndSupport() {
        val c = HandPairCounters()
        c.record(true, true, HandPairDiagnostics.Overlap(0.9, 0.05), sample(0.9, pl = 0.6f, pr = 1.0f, hl = 0.2f, hr = 0.8f, sl = 0.4f, sr = 0.2f))
        c.record(true, true, HandPairDiagnostics.Overlap(0.9, 0.05), sample(0.9, pl = 1.0f, pr = 0.6f, hl = Float.NaN, hr = 0.6f, sl = 0.6f, sr = 0.4f))
        val s = c.snapshot()
        assertEquals(0.8, s.highMeans.presenceLeft!!, 1e-6)
        assertEquals(0.8, s.highMeans.presenceRight!!, 1e-6)
        assertEquals(0.2, s.highMeans.handednessLeft!!, 1e-6)    // NaN sample excluded
        assertEquals(0.7, s.highMeans.handednessRight!!, 1e-6)
        assertEquals(0.5, s.highMeans.supportLeft!!, 1e-6)
        assertEquals(0.3, s.highMeans.supportRight!!, 1e-6)
    }

    @Test fun logFragmentIsNumbersOnlyAndStable() {
        val c = HandPairCounters()
        c.record(true, true, HandPairDiagnostics.Overlap(0.9, 0.05), sample(0.95, pl = 0.9f, pr = 0.8f, hl = 0.1f, hr = 0.9f, sl = 0.5f, sr = 0.25f))
        assertEquals(
            "hands[n=1 none=0 L=0 R=0 both=1 same=1 part=0 sep=0 na=0 same.roi=1/0 same.pres=0.90/0.80 same.hand=0.10/0.90 same.sup=0.50/0.25]",
            c.snapshot().toLogFragment(),
        )
    }

    @Test fun logFragmentShowsNaWhenNoSamples() {
        val line = HandPairCounters().snapshot().toLogFragment()
        assertEquals("hands[n=0 none=0 L=0 R=0 both=0 same=0 part=0 sep=0 na=0 same.roi=0/0 same.pres=na/na same.hand=na/na same.sup=na/na]", line)
    }
}
