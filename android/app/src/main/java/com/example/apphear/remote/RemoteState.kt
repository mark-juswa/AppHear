package com.example.apphear.remote

enum class RemoteRole { HOST, VIEWER }

/** Why something failed, in words the screen can explain. */
enum class RemoteIssue { NOT_CONFIGURED, OFFLINE, GUEST_SIGN_IN_OFF, SERVER_NOT_READY, INVITE_INVALID, RATE_LIMITED, OWN_INVITE, SERVER }

enum class RemoteEndReason { YOU_ENDED, OTHER_ENDED, TIMED_OUT }

sealed interface RemotePhase {
    object Idle : RemotePhase
    object Working : RemotePhase
    data class Inviting(val code: String, val secret: String, val expiresAtMs: Long) : RemotePhase
    object Connected : RemotePhase
    data class Ended(val reason: RemoteEndReason) : RemotePhase
    data class Failed(val issue: RemoteIssue) : RemotePhase
}

data class RemoteMessage(
    val id: String,
    val text: String,
    val seq: Long?,
    val fromMe: Boolean,
    val status: Status,
) {
    enum class Status { SENDING, SENT, SEEN, FAILED }
}

/**
 * Everything one phone knows about its remote conversation. Pure data plus pure transitions so the
 * ordering, de-duplication and delivery rules are unit-tested without a network.
 */
data class RemoteState(
    val role: RemoteRole,
    val phase: RemotePhase = RemotePhase.Idle,
    val conversationId: String? = null,
    val peerName: String = "",
    /** True while this phone's live connection is up. */
    val linkUp: Boolean = false,
    /** True while the other phone has AppHear open on this conversation. */
    val peerOnline: Boolean = false,
    val messages: List<RemoteMessage> = emptyList(),
) {
    val lastSeq: Long get() = messages.maxOfOrNull { it.seq ?: 0L } ?: 0L
    val pendingOutgoing: List<RemoteMessage>
        get() = messages.filter { it.fromMe && (it.status == RemoteMessage.Status.SENDING || it.status == RemoteMessage.Status.FAILED) }

    /** Adds a message being sent from this phone. */
    fun withOutgoing(id: String, text: String): RemoteState =
        copy(messages = trim(messages + RemoteMessage(id, text, null, fromMe = true, RemoteMessage.Status.SENDING)))

    /**
     * Applies a message the server confirmed (a send result, a live event or a catch-up fetch).
     * The same id twice is one message; order follows the server sequence.
     */
    fun withServerMessage(id: String, seq: Long, text: String, fromMe: Boolean): RemoteState {
        val existing = messages.firstOrNull { it.id == id }
        val updated = if (existing != null) {
            messages.map {
                if (it.id != id) it else it.copy(seq = seq, status = if (it.status == RemoteMessage.Status.SEEN)
                    it.status else RemoteMessage.Status.SENT)
            }
        } else {
            messages + RemoteMessage(id, text, seq, fromMe, RemoteMessage.Status.SENT)
        }
        return copy(messages = trim(ordered(updated)))
    }

    fun withSendFailed(id: String): RemoteState =
        copy(messages = messages.map { if (it.id == id && it.seq == null) it.copy(status = RemoteMessage.Status.FAILED) else it })

    /** The viewer has seen everything up to [seq]. */
    fun withSeenUpTo(seq: Long): RemoteState = copy(messages = messages.map {
        if (it.fromMe && it.seq != null && it.seq <= seq) it.copy(status = RemoteMessage.Status.SEEN) else it
    })

    private fun ordered(list: List<RemoteMessage>): List<RemoteMessage> {
        // Confirmed messages by server order; unconfirmed ones stay after them in send order.
        val (confirmed, waiting) = list.partition { it.seq != null }
        return confirmed.sortedBy { it.seq } + waiting
    }

    private fun trim(list: List<RemoteMessage>): List<RemoteMessage> =
        if (list.size <= MAX_MESSAGES) list else {
            // Never drop a message that still has to be sent.
            val keep = list.filter { it.seq == null }.toSet()
            val droppable = list.filter { it !in keep }.drop(list.size - MAX_MESSAGES)
            list.filter { it in keep || it in droppable }
        }

    companion object {
        const val MAX_MESSAGES = 60
    }
}
