package com.example.apphear

import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.ui.texttoasl.AslIdlePilotContract
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TextToAslIdleTest {
    private val original = AslAnimationAsset("idle", "Idle", "asl_animations/asl_idle.glb",
        AslAnimationAsset.Type.POSE, listOf("idle", "rest", "stand"))
    private val hash = "a".repeat(64)

    private fun validate(
        enabled: Boolean = true,
        originalAsset: AslAnimationAsset = original,
        type: String = "pose",
        path: String = AslIdlePilotContract.ASSET,
        animation: String = AslIdlePilotContract.ANIMATION,
        duration: Long = 6_000L,
        fallback: String = original.assetPath,
        declaredHash: String = hash,
        actualHash: String = hash,
    ) = AslIdlePilotContract.validate(enabled, originalAsset, "idle", "IDLE", type,
        path, AslIdlePilotContract.PROFILE, "FemaleASL-full-rig-341-875-342",
        animation, duration, fallback, declaredHash, actualHash)

    private fun rejected(action: () -> Unit) {
        assertTrue(runCatching(action).exceptionOrNull() is IllegalArgumentException)
    }

    @Test
    fun approvedIdleRetainsLoopTypeAliasesAndOriginalFallback() {
        validate()
        val replacement = original.copy(assetPath = AslIdlePilotContract.ASSET,
            replacement = AslAnimationAsset.Replacement(original.assetPath, AslIdlePilotContract.ANIMATION, 6_000L))
        assertEquals(AslAnimationAsset.Type.POSE, replacement.type)
        assertEquals(original.aliases, replacement.aliases)
        assertEquals(original, replacement.originalFallback())
    }

    @Test
    fun disabledPilotAndUnrelatedPosesAreRejected() {
        rejected { validate(enabled = false) }
        rejected { validate(originalAsset = original.copy(id = "other")) }
        rejected { validate(originalAsset = original.copy(type = AslAnimationAsset.Type.WORD)) }
        rejected { validate(type = "word") }
    }

    @Test
    fun wrongSourceClipDurationFallbackAndCorruptedHashAreRejected() {
        rejected { validate(path = "asl_animations/vnext/shared-words.glb") }
        rejected { validate(animation = "SIGN_LETTER_A_FEMALEASL") }
        rejected { validate(duration = 0) }
        rejected { validate(duration = 6_001) }
        rejected { validate(fallback = "asl_animations/a.glb") }
        rejected { validate(actualHash = "b".repeat(64)) }
        rejected { validate(declaredHash = "invalid", actualHash = "invalid") }
    }

    @Test
    fun derivativeManifestPreservesVocabularyAndMapsIdleAndSignsToOneBundle() {
        val dir = Path.of("src", "aslIdle", "assets", "asl_animations", "vnext")
        val root = JsonParser.parseString(String(Files.readAllBytes(dir.resolve("manifest.json")))).asJsonObject
        assertEquals(2, root.get("schemaVersion").asInt)
        val signs = root.getAsJsonArray("clips").map { it.asJsonObject } +
            root.getAsJsonArray("newClips").map { it.asJsonObject }
        assertEquals(27, signs.size)
        val idle = root.getAsJsonObject("idle")
        val bundleHash = MessageDigest.getInstance("SHA-256")
            .digest(Files.readAllBytes(dir.resolve("shared-words-idle.glb")))
            .joinToString("") { "%02x".format(it) }
        AslIdlePilotContract.validate(true, original, idle.get("id").asString,
            idle.get("sourceId").asString, idle.get("type").asString, idle.get("asset").asString,
            idle.get("profile").asString, idle.get("rigProfile").asString,
            idle.get("animationName").asString, idle.get("durationMs").asLong,
            idle.get("fallbackAsset").asString, idle.get("sha256").asString, bundleHash)
        for (sign in signs) {
            assertEquals(AslIdlePilotContract.ASSET, sign.get("asset").asString)
            assertEquals(AslIdlePilotContract.PROFILE, sign.get("profile").asString)
            assertEquals(bundleHash, sign.get("sha256").asString)
        }
        val baseline = JsonParser.parseString(String(Files.readAllBytes(Path.of("src", "aslWords", "assets",
            "asl_animations", "vnext", "manifest.json")))).asJsonObject
        val baselineSigns = baseline.getAsJsonArray("clips").map { it.asJsonObject } +
            baseline.getAsJsonArray("newClips").map { it.asJsonObject }
        for ((index, sign) in signs.withIndex()) {
            for ((key, value) in baselineSigns[index].entrySet()) {
                if (key !in setOf("asset", "profile", "sha256")) assertEquals(value, sign.get(key))
            }
        }
    }
}
