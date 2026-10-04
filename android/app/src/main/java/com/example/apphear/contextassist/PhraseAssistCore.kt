package com.example.apphear.contextassist

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.withTimeoutOrNull

data class SignScore(val gloss: String, val score: Float)
data class RecognitionEvidence(val eventId: Int, val timestampMs: Long, val originalGloss: String,
                               val topK: List<SignScore>) {
    companion object {
        fun fromExistingTop5(eventId: Int, timestampMs: Long, top5: IntArray,
                             scores: FloatArray, glosses: List<String>): RecognitionEvidence {
            require(top5.isNotEmpty())
            val candidates = top5.map { index -> SignScore(glosses[index], scores[index]) }
            return RecognitionEvidence(eventId, timestampMs, candidates.first().gloss, candidates)
        }
    }
}

enum class ConversationSpeaker { HEARING, DEAF }
enum class ConversationSource { SPEECH, TYPED_TEXT, SIGN_TO_TEXT }
data class ConversationTurn(val id: Long, val speaker: ConversationSpeaker, val source: ConversationSource,
                            val text: String, val timestampMs: Long)
/** Natural reply hypothesis plus expected observable anchors; neither proves what was signed. */
data class ReplyCandidate(val naturalText: String, val concepts: List<String>)
data class PredictionRequest(val hearingTurnId: Long, val recentTurns: List<ConversationTurn>,
                             val allowedGlosses: Set<String>)
fun interface ContextPredictionProvider {
    suspend fun predict(request: PredictionRequest): List<ReplyCandidate>
}

/** Process-local bounded text context shared by both conversation directions. */
class ConversationContext(private val maximumTurns: Int = 6) {
    init { require(maximumTurns > 0) }
    private val turns = ArrayDeque<ConversationTurn>()
    private var nextId = 1L
    private var currentHearingId: Long? = null
    private var replies: List<ReplyCandidate> = emptyList()

    @Synchronized fun add(speaker: ConversationSpeaker, source: ConversationSource, text: String,
                          timestampMs: Long): ConversationTurn {
        val turn = ConversationTurn(nextId++, speaker, source, text.trim(), timestampMs)
        require(turn.text.isNotBlank())
        turns.addLast(turn)
        while (turns.size > maximumTurns) turns.removeFirst()
        if (speaker == ConversationSpeaker.HEARING) { currentHearingId = turn.id; replies = emptyList() }
        return turn
    }

    @Synchronized fun snapshot(): List<ConversationTurn> = turns.toList()
    @Synchronized fun setReplies(hearingTurnId: Long, candidates: List<ReplyCandidate>): Boolean {
        if (currentHearingId != hearingTurnId) return false
        replies = candidates.toList()
        return true
    }
    @Synchronized fun repliesForLatestHearingTurn(): List<ReplyCandidate> = replies.toList()
    @Synchronized fun latestHearingTurnId(): Long? = currentHearingId
    @Synchronized fun finishReplyWindow(): List<ReplyCandidate> {
        val finished = replies.toList()
        replies = emptyList()
        currentHearingId = null
        return finished
    }
}

/** Rejects unsupported or malformed provider concepts before matching. */
object ReplyCandidateValidator {
    fun validate(candidates: List<ReplyCandidate>, allowed: Set<String>): List<ReplyCandidate> {
        val seen = HashSet<List<String>>()
        return candidates.take(5).mapNotNull { candidate ->
            val text = candidate.naturalText.trim()
            val concepts = candidate.concepts.map { it.trim() }
            if (text.isBlank() || text.length > 140 || concepts.isEmpty() || concepts.size > 8 ||
                concepts.any { it !in allowed } || !seen.add(concepts)) null
            else ReplyCandidate(text, concepts)
        }
    }
}

