package com.example.apphear.remote

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.nearby.Nearby
import com.google.android.gms.nearby.connection.AdvertisingOptions
import com.google.android.gms.nearby.connection.ConnectionInfo
import com.google.android.gms.nearby.connection.ConnectionLifecycleCallback
import com.google.android.gms.nearby.connection.ConnectionResolution
import com.google.android.gms.nearby.connection.ConnectionsStatusCodes
import com.google.android.gms.nearby.connection.DiscoveredEndpointInfo
import com.google.android.gms.nearby.connection.DiscoveryOptions
import com.google.android.gms.nearby.connection.EndpointDiscoveryCallback
import com.google.android.gms.nearby.connection.Payload
import com.google.android.gms.nearby.connection.PayloadCallback
import com.google.android.gms.nearby.connection.PayloadTransferUpdate
import com.google.android.gms.nearby.connection.Strategy
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import org.json.JSONObject
import java.util.UUID

/**
 * A remote conversation carried directly between two phones with Google Nearby Connections
 * (Bluetooth and Wi-Fi Direct; no internet or router). The host advertises its invite code; the
 * viewer finds that code, connects and proves the invite secret (a typed code alone is accepted for
 * the first join only). The host numbers the messages; after a dropped link the viewer reconnects
 * and the host re-sends what it missed. Ends when either phone ends it or the app process ends.
 */
class NearbySession(context: Context, role: RemoteRole, private val myName: String) : RemoteLink {
    private val client = Nearby.getConnectionsClient(context.applicationContext)
    private val main = Handler(Looper.getMainLooper())
    private val mutable = MutableStateFlow(RemoteState(role))
    override val state: StateFlow<RemoteState> = mutable.asStateFlow()
    override var playedSeq: Long = 0L

    private var code = ""
    private var secret: String? = null
    private var expiresAtMs = 0L
    private var peer: String? = null
    private var joinedOnce = false
    private var closed = false
    private var hostSeq = 0L
    private val assignedSeq = mutableMapOf<String, Long>()
    private val sentSeq = mutableSetOf<Long>()

    // ---- starting ----

    fun host() {
        code = RemoteInvite.randomCode()
        secret = RemoteInvite.randomSecret()
        expiresAtMs = System.currentTimeMillis() + INVITE_MS
        mutable.update { it.copy(conversationId = "nearby-$code", phase = invitePhase()) }
        advertise()
    }

    fun join(code: String, secret: String?) {
        this.code = code
        this.secret = secret
        mutable.update { it.copy(conversationId = "nearby-$code", phase = RemotePhase.Working) }
        discover()
        main.postDelayed({
            if (!closed && state.value.phase == RemotePhase.Working) {
                stopEverything()
                fail(RemoteIssue.NOT_FOUND_NEARBY)
            }
        }, FIND_TIMEOUT_MS)
    }

    override fun renewInvite() {
        if (state.value.role != RemoteRole.HOST || joinedOnce || closed) return
        client.stopAdvertising()
        host()
    }

    // ---- RemoteLink ----

    override fun attach() = Unit // the link lives with the process, not with a screen
    override fun detach() = Unit

    override fun send(text: String) {
        val body = text.trim().take(RemoteSession.MAX_MESSAGE_CHARS)
        if (body.isEmpty() || state.value.role != RemoteRole.HOST || state.value.phase != RemotePhase.Connected) return
        mutable.update { it.withOutgoing(UUID.randomUUID().toString(), body) }
        flush()
    }

    override fun markSeen(seq: Long) {
        if (state.value.role == RemoteRole.VIEWER) sendJson(JSONObject().put("t", "seen").put("seq", seq))
    }

    override fun end() {
        if (closed || state.value.phase is RemotePhase.Ended) return
        sendJson(JSONObject().put("t", "end"))
        // Give the goodbye a moment to leave before the link is cut.
        main.postDelayed({ stopEverything() }, 400)
        finish(RemoteEndReason.YOU_ENDED)
    }

    override fun close() {
        closed = true
        main.removeCallbacksAndMessages(null)
        stopEverything()
    }

    // ---- Nearby ----

    private fun advertise() {
        val name = listOf(NAME_PREFIX, code, myName.replace('|', ' ').take(RemotePreferences.MAX_NAME)).joinToString("|")
        client.startAdvertising(name, SERVICE_ID, connections,
            AdvertisingOptions.Builder().setStrategy(Strategy.P2P_POINT_TO_POINT).build())
            .addOnFailureListener { failure(it, "advertise") }
    }

