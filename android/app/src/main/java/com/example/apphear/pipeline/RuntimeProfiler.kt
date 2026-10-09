package com.example.apphear.pipeline

import android.util.Log
import kotlin.math.max

data class RuntimeTiming(
    val convNs: Long = 0L,
    val rotateNs: Long = 0L,
    val handNs: Long = 0L,
    val poseNs: Long = 0L,
    val recogNs: Long = 0L,
    val wallNs: Long = 0L,
    val interFrameNs: Long = 0L,
)

/**
 * Rolling profiler for real-device ablations. Reports mean + p50/p95 so slow-tail behavior is visible
 * instead of hidden behind an average. Enabled by `FeatureFlags.PROFILE_STAGES` or any non-full mode.
 */
class RuntimeProfiler(
    private val mode: ProfilingMode,
    private val deviceSummary: String,
    private val window: Int = 30,
) {
    private val conv = ArrayList<Long>(window)
    private val rotate = ArrayList<Long>(window)
    private val hand = ArrayList<Long>(window)
    private val pose = ArrayList<Long>(window)
    private val recog = ArrayList<Long>(window)
    private val wall = ArrayList<Long>(window)
    private val interFrame = ArrayList<Long>(window)
    private var announced = false

    fun record(
        timing: RuntimeTiming,
        cameraFps: Double,
        processedFps: Double,
        processedFrames: Long,
        droppedFrames: Long,
        lowFps: Boolean,
        poseEveryN: Int,
    ) {
        if (!announced) {
            announced = true
            Log.i(TAG, "profile_start mode=$mode $deviceSummary")
        }
        conv.add(timing.convNs)
        rotate.add(timing.rotateNs)
        hand.add(timing.handNs)
        pose.add(timing.poseNs)
        recog.add(timing.recogNs)
        wall.add(timing.wallNs)
        if (timing.interFrameNs > 0L) interFrame.add(timing.interFrameNs)
        if (wall.size < window) return

        Log.i(
            TAG,
            ("mode=$mode frames=$processedFrames dropped=$droppedFrames camera_fps=%.1f " +
                "processed_fps=%.1f low_fps=$lowFps pose_every=$poseEveryN " +
                "conv_ms=${stats(conv)} rotate_ms=${stats(rotate)} hand_ms=${stats(hand)} " +
                "pose_ms=${stats(pose)} recog_ms=${stats(recog)} wall_ms=${stats(wall)} " +
                "gap_ms=${stats(interFrame)}")
                .format(cameraFps, processedFps),
        )
        conv.clear()
        rotate.clear()
        hand.clear()
        pose.clear()
        recog.clear()
        wall.clear()
        interFrame.clear()
    }

    private fun stats(values: List<Long>): String {
        val sorted = values.sorted()
        val mean = values.sum().toDouble() / max(values.size, 1) / NS_PER_MS
        val p50 = sorted[((sorted.size - 1) * 0.50).toInt()] / NS_PER_MS
        val p95 = sorted[((sorted.size - 1) * 0.95).toInt()] / NS_PER_MS
        return "%.1f/%.1f/%.1f".format(mean, p50, p95)
    }

    private companion object {
        const val TAG = "AppHearPerf"
        const val NS_PER_MS = 1_000_000.0
    }
}


