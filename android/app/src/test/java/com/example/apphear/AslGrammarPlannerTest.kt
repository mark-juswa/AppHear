package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import org.junit.Assert.*
import org.junit.Test

/** Synthetic review records exercise software gates, not actual linguistic validation. */
class AslGrammarPlannerTest {
    private val profile = SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN
    private fun fixture(id: String, aliases: List<String> = listOf(id), markers: Set<String> = emptySet()) =
        AslAnimationAsset(id, id, "asl_animations/fixture_$id.glb", AslAnimationAsset.Type.WORD, aliases,
            metadata = SignDictionaryMetadata(language = SignDictionaryMetadata.Language.ASL,
                validationStatus = SignDictionaryMetadata.ValidationStatus.REVIEWED, avatarProfile = profile,
                source = "unit-test fixture", license = "unit-test fixture", reviewEvidence = "unit-test fixture",
                status = SignDictionaryMetadata.Status.LINGUISTICALLY_VALIDATED, gloss = listOf(id.uppercase()),
                meaning = "synthetic meaning", reviewer = "synthetic reviewer", reviewedOn = "2026-10-10",
                playbackEvidence = "synthetic playback", embeddedNonManualMarkers = markers))
    private val a = fixture("alpha")
    private val b = fixture("beta")
    private val review = ReviewedAslPhrase.ReviewRecord("synthetic reviewer", "2026-10-10", listOf("fixture"),
        "fixture", "fixture", "fixture", "fixture")
    private fun rule() = ReviewedAslPhrase("fixture_rule", listOf("alpha beta"), "synthetic meaning",
        AslInputAnalysis.Intent.STATEMENT, listOf("BETA", "ALPHA"), listOf("beta", "alpha"),
        SignDictionaryMetadata.Status.LINGUISTICALLY_VALIDATED, review)
    private fun planner(rule: ReviewedAslPhrase = rule(), assets: List<AslAnimationAsset> = listOf(a,b), enabled: Boolean = true) =
        AslTranslationPlanner(AslAnimationCatalog.fromAssets(assets), AslGrammarRegistry(enabled, listOf(rule)))

