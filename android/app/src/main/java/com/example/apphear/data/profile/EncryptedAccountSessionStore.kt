package com.example.apphear.data.profile

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.example.apphear.domain.profile.*
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class EncryptedAccountSessionStore(
    context: Context,
    private val backend: String,
    private val preferencesName: String = PREFERENCES,
    private val keyAlias: String = "apphear_account_session_v1",
) : AccountSessionStore {
    private val app = context.applicationContext
    private val preferences get() = app.getSharedPreferences(preferencesName, Context.MODE_PRIVATE)

    override fun load(): AccountSession? {
        val encoded = preferences.getString("session", null) ?: return null
        try {
            val envelope = JSONObject(encoded)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(envelope.getString("iv"), Base64.NO_WRAP)))
            cipher.updateAAD(backend.toByteArray(Charsets.UTF_8))
            val value = JSONObject(cipher.doFinal(Base64.decode(envelope.getString("data"), Base64.NO_WRAP)).toString(Charsets.UTF_8))
            if (value.getInt("version") != 1) throw AccountException(AccountIssue.SESSION_EXPIRED)
            return SupabaseAccountApi.parseSession(value)
        } catch (_: Exception) {
            clear()
            throw AccountException(AccountIssue.SESSION_EXPIRED)
        }
    }

    override fun save(session: AccountSession) {
        try {
            val p = session.profile
            val value = SupabaseAccountApi.json("version" to 1, "access_token" to session.accessToken,
                "refresh_token" to session.refreshToken, "expires_at" to session.expiresAt,
                "user" to SupabaseAccountApi.json("id" to p.id, "email" to p.email,
                    "user_metadata" to SupabaseAccountApi.json("username" to p.username, "full_name" to p.fullName, "avatar_url" to p.avatarUrl)))
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key())
            cipher.updateAAD(backend.toByteArray(Charsets.UTF_8))
            val encrypted = cipher.doFinal(value.toString().toByteArray(Charsets.UTF_8))
            val envelope = SupabaseAccountApi.json("iv" to Base64.encodeToString(cipher.iv, Base64.NO_WRAP),
                "data" to Base64.encodeToString(encrypted, Base64.NO_WRAP))
            if (!preferences.edit().putString("session", envelope.toString()).commit()) throw AccountException(AccountIssue.STORAGE)
        } catch (_: Exception) { throw AccountException(AccountIssue.STORAGE) }
    }

    override fun clear() {
        if (!preferences.edit().clear().commit() && !app.deleteSharedPreferences(preferencesName)) {
            throw AccountException(AccountIssue.STORAGE)
        }
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(keyAlias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build())
            generateKey()
        }
    }

    companion object {
        const val PREFERENCES = "apphear_account_secure"
    }
}
