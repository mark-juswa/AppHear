package com.example.apphear.sentenceassist

import java.nio.file.Files
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SentenceAssistAssetsTest {
    @Test
    fun policyParsesAndPointsAtShippedAssets() {
        val json = SentenceAssistAssets.policyJson()
        assertEquals(SentenceAssistPolicy.SCHEMA_VERSION, json["schemaVersion"].asInt)
        val policy = SentenceAssistAssets.policy()
        assertTrue(Files.exists(SentenceAssistAssets.assetRoot.resolve(policy.lexiconAsset)))
        // Substitution limits are Context Assist's own policy, not a second copy.
        assertEquals("context_phrase_assist_policy.json", policy.substitutionPolicyAsset)
        assertTrue(Files.exists(SentenceAssistAssets.assetRoot.resolve(policy.substitutionPolicyAsset)))
    }

    @Test
    fun lexiconCoversExactlyTheRecognizerVocabularyItWasBuiltFrom() {
        val root = SentenceAssistAssets.lexiconJson()
        assertEquals(GlossLexicon.SCHEMA_VERSION, root["schemaVersion"].asInt)
        val vocabularyBytes = Files.readAllBytes(
            SentenceAssistAssets.assetRoot.resolve(root["vocabularyAsset"].asString))
        val sha = MessageDigest.getInstance("SHA-256").digest(vocabularyBytes)
            .joinToString("") { "%02x".format(it) }
        assertEquals("Lexicon was built for a different vocabulary; rebuild it", root["vocabularySha256"].asString, sha)
        val vocabulary = SentenceAssistAssets.vocabulary()
        assertEquals(236, vocabulary.size)
        assertTrue(SentenceAssistAssets.lexicon().coversExactly(vocabulary))
    }

    @Test
    fun closedListsNeverAllowUnsignedNegationPossessionOrComparison() {
        val lexicon = SentenceAssistAssets.lexicon()
        for (word in listOf("not", "no", "never", "my", "your", "our", "their")) {
            assertFalse(word, word in lexicon.grammarWords || word in lexicon.inferablePronouns)
        }
        assertEquals(setOf("i", "me", "you", "we", "us"), lexicon.inferablePronouns)
        val allForms = lexicon.glosses.flatMap { gloss -> lexicon.formsOf(gloss).map { it.joinToString(" ") } }
        for (comparative in listOf("better", "best", "bigger", "biggest", "older", "worse")) {
            assertFalse(comparative, comparative in allForms)
        }
    }
}
