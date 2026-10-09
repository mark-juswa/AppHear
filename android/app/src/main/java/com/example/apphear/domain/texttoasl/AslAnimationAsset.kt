package com.example.apphear.domain.texttoasl

data class AslAnimationAsset(
    val id: String,
    val displayText: String,
    val assetPath: String,
    val type: Type,
    val aliases: List<String>,
    val replacement: Replacement? = null,
) {
    fun originalFallback(): AslAnimationAsset? = replacement?.fallbackAssetPath?.let { path ->
        copy(assetPath = path, replacement = null)
    }

    data class Replacement(
        val fallbackAssetPath: String?,
        val animationName: String,
        val durationMs: Long,
    )
    enum class Type {
        PHRASE,
        WORD,
        LETTER,
        POSE,
    }
}

