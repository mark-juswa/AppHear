package com.example.apphear

import com.example.apphear.data.profile.AccountRepository
import com.example.apphear.domain.profile.*
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class AccountRepositoryTest {
    private val user = AccountProfile("00000000-0000-0000-0000-000000000001", "synthetic@example.invalid", "synthetic", "Synthetic")
    private fun session(expires: Long = 5000, refresh: String = "synthetic-refresh") = AccountSession("synthetic-access", refresh, expires, user)
    private inner class Api : AccountApi {
        var current = session()
        var refreshes = 0
        var logouts = 0
        var loginPassword = ""
        var confirmation = false
        var refreshIssue: AccountIssue? = null
        var userIssue: AccountIssue? = null
        var firstUserUnauthorized = false
        var logoutIssue: AccountIssue? = null
        var updatedUsername = ""
        var avatarIssue: AccountIssue? = null
        override fun login(email: String, password: String): AccountSession { loginPassword = password; return current }
        override fun signup(username: String, email: String, password: String): SignupResult =
            if (confirmation) SignupResult.ConfirmationRequired else SignupResult.SignedIn(current)
        override fun refresh(refreshToken: String): AccountSession {
            refreshes++
            refreshIssue?.let { throw AccountException(it) }
            return session(refresh = "synthetic-rotated")
        }
        override fun user(accessToken: String): AccountProfile {
            if (firstUserUnauthorized) { firstUserUnauthorized = false; throw AccountException(AccountIssue.SESSION_EXPIRED) }
            userIssue?.let { throw AccountException(it) }
            return current.profile
        }
        override fun update(accessToken: String, username: String, fullName: String, avatarUrl: String): AccountProfile {
            updatedUsername = username
            return user.copy(username = username, fullName = fullName, avatarUrl = avatarUrl)
        }
        override fun uploadAvatar(accessToken: String, userId: String, jpeg: ByteArray): String {
            avatarIssue?.let { throw AccountException(it) }
            return "https://synthetic.invalid/avatar"
        }
        override fun logout(accessToken: String) { logouts++; logoutIssue?.let { throw AccountException(it) } }
    }
    private class Store : AccountSessionStore {
        var value: AccountSession? = null
        var failSave = false
        var clears = 0
        override fun load() = value
        override fun save(session: AccountSession) { if (failSave) throw AccountException(AccountIssue.STORAGE); value = session }
        override fun clear() { clears++; value = null }
    }
    private fun repo(api: Api, store: Store) = AccountRepository(api, store) { 1000L }
    private suspend fun expect(issue: AccountIssue, operation: suspend () -> Unit) {
        try { operation(); fail("Expected $issue") } catch (error: AccountException) { assertEquals(issue, error.issue) }
    }

    @Test fun rememberedLoginPersistsAndRestores() = runBlocking {
        val api = Api(); val store = Store(); val original = repo(api, store)
        original.login(user.email, "secret", true)
        assertEquals(user, original.profile.value)
        val recreated = repo(api, store); recreated.restore()
        assertEquals(user, recreated.profile.value)
    }
    @Test fun uncheckedLoginRemovesOldDiskSession() = runBlocking {
        val api = Api(); val store = Store().apply { value = session() }; val repository = repo(api, store)
        repository.login(user.email, "secret", false)
        assertNull(store.value)
        assertEquals(user, repository.profile.value)
        val recreated = repo(api, store); recreated.restore(); assertNull(recreated.profile.value)
    }
    @Test fun passwordWhitespaceIsPreserved() = runBlocking {
        val api = Api(); repo(api, Store()).login(user.email, " secret ", false)
        assertEquals(" secret ", api.loginPassword)
    }
    @Test fun confirmationDoesNotCreateSessionOrBlindLogin() = runBlocking {
        val api = Api().apply { confirmation = true }; val store = Store(); val repository = repo(api, store)
        assertFalse(repository.signup("synthetic", user.email, "secret", "secret"))
        assertNull(repository.profile.value); assertNull(store.value); assertEquals("", api.loginPassword)
    }
    @Test fun confirmedSignupRemembersSession() = runBlocking {
        val store = Store(); val repository = repo(Api(), store)
        assertTrue(repository.signup("synthetic", user.email, "secret", "secret")); assertNotNull(store.value)
    }
    @Test fun expiredTokenRefreshesAndStoresRotatedToken() = runBlocking {
        val api = Api(); val store = Store().apply { value = session(900) }; val repository = repo(api, store)
        repository.restore(); assertEquals(1, api.refreshes); assertEquals("synthetic-rotated", store.value?.refreshToken)
    }
    @Test fun unauthorizedUserRetriesOnceAfterRefresh() = runBlocking {
        val api = Api().apply { firstUserUnauthorized = true }; val store = Store().apply { value = session() }
        repo(api, store).restore(); assertEquals(1, api.refreshes)
    }
    @Test fun invalidRefreshClearsSession() = runBlocking {
        val api = Api().apply { refreshIssue = AccountIssue.CREDENTIALS }; val store = Store().apply { value = session(900) }
        val repository = repo(api, store)
        expect(AccountIssue.SESSION_EXPIRED) { repository.restore() }
        assertNull(store.value); assertNull(repository.profile.value)
    }
    @Test fun networkFailureKeepsCachedIdentityForGuestFallbackUI() = runBlocking {
        val api = Api().apply { userIssue = AccountIssue.NETWORK }; val store = Store().apply { value = session() }
        val repository = repo(api, store)
        expect(AccountIssue.NETWORK) { repository.restore() }
        assertEquals(user, repository.profile.value); assertNotNull(store.value)
    }
    @Test fun secondUnauthorizedResponseClearsSession() = runBlocking {
        val api = Api().apply { userIssue = AccountIssue.SESSION_EXPIRED }; val store = Store().apply { value = session() }
        val repository = repo(api, store)
        expect(AccountIssue.SESSION_EXPIRED) { repository.restore() }
        assertEquals(1, api.refreshes); assertNull(repository.profile.value); assertNull(store.value)
    }
    @Test fun concurrentOperationsOnlyRefreshOnce() = runBlocking {
        val api = Api().apply { current = session(900) }; val store = Store(); val repository = repo(api, store)
        repository.login(user.email, "secret", true)
        (1..12).map { async { repository.saveProfile("synthetic$it", "Synthetic") } }.awaitAll()
        assertEquals(1, api.refreshes)
    }
    @Test fun saveUpdatesAuthenticatedMetadataAndPreservesEmail() = runBlocking {
        val api = Api(); val store = Store(); val repository = repo(api, store)
        repository.login(user.email, "secret", true); repository.saveProfile(" edited ", " New Name ")
        assertEquals("edited", api.updatedUsername); assertEquals(user.email, repository.profile.value?.email)
        assertEquals("New Name", store.value?.profile?.fullName)
    }
    @Test fun logoutRevokesAndClearsPersistedProfile() = runBlocking {
        val api = Api(); val store = Store(); val repository = repo(api, store)
        repository.login(user.email, "secret", true); assertTrue(repository.logout())
        assertEquals(1, api.logouts); assertNull(repository.profile.value); assertNull(store.value)
    }
    @Test fun offlineLogoutStillClearsLocallyAndReportsIncompleteRevocation() = runBlocking {
        val api = Api().apply { logoutIssue = AccountIssue.NETWORK }; val store = Store(); val repository = repo(api, store)
        repository.login(user.email, "secret", true); assertFalse(repository.logout())
        assertNull(repository.profile.value); assertNull(store.value)
    }
    @Test fun storageFailureNeverClaimsRememberedLogin() = runBlocking {
        val api = Api(); val store = Store().apply { failSave = true }; val repository = repo(api, store)
        expect(AccountIssue.STORAGE) { repository.login(user.email, "secret", true) }
        assertNull(repository.profile.value); assertEquals(1, api.logouts)
    }
    @Test fun invalidFieldsDoNotReachApi() = runBlocking {
        val api = Api(); val repository = repo(api, Store())
        expect(AccountIssue.INVALID_INPUT) { repository.signup("", user.email, "secret", "secret") }
        expect(AccountIssue.INVALID_INPUT) { repository.login("invalid", "secret", true) }
        expect(AccountIssue.INVALID_INPUT) { repository.signup("synthetic", user.email, "secret", "mismatch") }
        assertEquals("", api.loginPassword)
        repository.login(user.email, "secret", false)
        expect(AccountIssue.INVALID_INPUT) { repository.saveProfile("x".repeat(81), "Synthetic") }
        expect(AccountIssue.INVALID_INPUT) { repository.saveProfile("synthetic", "bad\nname") }
        assertEquals("", api.updatedUsername)
    }
    @Test fun secretsAreRedactedFromDiagnostics() { assertEquals("AccountSession(redacted)", session().toString()) }
    @Test fun deniedAvatarDoesNotUpdateProfileOrDiscardSession() = runBlocking {
        val api = Api().apply { avatarIssue = AccountIssue.AVATAR }; val store = Store(); val repository = repo(api, store)
        repository.login(user.email, "secret", true)
        expect(AccountIssue.AVATAR) { repository.saveProfile("edited", "Edited", byteArrayOf(1, 2)) }
        assertEquals("", api.updatedUsername); assertEquals(user, repository.profile.value); assertEquals(user, store.value?.profile)
    }
    @Test fun oversizedAvatarIsRejectedBeforeUpload() = runBlocking {
        val api = Api(); val repository = repo(api, Store()); repository.login(user.email, "secret", false)
        expect(AccountIssue.AVATAR) { repository.saveProfile("edited", "Edited", ByteArray(AccountRepository.MAX_AVATAR_BYTES + 1)) }
        assertEquals("", api.updatedUsername)
    }
}
