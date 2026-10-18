package com.example.apphear.perceptionvnext

import kotlin.math.max

/** Genuine current-frame Candidate01 observation used by the phone-causal stack. */
internal data class PhoneRawObservation(
    val sourceIndex: Int,
    val timestampMs: Double,
    val sourceWidth: Int,
    val sourceHeight: Int,
    val handXy: Array<FloatArray>,
    val handJointValid: Array<BooleanArray>,
    val handProposalSupport: Array<FloatArray>,
    val handPresence: FloatArray,
    val handObserved: BooleanArray,
    val handProposalPresent: BooleanArray,
    val handRoiCenterSide: Array<FloatArray>,
    val bodyXy: FloatArray,
    val bodySupport: FloatArray,
    val bodyValid: BooleanArray,
    val bodyAvailable: Boolean,
    val candidatePreprocessMs: Double? = null,
    val candidatePoseInferenceMs: Double? = null,
    val candidatePoseDecodeMs: Double? = null,
    val candidateTotalMs: Double? = null,
) {
    init {
        require(sourceIndex >= 0 && timestampMs.isFinite())
        require(sourceWidth > 0 && sourceHeight > 0)
        require(handXy.size == 2 && handXy.all { it.size == 42 })
        require(handJointValid.size == 2 && handJointValid.all { it.size == 21 })
        require(handProposalSupport.size == 2 && handProposalSupport.all { it.size == 21 })
        require(handPresence.size == 2 && handObserved.size == 2 && handProposalPresent.size == 2)
        require(handRoiCenterSide.size == 2 && handRoiCenterSide.all { it.size == 3 })
        require(bodyXy.size == 16 && bodySupport.size == 8 && bodyValid.size == 8)
        require(
            listOf(
                candidatePreprocessMs,
                candidatePoseInferenceMs,
                candidatePoseDecodeMs,
                candidateTotalMs,
            ).all { it == null || (it.isFinite() && it >= 0.0) },
        )
    }
}

/** Byte-for-byte semantic port of segmentation_features.v1 for one causal observation. */
internal class PhoneSegmentationFeatureBuilder {
    private var previous: PhoneRawObservation? = null

    fun reset() {
        previous = null
    }

