package com.example.apphear.perceptionvnext

import com.example.apphear.pipeline.recognition.SentenceBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Phase 1 word-commit gate (F-001). These tests prove the gate's BEHAVIOR (accept / reject / uncertain,
 * no commit on non-ACCEPT, recovery, duplicate protection). They are not accuracy evidence: the
 * thresholds' evidence is the held-out-signer analysis in docs/PHASE_1_RECOGNITION_RELIABILITY.md.
 */
class PhoneCommitGateTest {
    private val stable = PhoneRecognitionConfiguration.STABLE.commitPolicy() // floor 0.55 + hand invariant
    private val glosses = List(236) { "G$it" }.toMutableList().apply {
        this[0] = "HELLO"; this[1] = "HOME"; this[2] = "STAND2"; this[3] = "HOSPITAL1"; this[4] = "TABLE"
    }

    /** A valid 236-way distribution with an explicit top-1 / top-2 and the remainder spread evenly. */
    private fun probs(top: Int, p1: Float, second: Int = (top + 1) % 236, p2: Float = 0f): FloatArray {
        val out = FloatArray(236) { (1f - p1 - p2) / 234f }
        out[top] = p1
        out[second] = p2
        return out
    }

    private fun top5(p: FloatArray) = p.indices.sortedWith(compareByDescending<Int> { p[it] }.thenBy { it })
        .take(5).toIntArray()

    private fun decide(c: PhoneEventCommitter, id: Int, p: FloatArray, hand: Double = 1.0) =
        c.decide(id, p, top5(p), glosses, hand)

    // ---- the pure policy -------------------------------------------------------------------------

    @Test fun highConfidenceValidRecognitionIsAcceptedAndCommitted() {
        val sentence = SentenceBuilder()
        val committer = PhoneEventCommitter(stable, sentence)
        val result = decide(committer, 1, probs(0, 0.99f, 1, 0.005f))
        assertEquals(CommitOutcome.ACCEPT, result.decision.outcome)
        assertEquals("HELLO", result.committed!!.gloss)
        assertEquals(0, result.committed!!.classId)
        assertEquals("HELLO", sentence.text())
    }

    @Test fun lowConfidenceIsUncertainAndNothingIsCommitted() {
        val sentence = SentenceBuilder()
        val result = decide(PhoneEventCommitter(stable, sentence), 1, probs(2, 0.30f, 3, 0.10f))
        assertEquals(CommitOutcome.UNCERTAIN, result.decision.outcome)
        assertEquals("TOP1_BELOW_FLOOR", result.decision.reason)
        assertNull(result.committed)
        assertTrue(sentence.isEmpty())
    }

    @Test fun ambiguousTop1Top2IsUncertain() {
        // 0.41 vs 0.40: a near-tie. Not committable even though top-1 is technically the argmax.
        val sentence = SentenceBuilder()
        val result = decide(PhoneEventCommitter(stable, sentence), 1, probs(0, 0.41f, 1, 0.40f))
        assertEquals(CommitOutcome.UNCERTAIN, result.decision.outcome)
        assertTrue(sentence.isEmpty())
    }

    @Test fun anyAcceptedEventHasAStrictlyDominantTop1ForFloorsAtOrAboveHalf() {
        // With a floor >= 0.5 a near-tie cannot be accepted: p2 <= 1 - p1 < p1. (So no separate margin
        // rule is needed for the calibrated floors 0.55 and 0.75.)
        for (policy in listOf(stable, PhoneRecognitionConfiguration.EXPERIMENTAL.commitPolicy())) {
            var p1 = 0.0f
            while (p1 <= 1.0f) {
                val p2 = (1f - p1).coerceAtMost(p1)
                val decision = policy.evaluate(PhoneCommitEvidence(p1, p2, 1.0))
                if (decision.committed) assertTrue("p1=$p1 p2=$p2", p1 > p2)
                p1 += 0.01f
            }
        }
    }

    @Test fun floorIsInclusiveAndJustBelowIsWithheld() {
        val at = stable.evaluate(PhoneCommitEvidence(0.55f, 0.20f, 1.0))
        val below = stable.evaluate(PhoneCommitEvidence(0.5499f, 0.20f, 1.0))
        assertEquals(CommitOutcome.ACCEPT, at.outcome)
        assertEquals(CommitOutcome.UNCERTAIN, below.outcome)
    }

