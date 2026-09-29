package com.example.apphear.data.profile

import com.example.apphear.domain.profile.*
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.util.UUID

class SupabaseAccountApi(private val baseUrl: String, private val publicKey: String) : AccountApi {
    private val base = baseUrl.trimEnd('/')

    override fun login(email: String, password: String) = parseSession(request(
        "/auth/v1/token?grant_type=password", "POST", json("email" to email, "password" to password),
    ))

    override fun signup(username: String, email: String, password: String): SignupResult {
        val response = request("/auth/v1/signup", "POST", json(
            "email" to email, "password" to password, "data" to json("username" to username),
        ))
        return parseSignup(response)
    }

    override fun refresh(refreshToken: String) = parseSession(request(
        "/auth/v1/token?grant_type=refresh_token", "POST", json("refresh_token" to refreshToken),
    ))

    override fun user(accessToken: String) = parseUser(request("/auth/v1/user", "GET", token = accessToken))

    override fun update(accessToken: String, username: String, fullName: String, avatarUrl: String) = parseUser(request(
        "/auth/v1/user", "PUT", json("data" to json("username" to username, "full_name" to fullName, "avatar_url" to avatarUrl)), accessToken,
    ))

    override fun uploadAvatar(accessToken: String, userId: String, jpeg: ByteArray): String {
        val id = try { UUID.fromString(userId).toString() } catch (_: IllegalArgumentException) {
            throw AccountException(AccountIssue.SESSION_EXPIRED)
        }
        val path = "$id/avatar_${UUID.randomUUID()}.jpg"
        request("/storage/v1/object/profile-images/$path", "POST", token = accessToken, bytes = jpeg, mime = "image/jpeg", avatar = true)
        return "$base/storage/v1/object/public/profile-images/$path"
    }

    override fun logout(accessToken: String) {
        request("/auth/v1/logout?scope=local", "POST", token = accessToken)
    }

    private fun request(path: String, method: String, body: JSONObject? = null, token: String? = null,
                        bytes: ByteArray? = null, mime: String = "application/json", avatar: Boolean = false): JSONObject {
        val uri = try { URI(base) } catch (_: Exception) { throw AccountException(AccountIssue.CONFIGURATION) }
        if (uri.scheme != "https" || uri.host.isNullOrEmpty() || uri.userInfo != null ||
            uri.query != null || uri.fragment != null || !publicClientKey(publicKey)) {
            throw AccountException(AccountIssue.CONFIGURATION)
        }
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.instanceFollowRedirects = false // Never forward bearer headers to a redirect host.
            connection.connectTimeout = 15_000
            connection.readTimeout = 25_000
            connection.setRequestProperty("apikey", publicKey)
            connection.setRequestProperty("Accept", "application/json")
            token?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
            val payload = bytes ?: body?.toString()?.toByteArray(Charsets.UTF_8)
            if (payload != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", mime)
                connection.setFixedLengthStreamingMode(payload.size)
                connection.outputStream.use { it.write(payload) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.use {
                val bounded = try { AccountAvatarImages.boundedBytes(it, MAX_RESPONSE_BYTES) }
                    catch (_: AccountException) { throw AccountException(AccountIssue.SERVER) }
                bounded.toString(Charsets.UTF_8)
            }.orEmpty()
            val response = try { if (text.isBlank()) JSONObject() else JSONObject(text) } catch (_: Exception) {
                throw AccountException(if (status == 429) AccountIssue.RATE_LIMIT else AccountIssue.SERVER)
            }
            if (status !in 200..299) {
                val code = response.optString("error_code", response.optString("code"))
                throw AccountException(when {
                    status == 429 -> AccountIssue.RATE_LIMIT
                    code == "email_not_confirmed" -> AccountIssue.EMAIL_UNCONFIRMED
                    code == "signup_disabled" -> AccountIssue.SIGNUP_DISABLED
                    code == "weak_password" -> AccountIssue.PASSWORD_POLICY
                    code == "captcha_failed" -> AccountIssue.CAPTCHA
                    status == 401 || code in setOf("bad_jwt", "session_not_found", "refresh_token_not_found", "refresh_token_already_used") -> AccountIssue.SESSION_EXPIRED
                    avatar -> AccountIssue.AVATAR
                    code == "invalid_credentials" || status == 400 || status == 422 -> AccountIssue.CREDENTIALS
                    else -> AccountIssue.SERVER
                })
            }
            return response
        } catch (error: IOException) {
            throw AccountException(AccountIssue.NETWORK)
        } finally { connection.disconnect() }
    }

    companion object {
        private const val MAX_RESPONSE_BYTES = 1024 * 1024
        private fun publicClientKey(key: String): Boolean {
            if (key.startsWith("sb_publishable_")) return true
            return try {
                val claims = JSONObject(java.util.Base64.getUrlDecoder().decode(key.split('.')[1]).toString(Charsets.UTF_8))
                claims.optString("role") == "anon"
            } catch (_: Exception) { false }
        }
        fun parseSignup(value: JSONObject): SignupResult {
            if (value.optString("access_token").isNotBlank()) return SignupResult.SignedIn(parseSession(value))
            parseUser(value.optJSONObject("user") ?: value)
            return SignupResult.ConfirmationRequired
        }
        fun json(vararg values: Pair<String, Any>): JSONObject = JSONObject().apply { values.forEach { put(it.first, it.second) } }
        fun parseUser(value: JSONObject): AccountProfile {
            val id = value.optString("id")
            try { UUID.fromString(id) } catch (_: IllegalArgumentException) { throw AccountException(AccountIssue.SERVER) }
            val metadata = value.optJSONObject("user_metadata") ?: JSONObject()
            return AccountProfile(id, value.optString("email"), metadata.optString("username"),
                metadata.optString("full_name"), metadata.optString("avatar_url"))
        }
        fun parseSession(value: JSONObject): AccountSession {
            val access = value.optString("access_token")
            val refresh = value.optString("refresh_token")
            val expires = value.optLong("expires_at", System.currentTimeMillis() / 1000 + value.optLong("expires_in"))
            val user = value.optJSONObject("user") ?: throw AccountException(AccountIssue.SERVER)
            if (access.isBlank() || refresh.isBlank() || expires <= 0) throw AccountException(AccountIssue.SERVER)
            return AccountSession(access, refresh, expires, parseUser(user))
        }
    }
}
