package com.example.apphear.domain.texttoasl

data class TextToAslPlan(
    val requestedText: String,
    val normalizedText: String,
    val queue: List<AslAnimationAsset>,
    val unsupportedTokens: List<String>,
) {
    val isPlayable: Boolean
        get() = queue.isNotEmpty()
}

