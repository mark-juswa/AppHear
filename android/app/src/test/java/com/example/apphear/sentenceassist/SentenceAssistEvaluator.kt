package com.example.apphear.sentenceassist

import com.example.apphear.contextassist.PhraseMatchPolicy
import com.example.apphear.contextassist.RecognitionEvidence
import com.example.apphear.contextassist.SignScore
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path

/** One offline evaluation case (`eval/sentence_assist/cases_v1.jsonl`). */
data class EvalCase(
    val id: String,
    val category: String,
    val hearing: String?,
    val turn: SignedTurn,
    val intended: List<String>,
    val intendedByEvent: List<String?>?,
)

/** One recorded provider reply written by `tools/sentence_assist/collect_outputs.py`. */
data class EvalOutput(
    val id: String,
    val promptVersion: String,
    val status: String,
    val sentence: String?,
    val substitutions: List<RenderingMapper.RawSubstitution>?,
    val latencyMs: Long?,
)

/**
 * Scores recorded outputs with the app's own [RenderingMapper] and [GroundingValidator], so the
 * offline numbers describe exactly what the shipped code would accept. Measures, never asserts.
 */
class SentenceAssistEvaluator(
    private val validator: GroundingValidator,
    private val substitutionPolicy: PhraseMatchPolicy,
    private val promptVersion: String,
) {
    data class Scored(val case: EvalCase, val output: EvalOutput, val aiStatus: AiStatus,
                      val result: GroundingResult?, val chosenSentence: String)

    fun score(case: EvalCase, output: EvalOutput, fallback: PlainGlossRenderer): Scored {
        val rendering = if (output.status == "ok") RenderingMapper.map(output.sentence, output.substitutions) else null
        val fallbackSentence = fallback.plain(case.turn).sentence
        if (rendering == null) {
            val status = if (output.status == "timeout") AiStatus.TIMEOUT else AiStatus.UNAVAILABLE
            return Scored(case, output, status, null, fallbackSentence)
        }
        return when (val result = validator.validate(case.turn, rendering)) {
            is GroundingResult.Accepted -> Scored(case, output, AiStatus.ACCEPTED, result, result.sentence)
            is GroundingResult.Rejected -> Scored(case, output, AiStatus.REJECTED, result, fallbackSentence)
        }
    }

    fun metrics(scored: List<Scored>): JsonObject {
        val root = JsonObject()
        root.addProperty("outputs", scored.size)
        root.addProperty("promptVersionMismatches", scored.count { it.output.promptVersion != promptVersion })
        root.add("aiStatus", counts(scored.map { it.aiStatus.name }))
        root.add("rejectReasons", counts(scored.mapNotNull { (it.result as? GroundingResult.Rejected)?.reason?.name }))
        val byCategory = JsonObject()
        scored.groupBy { it.case.category }.toSortedMap().forEach { (category, items) ->
            byCategory.add(category, JsonObject().apply {
                addProperty("outputs", items.size)
                addProperty("acceptedRate", items.count { it.aiStatus == AiStatus.ACCEPTED }.toDouble() / items.size)
            })
        }
        root.add("byCategory", byCategory)
        val clean = scored.filter { it.case.category in CLEAN_CATEGORIES }
        val cleanRate = if (clean.isEmpty()) null else clean.count { it.aiStatus == AiStatus.ACCEPTED }.toDouble() / clean.size
        root.addProperty("cleanAcceptedRate", cleanRate)
        root.addProperty("acceptedWithInferredPronoun", scored.count {
            (it.result as? GroundingResult.Accepted)?.inferredPronouns?.let { n -> n > 0 } == true
        })
        val swaps = swapCounts(scored)
        root.add("substitutions", swaps)
        val latencies = scored.filter { it.output.status == "ok" }.mapNotNull { it.output.latencyMs }.sorted()
        root.add("latencyMs", JsonObject().apply {
            addProperty("n", latencies.size)
            addProperty("p50", percentile(latencies, 0.5))
            addProperty("p95", percentile(latencies, 0.95))
        })
        val protectedEvents = swaps["correctTop1WithEligibleAlternative"].asInt
        val harmed = swaps["acceptedHarmed"].asInt
        val helped = swaps["acceptedHelped"].asInt
        root.add("gates", JsonObject().apply {
            addProperty("cleanAcceptedRateAtLeast90", cleanRate?.let { it >= 0.90 })
            addProperty("harmRateAtMost2Percent", if (protectedEvents == 0) null else harmed.toDouble() / protectedEvents <= 0.02)
            addProperty("helpedAtLeastHarmed", helped >= harmed)
            addProperty("humanReview", "pending: fill review.csv (meaning_preserved, adds_information)")
        })
        return root
    }

    /**
     * Substitution outcomes on cases with event-level ground truth. Helped: replaced a wrong Top-1
     * with the intended sign. Harmed: replaced a correct Top-1. Only accepted renderings count,
     * because rejected ones would never be offered; proposals are reported separately.
     */
    private fun swapCounts(scored: List<Scored>): JsonObject {
        var proposed = 0; var helped = 0; var harmed = 0; var neutral = 0
        var opportunities = 0; var protectedEvents = 0
        for (item in scored) {
            val evidence = item.case.turn.evidence ?: continue
            val truth = item.case.intendedByEvent ?: continue
            evidence.forEachIndexed { index, event ->
                val intended = truth.getOrNull(index)
                val eligible = SubstitutionBounds.eligibleAlternatives(event, substitutionPolicy)
                if (intended != null && intended != event.originalGloss && intended in eligible) opportunities++
                if (intended != null && intended == event.originalGloss && eligible.isNotEmpty()) protectedEvents++
            }
            val raw = item.output.substitutions.orEmpty()
            proposed += raw.size
            val accepted = (item.result as? GroundingResult.Accepted)?.substitutions.orEmpty()
            for (substitution in accepted) {
                val original = evidence[substitution.eventIndex].originalGloss
                val intended = truth.getOrNull(substitution.eventIndex)
                when {
                    intended != null && substitution.gloss == intended && original != intended -> helped++
                    intended != null && original == intended -> harmed++
                    else -> neutral++
                }
            }
        }
        return JsonObject().apply {
            addProperty("proposed", proposed)
            addProperty("acceptedHelped", helped)
            addProperty("acceptedHarmed", harmed)
            addProperty("acceptedNeutral", neutral)
            addProperty("helpOpportunities", opportunities)
            addProperty("correctTop1WithEligibleAlternative", protectedEvents)
        }
    }

    fun reviewCsv(scored: List<Scored>): String = buildString {
        appendLine(listOf("id", "category", "hearing", "recognized", "intended", "ai_status", "reject_reason",
            "ai_sentence", "chosen_sentence", "substitutions", "word_sources",
            "meaning_preserved", "adds_information", "notes").joinToString(",") { csv(it) })
        for (item in scored) {
            val accepted = item.result as? GroundingResult.Accepted
            appendLine(listOf(
                item.case.id, item.case.category, item.case.hearing.orEmpty(),
                item.case.turn.glosses.joinToString(" "), item.case.intended.joinToString(" "),
                item.aiStatus.name, (item.result as? GroundingResult.Rejected)?.let { "${it.reason}:${it.detail}" }.orEmpty(),
                item.output.sentence.orEmpty(), item.chosenSentence,
                item.output.substitutions.orEmpty().joinToString(" ") { "${it.signNumber}:${it.gloss}" },
                accepted?.words?.joinToString(" ") { "${it.text}/${it.source.name}" }.orEmpty(),
                "", "", "",
            ).joinToString(",") { csv(it) })
        }
    }

    private fun csv(value: String) = "\"" + value.replace("\"", "\"\"") + "\""

    private fun counts(values: List<String>) = JsonObject().apply {
        values.groupingBy { it }.eachCount().toSortedMap().forEach { (key, count) -> addProperty(key, count) }
    }

    private fun percentile(sorted: List<Long>, fraction: Double): Long? {
        if (sorted.isEmpty()) return null
        val rank = kotlin.math.ceil(fraction * sorted.size).toInt().coerceAtLeast(1)
        return sorted[rank - 1]
    }

    companion object {
        /** Correct recognitions: the rendering should be accepted (gate: at least 90 %). */
        val CLEAN_CATEGORIES = setOf("clean", "question", "pronoun", "long", "repeated", "negation")

        fun loadCases(path: Path): List<EvalCase> = Files.readAllLines(path).filter { it.isNotBlank() }.map { line ->
            val json = JsonParser.parseString(line).asJsonObject
            val evidence = json["evidence"].takeUnless { it.isJsonNull }?.asJsonArray?.mapIndexed { index, item ->
                val event = item.asJsonObject
                val topK = event["topK"].asJsonArray.map { pair ->
                    pair.asJsonArray.let { SignScore(it[0].asString, it[1].asFloat) }
                }
                RecognitionEvidence(index + 1, (index + 1) * 1_000L, event["gloss"].asString, topK)
            }
            EvalCase(
                id = json["id"].asString,
                category = json["category"].asString,
                hearing = json["hearing"].takeUnless { it.isJsonNull }?.asString,
                turn = SignedTurn(json["glosses"].asJsonArray.map { it.asString }, evidence),
                intended = json["intended"].asJsonArray.map { it.asString },
                intendedByEvent = json["intendedByEvent"].takeUnless { it.isJsonNull }?.asJsonArray
                    ?.map { it.takeUnless { value -> value.isJsonNull }?.asString },
            )
        }

        fun loadOutputs(path: Path): List<EvalOutput> = Files.readAllLines(path).filter { it.isNotBlank() }.map { line ->
            val json = JsonParser.parseString(line).asJsonObject
            EvalOutput(
                id = json["id"].asString,
                promptVersion = json["promptVersion"].asString,
                status = json["status"].asString,
                sentence = json["sentence"]?.takeUnless { it.isJsonNull }?.asString,
                substitutions = json["substitutions"]?.takeUnless { it.isJsonNull }?.asJsonArray?.map { item ->
                    val entry = item.asJsonObject
                    RenderingMapper.RawSubstitution(
                        entry["signNumber"]?.takeUnless { it.isJsonNull }?.asInt,
                        entry["gloss"]?.takeUnless { it.isJsonNull }?.asString,
                    )
                },
                latencyMs = json["latencyMs"]?.takeUnless { it.isJsonNull }?.asLong,
            )
        }
    }
}
