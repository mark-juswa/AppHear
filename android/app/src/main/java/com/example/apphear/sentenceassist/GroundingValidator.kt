package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.PhraseMatchPolicy
import com.example.apphear.contextassist.RecognitionEvidence

/**
 * One Deaf turn as recognized. [glosses] are the RECOGNIZED words exactly as Hear speaks them.
 * [evidence] (per-sign Top-5) is present only when it is complete and lines up with [glosses]:
 * its Top-1 sequence, with consecutive repeats collapsed like SentenceBuilder does, must equal
 * [glosses]. Without evidence no substitution can be grounded.
 */
data class SignedTurn(val glosses: List<String>, val evidence: List<RecognitionEvidence>? = null) {
    init {
        require(evidence == null || collapseRepeats(evidence.map { it.originalGloss }) == glosses) {
            "Evidence does not line up with the recognized words"
        }
    }
}

/** The renderer replaced the Top-1 of evidence event [eventIndex] with [gloss] from its Top-5. */
data class Substitution(val eventIndex: Int, val gloss: String)

/** What a renderer returns; its own word provenance is never trusted. */
data class Rendering(val sentence: String, val substitutions: List<Substitution> = emptyList())

enum class WordSource { SIGNED, SUBSTITUTED, GRAMMAR, INFERRED_PRONOUN }

data class GroundedWord(val text: String, val source: WordSource, val gloss: String? = null)

enum class RejectReason {
    NO_SIGNS, TOO_MANY_SIGNS, UNKNOWN_GLOSS, EMPTY_SENTENCE, TOO_LONG,
    SUBSTITUTION_WITHOUT_EVIDENCE, INVALID_SUBSTITUTION, UNSUPPORTED_WORD,
    TOO_MANY_INFERRED, MISSING_SIGN,
}

sealed interface GroundingResult {
    data class Accepted(
        val sentence: String,
        val words: List<GroundedWord>,
        val substitutions: List<Substitution>,
    ) : GroundingResult {
        val inferredPronouns: Int get() = words.count { it.source == WordSource.INFERRED_PRONOUN }
    }

    data class Rejected(val reason: RejectReason, val detail: String) : GroundingResult
}

/**
 * Accepts a rendering only when every signed concept is present and nothing unsigned is added:
 * each word must be a lexicon form of a signed (or validly substituted) gloss, a closed-class
 * grammar word, or an allowed inferred pronoun within the policy limit. Substitutions use the
 * same bounds as Context Assist's PhraseMatcher, so the two features cannot disagree.
 */
