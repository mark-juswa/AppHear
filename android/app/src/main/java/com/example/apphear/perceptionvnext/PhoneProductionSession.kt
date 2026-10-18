package com.example.apphear.perceptionvnext

import android.content.Context
import android.os.Build
import android.util.Log
import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.data.settings.RecognitionEngineSettings
import com.example.apphear.pipeline.recognition.RecognitionState
import com.example.apphear.pipeline.recognition.SentenceBuilder
import java.security.MessageDigest

/** The real-app owner of the validated causal path; no capture or tensor logging. */
internal class PhoneProductionSession private constructor(
    private val s2: PhoneS2Runner,
    private val recognizer: RecognitionV2LiveRecognizer,
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
    )

    private val features = PhoneSegmentationFeatureBuilder()
    private val episode = PhoneCausalEventProducer(configuration.decoderConfig())
    private val observations = PhoneObservationRingBuffer()
    private val sentence = SentenceBuilder()
    private var nextSourceIndex = 0
    private var lastCommittedEventId = 0
    private var heldCommit: RecognitionState.Committed? = null

    val sentenceText: String @Synchronized get() = sentence.text()
    val isReady: Boolean get() = episode.state == PhoneDecoderState.IDLE
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
            require(event.eventId > lastCommittedEventId) { "APP_PHONE_DUPLICATE_EVENT_ID" }
            val window = observations.materialize(event)
            val raw = phoneRecognitionRawSequence(window.observations)
            val view = RecognitionV2.temporalView(raw, RecognitionV2.TemporalCondition.DENSE)
            val prediction = recognizer.invoke(view, RecognitionV2.FEATURE_SCHEMA)
            val top1 = prediction.top5.first()
            val gloss = recognizer.glosses[top1]
            val candidates = prediction.top5.map { recognizer.glosses[it] }
            val evidence = RecognitionEvidence.fromExistingTop5(event.eventId, event.commitMs.toLong(),
                prediction.top5, prediction.probabilities, recognizer.glosses)
            sentence.add(gloss)
            lastCommittedEventId = event.eventId
            heldCommit = RecognitionState.Committed(gloss, top1, candidates)
            Log.i(TAG, "commit configuration=${configuration.name} package=${packageId.name} " +
                "event=${event.eventId} action=${decision.action} " +
                "window=${window.selectedStartIndex}..${window.selectedEndIndex} " +
                "observations=${window.observations.size} gloss=$gloss " +
                "probability=${prediction.probabilities[top1]}")
            return Update(
                checkNotNull(heldCommit), episode.state, event.eventId, window.observations.size,
                prediction.probabilities[top1], state.invocationMs, prediction.invocationMs, evidence,
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

    /** A new camera generation must not inherit stale temporal or perception evidence. */
    @Synchronized fun resetTemporalSession() {
        features.reset()
        s2.reset()
        episode.reset()
        observations.reset()
        nextSourceIndex = 0
        lastCommittedEventId = 0
        heldCommit = null
    }

    override fun close() {
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
                Log.e(TAG, "EXPERIMENTAL recognition failed to load; running STABLE", error)
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
            return try {
                val recognizer = RecognitionV2LiveRecognizer(context)
                PhoneProductionSession(s2, recognizer, packageId, configuration, fallbackReason).also {
                    Log.i(TAG, "configuration=${configuration.name} package=${packageId.name} " +
                        "fallback=${fallbackReason != null}")
                }
            } catch (error: Throwable) {
                s2.close()
                throw error
            }
        }
    }
}
