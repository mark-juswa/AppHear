package com.example.apphear.sentenceassist

import android.content.Context
import android.os.SystemClock
import android.util.Log
import com.example.apphear.BuildConfig
import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.conversation.ConversationTimeline
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * SHADOW-mode coordinator for one Recognition screen. It renders in the background after each
 * committed sign (debounced) and records what a visible build would have offered when Hear is
 * tapped, including whether the rendering was already ready. It only reads recognition state and
 * only writes logcat (tag [TAG]); it never changes RECOGNIZED, Hear text, TTS or Context Assist.
 * All calls are on the main thread.
 */
class SentenceAssistShadow private constructor(private val scope: CoroutineScope, private val appContext: Context) {
    private data class Key(val glosses: List<String>, val withEvidence: Boolean, val hearingTurnId: Long?)

    private var pipeline: ShadowRenderPipeline? = null
    private var policy: SentenceAssistPolicy? = null
    private var promptVersion = ""
    private var inFlight: Pair<Key, Deferred<ShadowOutcome>>? = null
    private var latest: Pair<Key, ShadowOutcome>? = null

    private fun loadAssets() {
        scope.launch {
            try {
                val assets = withContext(Dispatchers.IO) { SentenceAssistAssetLoader(appContext).load() }
                val key = BuildConfig.CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY
                val prompt = SentencePrompt(assets.template, assets.lexicon, assets.policy, assets.substitutionPolicy)
                pipeline = ShadowRenderPipeline(
                    renderer = GeminiSentenceRenderer(key, assets.template, prompt, assets.policy.renderTimeoutMs),
                    fallback = PlainGlossRenderer(assets.lexicon),
                    validator = GroundingValidator(assets.lexicon, assets.policy, assets.substitutionPolicy),
                    timeoutMs = assets.policy.renderTimeoutMs,
                    clockMs = SystemClock::elapsedRealtime,
                )
                policy = assets.policy
                promptVersion = assets.template.promptVersion
                Log.i(TAG, ConversationTimeline.format("shadow_ready", SystemClock.elapsedRealtime(),
                    System.currentTimeMillis(), listOf("prompt" to promptVersion, "gemini_key" to key.isNotBlank())))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                Log.w(TAG, "[sentenceassist/shadow] disabled: assets unavailable", error)
            }
        }
    }

    /** After each committed sign, with the screen's current RECOGNIZED text and Top-5 evidence. */
    fun signsChanged(recognizedText: String, evidence: List<RecognitionEvidence>, evidenceComplete: Boolean,
                     hearingText: String?, hearingTurnId: Long?) {
        val pipeline = pipeline ?: return
        val policy = policy ?: return
        val debounceMs = policy.debounceMs
        val turn = SignedTurnAssembler.assemble(recognizedText, evidence, evidenceComplete, policy.maxGlosses)
            ?: return reset()
        val key = Key(turn.glosses, turn.evidence != null, hearingTurnId)
        if (latest?.first == key || inFlight?.first == key) return
        inFlight?.second?.cancel()
        val request = RenderRequest(turn, hearingText)
        val deferred = scope.async {
            delay(debounceMs)
            pipeline.run(request)
        }
        inFlight = key to deferred
        scope.launch {
            val outcome = try { deferred.await() } catch (_: CancellationException) { return@launch }
            if (inFlight?.second === deferred) inFlight = null
            latest = key to outcome
            log("sign", outcome, hearingTurnId, readyAtHear = null, waitMs = null)
        }
    }

    /** When Hear speaks the RECOGNIZED text: record what a visible build would have offered. */
    fun hearTapped(recognizedText: String, evidence: List<RecognitionEvidence>, evidenceComplete: Boolean,
                   hearingText: String?, hearingTurnId: Long?) {
        val pipeline = pipeline ?: return
        val policy = policy ?: return
        val turn = SignedTurnAssembler.assemble(recognizedText, evidence, evidenceComplete, policy.maxGlosses) ?: return
        val key = Key(turn.glosses, turn.evidence != null, hearingTurnId)
        latest?.takeIf { it.first == key }?.let {
            log("hear", it.second, hearingTurnId, readyAtHear = true, waitMs = 0L)
            return
        }
        val tappedAt = SystemClock.elapsedRealtime()
        val pending = inFlight?.takeIf { it.first == key }?.second
        scope.launch {
            val outcome = try {
                pending?.await() ?: pipeline.run(RenderRequest(turn, hearingText))
            } catch (_: CancellationException) {
                return@launch
            }
            log("hear", outcome, hearingTurnId, readyAtHear = false, waitMs = SystemClock.elapsedRealtime() - tappedAt)
        }
    }

    /** Clear, a new hearing turn, or the screen closing: drop pending work and cached results. */
    fun reset() {
        inFlight?.second?.cancel()
        inFlight = null
        latest = null
    }

    private fun log(trigger: String, outcome: ShadowOutcome, hearingTurnId: Long?, readyAtHear: Boolean?, waitMs: Long?) {
        Log.i(TAG, ConversationTimeline.format("render", SystemClock.elapsedRealtime(), System.currentTimeMillis(), listOf(
            "trigger" to trigger,
            "prompt" to promptVersion,
            "hearing_turn" to hearingTurnId,
            "glosses" to outcome.turn.glosses.joinToString(" "),
            "evidence" to (outcome.turn.evidence != null),
            "ai_status" to outcome.aiStatus.name,
            "reject_reason" to outcome.rejectReason?.name,
            "reject_detail" to outcome.rejectDetail,
            "ai_sentence" to outcome.aiSentence,
            "substitutions" to outcome.aiSubstitutions.joinToString(",") { "${it.eventIndex}:${it.gloss}" },
            "words" to outcome.acceptedWords.joinToString("|") { "${it.text}/${it.source.name}" },
            "fallback" to outcome.fallbackSentence,
            "chosen" to outcome.chosenSentence,
            "latency_ms" to outcome.latencyMs,
            "ready_at_hear" to readyAtHear,
            "wait_ms" to waitMs,
        )))
    }

    companion object {
        const val TAG = "AppHearSentenceAssist"

        /** Null unless the build is in SHADOW mode; assets load asynchronously off the main thread. */
        fun create(context: Context, scope: CoroutineScope): SentenceAssistShadow? {
            if (SentenceAssistMode.current != SentenceAssistMode.SHADOW) return null
            return SentenceAssistShadow(scope, context.applicationContext).also { it.loadAssets() }
        }
    }
}
