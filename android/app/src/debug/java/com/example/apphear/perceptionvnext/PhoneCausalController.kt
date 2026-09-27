package com.example.apphear.perceptionvnext

import android.content.Context
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

internal data class PhoneCausalResult(
    val event: PhoneLogicalSignEvent,
    val window: PhoneMaterializedWindow,
    val gloss: String,
    val top1Probability: Float,
    val top5: List<Pair<String, Float>>,
    val recognitionInvocationMs: Double,
)

/** Orchestrates frozen components without moving inference responsibility between layers. */
internal class PhoneCausalController(
    context: Context,
    private val recognizer: RecognitionV2LiveRecognizer,
    private val sessionRoot: File,
    private val expectedGloss: String? = null,
    private val decoderConfig: PhoneDecoderConfig = PhoneDecoderConfig(),
    exactParityCaptureEnabled: Boolean = false,
    s2Package: PhoneS2Package = PhoneS2Package.PHASE7_CONTROL,
) : AutoCloseable {
    private val featureBuilder = PhoneSegmentationFeatureBuilder()
    private val s2 = PhoneS2Runner(context, s2Package)
    private val eventProducer = PhoneCausalEventProducer(decoderConfig)
    private val buffer = PhoneObservationRingBuffer()
    private val observationLog = BufferedWriter(FileWriter(File(sessionRoot, OBSERVATION_LOG), true))
    private val eventLog = BufferedWriter(FileWriter(File(sessionRoot, EVENT_LOG), true))
    private val attemptLog = BufferedWriter(FileWriter(File(sessionRoot, ATTEMPT_LOG), true))
    private val exactParityRecorder = if (exactParityCaptureEnabled) {
        PhoneS2ExactParityRecorder(File(sessionRoot, EXACT_PARITY_DIRECTORY))
    } else null
    private var observationCount = 0
    private var eventCount = 0
    private var previousTimestampMs: Double? = null
    private var activeAttemptId: Int? = null
    private var activeAttemptGloss: String? = null
    private var diagnosticCandidateStartIndex: Int? = null
    private var diagnosticCandidateStartMs: Double? = null
    private var diagnosticLastActiveMs: Double? = null
    private var diagnosticLastCommittedEventId: Int? = null
    private val deliveryLog = BufferedWriter(FileWriter(File(sessionRoot, "ui_delivery.jsonl"), true))
    private var deliveryLogClosed = false

    init {
        require(sessionRoot.exists() || sessionRoot.mkdirs())
        writeIdentity(context)
    }

    fun consume(observation: PhoneRawObservation): PhoneCausalResult? {
        require(observation.sourceIndex == observationCount) { "PHONE_CAUSAL_SOURCE_INDEX_DISCONTINUITY" }
        val featureStarted = System.nanoTime()
        val features = featureBuilder.derive(observation)
        val evidence = summarizePhoneSegmentationEvidence(features)
        val featureMs = (System.nanoTime() - featureStarted) / 1_000_000.0
        buffer.append(observation)
        val state = s2.predict(features, retainNormalizedInputDiagnostic = exactParityRecorder != null)
        exactParityRecorder?.record(
            observation = observation,
            features = features,
            normalized = requireNotNull(state.normalizedInputDiagnostic),
            probabilities = state.probabilities,
            historyLength = state.historyLength,
            argmaxState = state.argmaxState,
            attemptId = activeAttemptId,
            expectedGloss = activeAttemptGloss ?: expectedGloss,
        )
        val update = eventProducer.consume(observation.timestampMs, state.argmaxState)
        val decisionElapsedNs = SystemClock.elapsedRealtimeNanos()
        if (update.action == "START_ACTIVE_CANDIDATE") {
            diagnosticCandidateStartIndex = observation.sourceIndex
            diagnosticCandidateStartMs = observation.timestampMs
            diagnosticLastActiveMs = observation.timestampMs
        } else if (update.stateAfter == PhoneDecoderState.ACTIVE_CANDIDATE && state.argmaxState == 1) {
            diagnosticLastActiveMs = observation.timestampMs
        }
        if (update.event != null) diagnosticLastCommittedEventId = update.event.eventId
        observationCount++
        val observationJson = JSONObject()
            .put("schema", "apphear.phone_causal_recognition.observation.v1")
            .put("source_index", observation.sourceIndex)
            .put("source_timestamp_ms", observation.timestampMs)
            .put("decision_elapsed_realtime_ns", decisionElapsedNs)
            .put("raw_schema", RecognitionV2.RAW_SCHEMA)
            .put("feature_schema", PhoneSegmentationFeatureBuilder.SCHEMA)
            .put("exact_record_index", if (exactParityRecorder != null) observation.sourceIndex else JSONObject.NULL)
            .put("source_frame_identity", "frame_${(observation.sourceIndex + 1).toString().padStart(6, '0')}")
            .put("dt_ms", previousTimestampMs?.let { observation.timestampMs - it } ?: JSONObject.NULL)
            .put("left_observed", observation.handObserved[0])
            .put("right_observed", observation.handObserved[1])
            .put("left_valid_joint_count", observation.handJointValid[0].count { it })
            .put("right_valid_joint_count", observation.handJointValid[1].count { it })
            .put("left_presence", finiteOrNull(observation.handPresence[0]))
            .put("right_presence", finiteOrNull(observation.handPresence[1]))
            .put("left_proposal", observation.handProposalPresent[0])
            .put("right_proposal", observation.handProposalPresent[1])
            .put("left_proposal_support_mean", finiteMeanOrNull(observation.handProposalSupport[0]))
            .put("right_proposal_support_mean", finiteMeanOrNull(observation.handProposalSupport[1]))
            .put("body_available", observation.bodyAvailable)
            .put("body_valid_point_count", observation.bodyValid.count { it })
            .put("hand_delta_valid_count", evidence.handDeltaValidCount)
            .put("hand_delta_mean_magnitude", evidence.handDeltaMeanMagnitude ?: JSONObject.NULL)
            .put("hand_delta_max_magnitude", evidence.handDeltaMaxMagnitude ?: JSONObject.NULL)
            .put("roi_delta_valid_count", evidence.roiDeltaValidCount)
            .put("roi_delta_mean_magnitude", evidence.roiDeltaMeanMagnitude ?: JSONObject.NULL)
            .put("roi_delta_max_magnitude", evidence.roiDeltaMaxMagnitude ?: JSONObject.NULL)
            .put("body_delta_valid_count", evidence.bodyDeltaValidCount)
            .put("body_delta_mean_magnitude", evidence.bodyDeltaMeanMagnitude ?: JSONObject.NULL)
            .put("body_delta_max_magnitude", evidence.bodyDeltaMaxMagnitude ?: JSONObject.NULL)
            .put("observed_transition_count", evidence.observedTransitionCount)
            .put("proposal_transition_count", evidence.proposalTransitionCount)
            .put("attempt_id", activeAttemptId ?: JSONObject.NULL)
            .put("expected_gloss", activeAttemptGloss ?: expectedGloss ?: JSONObject.NULL)
            .put("pre_probability", state.probabilities[0])
            .put("active_probability", state.probabilities[1])
            .put("post_probability", state.probabilities[2])
            .put("argmax_state", state.argmaxState)
            .put("event_state_before", update.stateBefore.name)
            .put("event_state_after", update.stateAfter.name)
            .put("event_action", update.action)
            .put("candidate_open_index", diagnosticCandidateStartIndex ?: JSONObject.NULL)
            .put("candidate_open_ms", diagnosticCandidateStartMs ?: JSONObject.NULL)
            .put("candidate_active_span_ms", diagnosticCandidateStartMs?.let { start ->
                diagnosticLastActiveMs?.minus(start)
            } ?: JSONObject.NULL)
            .put("active_event_id", (if (update.stateAfter == PhoneDecoderState.EVENT_EMITTED_WAIT_REARM) {
                diagnosticLastCommittedEventId
            } else null) ?: JSONObject.NULL)
            .put("pending_event_ordinal", if (diagnosticCandidateStartIndex != null && update.event == null &&
                update.stateAfter != PhoneDecoderState.IDLE) eventCount + 1 else JSONObject.NULL)
            .put("event_completed", update.event != null)
            .put("wait_rearm_entered", update.stateBefore != PhoneDecoderState.EVENT_EMITTED_WAIT_REARM &&
                update.stateAfter == PhoneDecoderState.EVENT_EMITTED_WAIT_REARM)
            .put("event_decision_elapsed_realtime_ns", if (update.event != null) decisionElapsedNs else JSONObject.NULL)
            .put("rearm_policy", update.rearmPolicy.name)
            .put("rearm_candidate_state", update.rearmCandidateState ?: JSONObject.NULL)
            .put("rearm_timer_start_ms", update.rearmTimerStartMs ?: JSONObject.NULL)
            .put("rearm_elapsed_ms", update.rearmElapsedMs ?: JSONObject.NULL)
            .put("rearm_reason", update.rearmReason ?: JSONObject.NULL)
            .put("admission_policy", update.admissionPolicy.name)
            .put("admission_decision", update.admissionDecision ?: JSONObject.NULL)
            .put("admission_reason", update.admissionReason ?: JSONObject.NULL)
            .put("visual_evidence_ordinal", observation.sourceIndex + 1)
            .put(
                "visual_evidence_original",
                "continuous_visual/originals/frame_${(observation.sourceIndex + 1).toString().padStart(6, '0')}_original.jpg",
            )
            .put("candidate_preprocess_ms", observation.candidatePreprocessMs ?: JSONObject.NULL)
            .put("candidate_pose_inference_ms", observation.candidatePoseInferenceMs ?: JSONObject.NULL)
            .put("candidate_pose_decode_ms", observation.candidatePoseDecodeMs ?: JSONObject.NULL)
            .put("candidate_total_ms", observation.candidateTotalMs ?: JSONObject.NULL)
            .put("feature_ms", featureMs)
            .put("s2_ms", state.invocationMs)
            .put("s2_history_length", state.historyLength)
        appendJson(observationLog, observationJson)
        if (update.stateAfter == PhoneDecoderState.IDLE || update.event != null) {
            diagnosticCandidateStartIndex = null
            diagnosticCandidateStartMs = null
            diagnosticLastActiveMs = null
        }
        previousTimestampMs = observation.timestampMs
        return update.event?.let { recognizeEvent(it) }
    }

    fun snapshotJson() = JSONObject()
        .put("schema", "apphear.phone_causal_recognition.session_snapshot.v1")
        .put("observations", observationCount)
        .put("events", eventCount)
        .put("event_state", eventProducer.state.name)
        .put("rearm_policy", decoderConfig.rearmPolicy.name)
        .put("admission_policy", decoderConfig.admissionPolicy.name)
        .put("expected_gloss", expectedGloss ?: JSONObject.NULL)

    fun finalizeDiagnostics() {
        exactParityRecorder?.close()
        observationLog.flush()
        eventLog.flush()
        attemptLog.flush()
        synchronized(deliveryLog) { if (!deliveryLogClosed) deliveryLog.flush() }
        File(sessionRoot, SUMMARY_FILE).writeText(snapshotJson().toString(2))
    }

    /** Debug display delivery, not a claim about normal RecognitionActivity sentence commits. */
    fun recordUiDelivery(eventId: Int, deliveredAtNs: Long) {
        synchronized(deliveryLog) {
            // Teardown may race an already-posted UI callback. Missing delivery is visible in audit.
            if (deliveryLogClosed) return
            appendJson(deliveryLog, JSONObject()
                .put("event_id", eventId)
                .put("ui_delivery_elapsed_realtime_ns", deliveredAtNs)
                .put("ui_owner", "PerceptionVNextLiveRecognitionActivity")
                .put("normal_app_sentence_commit", false))
        }
    }

    fun beginAttempt(attemptId: Int, gloss: String, markedAtNs: Long) {
        require(activeAttemptId == null) { "PHONE_CAUSAL_ATTEMPT_ALREADY_ACTIVE" }
        activeAttemptId = attemptId
        activeAttemptGloss = gloss
        appendJson(
            attemptLog,
            JSONObject()
                .put("action", "BEGIN")
                .put("attempt_id", attemptId)
                .put("expected_gloss", gloss)
                .put("marked_at_elapsed_realtime_ns", markedAtNs)
                .put("observation_count_before_mark", observationCount)
                .put("event_count_before_mark", eventCount),
        )
    }

    fun completeAttempt(attemptId: Int, markedAtNs: Long) {
        require(activeAttemptId == attemptId) { "PHONE_CAUSAL_ATTEMPT_ID_MISMATCH" }
        appendJson(
            attemptLog,
            JSONObject()
                .put("action", "COMPLETE")
                .put("attempt_id", attemptId)
                .put("expected_gloss", activeAttemptGloss)
                .put("marked_at_elapsed_realtime_ns", markedAtNs)
                .put("observation_count_after_drain", observationCount)
                .put("event_count_after_drain", eventCount),
        )
        activeAttemptId = null
        activeAttemptGloss = null
    }

    private fun recognizeEvent(event: PhoneLogicalSignEvent): PhoneCausalResult {
        val materializerStarted = System.nanoTime()
        val window = buffer.materialize(event)
        val materializerMs = (System.nanoTime() - materializerStarted) / 1_000_000.0
        val raw = phoneRecognitionRawSequence(window.observations)
        val recognitionV2Started = System.nanoTime()
        val view = RecognitionV2.temporalView(raw, RecognitionV2.TemporalCondition.DENSE)
        val recognitionV2Ms = (System.nanoTime() - recognitionV2Started) / 1_000_000.0
        val recognitionStartNs = SystemClock.elapsedRealtimeNanos()
        val prediction = recognizer.invoke(view, RecognitionV2.FEATURE_SCHEMA)
        val recognitionCompleteNs = SystemClock.elapsedRealtimeNanos()
        val top1 = prediction.top5.first()
        val top5 = prediction.top5.map { recognizer.glosses[it] to prediction.probabilities[it] }
        val eventExpectedGloss = activeAttemptGloss ?: expectedGloss
        val expectedClass = eventExpectedGloss?.let { target ->
            recognizer.glosses.indexOfFirst { it.equals(target, ignoreCase = true) }.takeIf { it >= 0 }
        }
        val expectedRank = expectedClass?.let { target ->
            1 + prediction.probabilities.indices.count {
                prediction.probabilities[it] > prediction.probabilities[target] ||
                    (prediction.probabilities[it] == prediction.probabilities[target] && it < target)
            }
        }
        eventCount++
        val eventJson = JSONObject()
            .put("schema", "apphear.phone_causal_recognition.event.v1")
            .put("event_id", event.eventId)
            .put("logical_active_start_index", event.logicalActiveStartIndex)
            .put("logical_active_end_index", event.logicalActiveEndIndex)
            .put("logical_active_start_ms", event.logicalActiveStartMs)
            .put("logical_active_end_ms", event.logicalActiveEndMs)
            .put("terminal_post_index", event.terminalPostIndex)
            .put("terminal_post_ms", event.terminalPostMs)
            .put("commit_index", event.commitIndex)
            .put("commit_ms", event.commitMs)
            .put("recognizer_start_elapsed_realtime_ns", recognitionStartNs)
            .put("recognizer_complete_elapsed_realtime_ns", recognitionCompleteNs)
            .put("materialized_source_indices", JSONArray(window.observations.map { it.sourceIndex }))
            .put("recognition_v2_source_indices", JSONArray(view.sourceIndices.map { window.observations[it].sourceIndex }))
            .put("materialized_start_index", window.selectedStartIndex)
            .put("materialized_end_index", window.selectedEndIndex)
            .put("materialized_observation_count", window.observations.size)
            .put("requested_pre_context_ms", 250.0)
            .put("actual_pre_context_ms", window.actualPreContextMs)
            .put(
                "actual_pre_context_observation_count",
                window.observations.count { it.timestampMs < event.logicalActiveStartMs },
            )
            .put("requested_post_context_ms", 250.0)
            .put("actual_post_context_ms", window.actualPostContextMs)
            .put(
                "actual_post_context_observation_count",
                window.observations.count { it.timestampMs > event.terminalPostMs },
            )
            .put("left_censored", window.leftCensored)
            .put("right_censored", window.rightCensored)
            .put("materializer_ms", materializerMs)
            .put("recognition_v2_valid_count", view.realLength)
            .put("recognition_v2_mask_count", view.mask.count { it })
            .put("recognition_v2_ms", recognitionV2Ms)
            .put("top1_class", top1)
            .put("top1_gloss", recognizer.glosses[top1])
            .put("top1_probability", prediction.probabilities[top1])
            .put("top5", JSONArray(top5.map { (gloss, probability) ->
                JSONObject().put("gloss", gloss).put("probability", probability)
            }))
            .put("attempt_id", activeAttemptId ?: JSONObject.NULL)
            .put("expected_gloss", eventExpectedGloss ?: JSONObject.NULL)
            .put("expected_class", expectedClass ?: JSONObject.NULL)
            .put(
                "expected_probability",
                expectedClass?.let { prediction.probabilities[it] } ?: JSONObject.NULL,
            )
            .put("expected_rank", expectedRank ?: JSONObject.NULL)
            .put("recognition_invocation_ms", prediction.invocationMs)
            .put(
                "event_visual_evidence_directory",
                "continuous_visual/events/event_${event.eventId.toString().padStart(3, '0')}",
            )
            .put("genuine_observations_only", true)
            .put("interpolation", false)
            .put("duplication", false)
            .put("stale_carry", false)
        appendJson(eventLog, eventJson)
        return PhoneCausalResult(
            event,
            window,
            recognizer.glosses[top1],
            prediction.probabilities[top1],
            top5,
            prediction.invocationMs,
        )
    }

    private fun writeIdentity(context: Context) {
        val materializerContract = context.assets.open(MATERIALIZER_CONTRACT_ASSET).use { it.readBytes() }
        require(sha256(materializerContract) == MATERIALIZER_CONTRACT_SHA) {
            "PHONE_CAUSAL_MATERIALIZER_CONTRACT_DRIFT"
        }
        val value = JSONObject()
            .put("schema", "apphear.phone_causal_recognition.identity.v1")
            .put("milestone", "PHONE_REPEATED_RECOGNITION_INTEGRATION_01")
            .put("created_at_utc", utcNow())
            .put("candidate01", "FROZEN_DEBUG_PHONE_IMPLEMENTATION")
            .put("raw_schema", RecognitionV2.RAW_SCHEMA)
            .put("segmentation", s2.identityJson())
            .put("decoder", JSONObject()
                .put("reference", "PHASE8A_CONFIG_01_DIAGNOSTIC_BASELINE")
                 .put("minimum_active_ms", 133.308)
                 .put("pre_gap_reset_ms", 133.308)
                 .put("post_confirm_ms", 266.616)
                 .put("rearm_pre_stable_ms", decoderConfig.rearmPreStableMs)
                 .put("rearm_policy", decoderConfig.rearmPolicy.name)
                 .put("maximum_continuous_observation_gap_ms", decoderConfig.maximumContinuousObservationGapMs)
                 .put("admission_policy", decoderConfig.admissionPolicy.name))
            .put("materializer_contract_sha256", MATERIALIZER_CONTRACT_SHA)
            .put("recognizer", recognizer.identityJson())
            .put("recognition_v2_schema", RecognitionV2.FEATURE_SCHEMA)
            .put("training_executed", false)
            .put("exact_s2_parity_capture_enabled", exactParityRecorder != null)
            .put("expected_gloss", expectedGloss ?: JSONObject.NULL)
        File(sessionRoot, IDENTITY_FILE).writeText(value.toString(2))
    }

    private fun appendJson(writer: BufferedWriter, value: JSONObject) {
        writer.write(value.toString())
        writer.newLine()
        writer.flush()
    }

    private fun finiteOrNull(value: Float): Any = if (value.isFinite()) value else JSONObject.NULL

    private fun finiteMeanOrNull(values: FloatArray): Any {
        val finite = values.filter { it.isFinite() }
        return if (finite.isEmpty()) JSONObject.NULL else finite.average()
    }

    override fun close() {
        exactParityRecorder?.close()
        File(sessionRoot, SUMMARY_FILE).writeText(snapshotJson().toString(2))
        observationLog.close()
        eventLog.close()
        attemptLog.close()
        synchronized(deliveryLog) {
            deliveryLogClosed = true
            deliveryLog.close()
        }
        s2.close()
    }

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }

    private fun utcNow() = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }.format(Date())

    companion object {
        const val IMAGE_SEMANTICS = "UPRIGHT_UNMIRRORED_SOURCE_RGB"
        const val MATERIALIZER_CONTRACT_ASSET = "phone_causal_recognition_01/materializer_contract_frozen.json"
        const val MATERIALIZER_CONTRACT_SHA = "0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971"
        const val IDENTITY_FILE = "identity.json"
        const val OBSERVATION_LOG = "observations.jsonl"
        const val EVENT_LOG = "events.jsonl"
        const val ATTEMPT_LOG = "attempts.jsonl"
        const val SUMMARY_FILE = "session_summary.json"
        const val EXACT_PARITY_DIRECTORY = "s2_exact_parity"
    }
}
