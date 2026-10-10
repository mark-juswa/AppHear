package com.example.apphear.domain.texttoasl

data class TextToAslPlan(
    val requestedText: String,
    val normalizedText: String,
    val queue: List<AslAnimationAsset>,
    val unsupportedTokens: List<String>,
    val mode: Mode = Mode.LEGACY,
    val analysis: AslInputAnalysis? = null,
    val gloss: List<String> = emptyList(),
    val nonManualMarkers: List<ReviewedAslPhrase.NonManualMarker> = emptyList(),
    val translationNotice: String? = null,
    val ruleId: String? = null,
    val fingerspelledWords: List<String> = emptyList(),
) {
    enum class Mode { LEGACY, DICTIONARY_ENTRY, WORD_SEQUENCE, MIXED_FINGERSPELLING, VALIDATED_PHRASE, BLOCKED_MEANING }
    val isPlayable: Boolean
        get() = queue.isNotEmpty()
}

