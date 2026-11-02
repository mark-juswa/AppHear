package com.example.apphear.remote

import android.Manifest
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * The process's one remote conversation, shared by every screen (Text-to-ASL, Recognition).
 * Chooses how it travels: through the AppHear server when there is internet, otherwise directly
 * phone to phone (Nearby). "Offline only" in Settings always uses phone to phone. A server attempt
 * that finds no internet falls back to phone to phone by itself.
 */
object RemoteConversations {
    private val scope = MainScope()
    private val mutable = MutableStateFlow<RemoteLink?>(null)
    val active: StateFlow<RemoteLink?> = mutable.asStateFlow()

    /** Set when an invite link or QR opened the app; the Text-to-ASL screen asks to join. */
    var pendingLink: RemoteInvite.Link? = null

    /** Picks up a server conversation saved before the app was closed (phone-to-phone ones end with the app). */
    fun restore(context: Context) {
        if (mutable.value != null) return
        val saved = context.applicationContext.getSharedPreferences(RemoteSession.CONVERSATION_PREFERENCES, Context.MODE_PRIVATE)
        val id = saved.getString(RemoteSession.KEY_ID, null) ?: return
        val role = saved.getString(RemoteSession.KEY_ROLE, null)?.let { runCatching { RemoteRole.valueOf(it) }.getOrNull() } ?: return
        mutable.value = RemoteSession(context, role, RemotePreferences(context).displayName).also {
            it.restore(id, saved.getString(RemoteSession.KEY_PEER, "").orEmpty())
        }
    }

    fun host(context: Context) {
        val preferences = RemotePreferences(context)
        if (preferences.offlineOnly || !online(context)) return nearbyHost(context)
        val session = RemoteSession(context, RemoteRole.HOST, preferences.displayName)
        replace(session)
        session.host()
        fallBackOn(session, setOf(RemoteIssue.OFFLINE)) { nearbyHost(context) }
    }

    /** From a scanned QR or an opened link. */
    fun join(context: Context, link: RemoteInvite.Link) {
        if (link.nearby) return nearbyJoin(context, link.code, link.secret)
        if (!online(context)) {
            replace(null)
            mutable.value = failed(RemoteIssue.OFFLINE)
            return
        }
        val session = RemoteSession(context, RemoteRole.VIEWER, RemotePreferences(context).displayName)
        replace(session)
        session.join(link.code, link.secret)
    }

    /** From a typed code: the server first (when allowed and online), then phone to phone. */
    fun join(context: Context, code: String) {
        val preferences = RemotePreferences(context)
        if (preferences.offlineOnly || !online(context)) return nearbyJoin(context, code, null)
        val session = RemoteSession(context, RemoteRole.VIEWER, preferences.displayName)
        replace(session)
        session.join(code, null)
        // The code may belong to a phone-to-phone invite that the server has never seen.
        fallBackOn(session, setOf(RemoteIssue.OFFLINE, RemoteIssue.INVITE_INVALID)) { nearbyJoin(context, code, null) }
    }

    /** Recognition / Text-to-ASL host: a reply typed or said by the host also goes to the other phone. */
    fun sendFromHost(text: String) {
        val link = mutable.value ?: return
        if (link.state.value.role == RemoteRole.HOST) link.send(text)
    }

    /** Forgets a finished or failed conversation once its result has been shown. */
    fun clear() = replace(null)

    /** Runtime permissions phone-to-phone needs on this Android version. */
    fun nearbyPermissions(): Array<String> = when {
        Build.VERSION.SDK_INT >= 33 -> arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_ADVERTISE,
            Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.NEARBY_WIFI_DEVICES)
        Build.VERSION.SDK_INT >= 31 -> arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_ADVERTISE,
            Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.ACCESS_FINE_LOCATION)
        else -> arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
    }

    private fun nearbyHost(context: Context) {
        val session = NearbySession(context, RemoteRole.HOST, RemotePreferences(context).displayName)
        replace(session)
        session.host()
    }

    private fun nearbyJoin(context: Context, code: String, secret: String?) {
        val session = NearbySession(context, RemoteRole.VIEWER, RemotePreferences(context).displayName)
        replace(session)
        session.join(code, secret)
    }

    private fun fallBackOn(session: RemoteSession, issues: Set<RemoteIssue>, fallback: () -> Unit) {
        scope.launch {
            val settled = session.state.first { it.phase != RemotePhase.Working && it.phase != RemotePhase.Idle }
            val issue = (settled.phase as? RemotePhase.Failed)?.issue
            if (issue in issues && settled.conversationId == null && mutable.value === session) fallback()
        }
    }

    private fun replace(next: RemoteLink?) {
        val previous = mutable.value
        if (previous != null && previous !== next) {
            if (previous.state.value.phase.let { it is RemotePhase.Inviting || it is RemotePhase.Connected }) previous.end()
            previous.close()
        }
        mutable.value = next
    }

    /** A link that only reports [issue] (nothing was started). */
    private fun failed(issue: RemoteIssue): RemoteLink = object : RemoteLink {
        override val state: StateFlow<RemoteState> =
            MutableStateFlow(RemoteState(RemoteRole.VIEWER, RemotePhase.Failed(issue)))
        override var playedSeq = 0L
        override fun attach() = Unit
        override fun detach() = Unit
        override fun send(text: String) = Unit
        override fun markSeen(seq: Long) = Unit
        override fun renewInvite() = Unit
        override fun end() = Unit
        override fun close() = Unit
    }

    private fun online(context: Context): Boolean {
        val connectivity = context.getSystemService(ConnectivityManager::class.java) ?: return false
        val capabilities = connectivity.getNetworkCapabilities(connectivity.activeNetwork) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }
}
