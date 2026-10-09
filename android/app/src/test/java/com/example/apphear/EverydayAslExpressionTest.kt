package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import com.google.gson.Gson
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

/** Repository English meaning data and synthetic motion fixtures, not signer validation. */
class EverydayAslExpressionTest {
    private val entries = JsonParser.parseString(String(Files.readAllBytes(Path.of(
        "src/main/assets/asl_animations/everyday_asl.json")))).asJsonObject.getAsJsonArray("expressions")
        .map { Gson().fromJson(it, EverydayAslExpression::class.java) }
    private fun asset(id: String, alias: String = id, type: AslAnimationAsset.Type = AslAnimationAsset.Type.WORD) =
        AslAnimationAsset(id, alias, "asl_animations/fixture_$id.glb", type, listOf(alias),
            metadata = SignDictionaryMetadata(avatarProfile = SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN))
    private val catalog = AslAnimationCatalog.fromAssets(listOf(asset("hello"), asset("thank_you", "thank you"),
        asset("hot"), asset("today"), asset("beautiful"), asset("how"), asset("i_me", "me")))
    private val planner = AslTranslationPlanner(catalog, AslGrammarRegistry(everydayExpressions = entries))

    @Test fun tenEnglishMeaningsStayCandidatesWithoutExecutableGlosses() {
        assertEquals(10, entries.size)
        EverydayAslExpression.validate(entries, AslTextNormalizer())
        for (entry in entries) assertEquals(entry.id, planner.plan(entry.english.first()).ruleId)
    }

    @Test fun weatherVariantsIdentifyOneMeaningWithoutDroppingWordsGlobally() {
        for (input in listOf("It is hot today.", "IT IS HOT TODAY", "It's hot today!", "Today is hot.",
                "  It’s   hot today!  ")) {
            val plan = planner.plan(input)
            assertEquals("everyday_hot_today", plan.ruleId)
            assertEquals(TextToAslPlan.Mode.BLOCKED_MEANING, plan.mode)
            assertTrue(plan.queue.isEmpty())
            assertTrue(plan.unsupportedTokens.isEmpty())
            assertTrue(plan.translationNotice!!.contains("phrase order and non-manual features"))
            assertTrue(plan.gloss.isEmpty())
        }
        for (differentMeaning in listOf("It is not hot today", "It might be hot today", "It was hot yesterday",
                "Is it hot today?", "Its hot today tomorrow")) {
            assertNull(planner.plan(differentMeaning).ruleId)
        }
    }

    @Test fun onlyCompleteExistingGreetingAndGratitudeClipsCanPreview() {
        assertEquals(listOf("hello"), planner.plan("Hello.").queue.map { it.id })
        assertEquals(listOf("thank_you"), planner.plan("THANK YOU!").queue.map { it.id })
        for (input in listOf("Hello.", "Thank you.")) {
            val plan = planner.plan(input)
            assertTrue(plan.translationNotice!!.contains("validation pending"))
            assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, plan.mode)
        }
        assertEquals(listOf("hello", "beautiful"), planner.plan("HELLO BEAUTIFUL").queue.map { it.id })
    }

    @Test fun incompleteSentencesStopInsteadOfSigningUnrelatedFragments() {
        for (input in listOf("How are you?", "What is your name?", "It is raining.", "I am hungry.",
                "I am tired.", "Can you help me?")) {
            val plan = planner.plan(input)
            assertTrue(input, plan.queue.isEmpty())
            assertEquals(input, TextToAslPlan.Mode.BLOCKED_MEANING, plan.mode)
            assertTrue(input, plan.translationNotice!!.contains("missing compatible signs"))
        }
    }

    @Test fun arbitraryNameIsCapturedWithoutInventingANameSignOrSpelling() {
        for (input in listOf("My name is...", "My name is Nicole", "MY NAME IS ANA-MARIA")) {
            val plan = planner.plan(input)
            assertEquals("everyday_my_name", plan.ruleId)
            assertTrue(plan.queue.isEmpty())
            assertTrue(plan.unsupportedTokens.contains("NAME FINGERSPELLING"))
        }
        assertNull(planner.plan("My namesake is Nicole").ruleId)
    }

    @Test fun letterIAndLegacyClipsCannotSatisfyPersonalPronounRequirement() {
        val letter = asset("letter_i", "i", AslAnimationAsset.Type.LETTER)
        val legacy = asset("me").copy(metadata = SignDictionaryMetadata())
        val p = AslTranslationPlanner(AslAnimationCatalog.fromAssets(listOf(letter, legacy)),
            AslGrammarRegistry(everydayExpressions = entries))
        assertTrue(p.plan("I'm hungry.").unsupportedTokens.contains("ME"))
        assertTrue(p.plan("Hello").queue.isEmpty())
    }

    @Test fun ambiguousInventoryIsRejectedBeforePlayback() {
        val duplicate = entries + entries.first().copy(id = "other_hello")
        assertTrue(runCatching { AslTranslationPlanner(catalog, AslGrammarRegistry(everydayExpressions = duplicate)) }.isFailure)
    }

    @Test fun unavailableMeaningRegistryStopsSentencesButKeepsSingleWordPreview() {
        val p = AslTranslationPlanner(catalog, AslGrammarRegistry(enabled = false, meaningRegistryUnavailable = true))
        assertTrue(p.plan("hello beautiful").queue.isEmpty())
        assertEquals(listOf("hello"), p.plan("hello").queue.map { it.id })
    }
}
