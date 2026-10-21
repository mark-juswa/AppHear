package com.example.apphear.sentenceassist

import com.example.apphear.BuildConfig

/** Phase 2 mode. SHADOW computes and logs renderings; nothing is shown or spoken. */
enum class SentenceAssistMode { OFF, SHADOW;
    companion object {
        val current: SentenceAssistMode get() = valueOf(BuildConfig.SENTENCE_ASSIST_MODE)
    }
}

/** Values from `assets/sentence_assist/policy_v1.json`; substitution limits reuse Context Assist's policy. */
data class SentenceAssistPolicy(
    val lexiconAsset: String,
    val substitutionPolicyAsset: String,
    val debounceMs: Long,
    val renderTimeoutMs: Long,
    val maxGlosses: Int,
    val maxOutputChars: Int,
    val maxInferredPronouns: Int,
) {
    init {
        require(lexiconAsset.isNotBlank() && substitutionPolicyAsset.isNotBlank())
        require(debounceMs >= 0 && renderTimeoutMs > 0)
        require(maxGlosses > 0 && maxOutputChars > 0 && maxInferredPronouns >= 0)
    }

    companion object {
        const val ASSET = "sentence_assist/policy_v1.json"
        const val SCHEMA_VERSION = 1
    }
}
