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
    fun plannerReportsUnsupportedLettersWithoutPretendingPlaybackExists() {
        val plan = planner.plan("az")

        assertEquals(listOf("a"), plan.queue.map { it.id })
        assertEquals(listOf("z"), plan.unsupportedTokens)
        assertTrue(plan.isPlayable)
    }

    @Test
    fun plannerReportsNoPlayableAssetsForUnsupportedInput() {
        val plan = planner.plan("zzz")

        assertTrue(plan.queue.isEmpty())
        assertEquals(listOf("z", "z", "z"), plan.unsupportedTokens)
        assertFalse(plan.isPlayable)
    }

    @Test
    fun catalogValidatesMissingAssetPathsForManifestGate() {
        val missing = AslAnimationCatalog.validateAssetPaths(
            assets = listOf(hello, letterA, letterB),
            existingAssetPaths = setOf("asl_animations/hello.glb", "asl_animations/anim_a.glb"),
        )

        assertEquals(listOf("asl_animations/anim_b.glb"), missing)
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

