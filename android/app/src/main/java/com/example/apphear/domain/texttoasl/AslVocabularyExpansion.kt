package com.example.apphear.domain.texttoasl

/** Sourced, retargeted previews only; never upgrades phrase/linguistic validation. */
object AslVocabularyExpansion {
    data class Word(
        val id: String,
        val english: List<String>,
        val animationName: String,
        val durationMs: Long,
        val sourceAsset: String,
        val sourceSha256: String,
        val reference: String,
        val meaning: String,
        val license: String,
        val variantOf: String? = null,
    )

    fun merge(base: List<AslAnimationAsset>, words: List<Word>): List<AslAnimationAsset> {
        val additions = words.map { word ->
            require(word.id.matches(Regex("[a-z][a-z_]*")))
            require(word.english.isNotEmpty() && word.english.all { it.isNotBlank() })
            if (word.variantOf == null) {
                require(word.animationName == "SIGN_${word.id.uppercase(java.util.Locale.US)}_HUMAN_RETARGETED_PREVIEW")
            } else {
                // The documented NAME/NAMED form reuses one existing motion, not a generated pose.
                require(word.id == "name" && word.variantOf == "call_someones_name")
                val original = requireNotNull(base.singleOrNull { it.id == word.variantOf })
                val motion = requireNotNull(original.replacement)
                require(original.type == AslAnimationAsset.Type.WORD && motion.animationName == word.animationName &&
                    motion.durationMs == word.durationMs)
            }
            require(word.durationMs in 500..10_000 && word.meaning.isNotBlank())
            require(word.sourceAsset.matches(Regex("asl_animations/(?:[a-z0-9_]+/)*[a-z_-]+\\.glb")))
            require(word.sourceSha256.matches(Regex("[a-f0-9]{64}")))
            require(word.reference.startsWith("https://") && word.license.isNotBlank())
            AslAnimationAsset(word.id, word.english.first(), AslFingerspellingBundle.PATH,
                AslAnimationAsset.Type.WORD, word.english,
                AslAnimationAsset.Replacement(null, word.animationName, word.durationMs),
                SignDictionaryMetadata(avatarProfile = AslSingleAvatarPolicy.profile,
                    source = word.sourceAsset, license = word.license, meaning = word.meaning,
                    references = listOf(word.reference), category = "Everyday communication",
                    usageNotes = if (word.variantOf == null) "Unreviewed retargeted sign preview; not validated ASL translation"
                        else "Unreviewed NAME/NAMED form preview from existing motion; contact repetition and meaning require ASL review",
                    status = SignDictionaryMetadata.Status.MAPPED))
        }
        require((base + additions).all(AslSingleAvatarPolicy::permits))
        AslAnimationCatalog.fromAssets(base + additions) // Reject ID and alias collisions atomically.
        return base + additions
    }
}