    fun derive(current: PhoneRawObservation): FloatArray {
        val old = previous
        if (old != null) require(current.timestampMs > old.timestampMs) {
            "PHONE_SEGMENTATION_NON_CHRONOLOGICAL_TIMESTAMP"
        }
        val output = FloatArray(FEATURE_WIDTH)
        var offset = 0
        val width = max(current.sourceWidth, 1).toFloat()
        val height = max(current.sourceHeight, 1).toFloat()
        val shortSide = max(minOf(current.sourceWidth, current.sourceHeight), 1).toFloat()

        for (side in 0..1) for (joint in 0 until HAND_POINTS) for (axis in 0..1) {
            val valid = current.handObserved[side] && current.handJointValid[side][joint]
            val scale = if (axis == 0) width else height
            output[offset++] = if (valid) current.handXy[side][joint * 2 + axis] / scale else 0f
        }
        for (side in 0..1) for (joint in 0 until HAND_POINTS) {
            output[offset++] = flag(current.handObserved[side] && current.handJointValid[side][joint])
        }
        for (side in 0..1) for (joint in 0 until HAND_POINTS) {
            output[offset++] = finiteOrZero(current.handProposalSupport[side][joint])
        }
        for (side in 0..1) output[offset++] = finiteOrZero(current.handPresence[side])
        for (side in 0..1) output[offset++] = flag(current.handPresence[side].isFinite())
        for (side in 0..1) output[offset++] = flag(current.handObserved[side])
        for (side in 0..1) output[offset++] = flag(current.handProposalPresent[side])
        for (side in 0..1) for (axis in 0..2) {
            val scale = when (axis) { 0 -> width; 1 -> height; else -> shortSide }
            output[offset++] = if (current.handProposalPresent[side]) {
                current.handRoiCenterSide[side][axis] / scale
            } else 0f
        }
        for (point in 0 until BODY_POINTS) for (axis in 0..1) {
            val scale = if (axis == 0) width else height
            output[offset++] = if (current.bodyValid[point]) current.bodyXy[point * 2 + axis] / scale else 0f
        }
        for (point in 0 until BODY_POINTS) output[offset++] = finiteOrZero(current.bodySupport[point])
        for (point in 0 until BODY_POINTS) output[offset++] = flag(current.bodyValid[point])
        output[offset++] = flag(current.bodyAvailable)
        val dtSeconds = old?.let { ((current.timestampMs - it.timestampMs) / 1000.0).coerceIn(0.0, 1.0) } ?: 0.0
        output[offset++] = dtSeconds.toFloat()

        for (side in 0..1) for (joint in 0 until HAND_POINTS) for (axis in 0..1) {
            val valid = old != null && current.handObserved[side] && old.handObserved[side] &&
                current.handJointValid[side][joint] && old.handJointValid[side][joint]
            output[offset++] = if (valid) {
                val scale = if (axis == 0) width else height
                val oldScale = if (axis == 0) max(old!!.sourceWidth, 1).toFloat()
                else max(old!!.sourceHeight, 1).toFloat()
                current.handXy[side][joint * 2 + axis] / scale -
                    old.handXy[side][joint * 2 + axis] / oldScale
            } else 0f
        }
        for (side in 0..1) for (joint in 0 until HAND_POINTS) {
            val valid = old != null && current.handObserved[side] && old.handObserved[side] &&
                current.handJointValid[side][joint] && old.handJointValid[side][joint]
            output[offset++] = flag(valid)
        }
        for (side in 0..1) for (axis in 0..2) {
            val valid = old != null && current.handProposalPresent[side] && old.handProposalPresent[side]
            output[offset++] = if (valid) {
                val scale = when (axis) { 0 -> width; 1 -> height; else -> shortSide }
                val oldScale = when (axis) {
                    0 -> max(old!!.sourceWidth, 1).toFloat()
                    1 -> max(old!!.sourceHeight, 1).toFloat()
                    else -> max(minOf(old!!.sourceWidth, old.sourceHeight), 1).toFloat()
                }
                current.handRoiCenterSide[side][axis] / scale -
                    old.handRoiCenterSide[side][axis] / oldScale
            } else 0f
        }
        for (side in 0..1) {
            output[offset++] = flag(old != null && current.handProposalPresent[side] && old.handProposalPresent[side])
        }
        for (point in 0 until BODY_POINTS) for (axis in 0..1) {
            val valid = old != null && current.bodyValid[point] && old.bodyValid[point]
            output[offset++] = if (valid) {
                val scale = if (axis == 0) width else height
                val oldScale = if (axis == 0) max(old!!.sourceWidth, 1).toFloat()
                else max(old!!.sourceHeight, 1).toFloat()
                current.bodyXy[point * 2 + axis] / scale - old.bodyXy[point * 2 + axis] / oldScale
            } else 0f
        }
        for (point in 0 until BODY_POINTS) {
            output[offset++] = flag(old != null && current.bodyValid[point] && old.bodyValid[point])
        }
        for (side in 0..1) {
            output[offset++] = if (old == null) 0f else flag(current.handObserved[side]) - flag(old.handObserved[side])
        }
        for (side in 0..1) {
            output[offset++] = if (old == null) 0f else
                flag(current.handProposalPresent[side]) - flag(old.handProposalPresent[side])
        }
        check(offset == FEATURE_WIDTH)
        require(output.all { it.isFinite() }) { "PHONE_SEGMENTATION_NONFINITE_FEATURE" }
        previous = current
        return output
    }

    private fun finiteOrZero(value: Float) = if (value.isFinite()) value else 0f
    private fun flag(value: Boolean) = if (value) 1f else 0f

    companion object {
        const val RAW_SCHEMA = "apphear.perception_vnext.raw.v1"
        const val SCHEMA = "apphear.perception_vnext.segmentation_features.v1"
        const val FEATURE_WIDTH = 378
        const val HAND_POINTS = 21
        const val BODY_POINTS = 8
    }
}

