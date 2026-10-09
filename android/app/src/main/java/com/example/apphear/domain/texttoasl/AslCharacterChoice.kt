package com.example.apphear.domain.texttoasl

enum class AslCharacterChoice(val preferenceValue: String) {
    ORIGINAL("original"),
    NEW("new");

    companion object {
        fun resolve(saved: String?, selectionEnabled: Boolean, newAssetsAvailable: Boolean): AslCharacterChoice {
            if (!newAssetsAvailable) return ORIGINAL
            // Existing pilots keep their behavior when the selection experiment is off.
            if (!selectionEnabled) return NEW
            return entries.firstOrNull { it.preferenceValue == saved } ?: ORIGINAL
        }
    }
}
