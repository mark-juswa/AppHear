package com.example.apphear.domain.texttoasl

import java.util.Locale

class AslAnimationCatalog private constructor(
    private val assets: List<AslAnimationAsset>,
    private val aliasMap: Map<String, AslAnimationAsset>,
) {
    fun getAssets(): List<AslAnimationAsset> = assets

    fun findByAlias(alias: String): AslAnimationAsset? = aliasMap[normalizeAlias(alias)]

    fun getAliasesLongestFirst(): List<String> = aliasMap.keys.sortedByDescending { it.length }

    companion object {
        fun fromAssets(assets: List<AslAnimationAsset>): AslAnimationCatalog {
            val aliasMap = linkedMapOf<String, AslAnimationAsset>()
            val normalizedAssets = assets.map { asset ->
                asset.copy(
                    aliases = asset.aliases.map(::normalizeAlias).filter { it.isNotEmpty() }.distinct(),
                )
            }

            for (asset in normalizedAssets) {
                aliasMap[normalizeAlias(asset.id)] = asset
                aliasMap[normalizeAlias(asset.displayText)] = asset
                for (alias in asset.aliases) {
                    aliasMap[alias] = asset
                }
            }

            return AslAnimationCatalog(normalizedAssets.toList(), aliasMap.toMap())
        }

        fun validateAssetPaths(assets: List<AslAnimationAsset>, existingAssetPaths: Set<String>): List<String> {
            return assets
                .map { it.assetPath }
                .filterNot { existingAssetPaths.contains(it) }
                .distinct()
        }

        private fun normalizeAlias(text: String): String {
            return text
                .lowercase(Locale.US)
                .trim()
                .replace(Regex("\\s+"), " ")
        }
    }
}