/** Compact, raw-feature motion evidence retained for admission diagnostics only. */
internal data class PhoneSegmentationEvidenceSummary(
    val handDeltaValidCount: Int,
    val handDeltaMeanMagnitude: Double?,
    val handDeltaMaxMagnitude: Double?,
    val roiDeltaValidCount: Int,
    val roiDeltaMeanMagnitude: Double?,
    val roiDeltaMaxMagnitude: Double?,
    val bodyDeltaValidCount: Int,
    val bodyDeltaMeanMagnitude: Double?,
    val bodyDeltaMaxMagnitude: Double?,
    val observedTransitionCount: Int,
    val proposalTransitionCount: Int,
)

/**
 * Summarizes existing segmentation_features.v1 deltas without changing the feature contract.
 * Values are computed from the same genuine previous/current observation pair consumed by S2.
 */
internal fun summarizePhoneSegmentationEvidence(
    features: FloatArray,
): PhoneSegmentationEvidenceSummary {
    require(features.size == PhoneSegmentationFeatureBuilder.FEATURE_WIDTH)

    fun magnitudes(
        valueStart: Int,
        pairCount: Int,
        validStart: Int,
    ): List<Double> = buildList {
        for (pair in 0 until pairCount) {
            if (features[validStart + pair] <= 0.5f) continue
            val x = features[valueStart + pair * 2].toDouble()
            val y = features[valueStart + pair * 2 + 1].toDouble()
            add(kotlin.math.sqrt(x * x + y * y))
        }
    }

    fun roiMagnitudes(): List<Double> = buildList {
        for (side in 0 until 2) {
            if (features[348 + side] <= 0.5f) continue
            val base = 342 + side * 3
            val x = features[base].toDouble()
            val y = features[base + 1].toDouble()
            val size = features[base + 2].toDouble()
            add(kotlin.math.sqrt(x * x + y * y + size * size))
        }
    }

    fun meanOrNull(values: List<Double>) = values.takeIf { it.isNotEmpty() }?.average()
    fun maxOrNull(values: List<Double>) = values.maxOrNull()

    val hand = magnitudes(valueStart = 216, pairCount = 42, validStart = 300)
    val roi = roiMagnitudes()
    val body = magnitudes(valueStart = 350, pairCount = 8, validStart = 366)
    return PhoneSegmentationEvidenceSummary(
        handDeltaValidCount = hand.size,
        handDeltaMeanMagnitude = meanOrNull(hand),
        handDeltaMaxMagnitude = maxOrNull(hand),
        roiDeltaValidCount = roi.size,
        roiDeltaMeanMagnitude = meanOrNull(roi),
        roiDeltaMaxMagnitude = maxOrNull(roi),
        bodyDeltaValidCount = body.size,
        bodyDeltaMeanMagnitude = meanOrNull(body),
        bodyDeltaMaxMagnitude = maxOrNull(body),
        observedTransitionCount = (374..375).count { features[it] != 0f },
        proposalTransitionCount = (376..377).count { features[it] != 0f },
    )
}

internal enum class PhoneDecoderState {
    IDLE,
    ACTIVE_CANDIDATE,
    PRE_GAP,
    POST_CANDIDATE,
    EVENT_EMITTED_WAIT_REARM,
}

internal enum class PhoneRearmPolicy {
    PRE_ONLY,
    PRE_OR_POST_EXPERIMENTAL,
}

internal enum class PhoneSignAdmissionPolicy {
    PASS_THROUGH,
}

internal data class PhoneAdmissionDecision(
    val admitted: Boolean,
    val reason: String,
)

/** Explicit boundary for future new-sign admission; this milestone remains pass-through. */
internal class PhoneNewSignAdmission(
    private val policy: PhoneSignAdmissionPolicy,
) {
    fun evaluate(argmaxState: Int): PhoneAdmissionDecision {
        require(argmaxState == PhoneCausalEventProducer.ACTIVE_SIGN)
        return when (policy) {
            PhoneSignAdmissionPolicy.PASS_THROUGH -> PhoneAdmissionDecision(
                admitted = true,
                reason = "PASS_THROUGH_ACTIVE",
            )
        }
    }
}

