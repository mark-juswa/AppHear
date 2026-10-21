package com.example.apphear.sentenceassist

import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Debug-only Gemini transport, same endpoint and credential as Context Assist's provider. Every
 * failure (no key, HTTP error, timeout, malformed JSON) returns null so the caller falls back;
 * the [GroundingValidator] remains the only authority on whether a sentence is usable.
 */
class GeminiSentenceRenderer(
    private val apiKey: String,
    private val template: PromptTemplate,
    private val prompt: SentencePrompt,
    private val timeoutMs: Long,
) : SentenceRenderer {
    override suspend fun render(request: RenderRequest): Rendering? {
        if (apiKey.isBlank()) return null
        return try {
            withContext(Dispatchers.IO) { requestRendering(request) }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Log.w(TAG, "[sentenceassist/gemini] rendering unavailable: ${error.javaClass.simpleName}")
            null
        }
    }

    private fun requestRendering(request: RenderRequest): Rendering? {
        val connection = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = minOf(timeoutMs, CONNECT_TIMEOUT_CAP_MS).toInt()
            readTimeout = timeoutMs.toInt()
            doOutput = true
            setRequestProperty("x-goog-api-key", apiKey)
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            val body = JSONObject().put("model", template.model).put("store", false)
                .put("system_instruction", template.systemInstruction)
                .put("input", prompt.input(request))
                .put("response_format", JSONObject().put("type", "text")
                    .put("mime_type", "application/json").put("schema", JSONObject(template.responseSchemaJson)))
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            if (connection.responseCode !in 200..299) return null
            val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            return parse(response)
        } finally {
            connection.disconnect()
        }
    }

    private fun parse(response: JSONObject): Rendering? {
        if (response.optString("status") != "completed") return null
        val steps = response.optJSONArray("steps") ?: return null
        for (index in 0 until steps.length()) {
            val step = steps.optJSONObject(index) ?: continue
            if (step.optString("type") != "model_output") continue
            val content = step.optJSONArray("content") ?: continue
            for (itemIndex in 0 until content.length()) {
                val item = content.optJSONObject(itemIndex) ?: continue
                if (item.optString("type") != "text") continue
                val output = JSONObject(item.getString("text"))
                val raw = output.optJSONArray("substitutions")?.let { array ->
                    (0 until array.length()).map { i ->
                        val entry = array.optJSONObject(i)
                        RenderingMapper.RawSubstitution(
                            entry?.takeIf { it.has("signNumber") }?.optInt("signNumber"),
                            entry?.optString("gloss")?.takeIf { it.isNotEmpty() },
                        )
                    }
                }
                return RenderingMapper.map(output.optString("sentence").takeIf { output.has("sentence") }, raw)
            }
        }
        return null
    }

    private companion object {
        const val TAG = "AppHearSentenceAssist"
        const val ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
        const val CONNECT_TIMEOUT_CAP_MS = 5_000L
    }
}
