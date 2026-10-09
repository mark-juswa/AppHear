package com.example.apphear.fingerspelling

/** Operational timing, not a calibrated recognition-confidence threshold. Loaded from an asset. */
data class HeldLetterConfig(
    val windowMs: Double, val minimumSpanMs: Double, val minimumUsable: Int,
    val inferenceIntervalMs: Double, val stableDecodes: Int, val stableSpanMs: Double,
    val rearmMissingMs: Double, val rearmMissingObservations: Int, val maximumObservations: Int,
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
        missingStart = null; missingCount = 0; rearmedDuringAbsence = false
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
            missingStart = null; missingCount = 0; rearmedDuringAbsence = false
        } else {
            if (missingStart == null) missingStart = t
            missingCount++
            if (!rearmedDuringAbsence && missingCount >= config.rearmMissingObservations &&
                t - missingStart!! >= config.rearmMissingMs) {
                observations.clear(); latch = ""; epoch++; resetCandidate()
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
        if (waitingForHand) { lastAcceptanceReason = HeldLetterAcceptanceReason.HAND_CURRENTLY_MISSING; return false }
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
        observations.clear(); epoch++; resetCandidate()
        return true
    }

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
