package com.example.apphear.contextassist

import android.content.Context
import android.util.Log
import com.example.apphear.BuildConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

/** One process owner; prediction outlives a Text-to-ASL view and is versioned by hearing turn. */
object ConversationPhraseAssist {
    private const val TAG = "AppHearPhraseAssist"
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val context = ConversationContext()
    private val history = ArrayDeque<ShadowEvaluation>()
    private val presentation = MutableStateFlow(PhraseAssistUiState())
    @Volatile private var cachedPolicy: PhraseMatchPolicy? = null

    val enabled: Boolean get() = BuildConfig.CONTEXT_PHRASE_ASSIST_ENABLED
    val presentationState = presentation.asStateFlow()

    fun recordHearingMessage(appContext: Context, text: String, source: ConversationSource): Job? {
        if (!enabled || text.isBlank()) return null
        val turn = context.add(ConversationSpeaker.HEARING, source, text, System.currentTimeMillis())
        presentation.value = presentation.value.hearingTurn(turn)
        val turns = context.snapshot()
        val provider = provider()
        return scope.launch {
            val candidatesAndVocabulary = try {
                withContext(Dispatchers.IO) {
                    if (cachedPolicy == null) cachedPolicy = loadPolicy(appContext)
                    val request = PredictionRequest(turn.id, turns, supportedGlosses(appContext))
                    predictValidated(provider, request, 10_000)
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                Log.w(TAG, "Prediction unavailable; raw recognition remains active", error)
                emptyList()
            }
            if (context.setReplies(turn.id, candidatesAndVocabulary)) {
                presentation.value = presentation.value.predictions(turn.id, candidatesAndVocabulary)
                Stage3Diagnostics.cached(turn.id, turns, candidatesAndVocabulary)
                Log.i(TAG, "hearing_turn=${turn.id} reply_candidates=${candidatesAndVocabulary.size}")
            }
        }
    }

    fun evaluateShadowTurn(evidence: List<RecognitionEvidence>, rawSentence: String,
                           incomplete: Boolean = false): ShadowEvaluation {
        val rawEvents = evidence.toList()
        val hearingTurnId = if (enabled) context.latestHearingTurnId() else null
        val replies = if (enabled) context.finishReplyWindow() else emptyList()
        val (candidate, reason) = when {
            !enabled -> null to ShadowReason.DISABLED
            incomplete -> null to ShadowReason.INCOMPLETE_EVIDENCE
            rawEvents.isEmpty() -> null to ShadowReason.NO_EVIDENCE
            replies.isEmpty() -> null to ShadowReason.NO_PREDICTIONS
            else -> runCatching {
                PhraseMatcher(checkNotNull(cachedPolicy)).interpret(rawEvents, replies)
            }.fold(
                onSuccess = { match ->
                    if (match.matched) match to ShadowReason.MATCH
                    else null to ShadowReason.NO_MATCH_OR_AMBIGUOUS
                },
                onFailure = { error ->
                    Log.w(TAG, "Shadow matching unavailable", error)
                    null to ShadowReason.MATCHER_UNAVAILABLE
                },
            )
        }
        val evaluation = ShadowEvaluation(rawSentence.trim(), rawEvents, replies.toList(),
            candidate, candidate != null && candidate.assistedGlosses != rawEvents.map { it.originalGloss },
            reason)
        if (enabled) {
            presentation.value = presentation.value.evaluated(hearingTurnId, evaluation)
            // Conversation history follows what Hear communicated; evaluation keeps the event sequence.
            if (evaluation.rawSentence.isNotBlank()) {
                context.add(ConversationSpeaker.DEAF, ConversationSource.SIGN_TO_TEXT,
                    evaluation.rawSentence, System.currentTimeMillis())
            }
            history.addLast(evaluation)
            while (history.size > 6) history.removeFirst()
            Stage3Diagnostics.evaluated(evaluation, incomplete)
            Log.i(TAG, "shadow raw_sentence=${evaluation.rawSentence} " +
                "event_ids=${rawEvents.map { it.eventId }} top5=${rawEvents.map { it.topK }} " +
                "predictions=${evaluation.predictions} " +
                "assisted=${candidate?.assistedGlosses} natural=${candidate?.naturalText} " +
                "would_change=${evaluation.wouldChangeRaw} reason=$reason")
        }
        return evaluation
    }

    /** Read-only live preview after a committed sign; Hear still owns turn finalization. */
    fun previewSupportedTurn(evidence: List<RecognitionEvidence>, rawSentence: String,
                             incomplete: Boolean = false) {
        if (!enabled) return
        val turnId = context.latestHearingTurnId() ?: return
        val replies = context.repliesForLatestHearingTurn()
        if (incomplete || evidence.isEmpty() || replies.isEmpty()) return
        val match = runCatching {
            PhraseMatcher(checkNotNull(cachedPolicy)).interpret(evidence, replies)
        }.onFailure { Log.w(TAG, "Live advisory unavailable", it) }.getOrNull() ?: return
        if (!match.matched) return
        presentation.value = presentation.value.evaluated(turnId,
            ShadowEvaluation(rawSentence.trim(), evidence.toList(), replies, match,
                match.assistedGlosses != evidence.map { it.originalGloss }, ShadowReason.MATCH))
    }

    /** Read-only context identity for exclusive recognition routing; never a predicted reply. */
    fun activeHearingTurnId(): Long? = if(enabled) context.latestHearingTurnId() else null

    /** Called only after explicit spelling review. No WORD matcher or recognition mutation. */
    fun recordConfirmedSpelling(actualText: String, expectedHearingTurnId: Long?): Boolean {
        if(!enabled || actualText.isBlank() || actualText.any { it !in 'A'..'Z' && it!=' ' } ||
            context.latestHearingTurnId()!=expectedHearingTurnId) return false
        context.finishReplyWindow()
        context.add(ConversationSpeaker.DEAF,ConversationSource.SIGN_TO_TEXT,actualText,System.currentTimeMillis())
        presentation.value=PhraseAssistUiState()
        return true
    }

    fun recentTurns(): List<ConversationTurn> = context.snapshot()
    fun recentShadowEvaluations(): List<ShadowEvaluation> = history.toList()
    /** Keep conversation predictions visible; put visually supported prefixes first. */
    fun visibleRepliesForEvidence(evidence: List<RecognitionEvidence>): List<String> {
        if (!enabled) return emptyList()
        val turnId = context.latestHearingTurnId() ?: return emptyList()
        if (turnId != presentation.value.hearingTurnId) return emptyList()
        val replies = context.repliesForLatestHearingTurn()
        if (evidence.isEmpty()) return replies.map { it.naturalText }
        val policy = cachedPolicy ?: return replies.map { it.naturalText }
        return EvidenceAwareReplies.visible(replies, evidence, policy).map { it.naturalText }
    }

    fun replyHintsForEvidence(evidence: List<RecognitionEvidence>): List<EvidenceAwareReplies.Hint> {
        if (!enabled) return emptyList()
        val turnId = context.latestHearingTurnId() ?: return emptyList()
        if (turnId != presentation.value.hearingTurnId) return emptyList()
        val replies = context.repliesForLatestHearingTurn()
        val policy = cachedPolicy ?: return replies.map { EvidenceAwareReplies.Hint(it.naturalText, false) }
        return EvidenceAwareReplies.hints(replies, evidence, policy)
    }

    fun signingStarted() {
        if (!enabled) return
        val next = presentation.value.signingStarted()
        // Hear closes the prediction window. A later signing response cannot reuse its hints.
        presentation.value = if (context.repliesForLatestHearingTurn().isEmpty()) {
            next.copy(possibleReplies = emptyList())
        } else next
    }
    fun clearDisplayedInterpretation() = signingStarted()
    fun clearPendingHearingReply() {
        if (!enabled) return
        context.finishReplyWindow()
        presentation.value = PhraseAssistUiState()
    }
    fun recognitionScreenStopped(openedTurnId: Long?) {
        if (!enabled) return
        val closesThisReply = openedTurnId != null && context.latestHearingTurnId() == openedTurnId
        if (closesThisReply) context.finishReplyWindow()
        presentation.value = if (closesThisReply || context.latestHearingTurnId() == null) {
            presentation.value.copy(possibleReplies = emptyList(), contextSupported = null)
        } else {
            // A new Hearing turn can arrive while the old Recognition screen is closing.
            presentation.value.signingStarted()
        }
    }
    fun appBackgrounded() {
        if (!enabled) return
        context.clearSession()
        history.clear()
        presentation.value = PhraseAssistUiState()
    }

    private fun provider(): ContextPredictionProvider = when (BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER) {
        "fake" -> FakeContextPredictionProvider()
        "remote" -> RemoteContextPredictionProvider(BuildConfig.CONTEXT_PHRASE_ASSIST_API_KEY)
        "gemini" -> GeminiContextPredictionProvider(BuildConfig.CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY)
        else -> ContextPredictionProvider { emptyList() }
    }

    private fun supportedGlosses(appContext: Context): Set<String> {
        val manifest = appContext.assets.open("phase4a_gate2_recognizer_parity/manifest.json")
            .bufferedReader().use { it.readText() }
        val labels = JSONObject(manifest).getJSONArray("class_index_to_gloss")
        return (0 until labels.length()).mapTo(LinkedHashSet()) { labels.getString(it) }
    }

    private fun loadPolicy(appContext: Context): PhraseMatchPolicy {
        val config = appContext.assets.open("context_phrase_assist_policy.json")
            .bufferedReader().use { it.readText() }.let(::JSONObject)
        return PhraseMatchPolicy(
            config.getInt("maximum_changed_events"),
            config.getDouble("maximum_contradicting_top1").toFloat(),
            config.getDouble("maximum_changed_score_gap").toFloat(),
            config.getDouble("minimum_changed_score_ratio").toFloat(),
            config.getDouble("minimum_winner_lead").toFloat(),
        )
    }
}
