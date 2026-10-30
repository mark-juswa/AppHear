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
    /** Debug comparison recognizer on the identical view (logged only); null outside WORD_BLEND. */
    private val pairedRecognizer: RecognitionV2LiveRecognizer?,
    val packageId: PhoneS2Package,
    val configuration: PhoneRecognitionConfiguration,
    /** Set when the selected configuration could not load and [configuration] is a fallback. */
    val fallbackReason: String? = null,
    /** The configuration that was selected in Settings (differs from [configuration] after a fallback). */
    val requested: PhoneRecognitionConfiguration = configuration,
    /** V4 continuous hybrid (EXPERIMENTAL_WORD_V4_HYBRID only); null keeps the event-per-word path unchanged. */
    private val hybrid: LexicalV4HybridPath? = null,
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

    /** Hybrid: a named segment waiting to be committed (at most one word is committed per observation). */
    private data class HybridWord(
        val gloss: String, val top1: Int, val prediction: RecognitionV2LiveRecognizer.Prediction,
        val segment: HybridSegment, val windowSize: Int, val windowStart: Int, val windowEnd: Int,
    )
    private val pendingHybridWords = ArrayDeque<HybridWord>()
    private var hybridWordId = 0
    private var heldCommitIndex = -1
    private val lexicalMs = ArrayDeque<Double>()

    val sentenceText: String @Synchronized get() = sentence.text()
    val isReady: Boolean get() = episode.state == PhoneDecoderState.IDLE
    val displayLabel: String
        get() = when {
            fallbackReason == null -> configuration.label
            requested.wordFallback() == configuration -> "${configuration.label} (${requested.label} unavailable)"
            else -> "${configuration.label} (experimental unavailable)"
        }

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
        if (hybrid != null) return consumeHybrid(observation, decision, state.invocationMs)
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
            val paired = pairedRecognizer?.invoke(view, RecognitionV2.FEATURE_SCHEMA)
            val evidence = RecognitionEvidence.fromExistingTop5(event.eventId, event.commitMs.toLong(),
                prediction.top5, prediction.probabilities, recognizer.glosses)
            sentence.add(gloss)
            lastCommittedEventId = event.eventId
            heldCommit = RecognitionState.Committed(gloss, top1, candidates)
            Log.i(TAG, "commit configuration=${configuration.name} package=${packageId.name} " +
                "event=${event.eventId} action=${decision.action} " +
                "window=${window.selectedStartIndex}..${window.selectedEndIndex} " +
                "observations=${window.observations.size} gloss=$gloss " +
                "probability=${prediction.probabilities[top1]} word=${configuration.wordPackage().packageId} " +
                "wordMs=${"%.2f".format(prediction.invocationMs)} top5=${candidates.joinToString("|")}" +
                pairedLog(paired))
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

    /**
     * V4 continuous hybrid: S2 events and C2 markers go to the causal resolver; every decided segment is
     * named by WORD V4 on its materialized causal window, and committed one per observation in order.
     */
    private fun consumeHybrid(observation: PhoneRawObservation, decision: PhoneDecoderUpdate, s2Ms: Double): Update {
        val path = checkNotNull(hybrid)
        val t = observation.sourceIndex
        decision.event?.let {
            require(it.eventId > lastCommittedEventId) { "APP_PHONE_DUPLICATE_EVENT_ID" }
            lastCommittedEventId = it.eventId
        }
        val segments = path.observe(t, observations.tail(HybridConstants.W), decision.event, episode.openCandidateStartIndex)
        recordLexicalMs(path.lastLexicalMs)
        for (segment in segments.sortedBy { it.start }) pendingHybridWords.addLast(nameSegment(segment))
        val word = pendingHybridWords.removeFirstOrNull()
        if (word != null) {
            hybridWordId++
            val candidates = word.prediction.top5.map { recognizer.glosses[it] }
            val evidence = RecognitionEvidence.fromExistingTop5(hybridWordId, observation.timestampMs.toLong(),
                word.prediction.top5, word.prediction.probabilities, recognizer.glosses)
            sentence.add(word.gloss)
            heldCommit = RecognitionState.Committed(word.gloss, word.top1, candidates)
            heldCommitIndex = t
            Log.i(TAG, "commit configuration=${configuration.name} hybridWord=$hybridWordId origin=${word.segment.origin} " +
                "segment=${word.segment.start}..${word.segment.end} decidedAt=${word.segment.emit} committedAt=$t " +
                "window=${word.windowStart}..${word.windowEnd} observations=${word.windowSize} gloss=${word.gloss} " +
                "probability=${word.prediction.probabilities[word.top1]} word=${configuration.wordPackage().packageId} " +
                "wordMs=${"%.2f".format(word.prediction.invocationMs)} lexicalMs=${"%.2f".format(path.lastLexicalMs)} " +
                "top5=${candidates.joinToString("|")}")
            return Update(checkNotNull(heldCommit), episode.state, hybridWordId, word.windowSize,
                word.prediction.probabilities[word.top1], s2Ms, word.prediction.invocationMs + path.lastLexicalMs, evidence)
        }
        // Hybrid words can land after the decoder is back to IDLE: keep the last word visible ~1 s.
        if (heldCommit != null && episode.state == PhoneDecoderState.IDLE && t - heldCommitIndex > HELD_WORD_OBSERVATIONS) heldCommit = null
        val uiState = heldCommit ?: when (episode.state) {
            PhoneDecoderState.IDLE, PhoneDecoderState.EVENT_EMITTED_WAIT_REARM -> RecognitionState.Idle
            else -> RecognitionState.Signing(emptyList())
        }
        return Update(uiState, episode.state, null, null, null, s2Ms, null)
    }

    private fun nameSegment(segment: HybridSegment): HybridWord {
        val event = PhoneLogicalSignEvent(
            0,
            segment.start, segment.end, observations.timestampOf(segment.start), observations.timestampOf(segment.end),
            segment.terminalPost, observations.timestampOf(segment.terminalPost),
            segment.commit, observations.timestampOf(segment.commit),
        )
        val window = observations.materialize(event)
        val view = RecognitionV2.temporalView(phoneRecognitionRawSequence(window.observations), RecognitionV2.TemporalCondition.DENSE)
        val prediction = recognizer.invoke(view, RecognitionV2.FEATURE_SCHEMA)
        val top1 = prediction.top5.first()
        return HybridWord(recognizer.glosses[top1], top1, prediction, segment, window.observations.size,
            window.selectedStartIndex, window.selectedEndIndex)
    }

    /** Live C2 cost per observation (features + model + decode), logged every [LEXICAL_LOG_EVERY] observations. */
    private fun recordLexicalMs(ms: Double) {
        lexicalMs.addLast(ms)
        if (lexicalMs.size < LEXICAL_LOG_EVERY) return
        val sorted = lexicalMs.sorted()
        Log.i(TAG, "hybridLexicalTiming observations=${sorted.size} medianMs=${"%.2f".format(sorted[sorted.size / 2])} " +
            "p95Ms=${"%.2f".format(sorted[(sorted.size * 95) / 100])} maxMs=${"%.2f".format(sorted.last())}")
        lexicalMs.clear()
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
        lastCommittedEventId = 0
        heldCommit = null
        hybrid?.reset()
        pendingHybridWords.clear()
        hybridWordId = 0
        heldCommitIndex = -1
        lexicalMs.clear()
    }

    override fun close() {
        hybrid?.close()
        pairedRecognizer?.close()
        recognizer.close()
        s2.close()
    }

    companion object {
        private const val TAG = "AppHearPhone"
        private const val POST_STATE = 2
        private const val HELD_WORD_OBSERVATIONS = 5
        private const val LEXICAL_LOG_EVERY = 100
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
            var reason: String? = null
            for (candidate in listOfNotNull(requested, requested.wordFallback())) {
                try {
                    return open(context, candidate, reason, requested)
                } catch (error: Throwable) {
                    Log.e(TAG, "${candidate.name} recognition failed to load (requested ${requested.name})", error)
                    reason = reason ?: (error.message ?: error.javaClass.simpleName)
                }
            }
            Log.e(TAG, "${requested.name} unavailable; running STABLE")
            return open(context, PhoneRecognitionConfiguration.STABLE, reason, requested)
        }

        private fun open(
            context: Context,
            configuration: PhoneRecognitionConfiguration,
            fallbackReason: String?,
            requested: PhoneRecognitionConfiguration = configuration,
        ): PhoneProductionSession {
            val packageId = configuration.s2Package()
            val s2 = PhoneS2Runner(context, packageId)
            var recognizer: RecognitionV2LiveRecognizer? = null
            var paired: RecognitionV2LiveRecognizer? = null
            return try {
                recognizer = RecognitionV2LiveRecognizer(context, configuration.wordPackage())
                paired = configuration.pairedWordPackage()?.let { RecognitionV2LiveRecognizer(context, it) }
                val hybrid = configuration.lexicalPackage()?.let { LexicalV4HybridPath(context, it) }
                PhoneProductionSession(s2, recognizer, paired, packageId, configuration, fallbackReason, requested, hybrid).also {
                    Log.i(TAG, "configuration=${configuration.name} requested=${requested.name} package=${packageId.name} " +
                        "word=${configuration.wordPackage().packageId} " +
                        "wordModel=${configuration.wordPackage().modelSha256.take(12)} " +
                        "paired=${configuration.pairedWordPackage()?.packageId ?: "none"} " +
                        "lexical=${configuration.lexicalPackage()?.let { "${it.packageId}:${it.modelSha256.take(12)}" } ?: "none"} " +
                        "fallback=${fallbackReason != null}")
                }
            } catch (error: Throwable) {
                paired?.close()
                recognizer?.close()
                s2.close()
                throw error
            }
        }
    }
}
