package com.example.apphear.pipeline

/**
 * S1/S2 landmarker configuration — a VERBATIM mirror of the offline extraction config
 * (`pipeline/config/extract.yaml` + `pipeline/extract/constants.py`). These values are part of
 * the train/serve parity contract: if the on-device landmarkers don't match how the training
 * features were extracted, the S4 features won't match and the model degrades. Never tune these
 * here in isolation — change both sides together (see context/feature-schema.md).
 */
object LandmarkerConfig {
    // Byte-identical model files copied from repo assets/mediapipe/ (same models used for training).
    const val HAND_TASK = "mediapipe/hand_landmarker.task"
    const val POSE_TASK = "mediapipe/pose_landmarker_lite.task" // LITE — the locked, mobile-realistic choice

    const val NUM_HANDS = 2
    const val MIN_HAND_DETECTION_CONFIDENCE = 0.5f
    const val MIN_HAND_PRESENCE_CONFIDENCE = 0.5f
    const val MIN_HAND_TRACKING_CONFIDENCE = 0.5f

    const val NUM_POSES = 1
    const val MIN_POSE_DETECTION_CONFIDENCE = 0.5f
    const val MIN_POSE_PRESENCE_CONFIDENCE = 0.5f
    const val MIN_POSE_TRACKING_CONFIDENCE = 0.5f

    // Fixed model topology (properties of the MediaPipe models — never configurable).
    const val NUM_POSE_LANDMARKS = 33
    const val NUM_HAND_LANDMARKS = 21

    /**
     * IMAGE mode: stateless per-frame detection, no MediaPipe internal temporal tracking. Matches
     * offline extraction exactly; temporal smoothing is our own explicit S3 stage, not MediaPipe's
     * hidden VIDEO state. (NOTE: IMAGE mode is still continuous real-time — every frame is detected;
     * it just means each frame is detected independently. It is NOT a "snapshot" mode.)
     */
    // Hard floor from context/runtime-constraints.md: below this a 200ms sign spans <3 frames and
    // is physically unresolvable, so the pipeline enters degraded mode rather than emit garbage.
    const val MIN_PIPELINE_FPS = 15.0
}
