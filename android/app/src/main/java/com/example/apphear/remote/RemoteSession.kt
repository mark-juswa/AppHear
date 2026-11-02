package com.example.apphear.remote

import android.content.Context
import android.util.Log
import com.example.apphear.BuildConfig
import com.example.apphear.domain.profile.AccountException
import com.example.apphear.domain.profile.AccountSession
import com.example.apphear.data.profile.EncryptedAccountSessionStore
import com.example.apphear.ui.settings.AppConfiguration
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.util.UUID

/**
 * One phone's side of a remote conversation. Owns the guest sign-in, the server calls, the live
 * channel, reconnecting with catch-up, and the outgoing queue (each message keeps its id, so a retry
 * after a lost reply is never a duplicate). Lives for the process, not for a screen: screens attach
 * while visible and detach when hidden. Main-thread API.
 */
class RemoteSession internal constructor(context: Context, role: RemoteRole) {
    private val app = context.applicationContext
    private val backend = RemoteBackend(AppConfiguration.supabaseUrl, AppConfiguration.supabaseAnonKey)
    private val authStore = EncryptedAccountSessionStore(app, AppConfiguration.supabaseUrl.trimEnd('/'),
        AUTH_PREFERENCES, "apphear_remote_session_v1")
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val authLock = Mutex()
    private val mutable = MutableStateFlow(RemoteState(role))
    val state: StateFlow<RemoteState> = mutable.asStateFlow()

    private var auth: AccountSession? = null
    private var channel: RemoteRealtime? = null
    private var attached = false
    private var reconnectDelayMs = FIRST_RETRY_MS
    private var reconnectJob: Job? = null
    private var keepAliveJob: Job? = null
    private var flushing = false

    /** Viewer: the newest message already signed on this phone (survives the screen being recreated). */
    var playedSeq: Long = 0L

    private val active: Boolean
        get() = state.value.conversationId != null &&
            state.value.phase.let { it is RemotePhase.Inviting || it is RemotePhase.Connected }

    // ---- starting ----

    fun host(hostName: String) {
        mutable.update { it.copy(phase = RemotePhase.Working) }
        scope.launch {
            try {
                val invite = call { backend.createConversation(it, hostName) }
                mutable.update { it.copy(conversationId = invite.conversationId,
                    phase = RemotePhase.Inviting(invite.code, invite.secret, invite.expiresAtMs)) }
                remember()
                connect()
            } catch (error: RemoteException) {
                fail(error.issue)
            }
        }
    }

    fun renewInvite() {
        val id = state.value.conversationId ?: return
        scope.launch {
            try {
                val invite = call { backend.renewInvite(it, id) }
                mutable.update { it.copy(phase = RemotePhase.Inviting(invite.code, invite.secret, invite.expiresAtMs)) }
            } catch (error: RemoteException) {
                // The viewer may have joined in the meantime; the conversation row decides.
                if (!refreshConversation()) fail(error.issue)
            }
        }
    }

    fun join(code: String, secret: String?) {
        mutable.update { it.copy(phase = RemotePhase.Working) }
        scope.launch {
            try {
                val joined = call { backend.join(it, code, secret) }
                mutable.update { it.copy(conversationId = joined.conversationId, peerName = joined.hostName,
                    phase = RemotePhase.Connected) }
                remember()
                connect()
            } catch (error: RemoteException) {
                fail(error.issue)
            }
        }
    }

