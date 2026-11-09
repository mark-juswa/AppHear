package com.example.apphear.perceptionvnext

import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/**
 * Diagnostics for the "one physical hand shows two skeletons" report. OBSERVATION ONLY: nothing here changes
 * detection, the recorded observation, the overlay, or recognition.
 *
 * Why it exists: left and right hands are proposed by two independent DWPose keypoint groups and refined by
 * two independent refiner runs ([Candidate01FrameAnalyzer.runHand]); nothing compares them. If both groups land
 * on the same physical hand, both can pass `observed`, which draws two skeletons on one hand. Whether that
 * actually happens, and how often, is a measurement question, so this records it:
 *  - both slots observed AND the two skeletons coincide (IoU ~ 1, centroids together)  -> the duplicate case,
 *  - both slots observed AND the skeletons are separate (IoU ~ 0)                      -> two real hands.
 *
 * The three overlap bins are descriptive labels for a log line, NOT a decision rule and not a tuned threshold.
 * Only numbers are logged (no landmarks, no frames).
 */
internal object HandPairDiagnostics {
    data class Overlap(
        /** Intersection-over-union of the axis-aligned boxes around each hand's valid landmarks, 0..1. */
        val iou: Double,
        /** Distance between the two landmark centroids divided by the mean box side. ~0 = same hand. */
        val centroidDistanceOverSize: Double,
    )

    private const val MIN_VALID_POINTS = 3

    private class Box(val minX: Double, val minY: Double, val maxX: Double, val maxY: Double, val cx: Double, val cy: Double) {
        val width get() = maxX - minX
        val height get() = maxY - minY
    }

    private fun box(xy: FloatArray, valid: BooleanArray): Box? {
        var n = 0
        var minX = Double.MAX_VALUE; var minY = Double.MAX_VALUE
        var maxX = -Double.MAX_VALUE; var maxY = -Double.MAX_VALUE
        var sx = 0.0; var sy = 0.0
        for (i in valid.indices) {
            if (!valid[i]) continue
            val x = xy[i * 2].toDouble()
            val y = xy[i * 2 + 1].toDouble()
            if (!x.isFinite() || !y.isFinite()) continue
            n++
            minX = min(minX, x); maxX = max(maxX, x)
            minY = min(minY, y); maxY = max(maxY, y)
            sx += x; sy += y
        }
        return if (n < MIN_VALID_POINTS) null else Box(minX, minY, maxX, maxY, sx / n, sy / n)
    }

    /** Null when either hand has fewer than 3 usable points or a degenerate (zero-area) box. */
    fun overlap(aXy: FloatArray, aValid: BooleanArray, bXy: FloatArray, bValid: BooleanArray): Overlap? {
        val a = box(aXy, aValid) ?: return null
        val b = box(bXy, bValid) ?: return null
        val areaA = a.width * a.height
        val areaB = b.width * b.height
        if (areaA <= 0.0 || areaB <= 0.0) return null
        val iw = max(0.0, min(a.maxX, b.maxX) - max(a.minX, b.minX))
        val ih = max(0.0, min(a.maxY, b.maxY) - max(a.minY, b.minY))
        val inter = iw * ih
        val union = areaA + areaB - inter
        val size = (max(a.width, a.height) + max(b.width, b.height)) / 2.0
        if (union <= 0.0 || size <= 0.0) return null
        return Overlap(inter / union, hypot(a.cx - b.cx, a.cy - b.cy) / size)
    }

    /** IoU of the two DWPose-derived hand ROIs (squares), i.e. BEFORE the refiner. Null if either ROI is missing. */
    fun roiIou(a: PerceptionVNextMath.HandRoi?, b: PerceptionVNextMath.HandRoi?): Double? {
        if (a == null || b == null) return null
        val iw = max(0.0, (min(a.right, b.right) - max(a.left, b.left)).toDouble())
        val ih = max(0.0, (min(a.bottom, b.bottom) - max(a.top, b.top)).toDouble())
        val inter = iw * ih
        val union = a.side.toDouble() * a.side + b.side.toDouble() * b.side - inter
        return if (union <= 0.0) null else inter / union
    }
}

/** Per-frame context for a both-hands-observed frame. [roiIou] is the PRE-refinement ROI overlap; NaN values are excluded from means. */
internal data class HandPairSample(
    val roiIou: Double?,
    val presenceLeft: Float, val presenceRight: Float,
    /** Refiner handedness output per slot (raw; its meaning relative to the slot is exactly what the investigation checks). */
    val handednessLeft: Float, val handednessRight: Float,
    /** Mean DWPose support over the 21 points of each group. */
    val supportLeft: Float, val supportRight: Float,
)

