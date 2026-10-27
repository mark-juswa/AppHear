package com.example.apphear.domain.texttoasl

import java.util.Locale

class AslTextNormalizer {
    private fun expandContractions(input: String?): String {
        var text = input.orEmpty().lowercase(Locale.US).replace('\u2019', '\'')
        // English normalization only: preserve every word and all negation.
        // CAN'T stays atomic; its ASL sign is not simply CAN plus NOT.
        for ((form, expanded) in mapOf("don't" to "do not", "dont" to "do not", "i'm" to "i am",
            "you're" to "you are", "it's" to "it is", "let's" to "let us")) {
            text = text.replace(Regex("\\b${Regex.escape(form)}\\b"), expanded)
        }
        return text
    }

    fun normalizeSequence(input: String?, preserveSymbols: Boolean = false): String = expandContractions(input)
        .replace("'", "")
        .replace(Regex(if (preserveSymbols) "[\\p{P}]+" else "[\\p{P}\\p{S}]+"), " ")
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