    /** Continues a conversation saved before the app was closed. */
    internal fun restore(conversationId: String, peerName: String) {
        mutable.update { it.copy(conversationId = conversationId, peerName = peerName, phase = RemotePhase.Working) }
        scope.launch {
            try {
                val row = call { backend.conversation(it, conversationId) }
                when {
                    row == null || row.ended -> finish(RemoteEndReason.TIMED_OUT, notifyServer = false)
                    state.value.role == RemoteRole.HOST && row.viewerId == null -> {
                        // The invite secret is not stored, so the QR is made again.
                        val invite = call { backend.renewInvite(it, conversationId) }
                        mutable.update { it.copy(phase = RemotePhase.Inviting(invite.code, invite.secret, invite.expiresAtMs)) }
                        connect()
                    }
                    else -> {
                        // Messages the viewer already saw are not signed again.
                        if (state.value.role == RemoteRole.VIEWER) playedSeq = row.viewerSeenSeq
                        mutable.update { it.copy(phase = RemotePhase.Connected) }
                        connect()
                    }
                }
            } catch (error: RemoteException) {
                // Offline at start-up: show it as connected-but-reconnecting and keep trying.
                if (error.issue == RemoteIssue.OFFLINE) {
                    mutable.update { it.copy(phase = RemotePhase.Connected) }
                    scheduleReconnect()
                } else fail(error.issue)
            }
        }
    }

    // ---- screen lifecycle ----

    fun attach() {
        attached = true
        connect()
    }

    fun detach() {
        attached = false
        reconnectJob?.cancel()
        keepAliveJob?.cancel()
        dropChannel()
    }

    // ---- conversation ----

    /** Host only: sends typed or spoken text to the viewer. Ignored unless connected. */
    fun send(text: String) {
        val body = text.trim().take(MAX_MESSAGE_CHARS)
        if (body.isEmpty() || state.value.role != RemoteRole.HOST || state.value.phase != RemotePhase.Connected) return
        mutable.update { it.withOutgoing(UUID.randomUUID().toString(), body) }
        flush()
    }

    /** Viewer only: everything up to [seq] has been shown. */
    fun markSeen(seq: Long) {
        val id = state.value.conversationId ?: return
        if (state.value.role != RemoteRole.VIEWER) return
        scope.launch { try { call { backend.markSeen(it, id, seq) } } catch (_: RemoteException) { /* best effort */ } }
    }

    fun end() {
        if (state.value.phase is RemotePhase.Ended) return
        finish(RemoteEndReason.YOU_ENDED, notifyServer = true)
    }

    internal fun close() {
        detach()
        scope.cancel()
    }

    // ---- internals ----

    private fun connect() {
        if (!attached || channel != null || !active) return
        reconnectJob?.cancel()
        val id = state.value.conversationId ?: return
        scope.launch {
            val session = try { withContext(Dispatchers.IO) { token() } } catch (_: RemoteException) {
                scheduleReconnect(); return@launch
            }
            if (!attached || channel != null || !active) return@launch
            channel = RemoteRealtime(backend.realtimeUrl, id, session.profile.id, state.value.role, realtimeListener).also {
                it.connect(session.accessToken)
            }
        }
        keepAlive()
    }

    private val realtimeListener = object : RemoteRealtime.Listener {
        override fun onJoined() {
            reconnectDelayMs = FIRST_RETRY_MS
            mutable.update { it.copy(linkUp = true) }
            scope.launch { catchUp() }
        }

        override fun onClosed() {
            channel = null
            mutable.update { it.copy(linkUp = false, peerOnline = false) }
            scheduleReconnect()
        }

        override fun onMessage(row: RemoteBackend.MessageRow) = applyMessage(row)
        override fun onConversation(row: RemoteBackend.ConversationRow) = applyConversation(row)
        override fun onPeerPresence(online: Boolean) = mutable.update { it.copy(peerOnline = online) }
    }

