package com.example.apphear.sentenceassist

import android.content.Context
import android.os.SystemClock
import android.util.Log
import com.example.apphear.BuildConfig
import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.conversation.ConversationTimeline
import com.example.apphear.llm.LlmFallback
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Sentence-assist coordinator for one Recognition screen. It renders in the background after each
 * committed sign (debounced) and logs every rendering and Hear (tag [TAG]), including whether the
 * rendering was ready in time. It only reads recognition state and never changes SentenceBuilder or
 * Context Assist. SHADOW mode changes nothing on screen; in VISIBLE mode the screen shows
 * [displayState] in RECOGNIZED ("…" while pending, then the sentence) and Hear speaks the accepted
 * sentence. All calls are on the main thread.
 */
class SentenceAssistShadow private constructor(private val scope: CoroutineScope, private val appContext: Context) {
    private data class Key(val glosses: List<String>, val withEvidence: Boolean, val hearingTurnId: Long?)

    private var pipeline: ShadowRenderPipeline? = null
    private var plain: PlainGlossRenderer? = null
    private var policy: SentenceAssistPolicy? = null
    private var promptVersion = ""
    private var inFlight: Pair<Key, Deferred<ShadowOutcome>>? = null
    private var latest: Pair<Key, ShadowOutcome>? = null

    /** Called on the main thread when a rendering for the latest signed words completes. */
    var onRendered: ((ShadowOutcome) -> Unit)? = null

    private fun loadAssets() {
        scope.launch {
            try {
                val assets = withContext(Dispatchers.IO) { SentenceAssistAssetLoader(appContext).load() }
                val key = BuildConfig.CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY
                val prompt = SentencePrompt(assets.template, assets.lexicon, assets.policy, assets.substitutionPolicy)
                val gemini = GeminiSentenceRenderer(key, assets.template, prompt, assets.policy.renderTimeoutMs)
                val backup = LlmFallback.client()?.let {
                    OpenAiCompatibleSentenceRenderer(it, assets.template, prompt, assets.policy.renderTimeoutMs)
                }
                pipeline = ShadowRenderPipeline(
                    renderer = HedgedSentenceRenderer(gemini, backup, LlmFallback.hedge),
                    fallback = PlainGlossRenderer(assets.lexicon).also { plain = it },
                    validator = GroundingValidator(assets.lexicon, assets.policy, assets.substitutionPolicy),
                    timeoutMs = assets.policy.renderTimeoutMs,
                    clockMs = SystemClock::elapsedRealtime,
                )
                policy = assets.policy
                promptVersion = assets.template.promptVersion
                Log.i(TAG, ConversationTimeline.format("shadow_ready", SystemClock.elapsedRealtime(),
                    System.currentTimeMillis(), listOf("prompt" to promptVersion, "gemini_key" to key.isNotBlank(),
                    "fallback_model" to LlmFallback.client()?.model)))
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
        // A single sign gives the AI nothing to arrange: show it in plain form, no network call.
        if (turn.glosses.size < policy.minGlossesForAi) return reset()
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
            val current = inFlight?.second === deferred
            if (current) inFlight = null
            latest = key to outcome
            log("sign", outcome, hearingTurnId, readyAtHear = null, waitMs = null)
            if (current) onRendered?.invoke(outcome)
        }
    }

    /** What the RECOGNIZED area should show for these words. Text is never held back for the AI. */
    sealed interface DisplayState {
        /** Assistant not ready (assets loading) or nothing to show: show the words as recognized. */
        data object Idle : DisplayState
        /** The plain words, shown at once; [improving] while an AI rendering of them is in progress. */
        data class Plain(val sentence: String, val improving: Boolean) : DisplayState
        /** Finished: the grounded AI sentence when accepted, otherwise the plain fallback. */
        data class Done(val outcome: ShadowOutcome) : DisplayState
    }

    /**
     * Matches on the words and hearing turn only, not on whether Top-5 evidence was attached, so
     * the sentence stays on screen after Hear clears the evidence for the next turn.
     */
    fun displayState(recognizedText: String, hearingTurnId: Long?): DisplayState {
        val policy = policy ?: return DisplayState.Idle
        val plain = plain ?: return DisplayState.Idle
        val turn = SignedTurnAssembler.assemble(recognizedText, emptyList(), false, policy.maxGlosses)
            ?: return DisplayState.Idle
        fun same(key: Key) = key.glosses == turn.glosses && key.hearingTurnId == hearingTurnId
        latest?.takeIf { same(it.first) }?.let { return DisplayState.Done(it.second) }
        val improving = inFlight?.let { same(it.first) } == true
        return DisplayState.Plain(plain.plain(turn).sentence, improving)
    }

    /** When Hear is tapped: record what was (or would have been) offered and what was spoken. */
    fun hearTapped(recognizedText: String, evidence: List<RecognitionEvidence>, evidenceComplete: Boolean,
                   hearingText: String?, hearingTurnId: Long?, spokeAi: Boolean = false) {
        val pipeline = pipeline ?: return
        val policy = policy ?: return
        val turn = SignedTurnAssembler.assemble(recognizedText, evidence, evidenceComplete, policy.maxGlosses) ?: return
        val key = Key(turn.glosses, turn.evidence != null, hearingTurnId)
        latest?.takeIf { it.first == key }?.let {
            log("hear", it.second, hearingTurnId, readyAtHear = true, waitMs = 0L, spokeAi = spokeAi)
            return
        }
        val tappedAt = SystemClock.elapsedRealtime()
        val pending = inFlight?.takeIf { it.first == key }?.second
        // VISIBLE mode never makes an extra AI call just to log Hear; SHADOW measures what it would have been.
        if (pending == null && (SentenceAssistMode.current == SentenceAssistMode.VISIBLE ||
                turn.glosses.size < policy.minGlossesForAi)) return
        scope.launch {
            val outcome = try {
                pending?.await() ?: pipeline.run(RenderRequest(turn, hearingText))
            } catch (_: CancellationException) {
                return@launch
            }
            log("hear", outcome, hearingTurnId, readyAtHear = false, waitMs = SystemClock.elapsedRealtime() - tappedAt,
                spokeAi = spokeAi)
        }
    }

    /** Clear, a new hearing turn, or the screen closing: drop pending work and cached results. */
    fun reset() {
        inFlight?.second?.cancel()
        inFlight = null
        latest = null
    }

    private fun log(trigger: String, outcome: ShadowOutcome, hearingTurnId: Long?, readyAtHear: Boolean?, waitMs: Long?,
                    spokeAi: Boolean? = null) {
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
            "ai_source" to outcome.aiSource,
            "ready_at_hear" to readyAtHear,
            "wait_ms" to waitMs,
            "mode" to SentenceAssistMode.current.name,
            "hear_spoke_ai" to spokeAi,
        )))
    }

    companion object {
        const val TAG = "AppHearSentenceAssist"

        /** Null when the build's mode is OFF; assets load asynchronously off the main thread. */
        fun create(context: Context, scope: CoroutineScope): SentenceAssistShadow? {
            if (SentenceAssistMode.current == SentenceAssistMode.OFF) return null
            return SentenceAssistShadow(scope, context.applicationContext).also { it.loadAssets() }
        }
    }
}
