package com.example.apphear.pipeline.recognition

import com.example.apphear.pipeline.ProfilingMode

/**
 * Runtime feature flags (eval-protocol: every runtime change ships behind a flag with a fallback).
 * RECOGNITION_ENABLED off -> the app is F17 (camera + landmark preview + fps) with no model.
 */
object FeatureFlags {
    const val RECOGNITION_ENABLED = true

    /**
     * Try the MediaPipe GPU delegate for the S1/S2 landmarkers, falling back to CPU if the device
     * can't init it. Purpose: lift on-device fps on weak phones (the dominant accuracy lever at low
     * fps). NOTE: GPU landmarks differ sub-pixel from the CPU landmarks the training features were
     * extracted with - a small, deliberate parity divergence justified by the fps win. Flip to false
     * to restore byte-parity CPU landmarking.
     */
    const val LANDMARKER_TRY_GPU = true

    /**
     * Log per-stage timing (hand/pose/bitmap/recog ms + wall fps) from FrameAnalyzer every 30
     * frames (tag AppHearPerf). Off by default - no log spam in normal use.
     */
    const val PROFILE_STAGES = true

    /**
     * Device profiling ablation. Keep FULL_RECOGNITION for normal app behavior. For profiling runs,
     * rebuild with CAMERA_ONLY, HAND_ONLY, POSE_ONLY, or HAND_AND_POSE and compare AppHearPerf logs.
     */
    val PROFILING_MODE: ProfilingMode = ProfilingMode.FULL_RECOGNITION
}