internal data class HandPairMeans(
    val presenceLeft: Double?, val presenceRight: Double?,
    val handednessLeft: Double?, val handednessRight: Double?,
    val supportLeft: Double?, val supportRight: Double?,
)


internal data class HandPairSnapshot(
    val frames: Long,
    val noHand: Long,
    val leftOnly: Long,
    val rightOnly: Long,
    val bothObserved: Long,
    /** Both observed, skeleton boxes overlap with IoU >= 0.5: the duplicate-on-one-hand signature. */
    val bothHighOverlap: Long,
    /** Both observed, 0.1 <= IoU < 0.5. */
    val bothPartialOverlap: Long,
    /** Both observed, IoU < 0.1: two separate hands. */
    val bothSeparate: Long,
    val bothOverlapUnknown: Long,
    /** Among high-overlap frames: the two DWPose ROIs ALREADY coincided (IoU >= 0.5) => DWPose proposed the same hand twice. */
    val highRoiSame: Long,
    /** Among high-overlap frames: the ROIs were different (IoU < 0.5) yet both refined skeletons ended on one hand => refiner snapping. */
    val highRoiDifferent: Long,
    val highMeans: HandPairMeans,
) {
    fun toLogFragment(): String {
        fun f(v: Double?) = if (v == null) "na" else String.format(java.util.Locale.ROOT, "%.2f", v)
        return "hands[n=$frames none=$noHand L=$leftOnly R=$rightOnly both=$bothObserved " +
            "same=$bothHighOverlap part=$bothPartialOverlap sep=$bothSeparate na=$bothOverlapUnknown " +
            "same.roi=$highRoiSame/$highRoiDifferent " +
            "same.pres=${f(highMeans.presenceLeft)}/${f(highMeans.presenceRight)} " +
            "same.hand=${f(highMeans.handednessLeft)}/${f(highMeans.handednessRight)} " +
            "same.sup=${f(highMeans.supportLeft)}/${f(highMeans.supportRight)}]"
    }
}

/** Cumulative counters, one `record` per processed frame (a few field increments; no allocation). */
internal class HandPairCounters {
    private class Mean {
        var sum = 0.0
        var n = 0L
        fun add(v: Float) { if (v.isFinite()) { sum += v; n++ } }
        fun value(): Double? = if (n == 0L) null else sum / n
    }

    private var frames = 0L
    private var noHand = 0L
    private var leftOnly = 0L
    private var rightOnly = 0L
    private var both = 0L
    private var high = 0L
    private var partial = 0L
    private var separate = 0L
    private var unknown = 0L
    private var highRoiSame = 0L
    private var highRoiDifferent = 0L
    private val presL = Mean(); private val presR = Mean()
    private val handL = Mean(); private val handR = Mean()
    private val supL = Mean(); private val supR = Mean()

    @Synchronized
    fun record(leftObserved: Boolean, rightObserved: Boolean, overlap: HandPairDiagnostics.Overlap?, sample: HandPairSample?) {
        frames++
        when {
            !leftObserved && !rightObserved -> noHand++
            leftObserved && !rightObserved -> leftOnly++
            !leftObserved -> rightOnly++
            else -> {
                both++
                when {
                    overlap == null -> unknown++
                    overlap.iou >= 0.5 -> {
                        high++
                        if (sample != null) {
                            when {
                                sample.roiIou == null -> Unit
                                sample.roiIou >= 0.5 -> highRoiSame++
                                else -> highRoiDifferent++
                            }
                            presL.add(sample.presenceLeft); presR.add(sample.presenceRight)
                            handL.add(sample.handednessLeft); handR.add(sample.handednessRight)
                            supL.add(sample.supportLeft); supR.add(sample.supportRight)
                        }
                    }
                    overlap.iou >= 0.1 -> partial++
                    else -> separate++
                }
            }
        }
    }

    @Synchronized
    fun snapshot() = HandPairSnapshot(
        frames, noHand, leftOnly, rightOnly, both, high, partial, separate, unknown, highRoiSame, highRoiDifferent,
        HandPairMeans(presL.value(), presR.value(), handL.value(), handR.value(), supL.value(), supR.value()),
    )
}
