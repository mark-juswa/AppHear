package com.example.apphear.ui.texttoasl

import android.content.Context
import android.util.Log
import com.example.apphear.domain.texttoasl.AslGrammarRegistry
import com.example.apphear.domain.texttoasl.AslInputAnalysis
import com.example.apphear.domain.texttoasl.ReviewedAslPhrase
import com.example.apphear.domain.texttoasl.SignDictionaryMetadata
import com.example.apphear.domain.texttoasl.AslTextNormalizer
import com.example.apphear.domain.texttoasl.EverydayAslExpression
import org.json.JSONArray
import org.json.JSONObject

/** Small local reviewed-phrase registry; never loads reference datasets into the APK. */
class AndroidAslGrammarLoader(private val context: Context) {
    fun load(): AslGrammarRegistry = try {
        val root = JSONObject(context.assets.open(PATH).bufferedReader().use { it.readText() })
        require(root.getInt("schemaVersion") == 1 && root.getString("language") == "ASL")
        val phrases = mutableListOf<ReviewedAslPhrase>()
        val entries = root.getJSONArray("phrases")
        for (index in 0 until entries.length()) {
            try {
                val entry = entries.getJSONObject(index)
                require(entry.getString("language") == "ASL")
                // Candidate/mapped/playable records belong to the offline review inventory.
                if (entry.getString("status") != "LINGUISTICALLY_VALIDATED") continue
                val review = entry.getJSONObject("review")
                val markerArray = entry.getJSONArray("nonManualMarkers")
                val phrase = ReviewedAslPhrase(
                    id = entry.getString("id"), english = strings(entry.getJSONArray("english")),
                    meaning = entry.getString("meaning"), intent = AslInputAnalysis.Intent.valueOf(entry.getString("intent")),
                    gloss = strings(entry.getJSONArray("gloss")), signIds = strings(entry.getJSONArray("signIds")),
                    status = SignDictionaryMetadata.Status.LINGUISTICALLY_VALIDATED,
                    review = ReviewedAslPhrase.ReviewRecord(review.getString("reviewer"), review.getString("reviewedOn"),
                        strings(review.getJSONArray("sources")), review.getString("license"), review.getString("meaningEvidence"),
                        review.getString("nonManualEvidence"), review.getString("playbackEvidence")),
                    negated = entry.getBoolean("negated"), timeWords = strings(entry.getJSONArray("timeWords")).toSet(),
                    nonManualMarkers = (0 until markerArray.length()).map {
                        val marker = markerArray.getJSONObject(it)
                        ReviewedAslPhrase.NonManualMarker(marker.getString("marker"), marker.getInt("fromSign"), marker.getInt("throughSign"))
                    }, isQuestion = entry.getBoolean("isQuestion"),
                )
                require(phrase.review.isComplete() && phrase.id.matches(Regex("[a-z][a-z0-9_]*")))
                require(phrase.english.isNotEmpty() && phrase.english.all { AslTextNormalizer().normalizeSequence(it).isNotBlank() })
                phrases += phrase
            } catch (error: Exception) {
                Log.w("TextToAslGrammar", "Phrase $index rejected: ${error.message}")
            }
        }
        require(phrases.map { it.id }.distinct().size == phrases.size) { "Duplicate grammar ID" }
        val aliases = phrases.flatMap { phrase -> phrase.english.map { AslTextNormalizer().normalizeSequence(it) to phrase.id } }
        require(aliases.groupBy { it.first }.values.none { forms -> forms.map { it.second }.distinct().size > 1 }) {
            "Ambiguous grammar alias"
        }
        AslGrammarRegistry(root.getBoolean("enabled"), phrases, strings(root.getJSONArray("blockedLiteralExpressions")),
            loadEverydayExpressions())
    } catch (error: Exception) {
        Log.w("TextToAslGrammar", "Grammar unavailable; labeled dictionary previews only", error)
        AslGrammarRegistry(enabled = false, meaningRegistryUnavailable = true)
    }

    private fun loadEverydayExpressions(): List<EverydayAslExpression> {
        val root = JSONObject(context.assets.open(EVERYDAY_PATH).bufferedReader().use { it.readText() })
        require(root.getInt("schemaVersion") == 1 && root.getString("language") == "ASL")
        val entries = root.getJSONArray("expressions")
        val result = (0 until entries.length()).map { index ->
            val entry = entries.getJSONObject(index)
            require(entry.getString("status") == "CANDIDATE")
            // This inventory never supplies glosses, signing order, or synthesized face movements.
            require(entry.getJSONArray("gloss").length() == 0 && entry.getJSONArray("signIds").length() == 0)
            val requirements = entry.getJSONArray("requiredSigns")
            EverydayAslExpression(entry.getString("id"), strings(entry.getJSONArray("english")),
                entry.getString("meaning"), (0 until requirements.length()).map {
                    val requirement = requirements.getJSONObject(it)
                    EverydayAslExpression.RequiredSign(requirement.getString("concept"), strings(requirement.getJSONArray("aliases")))
                }, strings(entry.getJSONArray("references")), entry.getString("nonManualReview"),
                if (entry.isNull("previewSignId")) null else entry.getString("previewSignId"),
                strings(entry.getJSONArray("namePrefixes")))
        }
        EverydayAslExpression.validate(result, AslTextNormalizer())
        return result
    }

    private fun strings(array: JSONArray): List<String> = (0 until array.length()).map { array.getString(it) }
    companion object {
        const val PATH = "asl_animations/grammar_asl.json"
        const val EVERYDAY_PATH = "asl_animations/everyday_asl.json"
    }
}
