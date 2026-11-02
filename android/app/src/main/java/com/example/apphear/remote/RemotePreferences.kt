package com.example.apphear.remote

import android.content.Context
import com.example.apphear.data.profile.AccountServices

/** Remote conversation choices from Settings. */
class RemotePreferences(context: Context) {
    private val app = context.applicationContext
    private val preferences = app.getSharedPreferences("apphear_remote_preferences", Context.MODE_PRIVATE)

    /** The name the other phone shows ("Connected to …"). Defaults to the account username, if any. */
    var displayName: String
        get() = preferences.getString(KEY_NAME, null)?.takeIf { it.isNotBlank() } ?: accountName()
        set(value) { preferences.edit().putString(KEY_NAME, value.trim().take(MAX_NAME)).apply() }

    /** Always connect phone to phone (Nearby), never through the internet. */
    var offlineOnly: Boolean
        get() = preferences.getBoolean(KEY_OFFLINE, false)
        set(value) { preferences.edit().putBoolean(KEY_OFFLINE, value).apply() }

    private fun accountName(): String = if (!AccountServices.enabled) "" else
        AccountServices.repository(app).profile.value?.username.orEmpty()

    companion object {
        const val MAX_NAME = 40
        private const val KEY_NAME = "display_name"
        private const val KEY_OFFLINE = "offline_only"
    }
}
