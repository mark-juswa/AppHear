package com.example.apphear.demo

import android.util.Log
import com.example.apphear.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Question-based demo: when the on-device matcher is unsure, asks Gemini (same endpoint and key as
 * Context Assist) which listed question was asked. It may only pick one of the listed ids or "none",
 * so it can never invent an answer; any failure returns null and the on-device result is used.
 */
object GeminiQuestionPicker {
    private const val TAG = "AppHearDemo"
    private const val ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
    private const val MODEL = "gemini-3.5-flash-lite"
    private const val TIMEOUT_MS = 4_000

    val available: Boolean get() = BuildConfig.CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY.isNotBlank()

    /** The id of the question [spoken] asks, "none", or null when the helper could not answer. */
    suspend fun pick(spoken: String, topic: DemoTopic): String? {
        if (!available) return null
        return try {
            withContext(Dispatchers.IO) { request(spoken, topic) }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Log.w(TAG, "[demo/gemini] question match unavailable: ${error.javaClass.simpleName}")
            null
        }
    }

    private fun request(spoken: String, topic: DemoTopic): String? {
        val ids = topic.questions.map { it.id } + "none"
        val list = topic.questions.joinToString("\n") { q -> "${q.id}: ${q.phrasings.joinToString(" / ")}" }
        val instruction = "You match a question someone said aloud (speech recognition, may be imperfect, " +
            "English or Filipino) to one question from a fixed list about ${topic.title}. Answer with the id of " +
            "the listed question that asks the same thing, or \"none\" if none does. Never answer the question."
        val input = "Listed questions:\n$list\n\nSaid aloud: \"${spoken.take(300)}\""
        val schema = JSONObject().put("type", "object")
            .put("properties", JSONObject().put("id", JSONObject().put("type", "string").put("enum", JSONArray(ids))))
            .put("required", JSONArray().put("id"))
        val connection = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = TIMEOUT_MS
            readTimeout = TIMEOUT_MS
            doOutput = true
            setRequestProperty("x-goog-api-key", BuildConfig.CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY)
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            val body = JSONObject().put("model", MODEL).put("store", false)
                .put("system_instruction", instruction).put("input", input)
                .put("response_format", JSONObject().put("type", "text").put("mime_type", "application/json").put("schema", schema))
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            if (connection.responseCode !in 200..299) return null
            val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            val steps = response.optJSONArray("steps") ?: return null
            for (i in 0 until steps.length()) {
                val step = steps.optJSONObject(i)?.takeIf { it.optString("type") == "model_output" } ?: continue
                val content = step.optJSONArray("content") ?: continue
                for (j in 0 until content.length()) {
                    val item = content.optJSONObject(j)?.takeIf { it.optString("type") == "text" } ?: continue
                    return JSONObject(item.getString("text")).optString("id").takeIf { it in ids }
                }
            }
            return null
        } finally {
            connection.disconnect()
        }
    }
}
