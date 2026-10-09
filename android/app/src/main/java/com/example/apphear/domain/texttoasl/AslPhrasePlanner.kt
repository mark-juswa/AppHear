package com.example.apphear.domain.texttoasl

/**
 * Phrase mode intentionally requires a whole-input dictionary match. Concatenating
 * English words or partial fingerspelling is not an ASL translation.
 */
class AslPhrasePlanner(
    private val catalog: AslAnimationCatalog,
    private val normalizer: AslTextNormalizer = AslTextNormalizer(),
    private val strictPhraseMode: Boolean = true,
) {
    fun plan(input: String?): TextToAslPlan {
        if (!strictPhraseMode) return legacyPlan(input)
        val requested = input?.trim().orEmpty()
        val normalized = normalizer.normalize(input)
        if (normalized.isEmpty()) {
            return TextToAslPlan(requested, normalized, emptyList(),
                if (requested.isBlank()) emptyList() else listOf(requested))
        }
        val asset = catalog.findByAlias(normalized)
        val usable = asset?.takeIf {
            it.type != AslAnimationAsset.Type.POSE && it.type != AslAnimationAsset.Type.LETTER &&
                it.aliases.any { alias -> normalizer.normalize(alias) == normalized }
        }
        return TextToAslPlan(requested, normalized,
            usable?.let { listOf(it) }.orEmpty(),
            if (usable == null) listOf(requested) else emptyList())
    }

    // Rollback only; the redesigned UI never uses character-fragment fallback.
    private fun legacyPlan(input: String?): TextToAslPlan {
        var remaining = normalizer.normalize(input)
        val queue = mutableListOf<AslAnimationAsset>()
        val unsupported = mutableListOf<String>()
        while (remaining.isNotEmpty()) {
            val alias = catalog.getAliasesLongestFirst().firstOrNull {
                remaining == it || remaining.startsWith("$it ")
            }
            if (alias != null) {
                catalog.findByAlias(alias)?.let { queue += it }
                remaining = remaining.substring(alias.length).trim()
            } else {
                val letter = remaining.first()
                if (letter.isLetter()) {
                    val asset = catalog.findByAlias(letter.toString())
                    if (asset == null) unsupported += letter.toString() else queue += asset
                }
                remaining = remaining.substring(1).trim()
            }
        }
        return TextToAslPlan(input?.trim().orEmpty(), normalizer.normalize(input), queue, unsupported)
    }
}

