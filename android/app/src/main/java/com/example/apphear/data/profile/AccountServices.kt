package com.example.apphear.data.profile

import android.content.Context
import com.example.apphear.BuildConfig
import com.example.apphear.ui.settings.AppConfiguration

object AccountServices {
    val enabled: Boolean get() = BuildConfig.PROFILE_ACCOUNTS_ENABLED
    @Volatile private var instance: AccountRepository? = null

    fun repository(context: Context): AccountRepository = instance ?: synchronized(this) {
        instance ?: AccountRepository(
            SupabaseAccountApi(AppConfiguration.supabaseUrl, AppConfiguration.supabaseAnonKey),
            EncryptedAccountSessionStore(context.applicationContext, AppConfiguration.supabaseUrl.trimEnd('/')),
        ).also { instance = it }
    }
}
