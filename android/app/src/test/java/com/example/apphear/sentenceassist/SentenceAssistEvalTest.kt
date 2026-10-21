package com.example.apphear.sentenceassist

import com.google.gson.GsonBuilder
import com.google.gson.JsonObject
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Offline evaluation harness (Phase 2 step 6). Always: validates the case set and exports the
 * exact prompts the app would send. When recorded runs exist under
 * `eval/sentence_assist/runs/<run>/outputs.jsonl`, scores them with the shipped validator and
 * writes `metrics.json` and `review.csv` to `build/sentence_assist_eval/<run>/`.
 */
class SentenceAssistEvalTest {
    private val evalRoot = Path.of("../../eval/sentence_assist")
    private val outputRoot = Path.of("build/sentence_assist_eval")
    private val lexicon = SentenceAssistAssets.lexicon()
    private val template = SentenceAssistAssets.template()
    private val cases = SentenceAssistEvaluator.loadCases(evalRoot.resolve("cases_v1.jsonl"))
    private val gson = GsonBuilder().setPrettyPrinting().serializeNulls().create()

    @Test
    fun caseSetIsValidAgainstTheShippedLexicon() {
        assertTrue(cases.size >= 80)
        assertEquals(cases.size, cases.map { it.id }.toSet().size)
        for (case in cases) {
            val signs = case.turn.glosses + case.intended +
                case.turn.evidence.orEmpty().flatMap { event -> event.topK.map { it.gloss } }
            assertTrue(case.id, signs.all { it in lexicon.glosses })
            case.intendedByEvent?.let { assertEquals(case.id, case.turn.evidence?.size, it.size) }
        }
        val categories = cases.map { it.category }.toSet()
        assertTrue(categories.containsAll(listOf("clean", "noisy_real", "swap_help", "swap_decoy", "context_mismatch",
            "long", "repeated", "negation")))
        // Enough correct-but-swappable events for a 2 % harm gate to mean something.
        val policy = SentenceAssistAssets.substitutionPolicy()
        val protectedEvents = cases.sumOf { case ->
            val truth = case.intendedByEvent ?: return@sumOf 0
            case.turn.evidence.orEmpty().withIndex().count { (index, event) ->
                truth[index] == event.originalGloss && SubstitutionBounds.eligibleAlternatives(event, policy).isNotEmpty()
            }
        }
        assertTrue("only $protectedEvents protected events", protectedEvents >= 50)
    }

    @Test
    fun exportsTheExactPromptsTheAppWouldSend() {
        val prompt = SentenceAssistAssets.prompt()
        Files.createDirectories(outputRoot)
        val schema = SentenceAssistAssets.promptJson()["responseSchema"]
        val lines = cases.map { case ->
            JsonObject().apply {
                addProperty("id", case.id)
                addProperty("promptVersion", template.promptVersion)
                addProperty("model", template.model)
                addProperty("systemInstruction", template.systemInstruction)
                addProperty("input", prompt.input(RenderRequest(case.turn, case.hearing)))
                add("responseSchema", schema)
            }.toString()
        }
        Files.write(outputRoot.resolve("prompts_${template.promptVersion}.jsonl"), lines)
        assertEquals(cases.size, lines.size)
    }

    @Test
    fun scorerCountsHelpedAndHarmedSwapsWithTheShippedValidator() {
        val evaluator = SentenceAssistEvaluator(SentenceAssistAssets.validator(),
            SentenceAssistAssets.substitutionPolicy(), template.promptVersion)
        val fallback = PlainGlossRenderer(lexicon)
        val byId = cases.associateBy { it.id }
        fun ok(id: String, sentence: String, swap: Int? = null, gloss: String? = null) = EvalOutput(id,
            template.promptVersion, "ok", sentence,
            if (swap == null) emptyList() else listOf(RenderingMapper.RawSubstitution(swap, gloss)), 900L)
        val scored = listOf(
            // HOT shown, GOOD intended and within bounds: the swap helps.
            evaluator.score(byId.getValue("swap-help-01"), ok("swap-help-01", "I'm good.", 1, "GOOD"), fallback),
            // TIRED correct, GOOD a plausible decoy: the swap harms.
            evaluator.score(byId.getValue("swap-decoy-02"), ok("swap-decoy-02", "I'm good.", 1, "GOOD"), fallback),
            evaluator.score(byId.getValue("pronoun-02"), ok("pronoun-02", "I'm tired because."), fallback),
            evaluator.score(byId.getValue("pronoun-02"),
                EvalOutput("pronoun-02", template.promptVersion, "timeout", null, null, 8_000L), fallback),
        )
        val metrics = evaluator.metrics(scored)
        val swaps = metrics["substitutions"].asJsonObject
        assertEquals(1, swaps["acceptedHelped"].asInt)
        assertEquals(1, swaps["acceptedHarmed"].asInt)
        val statuses = metrics["aiStatus"].asJsonObject
        assertEquals(2, statuses["ACCEPTED"].asInt)
        assertEquals(1, statuses["REJECTED"].asInt)
        assertEquals(1, statuses["TIMEOUT"].asInt)
        assertEquals("Tired.", scored[3].chosenSentence)
        assertEquals(scored.size + 1, evaluator.reviewCsv(scored).lines().count { it.isNotEmpty() })
    }

    @Test
    fun scoresRecordedRunsWhenPresent() {
        val runs = evalRoot.resolve("runs")
        if (!Files.isDirectory(runs)) return
        val byId = cases.associateBy { it.id }
        val evaluator = SentenceAssistEvaluator(SentenceAssistAssets.validator(),
            SentenceAssistAssets.substitutionPolicy(), template.promptVersion)
        val fallback = PlainGlossRenderer(lexicon)
        runs.toFile().listFiles().orEmpty().map { it.toPath() }
            .filter { Files.isRegularFile(it.resolve("outputs.jsonl")) }.sorted()
            .forEach { run ->
                val outputs = SentenceAssistEvaluator.loadOutputs(run.resolve("outputs.jsonl"))
                val scored = outputs.mapNotNull { output ->
                    byId[output.id]?.let { evaluator.score(it, output, fallback) }
                }
                val target = outputRoot.resolve(run.fileName.toString())
                Files.createDirectories(target)
                Files.write(target.resolve("metrics.json"), gson.toJson(evaluator.metrics(scored)).toByteArray())
                Files.write(target.resolve("review.csv"), evaluator.reviewCsv(scored).toByteArray())
                assertEquals("Outputs reference unknown case ids in $run", outputs.size, scored.size)
            }
    }
}
