package com.example.apphear.domain.texttoasl

/** An alternative input for an existing motion; never a new or newly validated sign. */
data class ExistingAslAlias(
    val signId: String,
    val english: List<String>,
    val assetPath: String,
    val sha256: String,
    val reference: String,
) {
    fun apply(base: List<AslAnimationAsset>, actualHash: String): List<AslAnimationAsset> {
        require(sha256.matches(Regex("[a-f0-9]{64}")) && actualHash == sha256)
        require(reference.startsWith("https://"))
        val asset = requireNotNull(base.find { it.id == signId })
        require(AslSingleAvatarPolicy.permits(asset) && asset.assetPath == assetPath)
        require(asset.type == AslAnimationAsset.Type.WORD || asset.type == AslAnimationAsset.Type.PHRASE)
        val forms = english.map(AslTextNormalizer()::normalizeSequence)
        require(forms.isNotEmpty() && forms.all { it.isNotBlank() })
        val result = base.map { if (it.id == signId) it.copy(aliases = (it.aliases + forms).distinct()) else it }
        AslAnimationCatalog.fromAssets(result) // Reject conflicts with IDs, display text and existing aliases.
        return result
    }
}
