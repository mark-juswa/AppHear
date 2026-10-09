package com.example.apphear

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.data.profile.EncryptedAccountSessionStore
import com.example.apphear.data.profile.SupabaseAccountApi
import com.example.apphear.domain.profile.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.security.KeyStore
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class AccountSecurityInstrumentedTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val user = AccountProfile("00000000-0000-0000-0000-000000000001", "synthetic@example.invalid", "synthetic", "Synthetic")

    @Test fun secureSessionRoundTripAndBackendBinding() {
        val suffix = UUID.randomUUID().toString()
        val name = "account_security_test_$suffix"
        val alias = "account_security_test_$suffix"
        val store = EncryptedAccountSessionStore(context, "https://synthetic.invalid", name, alias)
        try {
            store.save(AccountSession("synthetic-access-only", "synthetic-refresh-only", 5000, user))
            val recreated = EncryptedAccountSessionStore(context, "https://synthetic.invalid", name, alias)
            assertEquals("synthetic-access-only", recreated.load()?.accessToken)
            assertEquals(user, recreated.load()?.profile)
            val raw = context.getSharedPreferences(name, Context.MODE_PRIVATE).getString("session", "").orEmpty()
            assertFalse(raw.contains("synthetic-access-only")); assertFalse(raw.contains(user.email))
            val otherBackend = EncryptedAccountSessionStore(context, "https://other.invalid", name, alias)
            try { otherBackend.load(); fail("Backend change must reject stored session") }
            catch (error: AccountException) { assertEquals(AccountIssue.SESSION_EXPIRED, error.issue) }
            assertNull(store.load())
        } finally {
            context.deleteSharedPreferences(name)
            KeyStore.getInstance("AndroidKeyStore").apply { load(null); deleteEntry(alias) }
        }
    }

    @Test fun jsonResponsesHandleConfirmedAndUnconfirmedRegistration() {
        val metadata = SupabaseAccountApi.json("username" to user.username, "full_name" to user.fullName)
        val jsonUser = SupabaseAccountApi.json("id" to user.id, "email" to user.email, "user_metadata" to metadata)
        assertSame(SignupResult.ConfirmationRequired, SupabaseAccountApi.parseSignup(jsonUser))
        val response = SupabaseAccountApi.json("access_token" to "synthetic", "refresh_token" to "synthetic",
            "expires_at" to 5000, "user" to jsonUser)
        assertTrue(SupabaseAccountApi.parseSignup(response) is SignupResult.SignedIn)
        assertEquals(user, SupabaseAccountApi.parseSession(response).profile)
        try { SupabaseAccountApi.parseSignup(JSONObject()); fail("Malformed response must fail") }
        catch (error: AccountException) { assertEquals(AccountIssue.SERVER, error.issue) }
    }

    @Test fun establishedProfileOrderAndReadOnlyEmailArePresent() {
        InstrumentationRegistry.getInstrumentation().runOnMainSync {
            val themed = android.view.ContextThemeWrapper(context, R.style.Theme_AppHear)
            val binding = com.example.apphear.databinding.FragmentProfileBinding.inflate(android.view.LayoutInflater.from(themed))
            val container = binding.profileContainer
            assertTrue(container.indexOfChild(binding.profileCard) < container.indexOfChild(binding.profilePreferences))
            assertFalse(binding.inputProfileEmail.isEnabled)
            assertEquals(android.view.View.GONE, binding.profileAuth.root.visibility)
            assertEquals(context.getString(R.string.profile_edit_profile), binding.profileEditLabel.text.toString())
            assertFalse(binding.profileAuth.inputPassword.isSaveEnabled)
            assertFalse(binding.profileAuth.inputConfirmPassword.isSaveEnabled)
        }
    }
}
