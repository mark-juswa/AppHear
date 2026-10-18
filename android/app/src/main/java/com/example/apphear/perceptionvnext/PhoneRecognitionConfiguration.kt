package com.example.apphear.perceptionvnext

import com.example.apphear.BuildConfig

/**
 * Live recognition configuration for the normal ASL Recognition screen. STABLE is the production
 * reference and the only configuration a release build can resolve. EXPERIMENTAL (debug builds
 * only) swaps the S2 package for the research Arm A e10 debug package and turns on the
 * confirm-boundary split; Candidate01, the materializer, the frozen WORD recognizer and
 * SentenceBuilder are shared and unchanged.
 */
internal enum class PhoneRecognitionConfiguration(
    val label: String,
    private val confirmBoundaryPostPeak: Double?,
) {
    STABLE("Stable - S2-R2", null),
    EXPERIMENTAL("Experimental - Arm A e10 + confirm-boundary", 0.7);

    fun s2Package(): PhoneS2Package = when (this) {
        STABLE -> PhoneS2Package.valueOf(BuildConfig.APP_PHONE_S2_PACKAGE)
        EXPERIMENTAL -> PhoneS2Package.ARM_A_E10_CANDIDATE
    }

    fun decoderConfig() = PhoneDecoderConfig(
        rearmPolicy = PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL,
        admissionPolicy = PhoneSignAdmissionPolicy.PASS_THROUGH,
        confirmBoundaryPostPeak = confirmBoundaryPostPeak,
    )

    companion object {
        /** Unknown, stale or non-debug choices resolve to STABLE. */
        fun resolve(saved: String?, experimentalAvailable: Boolean): PhoneRecognitionConfiguration =
            if (experimentalAvailable && saved == EXPERIMENTAL.name) EXPERIMENTAL else STABLE
    }
}