    private fun scheduleReconnect() {
        if (!attached || !active) return
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(reconnectDelayMs)
            reconnectDelayMs = (reconnectDelayMs * 2).coerceAtMost(MAX_RETRY_MS)
            connect()
        }
    }

    private fun keepAlive() {
        if (keepAliveJob?.isActive == true) return
        keepAliveJob = scope.launch {
            while (isActive && attached && active) {
                val id = state.value.conversationId ?: break
                try {
                    if (call { backend.touch(it, id) }) refreshConversation()
                } catch (_: RemoteException) { /* offline: the channel retry covers it */ }
                delay(KEEP_ALIVE_MS)
            }
        }
    }

    /** Fetches what was missed while disconnected, then sends anything still queued. */
    private suspend fun catchUp() {
        val id = state.value.conversationId ?: return
        try {
            call { backend.messagesAfter(it, id, state.value.lastSeq) }.forEach(::applyMessage)
            refreshConversation()
        } catch (error: RemoteException) {
            Log.w(TAG, "[remote] catch-up failed: ${error.issue}")
        }
        flush()
    }

    /** True when the conversation row was read (and applied). */
    private suspend fun refreshConversation(): Boolean {
        val id = state.value.conversationId ?: return false
        val row = try { call { backend.conversation(it, id) } } catch (_: RemoteException) { return false }
        if (row == null) finish(RemoteEndReason.TIMED_OUT, notifyServer = false) else applyConversation(row)
        return true
    }

    private fun applyMessage(row: RemoteBackend.MessageRow) {
        if (row.conversationId != state.value.conversationId) return
        val mine = row.senderId == auth?.profile?.id
        mutable.update { it.withServerMessage(row.id, row.seq, row.body, mine) }
    }

    private fun applyConversation(row: RemoteBackend.ConversationRow) {
        if (row.id != state.value.conversationId) return
        if (row.ended) {
            val reason = when (row.endedBy) {
                null -> RemoteEndReason.TIMED_OUT
                auth?.profile?.id -> RemoteEndReason.YOU_ENDED
                else -> RemoteEndReason.OTHER_ENDED
            }
            finish(reason, notifyServer = false)
            return
        }
        mutable.update {
            var next = it.withSeenUpTo(row.viewerSeenSeq)
            if (it.role == RemoteRole.HOST && row.viewerId != null && it.phase is RemotePhase.Inviting) {
                next = next.copy(phase = RemotePhase.Connected)
            }
            if (it.role == RemoteRole.VIEWER && row.hostName.isNotBlank()) next = next.copy(peerName = row.hostName)
            next
        }
        if (state.value.role == RemoteRole.HOST) remember()
    }

    private fun flush() {
        if (flushing || state.value.phase != RemotePhase.Connected) return
        val id = state.value.conversationId ?: return
        flushing = true
        scope.launch {
            try {
                for (message in state.value.pendingOutgoing) {
                    try {
                        applyMessage(call { backend.send(it, message.id, id, message.text) })
                    } catch (error: RemoteException) {
                        if (error.issue == RemoteIssue.OFFLINE) {
                            scheduleRetry()
                            break
                        }
                        mutable.update { it.withSendFailed(message.id) }
                    }
                }
            } finally {
                flushing = false
            }
        }
    }

    private fun scheduleRetry() {
        scope.launch {
            delay(SEND_RETRY_MS)
            if (attached) flush()
        }
    }

    private fun finish(reason: RemoteEndReason, notifyServer: Boolean) {
        val id = state.value.conversationId
        mutable.update { it.copy(phase = RemotePhase.Ended(reason), linkUp = false, peerOnline = false) }
        forget()
        reconnectJob?.cancel()
        keepAliveJob?.cancel()
        dropChannel()
        if (notifyServer && id != null) {
            // Not tied to this session's scope: a closed session must still tell the server.
            serverCalls.launch { try { call { backend.end(it, id) } } catch (_: RemoteException) { /* the server times it out */ } }
        }
    }

    private fun fail(issue: RemoteIssue) {
        Log.w(TAG, "[remote] failed: $issue")
        mutable.update { it.copy(phase = RemotePhase.Failed(issue)) }
        if (state.value.conversationId == null) forget()
    }

    private fun dropChannel() {
        channel?.close()
        channel = null
        mutable.update { it.copy(linkUp = false, peerOnline = false) }
    }

    // ---- auth ----

    /** Runs [block] off the main thread with a fresh access token, refreshing once if it is refused. */
    private suspend fun <T> call(block: (String) -> T): T = withContext(Dispatchers.IO) {
        try {
            block(token().accessToken)
        } catch (_: RemoteBackend.SessionExpired) {
            try { block(token(forceRefresh = true).accessToken) }
            catch (_: RemoteBackend.SessionExpired) { throw RemoteException(RemoteIssue.SERVER) }
        }
    }

    private suspend fun token(forceRefresh: Boolean = false): AccountSession = authLock.withLock {
        val current = auth ?: try { authStore.load() } catch (_: AccountException) { null }
        val now = System.currentTimeMillis() / 1000
        val fresh = when {
            current == null -> backend.signInAnonymously()
            forceRefresh || current.expiresAt <= now + REFRESH_MARGIN_S -> try {
                backend.refresh(current.refreshToken)
            } catch (error: RemoteException) {
                // A new guest identity cannot rejoin this conversation, so only start over when idle.
                if (error.issue == RemoteIssue.OFFLINE || active) throw error
                backend.signInAnonymously()
            } catch (_: RemoteBackend.SessionExpired) {
                if (active) throw RemoteException(RemoteIssue.SERVER)
                backend.signInAnonymously()
            }
            else -> current
        }
        if (fresh !== current) {
            try { authStore.save(fresh) } catch (_: AccountException) { /* kept in memory for this run */ }
            channel?.updateToken(fresh.accessToken)
        }
        auth = fresh
        fresh
    }

    // ---- saved conversation (survives the app being closed) ----

    private fun remember() {
        val s = state.value
        app.getSharedPreferences(CONVERSATION_PREFERENCES, Context.MODE_PRIVATE).edit()
            .putString(KEY_ID, s.conversationId).putString(KEY_ROLE, s.role.name).putString(KEY_PEER, s.peerName).apply()
    }

    private fun forget() {
        app.getSharedPreferences(CONVERSATION_PREFERENCES, Context.MODE_PRIVATE).edit().clear().apply()
    }

    companion object {
        private const val TAG = "AppHearRemote"
        const val MAX_MESSAGE_CHARS = 500
        private const val FIRST_RETRY_MS = 1_000L
        private const val MAX_RETRY_MS = 15_000L
        private const val SEND_RETRY_MS = 3_000L
        private const val KEEP_ALIVE_MS = 4 * 60_000L
        private const val REFRESH_MARGIN_S = 60L
        private const val AUTH_PREFERENCES = "apphear_remote_session"
        internal const val CONVERSATION_PREFERENCES = "apphear_remote_conversation"
        internal const val KEY_ID = "id"
        internal const val KEY_ROLE = "role"
        internal const val KEY_PEER = "peer"

        val enabled: Boolean get() = BuildConfig.REMOTE_CONVERSATION_ENABLED
        private val serverCalls = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    }
}

