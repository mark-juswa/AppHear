package com.example.apphear.domain.texttoasl

class AslPhrasePlanner(
    private val catalog: AslAnimationCatalog,
    private val normalizer: AslTextNormalizer = AslTextNormalizer(),
    private val completeWordFallback: Boolean = false,
    private val strictPhraseMode: Boolean = false,
) {
    fun plan(input: String?): TextToAslPlan {
        val requestedText = input?.trim().orEmpty()
        if (strictPhraseMode) {
            val normalized = normalizer.normalize(input, preserveUnknownCharacters = true)
            val dictionaryMatch = catalog.findByAlias(normalized)?.takeIf { asset ->
                asset.type != AslAnimationAsset.Type.POSE && asset.aliases.any { alias ->
                    normalizer.normalize(alias, preserveUnknownCharacters = true) == normalized
                }
            }
            val match = dictionaryMatch ?: if (completeWordFallback && normalized.length == 1 &&
                normalized[0] in 'a'..'z') catalog.findLetter(normalized[0]) else null
            // A dictionary clip does not establish English-to-ASL sentence translation.
            // Never perform a recognized fragment of an unsupported complete input.
            return TextToAslPlan(requestedText, normalized, match?.let { listOf(it) }.orEmpty(),
                if (match == null && requestedText.isNotBlank()) listOf(requestedText) else emptyList())
        }
        var remaining = normalizer.normalize(input)
        val queue = mutableListOf<AslAnimationAsset>()
        val unsupported = mutableListOf<String>()

        while (remaining.isNotEmpty()) {
            val match = findLongestMatch(remaining)
            if (match != null) {
                queue += match.asset
                remaining = consume(remaining, match.alias.length)
                continue
            }

            if (completeWordFallback) {
                val token = remaining.substringBefore(' ')
                val letters = token.map { catalog.findLetter(it) }
                if (token.isNotEmpty() && token.all { it in 'a'..'z' } && letters.all { it != null }) {
                    queue += letters.filterNotNull()
                } else if (token.isNotEmpty()) {
                    unsupported += token
                }
                remaining = consume(remaining, token.length)
            } else {
                val first = remaining.first()
                if (first.isLetter()) {
                    val letter = catalog.findByAlias(first.toString())
                    if (letter != null) queue += letter else unsupported += first.toString()
                }
                remaining = consume(remaining, 1)
            }
        }

        return TextToAslPlan(
            requestedText = requestedText,
            normalizedText = normalizer.normalize(input),
            queue = queue,
            unsupportedTokens = unsupported,
        )
    }

    private fun findLongestMatch(text: String): Match? {
        for (alias in catalog.getAliasesLongestFirst()) {
            if (text == alias || text.startsWith("$alias ")) {
                val asset = catalog.findByAlias(alias)
                if (asset != null) return Match(alias, asset)
            }
        }
        return null
    }

    private fun consume(text: String, count: Int): String {
        return text
            .substring(minOf(count, text.length))
            .trim()
            .replace(Regex("^\\s+"), "")
    }

    private data class Match(
        val alias: String,
        val asset: AslAnimationAsset,
    )
}