    private fun discover() {
        client.startDiscovery(SERVICE_ID, discovery,
            DiscoveryOptions.Builder().setStrategy(Strategy.P2P_POINT_TO_POINT).build())
            .addOnFailureListener { failure(it, "discover") }
    }

    private val discovery = object : EndpointDiscoveryCallback() {
        override fun onEndpointFound(endpointId: String, info: DiscoveredEndpointInfo) {
            val parts = info.endpointName.split('|')
            if (closed || parts.getOrNull(0) != NAME_PREFIX || parts.getOrNull(1) != code || peer != null) return
            client.stopDiscovery()
            client.requestConnection(myName.ifBlank { "AppHear" }, endpointId, connections)
                .addOnFailureListener { retryLater() }
        }

        override fun onEndpointLost(endpointId: String) = Unit
    }

    private val connections = object : ConnectionLifecycleCallback() {
        override fun onConnectionInitiated(endpointId: String, info: ConnectionInfo) {
            if (closed || (peer != null && peer != endpointId)) {
                client.rejectConnection(endpointId) // one viewer per conversation
                return
            }
            client.acceptConnection(endpointId, payloads)
        }

        override fun onConnectionResult(endpointId: String, resolution: ConnectionResolution) {
            if (closed) return
            if (resolution.status.statusCode != ConnectionsStatusCodes.STATUS_OK) {
                if (state.value.role == RemoteRole.VIEWER) retryLater()
                return
            }
            if (state.value.role == RemoteRole.VIEWER) {
                peer = endpointId
                sendJson(JSONObject().put("t", "hello").put("s", secret ?: JSONObject.NULL)
                    .put("name", myName).put("after", state.value.lastSeq))
            }
            // The host waits for "hello" before treating the endpoint as its viewer.
        }

        override fun onDisconnected(endpointId: String) {
            if (endpointId != peer) return
            peer = null
            mutable.update { it.copy(linkUp = false, peerOnline = false) }
            if (closed || state.value.phase !is RemotePhase.Connected) return
            // Reconnect: the host shows itself again under the same code; the viewer looks for it.
            if (state.value.role == RemoteRole.HOST) advertise() else discover()
        }
    }

    private val payloads = object : PayloadCallback() {
        override fun onPayloadReceived(endpointId: String, payload: Payload) {
            val bytes = payload.asBytes() ?: return
            val message = try { JSONObject(String(bytes, Charsets.UTF_8)) } catch (_: Exception) { return }
            main.post { if (!closed) receive(endpointId, message) }
        }

        override fun onPayloadTransferUpdate(endpointId: String, update: PayloadTransferUpdate) = Unit
    }

    private fun receive(endpointId: String, message: JSONObject) {
        when (message.optString("t")) {
            "hello" -> if (state.value.role == RemoteRole.HOST) welcome(endpointId, message)
            "welcome" -> if (state.value.role == RemoteRole.VIEWER) {
                secret = message.optString("s").takeIf { it.length == 32 } ?: secret
                mutable.update { it.copy(phase = RemotePhase.Connected, peerName = message.optString("name"),
                    linkUp = true, peerOnline = true) }
            }
            "refused" -> if (state.value.role == RemoteRole.VIEWER) {
                stopEverything()
                fail(RemoteIssue.INVITE_INVALID)
            }
            "msg" -> if (state.value.role == RemoteRole.VIEWER && endpointId == peer) {
                val id = message.optString("id")
                val seq = message.optLong("seq")
                if (id.isNotEmpty() && seq > 0) mutable.update { it.withServerMessage(id, seq, message.optString("text"), false) }
            }
            "seen" -> if (state.value.role == RemoteRole.HOST) mutable.update { it.withSeenUpTo(message.optLong("seq")) }
            "end" -> if (endpointId == peer) {
                stopEverything()
                finish(RemoteEndReason.OTHER_ENDED)
            }
        }
    }

    /** Host: checks the viewer's invite and, if valid, makes it the conversation's viewer. */
    private fun welcome(endpointId: String, hello: JSONObject) {
        val offered = hello.optString("s").takeIf { !hello.isNull("s") && it.isNotEmpty() }
        val inviteOpen = !joinedOnce && System.currentTimeMillis() < expiresAtMs
        val valid = (peer == null || peer == endpointId) &&
            (if (offered != null) offered == secret && (joinedOnce || inviteOpen) else inviteOpen)
        if (!valid) {
            client.sendPayload(endpointId, json(JSONObject().put("t", "refused")))
            main.postDelayed({ client.disconnectFromEndpoint(endpointId) }, 300)
            return
        }
        peer = endpointId
        joinedOnce = true
        client.stopAdvertising()
        mutable.update { it.copy(phase = RemotePhase.Connected, peerName = hello.optString("name"), linkUp = true, peerOnline = true) }
        sendJson(JSONObject().put("t", "welcome").put("name", myName).put("s", secret))
        // Re-send anything the viewer has not got (it reports the last one it has).
        val after = hello.optLong("after")
        sentSeq.removeAll { it > after }
        flush()
    }

