package com.example.apphear.domain.texttoasl

/** Standalone Original assets only; NEW and the frozen base catalog never change. */
object OriginalWordBatchCatalog {
    const val MANIFEST = "asl_animations/original_words_v1/manifest.json"
    const val MANIFEST_SHA256 = "4c08af4d1257ebb0b85258cd52c99cd54f0c66233b095cab28174f8296d88717"
    const val PREFIX = "asl_animations/original_words_v1/"
    const val REPLACEMENTS = 32
    const val ADDITIONS = 171

    data class Override(
        val id: String,
        val assetPath: String,
        val fallbackAssetPath: String,
        val animationName: String,
        val durationMs: Long,
    )

    fun validatePath(path: String) {
        require(path.matches(Regex("asl_animations/original_words_v1/[a-z_]+\\.glb"))) {
            "Invalid Original word asset path"
        }
    }

    fun merge(
        base: List<AslAnimationAsset>,
        overrides: List<Override>,
        additions: List<AslAnimationAsset>,
    ): List<AslAnimationAsset> {
        require(overrides.size == REPLACEMENTS && additions.size == ADDITIONS)
        require(overrides.map { it.id }.distinct().size == REPLACEMENTS)
        val byId = base.associateBy { it.id }
        for (entry in overrides) {
            val original = requireNotNull(byId[entry.id])
            require(original.type in setOf(AslAnimationAsset.Type.WORD, AslAnimationAsset.Type.PHRASE))
            require(entry.fallbackAssetPath == original.assetPath)
            validatePath(entry.assetPath)
            require(entry.animationName.isNotBlank() && entry.durationMs in 1..10_000)
        }
        for (entry in additions) {
            require(entry.id !in byId && entry.id !in setOf("stand", "idle"))
            require(entry.type == AslAnimationAsset.Type.WORD && entry.aliases.isNotEmpty())
            require(entry.replacement != null && entry.replacement.fallbackAssetPath == null)
            require(entry.replacement.animationName.isNotBlank() && entry.replacement.durationMs in 1..10_000)
            validatePath(entry.assetPath)
        }
        val mapped = overrides.associateBy { it.id }
        val result = base.map { original ->
            mapped[original.id]?.let { entry ->
                original.copy(assetPath = entry.assetPath, replacement = AslAnimationAsset.Replacement(
                    original.assetPath, entry.animationName, entry.durationMs))
            } ?: original
        } + additions
        // Validate collisions before returning anything: never expose a partially added catalog.
        AslAnimationCatalog.fromAssets(result)
        require(result.single { it.id == "idle" } == byId["idle"])
        return result
    }
}