    @Test fun nonSignWithNoHandEvidenceIsRejectedEvenWhenTheRecognizerIsConfident() {
        // Recorded case (docs/audit ledger, SEP27 confirmed non-sign): HELLO at p1=0.703 with zero accepted
        // hand observations in the span. The probability floor alone would have committed it.
        val sentence = SentenceBuilder()
        val result = decide(PhoneEventCommitter(stable, sentence), 1, probs(0, 0.703f, 1, 0.03f), hand = 0.0)
        assertEquals(CommitOutcome.REJECT, result.decision.outcome)
        assertEquals("NO_HAND_EVIDENCE_IN_SPAN", result.decision.reason)
        assertTrue(sentence.isEmpty())
    }

    @Test fun rejectionTakesPrecedenceOverUncertainty() {
        val decision = stable.evaluate(PhoneCommitEvidence(0.10f, 0.05f, 0.0))
        assertEquals(CommitOutcome.REJECT, decision.outcome)
    }

    @Test fun invalidRecognizerOutputIsRejected() {
        listOf(
            PhoneCommitEvidence(Float.NaN, 0.1f, 1.0),
            PhoneCommitEvidence(1.5f, 0.1f, 1.0),
            PhoneCommitEvidence(0.6f, 0.7f, 1.0), // top-2 above top-1 is impossible
            PhoneCommitEvidence(0.9f, 0.05f, Double.NaN),
        ).forEach { assertEquals(CommitOutcome.REJECT, stable.evaluate(it).outcome) }
    }

    @Test fun disabledPolicyReproducesThePreviousCommitEveryEventBehavior() {
        val sentence = SentenceBuilder()
        val committer = PhoneEventCommitter(PhoneCommitPolicy.DISABLED, sentence)
        val result = decide(committer, 1, probs(3, 0.05f, 4, 0.04f), hand = 0.0)
        assertEquals(CommitOutcome.ACCEPT, result.decision.outcome)
        assertEquals("GATE_DISABLED", result.decision.reason)
        assertEquals("HOSPITAL1", sentence.text())
    }

    @Test fun calibratedFloorsAreTheRepoSelectedOperatingPointsAndBlendHasNone() {
        assertEquals(0.55, PhoneRecognitionConfiguration.STABLE.commitPolicy().minTop1Probability!!, 0.0)
        assertEquals(0.75, PhoneRecognitionConfiguration.EXPERIMENTAL.commitPolicy().minTop1Probability!!, 0.0)
        for (blend in listOf(
            PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND,
            PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND_02,
        )) {
            val policy = blend.commitPolicy()
            assertNull("no calibration exists for ${blend.name}", policy.minTop1Probability)
            assertTrue(policy.requireHandEvidenceInSpan)
        }
    }

    @Test fun aCorrectButLowConfidenceWordIsWithheldThisIsTheMeasuredCostOfTheGate() {
        // Recorded case (SEP23 representative HOME, correct, p1=0.531): withheld at the 0.55 floor.
        val result = decide(PhoneEventCommitter(stable, SentenceBuilder()), 1, probs(1, 0.531f, 0, 0.18f))
        assertEquals(CommitOutcome.UNCERTAIN, result.decision.outcome)
    }

    // ---- hand-span evidence ------------------------------------------------------------------------

    private fun observation(index: Int, hand: Boolean) = PhoneRawObservation(
        sourceIndex = index, timestampMs = index * 66.7, sourceWidth = 480, sourceHeight = 360,
        handXy = Array(2) { FloatArray(42) }, handJointValid = Array(2) { BooleanArray(21) },
        handProposalSupport = Array(2) { FloatArray(21) }, handPresence = floatArrayOf(0f, 0f),
        handObserved = booleanArrayOf(hand, false), handProposalPresent = booleanArrayOf(hand, false),
        handRoiCenterSide = Array(2) { FloatArray(3) }, bodyXy = FloatArray(16), bodySupport = FloatArray(8),
        bodyValid = BooleanArray(8), bodyAvailable = true,
    )

