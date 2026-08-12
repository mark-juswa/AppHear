package com.example.apphear.pipeline.recognition

import android.content.Context
import com.example.apphear.pipeline.RuntimeLog
import com.example.apphear.pipeline.features.FEATURE_DIM

private const val TAG = "AppHearRecog"

sealed interface RecognitionState {
    data object Idle : RecognitionState
    data class Signing(val candidates: List<String>) : RecognitionState
    data class Committed(val gloss: String, val classId: Int, val candidates: List<String>) : RecognitionState
}

/**
 * S4->S5->S6->S7 orchestrator. Risky low-FPS behavior is config-gated; the default path remains the
 * deployed baseline plus pre-onset feature context.
 */
class RecognitionPipeline(
    private val recognizer: Recognizer,
    private val shadowRecognizer: Phase1ShadowRecognizer?,
    private val session: SessionNormalizer,
    private val detector: SigningDetector,
    private val confirmation: Confirmation,
    private val vocab: Vocab,
    private val runtime: RuntimeConfig,
) {
    private val timeWindow = recognizer.timeWindow
    private val window = Array(timeWindow) { FloatArray(FEATURE_DIM) }
    private val preOnset = ArrayDeque<FloatArray>()
    private var count = 0
    private var frameIndex = 0L

    private val sentence = SentenceBuilder()
    val sentenceText: String get() = sentence.text()
    fun clearSentence() = sentence.clear()

    private var awaitingRelease = false
    private var lastCommit: RecognitionState.Committed? = null
    private var lastCandidates: List<String> = emptyList()
    private var baselineBlockLogged = false
    private val postCommitRearm = if (runtime.enablePostCommitRearm) {
        PostCommitRearm(runtime.postCommitDepartureFrames)
    } else {
        null
    }

    val isSigning: Boolean get() = detector.isSigning
    val poseCadenceEveryN: Int
        get() = if (runtime.enableRecognitionPoseCadence) runtime.recognitionPoseEveryN else 1

    var handedness: Handedness
        get() = session.handedness
        set(value) { session.handedness = value }

    fun processFrame(pose: FloatArray, hands: FloatArray, lowFps: Boolean = false): RecognitionState {
        frameIndex++
        session.update(pose)
        val feature = if (runtime.enablePreOnsetBuffer || detector.isSigning) session.feature(pose, hands) else null

        when (detector.update(pose, hands, lowFps)) {
            SigningEvent.ONSET -> {
                RuntimeLog.i(TAG, "S5 ONSET (signing started; mirrored=${session.isMirrored}, low_fps=$lowFps)")
                resetSign(clearPreOnset = false)
                seedPreOnset()
            }
            SigningEvent.RELEASE -> {
                val dropped = !awaitingRelease
                val snap = confirmation.lastSnapshot
                RuntimeLog.i(
                    TAG,
                    ("S5 RELEASE frame=$frameIndex (signing ended, ${if (dropped) "no commit -> dropped" else "after commit"}) " +
                        "last_s7_reason='${snap.reason}' evidence=%.3f margin=%.3f " +
                        "hand_gap=${detector.lastDiagnostics.activeHandGapFrames}")
                        .format(snap.evidence, snap.margin),
                )
                resetSign(clearPreOnset = true)
                return RecognitionState.Idle
            }
            SigningEvent.NONE -> {}
        }

        if (!detector.isSigning) {
            if (feature != null) pushPreOnset(feature)
            return RecognitionState.Idle
        }

        if (awaitingRelease) {
            val feat = feature ?: session.feature(pose, hands)
            return processPostCommitFrame(feat, lowFps)
        }

        if (count < timeWindow) {
            val feat = feature ?: session.feature(pose, hands)
            System.arraycopy(feat, 0, window[count], 0, FEATURE_DIM)
            count++
        } else {
            return RecognitionState.Signing(lastCandidates)
        }

        val probs = recognizer.infer(window, count - 1)
        shadowRecognizer?.evaluateAndLog(window, count - 1, probs, vocab, frameIndex)
        val commit = confirmation.update(probs, lowFps)
        lastCandidates = confirmation.topCandidates.map { vocab.gloss(it) }
        return if (commit != null) {
            val gloss = vocab.gloss(commit.classId)
            RuntimeLog.i(
                TAG,
                ("COMMIT '$gloss' (id=${commit.classId}) at frame ${commit.frame} candidates=$lastCandidates " +
                    "evidence=%.3f margin=%.3f low_fps=$lowFps")
                    .format(commit.evidence, commit.margin),
            )
            acceptCommit(gloss, commit)
        } else {
            RecognitionState.Signing(lastCandidates)
        }
    }

    fun resetSession() {
        session.reset()
        resetSign(clearPreOnset = true)
    }

    private fun pushPreOnset(feature: FloatArray) {
        if (!runtime.enablePreOnsetBuffer || runtime.preOnsetFrames <= 0) return
        preOnset.addLast(feature.copyOf())
        while (preOnset.size > runtime.preOnsetFrames) preOnset.removeFirst()
    }

    private fun seedPreOnset() {
        if (!runtime.enablePreOnsetBuffer || preOnset.isEmpty()) return
        var seeded = 0
        while (preOnset.isNotEmpty() && count < timeWindow) {
            val feat = preOnset.removeFirst()
            System.arraycopy(feat, 0, window[count], 0, FEATURE_DIM)
            count++
            seeded++
        }
        RuntimeLog.i(TAG, "PRE_ONSET seeded_frames=$seeded configured=${runtime.preOnsetFrames}")
    }

    private fun resetSign(clearPreOnset: Boolean) {
        clearObservation()
        awaitingRelease = false
        lastCommit = null
        lastCandidates = emptyList()
        baselineBlockLogged = false
        postCommitRearm?.reset()
        if (clearPreOnset) preOnset.clear()
    }

    private fun processPostCommitFrame(feature: FloatArray, lowFps: Boolean): RecognitionState {
        val rearm = postCommitRearm
        if (rearm == null) {
            if (runtime.enablePostCommitMeasurementLogging && !baselineBlockLogged) {
                RuntimeLog.i(
                    TAG,
                    "POST_COMMIT_BASELINE_BLOCK_START frame=$frameIndex; waiting for S5 RELEASE",
                )
                baselineBlockLogged = true
            }
            return lastCommit ?: RecognitionState.Signing(lastCandidates)
        }
        val heldState = lastCommit ?: RecognitionState.Signing(lastCandidates)

        if (count >= timeWindow) {
            RuntimeLog.i(
                TAG,
                "POST_COMMIT_WINDOW_RESET frame=$frameIndex verifying=${rearm.isVerifying}",
            )
            if (rearm.isVerifying) rearm.verificationFailed()
            clearObservation()
        }

        System.arraycopy(feature, 0, window[count], 0, FEATURE_DIM)
        count++
        val probs = recognizer.infer(window, count - 1)

        if (!rearm.isVerifying) {
            val predictedClass = top1Class(probs)
            val update = rearm.observe(predictedClass)
            if (runtime.enablePostCommitMeasurementLogging) {
                val snapshot = rearm.snapshot
                RuntimeLog.i(
                    TAG,
                    "POST_COMMIT_OBSERVE frame=$frameIndex predicted=$predictedClass " +
                        "previous=${snapshot.lastCommittedClass} candidate=${snapshot.departureCandidate} " +
                        "departure_streak=${snapshot.departureStreak} armed=${snapshot.armedClass}",
                )
            }
            when (update) {
                PostCommitRearm.DepartureUpdate.None -> {}
                is PostCommitRearm.DepartureUpdate.CandidateStarted -> RuntimeLog.i(
                    TAG,
                    "POST_COMMIT_DEPARTURE_START frame=$frameIndex candidate=${update.classId} " +
                        "required=${runtime.postCommitDepartureFrames}",
                )
                is PostCommitRearm.DepartureUpdate.CandidateCancelled -> RuntimeLog.i(
                    TAG,
                    "POST_COMMIT_DEPARTURE_CANCEL frame=$frameIndex candidate=${update.classId}",
                )
                is PostCommitRearm.DepartureUpdate.Armed -> {
                    RuntimeLog.i(
                        TAG,
                        "POST_COMMIT_REARM frame=$frameIndex candidate=${update.classId} " +
                            "departure_frames=${update.frames}; fresh S7 verification starts next frame",
                    )
                    clearObservation()
                }
            }
            return heldState
        }

        val commit = confirmation.update(probs, lowFps)
        lastCandidates = confirmation.topCandidates.map { vocab.gloss(it) }
        if (runtime.enablePostCommitMeasurementLogging) {
            val snapshot = confirmation.lastSnapshot
            RuntimeLog.i(
                TAG,
                ("POST_COMMIT_S7 frame=$frameIndex armed=${rearm.armedClass} top1=${snapshot.top1} " +
                    "evidence=%.3f margin=%.3f streak=${snapshot.streak} committed=${snapshot.committed} " +
                    "reason='${snapshot.reason}'").format(snapshot.evidence, snapshot.margin),
            )
        }
        if (commit == null) return heldState

        if (!rearm.matchesVerifiedClass(commit.classId)) {
            RuntimeLog.i(
                TAG,
                "POST_COMMIT_VERIFY_MISMATCH frame=$frameIndex armed=${rearm.armedClass} " +
                    "s7_class=${commit.classId}; no word committed",
            )
            rearm.verificationFailed()
            clearObservation()
            return heldState
        }

        val gloss = vocab.gloss(commit.classId)
        RuntimeLog.i(
            TAG,
            "POST_COMMIT_VERIFY_MATCH frame=$frameIndex class=${commit.classId} gloss='$gloss'",
        )
        return acceptCommit(gloss, commit)
    }

    private fun acceptCommit(gloss: String, commit: Commit): RecognitionState.Committed {
        sentence.add(gloss)
        val committed = RecognitionState.Committed(gloss, commit.classId, lastCandidates)
        lastCommit = committed
        awaitingRelease = true
        baselineBlockLogged = false
        if (runtime.enablePostCommitMeasurementLogging) {
            RuntimeLog.i(
                TAG,
                "POST_COMMIT_LIFECYCLE_COMMIT frame=$frameIndex class=${commit.classId} gloss='$gloss' " +
                    "rearm_enabled=${postCommitRearm != null} " +
                    "departure_frames=${runtime.postCommitDepartureFrames}",
            )
        }
        postCommitRearm?.let {
            it.onCommit(commit.classId)
            clearObservation()
        }
        return committed
    }

    private fun clearObservation() {
        count = 0
        confirmation.reset()
        for (t in 0 until timeWindow) java.util.Arrays.fill(window[t], 0f)
    }

    private fun top1Class(probs: FloatArray): Int {
        var best = 0
        for (i in 1 until probs.size) {
            if (probs[i] > probs[best]) best = i
        }
        return best
    }

    fun close() {
        shadowRecognizer?.close()
        recognizer.close()
    }

    companion object {
        fun load(context: Context): RecognitionPipeline {
            val manifest = ModelManifest.load(context).also { it.validateOrThrow() }
            val recogCfg = RecognitionConfig.load(context)
            val runtime = RuntimeConfig.load(context)
            val signingCfg = SigningConfig.load(context)
            val vocab = Vocab.load(context)
            val recognizer = Recognizer.load(context, manifest.timeWindow, manifest.numClasses)
            val shadowRecognizer = runCatching {
                Phase1ShadowRecognizer.loadIfEnabled(context)
            }.getOrElse { error ->
                RuntimeLog.w(
                    TAG,
                    "Phase 1 shadow disabled after load failure: ${error.message}; " +
                        "production recognizer continues",
                )
                null
            }
            return RecognitionPipeline(
                recognizer = recognizer,
                shadowRecognizer = shadowRecognizer,
                session = SessionNormalizer(),
                detector = SigningDetector(signingCfg, runtime),
                confirmation = Confirmation(recogCfg, manifest.numClasses),
                vocab = vocab,
                runtime = runtime,
            )
        }
    }
}


