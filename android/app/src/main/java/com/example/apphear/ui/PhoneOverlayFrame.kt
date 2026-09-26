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
)
