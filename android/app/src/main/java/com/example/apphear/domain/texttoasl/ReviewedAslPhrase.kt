package com.example.apphear.domain.texttoasl

/** A whole English meaning mapped by a reviewer, never a universal reorder rule. */
data class ReviewedAslPhrase(
    val id: String,
    val english: List<String>,
    val meaning: String,
    val intent: AslInputAnalysis.Intent,
    val gloss: List<String>,
    val signIds: List<String>,
    val status: SignDictionaryMetadata.Status,
    val review: ReviewRecord,
    val negated: Boolean = false,
    val timeWords: Set<String> = emptySet(),
    val nonManualMarkers: List<NonManualMarker> = emptyList(),
    val isQuestion: Boolean = false,
) {
    data class NonManualMarker(val marker: String, val fromSign: Int, val throughSign: Int)
    data class ReviewRecord(
        val reviewer: String, val reviewedOn: String, val sources: List<String>, val license: String,
        val meaningEvidence: String, val nonManualEvidence: String, val playbackEvidence: String,
    ) {
        fun isComplete(): Boolean = listOf(reviewer, license, meaningEvidence, nonManualEvidence, playbackEvidence)
            .all { it.isNotBlank() } && sources.isNotEmpty() && sources.all { it.isNotBlank() } &&
            runCatching { java.time.LocalDate.parse(reviewedOn) }.isSuccess
    }
}

data class AslGrammarRegistry(val enabled: Boolean = true, val phrases: List<ReviewedAslPhrase> = emptyList(),
    val blockedLiteralExpressions: List<String> = emptyList())
