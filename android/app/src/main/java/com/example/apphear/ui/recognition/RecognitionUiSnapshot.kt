package com.example.apphear.ui.recognition

import com.example.apphear.pipeline.recognition.RecognitionState

data class RecognitionUiSnapshot(
    val primaryText: String,
    val candidatesText: String,
    val sentenceText: String,
    val showCandidates: Boolean,
    val showSentence: Boolean,
    val stateLabel: String,
) {
    companion object {
        fun from(
            state: RecognitionState?,
            sentence: String,
            idleText: String,
            signingText: String,
            sentencePlaceholder: String,
        ): RecognitionUiSnapshot {
            val cleanSentence = sentence.takeIf { it.isNotBlank() } ?: sentencePlaceholder
            return when (state) {
                is RecognitionState.Committed -> {
                    val alternatives = state.candidates.drop(1).joinToString("      ")
                    RecognitionUiSnapshot(
                        primaryText = state.candidates.firstOrNull() ?: state.gloss,
                        candidatesText = alternatives,
                        sentenceText = cleanSentence,
                        showCandidates = alternatives.isNotBlank(),
                        showSentence = cleanSentence != sentencePlaceholder,
                        stateLabel = "COMMITTED",
                    )
                }
                is RecognitionState.Signing -> {
                    val top = state.candidates.firstOrNull() ?: signingText
                    val alternatives = state.candidates.drop(1).joinToString("      ")
                    RecognitionUiSnapshot(
                        primaryText = top,
                        candidatesText = alternatives,
                        sentenceText = cleanSentence,
                        showCandidates = alternatives.isNotBlank(),
                        showSentence = cleanSentence != sentencePlaceholder,
                        stateLabel = "SIGNING",
                    )
                }
                else -> RecognitionUiSnapshot(
                    primaryText = idleText,
                    candidatesText = "",
                    sentenceText = cleanSentence,
                    showCandidates = false,
                    showSentence = cleanSentence != sentencePlaceholder,
                    stateLabel = "READY",
                )
            }
        }
    }
}
