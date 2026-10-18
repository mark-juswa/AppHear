package com.example.apphear.domain.texttoasl

/** Each selected catalog exposes only assets for its character. No retargeting. */
object AslAvatarCatalogPolicy {
    fun originalHuman(assets: List<AslAnimationAsset>): List<AslAnimationAsset> {
        val human = assets.filter { it.assetPath.startsWith(OriginalWordBatchCatalog.PREFIX) }
            .map { it.copy(replacement = it.replacement?.copy(fallbackAssetPath = null), metadata = it.metadata.copy(
                avatarProfile = SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN,
                source = OriginalWordBatchCatalog.MANIFEST)) }
        val hello = requireNotNull(human.find { it.id == "hello" }) { "Human HELLO asset missing" }
        // Sample the existing clip's initial resting frame; never play HELLO as idle.
        val neutral = hello.copy(id = "idle", displayText = "Neutral", type = AslAnimationAsset.Type.POSE,
            aliases = listOf("idle", "stand"), neutralFrameSeconds = 0.0)
        return human + neutral
    }

    fun newHuman(assets: List<AslAnimationAsset>): List<AslAnimationAsset> = assets
        .filter { it.assetPath.startsWith("asl_animations/vnext/") && it.replacement != null }
        .map { it.copy(replacement = it.replacement?.copy(fallbackAssetPath = null), metadata = it.metadata.copy(
            avatarProfile = SignDictionaryMetadata.AvatarProfile.NEW_HUMAN,
            source = "asl_animations/vnext/manifest.json")) }
        .also { require(it.any { asset -> asset.id == "idle" }) { "New neutral asset unavailable" } }

    fun permits(asset: AslAnimationAsset, profile: SignDictionaryMetadata.AvatarProfile): Boolean =
        profile != SignDictionaryMetadata.AvatarProfile.LEGACY && asset.metadata.avatarProfile == profile
}
