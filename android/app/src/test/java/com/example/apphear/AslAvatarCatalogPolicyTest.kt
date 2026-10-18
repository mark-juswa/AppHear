package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import org.junit.Assert.*
import org.junit.Test

class AslAvatarCatalogPolicyTest {
    private fun asset(id: String, path: String) = AslAnimationAsset(id, id, path,
        AslAnimationAsset.Type.WORD, listOf(id),
        AslAnimationAsset.Replacement("asl_animations/$id.glb", "SIGN_$id", 2_000))
    @Test fun originalHumanExcludesLegacyAndProvidesSampledNeutral() {
        val selected = AslAvatarCatalogPolicy.originalHuman(listOf(
            asset("hello", OriginalWordBatchCatalog.PREFIX + "hello.glb"),
            asset("beautiful", OriginalWordBatchCatalog.PREFIX + "beautiful.glb"),
            asset("legacy", "asl_animations/legacy.glb")))
        assertEquals(listOf("hello", "beautiful", "idle"), selected.map { it.id })
        assertTrue(selected.all { it.originalFallback() == null })
        assertTrue(selected.all { AslAvatarCatalogPolicy.permits(it, SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN) })
        assertEquals(0.0, selected.last().neutralFrameSeconds)
        assertEquals(AslAnimationAsset.Type.POSE, selected.last().type)
        assertEquals(SignDictionaryMetadata.ValidationStatus.UNREVIEWED, selected.first().metadata.validationStatus)
    }
    @Test fun newCharacterExcludesLegacyAndCannotPlayAnotherProfile() {
        val selected = AslAvatarCatalogPolicy.newHuman(listOf(
            asset("beautiful", "asl_animations/vnext/shared-alphabet.glb"),
            asset("idle", "asl_animations/vnext/shared-alphabet.glb"),
            asset("hello", "asl_animations/hello.glb")))
        assertEquals(listOf("beautiful", "idle"), selected.map { it.id })
        assertTrue(selected.all { it.originalFallback() == null })
        assertFalse(AslAvatarCatalogPolicy.permits(selected.first(), SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN))
    }
    @Test fun missingNeutralFailsInsteadOfFallingBack() {
        assertThrows(IllegalArgumentException::class.java) { AslAvatarCatalogPolicy.originalHuman(emptyList()) }
        assertThrows(IllegalArgumentException::class.java) { AslAvatarCatalogPolicy.newHuman(emptyList()) }
    }
}
