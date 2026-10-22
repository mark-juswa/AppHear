package com.example.apphear.llm

import android.os.SystemClock
import com.example.apphear.BuildConfig

/**
 * `llmFallback` (debug only): a second, independent LLM that backs up Gemini for the sentence
 * builder and Context Assist. Active only with the flag on and a key in the gitignored
 * `android/gradle.properties` (`APPHEAR_FALLBACK_LLM_API_KEY`); release builds have neither.
 */
object LlmFallback {
    /** Start the backup if Gemini has not answered by then (or fails sooner). */
    const val HEDGE_AFTER_MS = 2_500L

    const val PRIMARY_SOURCE = "gemini"
    const val SECONDARY_SOURCE = "fallback"

    val enabled: Boolean
        get() = BuildConfig.LLM_FALLBACK_ENABLED && BuildConfig.LLM_FALLBACK_API_KEY.isNotBlank()

    /** Null when the fallback is off. */
    fun client(): OpenAiCompatibleClient? = if (!enabled) null else OpenAiCompatibleClient(
        baseUrl = BuildConfig.LLM_FALLBACK_BASE_URL,
        model = BuildConfig.LLM_FALLBACK_MODEL,
        apiKey = BuildConfig.LLM_FALLBACK_API_KEY,
        reasoningEffort = BuildConfig.LLM_FALLBACK_REASONING_EFFORT,
    )

    val hedge: HedgedCall by lazy { HedgedCall(HEDGE_AFTER_MS, SystemClock::elapsedRealtime) }
}
