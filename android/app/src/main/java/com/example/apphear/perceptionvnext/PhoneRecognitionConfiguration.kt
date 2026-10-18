package com.example.apphear.perceptionvnext

import com.example.apphear.BuildConfig

/**
 * Live recognition configuration for the normal ASL Recognition screen. STABLE is the production
 * reference and the only configuration a release build can resolve. EXPERIMENTAL (debug builds
 * only) swaps the S2 package for the research Arm A e10 debug package and turns on the
 * confirm-boundary split; Candidate01, the materializer, the frozen WORD recognizer and
 * SentenceBuilder are shared and unchanged. EXPERIMENTAL_WORD_BLEND is EXPERIMENTAL with only the
 * WORD stage swapped for the debug WORD_BLEND_01 package; for side-by-side evidence it also runs
 * the frozen recognizer on the identical view and logs it (never shown or committed).
 * EXPERIMENTAL_WORD_BLEND_02 is the same with WORD_BLEND_02 (reviewed Sem-Lex package 02 added); its
 * logged comparison recognizer is WORD_BLEND_01, so a session compares 02 against 01 directly.
 */
internal enum class PhoneRecognitionConfiguration(
    val label: String,
    private val confirmBoundaryPostPeak: Double?,
) {
    STABLE("Stable - S2-R2", null),
    EXPERIMENTAL("Experimental - Arm A e10 + confirm-boundary", 0.7),
    EXPERIMENTAL_WORD_BLEND("Experimental + WORD Blend 01", 0.7),
    EXPERIMENTAL_WORD_BLEND_02("Experimental + WORD Blend 02", 0.7);

    fun s2Package(): PhoneS2Package = when (this) {
        STABLE -> PhoneS2Package.valueOf(BuildConfig.APP_PHONE_S2_PACKAGE)
        EXPERIMENTAL, EXPERIMENTAL_WORD_BLEND, EXPERIMENTAL_WORD_BLEND_02 -> PhoneS2Package.ARM_A_E10_CANDIDATE
    }

    fun decoderConfig() = PhoneDecoderConfig(
        rearmPolicy = PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL,
        admissionPolicy = PhoneSignAdmissionPolicy.PASS_THROUGH,
        confirmBoundaryPostPeak = confirmBoundaryPostPeak,
    )

    /** The recognizer whose top-1 is displayed and committed. */
    fun wordPackage(): RecognizerPackageSpec = when (this) {
        STABLE, EXPERIMENTAL -> RecognitionV2LiveRecognizer.FROZEN_GATE2
        EXPERIMENTAL_WORD_BLEND -> WORD_BLEND_01
        EXPERIMENTAL_WORD_BLEND_02 -> WORD_BLEND_02
    }

    /** Debug comparison only: classifies the identical view, logged, never displayed or committed. */
    fun pairedWordPackage(): RecognizerPackageSpec? = when (this) {
        STABLE, EXPERIMENTAL -> null
        EXPERIMENTAL_WORD_BLEND -> RecognitionV2LiveRecognizer.FROZEN_GATE2
        EXPERIMENTAL_WORD_BLEND_02 -> WORD_BLEND_01
    }

    companion object {
        /** 0.5 frozen + 0.5 mean of three Sem-Lex-ENRICH runs; assets in the debug source set only. */
        val WORD_BLEND_01 = RecognizerPackageSpec(
            packageId = "WORD_BLEND_01",
            manifestAsset = "word_blend_candidate_01/manifest.json",
            manifestSha256 = "a76d01e078a08454dc0dac2444a34d0ce1a89b07ce0c7850b99efa332339c651",
            modelSha256 = "bc8a6c91659eb0c12d3e4a486d6583e4ed7053abff9c7f72611138700e4ea4f1",
        )

        /** WORD_BLEND_01 rule with reviewed Sem-Lex package 02 in its members; debug assets only. */
        val WORD_BLEND_02 = RecognizerPackageSpec(
            packageId = "WORD_BLEND_02",
            manifestAsset = "word_blend_candidate_02/manifest.json",
            manifestSha256 = "ae9f8914733f808096b0d437b9e55806d7463aafb583771211f71af9c743188c",
            modelSha256 = "40533bc38c2c416ae2f48e4955029dbdd11d16325765df7aea66db278aaafb30",
        )

        /** Unknown, stale or non-debug choices resolve to STABLE. */
        fun resolve(saved: String?, experimentalAvailable: Boolean): PhoneRecognitionConfiguration =
            if (!experimentalAvailable) STABLE
            else entries.firstOrNull { it != STABLE && it.name == saved } ?: STABLE
    }
}
