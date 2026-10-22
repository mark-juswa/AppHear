package com.example.apphear.contextassist

import android.util.Log
import com.example.apphear.llm.HedgedCall
import com.example.apphear.llm.LlmFallback
import com.example.apphear.llm.OpenAiCompatibleClient

/** Gemini's exact prompt and schema, sent to the `llmFallback` model; [ReplyCandidateValidator] still filters. */
class OpenAiCompatibleContextPredictionProvider(
    private val client: OpenAiCompatibleClient,
    private val timeoutMs: Long = DEFAULT_TIMEOUT_MS,
) : ContextPredictionProvider {
    override suspend fun predict(request: PredictionRequest): List<ReplyCandidate> {
        val text = client.completeJson(GeminiContextPredictionProvider.SYSTEM_INSTRUCTION,
            GeminiContextPredictionProvider.prompt(request), SCHEMA_NAME,
            GeminiContextPredictionProvider.schema(), timeoutMs) ?: return emptyList()
        return GeminiContextPredictionProvider.parseCandidates(text)
    }

    private companion object {
        const val SCHEMA_NAME = "apphear_reply_candidates"
        const val DEFAULT_TIMEOUT_MS = 7_000L
    }
}

/**
 * Gemini first; the fallback joins after the hedge delay or a Gemini failure, and the first
 * non-empty candidate list wins. Logs which model answered. Without a fallback it is Gemini alone.
 */
class HedgedContextPredictionProvider(
    private val primary: ContextPredictionProvider,
    private val secondary: ContextPredictionProvider?,
    private val hedge: HedgedCall,
) : ContextPredictionProvider {
    override suspend fun predict(request: PredictionRequest): List<ReplyCandidate> {
        val answer = hedge.run(
            HedgedCall.Attempt(LlmFallback.PRIMARY_SOURCE) { primary.predict(request).takeIf { it.isNotEmpty() } },
            secondary?.let { backup ->
                HedgedCall.Attempt(LlmFallback.SECONDARY_SOURCE) { backup.predict(request).takeIf { it.isNotEmpty() } }
            },
        )
        Log.i(TAG, "prediction_source=${answer?.source ?: "none"} latency_ms=${answer?.latencyMs}")
        return answer?.value.orEmpty()
    }

    private companion object {
        const val TAG = "AppHearPhraseAssist"
    }
}
