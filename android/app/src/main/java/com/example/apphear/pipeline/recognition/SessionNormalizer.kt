package com.example.apphear.pipeline.recognition

import com.example.apphear.pipeline.features.CausalConfig
import com.example.apphear.pipeline.features.MirrorStabilizer
import com.example.apphear.pipeline.features.NormalizeConfig
import com.example.apphear.pipeline.features.Topology.LEFT_WRIST
import com.example.apphear.pipeline.features.Topology.RIGHT_WRIST
import com.example.apphear.pipeline.features.buildFeatureVector
import com.example.apphear.pipeline.features.clipScale
import com.example.apphear.pipeline.features.mirrorHandsFrame
import com.example.apphear.pipeline.features.mirrorPoseFrame
import com.example.apphear.pipeline.features.shoulderAngle
import com.example.apphear.pipeline.features.torsoCenter
import com.example.apphear.pipeline.features.transformFrame
import kotlin.math.hypot

/** Manual handedness setting; AUTO defers to the session auto-detect. */
enum class Handedness { AUTO, RIGHT, LEFT }

/**
 * SESSION-level S4. scale/roll/mirror are USER properties (F18b finding), so they are estimated
 * across the whole session rather than per sign: scale/roll = running median over a bounded rolling
 * window of pose frames (body size + camera tilt are stable); mirror = session-persistent
 * MirrorStabilizer (handedness auto-detect + lock), overridable by a manual [Handedness] setting.
 * This nearly erases the per-clip left-dominant penalty measured in F18b.
 *
 * The per-frame TRANSFORM reuses the SAME helpers the causal skew test proved byte-exact; only the
 * estimation WINDOW differs (session vs per-clip), so the math parity holds.
 */
class SessionNormalizer(
    private val cfg: NormalizeConfig = NormalizeConfig(),
    ccfg: CausalConfig = CausalConfig(),
    private val windowFrames: Int = 256,
) {
    private val window = ArrayDeque<FloatArray>()
    private val stabilizer =
        MirrorStabilizer(ccfg.mirrorDecisiveMargin, ccfg.mirrorMinAbsDiff, ccfg.mirrorConfirmK)
    private var cumL = 0.0
    private var cumR = 0.0
    private var prevL: DoubleArray? = null
    private var prevR: DoubleArray? = null
    private var autoMirror = false

    // Default RIGHT (no mirror) — the canonical/majority case, matching the offline data. AUTO is
    // available but NOT the default: on-device the auto-detect could lock to the WRONG handedness
    // mid-session (it did on the first device test — froze mirrored=true and broke recognition),
    // and there's no manual escape hatch until the F21 handedness toggle. Right-handed users get
    // correct no-mirror features; left-handed support arrives with the F21 setting.
    var handedness: Handedness = Handedness.RIGHT

    val isMirrored: Boolean
        get() = when (handedness) {
            Handedness.LEFT -> true
            Handedness.RIGHT -> false
            Handedness.AUTO -> autoMirror
        }

    /** Feed the current pose frame; updates the session estimators. Call once per frame. */
    fun update(poseFrame: FloatArray) {
        window.addLast(poseFrame)
        while (window.size > windowFrames) window.removeFirst()

        if (cfg.n3Handedness) {
            val l = doubleArrayOf(
                poseFrame[LEFT_WRIST * 4].toDouble(), poseFrame[LEFT_WRIST * 4 + 1].toDouble(),
            )
            val r = doubleArrayOf(
                poseFrame[RIGHT_WRIST * 4].toDouble(), poseFrame[RIGHT_WRIST * 4 + 1].toDouble(),
            )
            val pl = prevL
            val pr = prevR
            if (pl != null && pr != null) {
                val dl = hypot(l[0] - pl[0], l[1] - pl[1])
                val dr = hypot(r[0] - pr[0], r[1] - pr[1])
                if (dl.isFinite()) cumL += dl
                if (dr.isFinite()) cumR += dr
            }
            prevL = l
            prevR = r
            autoMirror = stabilizer.update(cumL, cumR)
        }
    }

    /**
     * 258 feature for the CURRENT frame using the session params. [poseFrame]/[handsFrame] must be
     * the same frame just passed to [update] (it is the window's last row).
     */
    fun feature(poseFrame: FloatArray, handsFrame: FloatArray): FloatArray {
        val win = window.toTypedArray()
        val doCenter = cfg.n1Scale || cfg.n2Roll || cfg.n3Handedness
        val s = if (cfg.n1Scale) clipScale(win) else 1.0
        val theta = if (cfg.n2Roll) shoulderAngle(win) else 0.0
        val center = if (doCenter) torsoCenter(win) else arrayOf(doubleArrayOf(0.0, 0.0))
        val cx = center[center.size - 1][0]
        val cy = center[center.size - 1][1]
        val poseF = transformFrame(poseFrame, 33, 4, cx, cy, s, theta, doCenter, cfg.n1Scale, cfg.n2Roll)
        val handsF = transformFrame(handsFrame, 42, 3, cx, cy, s, theta, doCenter, cfg.n1Scale, cfg.n2Roll)
        if (isMirrored) {
            mirrorPoseFrame(poseF)
            mirrorHandsFrame(handsF)
        }
        return buildFeatureVector(handsF, poseF)
    }

    /** New session (camera restart): forget handedness + estimators. */
    fun reset() {
        window.clear()
        cumL = 0.0
        cumR = 0.0
        prevL = null
        prevR = null
        autoMirror = false
    }
}
