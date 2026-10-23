package com.example.apphear.fingerspelling

/** Operational timing, not a calibrated recognition-confidence threshold. Loaded from an asset. */
data class HeldLetterConfig(
    val windowMs: Double, val minimumSpanMs: Double, val minimumUsable: Int,
    val inferenceIntervalMs: Double, val stableDecodes: Int, val stableSpanMs: Double,
    val rearmMissingMs: Double, val rearmMissingObservations: Int, val maximumObservations: Int,
    /** Practical v1: judge a result by the evidence of its own window, not by a one-frame dropout at callback time. */
    val acceptWhileHandMissing: Boolean = false,
) {
    init {
        require(windowMs >= minimumSpanMs && minimumSpanMs > 0 && minimumUsable > 0)
        require(inferenceIntervalMs > 0 && stableDecodes >= 2 && stableSpanMs > 0)
        require(rearmMissingMs > 0 && rearmMissingObservations >= 2 && maximumObservations >= minimumUsable)
    }
}

/** Read-only acceptance evidence. Never used as model input or to tune acceptance. */
data class HeldLetterAcceptanceState(
    val epoch: Int, val waitingForHand: Boolean, val missingObservations: Int,
    val candidate: String, val candidateCount: Int, val candidateSpanMs: Double, val latch: String,
)

enum class HeldLetterAcceptanceReason {
    NOT_EVALUATED, STALE_EPOCH, HAND_CURRENTLY_MISSING, OUT_OF_ORDER_RESULT,
    EMPTY_DECODE, SAME_AS_LATCH, NEED_MORE_MATCHING_DECODES, NEED_LONGER_STABLE_SPAN, APPENDED,
}

/** Camera-thread state machine. Draft letters are unconfirmed; the same prediction is latched until rearm. */
class HeldLetterPolicy(val config: HeldLetterConfig) {
    private val observations = java.util.ArrayDeque<CommonObservation>()
    private var lastTimestamp: Double? = null
    private var lastRequest = Double.NEGATIVE_INFINITY
    private var missingStart: Double? = null
    private var missingCount = 0
    private var rearmedDuringAbsence = false
    // Practical v1: a letter appended while the hand was already out of view keeps its latch through that
    // same absence (the user never saw it appear, so the absence is not a deliberate "lower to repeat").
    private var latchSurvivesAbsence = false
    private var candidate = ""
    private var candidateStart = 0.0
    private var candidateCount = 0
    private var lastDecision = Double.NEGATIVE_INFINITY
    var lastAcceptanceReason = HeldLetterAcceptanceReason.NOT_EVALUATED; private set
    fun acceptanceState(timestampMs: Double) = HeldLetterAcceptanceState(
        epoch, waitingForHand, missingCount, candidate, candidateCount,
        if(candidateCount > 0) timestampMs - candidateStart else 0.0, latch,
    )
    var latch = ""; private set
    var epoch = 0; private set
    var preview = ""; private set
    // Presentation-only latest valid decode. This does not control accumulation or acceptance.
    var currentLetter = ""; private set
    var observationsSeen = 0; private set
    val windowCount get() = observations.size
    val waitingForHand get() = missingCount > 0

    fun reset(clearPreview: Boolean = true, keepLatch: Boolean = false) {
        epoch++; observations.clear(); lastTimestamp = null; lastRequest = Double.NEGATIVE_INFINITY
        missingStart = null; missingCount = 0; rearmedDuringAbsence = false; latchSurvivesAbsence = false
        resetCandidate(); currentLetter = ""; lastAcceptanceReason = HeldLetterAcceptanceReason.NOT_EVALUATED
        if (!keepLatch) latch = ""
        if (clearPreview) preview = ""
    }

    private fun resetCandidate() {
        candidate = ""; candidateCount = 0; lastDecision = Double.NEGATIVE_INFINITY
    }

    fun observe(observation: CommonObservation) {
        val t = observation.timestampMs
        require(t.isFinite() && (lastTimestamp == null || t > lastTimestamp!!)) { "Chronological observations required" }
        lastTimestamp = t; observationsSeen++
        val usable = usable(observation)
        if (!usable) currentLetter = ""
        if (usable) {
            missingStart = null; missingCount = 0; rearmedDuringAbsence = false; latchSurvivesAbsence = false
        } else {
            if (missingStart == null) missingStart = t
            missingCount++
            if (!rearmedDuringAbsence && missingCount >= config.rearmMissingObservations &&
                t - missingStart!! >= config.rearmMissingMs) {
                observations.clear(); if (!latchSurvivesAbsence) latch = ""; epoch++; resetCandidate()
                rearmedDuringAbsence = true
            }
        }
        // A sustained absence is a task boundary, not a fabricated or forward-filled observation.
        if (!rearmedDuringAbsence) observations.addLast(observation.detached())
        while (observations.isNotEmpty() &&
            (t - observations.first.timestampMs > config.windowMs || observations.size > config.maximumObservations)) {
            observations.removeFirst()
        }
    }

