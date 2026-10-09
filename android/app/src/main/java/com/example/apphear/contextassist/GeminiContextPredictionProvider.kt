package com.example.apphear.contextassist

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Optional debug-only Gemini transport; application validation remains authoritative. */
class GeminiContextPredictionProvider(private val apiKey: String) : ContextPredictionProvider {
    override suspend fun predict(request: PredictionRequest): List<ReplyCandidate> {
        if (apiKey.isBlank()) return emptyList()
        val connection = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 5_000
            readTimeout = 8_000
            doOutput = true
            setRequestProperty("x-goog-api-key", apiKey)
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            val body = requestBody(request)
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            if (connection.responseCode !in 200..299) return emptyList()
            val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            if (response.optString("status") != "completed") return emptyList()
            val steps = response.optJSONArray("steps") ?: return emptyList()
            for (index in 0 until steps.length()) {
                val step = steps.optJSONObject(index) ?: continue
                if (step.optString("type") != "model_output") continue
                val content = step.optJSONArray("content") ?: continue
                for (itemIndex in 0 until content.length()) {
                    val item = content.optJSONObject(itemIndex) ?: continue
                    if (item.optString("type") != "text") continue
                    return parseCandidates(item.getString("text"))
                }
            }
            return emptyList()
        } finally {
            connection.disconnect()
        }
    }

    private fun requestBody(request: PredictionRequest): JSONObject {
        val turns = request.recentTurns.joinToString("\n") { "${it.speaker}: ${it.text}" }
        val prompt = "Recent conversation:\n$turns\n\nAllowed anchor labels: " +
            request.allowedGlosses.sorted().joinToString(",") +
            "\nPredict 3 to 5 meaningfully different plausible " +
            "next Deaf replies to the latest hearing turn. naturalText is a natural English " +
            "conversational hypothesis, not a claim that anything was signed. expectedConcepts " +
            "are ordered recognizer-supported semantic anchors, not English tokenization. " +
            "Use only exact labels from the supplied label list; omit grammatical filler without a supported " +
            "label. For example, 'I'm going home.' can use [GO, HOME], and 'I'm tired.' can use [TIRED]. " +
            "Keep substantive meaning grounded in those anchors or explicitly established conversation " +
            "context; do not add unsupported details. Prefer replies whose core meaning has supported " +
            "anchors. Keep the English natural; the vocabulary constrains anchors, not English grammar."
        return JSONObject().put("model", MODEL).put("store", false)
            .put("system_instruction",
                "You predict conversational reply hypotheses and their observable semantic anchors.")
            .put("input", prompt)
            .put("response_format", JSONObject().put("type", "text")
                .put("mime_type", "application/json").put("schema", schema()))
    }

    private fun parseCandidates(text: String): List<ReplyCandidate> {
        val values = JSONObject(text).getJSONArray("candidates")
        return (0 until minOf(values.length(), 5)).map { index ->
            val value = values.getJSONObject(index)
            // Preserve the provider-independent type and unchanged matcher input.
            val concepts = value.getJSONArray("expectedConcepts")
            ReplyCandidate(value.getString("naturalText"),
                (0 until concepts.length()).map { concepts.getString(it) })
        }
    }

    private fun schema(): JSONObject {
        val candidate = JSONObject().put("type", "object")
            .put("properties", JSONObject()
                .put("naturalText", JSONObject().put("type", "string")
                    .put("description", "Natural conversational hypothesis; grammar may be implicit in anchors."))
                .put("expectedConcepts", JSONObject().put("type", "array")
                    .put("description", "Ordered observable semantic anchors, not English words or proof of signing.")
                    .put("items", JSONObject().put("type", "string"))))
            .put("required", JSONArray(listOf("naturalText", "expectedConcepts")))
            .put("additionalProperties", false)
        return JSONObject().put("type", "object")
            .put("properties", JSONObject().put("candidates", JSONObject().put("type", "array")
                .put("items", candidate)))
            .put("required", JSONArray(listOf("candidates")))
            .put("additionalProperties", false)
    }

    private companion object {
        const val ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
        const val MODEL = "gemini-3.5-flash-lite"
    }
}
