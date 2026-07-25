package com.example.apphear.pipeline

/**
 * Runtime ablation modes for device profiling. These modes are measurement-only: they let a
 * developer isolate S0/S1/S2/S6 costs without changing the model artifact or feature contract.
 */
enum class ProfilingMode {
    CAMERA_ONLY,
    HAND_ONLY,
    POSE_ONLY,
    HAND_AND_POSE,
    FULL_RECOGNITION,
}

