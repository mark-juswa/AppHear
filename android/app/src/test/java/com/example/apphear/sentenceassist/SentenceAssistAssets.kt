package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.PhraseMatchPolicy
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path

/** Loads the shipped sentence-assist assets for JVM tests (org.json is unavailable here). */
object SentenceAssistAssets {
    val assetRoot: Path = Path.of("src/main/assets")

    fun json(asset: String): JsonObject =
        JsonParser.parseString(String(Files.readAllBytes(assetRoot.resolve(asset)), Charsets.UTF_8)).asJsonObject

    fun policyJson(): JsonObject = json(SentenceAssistPolicy.ASSET)

    fun policy(): SentenceAssistPolicy = policyJson().let {
        SentenceAssistPolicy(
            lexiconAsset = it["lexiconAsset"].asString,
            promptAsset = it["promptAsset"].asString,
            substitutionPolicyAsset = it["substitutionPolicyAsset"].asString,
            debounceMs = it["debounceMs"].asLong,
            minGlossesForAi = it["minGlossesForAi"].asInt,
            renderTimeoutMs = it["renderTimeoutMs"].asLong,
            maxGlosses = it["maxGlosses"].asInt,
            maxOutputChars = it["maxOutputChars"].asInt,
            maxInferredPronouns = it["maxInferredPronouns"].asInt,
        )
    }

    fun lexiconJson(): JsonObject = json(policy().lexiconAsset)

    fun lexicon(): GlossLexicon = lexiconJson().let { root ->
        GlossLexicon(
            glossForms = root["glosses"].asJsonObject.entrySet().associate { (gloss, forms) ->
                gloss to forms.asJsonArray.map { it.asString }
            },
            grammarWords = root["grammarWords"].asJsonArray.map { it.asString },
            inferablePronouns = root["inferablePronouns"].asJsonArray.map { it.asString },
        )
    }

    fun substitutionPolicy(): PhraseMatchPolicy = json(policy().substitutionPolicyAsset).let {
        PhraseMatchPolicy(
            it["maximum_changed_events"].asInt,
            it["maximum_contradicting_top1"].asFloat,
            it["maximum_changed_score_gap"].asFloat,
            it["minimum_changed_score_ratio"].asFloat,
            it["minimum_winner_lead"].asFloat,
        )
    }

    fun vocabulary(): List<String> =
        json(lexiconJson()["vocabularyAsset"].asString)["class_index_to_gloss"].asJsonArray.map { it.asString }

    fun validator(): GroundingValidator = GroundingValidator(lexicon(), policy(), substitutionPolicy())

    fun promptJson(): JsonObject = json(policy().promptAsset)

    fun template(): PromptTemplate = promptJson().let {
        PromptTemplate(
            promptVersion = it["promptVersion"].asString,
            model = it["model"].asString,
            systemInstruction = it["systemInstruction"].asString,
            inputTemplate = it["inputTemplate"].asString,
            substitutionRuleWithAlternatives = it["substitutionRuleWithAlternatives"].asString,
            substitutionRuleWithoutAlternatives = it["substitutionRuleWithoutAlternatives"].asString,
            noHearingContext = it["noHearingContext"].asString,
            responseSchemaJson = it["responseSchema"].toString(),
        )
    }

    fun prompt(): SentencePrompt = SentencePrompt(template(), lexicon(), policy(), substitutionPolicy())
}