/** Network failures and slow providers yield no predictions; parent cancellation remains cancellation. */
suspend fun predictValidated(provider: ContextPredictionProvider, request: PredictionRequest,
                             timeoutMs: Long): List<ReplyCandidate> {
    return try {
        val output = withTimeoutOrNull(timeoutMs) { provider.predict(request) } ?: return emptyList()
        ReplyCandidateValidator.validate(output, request.allowedGlosses)
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (_: Exception) {
        emptyList()
    }
}

data class PhraseMatchPolicy(val maximumChangedEvents: Int, val maximumContradictingTop1: Float,
                             val maximumChangedScoreGap: Float, val minimumChangedScoreRatio: Float,
                             val minimumWinnerLead: Float)
data class AssistedInterpretation(val rawGlosses: List<String>, val assistedGlosses: List<String>,
                                  val naturalText: String, val eventIds: List<Int>, val matched: Boolean,
                                  val evidence: List<RecognitionEvidence> = emptyList())

enum class ShadowReason {
    DISABLED, MATCH, NO_EVIDENCE, INCOMPLETE_EVIDENCE, NO_PREDICTIONS,
    NO_MATCH_OR_AMBIGUOUS, MATCHER_UNAVAILABLE,
}

/** Evaluation-only record. No member is a product sentence or speech command. */
data class ShadowEvaluation(
    val rawSentence: String,
    val evidence: List<RecognitionEvidence>,
    val predictions: List<ReplyCandidate>,
    val assistedCandidate: AssistedInterpretation?,
    val wouldChangeRaw: Boolean,
    val reason: ShadowReason,
) {
    val rawEventGlosses: List<String> get() = evidence.map { it.originalGloss }
}

/** Presentation-only projection. It never supplies sentence text or speech commands. */
data class PhraseAssistUiState(
    val hearingTurnId: Long? = null,
    val hearingText: String = "",
    val possibleReplies: List<String> = emptyList(),
    val contextSupported: String? = null,
) {
    fun hearingTurn(turn: ConversationTurn) = PhraseAssistUiState(turn.id, turn.text)

    fun predictions(turnId: Long, candidates: List<ReplyCandidate>): PhraseAssistUiState =
        if (hearingTurnId == turnId) copy(possibleReplies = candidates.map { it.naturalText }) else this

    fun signingStarted(): PhraseAssistUiState = copy(contextSupported = null)

    fun evaluated(turnId: Long?, evaluation: ShadowEvaluation): PhraseAssistUiState {
        if (turnId == null || turnId != hearingTurnId || evaluation.reason != ShadowReason.MATCH) return this
        val match = evaluation.assistedCandidate?.takeIf { it.matched } ?: return this
        val verified = evaluation.predictions.any {
            it.naturalText == match.naturalText && it.concepts == match.assistedGlosses
        }
        return if (verified) copy(contextSupported = match.naturalText) else this
    }
}

/** Conservative one-to-one comparison: every concept needs an actual signed event. */
class PhraseMatcher(private val policy: PhraseMatchPolicy) {
    fun interpret(evidence: List<RecognitionEvidence>, replies: List<ReplyCandidate>): AssistedInterpretation {
        val raw = evidence.map { it.originalGloss }
        val fallback = AssistedInterpretation(raw, raw, raw.joinToString(" "),
            evidence.map { it.eventId }, false, evidence.toList())
        if (evidence.isEmpty()) return fallback
        val scored = replies.mapNotNull { candidate ->
            if (candidate.concepts.size != evidence.size) return@mapNotNull null
            var changes = 0
            var score = 0f
            for (index in evidence.indices) {
                val event = evidence[index]
                val top1 = event.topK.firstOrNull() ?: return@mapNotNull null
                val visual = event.topK.firstOrNull { it.gloss == candidate.concepts[index] }
                    ?: return@mapNotNull null
                if (candidate.concepts[index] != event.originalGloss) {
                    changes++
                    if (changes > policy.maximumChangedEvents ||
                        top1.score > policy.maximumContradictingTop1 ||
                        top1.score - visual.score > policy.maximumChangedScoreGap ||
                        (top1.score > 0f && visual.score / top1.score < policy.minimumChangedScoreRatio))
                        return@mapNotNull null
                }
                score += visual.score
            }
            candidate to score / evidence.size
        }.sortedByDescending { it.second }
        val winner = scored.firstOrNull() ?: return fallback
        if (scored.size > 1 && winner.second - scored[1].second < policy.minimumWinnerLead) return fallback
        return AssistedInterpretation(raw, winner.first.concepts, winner.first.naturalText,
            evidence.map { it.eventId }, true, evidence.toList())
    }
}

/** Separate from S8, which collapses repeated glosses and does not track event IDs. */
class SigningTurnBuffer(private val maximumEvents: Int = 8) {
    init { require(maximumEvents > 0) }
    private val events = ArrayDeque<RecognitionEvidence>()
    private var lastEventId = 0
    var overflowed: Boolean = false
        private set
    fun add(evidence: RecognitionEvidence): Boolean {
        if (evidence.eventId <= lastEventId) return false
        lastEventId = evidence.eventId
        events.addLast(evidence)
        while (events.size > maximumEvents) { events.removeFirst(); overflowed = true }
        return true
    }
    fun snapshot(): List<RecognitionEvidence> = events.toList()
    fun clear() { events.clear(); lastEventId = 0; overflowed = false }
}

/** Deterministic offline provider for the complete product path. */
class FakeContextPredictionProvider : ContextPredictionProvider {
    override suspend fun predict(request: PredictionRequest): List<ReplyCandidate> {
        val latest = request.recentTurns.lastOrNull { it.speaker == ConversationSpeaker.HEARING }
            ?.text?.lowercase().orEmpty()
        return when {
            "where" in latest && "go" in latest -> listOf(
                ReplyCandidate("I'm going home.", listOf("GO", "HOME")),
                ReplyCandidate("I'm going to school.", listOf("GO", "SCHOOL")),
                ReplyCandidate("I'm going to work.", listOf("GO", "WORK")))
            "how are you" in latest -> listOf(
                ReplyCandidate("I'm good.", listOf("GOOD")),
                ReplyCandidate("I'm tired.", listOf("TIRED")),
                ReplyCandidate("I'm sick.", listOf("SICK")))
            else -> emptyList()
        }
    }
}
