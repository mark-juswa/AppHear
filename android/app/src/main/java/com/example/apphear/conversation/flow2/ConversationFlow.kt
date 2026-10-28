package com.example.apphear.conversation.flow2

/**
 * One-screen conversation (conversationFlowV2) turn logic. Pure Kotlin, no Android types: the
 * recognition screen feeds it events and carries out the [FlowEffect]s it returns.
 *
 * Every asynchronous step (speaking, listening, avatar playback) gets a fresh ticket; callbacks
 * carrying an older ticket are ignored, so a late TTS, speech or avatar callback can never move
 * the conversation after the user stopped or restarted that step.
 */
enum class FlowPhase { READY, SAYING, LISTENING, NOT_HEARD, REPLY, AVATAR }

enum class ReplySource { SPEECH, TYPED }

enum class ListenFailure {
    /** Nothing usable was said before the recognizer gave up. */
    NOT_HEARD,
    /** The microphone permission is missing or was denied. */
    NO_PERMISSION,
    /** In-app recognition is not available on this phone or for this language. */
    UNAVAILABLE,
    /** Network, audio or recognizer error. */
    ERROR,
}

enum class PrimaryAction { LISTEN, SAY_IT, STOP, SIGN_IT, REPLAY }

/** What the signer is about to say: the exact signed words plus an optional suggested sentence. */
data class SignedMessage(
    val signedWords: String,
    val suggestion: String? = null,
    val useSuggestion: Boolean = false,
) {
    val chosen: String get() = if (useSuggestion && suggestion != null) suggestion else signedWords
}

/** One row of history: what the signer said and/or what the hearing person replied. */
data class Exchange(val signed: String?, val reply: String?)

sealed interface FlowEffect {
    data class Speak(val text: String, val ticket: Long) : FlowEffect
    data object StopSpeaking : FlowEffect
    data class StartListening(val ticket: Long) : FlowEffect
    data object StopListening : FlowEffect
    /** In-app listening is unavailable: use the existing system speech dialog for this ticket. */
    data class OpenSystemListening(val ticket: Long) : FlowEffect
    /** Hand the reply to Context Assist exactly as the Text-to-ASL screen does today. */
    data class RecordHearing(val text: String, val source: ReplySource) : FlowEffect
    /** The said message got its reply: clear the S8 sentence so the next turn starts fresh. */
    data object ClearSignedWords : FlowEffect
    data class PlayAvatar(val text: String, val ticket: Long) : FlowEffect
    data object StopAvatar : FlowEffect
}

data class FlowState(
    val phase: FlowPhase = FlowPhase.READY,
    val message: SignedMessage? = null,
    /** The text being read aloud while [FlowPhase.SAYING], and the signed words it came from. */
    val speaking: String? = null,
    val speakingSignedWords: String? = null,
    val partialReply: String = "",
    val reply: String? = null,
    val avatarText: String? = null,
    val history: List<Exchange> = emptyList(),
    /** A message was said and its reply has not arrived yet. */
    val awaitingReply: Boolean = false,
    /** The signed words behind the last said message; only those are cleared when the reply comes. */
    val saidSignedWords: String? = null,
    /** The current listening ticket already fell back to the system dialog. */
    val systemListening: Boolean = false,
    val failure: ListenFailure? = null,
    val ticket: Long = 0,
)

data class Transition(val state: FlowState, val effects: List<FlowEffect> = emptyList())

object ConversationFlow {
    const val MAX_EXCHANGES = 6

    fun primaryAction(s: FlowState): PrimaryAction = when (s.phase) {
        FlowPhase.READY -> if (s.message != null) PrimaryAction.SAY_IT else PrimaryAction.LISTEN
        FlowPhase.SAYING, FlowPhase.LISTENING -> PrimaryAction.STOP
        FlowPhase.NOT_HEARD -> PrimaryAction.LISTEN
        FlowPhase.REPLY -> PrimaryAction.SIGN_IT
        FlowPhase.AVATAR -> PrimaryAction.REPLAY
    }

    /** The recognizer's displayed words changed (S8 sentence or confirmed spelling). */
    fun signedWordsChanged(s: FlowState, words: String): Transition {
        val text = words.trim()
        if (text.isEmpty()) return Transition(s.copy(message = null))
        val message = if (s.message?.signedWords == text) s.message else SignedMessage(text)
        // Signing again after a reply ends that reply's turn; it stays in history.
        val resumes = s.phase == FlowPhase.REPLY || s.phase == FlowPhase.NOT_HEARD
        return Transition(if (resumes) {
            s.copy(message = message, phase = FlowPhase.READY, reply = null, failure = null)
        } else s.copy(message = message))
    }

