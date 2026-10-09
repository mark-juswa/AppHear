package com.example.apphear.domain.texttoasl

data class AslAnimationAsset(
    val id: String,
    val displayText: String,
    val assetPath: String,
    val type: Type,
    val aliases: List<String>,
) {
    enum class Type {
        PHRASE,
        WORD,
        LETTER,
        POSE,
    }
}

