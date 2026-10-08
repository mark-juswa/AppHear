package com.example.apphear.data.settings

import android.content.Context
import com.example.apphear.BuildConfig
import com.example.apphear.fingerspelling.RecognitionMode

/** Default WORD. Unsupported/stale choices safely resolve to WORD in nonexperimental builds. */
class RecognitionModeSettings(context: Context) {
    private val prefs = context.getSharedPreferences("recognition_mode", Context.MODE_PRIVATE)
    val selectionAvailable get() = BuildConfig.FINGERSPELL_EXPERIMENT_ENABLED
    fun current() = resolve(prefs.getString("selected", null), selectionAvailable)
    fun select(mode: RecognitionMode) {
        require(mode == RecognitionMode.WORD || selectionAvailable)
        prefs.edit().putString("selected", mode.name).apply()
    }
    companion object {
        fun resolve(saved: String?, enabled: Boolean) =
            if (enabled && saved == RecognitionMode.FINGERSPELL.name) RecognitionMode.FINGERSPELL else RecognitionMode.WORD
    }
}
