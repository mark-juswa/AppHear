package com.example.apphear.pipeline

import android.util.Log

/**
 * Hysteresis around the low-FPS runtime state. It logs transitions only, so noisy frame-to-frame
 * variation does not spam logcat or flip tuning paths repeatedly.
 */
class LowFpsMonitor(
    private val enterBelowFps: Double,
    private val exitAboveFps: Double,
    private val consecutiveFrames: Int,
) {
    private var lowCount = 0
    private var highCount = 0
    var active: Boolean = false
        private set

    fun update(processedFps: Double): Boolean {
        if (!active) {
            if (processedFps > 0.0 && processedFps < enterBelowFps) lowCount++ else lowCount = 0
            if (lowCount >= consecutiveFrames) {
                active = true
                highCount = 0
                Log.w(TAG, "LOW_FPS_ENTER processed_fps=%.1f threshold=%.1f".format(processedFps, enterBelowFps))
            }
        } else {
            if (processedFps >= exitAboveFps) highCount++ else highCount = 0
            if (highCount >= consecutiveFrames) {
                active = false
                lowCount = 0
                Log.i(TAG, "LOW_FPS_EXIT processed_fps=%.1f threshold=%.1f".format(processedFps, exitAboveFps))
            }
        }
        return active
    }

    private companion object {
        const val TAG = "AppHearLowFps"
    }
}

