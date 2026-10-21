package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.contextassist.SignScore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SentenceRenderingTest {
    private val template = SentenceAssistAssets.template()
    private val prompt = SentenceAssistAssets.prompt()
    private val lexicon = SentenceAssistAssets.lexicon()
    private val validator = SentenceAssistAssets.validator()
    private val plain = PlainGlossRenderer(lexicon)

    private fun event(id: Int, vararg scores: Pair<String, Float>) =
        RecognitionEvidence(id, id * 1_000L, scores.first().first, scores.map { SignScore(it.first, it.second) })

    @Test
    fun promptAssetDeclaresTheResponseContract() {
        val json = SentenceAssistAssets.promptJson()
        assertEquals(PromptTemplate.SCHEMA_VERSION, json["schemaVersion"].asInt)
        val required = json["responseSchema"].asJsonObject["required"].asJsonArray.map { it.asString }
        assertEquals(listOf("sentence", "substitutions"), required)
        assertTrue(template.model.isNotBlank())
    }

    @Test
    fun promptWithoutEvidenceListsSignsAndForbidsSubstitution() {
        val input = prompt.input(RenderRequest(SignedTurn(listOf("HELLO", "HOW1"))))
        assertTrue(input.contains("1. HELLO = \"hello\"\n2. HOW1 = \"how\""))
        assertTrue(input.contains(template.noHearingContext))
        assertTrue(input.contains(template.substitutionRuleWithoutAlternatives))
        assertFalse(input.contains("{{"))
    }

    @Test
    fun promptCarriesHearingContextVerbatim() {
        val input = prompt.input(RenderRequest(SignedTurn(listOf("GOOD")), "  How are you?  "))
        assertTrue(input.contains("\nHow are you?\n"))
    }

    @Test
    fun promptOffersOnlyAlternativesTheValidatorWouldAccept() {
        val turn = SignedTurn(listOf("HOT", "HELLO"), listOf(
            event(1, "HOT" to 0.50f, "GOOD" to 0.45f, "SICK" to 0.02f),
            event(2, "HELLO" to 0.95f, "BYE" to 0.90f)))
        val input = prompt.input(RenderRequest(turn))
        assertTrue(input.contains("1. HOT = \"hot\" (alternatives: GOOD = \"good\")"))
        assertTrue("Confident sign offers no alternatives", input.contains("2. HELLO = \"hello\"\n"))
        assertFalse(input.contains("SICK"))
        assertTrue(input.contains(template.substitutionRuleWithAlternatives.replace("{{MAX_CHANGES}}", "1")))
    }

    @Test
    fun allConfidentEvidenceUsesTheNoSubstitutionRule() {
        val turn = SignedTurn(listOf("HELLO"), listOf(event(1, "HELLO" to 0.95f, "BYE" to 0.02f)))
        assertTrue(prompt.input(RenderRequest(turn)).contains(template.substitutionRuleWithoutAlternatives))
    }

    @Test
    fun plainFallbackIsGroundedForEveryGloss() {
        for (gloss in lexicon.glosses) {
            val turn = SignedTurn(listOf(gloss))
            val result = validator.validate(turn, plain.plain(turn))
            assertTrue("$gloss -> ${plain.plain(turn).sentence}: $result", result is GroundingResult.Accepted)
        }
    }

    @Test
    fun plainFallbackKeepsSigningOrderAndMarksQuestions() {
        val turn = SignedTurn(listOf("HELLO", "GOOD", "MORNING", "YOU", "HOW1"))
        assertEquals("Hello good morning you how?", plain.plain(turn).sentence)
        assertTrue(validator.validate(turn, plain.plain(turn)) is GroundingResult.Accepted)
        assertEquals("Do not know.", plain.plain(SignedTurn(listOf("DONTKNOW"))).sentence)
        assertEquals("", plain.plain(SignedTurn(emptyList())).sentence)
    }

    @Test
    fun mapperConvertsOneBasedSignNumbersAndRejectsMalformedReplies() {
        val raw = RenderingMapper.RawSubstitution(1, "GOOD")
        assertEquals(Rendering("I'm good.", listOf(Substitution(0, "GOOD"))),
            RenderingMapper.map(" I'm good. ", listOf(raw)))
        assertEquals(Rendering("Hi.", emptyList()), RenderingMapper.map("Hi.", emptyList()))
        assertNull(RenderingMapper.map(null, emptyList()))
        assertNull(RenderingMapper.map("  ", emptyList()))
        assertNull(RenderingMapper.map("Hi.", null))
        assertNull(RenderingMapper.map("Hi.", listOf(RenderingMapper.RawSubstitution(0, "GOOD"))))
        assertNull(RenderingMapper.map("Hi.", listOf(RenderingMapper.RawSubstitution(null, "GOOD"))))
        assertNull(RenderingMapper.map("Hi.", listOf(RenderingMapper.RawSubstitution(1, " "))))
    }
}
