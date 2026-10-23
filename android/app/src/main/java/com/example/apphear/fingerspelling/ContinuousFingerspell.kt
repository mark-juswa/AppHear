package com.example.apphear.fingerspelling

import android.content.Context
import android.os.SystemClock
import android.util.Log
import com.example.apphear.perceptionvnext.PhoneRawObservation
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors

/** Single bounded inference worker. State callbacks return to the existing camera executor. */
internal class ContinuousFingerspell(
    private val context: Context, private val models: FingerspellModels,
    resetWord: () -> Unit, private val dispatch: (() -> Unit) -> Unit,
    private val publish: (FingerspellSnapshot) -> Unit,
    /** FINGERSPELL-only practical v1 (debug flag). false == locked baseline behaviour. */
    val practical: Boolean = false,
) : AutoCloseable {
    private val owner = RecognitionModeController(resetWord)
    private val inferenceLock = Any()
    private val worker = Executors.newSingleThreadExecutor { Thread(it, "apphear-held-letter") }
    private val document = JSONObject(context.assets.open("fingerspelling/continuous_policy.json").bufferedReader().use { it.readText() })
    private val policy: HeldLetterPolicy
    @Volatile private var generation = 0
    @Volatile private var active = false
    @Volatile private var closed = false
    private var inFlight = false
    private var confirmed = ""
    private val events = java.util.ArrayDeque<JSONObject>()
    private val timestamps = java.util.ArrayDeque<Double>()
    private var inferenceCalls = 0
    private var skippedBusy = 0
    private var staleResults = 0
    private var completedDecodes = 0
    // Practical v1 state and interaction-cost counters (camera executor confined).
    private var reviewing = false
    private var deletes = 0; private var repeats = 0; private var clears = 0
    private var reviewHolds = 0; private var reviewResumes = 0; private var confirms = 0
    val mode get() = owner.mode
    val ownsFrames get() = mode == RecognitionMode.FINGERSPELL
    init {
        require(!models.visualEnabled && models.inputWidth == 405 &&
            models.manifest.getString("candidate_id") == FingerspellCapturePolicy.CANDIDATE)
        require(document.getString("schema_version") == "apphear.fingerspelling.held_letter_policy.v1")
        policy = HeldLetterPolicy(HeldLetterConfig(
            document.getDouble("window_ms"), document.getDouble("minimum_span_ms"), document.getInt("minimum_usable"),
            document.getDouble("inference_interval_ms"), document.getInt("stable_decodes"), document.getDouble("stable_span_ms"),
            document.getDouble("rearm_missing_ms"), document.getInt("rearm_missing_observations"), document.getInt("maximum_observations"),
            acceptWhileHandMissing = practical))
    }
    fun select(next: RecognitionMode) {
        if (ownsFrames) writeDiagnostics()
        val previous = mode
        // Finish any actual fingerspell invocation BEFORE WORD becomes the owner. No simultaneous recognizers.
        synchronized(inferenceLock) { generation++; active = false; owner.select(next) }
        if (practical) {
            reviewing = false
            // Same-owner reselect (activity resume, camera rebind) keeps the unconfirmed draft and its latch.
            // An owner change starts a fresh word: no stale spelling is carried into the next FINGERSPELL turn.
            if (previous == next) policy.reset(clearPreview = false, keepLatch = true)
            else { policy.reset(); confirmed = "" }
        } else policy.reset()
        timestamps.clear(); active = ownsFrames; emit()
        writeDiagnostics()
    }
    fun consume(raw: PhoneRawObservation) {
        if (!ownsFrames || !active || closed || reviewing) return
        val c = raw.fingerspellObservation()
        timestamps.addLast(c.timestampMs)
        while (timestamps.size > policy.config.maximumObservations) timestamps.removeFirst()
        policy.observe(c)
        emit()
        if (inFlight) { skippedBusy++; return }
        val window = policy.request() ?: return
        val ticket = generation; val epoch = policy.epoch; val t = window.last().timestampMs
        inFlight = true
        worker.execute {
            var result: FingerspellSingleLetterDecoder.Result? = null
            var modelMs = 0.0; var decoderMs = 0.0; var featureMs = 0.0
            var failure: Throwable? = null
            val started = SystemClock.elapsedRealtimeNanos()
            synchronized(inferenceLock) {
                if (!closed && active && ticket == generation) try {
                    // Recompute dt/motion from SELECTED RAW; never slice stateful prederived features.
                    val feature = models.manifest.getJSONObject("feature_config")
                    val adapter = FingerspellingFeatureAdapterV1(
                        feature.getDouble("minimum_scale_short_side_ratio").toFloat(),
                        feature.getDouble("maximum_motion_gap_seconds").toFloat())
                    val frames = window.map { adapter.derive(it) }
                    featureMs = (SystemClock.elapsedRealtimeNanos() - started) / 1e6
                    val modelStart = SystemClock.elapsedRealtimeNanos()
                    val logits = models.logits(frames); inferenceCalls++
                    modelMs = (SystemClock.elapsedRealtimeNanos() - modelStart) / 1e6
                    val decodeStart = SystemClock.elapsedRealtimeNanos()
                    result = FingerspellSingleLetterDecoder.decode(logits, models.blankPenalty)
                    decoderMs = (SystemClock.elapsedRealtimeNanos() - decodeStart) / 1e6
                } catch (error: Throwable) { failure = error }
            }
            dispatch {
                inFlight = false
                if (closed || !active || generation != ticket || !ownsFrames) { staleResults++; return@dispatch }
                if (failure != null) { Log.e("AppHearHeldLetter", "Inference failed", failure); emit("Recognition unavailable. Retry or select WORD."); return@dispatch }
                val decoded = result ?: return@dispatch
                val beforeAcceptance = policy.acceptanceState(t)
                val added = policy.accept(epoch, t, decoded.text)
                val afterAcceptance = policy.acceptanceState(t)
                completedDecodes++
                val event = JSONObject().put("timestamp_ms", t).put("window_observations", window.size)
                    .put("generation",ticket).put("window_start_ms",window.first().timestampMs)
                    .put("usable_observations", window.count { HeldLetterPolicy.usable(it) })
                    .put("acceptance_reason",policy.lastAcceptanceReason.name)
                    .put("request_epoch",epoch).put("epoch_before",beforeAcceptance.epoch).put("epoch_after",afterAcceptance.epoch)
                    .put("waiting_for_hand",beforeAcceptance.waitingForHand).put("missing_observations",beforeAcceptance.missingObservations)
                    .put("candidate_before",beforeAcceptance.candidate).put("candidate_after",afterAcceptance.candidate)
                    .put("candidate_count_before",beforeAcceptance.candidateCount).put("candidate_count_after",afterAcceptance.candidateCount)
                    .put("candidate_span_ms_before",beforeAcceptance.candidateSpanMs).put("candidate_span_ms_after",afterAcceptance.candidateSpanMs)
                    .put("latch_before",beforeAcceptance.latch).put("latch_after",afterAcceptance.latch)
                    .put("raw_letter", decoded.text).put("added_to_preview", added).put("preview", policy.preview)
                    .put("model_ms", modelMs).put("decoder_ms", decoderMs).put("feature_ms", featureMs)
                    .put("worker_ms", (SystemClock.elapsedRealtimeNanos() - started) / 1e6)
                events.addLast(event); while (events.size > policy.config.maximumObservations) events.removeFirst()
                emit(); if (added || completedDecodes % 10 == 0) writeDiagnostics()
            }
        }
    }
    fun confirm() {
        if (!ownsFrames || policy.preview.isEmpty()) return
        if (practical) confirms++
        confirmed += policy.preview
        invalidate(clearPreview = true, keepLatch = true)
        emit("Spelling added. Hold the next letter."); writeDiagnostics()
    }
    fun retry() { invalidate(); emit(); writeDiagnostics() }
    fun clear() { if (practical) clears++; confirmed = ""; invalidate(); emit(); writeDiagnostics() }
    /** Practical v1: remove only the last draft letter (no whole-word re-spelling for one wrong letter). */
    fun deleteLast() {
        if (!practical || !ownsFrames || reviewing) return
        synchronized(inferenceLock) { generation++ }
        if (policy.deleteLast()) { deletes++; emit(); writeDiagnostics() }
    }
    /** Practical v1: explicit double letter (e.g. the second L in HELLO) without lowering the hand. */
    fun repeatLast() {
        if (!practical || !ownsFrames || reviewing) return
        synchronized(inferenceLock) { generation++ }
        if (policy.repeatLast()) { repeats++; emit(); writeDiagnostics() }
    }
    /** Practical v1: no letter can be appended while the user reviews, so a confirmation cannot be invalidated. */
    fun holdForReview() {
        if (!practical || !ownsFrames || reviewing) return
        synchronized(inferenceLock) { generation++ }
        reviewing = true; reviewHolds++; emit()
    }
    fun resumeAfterReview() {
        if (!practical || !reviewing) return
        synchronized(inferenceLock) { generation++ }
        reviewing = false; reviewResumes++
        policy.reset(clearPreview = false, keepLatch = true); timestamps.clear(); emit()
    }
    private fun invalidate(clearPreview: Boolean = true, keepLatch: Boolean = false) {
        synchronized(inferenceLock) { generation++ }
        policy.reset(clearPreview, keepLatch)
    }
    fun pause() {
        synchronized(inferenceLock) { generation++; active = false; owner.pause() }
        writeDiagnostics(); timestamps.clear()
        // Practical v1: an interruption (screen off, app switch, camera rebind) must not erase the draft.
        if (practical) policy.reset(clearPreview = false, keepLatch = true) else policy.reset()
        emit("Recognition paused")
    }
    private fun emit(message: String? = null) {
        if (practical) { emitPractical(message); return }
        val text = message ?: when {
            !ownsFrames -> "WORD mode"
            policy.waitingForHand -> "Show your full hand. Lower it briefly to repeat a letter."
            policy.preview.isNotEmpty() -> "Check spelling, then Use. Hold the next letter."
            else -> "Hold ONE letter until it appears. Lower your hand to repeat it."
        }
        publish(FingerspellSnapshot(mode, if (policy.preview.isEmpty()) FingerspellPhase.CAPTURING else FingerspellPhase.PREVIEW,
            policy.preview, confirmed, policy.windowCount, text,
            currentLetter = if(ownsFrames) policy.currentLetter else ""))
    }
    /** Practical v1 guidance: what to do next and how far the held letter is from being added. */
    private fun emitPractical(message: String?) {
        val latch = policy.latch; val candidate = policy.candidateLetter
        val target = policy.config.stableDecodes
        val text = message ?: when {
            !ownsFrames -> "WORD mode"
            reviewing -> "Paused while you review the spelling"
            policy.waitingForHand -> if (policy.preview.isEmpty()) "Show your hand to start spelling" else "Hand out of view"
            candidate.isNotEmpty() -> "Holding $candidate (${minOf(policy.candidateProgress, target)}/$target)"
            latch.isNotEmpty() && policy.preview.endsWith(latch) -> "Added $latch. Hold the next letter, or tap Hear to review"
            policy.preview.isNotEmpty() -> "Hold the next letter, or tap Hear to review"
            else -> "Hold one letter steady until it is added"
        }
        publish(FingerspellSnapshot(mode, if (policy.preview.isEmpty()) FingerspellPhase.CAPTURING else FingerspellPhase.PREVIEW,
            policy.preview, confirmed, policy.windowCount, text,
            currentLetter = if (ownsFrames && !reviewing) policy.currentLetter else "",
            practical = true, reviewing = reviewing))
    }

    private fun writeDiagnostics() {
        runCatching {
            val span = if (timestamps.size > 1) (timestamps.last - timestamps.first) / 1000.0 else 0.0
            val report = JSONObject().put("schema_version", "apphear.fingerspelling.continuous_diagnostic.v1")
                .put("mode", mode.name).put("policy", document).put("model_manifest", models.manifest)
                .put("preview", policy.preview).put("confirmed", confirmed).put("inference_calls", inferenceCalls)
                .put("acceptance_diagnostics_version","apphear.fingerspelling.acceptance_diagnostic.v1")
                .put("completed_decodes",completedDecodes).put("skipped_busy", skippedBusy).put("stale_results", staleResults)
                .put("observations_in_cadence_window", timestamps.size).put("span_seconds", span)
                .put("cadence", if (span > 0) (timestamps.size - 1) / span else JSONObject.NULL)
                .put("events", JSONArray(events.toList())).put("training", false).put("retained_rgb_or_landmarks", false)
                .put("actual_decoder",FingerspellSingleLetterDecoder.VERSION).put("blank_penalty",models.blankPenalty.toDouble())
                .put("beam_executed",false).put("cadence_scope","LAST_64_OBSERVATIONS_WITHIN_CURRENT_ACTIVE_EPISODE")
                .put("accuracy_claim", "NONE").put("no_language_model", true)
            if (practical) report.put("practical_v1", JSONObject().put("accept_while_hand_missing", true)
                .put("deletes", deletes).put("repeats", repeats).put("clears", clears).put("confirms", confirms)
                .put("review_holds", reviewHolds).put("review_resumes", reviewResumes).put("reviewing", reviewing))
            File(context.filesDir, "fingerspell_continuous.json").writeText(report.toString(2))
            if (ownsFrames && timestamps.size > 1) {
                File(context.filesDir, "fingerspell_continuous_last_active.json").writeText(report.toString(2))
            }
        }.onFailure { Log.e("AppHearHeldLetter", "Diagnostic write failed", it) }
    }
    override fun close() {
        synchronized(inferenceLock) { closed = true; active = false; generation++; models.close() }
        worker.shutdown()
    }
}
