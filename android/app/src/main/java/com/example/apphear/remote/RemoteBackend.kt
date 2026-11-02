package com.example.apphear.remote

import com.example.apphear.data.profile.AccountAvatarImages
import com.example.apphear.domain.profile.AccountException
import com.example.apphear.domain.profile.AccountSession
import com.example.apphear.data.profile.SupabaseAccountApi
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.time.OffsetDateTime

class RemoteException(val issue: RemoteIssue) : Exception(issue.name)

/**
 * Blocking HTTPS calls to the AppHear Supabase project for remote conversations (run off the main
 * thread). Same hardening as SupabaseAccountApi: https only, no redirects, bounded responses.
 * Schema: supabase/migrations/20261102_remote_conversation.sql.
 */
class RemoteBackend(baseUrl: String, private val publicKey: String) {
    private val base = baseUrl.trim().trimEnd('/')

    data class Invite(val conversationId: String, val code: String, val secret: String, val expiresAtMs: Long)
    data class JoinResult(val conversationId: String, val hostName: String)
    data class ConversationRow(
        val id: String, val hostId: String, val hostName: String, val viewerId: String?,
        val viewerSeenSeq: Long, val ended: Boolean, val endedBy: String?, val viewerName: String = "",
    )
    data class MessageRow(val id: String, val conversationId: String, val seq: Long, val senderId: String, val body: String)

    val configured: Boolean get() = base.startsWith("https://") && publicKey.isNotBlank()
    val realtimeUrl: String get() = base.replaceFirst("https://", "wss://") +
        "/realtime/v1/websocket?apikey=" + URLEncoder.encode(publicKey, "UTF-8") + "&vsn=1.0.0"
    val key: String get() = publicKey

    fun signInAnonymously(): AccountSession = session(request("/auth/v1/signup", "POST", JSONObject())!!)
    fun refresh(refreshToken: String): AccountSession =
        session(request("/auth/v1/token?grant_type=refresh_token", "POST", JSONObject().put("refresh_token", refreshToken))!!)

    fun createConversation(token: String, hostName: String): Invite {
        val row = single(rpc(token, "create_remote_conversation", JSONObject().put("p_host_name", hostName)))
        return Invite(row.getString("id"), row.getString("code"), row.getString("secret"), millis(row.getString("expires_at")))
    }

    fun renewInvite(token: String, conversationId: String): Invite {
        val row = single(rpc(token, "renew_remote_invite", JSONObject().put("p_id", conversationId)))
        return Invite(conversationId, row.getString("code"), row.getString("secret"), millis(row.getString("expires_at")))
    }

    fun join(token: String, code: String, secret: String?, viewerName: String): JoinResult {
        val row = single(rpc(token, "join_remote_conversation", JSONObject().put("p_code", code)
            .put("p_secret", secret ?: JSONObject.NULL).put("p_viewer_name", viewerName)))
        when (row.optString("status")) {
            "joined" -> return JoinResult(row.getString("id"), row.optString("host_name"))
            "rate_limited" -> throw RemoteException(RemoteIssue.RATE_LIMITED)
            "own_invite" -> throw RemoteException(RemoteIssue.OWN_INVITE)
            "invalid" -> throw RemoteException(RemoteIssue.INVITE_INVALID)
            else -> throw RemoteException(RemoteIssue.SERVER)
        }
    }

    /** True when the conversation has ended (or this user is not in it). */
    fun touch(token: String, conversationId: String): Boolean =
        rpc(token, "touch_remote_conversation", JSONObject().put("p_id", conversationId)).let { it == "true" }

    fun markSeen(token: String, conversationId: String, seq: Long) {
        rpc(token, "mark_remote_seen", JSONObject().put("p_id", conversationId).put("p_seq", seq))
    }

    fun end(token: String, conversationId: String) {
        rpc(token, "end_remote_conversation", JSONObject().put("p_id", conversationId))
    }

    fun conversation(token: String, conversationId: String): ConversationRow? {
        val rows = JSONArray(request("/rest/v1/remote_conversations?id=eq.$conversationId&select=*", "GET", token = token)!!)
        return if (rows.length() == 0) null else conversationFromRecord(rows.getJSONObject(0))
    }

    /** Sends one message. Re-sending the same id after a lost reply is safe: the stored row is returned. */
    fun send(token: String, id: String, conversationId: String, body: String): MessageRow {
        val created = request("/rest/v1/remote_conversation_messages", "POST",
            JSONObject().put("id", id).put("conversation_id", conversationId).put("body", body),
            token, representation = true, conflictOk = true)
        val rows = JSONArray(created ?: request("/rest/v1/remote_conversation_messages?id=eq.$id&select=*", "GET", token = token))
        if (rows.length() == 0) throw RemoteException(RemoteIssue.SERVER)
        return messageRow(rows.getJSONObject(0))
    }

