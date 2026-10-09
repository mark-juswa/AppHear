package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import org.junit.Assert.*
import org.junit.Test

class TextToAslStrictInputTest {
    private fun asset(id: String, type: AslAnimationAsset.Type, vararg aliases: String) =
        AslAnimationAsset(id, id, "asl_animations/$id.glb", type, aliases.toList())
    private val catalog = AslAnimationCatalog.fromAssets(listOf(
        asset("hello", AslAnimationAsset.Type.PHRASE, "hello", "hi", "hey"),
        asset("beautiful", AslAnimationAsset.Type.WORD, "beautiful"),
        asset("thank_you", AslAnimationAsset.Type.PHRASE, "thank you", "thanks"),
        asset("nice_to_meet_you", AslAnimationAsset.Type.PHRASE, "nice to meet you"),
        asset("a", AslAnimationAsset.Type.LETTER, "a"),
        asset("b", AslAnimationAsset.Type.LETTER, "b"),
        asset("idle", AslAnimationAsset.Type.POSE, "idle", "stand")))
    private val planner = AslPhrasePlanner(catalog, dictionarySequenceMode = true)

    @Test fun supportedWordsCombineInTheirInputOrder() {
        for (input in listOf("hello beautiful", "HELLO BEAUTIFUL", "hello, beautiful!", "  Hello   beautiful  ")) {
            val plan = planner.plan(input)
            assertEquals(input, listOf("hello", "beautiful"), plan.queue.map { it.id })
            assertTrue(plan.unsupportedTokens.isEmpty())
            assertEquals(TextToAslPlan.Mode.WORD_SEQUENCE, plan.mode)
        }
        assertEquals(listOf("hello"), planner.plan("hello").queue.map { it.id })
        assertEquals(listOf("beautiful"), planner.plan("beautiful").queue.map { it.id })
    }
    @Test fun completePhraseAndLongestEmbeddedPhraseTakePriority() {
        val exact = planner.plan("thank you")
        assertEquals(listOf("thank_you"), exact.queue.map { it.id })
        assertEquals(TextToAslPlan.Mode.DICTIONARY_ENTRY, exact.mode)
        assertEquals(listOf("hello", "thank_you", "beautiful"), planner.plan("hello thank you beautiful").queue.map { it.id })
        assertEquals(listOf("nice_to_meet_you"), planner.plan("Nice to meet you!").queue.map { it.id })
    }
    @Test fun unknownWordsAreReportedWholeWithoutDiscardingSupportedWords() {
        val plan = planner.plan("hello unknownword beautiful")
        assertEquals(listOf("hello", "beautiful"), plan.queue.map { it.id })
        assertEquals(listOf("unknownword"), plan.unsupportedTokens)
        for (input in listOf("banana", "hello123", "hello\u4f60\u597d", "stand")) {
            assertTrue(input, planner.plan(input).queue.isEmpty())
            assertEquals(input, listOf(input), planner.plan(input).unsupportedTokens)
        }
    }
    @Test fun repeatedSignsRemainDistinctQueueItems() {
        assertEquals(listOf("hello", "hello", "beautiful"), planner.plan("hello hello beautiful").queue.map { it.id })
        assertEquals(planner.plan("HELLO BEAUTIFUL"), planner.plan("HELLO BEAUTIFUL"))
    }
    @Test fun noUnknownWordIsAutomaticallyFingerspelled() {
        val letters = mapOf('c' to asset("letter_c", AslAnimationAsset.Type.LETTER))
        val withAlphabet = AslAnimationCatalog.fromAssets(catalog.getAssets(), letters)
        val sequence = AslPhrasePlanner(withAlphabet, completeWordFallback = true, dictionarySequenceMode = true)
        assertEquals(listOf("letter_c"), sequence.plan("C").queue.map { it.id })
        assertTrue(sequence.plan("cab").queue.isEmpty())
        assertEquals(listOf("cab"), sequence.plan("cab").unsupportedTokens)
    }
    @Test fun punctuationOnlyAndEmptyInputNeverSelectThePose() {
        assertTrue(planner.plan(" ").queue.isEmpty())
        assertTrue(planner.plan("?!").queue.isEmpty())
    }
    @Test fun ambiguousNormalizedAliasesAreRejected() {
        val ambiguous = AslAnimationCatalog.fromAssets(listOf(
            asset("one", AslAnimationAsset.Type.WORD, "don't"), asset("two", AslAnimationAsset.Type.WORD, "dont")))
        assertThrows(IllegalArgumentException::class.java) {
            AslPhrasePlanner(ambiguous, dictionarySequenceMode = true).plan("dont")
        }
    }
    @Test fun flagOffRetainsTheExistingPlannerContract() {
        assertEquals(listOf("a", "b"), AslPhrasePlanner(catalog).plan("ab").queue.map { it.id })
        assertEquals("nice to meet you", AslTextNormalizer().normalize("Nice, to meet you!"))
    }
}
