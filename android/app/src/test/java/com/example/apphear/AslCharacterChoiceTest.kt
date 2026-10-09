package com.example.apphear

import com.example.apphear.domain.texttoasl.AslCharacterChoice
import org.junit.Assert.assertEquals
import org.junit.Test

class AslCharacterChoiceTest {
    @Test
    fun freshAndInvalidSelectionUsesOriginal() {
        for (value in listOf(null, "", "unknown", "NEW")) {
            assertEquals(AslCharacterChoice.ORIGINAL, AslCharacterChoice.resolve(value, true, true))
        }
    }

    @Test
    fun storedChoiceOnlyEnablesAvailableAssets() {
        assertEquals(AslCharacterChoice.NEW, AslCharacterChoice.resolve("new", true, true))
        assertEquals(AslCharacterChoice.ORIGINAL, AslCharacterChoice.resolve("original", true, true))
        assertEquals(AslCharacterChoice.ORIGINAL, AslCharacterChoice.resolve("new", true, false))
    }

    @Test
    fun disablingSelectionPreservesExistingPilotAndOrdinaryBuildBehavior() {
        assertEquals(AslCharacterChoice.NEW, AslCharacterChoice.resolve("original", false, true))
        assertEquals(AslCharacterChoice.ORIGINAL, AslCharacterChoice.resolve("new", false, false))
    }
}
