package com.example.apphear.domain.texttoasl

import java.util.Locale

class AslTextNormalizer {
    fun normalizeSequence(input: String?): String = input.orEmpty().lowercase(Locale.US)
        .replace('\u2019', '\'').replace("'", "")
        .replace(Regex("[\\p{P}\\p{S}]+"), " ")
        .replace(Regex("\\s+"), " ").trim()

    fun normalize(input: String?, preserveUnknownCharacters: Boolean = false): String {
        if (input.isNullOrBlank()) return ""

        if (preserveUnknownCharacters) {
            // Preserve unknown characters so they cannot silently change sign selection.
            return input.lowercase(Locale.US).replace('\u2019', '\'')
                .replace(Regex("\\bdon't\\b"), "dont")
                .trim().trimEnd('.', '!', '?').trim()
                .replace(Regex("\\s+"), " ")
        }
        val normalized = input
            .lowercase(Locale.US)
            .replace(Regex("['?]"), "")
            .replace(Regex("[^a-z0-9\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

        return when (normalized) {
            "hi", "hey" -> "hello"
            else -> normalized
        }
    }
}

