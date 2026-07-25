package com.example.apphear.domain.texttoasl

import java.util.Locale

class AslTextNormalizer {
    fun normalize(input: String?): String {
        if (input.isNullOrBlank()) return ""

        val normalized = input
            .lowercase(Locale.US)
            .replace(Regex("[^a-z0-9\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

        return when (normalized) {
            "hi", "hey" -> "hello"
            else -> normalized
        }
    }
}

