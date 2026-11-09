package com.example.apphear.perceptionvnext

import android.util.Log
import java.util.Locale

/**
 * SHADOW-ONLY counterfactual for the DWPose "echo" (one physical hand activating the opposite hand group; see
 * docs/DWPOSE_DUPLICATE_PROPOSAL_VALIDATION.md). It changes NOTHING: it never alters an observation, the overlay, the segmenter or the
 * recognizer input, never removes a candidate, and is OFF unless the debug build flag `-PhandEchoShadow=true` is given.
 *
 * Each frame it records the raw signals the investigation compared and which values of a FIXED EVALUATION GRID of support ratios would
 * have suppressed the weaker group. The grid is not a selected threshold: no value has been justified yet (one subject, no phone), and the
 * choice is deferred to offline analysis of multi-subject logs. The rule evaluated for the mask is:
 *   both groups observed AND their ROIs overlap (IoU >= [MIN_ROI_IOU]) AND (weaker support / stronger support) < grid value
 * where "support" is the mean DWPose SimCC activation of the group's 21 keypoints. Ratio, not absolute support, so it does not depend on
 * lighting or hand distance. Spatial overlap alone is never a decision (it is the weakest signal; touching hands overlap legitimately).
 *
 * Privacy/size: numbers and flags only, no landmark coordinates, no frames; at most [maxLines] lines per analyzer start. Any failure inside
 * is swallowed so a diagnostic can never fault the analyzer.
 */
internal enum class EchoSide { NONE, LEFT, RIGHT }

internal data class EchoGroupInput(
    val proposalPresent: Boolean,
    val observed: Boolean,
    /** Mean over the 21 hand keypoints of the DWPose group's support (min of the x/y SimCC peak activations). */
    val supportMean: Float,
    val pointsGe030: Int,
    val pointsGe010: Int,
    val presence: Float,
    /** Refiner handedness output (value ~ probability of a RIGHT hand on the unmirrored crop); NaN if none. Corroboration only. */
    val handedness: Float,
    val roi: PerceptionVNextMath.HandRoi?,
    /** DWPose hand-wrist keypoint and the same-side DWPose BODY wrist keypoint (source coordinates) with its support. */
    val wristXy: FloatArray,
    val bodyWristXy: FloatArray,
    val bodyWristSupport: Float,
    /** Refined skeleton (read only; used for skeleton overlap, never logged). */
    val refinedXy: FloatArray,
    val refinedValid: BooleanArray,
)

internal data class EchoRecord(
    /** weaker/stronger group support when both are observed, else null. */
    val ratio: Double?,
    val weakerSide: EchoSide,
    val roiIou: Double?,
    val skeletonIou: Double?,
    /** Bit i set = [HandEchoShadow.RATIO_GRID]`[i]` would have suppressed the weaker group. */
    val wouldSuppressMask: Int,
)

internal class HandEchoShadow(
    val enabled: Boolean,
    private val maxLines: Int = 1500,
    private val sink: (String) -> Unit = { Log.i(TAG, it) },
) {
    private var lines = 0

    /** Returns the record when enabled (also logs it, bounded); null when disabled. Never throws. */
    fun observe(sequence: Int, wallMs: Long, left: EchoGroupInput, right: EchoGroupInput): EchoRecord? {
        if (!enabled) return null
        return try {
            val record = evaluate(left, right)
            if (lines < maxLines) {
                lines++
                sink(toJson(sequence, wallMs, left, right, record))
            }
            record
        } catch (_: Throwable) {
            null
        }
    }

    companion object {
        const val TAG = "AppHearEcho"
        const val SCHEMA = "apphear.hand_echo_shadow.v1"
        const val DEFAULT_ENABLED = false
        /** EVALUATION GRID, not a chosen threshold (see class doc). */
        val RATIO_GRID = floatArrayOf(0.3f, 0.4f, 0.5f, 0.6f, 0.7f)
        /** Any meaningful region overlap; below this the two groups are not describing the same place. */
        const val MIN_ROI_IOU = 0.1

        fun evaluate(left: EchoGroupInput, right: EchoGroupInput): EchoRecord {
            val roiIou = HandPairDiagnostics.roiIou(left.roi, right.roi)
            val bothObserved = left.observed && right.observed
            val skeleton = if (bothObserved)
                HandPairDiagnostics.overlap(left.refinedXy, left.refinedValid, right.refinedXy, right.refinedValid)?.iou
            else null
            if (!bothObserved || !left.supportMean.isFinite() || !right.supportMean.isFinite()) {
                return EchoRecord(null, EchoSide.NONE, roiIou, skeleton, 0)
            }
            val leftWeaker = left.supportMean <= right.supportMean
            val weak = if (leftWeaker) left.supportMean else right.supportMean
            val strong = if (leftWeaker) right.supportMean else left.supportMean
            val ratio = if (strong > 0f) (weak / strong).toDouble() else 1.0
            var mask = 0
            if (roiIou != null && roiIou >= MIN_ROI_IOU) {
                for (i in RATIO_GRID.indices) if (ratio < RATIO_GRID[i]) mask = mask or (1 shl i)
            }
            return EchoRecord(ratio, if (leftWeaker) EchoSide.LEFT else EchoSide.RIGHT, roiIou, skeleton, mask)
        }

        private fun num(v: Double?): String = if (v == null || !v.isFinite()) "null" else String.format(Locale.ROOT, "%.4f", v)
        private fun num(v: Float): String = num(if (v.isFinite()) v.toDouble() else null)

        private fun groupJson(g: EchoGroupInput, rightSlot: Boolean): String {
            val slotConsistency = if (g.handedness.isFinite()) (if (rightSlot) g.handedness else 1f - g.handedness) else Float.NaN
            val wristAgreement = g.roi?.takeIf { it.side > 0f && g.wristXy.size >= 2 && g.bodyWristXy.size >= 2 }?.let {
                -kotlin.math.hypot((g.wristXy[0] - g.bodyWristXy[0]).toDouble(), (g.wristXy[1] - g.bodyWristXy[1]).toDouble()) / it.side
            }
            return "{\"observed\":${g.observed},\"proposal\":${g.proposalPresent},\"support\":${num(g.supportMean)},\"pts030\":${g.pointsGe030}," +
                "\"pts010\":${g.pointsGe010},\"presence\":${num(g.presence)},\"handedness\":${num(g.handedness)}," +
                "\"slot_consistency\":${num(slotConsistency)},\"body_wrist_support\":${num(g.bodyWristSupport)}," +
                "\"wrist_agreement\":${num(wristAgreement)},\"roi_side\":${num(g.roi?.side ?: Float.NaN)}}"
        }

        fun toJson(sequence: Int, wallMs: Long, left: EchoGroupInput, right: EchoGroupInput, r: EchoRecord): String =
            "{\"schema\":\"$SCHEMA\",\"seq\":$sequence,\"wall_ms\":$wallMs,\"ratio\":${num(r.ratio)}," +
                "\"weaker\":\"${r.weakerSide.name}\",\"roi_iou\":${num(r.roiIou)},\"skeleton_iou\":${num(r.skeletonIou)}," +
                "\"mask\":${r.wouldSuppressMask},\"grid\":[${RATIO_GRID.joinToString(",") { num(it) }}]," +
                "\"L\":${groupJson(left, false)},\"R\":${groupJson(right, true)}}"
    }
}
