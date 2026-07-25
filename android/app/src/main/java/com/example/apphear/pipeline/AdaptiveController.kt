package com.example.apphear.pipeline

/**
 * The performance safety net. Watches sustained pipeline fps and adapts the POSE cadence to keep
 * the app usable on weak devices while letting strong devices run at full quality:
 *
 *  - Hands run EVERY frame (they move fast — subsampling them loses the sign).
 *  - Pose runs every N frames and is held in between (the body moves slowly, so this is cheap and
 *    barely visible). N grows when we're below target fps, shrinks when there's headroom.
 *
 * This is the sanctioned `pose.cadence` lever from context/runtime-constraints.md — cadence
 * (sample rate) is a different axis from PRESENCE; we never drop the pose block itself (v2 lesson
 * b: ablating pose collapsed accuracy 35-83 pts). Hysteresis (a settling gap after each change)
 * prevents oscillation.
 *
 * NOTE (parity, for F18/F19): reducing pose cadence changes the feature stream vs training (which
 * had pose every frame). Harmless for F17 (display only); must be A/B-validated once features feed
 * the model.
 */
class AdaptiveController(
    private val targetFps: Double = LandmarkerConfig.MIN_PIPELINE_FPS,
    private val headroomFps: Double = LandmarkerConfig.MIN_PIPELINE_FPS + 7.0,
    private val settleFrames: Int = 25,
    private val maxPoseEveryN: Int = 4,
) {
    @Volatile
    var poseEveryN: Int = 1
        private set

    private var sinceChange = 0

    @Synchronized
    fun update(fps: Double) {
        sinceChange++
        if (sinceChange < settleFrames) return // let fps stabilize before adapting again
        if (fps < targetFps && poseEveryN < maxPoseEveryN) {
            poseEveryN++
            sinceChange = 0
        } else if (fps > headroomFps && poseEveryN > 1) {
            poseEveryN--
            sinceChange = 0
        }
    }

    fun qualityLabel(): String = when (poseEveryN) {
        1 -> "High"
        2 -> "Balanced"
        3 -> "Low"
        else -> "Minimum"
    }
}
