package com.example.apphear.sentenceassist

/** Produces a candidate sentence; null means "no rendering" (unavailable, timed out, malformed). */
fun interface SentenceRenderer {
    suspend fun render(request: RenderRequest): Rendering?
}

/**
 * Offline fallback: the recognized words in signing order using each gloss's citation English,
 * capitalized, ending in "?" when a question sign was used. It adds nothing, so it always
 * passes grounding; it is the honest baseline the AI rendering must beat.
 */
class PlainGlossRenderer(private val lexicon: GlossLexicon) : SentenceRenderer {
    override suspend fun render(request: RenderRequest): Rendering = plain(request.turn)

    fun plain(turn: SignedTurn): Rendering {
        val words = turn.glosses.joinToString(" ") { lexicon.displayForm(it) }
        val sentence = words.replaceFirstChar { it.uppercase() }
        val ending = if (turn.glosses.any { it in QUESTION_SIGNS }) "?" else "."
        return Rendering(if (sentence.isEmpty()) "" else sentence + ending)
    }

    private companion object {
        val QUESTION_SIGNS = setOf("WHAT1", "WHERE", "WHEN", "WHO", "WHY", "WHICH", "HOW1")
    }
}

/**
 * Converts a provider's raw reply into a [Rendering]. Sign numbers are 1-based in the prompt;
 * anything malformed (missing sentence, non-positive number, blank gloss) yields null rather
 * than a guessed repair. Grounding is checked separately by [GroundingValidator].
 */
object RenderingMapper {
    data class RawSubstitution(val signNumber: Int?, val gloss: String?)

    fun map(sentence: String?, substitutions: List<RawSubstitution>?): Rendering? {
        val text = sentence?.trim()?.takeIf { it.isNotEmpty() } ?: return null
        val mapped = (substitutions ?: return null).map { raw ->
            val number = raw.signNumber?.takeIf { it >= 1 } ?: return null
            val gloss = raw.gloss?.trim()?.takeIf { it.isNotEmpty() } ?: return null
            Substitution(number - 1, gloss)
        }
        return Rendering(text, mapped)
    }
}