    /** A suggestion arrived for [forWords]; ignored if the signed words have moved on. */
    fun suggestionReady(s: FlowState, forWords: String, suggestion: String?): Transition {
        val message = s.message ?: return Transition(s)
        if (message.signedWords != forWords.trim()) return Transition(s)
        val clean = suggestion?.trim()?.takeIf { it.isNotEmpty() && it != message.signedWords }
        return Transition(s.copy(message = message.copy(suggestion = clean,
            useSuggestion = message.useSuggestion && clean != null)))
    }

    fun chooseSuggestion(s: FlowState, use: Boolean): Transition {
        val message = s.message ?: return Transition(s)
        if (use && message.suggestion == null) return Transition(s)
        return Transition(s.copy(message = message.copy(useSuggestion = use)))
    }

    fun sayIt(s: FlowState): Transition {
        val message = s.message ?: return Transition(s)
        if (s.phase !in setOf(FlowPhase.READY, FlowPhase.NOT_HEARD, FlowPhase.REPLY)) return Transition(s)
        val ticket = s.ticket + 1
        val text = message.chosen
        return Transition(s.copy(phase = FlowPhase.SAYING, speaking = text, speakingSignedWords = message.signedWords,
            failure = null, ticket = ticket), listOf(FlowEffect.Speak(text, ticket)))
    }

    /** Speech output finished: the message is in the conversation; listen for the reply. */
    fun sayingDone(s: FlowState, ticket: Long): Transition {
        if (ticket != s.ticket || s.phase != FlowPhase.SAYING) return Transition(s)
        val said = s.speaking ?: return Transition(s)
        val next = s.ticket + 1
        return Transition(s.copy(phase = FlowPhase.LISTENING, speaking = null, speakingSignedWords = null,
            partialReply = "", history = capped(s.history + Exchange(said, null)), awaitingReply = true,
            saidSignedWords = s.speakingSignedWords, systemListening = false, ticket = next),
            listOf(FlowEffect.StartListening(next)))
    }

    fun sayingFailed(s: FlowState, ticket: Long): Transition {
        if (ticket != s.ticket || s.phase != FlowPhase.SAYING) return Transition(s)
        return Transition(rest(s.copy(speaking = null, speakingSignedWords = null, ticket = s.ticket + 1)))
    }

    /** LISTEN: the hearing person speaks without a message being said first. */
    fun listen(s: FlowState): Transition {
        if (s.phase !in setOf(FlowPhase.READY, FlowPhase.NOT_HEARD, FlowPhase.REPLY)) return Transition(s)
        val ticket = s.ticket + 1
        return Transition(s.copy(phase = FlowPhase.LISTENING, partialReply = "", failure = null,
            systemListening = false, ticket = ticket), listOf(FlowEffect.StartListening(ticket)))
    }

    fun partialReply(s: FlowState, ticket: Long, text: String): Transition {
        if (ticket != s.ticket || s.phase != FlowPhase.LISTENING) return Transition(s)
        return Transition(s.copy(partialReply = text.trim()))
    }

    /** Final speech result, from in-app listening or the system dialog. */
    fun replyHeard(s: FlowState, ticket: Long, text: String): Transition {
        if (ticket != s.ticket || s.phase != FlowPhase.LISTENING) return Transition(s)
        if (text.isBlank()) return listenFailed(s, ticket, ListenFailure.NOT_HEARD)
        return deliver(s.copy(ticket = s.ticket + 1), text.trim(), ReplySource.SPEECH)
    }

    fun typedReply(s: FlowState, text: String): Transition {
        val clean = text.trim()
        if (clean.isEmpty() || s.phase == FlowPhase.AVATAR) return Transition(s)
        val stops = when (s.phase) {
            FlowPhase.SAYING -> listOf(FlowEffect.StopSpeaking)
            FlowPhase.LISTENING -> listOf(FlowEffect.StopListening)
            else -> emptyList()
        }
        val delivered = deliver(s.copy(speaking = null, speakingSignedWords = null, ticket = s.ticket + 1), clean, ReplySource.TYPED)
        return Transition(delivered.state, stops + delivered.effects)
    }

