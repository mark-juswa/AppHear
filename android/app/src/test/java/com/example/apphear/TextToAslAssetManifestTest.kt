package com.example.apphear

import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextToAslAssetManifestTest {
    @Test
    fun smokeManifestOnlyReferencesBundledAssets() {
        val assetsDir = Path.of("src", "main", "assets")
        val manifestPath = assetsDir.resolve(Path.of("asl_animations", "manifest.json"))
        val manifest = JsonParser.parseString(String(Files.readAllBytes(manifestPath))).asJsonObject
        val clips = manifest.getAsJsonArray("clips")

        assertTrue("Smoke manifest should include at least one clip", clips.size() > 0)
        for (clip in clips) {
            val assetPath = clip.asJsonObject.get("asset").asString
            assertTrue(
                "Missing Text-to-ASL asset referenced by manifest: $assetPath",
                Files.exists(assetsDir.resolve(assetPath.replace('/', java.io.File.separatorChar))),
            )
        }
    }

    @Test
    fun modelViewerHtmlUsesLocalVendoredScriptOnly() {
        val viewerHtml = String(Files.readAllBytes(Path.of("src", "main", "assets", "model_viewer.html")))

        assertTrue(viewerHtml.contains("vendor/model-viewer/model-viewer-4.3.1.min.js"))
        assertFalse("Viewer must not depend on AppHear2's runtime CDN script", viewerHtml.contains("unpkg.com"))
        assertFalse("Viewer must not depend on a runtime Google CDN script", viewerHtml.contains("ajax.googleapis.com"))
    }
}