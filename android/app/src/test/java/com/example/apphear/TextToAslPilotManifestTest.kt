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
import org.junit.Assert.assertTrue
import org.junit.Test

class TextToAslPilotManifestTest {
    private val pilot = Path.of("src", "aslPilot", "assets")
    private val original = Path.of("src", "main", "assets")
    private fun readText(path: Path) = String(Files.readAllBytes(path))
    private fun clips() = JsonParser.parseString(
        readText(pilot.resolve("asl_animations/vnext/manifest.json")),
    ).asJsonObject.getAsJsonArray("clips").map { it.asJsonObject }

    @Test
    fun pilotFilesMatchHashesAndNamedAnimationsWithExistingFallbacks() {
        val entries = clips()
        assertEquals(setOf("a", "b", "family", "all", "brother", "child", "city"),
            entries.map { it.get("id").asString }.toSet())
        assertEquals(7, entries.size)
        for (entry in entries) {
            assertEquals(entry.get("id").asString.uppercase(), entry.get("sourceId").asString)
            val bytes = Files.readAllBytes(pilot.resolve(entry.get("asset").asString))
            val actual = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            assertEquals(entry.get("sha256").asString, actual)
            val header = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
            assertEquals(0x46546c67, header.getInt(0))
            assertEquals(2, header.getInt(4))
            val json = JsonParser.parseString(String(bytes, 20, header.getInt(12))).asJsonObject
            assertTrue(json.getAsJsonArray("animations").any {
                it.asJsonObject.get("name").asString == entry.get("animationName").asString
            })
            assertTrue(Files.exists(original.resolve(entry.get("fallbackAsset").asString)))
            assertTrue(entry.get("durationMs").asLong in 1..10_000)
            assertTrue(bytes.size < 13 * 1024 * 1024)
        }
    }

    @Test
    fun replacementKeepsVocabularyAndPronounIPlanning() {
        val replacements = clips().associateBy { it.get("id").asString }
        val base = JsonParser.parseString(readText(original.resolve("asl_animations/manifest.json")))
            .asJsonObject.getAsJsonArray("clips").map { raw ->
                val c = raw.asJsonObject
                AslAnimationAsset(c.get("id").asString, c.get("displayText").asString,
                    c.get("asset").asString, AslAnimationAsset.Type.valueOf(c.get("type").asString.uppercase()),
                    c.getAsJsonArray("aliases").map { it.asString })
            }
        val overlaid = base.map { asset ->
            replacements[asset.id]?.let { asset.copy(assetPath = it.get("asset").asString) } ?: asset
        }
        val before = AslAnimationCatalog.fromAssets(base)
        val after = AslAnimationCatalog.fromAssets(overlaid)
        assertEquals(before.getAliasesLongestFirst(), after.getAliasesLongestFirst())
        val oldPlan = AslPhrasePlanner(before).plan("a b family i hello")
        val newPlan = AslPhrasePlanner(after).plan("a b family i hello")
        assertEquals(oldPlan.queue.map { it.id }, newPlan.queue.map { it.id })
        assertEquals(before.findByAlias("i"), after.findByAlias("i"))
        assertEquals(102, after.getAssets().size)
        for (id in listOf("all", "brother", "child", "city")) {
            assertEquals("asl_animations/vnext/$id.glb", after.findByAlias(id)?.assetPath)
        }
        assertEquals(before.findByAlias("whole"), after.findByAlias("whole"))
        assertEquals(before.findByAlias("come to here"), after.findByAlias("come to here"))
    }

    @Test
    fun pilotHasLocalDecodersAndLeavesOriginalPlayerUnmodified() {
        val page = readText(pilot.resolve("model_viewer_pilot.html"))
        assertTrue(page.contains("vendor/asl-decoders/meshopt_decoder.js"))
        assertTrue(page.contains("vendor/asl-decoders/basis/"))
        for (file in listOf("meshopt_decoder.js", "basis/basis_transcoder.js", "basis/basis_transcoder.wasm")) {
            assertTrue(Files.size(pilot.resolve("vendor/asl-decoders/$file")) > 0)
        }
        assertTrue(readText(original.resolve("model_viewer.html")).contains("const loadedUrls = new Set()"))
    }
}
