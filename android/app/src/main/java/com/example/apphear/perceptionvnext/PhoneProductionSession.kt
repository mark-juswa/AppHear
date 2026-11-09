package com.example.apphear.perceptionvnext

import android.content.Context
import android.os.Build
import android.util.Log
import com.example.apphear.BuildConfig
import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.data.settings.RecognitionEngineSettings
import com.example.apphear.pipeline.recognition.RecognitionState
import com.example.apphear.pipeline.recognition.SentenceBuilder
import java.security.MessageDigest

/** The real-app owner of the validated causal path; no capture or tensor logging. */
internal class PhoneProductionSession private constructor(
    private val s2: PhoneS2Runner,
    private val recognizer: RecognitionV2LiveRecognizer,
    /** Debug comparison recognizer on the identical view (logged only); null outside WORD_BLEND. */
    private val pairedRecognizer: RecognitionV2LiveRecognizer?,
    val packageId: PhoneS2Package,
    val configuration: PhoneRecognitionConfiguration,
    /** Set when EXPERIMENTAL was selected but could not load, so STABLE is running instead. */
    val fallbackReason: String? = null,
) : AutoCloseable {
    data class Update(
        val state: RecognitionState,
        val decoderState: PhoneDecoderState,
        val eventId: Int?,
        val windowSize: Int?,
        val top1Probability: Float?,
        val s2InvocationMs: Double,
        val recognitionInvocationMs: Double?,
        val evidence: RecognitionEvidence? = null,
        /** Set for every emitted sign event; null on frames with no event. Diagnostic only. */
        val commitDecision: PhoneCommitDecision? = null,
    )

    private val features = PhoneSegmentationFeatureBuilder()
    private val episode = PhoneCausalEventProducer(configuration.decoderConfig())
    private val observations = PhoneObservationRingBuffer()
    private val sentence = SentenceBuilder()
    /** Phase 1 (F-001): disabled by `-PwordCommitGate=false`, which restores the previous pass-through. */
    private val committer = PhoneEventCommitter(
        if (BuildConfig.WORD_COMMIT_GATE_ENABLED) configuration.commitPolicy() else PhoneCommitPolicy.DISABLED,
        sentence,
    )
    private var nextSourceIndex = 0
    private var heldCommit: RecognitionState.Committed? = null

    val sentenceText: String @Synchronized get() = sentence.text()
    val isReady: Boolean get() = episode.state == PhoneDecoderState.IDLE
    /** Display-only (see [phoneDisplayReady]); keeps "Initializing…" off the screen after a withheld event. */
    val isReadyForDisplay: Boolean get() = phoneDisplayReady(episode.state, heldCommit != null)
    val displayLabel: String
        get() = if (fallbackReason == null) configuration.label else "${configuration.label} (experimental unavailable)"

    @Synchronized fun clearSentence() = sentence.clear()

    /** Called only on the single CameraX analysis executor. */
    @Synchronized fun consume(observation: PhoneRawObservation): Update {
        require(observation.sourceIndex == nextSourceIndex) { "APP_PHONE_SOURCE_INDEX_DISCONTINUITY" }
        val state = s2.predict(features.derive(observation))
        observations.append(observation)
        val decision = episode.consume(
            observation.timestampMs, state.argmaxState, state.probabilities[POST_STATE].toDouble(),
        )
        nextSourceIndex++
        val event = decision.event
        if (event != null) {
            val window = observations.materialize(event)
            val raw = phoneRecognitionRawSequence(window.observations)
            val view = RecognitionV2.temporalView(raw, RecognitionV2.TemporalCondition.DENSE)
            val prediction = recognizer.invoke(view, RecognitionV2.FEATURE_SCHEMA)
            val paired = pairedRecognizer?.invoke(view, RecognitionV2.FEATURE_SCHEMA)
            // Phase 1 (F-001): the single place a top-1 becomes a committed word. A non-ACCEPT event
            // never reaches the sentence, Context Assist evidence or the UI commit state.
            val handFraction = phoneHandSpanFraction(
                window.observations, event.logicalActiveStartIndex, event.logicalActiveEndIndex,
            )
            val result = committer.decide(
                event.eventId, prediction.probabilities, prediction.top5, recognizer.glosses, handFraction,
            )
            val candidates = prediction.top5.map { recognizer.glosses[it] }
            val committed = result.committed
            if (committed == null) {
                heldCommit = null
                Log.i(TAG, "commit_gate outcome=${result.decision.outcome} reason=${result.decision.reason} " +
                    "configuration=${configuration.name} event=${event.eventId} " +
                    "window=${window.selectedStartIndex}..${window.selectedEndIndex} " +
                    "handSpanFraction=${"%.2f".format(handFraction)} " +
                    "top1Probability=${"%.3f".format(result.top1Probability)} " +
                    "margin=${"%.3f".format(result.margin)} top5=${candidates.joinToString("|")}")
                return Update(
                    RecognitionState.Idle, episode.state, event.eventId, window.observations.size,
                    result.top1Probability, state.invocationMs, prediction.invocationMs,
                    evidence = null, commitDecision = result.decision,
                )
            }
            val evidence = RecognitionEvidence.fromExistingTop5(event.eventId, event.commitMs.toLong(),
                prediction.top5, prediction.probabilities, recognizer.glosses)
            heldCommit = committed
            Log.i(TAG, "commit configuration=${configuration.name} package=${packageId.name} " +
                "event=${event.eventId} action=${decision.action} " +
                "window=${window.selectedStartIndex}..${window.selectedEndIndex} " +
                "observations=${window.observations.size} gloss=${committed.gloss} " +
                "probability=${result.top1Probability} word=${configuration.wordPackage().packageId} " +
                "margin=${"%.3f".format(result.margin)} handSpanFraction=${"%.2f".format(handFraction)} " +
                "wordMs=${"%.2f".format(prediction.invocationMs)} top5=${candidates.joinToString("|")}" +
                pairedLog(paired))
            return Update(
                committed, episode.state, event.eventId, window.observations.size,
                result.top1Probability, state.invocationMs, prediction.invocationMs, evidence,
                commitDecision = result.decision,
            )
        }
        val uiState = when (episode.state) {
            PhoneDecoderState.IDLE -> {
                heldCommit = null
                RecognitionState.Idle
            }
            PhoneDecoderState.EVENT_EMITTED_WAIT_REARM -> heldCommit ?: RecognitionState.Idle
            else -> RecognitionState.Signing(emptyList())
        }
        return Update(uiState, episode.state, null, null, null, state.invocationMs, null)
    }

    private fun pairedLog(paired: RecognitionV2LiveRecognizer.Prediction?): String {
        val other = pairedRecognizer ?: return ""
        val p = paired ?: return ""
        val p1 = p.top5.first()
        return " paired=${checkNotNull(configuration.pairedWordPackage()).packageId} " +
            "pairedGloss=${other.glosses[p1]} pairedProbability=${p.probabilities[p1]} " +
            "pairedMs=${"%.2f".format(p.invocationMs)} " +
            "pairedTop5=${p.top5.joinToString("|") { other.glosses[it] }}"
    }

    /** A new camera generation must not inherit stale temporal or perception evidence. */
    @Synchronized fun resetTemporalSession() {
        features.reset()
        s2.reset()
        episode.reset()
        observations.reset()
        nextSourceIndex = 0
        committer.reset()
        heldCommit = null
    }

    override fun close() {
        pairedRecognizer?.close()
        recognizer.close()
        s2.close()
    }

    companion object {
        private const val TAG = "AppHearPhone"
        private const val POST_STATE = 2
        private const val MATERIALIZER_ASSET = "phone_causal_recognition_01/materializer_contract_frozen.json"
        private const val MATERIALIZER_SHA = "0a59dc80fe54cb37e09fbce8aa108dbfce32bc4b5cb48b98e61619b5b3b34971"

        fun load(context: Context): PhoneProductionSession {
            require(Build.SUPPORTED_ABIS.contains("arm64-v8a")) {
                "Candidate01 currently requires arm64-v8a; this device is unsupported"
            }
            try {
                System.loadLibrary("perceptionvnext")
            } catch (error: UnsatisfiedLinkError) {
                throw IllegalStateException("Candidate01 native library is unavailable for this device", error)
            }
            val materializer = context.assets.open(MATERIALIZER_ASSET).use { it.readBytes() }
            val sha = MessageDigest.getInstance("SHA-256").digest(materializer)
                .joinToString("") { "%02x".format(it) }
            require(sha == MATERIALIZER_SHA) { "APP_PHONE_MATERIALIZER_CONTRACT_DRIFT" }
            val requested = RecognitionEngineSettings(context).current()
            if (requested == PhoneRecognitionConfiguration.STABLE) return open(context, requested, null)
            return try {
                open(context, requested, null)
            } catch (error: Throwable) {
                Log.e(TAG, "${requested.name} recognition failed to load; running STABLE", error)
                open(context, PhoneRecognitionConfiguration.STABLE, error.message ?: error.javaClass.simpleName)
            }
        }

        private fun open(
            context: Context,
            configuration: PhoneRecognitionConfiguration,
            fallbackReason: String?,
        ): PhoneProductionSession {
            val packageId = configuration.s2Package()
            val s2 = PhoneS2Runner(context, packageId)
            var recognizer: RecognitionV2LiveRecognizer? = null
            return try {
                recognizer = RecognitionV2LiveRecognizer(context, configuration.wordPackage())
                val paired = configuration.pairedWordPackage()?.let { RecognitionV2LiveRecognizer(context, it) }
                PhoneProductionSession(s2, recognizer, paired, packageId, configuration, fallbackReason).also {
                    Log.i(TAG, "configuration=${configuration.name} package=${packageId.name} " +
                        "word=${configuration.wordPackage().packageId} " +
                        "wordModel=${configuration.wordPackage().modelSha256.take(12)} " +
                        "paired=${configuration.pairedWordPackage()?.packageId ?: "none"} " +
                        "fallback=${fallbackReason != null}")
                }
            } catch (error: Throwable) {
                recognizer?.close()
                s2.close()
                throw error
            }
        }
    }
}
