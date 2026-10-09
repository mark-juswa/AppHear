package com.example.apphear.data.settings

import android.content.Context
import com.example.apphear.BuildConfig
import com.example.apphear.domain.texttoasl.AslCharacterChoice

class AslCharacterSettings(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences("text_to_asl", Context.MODE_PRIVATE)

    val selectionAvailable: Boolean
        get() = BuildConfig.ASL_CHARACTER_SELECTION_ENABLED && BuildConfig.ASL_MORE_WORDS_ENABLED

    fun current(): AslCharacterChoice = AslCharacterChoice.resolve(
        saved = runCatching { preferences.getString(KEY_CHARACTER, null) }.getOrNull(),
        selectionEnabled = BuildConfig.ASL_CHARACTER_SELECTION_ENABLED,
        newAssetsAvailable = BuildConfig.ASL_ASSET_PILOT_ENABLED,
    )

    fun select(choice: AslCharacterChoice) {
        if (selectionAvailable) preferences.edit().putString(KEY_CHARACTER, choice.preferenceValue).apply()
    }

    private companion object {
        const val KEY_CHARACTER = "character"
    }
}
