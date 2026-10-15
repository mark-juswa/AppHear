package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

class AslVocabularyExpansionTest {
    private val root = Path.of("src/aslOriginalWords/assets")
    private fun json(path: Path) = JsonParser.parseString(String(Files.readAllBytes(path))).asJsonObject
    private val registry = json(root.resolve(AslFingerspellingBundle.MANIFEST))
    private val source = json(root.resolve(OriginalWordBatchCatalog.MANIFEST))
    private val frozen = json(Path.of("src/main/assets/asl_animations/manifest.json")).getAsJsonArray("clips")
        .associate { it.asJsonObject.get("id").asString to it.asJsonObject }
    private val words = registry.getAsJsonArray("wordAdditions").map { raw ->
        val e = raw.asJsonObject
        AslVocabularyExpansion.Word(e.get("id").asString, e.getAsJsonArray("english").map { it.asString },
            e.get("animationName").asString, e.get("durationMs").asLong, e.get("sourceAsset").asString,
            e.get("sourceSha256").asString, e.get("reference").asString, e.get("meaning").asString,
            e.get("license").asString, e.get("variantOf")?.asString)
    }
    private val originals = (source.getAsJsonArray("replacements") + source.getAsJsonArray("newClips")).map { raw ->
        val e = raw.asJsonObject
        val original = frozen[e.get("id").asString]
        AslAnimationAsset(e.get("id").asString, (e.get("displayText") ?: original!!.get("displayText")).asString, e.get("asset").asString,
            AslAnimationAsset.Type.WORD, (e.getAsJsonArray("aliases") ?: original!!.getAsJsonArray("aliases")).map { it.asString },
            AslAnimationAsset.Replacement(null, e.get("animationName").asString, e.get("durationMs").asLong),
            SignDictionaryMetadata(avatarProfile = AslSingleAvatarPolicy.profile))
    }
    private val aliases = json(Path.of("src/main/assets/asl_animations/existing_aliases_asl.json")).getAsJsonArray("aliases")
    private val base = aliases.fold(originals) { result, raw ->
        val e = raw.asJsonObject
        val path = e.get("asset").asString
        ExistingAslAlias(e.get("signId").asString, e.getAsJsonArray("english").map { it.asString }, path,
            e.get("sha256").asString, e.get("reference").asString).apply(result, hash(Files.readAllBytes(root.resolve(path))))
    }.map { it.copy(assetPath = AslFingerspellingBundle.PATH) }
    private val letters = AslFingerspellingBundle.letters(registry.getAsJsonArray("letters").map { raw ->
        val e = raw.asJsonObject
        AslFingerspellingBundle.Letter(e.get("letter").asString.single(), e.get("animationName").asString, e.get("durationMs").asLong)
    })
    private val catalog = AslAnimationCatalog.fromAssets(AslVocabularyExpansion.merge(base, words), letters)
    private val planner = AslTranslationPlanner(catalog)
    private fun ids(text: String) = planner.plan(text).queue.map { it.id }
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    @Test fun nameAndPronounsUseRealWordActionsInsteadOfSpelling() {
        assertEquals(listOf("name"), ids("NAME!"))
        assertEquals(listOf("you"), ids("You"))
        assertEquals(listOf("you_all"), ids("YOU ALL"))
        assertEquals(listOf("you_all"), ids("All of you."))
        assertEquals(listOf("hello", "you", "name"), ids("HELLO, YOU NAME!"))
        assertEquals(listOf("mother"), ids("mom"))
        assertEquals(listOf("mother"), ids("MUM"))
        assertEquals(listOf("father"), ids("Dad"))
        assertEquals(listOf("ok"), ids("Okay"))
    }

