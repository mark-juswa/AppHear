package com.example.apphear.sentenceassist

import java.util.Locale

/**
 * Normalizes English for grounding checks: lowercase words with contractions expanded, so
 * "I'm" -> [i, am], "don't" -> [do, not], "can't"/"cannot" -> [can, not]. Punctuation is dropped
 * because it never carries signed content. Lexicon forms go through the same function.
 */
object SentenceTokenizer {
    private val WORD = Regex("[a-z0-9]+(?:'[a-z]+)?")
    private val SUFFIX = mapOf("'m" to "am", "'re" to "are", "'ll" to "will")
    private val NEGATED_STEM = mapOf("can" to "can", "ca" to "can", "won" to "will", "wo" to "will")

    fun tokens(text: String): List<String> {
        val normalized = text.lowercase(Locale.US).replace('’', '\'').replace("cannot", "can not")
        return WORD.findAll(normalized).flatMap { expand(it.value) }.toList()
    }

    private fun expand(word: String): List<String> {
        if (word.endsWith("n't")) {
            val stem = word.dropLast(3)
            return listOf(NEGATED_STEM[stem] ?: stem, "not")
        }
        val apostrophe = word.indexOf('\'')
        if (apostrophe <= 0) return listOf(word)
        val base = word.substring(0, apostrophe)
        val suffix = word.substring(apostrophe)
        // 's (is/has/possessive), 've and 'd stay as grammar markers rather than guessed words.
        return listOf(base, SUFFIX[suffix] ?: suffix)
    }
}
