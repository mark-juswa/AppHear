package com.example.apphear.pipeline.features

import com.example.apphear.pipeline.features.Topology.LEFT_HIP
import com.example.apphear.pipeline.features.Topology.LEFT_SHOULDER
import com.example.apphear.pipeline.features.Topology.LEFT_WRIST
import com.example.apphear.pipeline.features.Topology.RIGHT_HIP
import com.example.apphear.pipeline.features.Topology.RIGHT_SHOULDER
import com.example.apphear.pipeline.features.Topology.RIGHT_WRIST
import kotlin.math.PI
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

/**
 * S4 — the on-device feature extractor. A direct, deterministic port of the offline stage-F math
 * (`pipeline/normalize/transforms.py`, `scale.py`, `handedness.py`, `features/contract.py`),
 * N4 OFF (streaming/real-timed). This is the #1 train/serve-parity surface: it must reproduce the
 * Python 258-vector byte-for-byte given the same landmarks + span. The `S4SkewTest` golden-vector
 * test is the gate (see context/feature-schema.md).
 *
 * Frame representation (flat, per frame):
 *  - pose:  FloatArray(132), landmark k channel c (x,y,z,visibility) at [k*4 + c]
 *  - hands: FloatArray(126), slot s (0=Left,1=Right) landmark l channel c (x,y,z) at [(s*21+l)*3 + c]
 * Missing landmarks are NaN (never a bare 0). Matches the offline (T,33,4)/(T,2,21,3) row-major layout.
 */

const val FEATURE_DIM = 258
const val HANDS_DIM = 126 // 2*21*3
const val POSE_DIM = 132 // 33*4

/** N1/N2/N3 flags + handedness epsilon — mirrors `pipeline/config/normalize.yaml` (parity-locked). */
data class NormalizeConfig(
    val n1Scale: Boolean = true,
    val n2Roll: Boolean = true,
    val n3Handedness: Boolean = true,
    val handednessEpsilon: Double = 0.15,
)

data class NormParams(
    val scale: Double,
    val rollAngle: Double, // radians
    val dominant: String,
    val mirrored: Boolean,
)

// ---- NaN-aware reductions (numpy nanmedian / nanmean / nansum semantics) -------------------

private fun nanMedian(values: DoubleArray): Double {
    val v = values.filter { !it.isNaN() }.sorted()
    if (v.isEmpty()) return Double.NaN
    val n = v.size
    return if (n % 2 == 1) v[n / 2] else (v[n / 2 - 1] + v[n / 2]) / 2.0
}

/** Mean of two possibly-NaN values, ignoring NaN (both NaN -> NaN). numpy nanmean over a pair. */
private fun nanMean2(a: Float, b: Float): Double {
    val an = !a.isNaN()
    val bn = !b.isNaN()
    return when {
        an && bn -> (a.toDouble() + b.toDouble()) / 2.0
        an -> a.toDouble()
        bn -> b.toDouble()
        else -> Double.NaN
    }
}

// ---- N1 scale (pipeline/normalize/scale.py) ------------------------------------------------

private fun shoulderWidthFrame(pose: FloatArray): Double {
    val lx = pose[LEFT_SHOULDER * 4]; val ly = pose[LEFT_SHOULDER * 4 + 1]
    val rx = pose[RIGHT_SHOULDER * 4]; val ry = pose[RIGHT_SHOULDER * 4 + 1]
    if (lx.isNaN() || ly.isNaN() || rx.isNaN() || ry.isNaN()) return Double.NaN
    return hypot((lx - rx).toDouble(), (ly - ry).toDouble())
}

private fun torsoLengthFrame(pose: FloatArray): Double {
    val ls = doubleArrayOf(pose[LEFT_SHOULDER * 4].toDouble(), pose[LEFT_SHOULDER * 4 + 1].toDouble())
    val rs = doubleArrayOf(pose[RIGHT_SHOULDER * 4].toDouble(), pose[RIGHT_SHOULDER * 4 + 1].toDouble())
    val lh = doubleArrayOf(pose[LEFT_HIP * 4].toDouble(), pose[LEFT_HIP * 4 + 1].toDouble())
    val rh = doubleArrayOf(pose[RIGHT_HIP * 4].toDouble(), pose[RIGHT_HIP * 4 + 1].toDouble())
    if (listOf(ls, rs, lh, rh).any { it[0].isNaN() || it[1].isNaN() }) return Double.NaN
    val sx = (ls[0] + rs[0]) / 2.0; val sy = (ls[1] + rs[1]) / 2.0
    val hx = (lh[0] + rh[0]) / 2.0; val hy = (lh[1] + rh[1]) / 2.0
    return hypot(sx - hx, sy - hy)
}

