package com.example.apphear.sentenceassist

import kotlinx.coroutines.withTimeoutOrNull

enum class AiStatus { ACCEPTED, REJECTED, UNAVAILABLE, TIMEOUT }

/**
 * One shadow rendering. [aiSentence] is kept even when rejected so offline review can see what
 * the model tried; [chosenSentence] is what a visible build would offer (the AI sentence only
 * when grounded, else the plain fallback). Nothing here is shown or spoken in SHADOW mode.
 */
data class ShadowOutcome(
    val turn: SignedTurn,
    val aiStatus: AiStatus,
    val rejectReason: RejectReason?,
    val rejectDetail: String?,
    val aiSentence: String?,
    val aiSubstitutions: List<Substitution>,
    val acceptedWords: List<GroundedWord>,
    val fallbackSentence: String,
    val latencyMs: Long,
) {
    val chosenSentence: String get() = if (aiStatus == AiStatus.ACCEPTED) aiSentence.orEmpty() else fallbackSentence
}

/** Renders with a hard timeout, validates, and always produces the grounded plain fallback. */
class ShadowRenderPipeline(
    private val renderer: SentenceRenderer,
    private val fallback: PlainGlossRenderer,
    private val validator: GroundingValidator,
    private val timeoutMs: Long,
    private val clockMs: () -> Long,
) {
    suspend fun run(request: RenderRequest): ShadowOutcome {
        val started = clockMs()
        // The holder separates "timed out" (null) from "renderer had no answer" (holder of null).
        val completed = withTimeoutOrNull(timeoutMs) { Completed(renderer.render(request)) }
        val latency = clockMs() - started
        val fallbackSentence = fallback.plain(request.turn).sentence
        val rendering = completed?.rendering
        if (rendering == null) {
            return ShadowOutcome(request.turn, if (completed == null) AiStatus.TIMEOUT else AiStatus.UNAVAILABLE,
                null, null, null, emptyList(), emptyList(), fallbackSentence, latency)
        }
        return when (val result = validator.validate(request.turn, rendering)) {
            is GroundingResult.Accepted -> ShadowOutcome(request.turn, AiStatus.ACCEPTED, null, null,
                result.sentence, result.substitutions, result.words, fallbackSentence, latency)
            is GroundingResult.Rejected -> ShadowOutcome(request.turn, AiStatus.REJECTED, result.reason,
                result.detail, rendering.sentence, rendering.substitutions, emptyList(), fallbackSentence, latency)
        }
    }

    private class Completed(val rendering: Rendering?)
}