    fun listenFailed(s: FlowState, ticket: Long, failure: ListenFailure): Transition {
        if (ticket != s.ticket || s.phase != FlowPhase.LISTENING) return Transition(s)
        val canFallBack = failure == ListenFailure.UNAVAILABLE || failure == ListenFailure.NO_PERMISSION
        if (canFallBack && !s.systemListening) {
            return Transition(s.copy(systemListening = true, partialReply = ""),
                listOf(FlowEffect.OpenSystemListening(ticket)))
        }
        return Transition(s.copy(phase = FlowPhase.NOT_HEARD, partialReply = "", failure = failure,
            ticket = s.ticket + 1))
    }

    /** STOP / CLOSE: ends whatever is in progress and returns to the resting state. */
    fun stop(s: FlowState): Transition {
        val effect = when (s.phase) {
            FlowPhase.SAYING -> FlowEffect.StopSpeaking
            FlowPhase.LISTENING -> FlowEffect.StopListening
            FlowPhase.AVATAR -> FlowEffect.StopAvatar
            else -> return Transition(s)
        }
        return Transition(rest(s.copy(speaking = null, speakingSignedWords = null, partialReply = "", avatarText = null,
            ticket = s.ticket + 1)), listOf(effect))
    }

    /** SIGN IT: plays the latest reply, or [text] from a history bubble. */
    fun signIt(s: FlowState, text: String? = null): Transition {
        val target = (text ?: s.reply)?.trim()?.takeIf { it.isNotEmpty() } ?: return Transition(s)
        if (s.phase in setOf(FlowPhase.SAYING, FlowPhase.LISTENING)) return Transition(s)
        val ticket = s.ticket + 1
        return Transition(s.copy(phase = FlowPhase.AVATAR, avatarText = target, ticket = ticket),
            listOf(FlowEffect.PlayAvatar(target, ticket)))
    }

    fun replay(s: FlowState): Transition {
        val text = s.avatarText
        if (s.phase != FlowPhase.AVATAR || text == null) return Transition(s)
        val ticket = s.ticket + 1
        return Transition(s.copy(ticket = ticket), listOf(FlowEffect.PlayAvatar(text, ticket)))
    }

    /** Genuine playback completion only; never a timer. */
    fun avatarFinished(s: FlowState, ticket: Long): Transition {
        if (ticket != s.ticket || s.phase != FlowPhase.AVATAR) return Transition(s)
        return Transition(rest(s.copy(avatarText = null, ticket = s.ticket + 1)))
    }

    fun clear(s: FlowState): Transition =
        Transition(s.copy(message = null), listOf(FlowEffect.ClearSignedWords))

    /** Back press: closes the avatar or stops speaking/listening; otherwise not handled. */
    fun back(s: FlowState): Transition? =
        if (s.phase in setOf(FlowPhase.SAYING, FlowPhase.LISTENING, FlowPhase.AVATAR)) stop(s) else null

    /** After the screen is recreated nothing in flight is resumed: no speech, mic or avatar restarts. */
    fun restored(s: FlowState): FlowState =
        rest(s.copy(speaking = null, speakingSignedWords = null, partialReply = "", avatarText = null, systemListening = false,
            ticket = s.ticket + 1))

    private fun deliver(s: FlowState, text: String, source: ReplySource): Transition {
        val last = s.history.lastOrNull()
        val history = if (s.awaitingReply && last != null && last.reply == null) {
            s.history.dropLast(1) + last.copy(reply = text)
        } else s.history + Exchange(null, text)
        // Clear the signed words only while they are still exactly what was said; words signed
        // since then have not been said yet and must survive the reply.
        val clearSigned = s.saidSignedWords != null && s.message?.signedWords == s.saidSignedWords
        val effects = buildList {
            add(FlowEffect.RecordHearing(text, source))
            if (clearSigned) add(FlowEffect.ClearSignedWords)
        }
        return Transition(s.copy(phase = FlowPhase.REPLY, reply = text, partialReply = "",
            message = if (clearSigned) null else s.message, history = capped(history),
            awaitingReply = false, saidSignedWords = null, systemListening = false, failure = null), effects)
    }

    private fun rest(s: FlowState): FlowState = s.copy(phase = when {
        s.message != null -> FlowPhase.READY
        s.reply != null -> FlowPhase.REPLY
        else -> FlowPhase.READY
    }, failure = null)

    private fun capped(history: List<Exchange>) = history.takeLast(MAX_EXCHANGES)
}
