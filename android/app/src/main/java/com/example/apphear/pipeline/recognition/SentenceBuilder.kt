package com.example.apphear.pipeline.recognition

/**
 * S8 sentence builder — SAFE SUBSET (raw passthrough + dedup). Accumulates committed glosses into an
 * ordered phrase, collapsing a consecutive repeat (the same gloss committed twice in a row → one
 * entry) and capping total length. NO LM-assisted gloss→text correction — that mode is deferred
 * until single-gloss recognition is trustworthy (chaining ~50%-wrong glosses through a corrector
 * would compound error). Inter-gloss spacing is already handled upstream: S5 onset/release +
 * one-commit-per-bout means each commit is a distinct signing bout.
 */
class SentenceBuilder(private val maxGlosses: Int = 20) {
    private val glosses = ArrayDeque<String>()

    /** Append a committed gloss; a consecutive duplicate is ignored. Returns true if it changed. */
    @Synchronized fun add(gloss: String): Boolean {
        if (glosses.lastOrNull() == gloss) return false
        glosses.addLast(gloss)
        while (glosses.size > maxGlosses) glosses.removeFirst() // bound growth; drop oldest
        return true
    }

    @Synchronized fun text(): String = glosses.joinToString(" ")

    /**
     * Removes the gloss at [index] (a word the signer marked as misrecognized). Returns false for an
     * index outside the phrase. Used only by the conversation screen (conversationFlowV2).
     */
    @Synchronized fun removeAt(index: Int, expectedText: String? = null): Boolean {
        if (expectedText != null && text() != expectedText) return false
        if (index !in glosses.indices) return false
        glosses.removeAt(index)
        return true
    }

    @Synchronized fun isEmpty(): Boolean = glosses.isEmpty()

    @Synchronized fun clear() = glosses.clear()
}