internal data class PhoneDecoderConfig(
    val minimumActiveMs: Double = 133.308,
    val preGapResetMs: Double = 133.308,
    val postConfirmMs: Double = 266.616,
    val rearmPreStableMs: Double = 399.924,
    val rearmPolicy: PhoneRearmPolicy = PhoneRearmPolicy.PRE_ONLY,
    val admissionPolicy: PhoneSignAdmissionPolicy = PhoneSignAdmissionPolicy.PASS_THROUGH,
    // Twice the frozen slow-cadence target interval. A longer observation gap is missing
    // evidence, not continuous recovery time, and therefore resets recovery persistence.
    val maximumContinuousObservationGapMs: Double = 533.232,
    // Experimental confirm-boundary split (research decoder CONFIRM_BOUNDARY_70; null = off,
    // production behaviour unchanged). When ACTIVE arrives after POST has lasted the full
    // confirmation time and P(POST) peaked at or above this value, the open sign is committed
    // and the ACTIVE observation starts the next sign instead of extending the current one.
    val confirmBoundaryPostPeak: Double? = null,
) {
    init {
        require(confirmBoundaryPostPeak == null || confirmBoundaryPostPeak in 0.0..1.0)
        require(minimumActiveMs > 0.0)
        require(preGapResetMs > 0.0)
        require(postConfirmMs > 0.0)
        require(rearmPreStableMs > 0.0)
        require(maximumContinuousObservationGapMs > 0.0)
    }
}

internal data class PhoneLogicalSignEvent(
    val eventId: Int,
    val logicalActiveStartIndex: Int,
    val logicalActiveEndIndex: Int,
    val logicalActiveStartMs: Double,
    val logicalActiveEndMs: Double,
    val terminalPostIndex: Int,
    val terminalPostMs: Double,
    val commitIndex: Int,
    val commitMs: Double,
)

internal data class PhoneDecoderUpdate(
    val stateBefore: PhoneDecoderState,
    val stateAfter: PhoneDecoderState,
    val action: String,
    val event: PhoneLogicalSignEvent?,
    val rearmPolicy: PhoneRearmPolicy,
    val rearmCandidateState: Int?,
    val rearmTimerStartMs: Double?,
    val rearmElapsedMs: Double?,
    val rearmReason: String?,
    val admissionPolicy: PhoneSignAdmissionPolicy,
    val admissionDecision: String?,
    val admissionReason: String?,
)

/** Exact CONFIG_01 hard-argmax behavior; no EOF flush and no future reads. */
internal class PhoneCausalEventProducer(private val config: PhoneDecoderConfig = PhoneDecoderConfig()) {
    var state = PhoneDecoderState.IDLE
        private set
    private var lastTimestampMs: Double? = null
    private var nextIndex = 0
    private var eventCount = 0
    private var candidateStartIndex: Int? = null
    private var candidateStartMs: Double? = null
    private var lastActiveIndex: Int? = null
    private var lastActiveMs: Double? = null
    private var preGapStartMs: Double? = null
    private var firstPostIndex: Int? = null
    private var firstPostMs: Double? = null
    private val admission = PhoneNewSignAdmission(config.admissionPolicy)
    private var rearmStartMs: Double? = null
    private var rearmCandidateState: Int? = null
    private var postPeak = 0.0

