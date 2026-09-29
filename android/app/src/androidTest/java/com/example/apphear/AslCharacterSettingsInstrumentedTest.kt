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
    fun selectedCatalogPreservesOriginalAndAddsOnlyApprovedNewEntries() {
        assumeTrue(BuildConfig.ASL_CHARACTER_SELECTION_ENABLED)
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val original = AndroidAssetAslCatalogLoader(context, false).load()
        val expanded = AndroidAssetAslCatalogLoader(context, true).load()
        assertEquals(102, original.getAssets().size)
        assertEquals(122, expanded.getAssets().size)
        assertTrue(original.getAssets().all { it.replacement == null })
        assertNull(original.findByAlias("big horizontally"))
        val sharedPath = when {
            BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED -> "asl_animations/vnext/shared-alphabet.glb"
            BuildConfig.ASL_NEW_IDLE_ENABLED -> "asl_animations/vnext/shared-words-idle.glb"
            else -> "asl_animations/vnext/shared-words.glb"
        }
        assertEquals(sharedPath, expanded.findByAlias("all")?.assetPath)
        val idle = expanded.findByAlias("idle")!!
        if (BuildConfig.ASL_NEW_IDLE_ENABLED) {
            assertEquals(sharedPath, idle.assetPath)
            assertEquals("IDLE_NEUTRAL_FEMALEASL", idle.replacement?.animationName)
            assertEquals(AslAnimationAsset.Type.POSE, idle.type)
            assertEquals(original.findByAlias("idle"), idle.originalFallback())
        } else {
            assertEquals(original.findByAlias("idle"), idle)
        }
        assertEquals(original.findByAlias("request"), expanded.findByAlias("request"))
        assertEquals(original.findByAlias("come to here"), expanded.findByAlias("come to here"))
        if (BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED) {
            assertEquals(null, original.findLetter('c'))
            assertEquals("SIGN_LETTER_C_FEMALEASL", expanded.findLetter('c')?.replacement?.animationName)
            assertEquals("SIGN_LETTER_Z_FEMALEASL", expanded.findLetter('z')?.replacement?.animationName)
            assertEquals(listOf("letter_c", "a", "letter_t"),
                AslPhrasePlanner(expanded, completeWordFallback = true).plan("cat").queue.map { it.id })
            assertEquals(listOf("hello"), AslPhrasePlanner(expanded).plan("hello").queue.map { it.id })
        }
        assertEquals(listOf("big_horizontally", "call_by_phone", "call_someones_name", "pay_me"),
            AslPhrasePlanner(expanded).plan("big horizontally call by phone call someone's name pay me")
                .queue.map { it.id })
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
