package com.example.apphear.pipeline.recognition

import android.content.Context
import com.example.apphear.pipeline.RuntimeLog
import com.example.apphear.pipeline.features.Topology.LEFT_ELBOW
import com.example.apphear.pipeline.features.Topology.LEFT_HIP
import com.example.apphear.pipeline.features.Topology.LEFT_SHOULDER
import com.example.apphear.pipeline.features.Topology.LEFT_WRIST
import com.example.apphear.pipeline.features.Topology.RIGHT_ELBOW
import com.example.apphear.pipeline.features.Topology.RIGHT_HIP
import com.example.apphear.pipeline.features.Topology.RIGHT_SHOULDER
import com.example.apphear.pipeline.features.Topology.RIGHT_WRIST
import org.json.JSONObject
import kotlin.math.hypot
import kotlin.math.max

/** S5 thresholds - mirror of pipeline/config/detect.yaml (tuned on val). */
data class SigningConfig(
    val thetaOn: Double,
    val thetaOff: Double,
    val kOn: Int,
    val kOff: Int,
    val raiseMargin: Double,
    val smoothingWindow: Int,
    val handAuxWeight: Double,
    val requireHands: Boolean,
) {
    companion object {
        fun load(context: Context): SigningConfig {
            val o = JSONObject(
                context.assets.open("recognition_config.json").bufferedReader().use { it.readText() },
            ).getJSONObject("signing")
            return SigningConfig(
                thetaOn = o.getDouble("theta_on"),
                thetaOff = o.getDouble("theta_off"),
                kOn = o.getInt("k_on"),
                kOff = o.getInt("k_off"),
                raiseMargin = o.getDouble("raise_margin"),
                smoothingWindow = o.getInt("smoothing_window"),
                handAuxWeight = o.getDouble("hand_aux_weight"),
                requireHands = o.optBoolean("require_hands", true),
            )
        }
    }
}

enum class SigningEvent { NONE, ONSET, RELEASE }

data class SigningDiagnostics(
    val frame: Long,
    val firstHandFrame: Long?,
    val firstMotionFrame: Long?,
    val firstCandidateFrame: Long?,
    val onsetFrame: Long?,
    val framesMotionToOnset: Long?,
    val framesCandidateToOnset: Long?,
    val activeHandGapFrames: Int,
    val releaseCausedByHandDropout: Boolean,
    val motion: Double,
    val handsSeen: Boolean,
    val raisedGate: Boolean,
    val onsetCandidate: Boolean,
    val onsetGapUsed: Boolean,
    val onsetGapBridgedThisFrame: Boolean,
    val onCount: Int,
    val offCount: Int,
)

/**
 * S5 - streaming signing detector. It remains a gate, not a feature-contract surface. Normal-FPS
 * behavior is unchanged unless low_fps_s5.enabled is set in recognition_config.json.
 */
