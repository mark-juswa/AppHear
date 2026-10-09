package com.example.apphear.domain.texttoasl

class AslPhrasePlanner(
    private val catalog: AslAnimationCatalog,
    private val normalizer: AslTextNormalizer = AslTextNormalizer(),
    private val completeWordFallback: Boolean = false,
    private val dictionarySequenceMode: Boolean = false,
) {
    fun plan(input: String?): TextToAslPlan {
        val requestedText = input?.trim().orEmpty()
        if (dictionarySequenceMode) return planDictionarySequence(requestedText)
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

    private fun planDictionarySequence(input: String): TextToAslPlan {
        val normalized = normalizer.normalizeSequence(input)
        // Match declared text forms, never internal IDs or partial characters of a word.
        val entries = catalog.getAssets().filter { it.type != AslAnimationAsset.Type.POSE }
            .flatMap { asset -> asset.aliases.map { normalizer.normalizeSequence(it) to asset } }
            .filter { it.first.isNotBlank() }
        val byAlias = linkedMapOf<String, AslAnimationAsset>()
        for ((alias, asset) in entries) {
            require(byAlias[alias] == null || byAlias[alias]?.id == asset.id) {
                "Ambiguous normalized sign alias: $alias"
            }
            byAlias[alias] = asset
        }
        byAlias[normalized]?.let { asset ->
            return TextToAslPlan(input, normalized, listOf(asset), emptyList(),
                TextToAslPlan.Mode.DICTIONARY_ENTRY)
        }
        var remaining = normalized
        val queue = mutableListOf<AslAnimationAsset>()
        val unsupported = mutableListOf<String>()
        val aliases = byAlias.keys.sortedByDescending { it.length }
        while (remaining.isNotEmpty()) {
            val alias = aliases.firstOrNull { remaining == it || remaining.startsWith("$it ") }
            if (alias != null) {
                queue += byAlias.getValue(alias)
                remaining = consume(remaining, alias.length)
            } else {
                val word = remaining.substringBefore(' ')
                val letter = if (completeWordFallback && word.length == 1 && word[0] in 'a'..'z')
                    catalog.findLetter(word[0]) else null
                if (letter != null) queue += letter else unsupported += word
                remaining = consume(remaining, word.length)
            }
        }
        return TextToAslPlan(input, normalized, queue, unsupported, TextToAslPlan.Mode.WORD_SEQUENCE)
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

