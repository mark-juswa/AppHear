package com.example.apphear.domain.texttoasl

/** Retargeted preview clips, not reviewed ASL lexical signs. All share the resident human. */
object AslFingerspellingBundle {
    const val BEFORE_INTEGRATION_SHA256 = "99dbd596f53c89a561cc517e8bc2f436dc737b3cc2001f4cfefaf89cc8a12963"
    const val ACTION_COUNT = 863
    const val PATH = "asl_animations/original_words_v1/fingerspelling-avatar.glb"
    const val MANIFEST = "asl_animations/original_words_v1/fingerspelling-avatar.json"
    const val SHA256 = "3601797dc5324851cf10d79290b4499f8d14fd8b200d8144c5f338530d52773c"
    data class Letter(val character: Char, val animationName: String, val durationMs: Long)

    /** Keep controller timeouts aligned with corrected glTF clocks, including aliases. */
    fun withDurations(assets: List<AslAnimationAsset>, overrides: Map<String, Long>,
                      paddingOverrides: Map<String, Double> = emptyMap()): List<AslAnimationAsset> {
        val known = assets.mapNotNull { it.replacement?.animationName }.toSet()
        require(overrides.keys.all { it in known }) { "Duration override references an unknown action" }
        require(overrides.values.all { it in 100..60_000 }) { "Invalid animation duration" }
        val lexical = assets.filter { it.type == AslAnimationAsset.Type.WORD || it.type == AslAnimationAsset.Type.PHRASE }
            .mapNotNull { it.replacement?.animationName }.toSet()
        require(paddingOverrides.keys.all { it in lexical }) { "Padding override requires a lexical action" }
        require(paddingOverrides.values.all { it.isFinite() && it in 0.0..1.0 }) { "Invalid synthetic padding" }
        return assets.map { asset ->
            val replacement = asset.replacement
            val duration = replacement?.animationName?.let(overrides::get)
            val padding = replacement?.animationName?.let(paddingOverrides::get)
            if (replacement == null || (duration == null && padding == null)) asset
            else {
                require(padding == null || padding * 2 < (duration ?: replacement.durationMs) / 1000.0) {
                    "Synthetic padding consumes the complete sign"
                }
                asset.copy(replacement = replacement.copy(durationMs = duration ?: replacement.durationMs),
                    syntheticPaddingSeconds = padding ?: asset.syntheticPaddingSeconds)
            }
        }
    }

    fun letters(entries: List<Letter>): Map<Char, AslAnimationAsset> {
        require(entries.size == 26 && entries.map { it.character }.toSet() == ('a'..'z').toSet())
        return entries.associate { e ->
            require(e.animationName == "SIGN_LETTER_${e.character.uppercaseChar()}_WOLF3D_PREVIEW")
            require(e.durationMs in 500..10_000)
            e.character to AslAnimationAsset("letter_${e.character}", "Letter ${e.character.uppercaseChar()}",
                PATH, AslAnimationAsset.Type.LETTER, emptyList(),
                AslAnimationAsset.Replacement(null, e.animationName, e.durationMs),
                SignDictionaryMetadata(avatarProfile = AslSingleAvatarPolicy.profile,
                    category = "Fingerspelling", source = "Existing AppHear FemaleASL alphabet; offline anatomical-frame retargeting",
                    license = "Existing motion provenance unresolved; no new redistribution rights asserted",
                    usageNotes = "Unreviewed retargeted alphabet preview; not a lexical sign",
                    references = listOf("https://www.lifeprint.com/asl101/fingerspelling/fingerspelling.htm")))
        }
    }
}