class SigningDetector(
    private val cfg: SigningConfig,
    private val runtime: RuntimeConfig = RuntimeConfig.defaults(),
    private val allowOneShortOnsetGap: Boolean = false,
) {
    private var signing = false
    private var onCount = 0
    private var offCount = 0
    private var prevPose: FloatArray? = null
    private var prevHands: FloatArray? = null
    private val motionRing = DoubleArray(max(cfg.smoothingWindow, runtime.lowFpsSmoothingWindow).coerceAtLeast(1))
    private var ringFilled = 0
    private var ringPos = 0
    private var lastScale = 1.0
    private var frame = -1L
    private var firstHandFrame: Long? = null
    private var firstMotionFrame: Long? = null
    private var firstCandidateFrame: Long? = null
    private var onsetFrame: Long? = null
    private var activeHandGapFrames = 0
    private var onsetGapUsed = false

    var lastDiagnostics = SigningDiagnostics(
        0, null, null, null, null, null, null, 0, false, 0.0, false, false, false,
        false, false, 0, 0,
    )
        private set

    val isSigning: Boolean get() = signing

    fun update(pose: FloatArray, hands: FloatArray, lowFps: Boolean = false): SigningEvent {
        frame++
        val sw = shoulderWidth(pose)
        val scale = if (sw.isFinite() && sw > 0.0) { lastScale = sw; sw } else lastScale

        val raw = frameMotion(prevPose, prevHands, pose, hands, scale)
        motionRing[ringPos] = raw
        ringPos = (ringPos + 1) % motionRing.size
        if (ringFilled < motionRing.size) ringFilled++
        val smoothN = effectiveSmoothing(lowFps).coerceAtMost(ringFilled).coerceAtLeast(1)
        var sum = 0.0
        for (i in 0 until smoothN) {
            val idx = (ringPos - 1 - i + motionRing.size) % motionRing.size
            sum += motionRing[idx]
        }
        val motion = sum / smoothN
        val gate = raisedGate(pose, scale)
        val handsSeen = !cfg.requireHands || LandmarkAdapter.handsPresent(hands)
        if (handsSeen && firstHandFrame == null) {
            firstHandFrame = frame
            RuntimeLog.i(TAG, "S5 first_hand_frame=$frame")
        }
        if (!signing && motion < cfg.thetaOff) firstMotionFrame = null
        if (!signing && !handsSeen) firstHandFrame = null
        if (motion > cfg.thetaOn && firstMotionFrame == null) {
            firstMotionFrame = frame
            RuntimeLog.i(TAG, "S5 first_motion_frame=$frame motion=%.3f".format(motion))
        }
        val onsetCandidate = motion > cfg.thetaOn && gate && handsSeen
        val bridgeOnsetGap = !signing &&
            allowOneShortOnsetGap &&
            onCount > 0 &&
            !onsetGapUsed &&
            !onsetCandidate &&
            handsSeen &&
            gate &&
            motion >= cfg.thetaOff
        if (!signing && !onsetCandidate && !bridgeOnsetGap) {
            firstCandidateFrame = null
        }
        if (!signing && onsetCandidate && firstCandidateFrame == null) {
            firstCandidateFrame = frame
            RuntimeLog.i(
                TAG,
                "S5 first_candidate_frame=$frame first_hand=$firstHandFrame first_motion=$firstMotionFrame motion=%.3f"
                    .format(motion),
            )
        }

        prevPose = pose
        prevHands = hands

        var releaseByDropout = false
        val event = if (!signing) {
            if (onsetCandidate) {
                onCount++
                if (onCount >= effectiveKOn(lowFps)) {
                    signing = true
                    onsetFrame = frame
                    activeHandGapFrames = 0
                    onsetGapUsed = false
                    onCount = 0
                    offCount = 0
                    val motionDelay = firstMotionFrame?.let { frame - it }
                    val candidateDelay = firstCandidateFrame?.let { frame - it }
                    RuntimeLog.i(
                        TAG,
                        "S5 ONSET_DIAG frame=$frame first_hand=$firstHandFrame first_motion=$firstMotionFrame " +
                            "first_candidate=$firstCandidateFrame frames_motion_to_onset=$motionDelay " +
                            "frames_candidate_to_onset=$candidateDelay low_fps=$lowFps motion=%.3f".format(motion),
                    )
                    SigningEvent.ONSET
                } else {
                    SigningEvent.NONE
                }
            } else if (bridgeOnsetGap) {
                onsetGapUsed = true
                SigningEvent.NONE
            } else {
                onCount = 0
                onsetGapUsed = false
                SigningEvent.NONE
            }
        } else {
            if (!handsSeen) activeHandGapFrames++
            if (motion < cfg.thetaOff || !handsSeen) {
                if (!handsSeen) releaseByDropout = true
                offCount++
                if (offCount >= effectiveKOff(lowFps)) {
                    signing = false
                    onCount = 0
                    offCount = 0
                    RuntimeLog.i(
                        TAG,
                        "S5 RELEASE_DIAG frame=$frame cause=${if (releaseByDropout) "hand_dropout" else "motion"} " +
                            "active_hand_gap_frames=$activeHandGapFrames low_fps=$lowFps motion=%.3f".format(motion),
                    )
                    SigningEvent.RELEASE
                } else {
                    SigningEvent.NONE
                }
            } else {
                offCount = 0
                SigningEvent.NONE
            }
        }

        lastDiagnostics = SigningDiagnostics(
            frame = frame,
            firstHandFrame = firstHandFrame,
            firstMotionFrame = firstMotionFrame,
            firstCandidateFrame = firstCandidateFrame,
            onsetFrame = onsetFrame,
            framesMotionToOnset = onsetFrame?.let { on -> firstMotionFrame?.let { on - it } },
            framesCandidateToOnset = onsetFrame?.let { on -> firstCandidateFrame?.let { on - it } },
            activeHandGapFrames = activeHandGapFrames,
            releaseCausedByHandDropout = releaseByDropout,
            motion = motion,
            handsSeen = handsSeen,
            raisedGate = gate,
            onsetCandidate = onsetCandidate,
            onsetGapUsed = onsetGapUsed,
            onsetGapBridgedThisFrame = bridgeOnsetGap,
            onCount = onCount,
            offCount = offCount,
        )
        if (event == SigningEvent.RELEASE) resetBoutDiagnostics()
        return event
    }

    fun reset() {
        signing = false
        onCount = 0
        offCount = 0
        prevPose = null
        prevHands = null
        ringFilled = 0
        ringPos = 0
        onsetGapUsed = false
        resetBoutDiagnostics()
    }

    private fun resetBoutDiagnostics() {
        firstHandFrame = null
        firstMotionFrame = null
        firstCandidateFrame = null
        onsetFrame = null
        activeHandGapFrames = 0
    }

    private fun effectiveKOn(lowFps: Boolean): Int =
        if (lowFps && runtime.enableLowFpsS5Tuning) runtime.lowFpsKOn else cfg.kOn

    private fun effectiveKOff(lowFps: Boolean): Int =
        if (lowFps && runtime.enableLowFpsS5Tuning) runtime.lowFpsKOff else cfg.kOff

    private fun effectiveSmoothing(lowFps: Boolean): Int =
        if (lowFps && runtime.enableLowFpsS5Tuning) runtime.lowFpsSmoothingWindow else cfg.smoothingWindow

    private fun shoulderWidth(pose: FloatArray): Double {
        val lx = pose[LEFT_SHOULDER * 4]; val ly = pose[LEFT_SHOULDER * 4 + 1]
        val rx = pose[RIGHT_SHOULDER * 4]; val ry = pose[RIGHT_SHOULDER * 4 + 1]
        if (lx.isNaN() || ly.isNaN() || rx.isNaN() || ry.isNaN()) return Double.NaN
        return hypot((lx - rx).toDouble(), (ly - ry).toDouble())
    }

    private fun frameMotion(
        prevPose: FloatArray?, prevHands: FloatArray?, pose: FloatArray, hands: FloatArray, scale: Double,
    ): Double {
        if (prevPose == null || scale <= 0.0) return 0.0
        val poseIdx = intArrayOf(LEFT_WRIST, RIGHT_WRIST, LEFT_ELBOW, RIGHT_ELBOW)
        val poseMotion = meanDisplacement(prevPose, pose, poseIdx, 4)
        var motion = poseMotion
        if (prevHands != null) {
            val handWrists = intArrayOf(0, 21)
            val handMotion = meanDisplacement(prevHands, hands, handWrists, 3)
            if (handMotion.isFinite()) motion += cfg.handAuxWeight * handMotion
        }
        return if (motion.isFinite()) motion / scale else 0.0
    }

    private fun meanDisplacement(prev: FloatArray, cur: FloatArray, idx: IntArray, stride: Int): Double {
        var sum = 0.0
        var n = 0
        for (k in idx) {
            val dx = (cur[k * stride] - prev[k * stride]).toDouble()
            val dy = (cur[k * stride + 1] - prev[k * stride + 1]).toDouble()
            val d = hypot(dx, dy)
            if (d.isFinite()) { sum += d; n++ }
        }
        return if (n > 0) sum / n else 0.0
    }

    private fun raisedGate(pose: FloatArray, scale: Double): Boolean {
        val lhy = pose[LEFT_HIP * 4 + 1]
        val rhy = pose[RIGHT_HIP * 4 + 1]
        val hipY = when {
            !lhy.isNaN() && !rhy.isNaN() -> (lhy + rhy) / 2.0
            !lhy.isNaN() -> lhy.toDouble()
            !rhy.isNaN() -> rhy.toDouble()
            else -> return true
        }
        val threshold = hipY - cfg.raiseMargin * scale
        val lwy = pose[LEFT_WRIST * 4 + 1]
        val rwy = pose[RIGHT_WRIST * 4 + 1]
        return (!lwy.isNaN() && lwy < threshold) || (!rwy.isNaN() && rwy < threshold)
    }

    private companion object {
        const val TAG = "AppHearS5"
    }
}





