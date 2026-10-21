package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.RecognitionEvidence

/**
 * Builds a [SignedTurn] from what the Recognition screen already holds, without changing it:
 * the RECOGNIZED text (SentenceBuilder output, glosses joined by spaces) and the per-sign
 * Top-5 evidence. Evidence is attached only when it is complete (no overflow, no interruption)
 * and lines up with the RECOGNIZED words; otherwise the renderer gets the words alone.
 */
object SignedTurnAssembler {
    fun assemble(
        recognizedText: String,
        evidence: List<RecognitionEvidence>,
        evidenceComplete: Boolean,
        maxGlosses: Int,
    ): SignedTurn? {
        val glosses = recognizedText.trim().split(WHITESPACE).filter { it.isNotEmpty() }
        if (glosses.isEmpty() || glosses.size > maxGlosses) return null
        val aligned = evidenceComplete && evidence.isNotEmpty() &&
            collapseRepeats(evidence.map { it.originalGloss }) == glosses
        return SignedTurn(glosses, if (aligned) evidence.toList() else null)
    }

    private val WHITESPACE = Regex("\\s+")
}
