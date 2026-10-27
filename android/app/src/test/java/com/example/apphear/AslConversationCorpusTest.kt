package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

class AslConversationCorpusTest {
    private val normalizer = AslTextNormalizer()
    private fun word(id: String, alias: String=id) = AslAnimationAsset(id,id,AslFingerspellingBundle.PATH,
        AslAnimationAsset.Type.WORD,listOf(alias),AslAnimationAsset.Replacement(null,"SIGN_${id.uppercase()}",1500),
        SignDictionaryMetadata(avatarProfile=AslSingleAvatarPolicy.profile))
    private val letters = AslFingerspellingBundle.letters(('a'..'z').map {
        AslFingerspellingBundle.Letter(it,"SIGN_LETTER_${it.uppercaseChar()}_WOLF3D_PREVIEW",1500)
    })
    private val catalog = AslAnimationCatalog.fromAssets(listOf(word("hello"),word("mean","mean"),
        word("mean_meaning","meaning"),word("right","right"),word("right_direction","right direction"),
        word("do"),word("not"),word("stop"),word("have"),word("let")),letters)
    private val planner = AslTranslationPlanner(catalog)
    @Test fun apostrophizedInputsPreserveNegationAndEveryWord() {
        assertEquals("i do not understand",normalizer.normalizeSequence("I DON'T understand!"))
        assertEquals("it is hot today",normalizer.normalizeSequence("It's hot today!"))
        assertEquals("i am fine",normalizer.normalizeSequence("I\u2019m fine."))
        assertEquals("cant",normalizer.normalizeSequence("can't"))
        assertEquals(listOf("not"),AslInputAnalysis.analyze("Don't worry.").negationWords)
        assertFalse(AslInputAnalysis.analyze("Don't worry.").isQuestion)
        assertEquals(AslInputAnalysis.Intent.GREETING,AslInputAnalysis.analyze("How are you?").intent)
        assertTrue(AslInputAnalysis.analyze("How are you?").isQuestion)
        assertEquals(setOf(0,1),AslLexicalContext.forPreview("how much does this cost",catalog).fingerspellTokens)
    }
    @Test fun contextSelectsMeaningWithoutDeletingAuxiliaries() {
        val meaning=planner.plan("What do you mean?")
        assertEquals("mean_meaning",meaning.queue.last().id)
        assertTrue(meaning.fingerspelledWords.contains("do"))
        assertEquals("right_direction",planner.plan("Turn right.").queue.last().id)
        assertTrue(planner.plan("Where is the bus stop?").fingerspelledWords.contains("stop"))
        assertTrue(planner.plan("Have a good day.").fingerspelledWords.contains("have"))
        assertTrue(planner.plan("Let's work together.").fingerspelledWords.contains("let"))
        assertEquals(listOf("do"),planner.plan("do").queue.map { it.id })
        val symbols=planner.plan("\uD83D\uDE42 what do you mean?")
        assertEquals(listOf("\uD83D\uDE42"),symbols.unsupportedTokens)
        assertEquals("mean_meaning",symbols.queue.last().id)
        assertEquals(1,symbols.queue.count { it.id == "mean_meaning" })
    }
    @Test fun all100InputsRemainExplicitUnvalidatedPreviews() {
        val corpus=JsonParser.parseString(String(Files.readAllBytes(Path.of("../tools/conversation-100-asl.json")))).asJsonObject
        val expressions=corpus.getAsJsonArray("expressions")
        assertEquals(100,expressions.size())
        for (raw in expressions) {
            val e=raw.asJsonObject
            val text=e.get("english").asString
            val plan=planner.plan(text)
            assertTrue(text,plan.queue.isNotEmpty())
            assertTrue(text,plan.unsupportedTokens.isEmpty())
            assertNotEquals(text,TextToAslPlan.Mode.VALIDATED_PHRASE,plan.mode)
            assertTrue(text,plan.gloss.isEmpty())
            assertTrue(text,plan.queue.all(AslSingleAvatarPolicy::permits))
            assertFalse(e.get("qualifiedAslValidation").asBoolean)
        }
    }
}
