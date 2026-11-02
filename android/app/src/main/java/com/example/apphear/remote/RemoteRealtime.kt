package com.example.apphear.remote

import android.os.Handler
import android.os.Looper
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * One live Supabase Realtime channel for a remote conversation: new messages and conversation
 * changes (row-level security applies with the user's token), plus presence so each phone knows
 * whether the other has AppHear open. Callbacks arrive on the main thread. A closed channel is not
 * reused; the owner makes a new one to reconnect.
 */
class RemoteRealtime(
    private val url: String,
    private val conversationId: String,
    private val userId: String,
    private val role: RemoteRole,
    private val listener: Listener,
) {
    interface Listener {
        fun onJoined()
        fun onClosed()
        fun onMessage(row: RemoteBackend.MessageRow)
        fun onConversation(row: RemoteBackend.ConversationRow)
        fun onPeerPresence(online: Boolean)
    }

    private val main = Handler(Looper.getMainLooper())
    private val topic = "realtime:apphear-remote-$conversationId"
    private val present = mutableSetOf<String>()
    private var socket: WebSocket? = null
    private var ref = 0
    private var joinRef = ""
    private var closed = false
    private val heartbeat = object : Runnable {
        override fun run() {
            send(JSONObject().put("topic", "phoenix").put("event", "heartbeat").put("payload", JSONObject()).put("ref", nextRef()))
            main.postDelayed(this, HEARTBEAT_MS)
        }
    }

    fun connect(accessToken: String) {
        socket = client.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                main.post { if (!closed) join(accessToken) }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                main.post { if (!closed) receive(text) }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = lost()
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = lost()
        })
    }

    fun updateToken(accessToken: String) {
        send(message("access_token", JSONObject().put("access_token", accessToken)))
    }

    fun close() {
        if (closed) return
        closed = true
        main.removeCallbacks(heartbeat)
        socket?.close(1000, null)
        socket = null
    }

    private fun lost() {
        main.post {
            if (closed) return@post
            close()
            listener.onClosed()
        }
    }

    private fun join(accessToken: String) {
        val changes = JSONArray()
            .put(JSONObject().put("event", "INSERT").put("schema", "public")
                .put("table", "remote_conversation_messages").put("filter", "conversation_id=eq.$conversationId"))
            .put(JSONObject().put("event", "UPDATE").put("schema", "public")
                .put("table", "remote_conversations").put("filter", "id=eq.$conversationId"))
        val config = JSONObject()
            .put("broadcast", JSONObject().put("self", false).put("ack", false))
            .put("presence", JSONObject().put("key", userId))
            .put("postgres_changes", changes)
            .put("private", false)
        joinRef = nextRef()
        send(JSONObject().put("topic", topic).put("event", "phx_join").put("ref", joinRef).put("join_ref", joinRef)
            .put("payload", JSONObject().put("config", config).put("access_token", accessToken)))
        main.postDelayed(heartbeat, HEARTBEAT_MS)
    }

    private fun receive(text: String) {
        val frame = try { JSONObject(text) } catch (_: Exception) { return }
        if (frame.optString("topic") != topic) return
        val payload = frame.optJSONObject("payload") ?: JSONObject()
        when (frame.optString("event")) {
            "phx_reply" -> if (frame.optString("ref") == joinRef) {
                if (payload.optString("status") == "ok") {
                    send(message("presence", JSONObject().put("type", "presence").put("event", "track")
                        .put("payload", JSONObject().put("role", role.name))))
                    listener.onJoined()
                } else lost()
            }
            "phx_error", "phx_close" -> lost()
            "system" -> if (payload.optString("status") == "error") lost()
            "postgres_changes" -> change(payload.optJSONObject("data") ?: return)
            "presence_state" -> {
                present.clear()
                payload.keys().forEach { present.add(it) }
                peerChanged()
            }
            "presence_diff" -> {
                payload.optJSONObject("joins")?.keys()?.forEach { present.add(it) }
                payload.optJSONObject("leaves")?.keys()?.forEach { present.remove(it) }
                peerChanged()
            }
        }
    }

    private fun change(data: JSONObject) {
        val record = data.optJSONObject("record") ?: return
        try {
            when (data.optString("table")) {
                "remote_conversation_messages" -> listener.onMessage(RemoteBackend.messageRow(record))
                "remote_conversations" -> listener.onConversation(RemoteBackend.conversationFromRecord(record))
            }
        } catch (_: Exception) { /* malformed record: the next catch-up fetch fills the gap */ }
    }

    private fun peerChanged() = listener.onPeerPresence(present.any { it != userId })

    private fun message(event: String, payload: JSONObject) =
        JSONObject().put("topic", topic).put("event", event).put("payload", payload).put("ref", nextRef()).put("join_ref", joinRef)

    private fun send(frame: JSONObject) {
        socket?.send(frame.toString())
    }

    private fun nextRef(): String = (++ref).toString()

    companion object {
        private const val HEARTBEAT_MS = 25_000L
        private val client: OkHttpClient by lazy {
            OkHttpClient.Builder()
                .pingInterval(20, TimeUnit.SECONDS)
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .build()
        }
    }
}
