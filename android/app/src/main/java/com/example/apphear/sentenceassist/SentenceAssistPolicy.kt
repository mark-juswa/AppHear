package com.example.apphear.sentenceassist

import com.example.apphear.BuildConfig

/**
 * Phase 2 mode. SHADOW computes and logs renderings only. VISIBLE turns RECOGNIZED into the
 * sentence builder (grounded AI sentence, or the plain words), and Hear speaks the accepted one.
 */
enum class SentenceAssistMode { OFF, SHADOW, VISIBLE;
    companion object {
        val current: SentenceAssistMode get() = valueOf(BuildConfig.SENTENCE_ASSIST_MODE)
    }
}

/** Values from `assets/sentence_assist/policy_v1.json`; substitution limits reuse Context Assist's policy. */
data class SentenceAssistPolicy(
    val lexiconAsset: String,
    val promptAsset: String,
    val substitutionPolicyAsset: String,
    val debounceMs: Long,
    /** Fewer signs than this are shown in plain form without calling the AI. */
    val minGlossesForAi: Int,
    val renderTimeoutMs: Long,
    val maxGlosses: Int,
    val maxOutputChars: Int,
    val maxInferredPronouns: Int,
) {
    init {
        require(lexiconAsset.isNotBlank() && promptAsset.isNotBlank() && substitutionPolicyAsset.isNotBlank())
        require(debounceMs >= 0 && renderTimeoutMs > 0 && minGlossesForAi >= 1)
        require(maxGlosses > 0 && maxOutputChars > 0 && maxInferredPronouns >= 0)
    }

    companion object {
        const val ASSET = "sentence_assist/policy_v1.json"
        const val SCHEMA_VERSION = 1
    }
}