    @Test fun handSpanFractionCountsOnlyObservationsInsideTheLogicalSpan() {
        // Hands are visible only in the context observations 0..2 and 8..9; the logical span 3..7 has none.
        val obs = (0..9).map { observation(it, hand = it <= 2 || it >= 8) }
        assertEquals(0.0, phoneHandSpanFraction(obs, 3, 7), 0.0)
        assertEquals(1.0, phoneHandSpanFraction(obs, 0, 2), 0.0)
        assertEquals(0.5, phoneHandSpanFraction(obs, 6, 10), 0.0) // observations 6..9 exist; hands at 8 and 9
        val mixed = (0..4).map { observation(it, hand = it % 2 == 0) }
        assertEquals(3.0 / 5.0, phoneHandSpanFraction(mixed, 0, 4), 1e-12)
        assertEquals(0.0, phoneHandSpanFraction(emptyList(), 0, 4), 0.0)
    }

    // ---- full decoder + committer scenarios --------------------------------------------------------

    /** Drives the production decoder and the committer exactly like PhoneProductionSession does. */
    private class Harness(policy: PhoneCommitPolicy, val glosses: List<String>) {
        val sentence = SentenceBuilder()
        private val committer = PhoneEventCommitter(policy, sentence)
        private val producer = PhoneCausalEventProducer(PhoneDecoderConfig())
        private val observations = mutableListOf<PhoneRawObservation>()
        private var index = 0
        val results = mutableListOf<PhoneEventCommitter.Result>()
        var eventsEmitted = 0

        private fun obs(hand: Boolean) = PhoneRawObservation(
            sourceIndex = index, timestampMs = index * 66.6667, sourceWidth = 480, sourceHeight = 360,
            handXy = Array(2) { FloatArray(42) }, handJointValid = Array(2) { BooleanArray(21) },
            handProposalSupport = Array(2) { FloatArray(21) }, handPresence = floatArrayOf(0f, 0f),
            handObserved = booleanArrayOf(hand, false), handProposalPresent = booleanArrayOf(hand, false),
            handRoiCenterSide = Array(2) { FloatArray(3) }, bodyXy = FloatArray(16),
            bodySupport = FloatArray(8), bodyValid = BooleanArray(8), bodyAvailable = true,
        )

        private fun feed(state: Int, hand: Boolean, probabilities: FloatArray?) {
            val o = obs(hand)
            observations.add(o)
            val update = producer.consume(o.timestampMs, state)
            index++
            val event = update.event ?: return
            eventsEmitted++
            val p = checkNotNull(probabilities) { "event emitted but no probabilities scripted" }
            val top5 = p.indices.sortedWith(compareByDescending<Int> { p[it] }.thenBy { it }).take(5).toIntArray()
            val handFraction = phoneHandSpanFraction(
                observations, event.logicalActiveStartIndex, event.logicalActiveEndIndex,
            )
            results.add(committer.decide(event.eventId, p, top5, glosses, handFraction))
        }

        /** A full sign episode: ACTIVE x[activeObs], POST x5 (>= 267 ms), then PRE x8 (>= 400 ms re-arm). */
        fun episode(activeObs: Int, hand: Boolean, probabilities: FloatArray?) {
            repeat(activeObs) { feed(PhoneCausalEventProducer.ACTIVE_SIGN, hand, probabilities) }
            repeat(5) { feed(PhoneCausalEventProducer.POST_RECOVERY, false, probabilities) }
            repeat(8) { feed(PhoneCausalEventProducer.PRE_IDLE, false, probabilities) }
        }
    }

    @Test fun incompleteSignEpisodeNeverReachesTheGateAndTheNextValidSignStillCommits() {
        val h = Harness(stable, glosses)
        h.episode(activeObs = 2, hand = true, probabilities = null) // 67 ms of ACTIVE < 133 ms minimum
        assertEquals("decoder must discard it before any recognition", 0, h.eventsEmitted)
        assertTrue(h.sentence.isEmpty())
        h.episode(activeObs = 8, hand = true, probabilities = probs(0, 0.97f, 1, 0.01f))
        assertEquals(1, h.eventsEmitted)
        assertEquals("HELLO", h.sentence.text())
    }

    @Test fun nonSignEpisodeWithoutHandsProducesNoWordAndRecognitionContinues() {
        val h = Harness(stable, glosses)
        h.episode(activeObs = 8, hand = false, probabilities = probs(0, 0.99f, 1, 0.005f)) // confident but handless
        assertEquals(CommitOutcome.REJECT, h.results.single().decision.outcome)
        assertTrue(h.sentence.isEmpty())
        h.episode(activeObs = 8, hand = true, probabilities = probs(1, 0.90f, 0, 0.05f))
        assertEquals(2, h.results.size)
        assertEquals(CommitOutcome.ACCEPT, h.results[1].decision.outcome)
        assertEquals("HOME", h.sentence.text())
    }

