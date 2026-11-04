package com.example.apphear.demo

/**
 * Question-based guided demo: a topic (e.g. School) holds questions and their answers. The hearing
 * person may ask them in any order; the question asked decides the signer's answer. Pure Kotlin.
 */
data class DemoQuestion(
    val id: String,
    /** Ways the question may be asked (English and Filipino/Taglish); the first is shown in lists. */
    val phrasings: List<String>,
    /** The signer's answer; `{spelled}` is the fingerspelling model's reading when [spell] is set. */
    val answer: String,
    val gloss: String,
    /** The answer's `{spelled}` part (a name or place) is the fingerspelling model's reading. */
    val spell: Boolean = false,
)

data class DemoTopic(val id: String, val title: String, val questions: List<DemoQuestion>)

/** The matcher's verdict for one spoken question. */
sealed interface QuestionMatch {
    data class Confident(val question: DemoQuestion) : QuestionMatch
    /** Probably [best], but the wording is unclear: ask the AI helper when it is available. */
    data class Unsure(val best: DemoQuestion?) : QuestionMatch
}

object DemoQuestionMatcher {
    /** Words that carry no meaning for telling questions apart. */
    private val STOP = setOf(
        "a", "an", "the", "is", "are", "am", "was", "do", "does", "did", "you", "your", "yours", "i", "me", "my",
        "to", "of", "in", "at", "on", "for", "and", "or", "so", "now", "please", "can", "could", "may", "would",
        "will", "ka", "mo", "ang", "ng", "na", "po", "ba", "ko", "sa", "naman", "yung", "um", "uh", "hey", "hi",
        "okay", "ok", "tell", "know", "us", "about",
    )
    private val EXPAND = mapOf("what's" to "what", "whats" to "what", "where's" to "where", "who's" to "who",
        "how's" to "how", "you're" to "you", "anong" to "ano", "saan" to "where", "sino" to "who")

    const val CONFIDENT = 0.6
    const val MARGIN = 0.15
    const val UNSURE_FLOOR = 0.3

    fun words(text: String): Set<String> =
        text.lowercase().replace(Regex("[^a-z0-9' ]"), " ").split(Regex("\\s+"))
            .map { EXPAND[it] ?: it.trim('\'') }
            .filter { it.isNotEmpty() && it !in STOP }.toSet()

    /** Dice overlap of the content words of [asked] with one phrasing. */
    fun score(asked: Set<String>, phrasing: String): Double {
        val target = words(phrasing)
        if (asked.isEmpty() || target.isEmpty()) return 0.0
        return 2.0 * asked.intersect(target).size / (asked.size + target.size)
    }

    fun match(spoken: String, topic: DemoTopic): QuestionMatch {
        val asked = words(spoken)
        val ranked = topic.questions.map { q -> q to (q.phrasings.maxOfOrNull { score(asked, it) } ?: 0.0) }
            .sortedByDescending { it.second }
        val (best, top) = ranked.firstOrNull() ?: return QuestionMatch.Unsure(null)
        val second = ranked.getOrNull(1)?.second ?: 0.0
        return when {
            top >= CONFIDENT && top - second >= MARGIN -> QuestionMatch.Confident(best)
            top >= UNSURE_FLOOR -> QuestionMatch.Unsure(best)
            else -> QuestionMatch.Unsure(null)
        }
    }

    /** A fingerspelled reading for display: letters only, each word capitalised ("NICOLE" -> "Nicole"). */
    fun spelledWords(reading: String): String =
        reading.trim().split(Regex("\\s+")).map { word -> word.filter { it.isLetterOrDigit() } }
            .filter { it.isNotEmpty() }
            .joinToString(" ") { it.lowercase().replaceFirstChar { c -> c.titlecase() } }
}
