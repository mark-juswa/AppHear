package com.example.apphear.ui

/** Display-only copy of current Candidate01 landmarks; never fed back into inference. */
data class PhoneOverlayFrame(
    val sourceWidth: Int,
    val sourceHeight: Int,
    val handXy: Array<FloatArray>,
    val handValid: Array<BooleanArray>,
    val handObserved: BooleanArray,
    val handPresence: FloatArray,
    val handRoiCenterSide: Array<FloatArray>,
    val bodyXy: FloatArray,
    val bodySupport: FloatArray,
    val bodyValid: BooleanArray,
    /** Latency diagnostics only: analyzer frame number (< 0 = none), camera sensor timestamp and the analyzer's delivery time (elapsedRealtimeNanos). */
    val sequence: Int = -1,
    val sourceTimestampNs: Long = 0L,
    val deliveredNs: Long = 0L,
)
