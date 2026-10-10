package com.example.apphear.domain.texttoasl

/** Retargeted preview clips, not reviewed ASL lexical signs. All share the resident human. */
object AslFingerspellingBundle {
    const val PATH = "asl_animations/original_words_v1/fingerspelling-avatar.glb"
    const val MANIFEST = "asl_animations/original_words_v1/fingerspelling-avatar.json"
    const val SHA256 = "bcd0e4b634b267baf3979f3193958520469ba91f69cd265406b76e9873d07d11"
    data class Letter(val character: Char, val animationName: String, val durationMs: Long)

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
