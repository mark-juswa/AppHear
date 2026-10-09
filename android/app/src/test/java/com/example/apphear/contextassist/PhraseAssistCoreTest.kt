package com.example.apphear.contextassist

import com.example.apphear.pipeline.recognition.SentenceBuilder
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.delay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PhraseAssistCoreTest {
    private val policy = PhraseMatchPolicy(1, 0.60f, 0.08f, 0.75f, 0.02f)
    private val matcher = PhraseMatcher(policy)

    @Test fun topFiveEvidenceKeepsExistingTopOneAndScores() {
        val scores = floatArrayOf(0.33f, 0.35f, 0.10f)
        val evidence = RecognitionEvidence.fromExistingTop5(7, 1000L, intArrayOf(1, 0, 2),
            scores, listOf("HOME", "THINK", "KNOW"))
        assertEquals("THINK", evidence.originalGloss)
        assertEquals(listOf("THINK", "HOME", "KNOW"), evidence.topK.map { it.gloss })
        assertEquals(0.33f, evidence.topK[1].score)
    }

    @Test fun supportedAmbiguousPhraseCanWinWithoutChangingRawHistory() {
        val events = listOf(
            event(1, "GO", "GO" to 0.72f, "COME" to 0.13f),
            event(2, "THINK", "THINK" to 0.35f, "HOME" to 0.33f))
        val result = matcher.interpret(events, listOf(
            ReplyCandidate("I'm going home.", listOf("GO", "HOME")),
            ReplyCandidate("I'm going to school.", listOf("GO", "SCHOOL"))))
        assertTrue(result.matched)
        assertEquals(listOf("GO", "THINK"), result.rawGlosses)
        assertEquals(listOf("GO", "HOME"), result.assistedGlosses)
        assertEquals("I'm going home.", result.naturalText)
        assertEquals(listOf(1, 2), result.eventIds)
        assertEquals(events, result.evidence)
    }

    @Test fun contradictoryVisualEvidenceForcesRawFallback() {
        val result = matcher.interpret(listOf(event(1, "HOSPITAL1",
            "HOSPITAL1" to 0.91f, "HOME" to 0.01f)),
            listOf(ReplyCandidate("Home.", listOf("HOME"))))
        assertFalse(result.matched)
        assertEquals("HOSPITAL1", result.naturalText)
    }

    @Test fun noCandidateOrMissingSignDoesNotInventPhrase() {
        val events = listOf(event(1, "GO", "GO" to 0.7f),
            event(2, "NEED", "NEED" to 0.8f))
        assertFalse(matcher.interpret(events, emptyList()).matched)
        assertFalse(matcher.interpret(events,
            listOf(ReplyCandidate("I'm going home.", listOf("GO", "HOME")))).matched)
        assertFalse(matcher.interpret(events.take(1),
            listOf(ReplyCandidate("I'm going home.", listOf("GO", "HOME")))).matched)
    }

    @Test fun hypotheticalMatchCannotMutateRawSentenceBuilder() {
        val rawSentence = SentenceBuilder()
        rawSentence.add("GO")
        rawSentence.add("THINK")
        val evidence = listOf(event(1, "GO", "GO" to 0.72f),
            event(2, "THINK", "THINK" to 0.35f, "HOME" to 0.33f))
        val prediction = ReplyCandidate("I'm going home.", listOf("GO", "HOME"))
        val candidate = matcher.interpret(evidence, listOf(prediction))
        val record = ShadowEvaluation(rawSentence.text(), evidence, listOf(prediction),
            candidate, candidate.assistedGlosses != candidate.rawGlosses, ShadowReason.MATCH)
        assertEquals("GO THINK", rawSentence.text())
        assertEquals("GO THINK", record.rawSentence)
        assertEquals(listOf("GO", "THINK"), record.rawEventGlosses)
        assertEquals(listOf("GO", "HOME"), record.assistedCandidate?.assistedGlosses)
        assertTrue(record.wouldChangeRaw)
    }

    @Test fun unsupportedAndMalformedConceptsAreRejected() {
        val valid = ReplyCandidate("I'm good.", listOf("GOOD"))
        assertEquals(listOf(valid), ReplyCandidateValidator.validate(listOf(
            ReplyCandidate("Unseen.", listOf("FINE")),
            ReplyCandidate("", listOf("GOOD")),
            valid,
            ReplyCandidate("Duplicate.", listOf("GOOD"))), setOf("GOOD")))
    }

    @Test fun naturalEnglishGrammarIsNotRequiredToBeARecognizerLabel() {
        val candidate = ReplyCandidate("I'm tired.", listOf("TIRED"))
        assertEquals(listOf(candidate), ReplyCandidateValidator.validate(listOf(candidate), setOf("TIRED")))
        assertTrue(ReplyCandidateValidator.validate(listOf(
            ReplyCandidate("I'm tired.", listOf("I", "TIRED"))), setOf("TIRED")).isEmpty())
    }

    @Test fun duplicateEventAndNavigationClearDoNotCarryEvidence() {
        val buffer = SigningTurnBuffer()
        assertTrue(buffer.add(event(1, "GO", "GO" to 0.5f)))
        assertFalse(buffer.add(event(1, "GO", "GO" to 0.5f)))
        assertEquals(1, buffer.snapshot().size)
        buffer.clear()
        assertTrue(buffer.snapshot().isEmpty())
        assertTrue(buffer.add(event(1, "HOME", "HOME" to 0.5f)))
    }

    @Test fun boundedBufferMarksIncompleteLongTurn() {
        val buffer = SigningTurnBuffer(1)
        buffer.add(event(1, "GO", "GO" to 0.5f))
        buffer.add(event(2, "HOME", "HOME" to 0.5f))
        assertTrue(buffer.overflowed)
        buffer.clear()
        assertFalse(buffer.overflowed)
    }

    @Test fun latePredictionCannotOverwriteNewHearingTurn() {
        val context = ConversationContext(2)
        val first = context.add(ConversationSpeaker.HEARING, ConversationSource.TYPED_TEXT, "How are you?", 1)
        val second = context.add(ConversationSpeaker.HEARING, ConversationSource.SPEECH, "Where go?", 2)
        assertFalse(context.setReplies(first.id, listOf(ReplyCandidate("Good.", listOf("GOOD")))))
        assertTrue(context.setReplies(second.id, listOf(ReplyCandidate("Home.", listOf("HOME")))))
        assertEquals("HOME", context.repliesForLatestHearingTurn().single().concepts.single())
        assertEquals(1, context.finishReplyWindow().size)
        assertFalse(context.setReplies(second.id, listOf(ReplyCandidate("Late.", listOf("HOME")))))
        assertTrue(context.repliesForLatestHearingTurn().isEmpty())
        context.add(ConversationSpeaker.DEAF, ConversationSource.SIGN_TO_TEXT, "Home.", 3)
        assertEquals(2, context.snapshot().size)
    }

    @Test fun backgroundSessionClearsRepliesAndRejectsLateProviderResult() {
        val context = ConversationContext()
        val old = context.add(ConversationSpeaker.HEARING, ConversationSource.TYPED_TEXT,
            "Where are you going?", 1)
        assertTrue(context.setReplies(old.id,
            listOf(ReplyCandidate("I'm going home.", listOf("GO", "HOME")))))
        context.clearSession()
        assertTrue(context.snapshot().isEmpty())
        assertTrue(context.repliesForLatestHearingTurn().isEmpty())
        assertFalse(context.setReplies(old.id,
            listOf(ReplyCandidate("Late.", listOf("HOME")))))
        val fresh = context.add(ConversationSpeaker.HEARING, ConversationSource.TYPED_TEXT,
            "Are you tired?", 2)
        assertTrue(fresh.id > old.id)
    }

    @Test fun possibleRepliesRemainVisibleWhileTopFiveEvidenceRanksSupportedPrefixes() {
        val replies = listOf(
            ReplyCandidate("I'm going to school.", listOf("GO", "SCHOOL")),
            ReplyCandidate("I'm going to work.", listOf("GO", "WORK")),
            ReplyCandidate("I'm going home.", listOf("GO", "HOME")),
        )
        val first = event(1, "GO", "GO" to 0.72f)
        assertEquals(replies, EvidenceAwareReplies.visible(replies, emptyList(), policy))
        assertEquals(replies, EvidenceAwareReplies.visible(replies, listOf(first), policy))
        assertFalse(matcher.interpret(listOf(first), replies).matched)
        val second = event(2, "THINK", "THINK" to 0.35f, "HOME" to 0.33f)
        assertEquals(listOf(replies.last(), replies.first(), replies[1]),
            EvidenceAwareReplies.visible(replies, listOf(first, second), policy))
        val unsupported = event(2, "GIFT", "GIFT" to 0.91f, "HOME" to 0.01f)
        assertEquals(replies, EvidenceAwareReplies.visible(replies, listOf(first, unsupported), policy))
    }

    @Test fun aSingleVisualAnchorRanksOnlyThePredictionAndNeverMatchesThePhrase() {
        val replies = listOf(
            ReplyCandidate("I'm going to school.", listOf("GO", "SCHOOL")),
            ReplyCandidate("I'm going home.", listOf("GO", "HOME")),
        )
        val home = event(1, "HOME", "HOME" to 0.72f)
        val hints = EvidenceAwareReplies.hints(replies, listOf(home), policy)
        assertEquals("I'm going home.", hints.first().naturalText)
        assertTrue(hints.first().latestSignSupportsAnchor)
        assertFalse(hints.last().latestSignSupportsAnchor)
        assertFalse(matcher.interpret(listOf(home), replies).matched)
        val unsupported = event(2, "GIFT", "GIFT" to 0.91f, "HOME" to 0.01f)
        assertEquals(replies.map { it.naturalText },
            EvidenceAwareReplies.hints(replies, listOf(unsupported), policy).map { it.naturalText })
        assertTrue(EvidenceAwareReplies.hints(replies, listOf(unsupported), policy)
            .none { it.latestSignSupportsAnchor })
    }

    @Test fun fakeProviderPredictsOnlySupportedDemoConcepts() = runBlocking {
        val context = ConversationContext()
        val turn = context.add(ConversationSpeaker.HEARING, ConversationSource.TYPED_TEXT,
            "Where are you going?", 1)
        val allowed = setOf("GO", "HOME", "SCHOOL", "WORK")
        val replies = FakeContextPredictionProvider().predict(PredictionRequest(turn.id,
            context.snapshot(), allowed))
        assertEquals(3, ReplyCandidateValidator.validate(replies, allowed).size)
    }

    @Test fun providerFailureAndTimeoutLeaveRawPathAvailable() = runBlocking {
        val request = PredictionRequest(1, emptyList(), setOf("GOOD"))
        val failed = predictValidated(ContextPredictionProvider { throw IllegalStateException("offline") },
            request, 100)
        val timedOut = predictValidated(ContextPredictionProvider {
            delay(50)
            listOf(ReplyCandidate("Good.", listOf("GOOD")))
        }, request, 1)
        assertTrue(failed.isEmpty())
        assertTrue(timedOut.isEmpty())
        assertFalse(matcher.interpret(listOf(event(1, "GOOD", "GOOD" to 0.9f)), timedOut).matched)
    }

    private fun event(id: Int, original: String, vararg scores: Pair<String, Float>) =
        RecognitionEvidence(id, id.toLong(), original, scores.map { SignScore(it.first, it.second) })
}