    @Test fun newWordsPreserveFallbackAndSentenceValidationBoundary() {
        val mixed = planner.plan("YOU NICOLE")
        assertEquals(listOf("you", "letter_n", "letter_i", "letter_c", "letter_o", "letter_l", "letter_e"), mixed.queue.map { it.id })
        assertEquals(listOf("nicole"), mixed.fingerspelledWords)
        assertEquals(1, mixed.queue.map { it.assetPath }.distinct().size)
        assertTrue(mixed.queue.all(AslSingleAvatarPolicy::permits))
        assertTrue(mixed.translationNotice!!.contains("not a validated ASL sentence"))
        val question = planner.plan("WHAT IS YOUR NAME?")
        assertEquals(listOf("what", "letter_i", "letter_s", "your_yours", "name"), question.queue.map { it.id })
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, question.mode)
        assertTrue(words.all { !catalog.findByAlias(it.english.first())!!.metadata.isLinguisticallyValidated })
        assertTrue(planner.plan("you nicole2").unsupportedTokens.contains("nicole2"))
    }

    @Test fun additionsAreNamedInTheHashedBundleAndSourceAssetsExist() {
        val bytes = Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
        assertEquals(AslFingerspellingBundle.SHA256, hash(bytes))
        val length = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12)
        val g = JsonParser.parseString(String(bytes, 20, length)).asJsonObject
        val names = g.getAsJsonArray("animations").map { it.asJsonObject.get("name").asString }
        assertEquals(248, names.size)
        for (word in words) {
            assertTrue(names.contains(word.animationName))
            val folder = if (word.variantOf == null) Path.of("src/main/assets") else root
            assertEquals(word.sourceSha256, hash(Files.readAllBytes(folder.resolve(word.sourceAsset))))
        }
        assertEquals(listOf("you", "you_all", "name", "best", "better", "divorce", "from", "grandma",
            "grandpa", "here", "parents", "prefer", "single", "again", "class", "must", "fingerspell",
            "so_so", "grow_up"), words.map { it.id })
        val name = catalog.findByAlias("name")!!
        assertEquals("SIGN_CALL__TO_CALL_SOMEONE_S_NAME", name.replacement!!.animationName)
        assertEquals(base.single { it.id == "call_someones_name" }.replacement!!.animationName, name.replacement.animationName)
        assertEquals(SignDictionaryMetadata.Status.MAPPED, name.metadata.status)
    }

    @Test fun invalidOrConflictingEntriesAreRejected() {
        val you = words.first()
        for (invalid in listOf(you.copy(id = "hello"), you.copy(english = listOf("hello")),
                you.copy(animationName = "made_up"), you.copy(sourceSha256 = "bad"),
                you.copy(id = "other", variantOf = "call_someones_name"))) {
            assertTrue(runCatching { AslVocabularyExpansion.merge(base, listOf(invalid)) }.isFailure)
        }
    }

    @Test fun tenEverydayEntriesAreNewLexicalActionsNotSpellingOrAliases() {
        val newIds=listOf("best","better","divorce","from","grandma","grandpa","here","parents","prefer","single")
        for(id in newIds) {
            assertFalse("Previously absent entry: $id",base.any { it.id==id || id in it.aliases })
            assertEquals(listOf(id),ids("  ${id.uppercase()}!  "))
            val entry=catalog.findByAlias(id)!!
            assertEquals(AslAnimationAsset.Type.WORD,entry.type)
            assertEquals("SIGN_${id.uppercase()}_HUMAN_RETARGETED_PREVIEW",entry.replacement!!.animationName)
            assertFalse(entry.metadata.isLinguisticallyValidated)
        }
        assertEquals(listOf("grandma"),ids("grandmother"))
        assertEquals(listOf("grandpa"),ids("grandfather"))
        assertEquals(listOf("prefer"),ids("favorite"))
    }

    @Test fun newWordsMixWithLexicalSignsAndAutomaticSpellingOnOneAvatar() {
        val mixed=planner.plan("HELLO GRANDMA NICOLE")
        assertEquals(listOf("hello","grandma","letter_n","letter_i","letter_c","letter_o","letter_l","letter_e"),mixed.queue.map { it.id })
        assertEquals(listOf("nicole"),mixed.fingerspelledWords)
        assertEquals(1,mixed.queue.map {it.assetPath}.distinct().size)
        assertTrue(mixed.queue.all(AslSingleAvatarPolicy::permits))
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,mixed.mode)
        assertTrue(mixed.translationNotice!!.contains("not a validated ASL sentence"))
    }

    @Test fun expansionKeepsTechnicalAndLinguisticReviewSeparate() {
        val audit=registry.getAsJsonObject("everydayExpansion")
        assertEquals(232,audit.get("preservedActions").asInt)
        assertEquals(10,audit.get("newLexicalActions").asInt)
        assertEquals(0,audit.get("qualifiedAslValidations").asInt)
        assertTrue(audit.get("sourceGeometryUnchanged").asBoolean)
        assertEquals(10,audit.getAsJsonArray("checks").size())
        assertTrue(words.takeLast(10).all {catalog.findByAlias(it.english.first())!!.metadata.status==SignDictionaryMetadata.Status.MAPPED})
    }

    @Test fun secondBatchAddsSixAbsentLexicalActionsWithConservativeAliases() {
        val forms=mapOf("AGAIN!" to "again", "repeat" to "again", "CLASS" to "class",
            "must" to "must", "fingerspelling" to "fingerspell", "spell" to "fingerspell",
            "So-so." to "so_so", "  GROW   UP! " to "grow_up")
        for((input,id) in forms) {
            assertFalse(base.any {it.id==id})
            assertEquals(listOf(id),ids(input))
            val entry=catalog.findByAlias(input.trim().trimEnd('!','.').lowercase().replace(Regex("\\s+")," "))
                ?: catalog.findByAlias(words.single {it.id==id}.english.first())!!
            assertEquals(AslAnimationAsset.Type.WORD,entry.type)
            assertEquals("SIGN_${id.uppercase()}_HUMAN_RETARGETED_PREVIEW",entry.replacement!!.animationName)
            assertFalse(entry.metadata.isLinguisticallyValidated)
        }
        // Rejected source mappings remain automatic spelling, never a wrong lexical sign.
        assertNull(catalog.findByAlias("request"))
        assertNull(catalog.findByAlias("girl"))
        assertEquals(listOf("girl"),planner.plan("girl").fingerspelledWords)
        assertNull(catalog.findByAlias("critical"))
        assertNull(catalog.findByAlias("raised"))
        val audit=registry.getAsJsonObject("everydayExpansion2")
        assertEquals(242,audit.get("preservedActions").asInt)
        assertEquals(6,audit.get("newLexicalActions").asInt)
        assertEquals(0,audit.get("qualifiedAslValidations").asInt)
    }

    @Test fun secondBatchMixesWithExistingWordsAndSpellingWithoutSentenceCertification() {
        val result=planner.plan("HELLO CLASS NICOLE")
        assertEquals(listOf("hello","class","letter_n","letter_i","letter_c","letter_o","letter_l","letter_e"),result.queue.map {it.id})
        assertEquals(listOf("nicole"),result.fingerspelledWords)
        assertEquals(1,result.queue.map {it.assetPath}.distinct().size)
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,result.mode)
        assertTrue(result.translationNotice!!.contains("not a validated ASL sentence"))
        assertEquals(listOf("help","again"),ids("help again"))
    }
}
