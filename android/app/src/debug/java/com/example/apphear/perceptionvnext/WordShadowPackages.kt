package com.example.apphear.perceptionvnext

/**
 * Debug-only WORD recognizer candidates for shadow evaluation. A shadow recognizer classifies the
 * same materialized window and Recognition V2 view as the primary (frozen Gate-2) recognizer; only
 * its prediction is logged. The displayed word, decoder, S2 and SentenceBuilder never see it.
 * Assets live in the debug source set (word_v2_candidate/), so release builds cannot load them.
 */
internal object WordShadowPackages {
    val WORD_V2_CANDIDATE = RecognizerPackageSpec(
        packageId = "WORD_V2_CANDIDATE",
        manifestAsset = "word_v2_candidate/manifest.json",
        manifestSha256 = "2d4fd4ecc04e91dda7903d70d314300dbb4fec4b5dc313ac3e73dfbdc31bc7da",
        modelSha256 = "1de85b3cb063be8ed25fb95fe1e71ea8e784f63679fc0a987e4895797956d9df",
    )

    fun byName(name: String?): RecognizerPackageSpec? = when (name?.trim()?.uppercase()) {
        null, "", "NONE" -> null
        WORD_V2_CANDIDATE.packageId -> WORD_V2_CANDIDATE
        else -> throw IllegalArgumentException("WORD_SHADOW_UNKNOWN_PACKAGE: $name")
    }
}
