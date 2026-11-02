package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.PhraseMatchPolicy

/** Contents of the prompt asset named in the policy (`prompt_v2.json`), shared by the app and offline evaluation. */
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
    /**
     * Recent conversation lines offered as context, labelled "Them:" / "You:" (prompt v3+). 0 keeps the
     * older behaviour: only the latest hearing message, unlabelled.
     */
    val conversationLines: Int = 0,
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
data class RenderRequest(
    val turn: SignedTurn,
    val hearingContext: String? = null,
    /** Recent exchanges, oldest first, used when the prompt asks for [PromptTemplate.conversationLines]. */
    val conversation: List<ConversationLine> = emptyList(),
)

/** One earlier line of the conversation: the hearing person's reply, or what the signer said. */
data class ConversationLine(val fromSigner: Boolean, val text: String)

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
        val hearing = context(request) ?: template.noHearingContext
        return template.inputTemplate
            .replace("{{SIGNS}}", signs.joinToString("\n"))
            .replace("{{HEARING}}", hearing)
            .replace("{{GRAMMAR_WORDS}}", lexicon.grammarWords.sorted().joinToString(", "))
            .replace("{{MAX_INFERRED}}", policy.maxInferredPronouns.toString())
            .replace("{{PRONOUNS}}", lexicon.inferablePronouns.sorted().joinToString(", "))
            .replace("{{SUBSTITUTION_RULE}}", substitutionRule)
    }

    /**
     * The context block: with [PromptTemplate.conversationLines], the last few exchanges labelled
     * "Them:" / "You:" (or just the latest hearing message, labelled); otherwise the latest hearing
     * message as before. Context never supplies words: the validator rejects anything unsigned.
     */
    private fun context(request: RenderRequest): String? {
        val hearing = request.hearingContext?.trim()?.takeIf { it.isNotEmpty() }
        if (template.conversationLines <= 0) return hearing
        val lines = request.conversation.filter { it.text.isNotBlank() }.takeLast(template.conversationLines)
            .map { (if (it.fromSigner) "You: " else "Them: ") + it.text.trim().take(policy.maxOutputChars) }
        return if (lines.isNotEmpty()) lines.joinToString("\n") else hearing?.let { "Them: ${it.take(policy.maxOutputChars)}" }
    }

    private fun line(index: Int, gloss: String, alternatives: List<String>): String {
        val sign = "${index + 1}. $gloss = \"${lexicon.displayForm(gloss)}\""
        if (alternatives.isEmpty()) return sign
        return sign + " (alternatives: " +
            alternatives.joinToString(", ") { "$it = \"${lexicon.displayForm(it)}\"" } + ")"
    }
}
