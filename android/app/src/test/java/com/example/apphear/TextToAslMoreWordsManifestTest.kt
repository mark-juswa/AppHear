package com.example.apphear

import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextToAslMoreWordsManifestTest {
    private val expanded = Path.of("src", "aslWords", "assets", "asl_animations", "vnext")
    private val original = Path.of("src", "main", "assets", "asl_animations", "manifest.json")
    private val root by lazy {
        JsonParser.parseString(String(Files.readAllBytes(expanded.resolve("manifest.json")))).asJsonObject
    }
    private val words by lazy { root.getAsJsonArray("newClips").map { it.asJsonObject } }

    @Test
    fun existingReplacementFallsBackButNewWordFailsClearly() {
        val original = AslAnimationAsset("all", "All", "asl_animations/vnext/shared-words.glb",
            AslAnimationAsset.Type.WORD, listOf("all"),
            AslAnimationAsset.Replacement("asl_animations/all.glb", "SIGN_ALL_FEMALEASL", 2367))
        assertEquals("asl_animations/all.glb", original.originalFallback()?.assetPath)
        assertEquals(null, original.originalFallback()?.replacement)
        val added = original.copy(id = "ask", replacement =
            AslAnimationAsset.Replacement(null, "SIGN_ASK_FEMALEASL", 2600))
        assertEquals(null, added.originalFallback())
    }

    @Test
    fun bundleContainsExactlyApprovedNamedClipsAndValidHashes() {
        assertEquals(2, root.get("schemaVersion").asInt)
        assertEquals(7, root.getAsJsonArray("clips").size())
        assertEquals(20, words.size)
        val bytes = Files.readAllBytes(expanded.resolve("shared-words.glb"))
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
        val header = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(0x46546c67, header.getInt(0))
        assertEquals(2, header.getInt(4))
        val gltf = JsonParser.parseString(String(bytes, 20, header.getInt(12))).asJsonObject
        val names = gltf.getAsJsonArray("animations").map { it.asJsonObject.get("name").asString }
        assertEquals(27, names.size)
        for (entry in root.getAsJsonArray("clips").map { it.asJsonObject } + words) {
            assertEquals(hash, entry.get("sha256").asString)
            assertEquals("asl_animations/vnext/shared-words.glb", entry.get("asset").asString)
            assertTrue(entry.get("animationName").asString in names)
            assertTrue(entry.get("durationMs").asLong in 1..10_000)
        }
        assertEquals(27, names.distinct().size)
    }

    @Test
    fun newPhrasesDoNotRemapPlainAmbiguousWordsOrOriginals() {
        val base = JsonParser.parseString(String(Files.readAllBytes(original))).asJsonObject
            .getAsJsonArray("clips").map { raw ->
                val clip = raw.asJsonObject
                AslAnimationAsset(
                    clip.get("id").asString, clip.get("displayText").asString,
                    clip.get("asset").asString,
                    AslAnimationAsset.Type.valueOf(clip.get("type").asString.uppercase()),
                    clip.getAsJsonArray("aliases").map { it.asString },
                )
            }
        val newAssets = words.map { clip ->
            AslAnimationAsset(
                clip.get("id").asString, clip.get("displayText").asString,
                clip.get("asset").asString, AslAnimationAsset.Type.WORD,
                clip.getAsJsonArray("aliases").map { it.asString },
            )
        }
        val catalog = AslAnimationCatalog.fromAssets(base + newAssets)
        val planner = AslPhrasePlanner(catalog)
        assertEquals(122, catalog.getAssets().size)
        assertEquals(listOf("big_horizontally", "call_by_phone", "call_someones_name", "pay_me"),
            planner.plan("big horizontally call by phone call someone's name pay me").queue.map { it.id })
        for (plain in listOf("big", "call", "pay")) {
            val ids = planner.plan(plain).queue.map { it.id }
            assertFalse(ids.any { it in setOf("big_horizontally", "call_by_phone", "call_someones_name", "pay_me") })
        }
        assertEquals("i_me", catalog.findByAlias("i")?.id)
        assertEquals("request", catalog.findByAlias("request")?.id)
        assertEquals("come_to_here", catalog.findByAlias("come to here")?.id)
        for (entry in words) {
            val phrase = entry.getAsJsonArray("aliases").single().asString
            assertEquals(entry.get("id").asString, planner.plan(phrase).queue.single().id)
        }
    }
}