/** The process's one remote conversation, plus an invite link waiting for the Text-to-ASL screen. */
object RemoteConversations {
    private var session: RemoteSession? = null

    /** Set when an invite link or QR opened the app; the Text-to-ASL screen asks to join. */
    var pendingLink: RemoteInvite.Link? = null

    fun current(context: Context): RemoteSession? {
        session?.let { return it }
        val saved = context.applicationContext.getSharedPreferences(RemoteSession.CONVERSATION_PREFERENCES, Context.MODE_PRIVATE)
        val id = saved.getString(RemoteSession.KEY_ID, null) ?: return null
        val role = saved.getString(RemoteSession.KEY_ROLE, null)?.let { runCatching { RemoteRole.valueOf(it) }.getOrNull() } ?: return null
        return RemoteSession(context, role).also {
            session = it
            it.restore(id, saved.getString(RemoteSession.KEY_PEER, "").orEmpty())
        }
    }

    fun start(context: Context, role: RemoteRole): RemoteSession {
        session?.let { if (it.state.value.phase.let { p -> p is RemotePhase.Inviting || p is RemotePhase.Connected }) it.end() }
        session?.close()
        return RemoteSession(context, role).also { session = it }
    }

    /** Forgets a finished or failed session once its result has been shown. */
    fun clear() {
        session?.close()
        session = null
    }
}
