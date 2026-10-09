package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import org.junit.Assert.*
import org.junit.Test

class StrictAslPlannerTest {
    private fun asset(id: String, type: AslAnimationAsset.Type, vararg aliases: String) =
        AslAnimationAsset(id, id, "asl_animations/$id.glb", type, aliases.toList() + id.replace('_', ' '))
    private val planner = AslPhrasePlanner(AslAnimationCatalog.fromAssets(listOf(
        asset("hello", AslAnimationAsset.Type.PHRASE, "hi", "hey"),
        asset("here", AslAnimationAsset.Type.WORD),
        asset("thank_you", AslAnimationAsset.Type.PHRASE, "thank you"),
        asset("a", AslAnimationAsset.Type.LETTER),
        asset("b", AslAnimationAsset.Type.LETTER),
        asset("idle", AslAnimationAsset.Type.POSE, "rest"),
    )))
    @Test fun exactPhraseMatchesCaseWhitespaceAndTerminalPunctuation() {
        assertEquals(listOf("thank_you"), planner.plan("  THANK   YOU! ").queue.map { it.id })
        assertEquals(listOf("hello"), planner.plan("Hi").queue.map { it.id })
    }
    @Test fun unknownWordsNeverProduceFragmentsOrSuffixSigns() {
        for (input in listOf("banana", "hi there", "hello here", "hello 123", "hello\u4f60\u597d", "a", "rest", "?!")) {
            val plan = planner.plan(input)
            assertFalse(input, plan.isPlayable)
            assertEquals(listOf(input), plan.unsupportedTokens)
        }
    }
    @Test fun blankInputProducesNoPlaybackAndNoUnsupportedWarning() {
        assertTrue(planner.plan(null).queue.isEmpty())
        assertTrue(planner.plan("  ").unsupportedTokens.isEmpty())
    }
}
