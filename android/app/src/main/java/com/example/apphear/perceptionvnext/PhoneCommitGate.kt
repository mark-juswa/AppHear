package com.example.apphear.perceptionvnext

import com.example.apphear.pipeline.recognition.RecognitionState
import com.example.apphear.pipeline.recognition.SentenceBuilder

/**
 * Word-commit gate (Phase 1, finding F-001). Decides whether a completed sign episode's Recognition-v2
 * top-1 may become a committed word. Pure Kotlin so it is JVM-testable; it never touches the
 * Candidate01 observation stream, S2, the event decoder, the materializer or the recognizer.
 *
 * Outcomes:
 *  - ACCEPT: commit the top-1 word.
 *  - REJECT: the episode is structurally not a sign (no hand was ever observed inside the sign span) or
 *    the recognizer output is unusable. Nothing is committed.
 *  - UNCERTAIN: the recognizer's own top-1 probability is below the configured floor. Nothing is
 *    committed; the decoder keeps running and the next episode is judged independently.
 *
 * What the evidence behind each rule is (docs/PHASE_1_RECOGNITION_RELIABILITY.md):
 *  - top-1 probability is an UNCALIBRATED ranking score (softmax of a frozen 236-way recognizer with no
 *    "none" class). It is used only as a dial whose operating point was chosen on held-out signers by the
 *    repo's pre-registered Youden-J rule (docs/audit/probes/output_policy/calibrate.py); it is never
 *    interpreted as a probability of being correct.
 *  - the hand-evidence rule is an invariant (a sign needs a visible hand; with no hand observation in the
 *    span the recognizer input is entirely "missing"), not a fitted threshold.
 */
internal enum class CommitOutcome { ACCEPT, REJECT, UNCERTAIN }

internal data class PhoneCommitEvidence(
    /** Recognition-v2 top-1 softmax output (uncalibrated). */
    val top1Probability: Float,
    /** Recognition-v2 second-highest softmax output. Logged for evidence collection; not a rule input. */
    val top2Probability: Float,
    /** Fraction of observations inside the LOGICAL sign span with at least one accepted hand, in [0,1]. */
    val handSpanFraction: Double,
) {
    val margin: Float get() = top1Probability - top2Probability
}

internal data class PhoneCommitDecision(val outcome: CommitOutcome, val reason: String) {
    val committed: Boolean get() = outcome == CommitOutcome.ACCEPT
}

/**
 * [minTop1Probability] == null means "no calibrated floor exists for this configuration" (no floor is
 * applied; never a guessed one). [requireHandEvidenceInSpan] enables the structural invariant.
 * [DISABLED] reproduces the pre-Phase-1 behaviour exactly (every event is accepted).
 */
internal data class PhoneCommitPolicy(
    val minTop1Probability: Double?,
    val requireHandEvidenceInSpan: Boolean,
) {
    init {
        require(minTop1Probability == null || minTop1Probability in 0.0..1.0) { "PHONE_COMMIT_FLOOR_RANGE" }
    }

    val enabled: Boolean get() = minTop1Probability != null || requireHandEvidenceInSpan

    fun evaluate(evidence: PhoneCommitEvidence): PhoneCommitDecision {
        if (!enabled) return PhoneCommitDecision(CommitOutcome.ACCEPT, "GATE_DISABLED")
        val p1 = evidence.top1Probability
        val p2 = evidence.top2Probability
        if (!p1.isFinite() || !p2.isFinite() || p1 < 0f || p1 > 1f || p2 < 0f || p2 > p1 ||
            !evidence.handSpanFraction.isFinite()
        ) {
            return PhoneCommitDecision(CommitOutcome.REJECT, "INVALID_RECOGNIZER_OUTPUT")
        }
        if (requireHandEvidenceInSpan && evidence.handSpanFraction <= 0.0) {
            return PhoneCommitDecision(CommitOutcome.REJECT, "NO_HAND_EVIDENCE_IN_SPAN")
        }
        val floor = minTop1Probability
        if (floor != null && p1 < floor) {
            return PhoneCommitDecision(CommitOutcome.UNCERTAIN, "TOP1_BELOW_FLOOR")
        }
        return PhoneCommitDecision(CommitOutcome.ACCEPT, "ACCEPT")
    }

    companion object {
        val DISABLED = PhoneCommitPolicy(minTop1Probability = null, requireHandEvidenceInSpan = false)
    }
}

/**
 * Fraction of observations whose source index lies inside the event's LOGICAL sign span
 * [startIndex, endIndex] that have at least one accepted hand. Mirrors `hand_fraction` of the offline
 * event ledger (`eval/runtime_diagnostics/event_reliability.py`): context observations outside the
 * logical span are ignored. Returns 0.0 when the span contains no observation.
 */
internal fun phoneHandSpanFraction(
    observations: List<PhoneRawObservation>,
    startIndex: Int,
    endIndex: Int,
): Double {
    var inSpan = 0
    var withHand = 0
    for (observation in observations) {
        if (observation.sourceIndex < startIndex || observation.sourceIndex > endIndex) continue
        inSpan++
        if (observation.handObserved[0] || observation.handObserved[1]) withHand++
    }
    return if (inSpan == 0) 0.0 else withHand.toDouble() / inSpan
}

/**
 * UI-only readiness. The decoder is not IDLE while it re-arms after an emitted event. After an ACCEPTED
 * event the screen shows the held word (unchanged). After a withheld event there is no held word, and the
 * recognition screen would otherwise show "Initializing recognition…" for the whole re-arm wait. The
 * decoder state itself ([PhoneProductionSession.isReady], used by the coordination router) is untouched.
 */
internal fun phoneDisplayReady(state: PhoneDecoderState, holdingCommittedWord: Boolean): Boolean =
    state == PhoneDecoderState.IDLE ||
        (state == PhoneDecoderState.EVENT_EMITTED_WAIT_REARM && !holdingCommittedWord)

/**
 * Owns "event -> committed word": the monotonic event-id guard, the gate decision and the sentence
 * mutation. A non-ACCEPT event still advances the event id (so no event can be processed twice) but never
 * touches the sentence or the last committed gloss.
 */
internal class PhoneEventCommitter(
    private val policy: PhoneCommitPolicy,
    private val sentence: SentenceBuilder,
) {
    data class Result(
        val decision: PhoneCommitDecision,
        val committed: RecognitionState.Committed?,
        val top1: Int,
        val top1Probability: Float,
        val margin: Float,
    )

    private var lastEventId = 0

    /**
     * [top5] must be ordered best-first and [probabilities] is the full recognizer output; the committed
     * candidates list is the existing top-5 gloss list.
     */
    fun decide(
        eventId: Int,
        probabilities: FloatArray,
        top5: IntArray,
        glosses: List<String>,
        handSpanFraction: Double,
    ): Result {
        require(eventId > lastEventId) { "APP_PHONE_DUPLICATE_EVENT_ID" }
        lastEventId = eventId
        val top1 = top5.first()
        val p1 = probabilities[top1]
        val p2 = if (top5.size > 1) probabilities[top5[1]] else 0f
        val decision = policy.evaluate(PhoneCommitEvidence(p1, p2, handSpanFraction))
        if (!decision.committed) return Result(decision, null, top1, p1, p1 - p2)
        sentence.add(glosses[top1])
        val committed = RecognitionState.Committed(glosses[top1], top1, top5.map { glosses[it] })
        return Result(decision, committed, top1, p1, p1 - p2)
    }

    fun reset() {
        lastEventId = 0
    }
}
