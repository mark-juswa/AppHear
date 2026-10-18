package com.example.apphear

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.data.settings.AslCharacterSettings
import com.example.apphear.domain.texttoasl.AslCharacterChoice
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.example.apphear.ui.texttoasl.AndroidAssetAslCatalogLoader
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AslCharacterSettingsInstrumentedTest {
    @Test
    fun selectedCatalogUsesOneHumanRigAndNeverFallsBack() {
        assumeTrue(BuildConfig.ASL_CHARACTER_SELECTION_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED && BuildConfig.ASL_ASSET_PILOT_ENABLED)
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val original = AndroidAssetAslCatalogLoader(context, false).load()
        val expanded = AndroidAssetAslCatalogLoader(context, true).load()
        assertEquals(204, original.getAssets().size)
        assertEquals(28, expanded.getAssets().size)
        assertTrue(original.getAssets().all { it.metadata.avatarProfile == com.example.apphear.domain.texttoasl.SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN })
        assertTrue(expanded.getAssets().all { it.metadata.avatarProfile == com.example.apphear.domain.texttoasl.SignDictionaryMetadata.AvatarProfile.NEW_HUMAN })
        assertTrue((original.getAssets() + expanded.getAssets()).all { it.replacement?.fallbackAssetPath == null })
        assertNull(expanded.findByAlias("hello"))
        assertEquals(0.0, original.findByAlias("idle")!!.neutralFrameSeconds)
        assertEquals("IDLE_NEUTRAL_FEMALEASL", expanded.findByAlias("idle")!!.replacement?.animationName)
        assertEquals(AslAnimationAsset.Type.POSE, expanded.findByAlias("idle")!!.type)
        val originalPlan = AslPhrasePlanner(original, dictionarySequenceMode = true).plan("HELLO BEAUTIFUL")
        assertEquals(listOf("hello", "beautiful"), originalPlan.queue.map { it.id })
        val newPlan = AslPhrasePlanner(expanded, dictionarySequenceMode = true).plan("HELLO BEAUTIFUL")
        assertEquals(listOf("beautiful"), newPlan.queue.map { it.id })
        assertEquals(listOf("hello"), newPlan.unsupportedTokens)
        assertEquals(listOf("cat"), AslPhrasePlanner(expanded, completeWordFallback = true,
            dictionarySequenceMode = true).plan("cat").unsupportedTokens)
    }
    @Test
    fun characterChoicePersistsAcrossRepositoryRecreationAndDefaultsSafely() {
        assumeTrue(BuildConfig.ASL_CHARACTER_SELECTION_ENABLED)
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val preferences = context.getSharedPreferences("text_to_asl", Context.MODE_PRIVATE)
        val previous = preferences.getString("character", null)
        try {
            preferences.edit().remove("character").commit()
            assertEquals(AslCharacterChoice.ORIGINAL, AslCharacterSettings(context).current())
            AslCharacterSettings(context).select(AslCharacterChoice.NEW)
            assertEquals(AslCharacterChoice.NEW, AslCharacterSettings(context).current())
            AslCharacterSettings(context).select(AslCharacterChoice.ORIGINAL)
            assertEquals(AslCharacterChoice.ORIGINAL, AslCharacterSettings(context).current())
            preferences.edit().putString("character", "unsupported").commit()
            assertEquals(AslCharacterChoice.ORIGINAL, AslCharacterSettings(context).current())
        } finally {
            preferences.edit().apply {
                if (previous == null) remove("character") else putString("character", previous)
            }.commit()
        }
    }
}
