package com.example.apphear.domain.texttoasl

import java.util.Locale

class AslAnimationCatalog private constructor(
    private val assets: List<AslAnimationAsset>,
    private val aliasMap: Map<String, AslAnimationAsset>,
    private val letterMap: Map<Char, AslAnimationAsset>,
) {
    fun getAssets(): List<AslAnimationAsset> = assets

    fun findByAlias(alias: String): AslAnimationAsset? = aliasMap[normalizeAlias(alias)]

    fun findLetter(letter: Char): AslAnimationAsset? = letterMap[letter.lowercaseChar()]

    fun getAliasesLongestFirst(): List<String> = aliasMap.keys.sortedByDescending { it.length }

    companion object {
        fun fromAssets(
            assets: List<AslAnimationAsset>,
            fallbackLetters: Map<Char, AslAnimationAsset> = emptyMap(),
        ): AslAnimationCatalog {
            val aliasMap = linkedMapOf<String, AslAnimationAsset>()
            val normalizedAssets = assets.map { asset ->
                require(asset.id.isNotBlank()) { "ASL animation id must not be blank" }
                require(asset.assetPath.startsWith("asl_animations/") && asset.assetPath.endsWith(".glb")) {
                    "Invalid ASL animation asset path: ${asset.assetPath}"
                }
                asset.copy(
                    aliases = asset.aliases.map(::normalizeAlias).filter { it.isNotEmpty() }.distinct(),
                )
            }

            val duplicateIds = normalizedAssets.groupingBy { normalizeAlias(it.id) }
                .eachCount()
                .filterValues { it > 1 }
                .keys
            require(duplicateIds.isEmpty()) {
                "Duplicate ASL animation ids: ${duplicateIds.sorted().joinToString(", ")}"
            }

            for (asset in normalizedAssets) {
                registerAlias(aliasMap, asset.id, asset)
                registerAlias(aliasMap, asset.displayText, asset)
                for (alias in asset.aliases) {
                    registerAlias(aliasMap, alias, asset)
                }
            }
            val letterMap = normalizedAssets.filter { it.type == AslAnimationAsset.Type.LETTER }
                .filter { it.id.length == 1 && it.id[0] in 'a'..'z' }
                .associateBy { it.id[0] }.toMutableMap()
            for ((letter, asset) in fallbackLetters) {
                require(letter in 'a'..'z' && asset.type == AslAnimationAsset.Type.LETTER)
                require(asset.assetPath.startsWith("asl_animations/") && asset.assetPath.endsWith(".glb"))
                require(letter !in letterMap) { "Duplicate ASL fallback letter: $letter" }
                letterMap[letter] = asset
            }
            return AslAnimationCatalog(normalizedAssets.toList(), aliasMap.toMap(), letterMap.toMap())
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

        private fun registerAlias(
            aliasMap: MutableMap<String, AslAnimationAsset>,
            rawAlias: String,
            asset: AslAnimationAsset,
        ) {
            val alias = normalizeAlias(rawAlias)
            if (alias.isEmpty()) return

            val existing = aliasMap[alias]
            require(existing == null || existing.id == asset.id) {
                "Duplicate ASL alias '$alias' maps to both '${existing?.id}' and '${asset.id}'"
            }
            aliasMap[alias] = asset
        }
    }
}