class GroundingValidator(
    private val lexicon: GlossLexicon,
    private val policy: SentenceAssistPolicy,
    private val substitutionPolicy: PhraseMatchPolicy,
) {
    fun validate(turn: SignedTurn, rendering: Rendering): GroundingResult {
        if (turn.glosses.isEmpty()) return reject(RejectReason.NO_SIGNS, "")
        if (turn.glosses.size > policy.maxGlosses) {
            return reject(RejectReason.TOO_MANY_SIGNS, "${turn.glosses.size} > ${policy.maxGlosses}")
        }
        turn.glosses.firstOrNull { it !in lexicon.glosses }?.let {
            return reject(RejectReason.UNKNOWN_GLOSS, it)
        }
        val sentence = rendering.sentence.trim()
        val tokens = SentenceTokenizer.tokens(sentence)
        if (tokens.isEmpty()) return reject(RejectReason.EMPTY_SENTENCE, "")
        if (sentence.length > policy.maxOutputChars) {
            return reject(RejectReason.TOO_LONG, "${sentence.length} > ${policy.maxOutputChars}")
        }

        substitutionRejection(turn, rendering.substitutions)?.let { return it }
        val unchanged = unchangedGlosses(turn, rendering.substitutions)
        val substituted = rendering.substitutions.map { it.gloss }.toSet() - unchanged
        val allSigned = unchanged + substituted

        val words = mutableListOf<GroundedWord>()
        val covered = mutableSetOf<String>()
        var index = 0
        while (index < tokens.size) {
            val match = longestSignedMatch(tokens, index, allSigned)
            if (match != null) {
                val (gloss, length) = match
                covered += gloss
                val source = if (gloss in substituted) WordSource.SUBSTITUTED else WordSource.SIGNED
                words += GroundedWord(tokens.subList(index, index + length).joinToString(" "), source, gloss)
                index += length
                continue
            }
            val token = tokens[index]
            words += when (token) {
                in lexicon.grammarWords -> GroundedWord(token, WordSource.GRAMMAR)
                in lexicon.inferablePronouns -> GroundedWord(token, WordSource.INFERRED_PRONOUN)
                else -> return reject(RejectReason.UNSUPPORTED_WORD, token)
            }
            index++
        }
        val inferred = words.count { it.source == WordSource.INFERRED_PRONOUN }
        if (inferred > policy.maxInferredPronouns) {
            return reject(RejectReason.TOO_MANY_INFERRED, "$inferred > ${policy.maxInferredPronouns}")
        }
        (allSigned - covered).sorted().firstOrNull()?.let {
            return reject(RejectReason.MISSING_SIGN, it)
        }
        return GroundingResult.Accepted(sentence, words, rendering.substitutions)
    }

    private fun substitutionRejection(turn: SignedTurn, substitutions: List<Substitution>): GroundingResult.Rejected? {
        if (substitutions.isEmpty()) return null
        val evidence = turn.evidence ?: return reject(RejectReason.SUBSTITUTION_WITHOUT_EVIDENCE, "")
        return substitutionProblem(evidence, substitutions)?.let { reject(RejectReason.INVALID_SUBSTITUTION, it) }
    }

    /** Signed glosses that stay as recognized once (already validated) substitutions apply. */
    private fun unchangedGlosses(turn: SignedTurn, substitutions: List<Substitution>): Set<String> {
        val evidence = turn.evidence
        if (substitutions.isEmpty() || evidence == null) return turn.glosses.toSet()
        val replaced = substitutions.map { it.eventIndex }.toSet()
        return evidence.indices.filter { it !in replaced }.map { evidence[it].originalGloss }.toSet()
    }

    private fun substitutionProblem(evidence: List<RecognitionEvidence>, substitutions: List<Substitution>): String? {
        if (substitutions.size > substitutionPolicy.maximumChangedEvents) {
            return "${substitutions.size} changes > ${substitutionPolicy.maximumChangedEvents}"
        }
        if (substitutions.map { it.eventIndex }.distinct().size != substitutions.size) return "duplicate event"
        for (substitution in substitutions) {
            val event = evidence.getOrNull(substitution.eventIndex) ?: return "event ${substitution.eventIndex} out of range"
            if (substitution.gloss == event.originalGloss) return "event ${substitution.eventIndex} unchanged"
            if (substitution.gloss !in lexicon.glosses) return "unknown gloss ${substitution.gloss}"
            if (event.topK.none { it.gloss == substitution.gloss }) {
                return "${substitution.gloss} not in Top-5 of event ${substitution.eventIndex}"
            }
            if (!SubstitutionBounds.allows(event, substitution.gloss, substitutionPolicy)) {
                return "${substitution.gloss} outside substitution bounds"
            }
        }
        return null
    }

    private fun longestSignedMatch(tokens: List<String>, start: Int, signed: Set<String>): Pair<String, Int>? {
        var best: Pair<String, Int>? = null
        for (gloss in signed.sorted()) {
            for (form in lexicon.formsOf(gloss)) {
                if (form.size <= (best?.second ?: 0) || start + form.size > tokens.size) continue
                if (tokens.subList(start, start + form.size) == form) best = gloss to form.size
            }
        }
        return best
    }

    private fun reject(reason: RejectReason, detail: String) = GroundingResult.Rejected(reason, detail)
}

/**
 * One rule for both the prompt (which alternatives the renderer is offered) and the validator:
 * identical to PhraseMatcher's changed-event checks, so Context Assist and sentence assist
 * can never disagree about when a Top-5 alternative may replace the recognized word.
 */
object SubstitutionBounds {
    fun allows(event: RecognitionEvidence, gloss: String, policy: PhraseMatchPolicy): Boolean {
        val top1 = event.topK.firstOrNull() ?: return false
        if (gloss == event.originalGloss) return false
        val visual = event.topK.firstOrNull { it.gloss == gloss } ?: return false
        return top1.score <= policy.maximumContradictingTop1 &&
            top1.score - visual.score <= policy.maximumChangedScoreGap &&
            !(top1.score > 0f && visual.score / top1.score < policy.minimumChangedScoreRatio)
    }

    fun eligibleAlternatives(event: RecognitionEvidence, policy: PhraseMatchPolicy): List<String> =
        event.topK.map { it.gloss }.filter { allows(event, it, policy) }
}

/** SentenceBuilder's rule: a gloss committed twice in a row appears once. */
internal fun collapseRepeats(glosses: List<String>): List<String> =
    glosses.filterIndexed { index, gloss -> index == 0 || glosses[index - 1] != gloss }
