package com.example.apphear.data.profile

import com.example.apphear.domain.profile.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Account-only IO; never touches recognition or local character preferences. */
class AccountRepository(
    private val api: AccountApi,
    private val store: AccountSessionStore,
    private val clockSeconds: () -> Long = { System.currentTimeMillis() / 1000 },
) {
    private val mutex = Mutex()
    private var session: AccountSession? = null
    private var remembered = false
    private var initialized = false
    private val mutableProfile = MutableStateFlow<AccountProfile?>(null)
    val profile: StateFlow<AccountProfile?> = mutableProfile.asStateFlow()

    // A rotated refresh token must be committed even if the user leaves the screen mid-request.
    private suspend fun <T> operation(block: () -> T): T = withContext(Dispatchers.IO) {
        mutex.withLock { withContext(NonCancellable) { block() } }
    }

    suspend fun restore() = operation {
        if (!initialized) {
            initialized = true
            session = store.load()
            remembered = session != null
            mutableProfile.value = session?.profile
        }
        if (session != null) {
            val user = authorized { api.user(it.accessToken) }
            commit(requireSession().withProfile(user))
        }
    }

    suspend fun login(email: String, password: String, remember: Boolean) = operation {
        AccountValidation.credentials(email, password, false)
        val result = api.login(email.trim(), password) // Password whitespace is significant.
        accept(result, remember)
    }

    suspend fun signup(username: String, email: String, password: String, confirmation: String): Boolean = operation {
        AccountValidation.profile(username, "")
        AccountValidation.credentials(email, password, true, confirmation)
        when (val result = api.signup(username.trim(), email.trim(), password)) {
            SignupResult.ConfirmationRequired -> false
            is SignupResult.SignedIn -> { accept(result.session, true); true }
        }
    }

    suspend fun saveProfile(username: String, fullName: String, jpeg: ByteArray? = null) = operation {
        AccountValidation.profile(username, fullName)
        var avatar = requireSession().profile.avatarUrl
        if (jpeg != null) {
            if (jpeg.isEmpty() || jpeg.size > MAX_AVATAR_BYTES) throw AccountException(AccountIssue.AVATAR)
            avatar = authorized { api.uploadAvatar(it.accessToken, it.profile.id, jpeg) }
        }
        val user = authorized { api.update(it.accessToken, username.trim(), fullName.trim(), avatar) }
        commit(requireSession().withProfile(user))
    }

    /** False means local sign-out succeeded but server revocation could not be confirmed. */
    suspend fun logout(): Boolean = operation {
        var revoked = true
        try {
            if (session != null) authorized { api.logout(it.accessToken) }
        } catch (error: AccountException) {
            revoked = error.issue == AccountIssue.SESSION_EXPIRED
        } finally {
            clearSession()
        }
        revoked
    }

    private fun accept(value: AccountSession, remember: Boolean) {
        initialized = true
        // Avoid reporting a remembered login when secure persistence failed.
        try {
            if (remember) store.save(value) else store.clear()
        } catch (error: AccountException) {
            try { api.logout(value.accessToken) } catch (_: AccountException) { /* Best effort; no token is retained. */ }
            throw error
        }
        remembered = remember
        session = value
        mutableProfile.value = value.profile
    }

    private fun commit(value: AccountSession) {
        if (session != null && value.profile.id != session?.profile?.id) {
            clearSession()
            throw AccountException(AccountIssue.SESSION_EXPIRED)
        }
        session = value
        mutableProfile.value = value.profile
        if (remembered) store.save(value)
    }

    private fun requireSession(): AccountSession = session ?: throw AccountException(AccountIssue.SESSION_EXPIRED)

    private fun refresh() {
        val before = requireSession()
        val result = try { api.refresh(before.refreshToken) } catch (error: AccountException) {
            if (error.issue == AccountIssue.CREDENTIALS || error.issue == AccountIssue.SESSION_EXPIRED) {
                clearSession()
                throw AccountException(AccountIssue.SESSION_EXPIRED)
            }
            throw error
        }
        if (result.profile.id != before.profile.id) {
            clearSession()
            throw AccountException(AccountIssue.SESSION_EXPIRED)
        }
        commit(result)
    }

    private fun <T> authorized(block: (AccountSession) -> T): T {
        if (requireSession().expiresAt <= clockSeconds() + REFRESH_MARGIN_SECONDS) refresh()
        try { return block(requireSession()) } catch (error: AccountException) {
            if (error.issue != AccountIssue.SESSION_EXPIRED) throw error
        }
        refresh()
        return try { block(requireSession()) } catch (error: AccountException) {
            if (error.issue == AccountIssue.SESSION_EXPIRED) clearSession()
            throw error
        }
    }

    private fun clearSession() {
        session = null
        remembered = false
        mutableProfile.value = null
        store.clear()
    }

    companion object {
        const val MAX_AVATAR_BYTES = 2 * 1024 * 1024
        private const val REFRESH_MARGIN_SECONDS = 60L
    }
}
