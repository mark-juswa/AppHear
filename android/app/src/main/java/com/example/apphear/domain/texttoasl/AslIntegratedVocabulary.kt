package com.example.apphear.domain.texttoasl

/** Same-rig licensed motion additions. Technical mapping never implies ASL validation. */
object AslIntegratedVocabulary {
    const val MANIFEST = "asl_animations/original_words_v1/integration-manifest.json"
    const val MANIFEST_SHA256 = "a949a1cb658bd2dc5ec75110caaf20d0ca708356b2b444312a676c0f388faf1e"
    const val ENTRIES = 785
    const val ADDITIONS = 527
    data class Word(val id: String, val english: List<String>, val animation: String,
        val durationMs: Long, val sourceSha256: String, val motionSha256: String)
    data class Alias(val signId: String, val english: List<String>)

    fun merge(base: AslAnimationCatalog, words: List<Word>, aliases: List<Alias>): AslAnimationCatalog {
        require(base.getAssets().count { it.type != AslAnimationAsset.Type.POSE } == 258)
        require(words.size == ADDITIONS && words.map { it.id }.distinct().size == ADDITIONS)
        val additions = words.map { w ->
            require(w.id.matches(Regex("[a-z]+")) && w.english.isNotEmpty())
            require(w.animation == "SIGN_${w.id.uppercase(java.util.Locale.US)}_3DLEX_ASL_PREVIEW")
            require(w.durationMs in 500..12_500)
            require(listOf(w.sourceSha256, w.motionSha256).all { it.matches(Regex("[a-f0-9]{64}")) })
            AslAnimationAsset(w.id, w.english.first(), AslFingerspellingBundle.PATH,
                AslAnimationAsset.Type.WORD, w.english,
                AslAnimationAsset.Replacement(null, w.animation, w.durationMs),
                SignDictionaryMetadata(avatarProfile = AslSingleAvatarPolicy.profile,
                    source = "3D-LEX v1.0 ASL Animation Data: ANIM_GLB/${w.id}.glb",
                    license = "CC-BY-4.0; see packaged 3DLEX_ATTRIBUTION.md. Existing avatar rights remain separate.",
                    meaning = w.id, category = "Licensed ASL lexical preview",
                    references = listOf("https://osf.io/mqzyk/", "https://aclanthology.org/2024.signlang-1.33/"),
                    usageNotes = "Unreviewed retargeted lexical preview; facial grammar and sentence translation require ASL review",
                    status = SignDictionaryMetadata.Status.MAPPED),
                syntheticPaddingSeconds = 0.2)
        }
        var result = base.getAssets() + additions
        AslAnimationCatalog.fromAssets(result) // Fail atomically on ID/input collisions.
        for (alias in aliases) {
            require(alias.english.isNotEmpty() && alias.english.all(String::isNotBlank))
            val old = result.single { it.id == alias.signId }
            require(old.type != AslAnimationAsset.Type.POSE)
            result = result.map { if (it.id == old.id) it.copy(aliases = (it.aliases + alias.english).distinct()) else it }
        }
        require(result.all(AslSingleAvatarPolicy::permits))
        require(result.count { it.type != AslAnimationAsset.Type.POSE } == ENTRIES)
        val letters = ('a'..'z').associateWith { requireNotNull(base.findLetter(it)) }
        return AslAnimationCatalog.fromAssets(result, letters)
    }
}
