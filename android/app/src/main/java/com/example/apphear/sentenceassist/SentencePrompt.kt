package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.PhraseMatchPolicy

/** Contents of `assets/sentence_assist/prompt_v1.json`, shared by the app and offline evaluation. */
data class PromptTemplate(
    val promptVersion: String,
    val model: String,
    val systemInstruction: String,
    val inputTemplate: String,
    val substitutionRuleWithAlternatives: String,
    val substitutionRuleWithoutAlternatives: String,
    val noHearingContext: String,
    /** The JSON schema exactly as stored in the asset; sent verbatim to the provider. */
    val responseSchemaJson: String,
) {
    init {
        require(PLACEHOLDERS.all { it in inputTemplate }) { "Prompt template is missing a placeholder" }
        require("{{MAX_CHANGES}}" in substitutionRuleWithAlternatives)
    }

    companion object {
        const val SCHEMA_VERSION = 1
        val PLACEHOLDERS = listOf(
            "{{SIGNS}}", "{{HEARING}}", "{{GRAMMAR_WORDS}}", "{{MAX_INFERRED}}", "{{PRONOUNS}}",
            "{{SUBSTITUTION_RULE}}",
        )
    }
}

/** What the renderer is asked to turn into a sentence. */
data class RenderRequest(val turn: SignedTurn, val hearingContext: String? = null)

/**
 * Builds the provider input. Pure, so the offline evaluation can record the exact prompt the
 * app would send. Alternatives are offered only when they would pass [SubstitutionBounds]; a
 * confidently recognized sign is shown without any.
 */
class SentencePrompt(
    private val template: PromptTemplate,
    private val lexicon: GlossLexicon,
    private val policy: SentenceAssistPolicy,
    private val substitutionPolicy: PhraseMatchPolicy,
) {
    fun input(request: RenderRequest): String {
        val evidence = request.turn.evidence
        val signs: List<String>
        var anyAlternatives = false
        if (evidence == null) {
            signs = request.turn.glosses.mapIndexed { index, gloss -> line(index, gloss, emptyList()) }
        } else {
            signs = evidence.mapIndexed { index, event ->
                val alternatives = SubstitutionBounds.eligibleAlternatives(event, substitutionPolicy)
                    .filter { it in lexicon.glosses }
                if (alternatives.isNotEmpty()) anyAlternatives = true
                line(index, event.originalGloss, alternatives)
            }
        }
        val substitutionRule = if (anyAlternatives) {
            template.substitutionRuleWithAlternatives
                .replace("{{MAX_CHANGES}}", substitutionPolicy.maximumChangedEvents.toString())
        } else {
            template.substitutionRuleWithoutAlternatives
        }
        val hearing = request.hearingContext?.trim()?.takeIf { it.isNotEmpty() } ?: template.noHearingContext
        return template.inputTemplate
            .replace("{{SIGNS}}", signs.joinToString("\n"))
            .replace("{{HEARING}}", hearing)
            .replace("{{GRAMMAR_WORDS}}", lexicon.grammarWords.sorted().joinToString(", "))
            .replace("{{MAX_INFERRED}}", policy.maxInferredPronouns.toString())
            .replace("{{PRONOUNS}}", lexicon.inferablePronouns.sorted().joinToString(", "))
            .replace("{{SUBSTITUTION_RULE}}", substitutionRule)
    }

    private fun line(index: Int, gloss: String, alternatives: List<String>): String {
        val sign = "${index + 1}. $gloss = \"${lexicon.displayForm(gloss)}\""
        if (alternatives.isEmpty()) return sign
        return sign + " (alternatives: " +
            alternatives.joinToString(", ") { "$it = \"${lexicon.displayForm(it)}\"" } + ")"
    }
}
