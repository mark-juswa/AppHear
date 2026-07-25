package com.example.apphear.pipeline.features

import com.example.apphear.pipeline.features.Topology.LEFT_WRIST
import com.example.apphear.pipeline.features.Topology.RIGHT_WRIST
import kotlin.math.hypot

/**
 * Causal (streaming) S4 — the on-device counterpart of the offline `pipeline/normalize/causal.py`.
 * Each frame's scale/roll come from a running median over and the mirror is frozen once
 * left-dominance is decisive. This is the parity target for `CausalSkewTest` (must reproduce Python
 * `clip_features_causal` byte-for-byte). Reuses the SAME internal transform helpers as the full-span
 * S4, so only the estimation WINDOW differs — never the per-frame math.
 *
 * NOTE on deployment (F19b): scale/roll/mirror are USER/session properties, so on-device the
 * estimators persist across signs (handedness auto-detect + lock). This function is the per-clip
 * form used for the skew test; the session wrapper reuses the same MirrorStabilizer + running math.
 */

/** Mirrors `pipeline/config/causal.yaml` (parity-locked). */
data class CausalConfig(
    val mirrorDecisiveMargin: Double = 0.30,
    val mirrorMinAbsDiff: Double = 0.15,
    val mirrorConfirmK: Int = 4,
)

/**
 * Default no-mirror; freeze to MIRROR once left-dominance is decisive — ratio
 * (cumL-cumR)/(cumL+cumR) >= decisiveMargin AND absolute lead (cumL-cumR) >= minAbs (the abs guard
 * rejects early tiny-motion noise) — held for confirmK consecutive frames. Once frozen, never
 * flips. Port of the Python MirrorStabilizer.
 */
class MirrorStabilizer(
    private val decisiveMargin: Double,
    private val minAbs: Double,
    private val confirmK: Int,
) {
    private var frozen = false
    private var streak = 0

    fun update(cumL: Double, cumR: Double): Boolean {
        if (frozen) return true
        val diff = cumL - cumR
        val total = cumL + cumR
        if (total > 0.0 && diff >= minAbs && diff / total >= decisiveMargin) {
            streak++
            if (streak >= confirmK) frozen = true
        } else {
            streak = 0
        }
        return frozen
    }

    val isMirrored: Boolean get() = frozen
}

private fun wristXY(pose: FloatArray, wrist: Int): DoubleArray =
    doubleArrayOf(pose[wrist * 4].toDouble(), pose[wrist * 4 + 1].toDouble())

/**
 * Causal per-frame features over the span. Exact port of `clip_features_causal` /
 * `normalize_clip_causal`. Returns the real (unpadded) 258 feature frames.
 */
fun clipFeaturesCausal(
    handsImage: Array<FloatArray>,
    poseImage: Array<FloatArray>,
    onset: Int,
    release: Int,
    cfg: NormalizeConfig,
    ccfg: CausalConfig,
): List<FloatArray> {
    val t = poseImage.size
    val on = if (onset < 0) 0 else onset
    val rel = if (onset < 0) t - 1 else release
    val spanPose = poseImage.copyOfRange(on, rel + 1)
    val spanHands = handsImage.copyOfRange(on, rel + 1)
    val length = spanPose.size
    val doCenter = cfg.n1Scale || cfg.n2Roll || cfg.n3Handedness
    val stab = MirrorStabilizer(ccfg.mirrorDecisiveMargin, ccfg.mirrorMinAbsDiff, ccfg.mirrorConfirmK)

    var cumL = 0.0
    var cumR = 0.0
    var prevL = wristXY(spanPose[0], LEFT_WRIST)
    var prevR = wristXY(spanPose[0], RIGHT_WRIST)

    val out = ArrayList<FloatArray>(length)
    for (i in 0 until length) {
        val win = spanPose.copyOfRange(0, i + 1) // causal window [0..i]
        val s = if (cfg.n1Scale) clipScale(win) else 1.0
        val theta = if (cfg.n2Roll) shoulderAngle(win) else 0.0

        var mirrored = false
        if (cfg.n3Handedness) {
            if (i > 0) {
                val l = wristXY(spanPose[i], LEFT_WRIST)
                val r = wristXY(spanPose[i], RIGHT_WRIST)
                val dl = hypot(l[0] - prevL[0], l[1] - prevL[1])
                val dr = hypot(r[0] - prevR[0], r[1] - prevR[1])
                if (dl.isFinite()) cumL += dl
                if (dr.isFinite()) cumR += dr
                prevL = l
                prevR = r
            }
            mirrored = stab.update(cumL, cumR)
        }

        val center = if (doCenter) torsoCenter(win) else Array(i + 1) { doubleArrayOf(0.0, 0.0) }
        val cx = center[i][0]
        val cy = center[i][1]
        val poseF = transformFrame(spanPose[i], 33, 4, cx, cy, s, theta, doCenter, cfg.n1Scale, cfg.n2Roll)
        val handsF = transformFrame(spanHands[i], 42, 3, cx, cy, s, theta, doCenter, cfg.n1Scale, cfg.n2Roll)
        if (mirrored) {
            mirrorPoseFrame(poseF)
            mirrorHandsFrame(handsF)
        }
        out.add(buildFeatureVector(handsF, poseF))
    }
    return out
}