    @Test fun recoveryAfterAnUncertainEpisodeAndValidRecognitionFollowingIt() {
        val h = Harness(stable, glosses)
        h.episode(8, hand = true, probabilities = probs(2, 0.35f, 3, 0.30f)) // e.g. general movement -> STAND2
        h.episode(8, hand = true, probabilities = probs(0, 0.95f, 1, 0.02f))
        assertEquals(
            listOf(CommitOutcome.UNCERTAIN, CommitOutcome.ACCEPT),
            h.results.map { it.decision.outcome },
        )
        assertEquals("HELLO", h.sentence.text())
        assertEquals("event ids keep advancing across a rejected episode", 2, h.results.size)
    }

    @Test fun inconsistentConsecutiveEventsAreJudgedIndependentlyAndARejectedEventLeavesNoTrace() {
        val h = Harness(stable, glosses)
        h.episode(8, true, probs(0, 0.95f, 1, 0.02f)) // HELLO accepted
        h.episode(8, true, probs(1, 0.40f, 4, 0.38f)) // contradictory low-confidence word withheld
        h.episode(8, true, probs(4, 0.90f, 0, 0.05f)) // TABLE accepted
        assertEquals("HELLO TABLE", h.sentence.text())
        assertEquals(
            listOf(CommitOutcome.ACCEPT, CommitOutcome.UNCERTAIN, CommitOutcome.ACCEPT),
            h.results.map { it.decision.outcome },
        )
    }

    @Test fun duplicateRecognitionIsPrevented() {
        // Same event id twice (accepted or not) is a hard error; and the existing sentence-level
        // de-duplication still collapses a legitimately repeated word.
        val sentence = SentenceBuilder()
        val committer = PhoneEventCommitter(stable, sentence)
        decide(committer, 1, probs(0, 0.95f, 1, 0.02f))
        assertThrows(IllegalArgumentException::class.java) { decide(committer, 1, probs(1, 0.95f, 0, 0.02f)) }
        decide(committer, 2, probs(2, 0.30f, 3, 0.10f)) // withheld, but id 2 is now consumed
        assertThrows(IllegalArgumentException::class.java) { decide(committer, 2, probs(1, 0.95f, 0, 0.02f)) }
        decide(committer, 3, probs(0, 0.96f, 1, 0.02f)) // HELLO again after the withheld event
        assertEquals("HELLO", sentence.text())
    }

    @Test fun resetAllowsANewCameraGenerationToRestartEventIds() {
        val sentence = SentenceBuilder()
        val committer = PhoneEventCommitter(stable, sentence)
        decide(committer, 1, probs(0, 0.95f, 1, 0.02f))
        committer.reset()
        assertNotNull(decide(committer, 1, probs(1, 0.95f, 0, 0.02f)).committed)
        assertEquals("HELLO HOME", sentence.text())
    }

    @Test fun screenReadinessKeepsInitializingOffTheScreenAfterAWithheldEventButNotWhileSigning() {
        assertTrue(phoneDisplayReady(PhoneDecoderState.IDLE, holdingCommittedWord = false))
        // Withheld event: re-arming with no held word -> display as ready (idle placeholder).
        assertTrue(phoneDisplayReady(PhoneDecoderState.EVENT_EMITTED_WAIT_REARM, holdingCommittedWord = false))
        // Accepted event: re-arming while the committed word is shown -> unchanged previous behaviour.
        assertFalse(phoneDisplayReady(PhoneDecoderState.EVENT_EMITTED_WAIT_REARM, holdingCommittedWord = true))
        for (s in listOf(PhoneDecoderState.ACTIVE_CANDIDATE, PhoneDecoderState.PRE_GAP, PhoneDecoderState.POST_CANDIDATE)) {
            assertFalse(phoneDisplayReady(s, holdingCommittedWord = false))
        }
    }

    @Test fun uncertainAndRejectedResultsCarryNoCommittedState() {
        val uncertain = decide(PhoneEventCommitter(stable, SentenceBuilder()), 1, probs(2, 0.2f, 3, 0.1f))
        val rejected = decide(PhoneEventCommitter(stable, SentenceBuilder()), 1, probs(0, 0.9f, 1, 0.05f), 0.0)
        assertFalse(uncertain.decision.committed)
        assertFalse(rejected.decision.committed)
        assertNull(uncertain.committed)
        assertNull(rejected.committed)
    }
}