internal fun clipScale(spanPose: Array<FloatArray>): Double {
    if (spanPose.isEmpty()) return 1.0
    var w = nanMedian(DoubleArray(spanPose.size) { shoulderWidthFrame(spanPose[it]) })
    if (w.isNaN() || w <= 0.0) {
        w = nanMedian(DoubleArray(spanPose.size) { torsoLengthFrame(spanPose[it]) })
    }
    return if (w.isNaN() || w <= 0.0) 1.0 else w
}

// ---- N2 roll (shoulder-line tilt, folded to +/- pi/2) --------------------------------------

internal fun shoulderAngle(spanPose: Array<FloatArray>): Double {
    val dx = DoubleArray(spanPose.size) {
        (spanPose[it][RIGHT_SHOULDER * 4] - spanPose[it][LEFT_SHOULDER * 4]).toDouble()
    }
    val dy = DoubleArray(spanPose.size) {
        (spanPose[it][RIGHT_SHOULDER * 4 + 1] - spanPose[it][LEFT_SHOULDER * 4 + 1]).toDouble()
    }
    val mdx = nanMedian(dx)
    val mdy = nanMedian(dy)
    if (mdx.isNaN() || mdy.isNaN()) return 0.0
    var ang = atan2(mdy, mdx)
    if (ang > PI / 2) ang -= PI else if (ang <= -PI / 2) ang += PI
    return ang
}

// ---- N3 handedness (pipeline/normalize/handedness.py) --------------------------------------

private fun wristMotion(spanPose: Array<FloatArray>, wrist: Int): Double {
    if (spanPose.size < 2) return 0.0
    var total = 0.0
    for (t in 1 until spanPose.size) {
        val dx = (spanPose[t][wrist * 4] - spanPose[t - 1][wrist * 4]).toDouble()
        val dy = (spanPose[t][wrist * 4 + 1] - spanPose[t - 1][wrist * 4 + 1]).toDouble()
        val d = hypot(dx, dy)
        if (!d.isNaN()) total += d // nansum: NaN pairs contribute 0
    }
    return total
}

private fun decideHandedness(spanPose: Array<FloatArray>, epsilon: Double): NormParams {
    val left = wristMotion(spanPose, LEFT_WRIST)
    val right = wristMotion(spanPose, RIGHT_WRIST)
    val total = left + right
    if (total <= 0.0 || kotlin.math.abs(left - right) / total < epsilon) {
        return NormParams(0.0, 0.0, "Right", false) // scale/roll filled by caller
    }
    val dominant = if (left > right) "Left" else "Right"
    return NormParams(0.0, 0.0, dominant, dominant == "Left")
}

// ---- torso center (per-frame shoulder midpoint, span-median fallback) -----------------------

internal fun torsoCenter(pose: Array<FloatArray>): Array<DoubleArray> {
    val t = pose.size
    val cx = DoubleArray(t)
    val cy = DoubleArray(t)
    for (i in 0 until t) {
        cx[i] = nanMean2(pose[i][LEFT_SHOULDER * 4], pose[i][RIGHT_SHOULDER * 4])
        cy[i] = nanMean2(pose[i][LEFT_SHOULDER * 4 + 1], pose[i][RIGHT_SHOULDER * 4 + 1])
    }
    val anyNaN = (0 until t).any { cx[it].isNaN() || cy[it].isNaN() }
    if (anyNaN) {
        var medX = nanMedian(cx); if (medX.isNaN()) medX = 0.0
        var medY = nanMedian(cy); if (medY.isNaN()) medY = 0.0
        for (i in 0 until t) {
            if (cx[i].isNaN() || cy[i].isNaN()) {
                cx[i] = medX; cy[i] = medY
            }
        }
    }
    return Array(t) { doubleArrayOf(cx[it], cy[it]) }
}

// ---- the transform (center -> scale -> roll), matching _transform_block ---------------------

internal fun transformFrame(
    src: FloatArray, nLandmarks: Int, channels: Int, cx: Double, cy: Double, s: Double, theta: Double,
    doCenter: Boolean, doScale: Boolean, doRoll: Boolean,
): FloatArray {
    val out = src.copyOf()
    val c = cos(-theta)
    val sn = sin(-theta)
    for (k in 0 until nLandmarks) {
        val base = k * channels
        var x = out[base].toDouble()
        var y = out[base + 1].toDouble()
        var z = out[base + 2].toDouble()
        if (doCenter) { x -= cx; y -= cy }
        if (doScale && s > 0.0) { x /= s; y /= s; z /= s }
        if (doRoll) { val nx = c * x - sn * y; val ny = sn * x + c * y; x = nx; y = ny }
        out[base] = x.toFloat()
        out[base + 1] = y.toFloat()
        out[base + 2] = z.toFloat()
    }
    return out
}

