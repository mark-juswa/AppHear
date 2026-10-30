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
 * EXPERIMENTAL_WORD_MIRROR_BLEND is the same with WORD_MIRROR_BLEND (BLEND_02 rule, members trained
 * with left/right mirroring); its logged comparison recognizer is WORD_BLEND_02, the engine it would
 * replace, and selecting EXPERIMENTAL_WORD_BLEND_02 again is the rollback.
 * EXPERIMENTAL_WORD_V4 is the same with the Recognition V4 WORD candidate (V4_WORD_MEAN2: mean of
 * two masked-transformer members, identical I/O and vocabulary); its logged comparison recognizer
 * is WORD_BLEND_02, and it falls back to WORD_BLEND_02 if its model file is absent.
 * EXPERIMENTAL_WORD_V4_HYBRID is EXPERIMENTAL_WORD_V4 plus the V4 continuous hybrid: the lexical model
 * C2 runs on every observation and its sign markers split events that hold two signs and add signs no
 * event covers; WORD V4 names every segment (LexicalV4Hybrid.kt). No paired recognizer (CPU budget);
 * it falls back to EXPERIMENTAL_WORD_V4 if the lexical package is absent.
 */
internal enum class PhoneRecognitionConfiguration(
    val label: String,
    private val confirmBoundaryPostPeak: Double?,
) {
    STABLE("Stable - S2-R2", null),
    EXPERIMENTAL("Experimental - Arm A e10 + confirm-boundary", 0.7),
    EXPERIMENTAL_WORD_BLEND("Experimental + WORD Blend 01", 0.7),
    EXPERIMENTAL_WORD_BLEND_02("Experimental + WORD Blend 02", 0.7),
    EXPERIMENTAL_WORD_MIRROR_BLEND("Experimental + WORD Mirror Blend", 0.7),
    EXPERIMENTAL_WORD_V4("Experimental + WORD V4", 0.7),
    EXPERIMENTAL_WORD_V4_HYBRID("Experimental + WORD V4 + continuous hybrid", 0.7);

    fun s2Package(): PhoneS2Package = when (this) {
        STABLE -> PhoneS2Package.valueOf(BuildConfig.APP_PHONE_S2_PACKAGE)
        EXPERIMENTAL, EXPERIMENTAL_WORD_BLEND, EXPERIMENTAL_WORD_BLEND_02, EXPERIMENTAL_WORD_MIRROR_BLEND,
        EXPERIMENTAL_WORD_V4, EXPERIMENTAL_WORD_V4_HYBRID -> PhoneS2Package.ARM_A_E10_CANDIDATE
    }

    /** The continuous-hybrid lexical package, or null for every engine without the hybrid. */
    fun lexicalPackage(): LexicalPackageSpec? = when (this) {
        EXPERIMENTAL_WORD_V4_HYBRID -> LEXICAL_C2
        else -> null
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
        EXPERIMENTAL_WORD_MIRROR_BLEND -> WORD_MIRROR_BLEND
        EXPERIMENTAL_WORD_V4, EXPERIMENTAL_WORD_V4_HYBRID -> WORD_V4
    }

    /** Debug comparison only: classifies the identical view, logged, never displayed or committed. */
    fun pairedWordPackage(): RecognizerPackageSpec? = when (this) {
        STABLE, EXPERIMENTAL, EXPERIMENTAL_WORD_V4_HYBRID -> null
        EXPERIMENTAL_WORD_BLEND -> RecognitionV2LiveRecognizer.FROZEN_GATE2
        EXPERIMENTAL_WORD_BLEND_02 -> WORD_BLEND_01
        EXPERIMENTAL_WORD_MIRROR_BLEND, EXPERIMENTAL_WORD_V4 -> WORD_BLEND_02
    }

    /**
     * Where to go if this configuration cannot load, before the last-resort STABLE fallback. Only
     * WORD_MIRROR_BLEND and WORD_V4 have one: their model files may be absent from a checkout (kept
     * out of the public repository), and the closest behaviour is the engine they would replace,
     * WORD_BLEND_02, which shares their S2 package and decoder. Every other configuration keeps the
     * original STABLE fallback.
     */
    fun wordFallback(): PhoneRecognitionConfiguration? = when (this) {
        EXPERIMENTAL_WORD_MIRROR_BLEND, EXPERIMENTAL_WORD_V4 -> EXPERIMENTAL_WORD_BLEND_02
        EXPERIMENTAL_WORD_V4_HYBRID -> EXPERIMENTAL_WORD_V4
        else -> null
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

        /**
         * WORD_BLEND_02 rule with members trained under left/right mirroring (p = 0.5; pre-registered,
         * docs/audit/WORD_ROOT_CAUSE_2026-10-22.md); same I/O, vocabulary and cost. Debug assets only.
         */
        val WORD_MIRROR_BLEND = RecognizerPackageSpec(
            packageId = "WORD_MIRROR_BLEND",
            manifestAsset = "word_mirror_blend_candidate_01/manifest.json",
            manifestSha256 = "7192f398a1ec342bad644587a0ffb6f4b1007618ed6a1246960e9146d95cdcec",
            modelSha256 = "8f854bf0f4a1224b6db74855bb5f15109034798d0c40a47282ecf6ce7bf3c43d",
        )

        /**
         * Recognition V4 WORD candidate V4_WORD_MEAN2 (branch v4/recognition,
         * context/recognition_v4/M2_WORD_RESULT.md): same Recognition V2 [96,350] + mask input, 236
         * outputs and vocabulary as WORD_BLEND_02; host parity 20/20 fixtures, DEV 816/816. Its manifest
         * also declares a 32-row model (same weights, identical outputs for windows of <= 32
         * observations: 54,465/54,465 host views) that the recognizer prefers. Debug only.
         */
        val WORD_V4 = RecognizerPackageSpec(
            packageId = "WORD_V4",
            manifestAsset = "word_v4_candidate_01/manifest.json",
            manifestSha256 = "67dce96e1ff096109ec4388a7dfcca1f871b23f195f5932dfba296cb08018b0a",
            modelSha256 = "3e4d79c0ee2b371679a015d835322daf4ef3ec78c7824d718d286c75bef77cd4",
        )

        /**
         * V4 M3 continuous-hybrid lexical model C2 (branch v4/recognition,
         * context/recognition_v4/M3_CONTINUOUS_RESULT.md): 24-row FP32 TFLite, host parity exact on 406
         * DEV streams; causal hybrid on DEV 62.6% natural / 39.2% continuous vs 57.3% / 29.6%. Debug only.
         */
        val LEXICAL_C2 = LexicalPackageSpec(
            packageId = "LEXICAL_C2",
            manifestAsset = "lexical_v4_candidate_01/manifest.json",
            manifestSha256 = "0baad62d1501948bb00fe2f05eb1b8e65762d25edf674616e30ecb5dec4ce75d",
            modelSha256 = "66135ea85b74bac6511b13633b4b1a749306a8a88dc3c19effa20f1f3dca1f91",
        )

        /** Unknown, stale or non-debug choices resolve to STABLE. */
        fun resolve(saved: String?, experimentalAvailable: Boolean): PhoneRecognitionConfiguration =
            if (!experimentalAvailable) STABLE
            else entries.firstOrNull { it != STABLE && it.name == saved } ?: STABLE
    }
}
