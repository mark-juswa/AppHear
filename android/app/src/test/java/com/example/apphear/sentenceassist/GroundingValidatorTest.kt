package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.contextassist.SignScore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class GroundingValidatorTest {
    private val validator = SentenceAssistAssets.validator()

    private fun turn(vararg glosses: String) = SignedTurn(glosses.toList())

    private fun event(id: Int, vararg scores: Pair<String, Float>) =
        RecognitionEvidence(id, id * 1_000L, scores.first().first, scores.map { SignScore(it.first, it.second) })

    private fun accepted(turn: SignedTurn, sentence: String, substitutions: List<Substitution> = emptyList()) =
        validator.validate(turn, Rendering(sentence, substitutions)).let {
            assertTrue("Expected acceptance, got $it", it is GroundingResult.Accepted)
            it as GroundingResult.Accepted
        }

    private fun rejected(turn: SignedTurn, sentence: String, substitutions: List<Substitution> = emptyList()) =
        validator.validate(turn, Rendering(sentence, substitutions)).let {
            assertTrue("Expected rejection, got $it", it is GroundingResult.Rejected)
            it as GroundingResult.Rejected
        }

    @Test
    fun naturalSentenceKeepsEverySignAndAddsOnlyGrammar() {
        val result = accepted(turn("HELLO", "GOOD", "MORNING", "YOU", "HOW1"), "Hello, good morning! How are you?")
        assertEquals(0, result.inferredPronouns)
        assertEquals(WordSource.GRAMMAR, result.words.single { it.text == "are" }.source)
        assertEquals("HOW1", result.words.single { it.text == "how" }.gloss)
    }

    @Test
    fun oneInferredSubjectPronounIsAllowedAndLabelled() {
        val result = accepted(turn("TIRED"), "I'm tired.")
        assertEquals(listOf(WordSource.INFERRED_PRONOUN, WordSource.GRAMMAR, WordSource.SIGNED),
            result.words.map { it.source })
    }

    @Test
    fun inferringMoreThanThePolicyLimitIsRejected() {
        assertEquals(RejectReason.TOO_MANY_INFERRED, rejected(turn("WANT2", "GO"), "I want you to go.").reason)
    }

    @Test
    fun droppingASignIsRejected() {
        val result = rejected(turn("HELLO", "GOOD"), "Hello!")
        assertEquals(RejectReason.MISSING_SIGN, result.reason)
        assertEquals("GOOD", result.detail)
    }

    @Test
    fun addingUnsignedContentIsRejected() {
        assertEquals("after", rejected(turn("GO", "HOME"), "I'm going home after work.").detail)
        assertEquals("my", rejected(turn("FATHER", "SICK"), "My father is sick.").detail)
    }

    @Test
    fun negationNeedsASignedNegation() {
        assertEquals("not", rejected(turn("LIKE"), "I don't like it.").detail)
        accepted(turn("NO", "LIKE"), "I don't like it.")
        accepted(turn("CANNOT", "GO"), "I can't go.")
        accepted(turn("CANNOT", "GO"), "I cannot go.")
    }

    @Test
    fun multiWordFormsMatchAsOneSign() {
        val result = accepted(turn("DONTKNOW"), "I don't know.")
        assertEquals(GroundedWord("do not know", WordSource.SIGNED, "DONTKNOW"), result.words.last())
    }

    @Test
    fun inflectionsAndSharedFormsAreGrounded() {
        accepted(turn("GO", "SCHOOL", "YESTERDAY"), "I went to school yesterday.")
        accepted(turn("PERSON", "MANY"), "Many people.")
    }

    @Test
    fun boundedTopFiveSubstitutionIsAcceptedAndLabelled() {
        val turn = SignedTurn(listOf("HOT"), listOf(event(1, "HOT" to 0.50f, "GOOD" to 0.45f, "SICK" to 0.02f)))
        val result = accepted(turn, "I'm good.", listOf(Substitution(0, "GOOD")))
        assertEquals(GroundedWord("good", WordSource.SUBSTITUTED, "GOOD"), result.words.last())
        // The replaced word is no longer signed, so it cannot appear.
        assertEquals("hot", rejected(turn, "I'm hot.", listOf(Substitution(0, "GOOD"))).detail)
    }

    @Test
    fun substitutionsOutsideContextAssistBoundsAreRejected() {
        val confident = SignedTurn(listOf("HOT"), listOf(event(1, "HOT" to 0.80f, "GOOD" to 0.75f)))
        val farApart = SignedTurn(listOf("HOT"), listOf(event(1, "HOT" to 0.55f, "GOOD" to 0.40f)))
        val absent = SignedTurn(listOf("HOT"), listOf(event(1, "HOT" to 0.50f, "SICK" to 0.45f)))
        for (turn in listOf(confident, farApart, absent)) {
            assertEquals(RejectReason.INVALID_SUBSTITUTION,
                rejected(turn, "I'm good.", listOf(Substitution(0, "GOOD"))).reason)
        }
        val two = SignedTurn(listOf("HOT", "WORK"), listOf(
            event(1, "HOT" to 0.50f, "GOOD" to 0.45f), event(2, "WORK" to 0.50f, "HOME" to 0.45f)))
        assertEquals(RejectReason.INVALID_SUBSTITUTION, rejected(two, "Good home.",
            listOf(Substitution(0, "GOOD"), Substitution(1, "HOME"))).reason)
    }

    @Test
    fun substitutionWithoutEvidenceIsRejected() {
        assertEquals(RejectReason.SUBSTITUTION_WITHOUT_EVIDENCE,
            rejected(turn("HOT"), "I'm good.", listOf(Substitution(0, "GOOD"))).reason)
    }

    @Test
    fun evidenceMustLineUpWithTheRecognizedWords() {
        SignedTurn(listOf("HELLO", "GOOD"), listOf(
            event(1, "HELLO" to 0.9f), event(2, "HELLO" to 0.9f), event(3, "GOOD" to 0.9f)))
        assertThrows(IllegalArgumentException::class.java) {
            SignedTurn(listOf("HELLO", "GOOD"), listOf(event(1, "HELLO" to 0.9f)))
        }
    }

    @Test
    fun malformedInputsAreRejected() {
        assertEquals(RejectReason.NO_SIGNS, rejected(turn(), "Hello.").reason)
        assertEquals(RejectReason.UNKNOWN_GLOSS, rejected(turn("NOTAGLOSS"), "Hello.").reason)
        assertEquals(RejectReason.EMPTY_SENTENCE, rejected(turn("HELLO"), "?!").reason)
        assertEquals(RejectReason.TOO_LONG, rejected(turn("HELLO"), "Hello " + "hello ".repeat(40)).reason)
        assertEquals(RejectReason.TOO_MANY_SIGNS, rejected(SignedTurn(List(21) { "HELLO" }), "Hello.").reason)
    }

    @Test
    fun tokenizerExpandsContractionsAndIgnoresPunctuation() {
        assertEquals(listOf("i", "am", "do", "not", "can", "not", "will", "not", "can", "not", "what", "'s"),
            SentenceTokenizer.tokens("I’m DON'T can't won't cannot... What's?"))
    }
}
