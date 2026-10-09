package com.example.apphear.domain.texttoasl

import java.util.Locale

class AslTextNormalizer {
    fun normalize(input: String?): String {
        if (input.isNullOrBlank()) return ""
        // Keep digits, non-Latin text and internal punctuation so they cannot be
        // silently erased into an unrelated supported phrase.
        return input.lowercase(Locale.US)
            .replace('’', '\'')
            .replace(Regex("\\bdon't\\b"), "dont")
            .trim()
            .trimEnd('.', '!', '?')
            .trim()
            .replace(Regex("\\s+"), " ")
    }
}

