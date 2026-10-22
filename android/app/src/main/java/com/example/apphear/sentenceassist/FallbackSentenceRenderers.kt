package com.example.apphear.sentenceassist

import android.util.Log
import com.example.apphear.llm.HedgedCall
import com.example.apphear.llm.LlmFallback
import com.example.apphear.llm.OpenAiCompatibleClient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** The same prompt and schema as Gemini, sent to the `llmFallback` model. Any failure returns null. */
class OpenAiCompatibleSentenceRenderer(
    private val client: OpenAiCompatibleClient,
    private val template: PromptTemplate,
    private val prompt: SentencePrompt,
    private val timeoutMs: Long,
) : SentenceRenderer {
    override suspend fun render(request: RenderRequest): Rendering? = try {
        withContext(Dispatchers.IO) {
            client.completeJson(template.systemInstruction, prompt.input(request), SCHEMA_NAME,
                JSONObject(template.responseSchemaJson), timeoutMs)?.let(RenderingMapper::fromJson)
        }
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        Log.w(TAG, "[sentenceassist/fallback] rendering unavailable: ${error.javaClass.simpleName}")
        null
    }

    private companion object {
        const val TAG = "AppHearSentenceAssist"
        const val SCHEMA_NAME = "apphear_sentence"
    }
}

/**
 * Gemini first; the fallback model joins after [HedgedCall]'s delay or a Gemini failure, and the
 * first rendering wins. The result is tagged with its source; [GroundingValidator] still decides
 * whether it may be shown. With no fallback configured this is exactly the Gemini renderer.
 */
class HedgedSentenceRenderer(
    private val primary: SentenceRenderer,
    private val secondary: SentenceRenderer?,
    private val hedge: HedgedCall,
) : SentenceRenderer {
    override suspend fun render(request: RenderRequest): Rendering? {
        val answer = hedge.run(
            HedgedCall.Attempt(LlmFallback.PRIMARY_SOURCE) { primary.render(request) },
            secondary?.let { HedgedCall.Attempt(LlmFallback.SECONDARY_SOURCE) { it.render(request) } },
        ) ?: return null
        return answer.value.copy(source = answer.source)
    }
}
