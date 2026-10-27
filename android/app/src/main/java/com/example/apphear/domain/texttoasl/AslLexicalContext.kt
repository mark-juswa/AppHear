package com.example.apphear.domain.texttoasl

/** Word-sense safeguards for English previews; never ASL grammar or word deletion. */
data class AslLexicalContext(
    val replacementIds: Map<Int, String> = emptyMap(),
    val fingerspellTokens: Set<Int> = emptySet(),
) {
    companion object {
        fun forPreview(normalized: String, catalog: AslAnimationCatalog): AslLexicalContext {
            val words = normalized.split(' ').filter(String::isNotBlank)
            val replacements = AslAdverbPolicy.speedReplacements(normalized, catalog).toMutableMap()
            val spell = mutableSetOf<Int>()
            val subjects = setOf("i", "you", "we", "they", "he", "she", "it")
            val wh = setOf("what", "where", "when", "why", "how", "who", "which")
            // English auxiliary DO is not the lexical ASL activity DO. Retain
            // its letters in an explicitly labeled preview instead of signing
            // an unrelated activity or silently dropping it.
            for (index in words.indices) {
                if (words[index] == "do" && (words.getOrNull(index + 1) == "not" ||
                    (words.getOrNull(index + 1) in subjects && (index == 0 || words[index - 1] in wh)))) spell += index
            }
            // Price HOW-MUCH is a distinct sign; it is not generic HOW+MUCH.
            if (words.take(2) == listOf("how", "much") && catalog.findByAlias("how much") == null) spell += setOf(0, 1)
            for (start in words.indices) {
                if (words.drop(start).take(4) == listOf("what", "do", "you", "mean")) replacements[start + 3] = "mean_meaning"
            }
            if (normalized == "turn right") replacements[1] = "right_direction"
            // STOP (cease) does not, by itself, mean a bus-stop location.
            if (catalog.findByAlias("bus stop") == null) for (index in 1 until words.size) {
                if (words[index - 1] == "bus" && words[index] == "stop") spell += index
            }
            if (normalized == "have a good day") spell += 0 // Wish, not possession.
            if (words.take(2) == listOf("let", "us")) spell += 0 // Invitation, not ALLOW.
            return AslLexicalContext(replacements, spell)
        }
    }
}
