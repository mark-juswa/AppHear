package com.example.apphear.ui.texttoasl

import android.content.Context
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.Locale

class AndroidAssetAslCatalogLoader(
    private val context: Context,
) {
    fun load(): AslAnimationCatalog {
        val manifest = readAssetText(MANIFEST_PATH)
        val root = JSONObject(manifest)
        val clips = root.getJSONArray("clips")
        val assets = buildList {
            for (index in 0 until clips.length()) {
                val clip = clips.getJSONObject(index)
                val assetPath = clip.getString("asset")
                validateAssetExists(assetPath)
                val aliases = clip.getJSONArray("aliases")
                add(
                    AslAnimationAsset(
                        id = clip.getString("id"),
                        displayText = clip.getString("displayText"),
                        assetPath = assetPath,
                        type = parseType(clip.getString("type")),
                        aliases = buildList {
                            for (aliasIndex in 0 until aliases.length()) {
                                add(aliases.getString(aliasIndex))
                            }
                        },
                    ),
                )
            }
        }
        return AslAnimationCatalog.fromAssets(assets)
    }

    private fun readAssetText(path: String): String {
        return context.assets.open(path).use { input ->
            BufferedReader(InputStreamReader(input)).use { reader ->
                reader.readText()
            }
        }
    }

    private fun validateAssetExists(path: String) {
        context.assets.open(path).use { }
    }

    private fun parseType(rawType: String): AslAnimationAsset.Type {
        return when (rawType.lowercase(Locale.US)) {
            "phrase" -> AslAnimationAsset.Type.PHRASE
            "word" -> AslAnimationAsset.Type.WORD
            "letter" -> AslAnimationAsset.Type.LETTER
            "pose" -> AslAnimationAsset.Type.POSE
            else -> AslAnimationAsset.Type.PHRASE
        }
    }

    private companion object {
        const val MANIFEST_PATH = "asl_animations/manifest.json"
    }
}