    fun messagesAfter(token: String, conversationId: String, seq: Long): List<MessageRow> {
        val rows = JSONArray(request("/rest/v1/remote_conversation_messages?conversation_id=eq.$conversationId" +
            "&seq=gt.$seq&order=seq.asc&limit=100&select=*", "GET", token = token)!!)
        return (0 until rows.length()).map { messageRow(rows.getJSONObject(it)) }
    }

    private fun rpc(token: String, name: String, body: JSONObject): String =
        request("/rest/v1/rpc/$name", "POST", body, token)!!

    private fun single(text: String): JSONObject {
        val rows = JSONArray(text)
        if (rows.length() == 0) throw RemoteException(RemoteIssue.SERVER)
        return rows.getJSONObject(0)
    }

    private fun session(text: String): AccountSession = try {
        SupabaseAccountApi.parseSession(JSONObject(text))
    } catch (_: AccountException) { throw RemoteException(RemoteIssue.SERVER) }

    private fun request(path: String, method: String, body: JSONObject? = null, token: String? = null,
                        representation: Boolean = false, conflictOk: Boolean = false): String? {
        if (!configured) throw RemoteException(RemoteIssue.NOT_CONFIGURED)
        val uri = try { URI(base) } catch (_: Exception) { throw RemoteException(RemoteIssue.NOT_CONFIGURED) }
        if (uri.host.isNullOrEmpty() || uri.userInfo != null || uri.query != null) throw RemoteException(RemoteIssue.NOT_CONFIGURED)
        try {
            val connection = URL(base + path).openConnection() as HttpURLConnection
            try {
                connection.requestMethod = method
                connection.instanceFollowRedirects = false // never forward the bearer token elsewhere
                connection.connectTimeout = 10_000
                connection.readTimeout = 15_000
                connection.setRequestProperty("apikey", publicKey)
                connection.setRequestProperty("Accept", "application/json")
                connection.setRequestProperty("Authorization", "Bearer ${token ?: publicKey}")
                if (representation) connection.setRequestProperty("Prefer", "return=representation")
                if (body != null) {
                    val payload = body.toString().toByteArray(Charsets.UTF_8)
                    connection.doOutput = true
                    connection.setRequestProperty("Content-Type", "application/json")
                    connection.setFixedLengthStreamingMode(payload.size)
                    connection.outputStream.use { it.write(payload) }
                }
                val status = connection.responseCode
                val stream = if (status in 200..299) connection.inputStream else connection.errorStream
                val text = stream?.use {
                    try { AccountAvatarImages.boundedBytes(it, MAX_RESPONSE_BYTES).toString(Charsets.UTF_8) }
                    catch (_: AccountException) { throw RemoteException(RemoteIssue.SERVER) }
                }.orEmpty()
                if (status == 409 && conflictOk) return null
                if (status !in 200..299) {
                    val error = try { JSONObject(text) } catch (_: Exception) { JSONObject() }
                    val code = error.optString("error_code", error.optString("code"))
                    val message = error.optString("msg", error.optString("message"))
                    if (status == 401 || code == "bad_jwt" || code == "PGRST301" || code == "PGRST303") throw SessionExpired()
                    throw RemoteException(when {
                        code == "anonymous_provider_disabled" || message.contains("anonymous sign-ins are disabled", true) ->
                            RemoteIssue.GUEST_SIGN_IN_OFF
                        code == "PGRST202" || code == "PGRST205" || code == "42P01" || status == 404 -> RemoteIssue.SERVER_NOT_READY
                        status == 429 -> RemoteIssue.RATE_LIMITED
                        else -> RemoteIssue.SERVER
                    })
                }
                return text
            } finally {
                connection.disconnect()
            }
        } catch (_: IOException) {
            throw RemoteException(RemoteIssue.OFFLINE)
        }
    }

    /** The access token was refused: refresh it and retry once. */
    class SessionExpired : Exception("session expired")

    companion object {
        private const val MAX_RESPONSE_BYTES = 512 * 1024

        fun messageRow(value: JSONObject) = MessageRow(value.getString("id"), value.getString("conversation_id"),
            value.getLong("seq"), value.getString("sender_id"), value.getString("body"))

        fun conversationFromRecord(value: JSONObject) = ConversationRow(
            id = value.getString("id"), hostId = value.getString("host_id"), hostName = value.optString("host_name"),
            viewerId = value.optString("viewer_id").takeIf { it.isNotBlank() && it != "null" },
            viewerSeenSeq = value.optLong("viewer_seen_seq"),
            ended = !value.isNull("ended_at"), endedBy = value.optString("ended_by").takeIf { it.isNotBlank() && it != "null" },
            viewerName = value.optString("viewer_name").takeIf { it != "null" }.orEmpty(),
        )

        fun millis(timestamp: String): Long = OffsetDateTime.parse(timestamp).toInstant().toEpochMilli()
    }
}