    /** [postProbability] is required only when the experimental confirm-boundary split is on. */
    fun consume(timestampMs: Double, argmaxState: Int, postProbability: Double? = null): PhoneDecoderUpdate {
        require(timestampMs.isFinite() && (lastTimestampMs == null || timestampMs > lastTimestampMs!!))
        require(argmaxState in PRE_IDLE..POST_RECOVERY)
        val splitPeak = config.confirmBoundaryPostPeak
        require(splitPeak == null || (postProbability != null && postProbability.isFinite())) {
            "PHONE_DECODER_CONFIRM_BOUNDARY_REQUIRES_POST_PROBABILITY"
        }
        val index = nextIndex++
        val observationGapMs = lastTimestampMs?.let { timestampMs - it }
        lastTimestampMs = timestampMs
        val before = state
        var action = "NO_CHANGE"
        var event: PhoneLogicalSignEvent? = null
        var rearmReason: String? = null
        var terminalRearmElapsedMs: Double? = null
        var admissionDecision: String? = null
        var admissionReason: String? = null
        when (state) {
            PhoneDecoderState.IDLE -> if (argmaxState == ACTIVE_SIGN) {
                val decision = admission.evaluate(argmaxState)
                admissionDecision = if (decision.admitted) "ADMIT" else "REJECT"
                admissionReason = decision.reason
                if (decision.admitted) {
                    startCandidate(index, timestampMs); action = "START_ACTIVE_CANDIDATE"
                } else {
                    action = "REJECT_ACTIVE_ONSET"
                }
            }
            PhoneDecoderState.ACTIVE_CANDIDATE -> when (argmaxState) {
                ACTIVE_SIGN -> { lastActiveIndex = index; lastActiveMs = timestampMs; action = "EXTEND_ACTIVE_CANDIDATE" }
                POST_RECOVERY -> {
                    enterPost(index, timestampMs); action = "BEGIN_POST_CANDIDATE"
                    if (splitPeak != null) postPeak = checkNotNull(postProbability)
                }
                else -> { preGapStartMs = timestampMs; state = PhoneDecoderState.PRE_GAP; action = "BEGIN_PRE_GAP" }
            }
            PhoneDecoderState.PRE_GAP -> {
                val elapsed = timestampMs - checkNotNull(preGapStartMs)
                when {
                    argmaxState == ACTIVE_SIGN && elapsed < config.preGapResetMs -> {
                        lastActiveIndex = index; lastActiveMs = timestampMs; preGapStartMs = null
                        state = PhoneDecoderState.ACTIVE_CANDIDATE; action = "BRIDGE_PRE_GAP_TO_ACTIVE"
                    }
                    argmaxState == POST_RECOVERY && elapsed < config.preGapResetMs -> {
                        enterPost(index, timestampMs); action = "BRIDGE_PRE_GAP_TO_POST"
                    }
                    elapsed >= config.preGapResetMs -> { discardCandidate(); action = "DISCARD_SUSTAINED_PRE_GAP" }
                }
            }
            PhoneDecoderState.POST_CANDIDATE -> {
                val elapsed = timestampMs - checkNotNull(firstPostMs)
                if (splitPeak != null) postPeak = maxOf(postPeak, checkNotNull(postProbability))
                when {
                    splitPeak != null && argmaxState == ACTIVE_SIGN &&
                        elapsed >= config.postConfirmMs && postPeak >= splitPeak -> {
                        val activeSpan = checkNotNull(lastActiveMs) - checkNotNull(candidateStartMs)
                        if (activeSpan < config.minimumActiveMs) {
                            action = "SPLIT_CONFIRM_BOUNDARY_DISCARD_TOO_SHORT"
                        } else {
                            eventCount++
                            event = PhoneLogicalSignEvent(
                                eventCount,
                                checkNotNull(candidateStartIndex), checkNotNull(lastActiveIndex),
                                checkNotNull(candidateStartMs), checkNotNull(lastActiveMs),
                                checkNotNull(firstPostIndex), checkNotNull(firstPostMs), index, timestampMs,
                            )
                            action = "SPLIT_CONFIRM_BOUNDARY"
                        }
                        resetRearm()
                        startCandidate(index, timestampMs)
                        postPeak = 0.0
                    }
                    argmaxState == ACTIVE_SIGN -> {
                        lastActiveIndex = index; lastActiveMs = timestampMs
                        firstPostIndex = null; firstPostMs = null
                        state = PhoneDecoderState.ACTIVE_CANDIDATE
                        action = if (elapsed < config.postConfirmMs) {
                            "CANCEL_POST_ACTIVE_RESUMED"
                        } else "CANCEL_POST_ACTIVE_AT_CONFIRM_BOUNDARY"
                    }
                    elapsed >= config.postConfirmMs -> {
                        val activeSpan = checkNotNull(lastActiveMs) - checkNotNull(candidateStartMs)
                        if (activeSpan < config.minimumActiveMs) {
                            discardCandidate(); action = "DISCARD_TOO_SHORT"
                        } else {
                            eventCount++
                            event = PhoneLogicalSignEvent(
                                eventCount,
                                checkNotNull(candidateStartIndex), checkNotNull(lastActiveIndex),
                                checkNotNull(candidateStartMs), checkNotNull(lastActiveMs),
                                checkNotNull(firstPostIndex), checkNotNull(firstPostMs), index, timestampMs,
                            )
                            clearCandidate()
                            state = PhoneDecoderState.EVENT_EMITTED_WAIT_REARM
                            if (isRearmEligible(argmaxState)) {
                                rearmStartMs = timestampMs
                                rearmCandidateState = argmaxState
                                rearmReason = "EVENT_COMMIT_ELIGIBLE_${stateName(argmaxState)}"
                            } else {
                                resetRearm()
                                rearmReason = "EVENT_COMMIT_ACTIVE"
                            }
                            action = "EMIT_SIGN_EVENT"
                        }
                    }
                }
            }
            PhoneDecoderState.EVENT_EMITTED_WAIT_REARM -> {
                val gapInvalid = observationGapMs != null &&
                    observationGapMs > config.maximumContinuousObservationGapMs
                when {
                    gapInvalid -> {
                        val hadCandidate = rearmStartMs != null
                        terminalRearmElapsedMs = rearmStartMs?.let { timestampMs - it }
                        resetRearm()
                        rearmReason = "OBSERVATION_GAP_${observationGapMs}_MS"
                        if (isRearmEligible(argmaxState)) {
                            beginRearm(timestampMs, argmaxState)
                            action = if (hadCandidate) "RESET_REARM_GAP_AND_BEGIN" else "BEGIN_REARM_AFTER_GAP"
                        } else {
                            action = if (hadCandidate) "RESET_REARM_GAP" else "WAIT_REARM_ACTIVE"
                        }
                    }
                    argmaxState == ACTIVE_SIGN -> {
                        val hadCandidate = rearmStartMs != null
                        terminalRearmElapsedMs = rearmStartMs?.let { timestampMs - it }
                        resetRearm()
                        rearmReason = "ACTIVE_INTERRUPTED_RECOVERY"
                        if (hadCandidate) {
                            action = if (config.rearmPolicy == PhoneRearmPolicy.PRE_ONLY) {
                                "RESET_REARM_PRE"
                            } else "RESET_REARM_ACTIVE"
                        }
                    }
                    isRearmEligible(argmaxState) -> {
                        if (rearmStartMs == null) {
                            beginRearm(timestampMs, argmaxState)
                            rearmReason = "BEGIN_STABLE_${stateName(argmaxState)}"
                            action = if (config.rearmPolicy == PhoneRearmPolicy.PRE_ONLY) {
                                "BEGIN_REARM_PRE"
                            } else "BEGIN_REARM_NON_ACTIVE"
                        } else if (timestampMs - checkNotNull(rearmStartMs) >= config.rearmPreStableMs) {
                            terminalRearmElapsedMs = timestampMs - checkNotNull(rearmStartMs)
                            rearmReason = "STABLE_NON_ACTIVE_COMPLETE"
                            resetRearm()
                            state = PhoneDecoderState.IDLE
                            action = "REARM_COMPLETE"
                        } else {
                            rearmCandidateState = argmaxState
                            rearmReason = "CONTINUE_STABLE_NON_ACTIVE"
                        }
                    }
                }
            }
        }
        val rearmElapsedMs = rearmStartMs?.let { timestampMs - it } ?: terminalRearmElapsedMs
        return PhoneDecoderUpdate(
            before,
            state,
            action,
            event,
            config.rearmPolicy,
            rearmCandidateState,
            rearmStartMs,
            rearmElapsedMs,
            rearmReason,
            config.admissionPolicy,
            admissionDecision,
            admissionReason,
        )
    }