/**
 * N1-N3 → canonical space. Returns (handsNorm [T][126], poseNorm [T][132], params). `onset < 0`
 * means "use the whole clip". Direct port of `normalize_clip`.
 */
fun normalizeClip(
    handsImage: Array<FloatArray>,
    poseImage: Array<FloatArray>,
    onset: Int,
    release: Int,
    cfg: NormalizeConfig,
): Triple<Array<FloatArray>, Array<FloatArray>, NormParams> {
    val t = poseImage.size
    val on = if (onset < 0) 0 else onset
    val rel = if (onset < 0) t - 1 else release
    val spanPose = poseImage.copyOfRange(on, rel + 1)

    val doCenter = cfg.n1Scale || cfg.n2Roll || cfg.n3Handedness
    val s = if (cfg.n1Scale) clipScale(spanPose) else 1.0
    val theta = if (cfg.n2Roll) shoulderAngle(spanPose) else 0.0
    val hd = if (cfg.n3Handedness) decideHandedness(spanPose, cfg.handednessEpsilon) else null
    val mirrored = hd?.mirrored ?: false
    val center = if (doCenter) torsoCenter(poseImage) else Array(t) { doubleArrayOf(0.0, 0.0) }

    val poseOut = Array(t) { i ->
        transformFrame(poseImage[i], 33, 4, center[i][0], center[i][1], s, theta, doCenter, cfg.n1Scale, cfg.n2Roll)
    }
    val handsOut = Array(t) { i ->
        transformFrame(handsImage[i], 42, 3, center[i][0], center[i][1], s, theta, doCenter, cfg.n1Scale, cfg.n2Roll)
    }

    if (mirrored) {
        for (i in 0 until t) {
            mirrorPoseFrame(poseOut[i])
            mirrorHandsFrame(handsOut[i])
        }
    }

    val params = NormParams(s, theta, hd?.dominant ?: "Right", mirrored)
    return Triple(handsOut, poseOut, params)
}

/** Negate x on every pose landmark, then swap left/right landmark pairs (in place). */
internal fun mirrorPoseFrame(pose: FloatArray) {
    for (k in 0 until 33) pose[k * 4] = -pose[k * 4]
    val src = pose.copyOf()
    val perm = Topology.POSE_MIRROR_PERM
    for (k in 0 until 33) {
        val from = perm[k]
        for (c in 0 until 4) pose[k * 4 + c] = src[from * 4 + c]
    }
}

/** Negate x on every hand landmark, then swap the two hand slots (in place). */
internal fun mirrorHandsFrame(hands: FloatArray) {
    for (m in 0 until 42) hands[m * 3] = -hands[m * 3]
    val src = hands.copyOf()
    for (l in 0 until 21) {
        for (c in 0 until 3) {
            hands[(0 * 21 + l) * 3 + c] = src[(1 * 21 + l) * 3 + c]
            hands[(1 * 21 + l) * 3 + c] = src[(0 * 21 + l) * 3 + c]
        }
    }
}

// ---- feature vector + real-timed composition (features/contract.py) ------------------------

/** (hands 126, pose 132) for one frame -> 258 vector (NaN->0). Port of build_feature_vector. */
fun buildFeatureVector(handsFrame: FloatArray, poseFrame: FloatArray): FloatArray {
    val feat = FloatArray(FEATURE_DIM)
    for (i in 0 until HANDS_DIM) feat[i] = if (handsFrame[i].isNaN()) 0f else handsFrame[i]
    for (i in 0 until POSE_DIM) {
        val v = poseFrame[i]
        feat[HANDS_DIM + i] = if (v.isNaN()) 0f else v
    }
    return feat
}

/**
 * Full S4 (streaming, N4 OFF): normalize -> take the span's real frames -> 258 per frame. Returns
 * the real (unpadded) feature frames; padding to t_max is trivial and done by the caller. Port of
 * `clip_features_realtimed` (minus the zero-padding).
 */
fun clipFeaturesRealtimed(
    handsImage: Array<FloatArray>,
    poseImage: Array<FloatArray>,
    onset: Int,
    release: Int,
    cfg: NormalizeConfig,
): Pair<List<FloatArray>, NormParams> {
    val (handsN, poseN, params) = normalizeClip(handsImage, poseImage, onset, release, cfg)
    val on = if (onset < 0) 0 else onset
    val rel = if (onset < 0) poseN.size - 1 else release
    val frames = ArrayList<FloatArray>(rel - on + 1)
    for (i in on..rel) frames.add(buildFeatureVector(handsN[i], poseN[i]))
    return frames to params
}
