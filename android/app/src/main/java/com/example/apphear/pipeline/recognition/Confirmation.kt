package com.example.apphear.pipeline.recognition

import com.example.apphear.pipeline.RuntimeLog
import java.util.Arrays
import kotlin.math.exp
import kotlin.math.ln

/** A committed sign: the class id and the frame (since onset) it committed on. */
data class Commit(val classId: Int, val frame: Int, val evidence: Double, val margin: Double)

data class ConfirmationSnapshot(
    val top1: Int = -1,
    val evidence: Double = Double.NEGATIVE_INFINITY,
    val margin: Double = 0.0,
    val streak: Int = 0,
    val committed: Boolean = false,
    val reason: String = "no_frames",
)

/**
 * S7 confirmation - cumulative-mean calibrated log-posterior with margin + stability gates. Normal
 * behavior is unchanged unless low_fps_confirmation.enabled is set in recognition_config.json.
 */
class Confirmation(
    private val cfg: RecognitionConfig,
    numClasses: Int,
) {
    private val sum = DoubleArray(numClasses)
    private var count = 0
    private var prevTop1 = -1
    private var streak = 0
    private var committed = false

    var topCandidates: IntArray = IntArray(0)
        private set

    var lastSnapshot: ConfirmationSnapshot = ConfirmationSnapshot()
        private set

    /** Feed the current per-frame softmax posterior. Returns a Commit the frame it fires, else null. */
    fun update(probs: FloatArray, lowFps: Boolean = false): Commit? {
        if (committed) return null
        count++
        val temp = cfg.temperature
        val n = probs.size
        val logits = DoubleArray(n)
        var maxLogit = Double.NEGATIVE_INFINITY
        for (c in 0 until n) {
            val lg = ln(maxOf(probs[c].toDouble(), 1e-8)) / temp
            logits[c] = lg
            if (lg > maxLogit) maxLogit = lg
        }
        var sumExp = 0.0
        for (c in 0 until n) sumExp += exp(logits[c] - maxLogit)
        val lse = maxLogit + ln(sumExp)

        var top1 = 0
        var top2 = -1
        var top3 = -1
        var a1 = Double.NEGATIVE_INFINITY
        var a2 = Double.NEGATIVE_INFINITY
        var a3 = Double.NEGATIVE_INFINITY
        for (c in 0 until n) {
            sum[c] += logits[c] - lse
            val a = sum[c] / count
            if (a > a1) {
                a3 = a2; top3 = top2
                a2 = a1; top2 = top1
                a1 = a; top1 = c
            } else if (a > a2) {
                a3 = a2; top3 = top2
                a2 = a; top2 = c
            } else if (a > a3) {
                a3 = a; top3 = c
            }
        }
        topCandidates = intArrayOf(top1, top2, top3).filter { it >= 0 }.toIntArray()

        streak = if (top1 == prevTop1) streak + 1 else 1
        prevTop1 = top1

        val lowFpsConfirmation = lowFps && cfg.enableLowFpsConfirmation
        val theta = if (lowFpsConfirmation) cfg.lowFpsThetaConf else cfg.thetaConf
        val marginNeed = if (lowFpsConfirmation) cfg.lowFpsThetaMargin else cfg.thetaMargin
        val kNeed = if (lowFpsConfirmation) cfg.lowFpsKStability else cfg.kStability
        val minCommitFrame = if (lowFpsConfirmation) cfg.lowFpsMinCommitFrame else 0
        val commitFrame = count - 1
        val margin = a1 - a2
        val reason = when {
            a1 < theta -> "evidence %.3f < theta %.3f".format(a1, theta)
            margin < marginNeed -> "margin %.3f < need %.3f".format(margin, marginNeed)
            streak < kNeed -> "streak $streak < need $kNeed"
            commitFrame < minCommitFrame -> "frame $commitFrame < min_commit_frame $minCommitFrame"
            else -> "commit"
        }
        val shouldCommit = reason == "commit"
        lastSnapshot = ConfirmationSnapshot(top1, a1, margin, streak, shouldCommit, reason)
        if (!shouldCommit) return null

        committed = true
        RuntimeLog.i(
            TAG,
            ("S7 COMMIT_DIAG class=$top1 frame=$commitFrame evidence=%.3f margin=%.3f streak=$streak " +
                "low_fps=$lowFps low_fps_mode=$lowFpsConfirmation min_commit_frame=$minCommitFrame")
                .format(a1, margin),
        )
        return Commit(top1, commitFrame, a1, margin)
    }

    fun reset() {
        Arrays.fill(sum, 0.0)
        count = 0
        prevTop1 = -1
        streak = 0
        committed = false
        topCandidates = IntArray(0)
        lastSnapshot = ConfirmationSnapshot()
    }

    private companion object {
        const val TAG = "AppHearS7"
    }
}


