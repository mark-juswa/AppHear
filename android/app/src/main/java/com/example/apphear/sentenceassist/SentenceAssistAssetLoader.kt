package com.example.apphear.sentenceassist

import android.content.Context
import com.example.apphear.contextassist.PhraseMatchPolicy
import org.json.JSONArray
import org.json.JSONObject

/**
 * Loads the shipped sentence-assist assets on device. Schema versions are checked so a
 * mismatched asset fails loudly instead of being interpreted; the lexicon must cover exactly the
 * recognizer's label set. Call off the main thread.
 */
class SentenceAssistAssetLoader(private val context: Context) {
    data class Assets(
        val policy: SentenceAssistPolicy,
        val lexicon: GlossLexicon,
        val template: PromptTemplate,
        val substitutionPolicy: PhraseMatchPolicy,
    )

    fun load(): Assets {
        val policyJson = json(SentenceAssistPolicy.ASSET)
        require(policyJson.getInt("schemaVersion") == SentenceAssistPolicy.SCHEMA_VERSION) {
            "[sentenceassist/assets] policy schema mismatch"
        }
        val policy = SentenceAssistPolicy(
            lexiconAsset = policyJson.getString("lexiconAsset"),
            promptAsset = policyJson.getString("promptAsset"),
            substitutionPolicyAsset = policyJson.getString("substitutionPolicyAsset"),
            debounceMs = policyJson.getLong("debounceMs"),
            renderTimeoutMs = policyJson.getLong("renderTimeoutMs"),
            maxGlosses = policyJson.getInt("maxGlosses"),
            maxOutputChars = policyJson.getInt("maxOutputChars"),
            maxInferredPronouns = policyJson.getInt("maxInferredPronouns"),
        )
        val lexiconJson = json(policy.lexiconAsset)
        require(lexiconJson.getInt("schemaVersion") == GlossLexicon.SCHEMA_VERSION) {
            "[sentenceassist/assets] lexicon schema mismatch"
        }
        val glosses = lexiconJson.getJSONObject("glosses")
        val lexicon = GlossLexicon(
            glossForms = glosses.keys().asSequence().associateWith { strings(glosses.getJSONArray(it)) },
            grammarWords = strings(lexiconJson.getJSONArray("grammarWords")),
            inferablePronouns = strings(lexiconJson.getJSONArray("inferablePronouns")),
        )
        val vocabulary = strings(json(lexiconJson.getString("vocabularyAsset")).getJSONArray("class_index_to_gloss"))
        require(lexicon.coversExactly(vocabulary)) { "[sentenceassist/assets] lexicon does not match the recognizer vocabulary" }
        val promptJson = json(policy.promptAsset)
        require(promptJson.getInt("schemaVersion") == PromptTemplate.SCHEMA_VERSION) {
            "[sentenceassist/assets] prompt schema mismatch"
        }
        val template = PromptTemplate(
            promptVersion = promptJson.getString("promptVersion"),
            model = promptJson.getString("model"),
            systemInstruction = promptJson.getString("systemInstruction"),
            inputTemplate = promptJson.getString("inputTemplate"),
            substitutionRuleWithAlternatives = promptJson.getString("substitutionRuleWithAlternatives"),
            substitutionRuleWithoutAlternatives = promptJson.getString("substitutionRuleWithoutAlternatives"),
            noHearingContext = promptJson.getString("noHearingContext"),
            responseSchemaJson = promptJson.getJSONObject("responseSchema").toString(),
        )
        val substitution = json(policy.substitutionPolicyAsset)
        val substitutionPolicy = PhraseMatchPolicy(
            substitution.getInt("maximum_changed_events"),
            substitution.getDouble("maximum_contradicting_top1").toFloat(),
            substitution.getDouble("maximum_changed_score_gap").toFloat(),
            substitution.getDouble("minimum_changed_score_ratio").toFloat(),
            substitution.getDouble("minimum_winner_lead").toFloat(),
        )
        return Assets(policy, lexicon, template, substitutionPolicy)
    }

    private fun json(asset: String): JSONObject =
        JSONObject(context.assets.open(asset).bufferedReader().use { it.readText() })

    private fun strings(array: JSONArray): List<String> = (0 until array.length()).map { array.getString(it) }
}
