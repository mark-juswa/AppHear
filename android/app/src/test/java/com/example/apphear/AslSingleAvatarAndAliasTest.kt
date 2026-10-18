package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import org.junit.Assert.*
import org.junit.Test

class AslSingleAvatarAndAliasTest {
    private val hash = "a".repeat(64)
    private val bye = AslAnimationAsset("bye", "Bye", "asl_animations/original_words_v1/bye.glb",
        AslAnimationAsset.Type.WORD, listOf("bye"), metadata = SignDictionaryMetadata(
            avatarProfile = SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN))
    private val alias = ExistingAslAlias("bye", listOf("goodbye"), bye.assetPath, hash, "https://example.org/reference")

    @Test fun oneActivePolicyRejectsEveryOtherRig() {
        assertEquals(AslCharacterChoice.ORIGINAL, AslSingleAvatarPolicy.choice)
        assertTrue(AslSingleAvatarPolicy.permits(bye))
        for (profile in SignDictionaryMetadata.AvatarProfile.entries.filter { it != AslSingleAvatarPolicy.profile }) {
            assertFalse(AslSingleAvatarPolicy.permits(bye.copy(metadata = bye.metadata.copy(avatarProfile = profile))))
        }
    }

    @Test fun alternativeInputKeepsSameAssetAndUnreviewedMetadata() {
        val expanded = alias.apply(listOf(bye), hash)
        assertEquals(1, expanded.size)
        assertEquals(bye.assetPath, expanded.single().assetPath)
        assertEquals(bye.metadata, expanded.single().metadata)
        assertFalse(expanded.single().metadata.isLinguisticallyValidated)
        val planner = AslPhrasePlanner(AslAnimationCatalog.fromAssets(expanded), dictionarySequenceMode = true)
        assertEquals(listOf("bye"), planner.plan("GOODBYE!").queue.map { it.id })
        assertEquals(listOf("bye"), planner.plan("bye").queue.map { it.id })
    }

    @Test fun staleHashWrongPathMissingSignAndOtherRigCannotAddAnAlias() {
        for (invalid in listOf(alias.copy(sha256 = "b".repeat(64)), alias.copy(assetPath = "asl_animations/wrong.glb"),
                alias.copy(signId = "name"))) {
            assertTrue(runCatching { invalid.apply(listOf(bye), hash) }.isFailure)
        }
        val other = bye.copy(metadata = bye.metadata.copy(avatarProfile = SignDictionaryMetadata.AvatarProfile.NEW_HUMAN))
        assertTrue(runCatching { alias.apply(listOf(other), hash) }.isFailure)
    }

    @Test fun lettersPosesAndConflictingMeaningsCannotBeAliased() {
        for (type in listOf(AslAnimationAsset.Type.LETTER, AslAnimationAsset.Type.POSE)) {
            assertTrue(runCatching { alias.apply(listOf(bye.copy(type = type)), hash) }.isFailure)
        }
        val unrelated = bye.copy(id = "other", displayText = "Goodbye", aliases = listOf("other"))
        assertTrue(runCatching { alias.apply(listOf(bye, unrelated), hash) }.isFailure)
    }
}
