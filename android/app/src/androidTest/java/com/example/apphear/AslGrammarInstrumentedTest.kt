package com.example.apphear

import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.domain.texttoasl.AslTranslationPlanner
import com.example.apphear.domain.texttoasl.TextToAslPlan
import com.example.apphear.ui.texttoasl.AndroidAslGrammarLoader
import com.example.apphear.ui.texttoasl.AndroidAssetAslCatalogLoader
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Tests packaged registry/catalog wiring; qualified ASL review is a separate activity. */
class AslGrammarInstrumentedTest {
    @Test fun packagedDictionaryPreviewsCannotBecomeValidatedSentenceTranslations() {
        assumeTrue(BuildConfig.ASL_ASSET_PILOT_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED)
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val registry = AndroidAslGrammarLoader(context).load()
        assertTrue(registry.enabled)
        assertTrue("No invented validated phrase records",registry.phrases.isEmpty())
        assertEquals(10,registry.everydayExpressions.size)
        val catalog = AndroidAssetAslCatalogLoader(context,false).load()
        val planner = AslTranslationPlanner(catalog,registry)
        assertTrue(catalog.getAssets().none { it.metadata.isLinguisticallyValidated })
        assertEquals(listOf("hello","beautiful"),planner.plan("HELLO BEAUTIFUL").queue.map { it.id })
        val question = planner.plan("What is your name?")
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,question.mode)
        assertTrue(question.translationNotice!!.contains("unavailable"))
        assertTrue(question.unsupportedTokens.contains("NAME"))
        assertTrue(question.queue.isEmpty())
        for (text in listOf("It is hot today.", "IT IS HOT TODAY", "It's hot today!", "Today is hot.")) {
            val plan = planner.plan(text)
            assertEquals("everyday_hot_today",plan.ruleId)
            assertTrue(plan.queue.isEmpty())
            assertTrue(plan.unsupportedTokens.isEmpty())
        }
        assertTrue(planner.plan("I am not a student").queue.isEmpty())
        assertTrue(planner.plan("break a leg").queue.isEmpty())
        assertNotNull(catalog.findByAlias("idle"))
    }
}
