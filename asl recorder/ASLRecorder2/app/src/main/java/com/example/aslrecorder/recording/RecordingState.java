package com.example.aslrecorder.recording;

public enum RecordingState {
    /**
     * Camera is idle. Waiting for user to tap START.
     */
    IDLE,

    /**
     * Camera is active, landmark overlay visible, signer should position themselves.
     * Countdown will not start until tracking is stable.
     */
    PREPARE,

    /**
     * Counting down 3 → 2 → 1 → SIGN!
     */
    COUNTDOWN,

    /**
     * Capturing 30 landmark frames. LandmarkFrameBuffer is collecting.
     */
    RECORDING,

    /**
     * 30 frames collected. SampleQualityAnalyzer is running checks.
     */
    ANALYZING,

    /**
     * Sample passed all quality checks. Being saved to accepted folder.
     */
    ACCEPTED,

    /**
     * Sample failed a quality check. Being saved to rejected folder.
     */
    REJECTED,

    /**
     * Brief rest period (1 second) between samples. Signer lowers hands.
     */
    REST,

    /**
     * Transitioning to the next sample. Decides whether to loop or complete.
     */
    NEXT_SAMPLE,

    /**
     * Session target reached. All samples collected.
     */
    COMPLETE,

    /**
     * User tapped PAUSE. Recording halted after current REST period.
     */
    PAUSED
}
