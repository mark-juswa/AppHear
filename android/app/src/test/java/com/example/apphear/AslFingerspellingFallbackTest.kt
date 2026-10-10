package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import org.junit.Assert.*
import org.junit.Test

class AslFingerspellingFallbackTest {
    private val assetRoot = Path.of("src/aslOriginalWords/assets")
    private val registry = JsonParser.parseString(String(Files.readAllBytes(assetRoot.resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject
    private val letters = AslFingerspellingBundle.letters(registry.getAsJsonArray("letters").map {
        val e=it.asJsonObject
        AslFingerspellingBundle.Letter(e.get("letter").asString.single(),e.get("animationName").asString,e.get("durationMs").asLong)
    })
    private fun word(id: String, alias: String = id) = AslAnimationAsset(id,id,AslFingerspellingBundle.PATH,
        AslAnimationAsset.Type.WORD,listOf(alias),AslAnimationAsset.Replacement(null,"SIGN_${id.uppercase()}",1500),
        SignDictionaryMetadata(avatarProfile=AslSingleAvatarPolicy.profile))
    private val catalog = AslAnimationCatalog.fromAssets(listOf(word("hello"),word("beautiful"),word("thank_you","thank you"),
        word("what"),word("your")),letters)
    private val planner = AslTranslationPlanner(catalog)
    private fun ids(text: String) = planner.plan(text).queue.map { it.id }
    private fun spelling(word: String) = word.lowercase().map { "letter_$it" }

    @Test fun missingWordsAndNamesSpellAllLettersAtomically() {
        for (word in listOf("NAME","NICOLE","ACTION","ANNA","JAZZ","unknownword")) {
            val plan=planner.plan(word)
            assertEquals(word,spelling(word),plan.queue.map { it.id })
            assertTrue(plan.unsupportedTokens.isEmpty())
            assertEquals(listOf(word.lowercase()),plan.fingerspelledWords)
            assertTrue(plan.queue.all { it.type==AslAnimationAsset.Type.LETTER && !it.metadata.isLinguisticallyValidated })
        }
        assertEquals(listOf("letter_a","letter_n","letter_n","letter_a"),ids("ANNA"))
        assertEquals(listOf("letter_j","letter_a","letter_z","letter_z"),ids("JAZZ"))
    }
    @Test fun wordSignsKeepPriorityAndSpellingRetainsBoundaries() {
        assertEquals(listOf("hello","beautiful"),ids("HELLO BEAUTIFUL"))
        assertEquals(listOf("hello")+spelling("nicole"),ids("HELLO, NICOLE!"))
        assertEquals(listOf("thank_you")+spelling("nicole"),ids("THANK YOU NICOLE"))
        val plan=planner.plan("HELLO BEAUTIFUL NICOLE ANNA")
        assertEquals(listOf("nicole","anna"),plan.fingerspelledWords)
        assertTrue(plan.queue[2].displayText.contains("NICOLE"))
        assertTrue(plan.queue.last().displayText.contains("ANNA"))
        assertTrue(plan.translationNotice!!.contains("not a validated ASL sentence"))
        assertEquals(1,plan.queue.map { it.assetPath }.distinct().size)
        assertTrue(plan.queue.all(AslSingleAvatarPolicy::permits))
    }
    @Test fun unrenderableTokensAreReportedWithoutPartialSpelling() {
        for (text in listOf("nicole2","josé","🙂")) {
            val plan=planner.plan("hello $text")
            assertEquals(listOf("hello"),plan.queue.map { it.id })
            assertEquals(listOf(text),plan.unsupportedTokens)
        }
        val incomplete = AslAnimationCatalog.fromAssets(listOf(word("hello")),letters-'n')
        val plan=AslPhrasePlanner(incomplete,completeWordFallback=true,dictionarySequenceMode=true).plan("hello nicole")
        assertEquals(listOf("hello"),plan.queue.map { it.id })
        assertEquals(listOf("nicole"),plan.unsupportedTokens)
    }
    @Test fun grammarCandidatesUseLabeledTemporaryOutputWithoutClaimingSentenceValidation() {
        val everyday=JsonParser.parseString(String(Files.readAllBytes(Path.of("src/main/assets/asl_animations/everyday_asl.json")))).asJsonObject
        val expressions=com.google.gson.Gson().fromJson(everyday.get("expressions"),Array<EverydayAslExpression>::class.java).toList()
        val p=AslTranslationPlanner(catalog,AslGrammarRegistry(everydayExpressions=expressions,blockedLiteralExpressions=listOf("break a leg")))
        val plan=p.plan("WHAT IS YOUR NAME?")
        assertFalse(plan.queue.isEmpty())
        assertEquals(listOf("what")+spelling("is")+listOf("your")+spelling("name"),plan.queue.map { it.id })
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,plan.mode)
        assertTrue(plan.gloss.isEmpty());assertTrue(plan.nonManualMarkers.isEmpty())
        assertTrue(plan.translationNotice!!.contains("non-manual"))
        assertTrue(p.plan("break a leg").queue.isEmpty())
        assertEquals(spelling("not"),p.plan("not").queue.map { it.id })
    }
    @Test fun bundledAlphabetContainsRealNamedActionsAndPreservesEveryOriginalWord() {
        val bytes=Files.readAllBytes(assetRoot.resolve(AslFingerspellingBundle.PATH))
        assertEquals(AslFingerspellingBundle.SHA256,MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })
        fun document(b: ByteArray)=JsonParser.parseString(String(b,20,ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        val g=document(bytes)
        val old=document(Files.readAllBytes(assetRoot.resolve(AslResidentAvatarBundle.PATH)))
        for (key in listOf("nodes","skins","meshes","materials","textures","images","scenes")) assertEquals(old.get(key),g.get(key))
        assertEquals(230,g.getAsJsonArray("animations").size())
        // LOVE alone has an explicitly audited six-bone contact correction.
        // AslLoveContactTest verifies its scope and preserved finger channels.
        assertEquals(old.getAsJsonArray("animations").filter { it.asJsonObject.get("name").asString!="SIGN_LOVE" },
            g.getAsJsonArray("animations").take(203).filter { it.asJsonObject.get("name").asString!="SIGN_LOVE" })
        val names=g.getAsJsonArray("animations").map { it.asJsonObject.get("name").asString }
        for ((character,asset) in letters) {
            assertTrue(names.contains(asset.replacement!!.animationName))
            assertEquals(character,"abcdefghijklmnopqrstuvwxyz".first { it==character })
            assertTrue(asset.originalFallback()==null)
        }
        assertTrue(registry.getAsJsonArray("audit").any { it.asJsonObject.get("letter").asString=="J" })
        for (letter in listOf("J","Z")) {
            val a=registry.getAsJsonArray("audit").single { it.asJsonObject.get("letter").asString==letter }.asJsonObject
            assertTrue(a.getAsJsonArray("sourceHandMotionSpan").any { it.asDouble>0.01 })
            assertTrue(a.get("sourceSamples").asInt>2)
        }
    }
}
