package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import org.junit.Assert.*
import org.junit.Test

class TextToAslStrictInputTest {
    private fun asset(id: String, type: AslAnimationAsset.Type, vararg aliases: String) =
        AslAnimationAsset(id, id, "asl_animations/$id.glb", type, aliases.toList())
    private val catalog = AslAnimationCatalog.fromAssets(listOf(
        asset("hello", AslAnimationAsset.Type.PHRASE, "hello", "hi"),
        asset("here", AslAnimationAsset.Type.WORD, "here"),
        asset("nice_to_meet_you", AslAnimationAsset.Type.PHRASE, "nice to meet you"),
        asset("a", AslAnimationAsset.Type.LETTER, "a"),
        asset("b", AslAnimationAsset.Type.LETTER, "b"),
        asset("idle", AslAnimationAsset.Type.POSE, "idle", "stand"),
    ))
    private val strict = AslPhrasePlanner(catalog, strictPhraseMode = true)

    @Test fun unknownWordsNeverBecomePartialLettersOrSuffixSigns() {
        for (input in listOf("banana", "hi there", "hello cat", "hello here", "hello123",
            "hello\u4f60\u597d", "h'ello", "hello?cat", "nice_to_meet_you", "stand")) {
            val plan = strict.plan(input)
            assertTrue(input, plan.queue.isEmpty())
            assertEquals(input, listOf(input), plan.unsupportedTokens)
        }
    }
    @Test fun supportedPhraseAndTerminalPunctuationSelectOneClip() {
        assertEquals(listOf("nice_to_meet_you"), strict.plan("  Nice to meet you! ").queue.map { it.id })
        assertEquals(listOf("hello"), strict.plan("HI").queue.map { it.id })
        assertEquals(listOf("a"), strict.plan("a").queue.map { it.id })
    }
    @Test fun emptyInputAndPunctuationDoNotSelectIdle() {
        assertTrue(strict.plan(" ").unsupportedTokens.isEmpty())
        assertTrue(strict.plan("?!").queue.isEmpty())
        assertEquals(listOf("?!"), strict.plan("?!").unsupportedTokens)
    }
    @Test fun availableAlphabetSupportsOneExplicitLetterButNeverSpellsAnUnknownWord() {
        val letters = mapOf('c' to asset("letter_c", AslAnimationAsset.Type.LETTER))
        val withAlphabet = AslAnimationCatalog.fromAssets(catalog.getAssets(), letters)
        val planner = AslPhrasePlanner(withAlphabet, completeWordFallback = true, strictPhraseMode = true)
        assertEquals(listOf("letter_c"), planner.plan("C").queue.map { it.id })
        assertTrue(planner.plan("cab").queue.isEmpty())
    }
    @Test fun flagOffRetainsTheExistingPlannerContract() {
        assertEquals(listOf("a", "b"), AslPhrasePlanner(catalog).plan("ab").queue.map { it.id })
        assertEquals("nice to meet you", AslTextNormalizer().normalize("Nice, to meet you!"))
    }
}
