package com.example.apphear.contextassist

import android.util.Log
import com.example.apphear.BuildConfig
import org.json.JSONArray
import org.json.JSONObject

/** Opt-in synthetic-text diagnostic export only. No product-state writes or retained evidence. */
internal object Stage3Diagnostics {
    private const val TAG = "AppHearStage3"
    private var nextEvaluationId = 1L
    private val enabled: Boolean get() = BuildConfig.DEBUG &&
        BuildConfig.CONTEXT_PHRASE_ASSIST_ENABLED && BuildConfig.CONTEXT_PHRASE_CAPTURE_ENABLED

    private fun emit(kind: String, fields: JSONObject.() -> Unit) {
        if (!enabled) return
        // A diagnostic failure must never interrupt recognition, cache publication, or Hear.
        runCatching {
            val record = JSONObject().put("version", 1).put("kind", kind)
                .put("processId", android.os.Process.myPid())
                .put("wallTimeMs", System.currentTimeMillis())
            record.fields()
            Log.i(TAG, record.toString())
        }
    }

    fun cached(turnId: Long, turns: List<ConversationTurn>, candidates: List<ReplyCandidate>) {
        if (!enabled) return
        emit("cache") { put("hearingTurnId", turnId); put("candidateCount", candidates.size) }
        turns.forEach { turn ->
            emit("conversation") {
                put("hearingTurnId", turnId); put("turnId", turn.id)
                put("speaker", turn.speaker.name); put("source", turn.source.name)
                put("text", turn.text.take(500)); put("textTruncated", turn.text.length > 500)
            }
        }
        candidates.forEachIndexed { index, candidate ->
            emit("cached_candidate") {
                put("hearingTurnId", turnId); put("index", index)
                put("naturalText", candidate.naturalText)
                put("expectedConcepts", JSONArray(candidate.concepts))
            }
        }
        emit("cache_complete") { put("hearingTurnId", turnId); put("candidateCount", candidates.size) }
    }

    fun committed(evidence: RecognitionEvidence) {
        emit("committed_event") { putEvidence(evidence) }
    }

    fun evaluated(evaluation: ShadowEvaluation, incomplete: Boolean) {
        if (!enabled) return
        val id = nextEvaluationId++
        emit("evaluation") {
            put("evaluationId", id); put("rawSentence", evaluation.rawSentence)
            put("eventIds", JSONArray(evaluation.evidence.map { it.eventId }))
            put("reason", evaluation.reason.name); put("incomplete", incomplete)
            put("wouldChangeRaw", evaluation.wouldChangeRaw)
            put("assistedConcepts", evaluation.assistedCandidate?.let { JSONArray(it.assistedGlosses) }
                ?: JSONObject.NULL)
            put("naturalText", evaluation.assistedCandidate?.naturalText ?: JSONObject.NULL)
            put("candidateCount", evaluation.predictions.size)
        }
        evaluation.evidence.forEach { event ->
            emit("evaluation_event") { put("evaluationId", id); putEvidence(event) }
        }
        evaluation.predictions.forEachIndexed { index, candidate ->
            emit("evaluation_candidate") {
                put("evaluationId", id); put("index", index)
                put("naturalText", candidate.naturalText)
                put("expectedConcepts", JSONArray(candidate.concepts))
            }
        }
        emit("evaluation_complete") { put("evaluationId", id) }
    }

    private fun JSONObject.putEvidence(evidence: RecognitionEvidence) {
        put("eventId", evidence.eventId); put("timestampMs", evidence.timestampMs)
        put("top1", evidence.originalGloss)
        put("topK", JSONArray(evidence.topK.map {
            JSONObject().put("label", it.gloss).put("score", it.score.toDouble())
        }))
    }
}
