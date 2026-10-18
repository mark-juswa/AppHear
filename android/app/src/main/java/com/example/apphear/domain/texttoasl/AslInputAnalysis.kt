package com.example.apphear.domain.texttoasl

/** Conservative English routing facts; this is not a general meaning/ASL model. */
data class AslInputAnalysis(
    val intent: Intent,
    val negationWords: List<String>,
    val timeWords: List<String>,
    val isQuestion: Boolean,
) {
    enum class Intent { GREETING, EXPRESSION, STATEMENT, WH_QUESTION, YES_NO_QUESTION, REQUEST, UNKNOWN }

    companion object {
        private val wh = setOf("what", "where", "when", "why", "who", "whose", "which", "how")
        private val auxiliaries = setOf("is", "are", "am", "was", "were", "do", "does", "did", "can", "could", "will", "would", "have", "has", "should")
        private val negatives = setOf("not", "no", "never", "dont", "doesnt", "didnt", "cant", "cannot", "couldnt", "wont", "wouldnt", "isnt", "arent", "wasnt", "werent", "havent", "hasnt", "shouldnt")
        private val times = setOf("today", "tomorrow", "yesterday", "now", "later", "before", "after", "morning", "afternoon", "evening", "tonight")

        fun analyze(input: String, normalizer: AslTextNormalizer = AslTextNormalizer()): AslInputAnalysis {
            val text = normalizer.normalizeSequence(input)
            val words = text.split(' ').filter { it.isNotBlank() }
            val first = words.firstOrNull()
            val request = text.startsWith("please ") || text.startsWith("can you ") || text.startsWith("could you ") ||
                text in setOf("i need help", "i need water")
            val question = input.contains('?') || input.contains('？') || first in wh || first in auxiliaries
            val intent = when {
                words.isEmpty() -> Intent.UNKNOWN
                request -> Intent.REQUEST
                first in wh -> Intent.WH_QUESTION
                question -> Intent.YES_NO_QUESTION
                text in setOf("hello", "hi", "hey", "hello beautiful", "good morning", "good afternoon", "good evening") -> Intent.GREETING
                text in setOf("thank you", "thanks", "nice to meet you", "see you tomorrow", "sorry", "youre welcome") -> Intent.EXPRESSION
                words.size > 1 -> Intent.STATEMENT
                else -> Intent.UNKNOWN
            }
            return AslInputAnalysis(intent, words.filter { it in negatives }, words.filter { it in times }, question)
        }
    }
}
