package com.example.apphear.domain.texttoasl

class AslTranslationPlanner(
    private val catalog: AslAnimationCatalog,
    private val registry: AslGrammarRegistry = AslGrammarRegistry(),
    private val wordPlanner: AslPhrasePlanner = AslPhrasePlanner(catalog, completeWordFallback = true, dictionarySequenceMode = true),
    private val normalizer: AslTextNormalizer = AslTextNormalizer(),
) {
    private val assets = catalog.getAssets().associateBy { it.id }
    private val everydayByEnglish = linkedMapOf<String, EverydayAslExpression>().also { aliases ->
        EverydayAslExpression.validate(registry.everydayExpressions, normalizer)
        for (entry in registry.everydayExpressions) for (form in entry.english) {
            aliases[normalizer.normalizeSequence(form)] = entry
        }
    }
    private val byEnglish = linkedMapOf<String, ReviewedAslPhrase>().also { aliases ->
        require(registry.phrases.map { it.id }.distinct().size == registry.phrases.size) { "Duplicate grammar ID" }
        for (phrase in registry.phrases) for (form in phrase.english) {
            val normalized = normalizer.normalizeSequence(form)
            require(normalized.isNotBlank()) { "Empty grammar alias" }
            require(aliases[normalized] == null || aliases[normalized]?.id == phrase.id) { "Ambiguous grammar alias" }
            aliases[normalized] = phrase
        }
    }

    fun plan(input: String?): TextToAslPlan {
        val text = input?.trim().orEmpty()
        val normalized = normalizer.normalizeSequence(text)
        val analysis = AslInputAnalysis.analyze(text, normalizer)
        if (registry.enabled) byEnglish[normalized]?.let { phrase ->
            validatedQueue(phrase, analysis)?.let { queue ->
                return TextToAslPlan(text, normalized, queue, emptyList(), TextToAslPlan.Mode.VALIDATED_PHRASE,
                    analysis, phrase.gloss, phrase.nonManualMarkers, ruleId = phrase.id)
            }
        }
        val namePrefix = registry.everydayExpressions.flatMap { it.namePrefixes }.map { normalizer.normalizeSequence(it) }
            .filter { normalized == it || normalized.startsWith("$it ") }.maxByOrNull { it.length }
        // A person's name can also be a dictionary word (Hope, Rose). Never substitute its lexical sign.
        val fallback = wordPlanner.plan(text, forceSpellingFromToken = namePrefix?.split(' ')?.size)
        val spellingAvailable = ('a'..'z').all { catalog.findLetter(it)?.let { letter ->
            AslSingleAvatarPolicy.permits(letter) && letter.replacement != null } == true }
        val mixedNotice = "English word-sign/fingerspelling preview; not a validated ASL sentence" +
            if (fallback.fingerspelledWords.isEmpty()) "" else "; fingerspelling: ${fallback.fingerspelledWords.joinToString(", ")}"
        if (registry.meaningRegistryUnavailable && normalized.contains(' ')) {
            return fallback.copy(queue = emptyList(), mode = TextToAslPlan.Mode.BLOCKED_MEANING, analysis = analysis,
                translationNotice = "ASL expression dictionary unavailable; sentence playback stopped")
        }
        val everyday = everydayByEnglish[normalized] ?: registry.everydayExpressions.firstOrNull { entry ->
            entry.namePrefixes.any { prefix ->
                val p = normalizer.normalizeSequence(prefix)
                normalized == p || normalized.startsWith("$p ")
            }
        }
        if (registry.enabled && everyday != null) {
            val preview = everyday.previewSignId?.let { assets[it] }
            if (preview != null && fallback.queue.size == 1 && fallback.queue.single().id == preview.id &&
                preview.type != AslAnimationAsset.Type.POSE && preview.type != AslAnimationAsset.Type.LETTER &&
                preview.metadata.avatarProfile != SignDictionaryMetadata.AvatarProfile.LEGACY) {
                return fallback.copy(analysis = analysis, ruleId = everyday.id,
                    translationNotice = "ASL expression preview; linguistic validation pending")
            }
            // Requirements describe concepts for asset acquisition, never a generated signing sequence.
            // LETTER I must not satisfy the personal pronoun ME/I requirement.
            val missing = everyday.requiredSigns.filter { requirement -> requirement.aliases.none { alias ->
                catalog.findByAlias(alias)?.let { asset ->
                    asset.type != AslAnimationAsset.Type.POSE && asset.type != AslAnimationAsset.Type.LETTER &&
                        asset.metadata.avatarProfile != SignDictionaryMetadata.AvatarProfile.LEGACY
                } == true
            } }.map { it.concept }
            val reason = if (missing.isEmpty()) "phrase order and non-manual features need ASL review"
                else "missing compatible signs: ${missing.joinToString(", ")}; ASL review also required"
            if (spellingAvailable && fallback.isPlayable) return fallback.copy(analysis = analysis,
                ruleId = everyday.id, translationNotice = "$mixedNotice; phrase grammar/non-manual features await review")
            return fallback.copy(queue = emptyList(), unsupportedTokens = missing,
                mode = TextToAslPlan.Mode.BLOCKED_MEANING, analysis = analysis, ruleId = everyday.id,
                translationNotice = "ASL expression unavailable: $reason")
        }
        if (registry.blockedLiteralExpressions.any { normalizer.normalizeSequence(it) == normalized }) {
            return fallback.copy(queue = emptyList(), mode = TextToAslPlan.Mode.BLOCKED_MEANING, analysis = analysis,
                translationNotice = "ASL idiom translation unavailable; literal playback stopped")
        }
        // Losing negation can turn an incomplete preview into its opposite meaning.
        if (analysis.negationWords.any { it in fallback.unsupportedTokens }) {
            return fallback.copy(queue = emptyList(), mode = TextToAslPlan.Mode.BLOCKED_MEANING, analysis = analysis,
                translationNotice = "ASL sentence not validated; playback stopped to preserve negation")
        }
        val notice = when {
            normalized.isBlank() -> null
            analysis.isQuestion || normalized.contains(' ') || analysis.negationWords.isNotEmpty() ->
                "ASL sentence not validated; individual sign preview"
            else -> null
        }
        return fallback.copy(analysis = analysis,
            translationNotice = if (fallback.fingerspelledWords.isNotEmpty()) mixedNotice else notice)
    }

    private fun validatedQueue(phrase: ReviewedAslPhrase, analysis: AslInputAnalysis): List<AslAnimationAsset>? {
        if (phrase.status != SignDictionaryMetadata.Status.LINGUISTICALLY_VALIDATED || !phrase.review.isComplete() ||
            phrase.meaning.isBlank() || phrase.gloss.isEmpty() || phrase.gloss.any { it.isBlank() } ||
            phrase.signIds.isEmpty() || phrase.negated != analysis.negationWords.isNotEmpty() ||
            phrase.timeWords != analysis.timeWords.toSet() || phrase.isQuestion != analysis.isQuestion ||
            phrase.intent != analysis.intent) return null
        val queue = phrase.signIds.map { assets[it] ?: return null }
        if (queue.any { it.type == AslAnimationAsset.Type.POSE || !it.metadata.isLinguisticallyValidated ||
                it.metadata.avatarProfile == SignDictionaryMetadata.AvatarProfile.LEGACY } ||
            queue.map { it.metadata.avatarProfile }.distinct().size != 1) return null
        if (phrase.gloss != queue.flatMap { it.metadata.gloss } ||
            (analysis.isQuestion && phrase.nonManualMarkers.isEmpty())) return null
        for (requirement in phrase.nonManualMarkers) {
            if (requirement.marker.isBlank() || requirement.fromSign !in queue.indices ||
                requirement.throughSign !in queue.indices || requirement.throughSign < requirement.fromSign) return null
            if ((requirement.fromSign..requirement.throughSign).any {
                    requirement.marker !in queue[it].metadata.embeddedNonManualMarkers }) return null
        }
        // Recorded requirements are embedded in reviewed clips; no invented face overlay.
        return queue
    }
}
