package com.example.apphear.contextassist

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PhraseAssistUiStateTest {
    private val first = ConversationTurn(1, ConversationSpeaker.HEARING,
        ConversationSource.TYPED_TEXT, "Where are you going?", 10)
    private val second = first.copy(id = 2, text = "Are you tired?")
    private val reply = ReplyCandidate("I'm going home.", listOf("GO", "HOME"))

    @Test fun predictionsBelongOnlyToCurrentHearingTurn() {
        val state = PhraseAssistUiState().hearingTurn(first)
            .predictions(first.id, listOf(reply))
            .hearingTurn(second)
            .predictions(first.id, listOf(reply))
        assertEquals("Are you tired?", state.hearingText)
        assertEquals(emptyList<String>(), state.possibleReplies)
        assertNull(state.contextSupported)
    }

    @Test fun onlyAcceptedMatcherCandidateBecomesAdvisoryText() {
        val raw = "GO THINK"
        val evidence = listOf(
            RecognitionEvidence(1, 1, "GO", listOf(SignScore("GO", .72f))),
            RecognitionEvidence(2, 2, "THINK", listOf(
                SignScore("THINK", .35f), SignScore("HOME", .33f))),
        )
        val match = PhraseMatcher(PhraseMatchPolicy(1, .6f, .08f, .75f, .02f))
            .interpret(evidence, listOf(reply))
        val evaluation = ShadowEvaluation(raw, evidence, listOf(reply), match, true, ShadowReason.MATCH)
        val displayed = PhraseAssistUiState().hearingTurn(first)
            .predictions(first.id, listOf(reply)).evaluated(first.id, evaluation)
        assertEquals(raw, evaluation.rawSentence)
        assertEquals(listOf("I'm going home."), displayed.possibleReplies)
        assertEquals("I'm going home.", displayed.contextSupported)
        assertNull(displayed.signingStarted().contextSupported)
        assertEquals(listOf("I'm going home."), displayed.signingStarted().possibleReplies)
        assertNull(displayed.hearingTurn(second).contextSupported)
    }

    @Test fun abstainIncompleteAndUnverifiedCandidateNeverDisplayInterpretation() {
        val state = PhraseAssistUiState().hearingTurn(first).predictions(first.id, listOf(reply))
        val raw = "GIFT HOME"
        val unsupported = AssistedInterpretation(listOf("GIFT", "HOME"), listOf("GO", "HOME"),
            "I'm going home.", listOf(1, 2), true)
        val base = ShadowEvaluation(raw, emptyList(), listOf(reply), unsupported, true,
            ShadowReason.INCOMPLETE_EVIDENCE)
        assertNull(state.evaluated(first.id, base).contextSupported)
        assertNull(state.evaluated(first.id, base.copy(reason = ShadowReason.NO_MATCH_OR_AMBIGUOUS)).contextSupported)
        assertNull(state.evaluated(second.id, base.copy(reason = ShadowReason.MATCH)).contextSupported)
        val invented = base.copy(reason = ShadowReason.MATCH, assistedCandidate =
            unsupported.copy(naturalText = "Invented extra claim"))
        assertNull(state.evaluated(first.id, invented).contextSupported)
    }
}
