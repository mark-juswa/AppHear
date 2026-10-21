package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.contextassist.SignScore
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ShadowPipelineTest {
    private val lexicon = SentenceAssistAssets.lexicon()
    private val validator = SentenceAssistAssets.validator()

    private fun event(id: Int, vararg scores: Pair<String, Float>) =
        RecognitionEvidence(id, id * 1_000L, scores.first().first, scores.map { SignScore(it.first, it.second) })

    private fun pipeline(timeoutMs: Long = 1_000L, renderer: SentenceRenderer) =
        ShadowRenderPipeline(renderer, PlainGlossRenderer(lexicon), validator, timeoutMs, System::currentTimeMillis)

    private val tired = RenderRequest(SignedTurn(listOf("TIRED")), "How are you?")

    @Test
    fun assemblerAttachesEvidenceOnlyWhenCompleteAndAligned() {
        val evidence = listOf(event(1, "HELLO" to 0.9f), event(2, "HELLO" to 0.9f), event(3, "GOOD" to 0.9f))
        assertEquals(evidence, SignedTurnAssembler.assemble(" HELLO  GOOD ", evidence, true, 20)?.evidence)
        assertNull(SignedTurnAssembler.assemble("HELLO GOOD", evidence, false, 20)?.evidence)
        assertNull(SignedTurnAssembler.assemble("HELLO GOOD MORNING", evidence, true, 20)?.evidence)
        assertEquals(listOf("HELLO", "GOOD", "MORNING"),
            SignedTurnAssembler.assemble("HELLO GOOD MORNING", evidence, true, 20)?.glosses)
        assertNull(SignedTurnAssembler.assemble("   ", evidence, true, 20))
        assertNull(SignedTurnAssembler.assemble("HELLO GOOD", emptyList(), true, 1))
    }

    @Test
    fun groundedRenderingIsAcceptedAndChosen() = runBlocking {
        val outcome = pipeline { Rendering("I'm tired.") }.run(tired)
        assertEquals(AiStatus.ACCEPTED, outcome.aiStatus)
        assertEquals("I'm tired.", outcome.chosenSentence)
        assertEquals("Tired.", outcome.fallbackSentence)
        assertTrue(outcome.acceptedWords.any { it.source == WordSource.INFERRED_PRONOUN })
    }

    @Test
    fun ungroundedRenderingIsKeptForReviewButFallbackIsChosen() = runBlocking {
        val outcome = pipeline { Rendering("I'm tired because of work.") }.run(tired)
        assertEquals(AiStatus.REJECTED, outcome.aiStatus)
        assertEquals(RejectReason.UNSUPPORTED_WORD, outcome.rejectReason)
        assertEquals("I'm tired because of work.", outcome.aiSentence)
        assertEquals("Tired.", outcome.chosenSentence)
    }

    @Test
    fun missingAnswerAndTimeoutAreDistinguished() = runBlocking {
        assertEquals(AiStatus.UNAVAILABLE, pipeline { null }.run(tired).aiStatus)
        val slow = pipeline(timeoutMs = 50L) { delay(5_000); Rendering("I'm tired.") }.run(tired)
        assertEquals(AiStatus.TIMEOUT, slow.aiStatus)
        assertEquals("Tired.", slow.chosenSentence)
        assertTrue(slow.latencyMs < 2_000)
    }
}
