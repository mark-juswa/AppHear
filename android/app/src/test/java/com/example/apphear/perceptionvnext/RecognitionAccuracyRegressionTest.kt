package com.example.apphear.perceptionvnext

import com.example.apphear.pipeline.recognition.SentenceBuilder
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

/**
 * Phase 3 regression guards for the recognition contract. They protect the 236-word vocabulary, the model packages
 * and the way recognizer output is interpreted and gated, so a candidate model, an asset swap or a refactor cannot
 * silently change them. They prove CONTRACTS, not accuracy.
 */
class RecognitionAccuracyRegressionTest {
    private val main = Path.of("src", "main", "assets")
    private val debug = Path.of("src", "debug", "assets")
    private val evidence = Path.of("..", "..", "docs", "audit", "probes")

    private fun json(p: Path): JsonObject = JsonParser.parseString(String(Files.readAllBytes(p), Charsets.UTF_8)).asJsonObject
    private fun sha(p: Path): String = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p))
        .joinToString("") { "%02x".format(it) }
    private fun glosses(a: JsonArray) = a.map { it.asString }

    private class Pkg(val name: String, val manifest: JsonObject, val root: Path)

    private fun packages(): List<Pkg> = listOf(
        Pkg("GATE2_FROZEN", json(main.resolve("phase4a_gate2_recognizer_parity/manifest.json")), main),
        Pkg("WORD_V2_CANDIDATE", json(debug.resolve("word_v2_candidate/manifest.json")), debug),
        Pkg("WORD_BLEND_01", json(debug.resolve("word_blend_candidate_01/manifest.json")), debug),
        Pkg("WORD_BLEND_02", json(debug.resolve("word_blend_candidate_02/manifest.json")), debug),
    )

    // ---- vocabulary: every class -------------------------------------------------------------------------------

    @Test fun everyOneOf236ClassesMapsIdenticallyAcrossEveryPackageAndTheLegacyVocabulary() {
        val reference = glosses(packages()[0].manifest.getAsJsonArray("class_index_to_gloss"))
        assertEquals(236, reference.size)
        assertEquals("class names must be unique", reference.size, reference.toSet().size)
        for (pkg in packages()) {
            assertEquals("${pkg.name} class order", reference, glosses(pkg.manifest.getAsJsonArray("class_index_to_gloss")))
            assertEquals("${pkg.name} vocabulary pin", RecognitionV2LiveRecognizer.VOCAB_SHA, pkg.manifest.get("vocabulary_sha256").asString)
        }
        val legacy = json(main.resolve("vocab.json"))
        assertEquals(236, legacy.size())
        for ((index, gloss) in reference.withIndex()) {
            assertNotNull("legacy vocab is missing class $gloss", legacy.get(gloss))
            assertEquals("class $gloss ($index) maps to a different index in vocab.json", index, legacy.get(gloss).asInt)
        }
    }

    @Test fun theDocumentedDifficultClassesAndConfusionPartnersAreAllRealVocabularyClasses() {
        val vocab = glosses(packages()[0].manifest.getAsJsonArray("class_index_to_gloss")).toSet()
        val per = json(evidence.resolve("word_accuracy/difficult_words.json")).getAsJsonObject("models")
        for (model in listOf("frozen", "BLEND_01", "BLEND_02")) {
            val classes = per.getAsJsonObject(model).getAsJsonObject("classes")
            assertEquals("$model evidence must cover every class exactly once", vocab, classes.keySet())
            for ((cls, v) in classes.entrySet()) {
                val partner = v.asJsonObject.get("partner")
                if (partner != null && !partner.isJsonNull && partner.asString.isNotEmpty()) assertTrue("$model partner of $cls: ${partner.asString}", partner.asString in vocab)
            }
        }
    }

    // ---- model input/output compatibility and integrity --------------------------------------------------------------

    @Test fun everyPackagedRecognizerMatchesItsManifestAndTheRecognitionV2Contract() {
        assertEquals(350, RecognitionV2.FEATURE_WIDTH)
        assertEquals(96, RecognitionV2.MAX_SEQUENCE_LENGTH)
        assertEquals(96 * 350, RecognitionV2LiveRecognizer.FEATURE_ELEMENTS)
        assertEquals(236, RecognitionV2LiveRecognizer.OUTPUTS)
        for (pkg in packages()) {
            val m = pkg.manifest
            val model = pkg.root.resolve(m.get("model_asset").asString)
            assertTrue("${pkg.name} model file", Files.isRegularFile(model))
            assertEquals("${pkg.name} TFLite hash", m.get("model_sha256").asString, sha(model))
            assertEquals("${pkg.name} feature schema", RecognitionV2.FEATURE_SCHEMA, m.get("feature_schema").asString)
            assertEquals("${pkg.name} input", listOf(1, 96, 350), m.getAsJsonArray("input_shape").map { it.asInt })
            assertEquals("${pkg.name} mask", listOf(1, 96), m.getAsJsonArray("mask_shape").map { it.asInt })
            assertEquals("${pkg.name} output", listOf(1, 236), m.getAsJsonArray("output_shape").map { it.asInt })
            assertEquals("${pkg.name} output is probabilities", "probabilities_softmax", m.get("output_semantics")?.asString ?: "probabilities_softmax")
            assertFalse("${pkg.name} must not have touched protected data", m.get("protected_test_accessed").asBoolean)
        }
        assertEquals(RecognitionV2LiveRecognizer.MODEL_SHA, sha(main.resolve("phase4a_gate2_recognizer_parity/ordinary_v2_tcn_fp32.tflite")))
    }

    @Test fun theProductionConfigurationsStillPointAtTheFrozenRecognizerAndCandidatesStayDebugOnly() {
        assertEquals(RecognitionV2LiveRecognizer.FROZEN_GATE2, PhoneRecognitionConfiguration.STABLE.wordPackage())
        assertEquals(RecognitionV2LiveRecognizer.FROZEN_GATE2, PhoneRecognitionConfiguration.EXPERIMENTAL.wordPackage())
        assertEquals("WORD_BLEND_01", PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND.wordPackage().packageId)
        assertEquals("WORD_BLEND_02", PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND_02.wordPackage().packageId)
        // candidate model files exist only in the debug source set: a release build cannot load them
        for (name in listOf("word_blend_candidate_01", "word_blend_candidate_02", "word_v2_candidate")) {
            assertFalse("$name must not be in main assets", Files.exists(main.resolve(name)))
            assertTrue("$name must be in debug assets", Files.isDirectory(debug.resolve(name)))
        }
    }

    // ---- model fallback ---------------------------------------------------------------------------------------------

    @Test fun unknownStaleOrNonDebugSelectionsFallBackToStable() {
        for (saved in listOf(null, "", "NOPE", "stable", "EXPERIMENTAL_WORD_BLEND_99")) {
            assertEquals("saved=$saved", PhoneRecognitionConfiguration.STABLE, PhoneRecognitionConfiguration.resolve(saved, true))
        }
        for (c in PhoneRecognitionConfiguration.entries) {
            assertEquals("release must always resolve STABLE (saved=${c.name})", PhoneRecognitionConfiguration.STABLE, PhoneRecognitionConfiguration.resolve(c.name, false))
        }
        assertEquals(PhoneRecognitionConfiguration.EXPERIMENTAL, PhoneRecognitionConfiguration.resolve("EXPERIMENTAL", true))
    }

    // ---- confidence floors and the gate ----------------------------------------------------------------------------------

    @Test fun theConfidenceFloorsInCodeAreTheCalibratedOperatingPointsInTheEvidenceFile() {
        val policy = json(evidence.resolve("event_reliability/gate_policy.json"))
        assertEquals(policy.getAsJsonObject("S2_R2__BASELINE").get("threshold").asDouble,
            PhoneRecognitionConfiguration.STABLE.commitPolicy().minTop1Probability!!, 0.0)
        assertEquals(policy.getAsJsonObject("ARM_A_E10__CONFIRM_BOUNDARY_70").get("threshold").asDouble,
            PhoneRecognitionConfiguration.EXPERIMENTAL.commitPolicy().minTop1Probability!!, 0.0)
        for (c in listOf(PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND, PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND_02)) {
            assertNull("no independent calibration exists for ${c.name}; a guessed floor is forbidden", c.commitPolicy().minTop1Probability)
        }
        for (c in PhoneRecognitionConfiguration.entries) assertTrue(c.commitPolicy().requireHandEvidenceInSpan)
    }

    private val vocab: List<String> by lazy { glosses(packages()[0].manifest.getAsJsonArray("class_index_to_gloss")) }

    private fun probs(top: Int, p1: Float, second: Int, p2: Float) =
        FloatArray(236) { (1f - p1 - p2) / 234f }.also { it[top] = p1; it[second] = p2 }

    private fun top5(p: FloatArray) = p.indices.sortedWith(compareByDescending<Int> { p[it] }.thenBy { it }).take(5).toIntArray()

    @Test fun theGateTreatsEveryVocabularyClassIdenticallyConfidentCommitsAndLowConfidenceIsWithheld() {
        val stable = PhoneRecognitionConfiguration.STABLE.commitPolicy()
        for (cls in 0 until 236) {
            val sentence = SentenceBuilder()
            val committer = PhoneEventCommitter(stable, sentence)
            val strong = probs(cls, 0.90f, (cls + 1) % 236, 0.05f)
            val accepted = committer.decide(1, strong, top5(strong), vocab, 1.0)
            assertEquals("class $cls (${vocab[cls]})", CommitOutcome.ACCEPT, accepted.decision.outcome)
            assertEquals(vocab[cls], sentence.text())
            assertEquals(cls, accepted.committed!!.classId)
            val weak = probs(cls, 0.30f, (cls + 2) % 236, 0.20f)
            val withheld = committer.decide(2, weak, top5(weak), vocab, 1.0)
            assertEquals("class $cls low confidence", CommitOutcome.UNCERTAIN, withheld.decision.outcome)
            assertEquals("a withheld class must not change the sentence", vocab[cls], sentence.text())
        }
    }

    @Test fun everyDifficultClassIsTreatedLikeAnyOtherAndTheEvidenceListIsNonTrivial() {
        val frozen = json(evidence.resolve("word_accuracy/difficult_words.json")).getAsJsonObject("models")
            .getAsJsonObject("frozen").getAsJsonObject("classes")
        val hard = frozen.entrySet().filter { it.value.asJsonObject.get("recall_real").asDouble <= 0.30 }.map { it.key }
        assertEquals("published hard-class count for the frozen recognizer", 98, hard.size)
        val stable = PhoneRecognitionConfiguration.STABLE.commitPolicy()
        for (cls in hard) {
            val index = vocab.indexOf(cls)
            assertTrue("hard class $cls is in the vocabulary", index >= 0)
            val p = probs(index, 0.60f, (index + 1) % 236, 0.10f)
            val r = PhoneEventCommitter(stable, SentenceBuilder()).decide(1, p, top5(p), vocab, 1.0)
            assertEquals("no class-specific rule exists: $cls at 0.60 is accepted like any class", CommitOutcome.ACCEPT, r.decision.outcome)
        }
    }

    @Test fun misorderedOrInconsistentRecognizerOutputIsRejectedNeverCommitted() {
        val stable = PhoneRecognitionConfiguration.STABLE.commitPolicy()
        // (a) top-5 not best-first with DISTINCT probabilities: top-2 exceeds top-1
        val distinct = FloatArray(236) { 0.0001f * (it % 7) }.also { it[5] = 0.90f; it[6] = 0.05f; it[7] = 0.03f; it[8] = 0.01f; it[9] = 0.005f }
        val reversed = top5(distinct).reversedArray()
        val s1 = SentenceBuilder()
        val r1 = PhoneEventCommitter(stable, s1).decide(1, distinct, reversed, vocab, 1.0)
        assertEquals(CommitOutcome.REJECT, r1.decision.outcome)
        assertTrue(s1.isEmpty())
        // (b) a TIED mis-ordered list that the p2 > p1 test alone cannot see: top-1 is not an argmax of the output
        val p = probs(5, 0.90f, 6, 0.05f)
        val s2 = SentenceBuilder()
        val r2 = PhoneEventCommitter(stable, s2).decide(1, p, top5(p).reversedArray(), vocab, 1.0)
        assertEquals(CommitOutcome.REJECT, r2.decision.outcome)
        assertEquals("INVALID_RECOGNIZER_OUTPUT", r2.decision.reason)
        assertTrue(s2.isEmpty())
        // (c) a correctly ordered list is untouched, and the disabled (pre-gate) policy still commits exactly as before
        assertEquals(CommitOutcome.ACCEPT, PhoneEventCommitter(stable, SentenceBuilder()).decide(1, p, top5(p), vocab, 1.0).decision.outcome)
        val legacy = SentenceBuilder()
        PhoneEventCommitter(PhoneCommitPolicy.DISABLED, legacy).decide(1, p, top5(p).reversedArray(), vocab, 1.0)
        assertFalse("pre-gate behaviour is preserved for the disabled policy", legacy.isEmpty())
    }

    @Test fun top5InterpretationIsDescendingProbabilityWithLowestIndexFirstOnTies() {
        val p = FloatArray(236)
        p[10] = 0.2f; p[3] = 0.2f; p[200] = 0.5f; p[7] = 0.05f; p[8] = 0.05f
        assertEquals(listOf(200, 3, 10, 7, 8), top5(p).toList())
        val r = PhoneEventCommitter(PhoneRecognitionConfiguration.STABLE.commitPolicy(), SentenceBuilder()).decide(1, p, top5(p), vocab, 1.0)
        assertEquals(200, r.top1)
        assertEquals(0.3f, r.margin, 1e-6f) // 0.5 - 0.2: the margin is only logged, never a rule
    }

    // ---- recognition after analyzer recovery ----------------------------------------------------------------------------

    @Test fun recognitionResumesAfterAnAnalyzerRecoveryAndTheSentenceSurvivesTheReset() {
        val sentence = SentenceBuilder()
        val committer = PhoneEventCommitter(PhoneRecognitionConfiguration.STABLE.commitPolicy(), sentence)
        val metrics = DetectionMetrics()
        val supervisor = AnalyzerSupervisor(resetTemporalState = { committer.reset() }, metrics = metrics)
        fun event(id: Int, cls: Int, p1: Float) {
            val p = probs(cls, p1, (cls + 1) % 236, 0.02f)
            committer.decide(id, p, top5(p), vocab, 1.0)
        }
        assertEquals(FrameOutcome.Ok, supervisor.runFrame { event(1, vocab.indexOf("HELLO"), 0.95f) })
        // a session-phase failure: the temporal session (and the commit-gate event ids) are reset, the sentence is not
        val fault = supervisor.runFrame { ctx -> ctx.phase = AnalyzerPhase.SESSION; throw IllegalStateException("PHONE_SEGMENTATION_NONFINITE_FEATURE") }
        assertTrue(fault is FrameOutcome.Recovered)
        // event ids restart at 1 after the reset; without committer.reset() this would throw APP_PHONE_DUPLICATE_EVENT_ID
        assertEquals(FrameOutcome.Ok, supervisor.runFrame { event(1, vocab.indexOf("HOME"), 0.92f) })
        assertEquals("HELLO HOME", sentence.text())
        // a withheld event after recovery does not disturb the next valid one
        assertEquals(FrameOutcome.Ok, supervisor.runFrame { event(2, vocab.indexOf("TABLE"), 0.20f) })
        assertEquals(FrameOutcome.Ok, supervisor.runFrame { event(3, vocab.indexOf("TABLE"), 0.90f) })
        assertEquals("HELLO HOME TABLE", sentence.text())
        assertEquals(1L, metrics.snapshot().recoverySuccesses)
    }
}