    /** Host: sends every message the viewer has not received yet, in order. */
    private fun flush() {
        val endpoint = peer ?: return
        if (state.value.role != RemoteRole.HOST) return
        state.value.messages.filter { it.fromMe }.forEach { message ->
            val seq = assignedSeq.getOrPut(message.id) { ++hostSeq }
            if (seq in sentSeq) return@forEach
            sentSeq.add(seq)
            client.sendPayload(endpoint, json(JSONObject().put("t", "msg").put("id", message.id).put("seq", seq)
                .put("text", message.text)))
                .addOnSuccessListener { mutable.update { it.withServerMessage(message.id, seq, message.text, true) } }
                .addOnFailureListener {
                    sentSeq.remove(seq)
                    mutable.update { it.withSendFailed(message.id) }
                }
        }
    }

    private fun sendJson(message: JSONObject) {
        val endpoint = peer ?: return
        client.sendPayload(endpoint, json(message))
    }

    private fun json(message: JSONObject) = Payload.fromBytes(message.toString().toByteArray(Charsets.UTF_8))

    private fun retryLater() {
        if (closed || state.value.phase is RemotePhase.Ended || state.value.phase is RemotePhase.Failed) return
        main.postDelayed({ if (!closed && peer == null) discover() }, RETRY_MS)
    }

    private fun failure(error: Exception, step: String) {
        val code = (error as? ApiException)?.statusCode
        if (code == ConnectionsStatusCodes.STATUS_ALREADY_ADVERTISING || code == ConnectionsStatusCodes.STATUS_ALREADY_DISCOVERING) return
        Log.w(TAG, "[nearby] $step failed: $code")
        stopEverything()
        fail(when (code) {
            ConnectionsStatusCodes.MISSING_PERMISSION_ACCESS_COARSE_LOCATION,
            ConnectionsStatusCodes.MISSING_PERMISSION_ACCESS_FINE_LOCATION,
            ConnectionsStatusCodes.MISSING_PERMISSION_BLUETOOTH,
            ConnectionsStatusCodes.MISSING_PERMISSION_BLUETOOTH_ADMIN,
            ConnectionsStatusCodes.MISSING_PERMISSION_ACCESS_WIFI_STATE,
            ConnectionsStatusCodes.MISSING_PERMISSION_CHANGE_WIFI_STATE,
            ConnectionsStatusCodes.MISSING_PERMISSION_BLUETOOTH_SCAN,
            ConnectionsStatusCodes.MISSING_PERMISSION_BLUETOOTH_ADVERTISE,
            ConnectionsStatusCodes.MISSING_PERMISSION_BLUETOOTH_CONNECT,
            ConnectionsStatusCodes.MISSING_PERMISSION_NEARBY_WIFI_DEVICES -> RemoteIssue.NEARBY_PERMISSION
            else -> RemoteIssue.NEARBY_UNAVAILABLE
        })
    }

    private fun stopEverything() {
        client.stopAdvertising()
        client.stopDiscovery()
        client.stopAllEndpoints()
        peer = null
    }

    private fun finish(reason: RemoteEndReason) {
        mutable.update { it.copy(phase = RemotePhase.Ended(reason), linkUp = false, peerOnline = false) }
    }

    private fun fail(issue: RemoteIssue) {
        mutable.update { it.copy(phase = RemotePhase.Failed(issue), linkUp = false, peerOnline = false) }
    }

    private fun invitePhase() = RemotePhase.Inviting(code, secret!!, expiresAtMs, nearby = true)

    companion object {
        private const val TAG = "AppHearRemote"
        /** Same for every AppHear build, so the everyday app and the Lab app can find each other. */
        private const val SERVICE_ID = "apphear.remote.v1"
        private const val NAME_PREFIX = "AH1"
        private const val INVITE_MS = 10 * 60_000L
        private const val FIND_TIMEOUT_MS = 25_000L
        private const val RETRY_MS = 2_000L
    }
}
