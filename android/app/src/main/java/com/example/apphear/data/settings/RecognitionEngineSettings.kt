package com.example.apphear.data.settings

import android.content.Context
import com.example.apphear.BuildConfig
import com.example.apphear.perceptionvnext.PhoneRecognitionConfiguration

/** Debug-only Stable/Experimental live recognition choice; default and release are STABLE. */
internal class RecognitionEngineSettings(context: Context) {
    private val prefs = context.getSharedPreferences("recognition_engine", Context.MODE_PRIVATE)
    val selectionAvailable get() = BuildConfig.DEBUG
    /** The saved choice; with none saved, the build's default (STABLE unless a debug build sets one). */
    fun current() = PhoneRecognitionConfiguration.resolve(
        prefs.getString("selected", null) ?: BuildConfig.DEFAULT_RECOGNITION_ENGINE, selectionAvailable)
    fun select(configuration: PhoneRecognitionConfiguration) {
        require(configuration == PhoneRecognitionConfiguration.STABLE || selectionAvailable)
        prefs.edit().putString("selected", configuration.name).apply()
    }
}
