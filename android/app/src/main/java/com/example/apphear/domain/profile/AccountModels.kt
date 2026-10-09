package com.example.apphear.domain.profile

data class AccountProfile(
    val id: String,
    val email: String,
    val username: String,
    val fullName: String,
    val avatarUrl: String = "",
) {
    val displayName: String get() = fullName.ifBlank { username }.ifBlank { email.substringBefore('@') }
}

// Never let a diagnostic interpolation expose credentials.
class AccountSession(val accessToken: String, val refreshToken: String, val expiresAt: Long, val profile: AccountProfile) {
    fun withProfile(value: AccountProfile) = AccountSession(accessToken, refreshToken, expiresAt, value)
    override fun toString() = "AccountSession(redacted)"
}

sealed interface SignupResult {
    class SignedIn(val session: AccountSession) : SignupResult
    data object ConfirmationRequired : SignupResult
}

enum class AccountIssue {
    CONFIGURATION, NETWORK, CREDENTIALS, EMAIL_UNCONFIRMED, RATE_LIMIT, SIGNUP_DISABLED,
    PASSWORD_POLICY, CAPTCHA, SESSION_EXPIRED, STORAGE, AVATAR, SERVER, INVALID_INPUT,
}

class AccountException(val issue: AccountIssue) : Exception(issue.name)

object AccountValidation {
    fun profile(username: String, fullName: String) {
        if (username.trim().isEmpty() || username.trim().length > 80 || fullName.trim().length > 120 ||
            (username + fullName).any { it.isISOControl() }) throw AccountException(AccountIssue.INVALID_INPUT)
    }

    fun credentials(email: String, password: String, signup: Boolean, confirmation: String = password) {
        if (email.length > 254 || !Regex("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$").matches(email.trim()) ||
            password.isEmpty() || password.length > 1024 || (signup && (password.length < 6 || password != confirmation))) {
            throw AccountException(AccountIssue.INVALID_INPUT)
        }
    }
}

interface AccountApi {
    fun login(email: String, password: String): AccountSession
    fun signup(username: String, email: String, password: String): SignupResult
    fun refresh(refreshToken: String): AccountSession
    fun user(accessToken: String): AccountProfile
    fun update(accessToken: String, username: String, fullName: String, avatarUrl: String): AccountProfile
    fun uploadAvatar(accessToken: String, userId: String, jpeg: ByteArray): String
    fun logout(accessToken: String)
}

interface AccountSessionStore {
    fun load(): AccountSession?
    fun save(session: AccountSession)
    fun clear()
}