    fun request(): List<CommonObservation>? {
        if (waitingForHand || observations.size < config.minimumUsable) return null
        val t = observations.last.timestampMs
        if (t - lastRequest < config.inferenceIntervalMs ||
            t - observations.first.timestampMs < config.minimumSpanMs ||
            observations.count { usable(it) } < config.minimumUsable) return null
        lastRequest = t
        return observations.toList()
    }

    /** Results refer to the exact requested raw-window epoch; stale/duplicate results cannot append. */
    fun accept(requestEpoch: Int, timestampMs: Double, letter: String): Boolean {
        if (requestEpoch != epoch) { lastAcceptanceReason = HeldLetterAcceptanceReason.STALE_EPOCH; return false }
        // A sustained absence already rearms (new epoch, STALE_EPOCH above). A shorter dropout after the
        // window was requested does not invalidate evidence the window already had (practical v1).
        if (waitingForHand && !config.acceptWhileHandMissing) { lastAcceptanceReason = HeldLetterAcceptanceReason.HAND_CURRENTLY_MISSING; return false }
        if (timestampMs <= lastDecision) { lastAcceptanceReason = HeldLetterAcceptanceReason.OUT_OF_ORDER_RESULT; return false }
        require(letter.isEmpty() || (letter.length == 1 && letter[0] in 'A'..'Z'))
        lastDecision = timestampMs
        currentLetter = letter
        if (letter.isEmpty() || letter == latch) {
            lastAcceptanceReason = if(letter.isEmpty()) HeldLetterAcceptanceReason.EMPTY_DECODE else HeldLetterAcceptanceReason.SAME_AS_LATCH
            candidate = ""; candidateCount = 0; return false
        }
        if (letter != candidate) { candidate = letter; candidateStart = timestampMs; candidateCount = 1 }
        else candidateCount++
        if (candidateCount < config.stableDecodes) { lastAcceptanceReason = HeldLetterAcceptanceReason.NEED_MORE_MATCHING_DECODES; return false }
        if (timestampMs - candidateStart < config.stableSpanMs) { lastAcceptanceReason = HeldLetterAcceptanceReason.NEED_LONGER_STABLE_SPAN; return false }
        lastAcceptanceReason = HeldLetterAcceptanceReason.APPENDED
        preview += letter; latch = letter
        if (waitingForHand && config.acceptWhileHandMissing) latchSurvivesAbsence = true
        observations.clear(); epoch++; resetCandidate()
        return true
    }

    /**
     * Practical v1 correction: remove the last draft letter. A new epoch drops in-flight results and the window;
     * the latch is kept, so a still-held deleted pose cannot immediately re-append (lower the hand to repeat it).
     */
    fun deleteLast(): Boolean {
        if (preview.isEmpty()) return false
        preview = preview.dropLast(1)
        epoch++; observations.clear(); lastRequest = Double.NEGATIVE_INFINITY
        resetCandidate(); currentLetter = ""; lastAcceptanceReason = HeldLetterAcceptanceReason.NOT_EVALUATED
        return true
    }

    /**
     * Practical v1 explicit double letter: append the last draft letter again (natural slide/bounce doubles are not
     * separable by the singleton window). Latched, so the still-held pose cannot add a third copy.
     */
    fun repeatLast(): Boolean {
        val last = preview.lastOrNull() ?: return false
        preview += last; latch = last.toString()
        epoch++; observations.clear(); lastRequest = Double.NEGATIVE_INFINITY
        resetCandidate(); lastAcceptanceReason = HeldLetterAcceptanceReason.NOT_EVALUATED
        return true
    }

    /** Presentation-only progress of the current unlatched candidate toward [HeldLetterConfig.stableDecodes]. */
    val candidateLetter get() = candidate
    val candidateProgress get() = candidateCount

    companion object {
        fun usable(c: CommonObservation) = (0..1).any { c.observed[it] && c.valid[it].any { valid -> valid } }
    }
}

/** CameraX/perception arrays may be reused after analyze(): retain only independent raw evidence. */
fun CommonObservation.detached() = copy(
    xy = Array(xy.size) { xy[it].copyOf() }, valid = Array(valid.size) { valid[it].copyOf() },
    support = Array(support.size) { support[it].copyOf() }, presence = presence.copyOf(),
    observed = observed.copyOf(), proposal = proposal.copyOf(), roi = Array(roi.size) { roi[it].copyOf() },
    bodyXy = bodyXy.copyOf(), bodySupport = bodySupport.copyOf(), bodyValid = bodyValid.copyOf(),
)
