package com.example.apphear.domain.texttoasl

/** One active Text-to-Sign character. Saved alternate choices never change this engine. */
object AslSingleAvatarPolicy {
    val choice = AslCharacterChoice.ORIGINAL
    val profile = SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN

    fun permits(asset: AslAnimationAsset): Boolean = AslAvatarCatalogPolicy.permits(asset, profile)
}