    fun reset() {
        state = PhoneDecoderState.IDLE
        lastTimestampMs = null
        nextIndex = 0
        eventCount = 0
        postPeak = 0.0
        resetRearm()
        clearCandidate()
    }

    private fun isRearmEligible(argmaxState: Int): Boolean = when (config.rearmPolicy) {
        PhoneRearmPolicy.PRE_ONLY -> argmaxState == PRE_IDLE
        PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL -> argmaxState == PRE_IDLE || argmaxState == POST_RECOVERY
    }

    private fun beginRearm(timestampMs: Double, argmaxState: Int) {
        rearmStartMs = timestampMs
        rearmCandidateState = argmaxState
    }

    private fun resetRearm() {
        rearmStartMs = null
        rearmCandidateState = null
    }

    private fun stateName(argmaxState: Int): String = when (argmaxState) {
        PRE_IDLE -> "PRE"
        ACTIVE_SIGN -> "ACTIVE"
        POST_RECOVERY -> "POST"
        else -> error("PHONE_DECODER_UNKNOWN_STATE")
    }

    private fun startCandidate(index: Int, timestampMs: Double) {
        candidateStartIndex = index; candidateStartMs = timestampMs
        lastActiveIndex = index; lastActiveMs = timestampMs
        preGapStartMs = null; firstPostIndex = null; firstPostMs = null
        state = PhoneDecoderState.ACTIVE_CANDIDATE
    }

