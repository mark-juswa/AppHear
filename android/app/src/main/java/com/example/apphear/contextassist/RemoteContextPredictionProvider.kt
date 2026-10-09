package com.example.apphear.contextassist

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Optional debug transport. The deterministic validator remains authoritative. */
class RemoteContextPredictionProvider(private val apiKey: String) : ContextPredictionProvider {
    override suspend fun predict(request: PredictionRequest): List<ReplyCandidate> {
        if (apiKey.isBlank()) return emptyList()
        val connection = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 5_000
            readTimeout = 8_000
            doOutput = true
            setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            val turns = request.recentTurns.joinToString("\n") { "${it.speaker}: ${it.text}" }
            val prompt = "Recent conversation:\n$turns\n\nAllowed signed concepts: " +
                request.allowedGlosses.sorted().joinToString(",") +
                "\nPredict 3 to 5 plausible next Deaf replies. Each concept sequence must use only " +
                "the listed concepts and must represent signs the person would actually produce. " +
                "Natural English may include grammar absent from the concept sequence. " +
                "Do not claim a response was signed; these are predictions only."
            val body = JSONObject()
                .put("model", MODEL)
                .put("store", false)
                .put("input", JSONArray()
                    .put(JSONObject().put("role", "system").put("content",
                        "You predict possible conversational replies for a constrained ASL recognizer."))
                    .put(JSONObject().put("role", "user").put("content", prompt)))
                .put("text", JSONObject().put("format", JSONObject()
                    .put("type", "json_schema")
                    .put("name", "apphear_reply_candidates")
                    .put("strict", true)
                    .put("schema", schema())))
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            if (connection.responseCode !in 200..299) return emptyList()
            val response = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            if (response.optString("status") != "completed") return emptyList()
            val output = response.optJSONArray("output") ?: return emptyList()
            for (index in 0 until output.length()) {
                val content = output.optJSONObject(index)?.optJSONArray("content") ?: continue
                for (itemIndex in 0 until content.length()) {
                    val item = content.optJSONObject(itemIndex) ?: continue
                    if (item.optString("type") != "output_text") continue
                    return parseCandidates(item.getString("text"))
                }
            }
            return emptyList()
        } finally {
            connection.disconnect()
        }
    }

    private fun parseCandidates(text: String): List<ReplyCandidate> {
        val values = JSONObject(text).getJSONArray("candidates")
        return (0 until minOf(values.length(), 5)).map { index ->
            val value = values.getJSONObject(index)
            val concepts = value.getJSONArray("concepts")
            ReplyCandidate(value.getString("naturalText"),
                (0 until concepts.length()).map { concepts.getString(it) })
        }
    }

    private fun schema(): JSONObject {
        val candidate = JSONObject().put("type", "object")
            .put("properties", JSONObject()
                .put("naturalText", JSONObject().put("type", "string"))
                .put("concepts", JSONObject().put("type", "array")
                    .put("items", JSONObject().put("type", "string"))))
            .put("required", JSONArray(listOf("naturalText", "concepts")))
            .put("additionalProperties", false)
        return JSONObject().put("type", "object")
            .put("properties", JSONObject().put("candidates", JSONObject().put("type", "array")
                .put("items", candidate)))
            .put("required", JSONArray(listOf("candidates")))
            .put("additionalProperties", false)
    }

    private companion object {
        const val ENDPOINT = "https://api.openai.com/v1/responses"
        const val MODEL = "gpt-4o-mini"
    }
}
