package com.example.apphear.ui.settings

import com.example.apphear.BuildConfig
import java.net.URI

object AppConfiguration {
    val supabaseUrl: String = BuildConfig.SUPABASE_URL.trim()
    val supabaseAnonKey: String = BuildConfig.SUPABASE_ANON_KEY.trim()
    val elevenLabsApiKey: String = BuildConfig.ELEVENLABS_API_KEY.trim()
    val elevenLabsVoiceId: String = BuildConfig.ELEVENLABS_VOICE_ID.trim()

    val supabaseConfigured: Boolean
        get() = supabaseUrl.startsWith("https://") && supabaseAnonKey.isNotBlank()

    val elevenLabsConfigured: Boolean
        get() = elevenLabsApiKey.isNotBlank() && elevenLabsVoiceId.isNotBlank()

    val supabaseHost: String
        get() = runCatching { URI(supabaseUrl).host.orEmpty() }
            .getOrDefault("")
            .ifBlank { "Configured" }
}
