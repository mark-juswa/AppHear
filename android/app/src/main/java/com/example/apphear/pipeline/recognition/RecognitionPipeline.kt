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
                    ("S5 RELEASE (signing ended, ${if (dropped) "no commit -> dropped" else "after commit"}) " +
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

        if (awaitingRelease) return lastCommit ?: RecognitionState.Signing(lastCandidates)

        if (count < timeWindow) {
            val feat = feature ?: session.feature(pose, hands)
            System.arraycopy(feat, 0, window[count], 0, FEATURE_DIM)
            count++
        } else {
            return RecognitionState.Signing(lastCandidates)
        }

        val probs = recognizer.infer(window, count - 1)
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
            sentence.add(gloss)
            val committed = RecognitionState.Committed(gloss, commit.classId, lastCandidates)
            lastCommit = committed
            awaitingRelease = true
            committed
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
        count = 0
        confirmation.reset()
        awaitingRelease = false
        lastCommit = null
        lastCandidates = emptyList()
        for (t in 0 until timeWindow) java.util.Arrays.fill(window[t], 0f)
        if (clearPreOnset) preOnset.clear()
    }

    fun close() = recognizer.close()

    companion object {
        fun load(context: Context): RecognitionPipeline {
            val manifest = ModelManifest.load(context).also { it.validateOrThrow() }
            val recogCfg = RecognitionConfig.load(context)
            val runtime = RuntimeConfig.load(context)
            val signingCfg = SigningConfig.load(context)
            val vocab = Vocab.load(context)
            val recognizer = Recognizer.load(context, manifest.timeWindow, manifest.numClasses)
            return RecognitionPipeline(
                recognizer = recognizer,
                session = SessionNormalizer(),
                detector = SigningDetector(signingCfg, runtime),
                confirmation = Confirmation(recogCfg, manifest.numClasses),
                vocab = vocab,
                runtime = runtime,
            )
        }
    }
}


