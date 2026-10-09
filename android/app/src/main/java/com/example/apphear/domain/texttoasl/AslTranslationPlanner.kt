package com.example.apphear.domain.texttoasl

class AslTranslationPlanner(
    private val catalog: AslAnimationCatalog,
    private val registry: AslGrammarRegistry = AslGrammarRegistry(),
    private val wordPlanner: AslPhrasePlanner = AslPhrasePlanner(catalog, dictionarySequenceMode = true),
    private val normalizer: AslTextNormalizer = AslTextNormalizer(),
) {
    private val assets = catalog.getAssets().associateBy { it.id }
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
        val fallback = wordPlanner.plan(text)
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
        return fallback.copy(analysis = analysis, translationNotice = notice)
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
