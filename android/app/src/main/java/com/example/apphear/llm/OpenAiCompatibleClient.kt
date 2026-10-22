package com.example.apphear.llm

import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Debug-only transport for any OpenAI-compatible chat-completions service (Groq by default; Hugging
 * Face's router or others by changing [baseUrl] and [model]). Asks for strict JSON-schema output and
 * returns the model's JSON text, or null on any failure. The callers' validators stay the only
 * authority on whether the answer is usable. Blocking: call off the main thread. Never logs the key.
 */
class OpenAiCompatibleClient(
    private val baseUrl: String,
    val model: String,
    private val apiKey: String,
    private val reasoningEffort: String,
) {
    fun completeJson(system: String, user: String, schemaName: String, schema: JSONObject, timeoutMs: Long): String? {
        if (apiKey.isBlank()) return null
        val connection = (URL(baseUrl.trimEnd('/') + "/chat/completions").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = minOf(timeoutMs, CONNECT_TIMEOUT_CAP_MS).toInt()
            readTimeout = timeoutMs.toInt()
            doOutput = true
            setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            val body = JSONObject().put("model", model)
                .put("messages", JSONArray()
                    .put(JSONObject().put("role", "system").put("content", system))
                    .put(JSONObject().put("role", "user").put("content", user)))
                .put("response_format", JSONObject().put("type", "json_schema").put("json_schema",
                    JSONObject().put("name", schemaName).put("strict", true).put("schema", schema)))
                .put("temperature", TEMPERATURE)
                .put("max_completion_tokens", MAX_COMPLETION_TOKENS)
            if (reasoningEffort.isNotBlank()) body.put("reasoning_effort", reasoningEffort)
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            if (code !in 200..299) {
                Log.w(TAG, "[llm/fallback] $model HTTP $code")
                return null
            }
            val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            val choice = response.optJSONArray("choices")?.optJSONObject(0) ?: return null
            // A cut-off answer is not valid JSON for the schema; never repair it.
            if (choice.optString("finish_reason") == "length") return null
            return choice.optJSONObject("message")?.optString("content")?.takeIf { it.isNotBlank() }
        } finally {
            connection.disconnect()
        }
    }

    private companion object {
        const val TAG = "AppHearLlmFallback"
        const val CONNECT_TIMEOUT_CAP_MS = 5_000L
        const val TEMPERATURE = 0.2
        // Reasoning models count their thinking here too; the JSON answers themselves are short.
        const val MAX_COMPLETION_TOKENS = 1_024
    }
}
