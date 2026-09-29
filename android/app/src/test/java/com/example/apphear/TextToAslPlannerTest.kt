package com.example.apphear

import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.example.apphear.domain.texttoasl.AslTextNormalizer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextToAslPlannerTest {
    private val hello = asset(
        id = "hello",
        display = "Hello",
        path = "asl_animations/hello.glb",
        type = AslAnimationAsset.Type.PHRASE,
        aliases = listOf("hello", "hi", "hey"),
    )
    private val niceToMeetYou = asset(
        id = "nice_to_meet_you",
        display = "Nice to meet you",
        path = "asl_animations/nice2meetU_final.glb",
        type = AslAnimationAsset.Type.PHRASE,
        aliases = listOf("nice to meet you", "nice meeting you", "meet you"),
    )
    private val meet = asset(
        id = "meet",
        display = "Meet",
        path = "asl_animations/MEET.glb",
        type = AslAnimationAsset.Type.PHRASE,
        aliases = listOf("meet"),
    )
    private val letterA = asset(
        id = "a",
        display = "A",
        path = "asl_animations/anim_a.glb",
        type = AslAnimationAsset.Type.LETTER,
        aliases = listOf("a"),
    )
    private val letterB = asset(
        id = "b",
        display = "B",
        path = "asl_animations/anim_b.glb",
        type = AslAnimationAsset.Type.LETTER,
        aliases = listOf("b"),
    )
    private val catalog = AslAnimationCatalog.fromAssets(
        listOf(hello, niceToMeetYou, meet, letterA, letterB),
    )
    private val planner = AslPhrasePlanner(catalog)

    @Test
    fun normalizerMatchesAppHear2ReferenceRules() {
        val normalizer = AslTextNormalizer()

        assertEquals("", normalizer.normalize(null))
        assertEquals("", normalizer.normalize("   "))
        assertEquals("hello", normalizer.normalize("HEY"))
        assertEquals("hello", normalizer.normalize("hi"))
        assertEquals("dont", normalizer.normalize("Don't"))
        assertEquals("nice to meet you", normalizer.normalize("Nice, to   meet you!"))
    }

    @Test
    fun plannerPrefersLongestAliasBeforeShorterAlias() {
        val plan = planner.plan("nice to meet you")

        assertEquals(listOf("nice_to_meet_you"), plan.queue.map { it.id })
        assertTrue(plan.unsupportedTokens.isEmpty())
    }

    @Test
    fun plannerFallsBackToLettersWhenNoPhraseMatches() {
        val plan = planner.plan("ab")

        assertEquals(listOf("a", "b"), plan.queue.map { it.id })
        assertTrue(plan.unsupportedTokens.isEmpty())
    }

    @Test
    fun plannerDoesNotPlayPartOfAnUnsupportedWord() {
        val plan = AslPhrasePlanner(catalog, completeWordFallback = true).plan("az")

        assertTrue(plan.queue.isEmpty())
        assertEquals(listOf("az"), plan.unsupportedTokens)
        assertFalse(plan.isPlayable)
        val mixed = AslPhrasePlanner(catalog, completeWordFallback = true).plan("hello cat")
        assertEquals(listOf("hello"), mixed.queue.map { it.id })
        assertEquals(listOf("cat"), mixed.unsupportedTokens)
    }

    @Test
    fun plannerReportsNoPlayableAssetsForUnsupportedInput() {
        val plan = AslPhrasePlanner(catalog, completeWordFallback = true).plan("zzz")

        assertTrue(plan.queue.isEmpty())
        assertEquals(listOf("zzz"), plan.unsupportedTokens)
        assertFalse(plan.isPlayable)
    }

    @Test
    fun separateLetterLookupSpellsUnknownWordWithoutHijackingPronounI() {
        val pronoun = asset("i_me", "I / Me", "asl_animations/i-me.glb",
            AslAnimationAsset.Type.WORD, listOf("i", "me"))
        val letters = "cit".associateWith { letter ->
            asset("letter_$letter", letter.uppercase(), "asl_animations/letter_$letter.glb",
                AslAnimationAsset.Type.LETTER, emptyList())
        }
        val full = AslPhrasePlanner(AslAnimationCatalog.fromAssets(
            listOf(hello, pronoun, letterA, letterB), letters,
        ), completeWordFallback = true)

        assertEquals(listOf("letter_c", "a", "letter_t"), full.plan("cat").queue.map { it.id })
        assertEquals(listOf("i_me"), full.plan("I").queue.map { it.id })
        assertEquals(listOf("letter_c", "letter_i", "letter_t"), full.plan("cit").queue.map { it.id })
        assertEquals(listOf("hello", "letter_c", "a", "letter_t"),
            full.plan("hello cat").queue.map { it.id })
        assertTrue(full.plan("hello cat").unsupportedTokens.isEmpty())
    }

    @Test
    fun completeAlphabetSpellsEveryLetterInOrder() {
        val letters = ('c'..'z').associateWith { letter ->
            asset("letter_$letter", letter.uppercase(), "asl_animations/letter_$letter.glb",
                AslAnimationAsset.Type.LETTER, emptyList())
        }
        val full = AslPhrasePlanner(AslAnimationCatalog.fromAssets(
            listOf(hello, letterA, letterB), letters,
        ), completeWordFallback = true)

        val plan = full.plan("abcdefghijklmnopqrstuvwxyz")
        assertEquals(listOf("a", "b") + ('c'..'z').map { "letter_$it" }, plan.queue.map { it.id })
        assertTrue(plan.unsupportedTokens.isEmpty())
    }

    @Test
    fun catalogValidatesMissingAssetPathsForManifestGate() {
        val missing = AslAnimationCatalog.validateAssetPaths(
            assets = listOf(hello, letterA, letterB),
            existingAssetPaths = setOf("asl_animations/hello.glb", "asl_animations/anim_a.glb"),
        )

        assertEquals(listOf("asl_animations/anim_b.glb"), missing)
    }

    @Test(expected = IllegalArgumentException::class)
    fun catalogRejectsAliasesThatWouldSilentlyReplaceAnotherAnimation() {
        AslAnimationCatalog.fromAssets(
            listOf(
                hello,
                asset(
                    id = "other_hello",
                    display = "Other hello",
                    path = "asl_animations/other-hello.glb",
                    type = AslAnimationAsset.Type.WORD,
                    aliases = listOf("hello"),
                ),
            ),
        )
    }

    private fun asset(
        id: String,
        display: String,
        path: String,
        type: AslAnimationAsset.Type,
        aliases: List<String>,
    ): AslAnimationAsset {
        return AslAnimationAsset(
            id = id,
            displayText = display,
            assetPath = path,
            type = type,
            aliases = aliases,
        )
    }
}