    private fun enterPost(index: Int, timestampMs: Double) {
        firstPostIndex = index; firstPostMs = timestampMs; preGapStartMs = null
        state = PhoneDecoderState.POST_CANDIDATE
    }

    private fun discardCandidate() {
        clearCandidate(); state = PhoneDecoderState.IDLE
    }

    private fun clearCandidate() {
        candidateStartIndex = null; candidateStartMs = null
        lastActiveIndex = null; lastActiveMs = null
        preGapStartMs = null; firstPostIndex = null; firstPostMs = null
    }

    companion object {
        const val PRE_IDLE = 0
        const val ACTIVE_SIGN = 1
        const val POST_RECOVERY = 2
    }
}

internal data class PhoneMaterializedWindow(
    val observations: List<PhoneRawObservation>,
    val selectedStartIndex: Int,
    val selectedEndIndex: Int,
    val requestedStartMs: Double,
    val requestedEndMs: Double,
    val actualPreContextMs: Double,
    val actualPostContextMs: Double,
    val leftCensored: Boolean,
    val rightCensored: Boolean,
)

internal class PhoneObservationRingBuffer(
    private val maxObservations: Int = 256,
    private val maxAgeMs: Double = 30_000.0,
) {
    private val items = ArrayDeque<PhoneRawObservation>()

    fun append(observation: PhoneRawObservation) {
        require(items.lastOrNull()?.let { observation.timestampMs > it.timestampMs } ?: true)
        items.addLast(observation)
        while (items.size > maxObservations) items.removeFirst()
        while (items.isNotEmpty() && observation.timestampMs - items.first().timestampMs > maxAgeMs) {
            items.removeFirst()
        }
    }

    fun materialize(
        event: PhoneLogicalSignEvent,
        preContextMs: Double = 250.0,
        postContextMs: Double = 250.0,
    ): PhoneMaterializedWindow {
        val causal = items.filter { it.sourceIndex <= event.commitIndex }
        require(causal.any { it.sourceIndex == event.logicalActiveStartIndex })
        require(causal.any { it.sourceIndex == event.logicalActiveEndIndex })
        require(causal.any { it.sourceIndex == event.terminalPostIndex })
        require(causal.any { it.sourceIndex == event.commitIndex })
        val requestedStart = event.logicalActiveStartMs - preContextMs
        val startCandidates = causal.filter { it.timestampMs <= requestedStart }
        val leftCensored = startCandidates.isEmpty()
        val start = startCandidates.lastOrNull() ?: causal.first()
        val requestedEnd = event.terminalPostMs + postContextMs
        val endCandidates = causal.filter { it.timestampMs >= requestedEnd }
        val rightCensored = endCandidates.isEmpty()
        val end = endCandidates.firstOrNull() ?: causal.last()
        require(end.sourceIndex >= event.logicalActiveEndIndex)
        val selected = causal.filter { it.sourceIndex in start.sourceIndex..end.sourceIndex }
        return PhoneMaterializedWindow(
            selected,
            start.sourceIndex, end.sourceIndex,
            requestedStart, requestedEnd,
            event.logicalActiveStartMs - start.timestampMs,
            end.timestampMs - event.terminalPostMs,
            leftCensored, rightCensored,
        )
    }

    fun reset() = items.clear()
}
