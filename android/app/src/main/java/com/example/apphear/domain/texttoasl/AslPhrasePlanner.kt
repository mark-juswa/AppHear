package com.example.apphear.domain.texttoasl

class AslPhrasePlanner(
    private val catalog: AslAnimationCatalog,
    private val normalizer: AslTextNormalizer = AslTextNormalizer(),
) {
    fun plan(input: String?): TextToAslPlan {
        val requestedText = input?.trim().orEmpty()
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

            val first = remaining.first()
            if (first.isLetter()) {
                val letter = catalog.findByAlias(first.toString())
                if (letter != null) {
                    queue += letter
                } else {
                    unsupported += first.toString()
                }
                remaining = consume(remaining, 1)
            } else {
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