    @Test fun reviewedWholeMeaningSelectsDeclaredOrderNotEnglishOrder() {
        val result = planner().plan("ALPHA, BETA!")
        assertEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, result.mode)
        assertEquals(listOf("beta", "alpha"), result.queue.map { it.id })
        assertEquals(listOf("BETA", "ALPHA"), result.gloss)
        assertEquals("fixture_rule", result.ruleId)
    }

    @Test fun candidateAndTechnicallyPlayableRulesNeverClaimValidation() {
        for (status in SignDictionaryMetadata.Status.entries.filter { it != SignDictionaryMetadata.Status.LINGUISTICALLY_VALIDATED }) {
            val result = planner(rule().copy(status = status)).plan("alpha beta")
            assertEquals(listOf("alpha", "beta"), result.queue.map { it.id })
            assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, result.mode)
            assertTrue(result.translationNotice!!.contains("not validated"))
        }
    }

    @Test fun incompleteReviewOrWrongMeaningCannotEnableRule() {
        for (bad in listOf(rule().copy(review = review.copy(playbackEvidence = "")),
                rule().copy(review = review.copy(reviewedOn = "2026-02-30")),
                rule().copy(gloss = listOf("UNRELATED")), rule().copy(negated = true),
                rule().copy(timeWords = setOf("tomorrow")), rule().copy(intent = AslInputAnalysis.Intent.WH_QUESTION))) {
            assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(bad).plan("alpha beta").mode)
        }
    }

    @Test fun missingUnreviewedOrOtherAvatarAssetCannotEnableRule() {
        val unreviewed = b.copy(metadata = b.metadata.copy(status = SignDictionaryMetadata.Status.MAPPED))
        val other = b.copy(metadata = b.metadata.copy(avatarProfile = SignDictionaryMetadata.AvatarProfile.NEW_HUMAN))
        for (assets in listOf(listOf(a), listOf(a,unreviewed), listOf(a,other))) {
            assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(assets = assets).plan("alpha beta").mode)
        }
    }

    @Test fun nonManualScopeRequiresReviewedEmbeddedFeatures() {
        val required = rule().copy(nonManualMarkers = listOf(ReviewedAslPhrase.NonManualMarker("fixture_marker",0,1)))
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(required).plan("alpha beta").mode)
        val supported = listOf(a,b).map { it.copy(metadata = it.metadata.copy(embeddedNonManualMarkers = setOf("fixture_marker"))) }
        assertEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(required,supported).plan("alpha beta").mode)
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(required.copy(nonManualMarkers =
            listOf(ReviewedAslPhrase.NonManualMarker("fixture_marker",0,2))),supported).plan("alpha beta").mode)
    }

    @Test fun questionWithOnlyManualClipsIsNotValidated() {
        val question = rule().copy(english = listOf("what alpha"), intent = AslInputAnalysis.Intent.WH_QUESTION,
            isQuestion = true, gloss = listOf("ALPHA"), signIds = listOf("alpha"))
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(question).plan("what alpha?").mode)
    }

    @Test fun unsupportedNegationBlocksAffirmativePartialPlayback() {
        for (input in listOf("not alpha", "I don't alpha", "I can’t alpha", "never alpha")) {
            val result = AslTranslationPlanner(AslAnimationCatalog.fromAssets(listOf(a))).plan(input)
            assertEquals(TextToAslPlan.Mode.BLOCKED_MEANING, result.mode)
            assertTrue(result.queue.isEmpty())
            assertTrue(result.translationNotice!!.contains("negation"))
        }
    }

    @Test fun supportedNegationAndTimeAreNotDeletedInPreview() {
        val catalog = AslAnimationCatalog.fromAssets(listOf(a,fixture("not"),fixture("tomorrow")))
        val result = AslTranslationPlanner(catalog).plan("not alpha tomorrow")
        assertEquals(listOf("not","alpha","tomorrow"), result.queue.map { it.id })
        assertEquals(listOf("not"),result.analysis!!.negationWords)
        assertEquals(listOf("tomorrow"),result.analysis!!.timeWords)
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,result.mode)
    }

    @Test fun idiomIsBlockedAndRegistrySwitchPreservesWordSequence() {
        val catalog = AslAnimationCatalog.fromAssets(listOf(a,b))
        val blocked = AslTranslationPlanner(catalog, AslGrammarRegistry(blockedLiteralExpressions = listOf("alpha beta")))
        assertTrue(blocked.plan("alpha beta").queue.isEmpty())
        assertEquals(listOf("alpha","beta"),planner(enabled = false).plan("alpha beta").queue.map { it.id })
    }

    @Test fun aliasesMustNotEraseTimeNegationOrCreateSubstringRules() {
        val withAlias = rule().copy(english = listOf("alpha beta", "alpha beta tomorrow", "not alpha beta"))
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(withAlias).plan("alpha beta tomorrow").mode)
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner(withAlias).plan("not alpha beta").mode)
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner().plan("alpha beta unknownword").mode)
        assertThrows(IllegalArgumentException::class.java) {
            AslTranslationPlanner(AslAnimationCatalog.fromAssets(listOf(a,b)),
                AslGrammarRegistry(phrases = listOf(rule(), rule().copy(id = "collision"))))
        }
    }

    @Test fun intentRoutingRecognizesTestExpressionsWithoutClaimingTranslation() {
        val expected = mapOf("Hello" to AslInputAnalysis.Intent.GREETING,
            "What is your name?" to AslInputAnalysis.Intent.WH_QUESTION,
            "How are you?" to AslInputAnalysis.Intent.WH_QUESTION,
            "Where are you going?" to AslInputAnalysis.Intent.WH_QUESTION,
            "Can you help me?" to AslInputAnalysis.Intent.REQUEST,
            "I need help" to AslInputAnalysis.Intent.REQUEST,
            "I am hungry" to AslInputAnalysis.Intent.STATEMENT,
            "Thank you" to AslInputAnalysis.Intent.EXPRESSION)
        for ((text,intent) in expected) assertEquals(text,intent,AslInputAnalysis.analyze(text).intent)
        assertEquals(listOf("tomorrow"),AslInputAnalysis.analyze("See you tomorrow").timeWords)
    }

    @Test fun metadataStatusesDoNotEquateReviewLabelWithASLValidation() {
        assertTrue(a.metadata.isLinguisticallyValidated)
        assertFalse(a.metadata.copy(status = SignDictionaryMetadata.Status.PLAYABLE).isLinguisticallyValidated)
        assertFalse(a.metadata.copy(license = null).isLinguisticallyValidated)
        assertFalse(a.metadata.copy(reviewedOn = "2026-02-30").isLinguisticallyValidated)
        assertFalse(a.metadata.copy(language = SignDictionaryMetadata.Language.FSL).isLinguisticallyValidated)
    }
}
