package com.example.apphear

import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextToAslAssetManifestTest {
    private val assetsDir = Path.of("src", "main", "assets")
    private val animationDir = assetsDir.resolve("asl_animations")
    private val manifestPath = animationDir.resolve("manifest.json")

    @Test
    fun manifestReferencesEveryBundledGlbExactlyOnce() {
        val clips = readClips()
        val referenced = clips.map { it.get("asset").asString }.toSet()
        val bundled = Files.newDirectoryStream(animationDir, "*.glb").use { paths ->
            paths.map { "asl_animations/${it.fileName}" }.toSet()
        }

        assertEquals("Every bundled GLB must have one catalog entry", bundled, referenced)
        assertEquals("Manifest paths must be unique", clips.size, referenced.size)
        assertEquals("Expanded Text-to-ASL catalog size changed unexpectedly", 102, clips.size)
    }

    @Test
    fun expandedManifestHasNoAliasOrIdCollisions() {
        val assets = readClips().map { clip ->
            AslAnimationAsset(
                id = clip.get("id").asString,
                displayText = clip.get("displayText").asString,
                assetPath = clip.get("asset").asString,
                type = AslAnimationAsset.Type.valueOf(clip.get("type").asString.uppercase()),
                aliases = clip.getAsJsonArray("aliases").map { it.asString },
            )
        }

        val catalog = AslAnimationCatalog.fromAssets(assets)

        assertEquals(102, catalog.getAssets().size)
        assertEquals("how_are_you", catalog.findByAlias("how are you")?.id)
        assertEquals("well", catalog.findByAlias("well")?.id)
        assertEquals("good", catalog.findByAlias("good")?.id)
        assertEquals("entire_whole", catalog.findByAlias("whole")?.id)
        assertEquals("all", catalog.findByAlias("all")?.id)
    }

    @Test
    fun everyCatalogGlbIsVersionTwoAndContainsAnimationData() {
        for (clip in readClips()) {
            val assetPath = clip.get("asset").asString
            val glbPath = assetsDir.resolve(assetPath.replace('/', java.io.File.separatorChar))
            assertTrue("Missing Text-to-ASL asset referenced by manifest: $assetPath", Files.exists(glbPath))
            val json = readGlbJson(glbPath)

            assertTrue("Text-to-ASL GLB has no animation: $assetPath", (json.getAsJsonArray("animations")?.size() ?: 0) > 0)
            assertTrue("Text-to-ASL GLB has no avatar nodes: $assetPath", (json.getAsJsonArray("nodes")?.size() ?: 0) > 0)
            assertEquals(clip.get("animationName").asString,
                json.getAsJsonArray("animations")[0].asJsonObject.get("name").asString)
            assertEquals("unreviewed", clip.getAsJsonObject("validation").get("status").asString)
        }
    }

    @Test
    fun modelViewerHtmlUsesLocalVendoredScriptAndCompletionEvents() {
        val viewerHtml = String(Files.readAllBytes(assetsDir.resolve("model_viewer.html")))

        assertTrue(viewerHtml.contains("vendor/model-viewer/model-viewer-4.3.1.min.js"))
        assertTrue(viewerHtml.contains("onPlaybackFinished"))
        assertFalse("Viewer must not depend on AppHear2's runtime CDN script", viewerHtml.contains("unpkg.com"))
        assertFalse("Viewer must not depend on a runtime Google CDN script", viewerHtml.contains("ajax.googleapis.com"))
    }

    private fun readClips(): List<JsonObject> {
        val manifest = JsonParser.parseString(String(Files.readAllBytes(manifestPath))).asJsonObject
        return manifest.getAsJsonArray("clips").map { it.asJsonObject }
    }

    private fun readGlbJson(path: Path): JsonObject {
        RandomAccessFile(path.toFile(), "r").use { file ->
            val header = ByteArray(GLB_HEADER_BYTES)
            file.readFully(header)
            val headerBuffer = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN)
            val magic = headerBuffer.int
            val version = headerBuffer.int
            val declaredLength = headerBuffer.int.toLong() and 0xffffffffL
            val jsonLength = headerBuffer.int
            val jsonChunkType = headerBuffer.int

            assertEquals("Invalid GLB magic: $path", GLB_MAGIC, magic)
            assertEquals("Unsupported GLB version: $path", 2, version)
            assertEquals("GLB length mismatch: $path", file.length(), declaredLength)
            assertEquals("First GLB chunk is not JSON: $path", JSON_CHUNK_TYPE, jsonChunkType)
            assertTrue("Invalid GLB JSON chunk length: $path", jsonLength > 0 && jsonLength < file.length())

            val jsonBytes = ByteArray(jsonLength)
            file.readFully(jsonBytes)
            val jsonText = String(jsonBytes, StandardCharsets.UTF_8).trimEnd(' ', '\u0000')
            return JsonParser.parseString(jsonText).asJsonObject
        }
    }

    private companion object {
        const val GLB_HEADER_BYTES = 20
        const val GLB_MAGIC = 0x46546C67
        const val JSON_CHUNK_TYPE = 0x4E4F534A
    }
}