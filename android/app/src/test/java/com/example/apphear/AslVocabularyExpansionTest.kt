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
            e.get("license").asString, e.get("variantOf")?.asString,
            e.get("construction")?.asString ?: "RETARGETED_PREVIEW")
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
    private val thirdBatchWords = words.filter { it.id in setOf("stop", "understand", "hungry", "finish", "tired", "deaf", "hearing", "learn", "rain", "now") }
    private val catalog = AslAnimationCatalog.fromAssets(AslFingerspellingBundle.withDurations(
        AslVocabularyExpansion.merge(base, words), registry.getAsJsonObject("durationOverridesMs")?.entrySet()
            ?.associate { it.key to it.value.asLong }.orEmpty()), letters)
    private val planner = AslTranslationPlanner(catalog)
    private fun ids(text: String) = planner.plan(text).queue.map { it.id }
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    @Test fun adverbAuditDistinguishesExistingMotionsFromEnglishInputForms() {
        assertEquals(19, AslAdverbPolicy.entries.size)
        assertEquals(19, AslAdverbPolicy.entries.map { it.english }.distinct().size)
        assertEquals(258, catalog.getAssets().size)
        assertEquals(setOf("here", "now"), AslAdverbPolicy.entries.filter {
            catalog.findByAlias(it.english) != null
        }.map { it.english }.toSet())
        for (id in listOf("fast", "slow", "here", "now")) {
            val asset = catalog.getAssets().single { it.id == id }
            assertNotNull(asset.replacement)
            assertTrue(AslSingleAvatarPolicy.permits(asset))
            assertFalse(asset.metadata.isLinguisticallyValidated)
        }
        assertTrue(AslAdverbPolicy.entries.all { it.meaning.isNotBlank() && it.limitation.isNotBlank() })
    }

    @Test fun speedAdverbsReuseExistingActionsWithoutNewAnimations() {
        assertEquals(ids("fast"), ids("QUICKLY!"))
        assertEquals(ids("slow"), ids("  Slowly.  "))
        assertEquals("fast", ids("Please come quickly.").last())
        assertEquals("slow", ids("Please sign slowly.").last())
        assertEquals(listOf("fast", "slow"), ids("quickly slowly"))
        for (text in listOf("quickly", "slowly", "Please sign slowly.", "Please come quickly.")) {
            val plan = planner.plan(text)
            assertTrue(plan.isPlayable)
            assertTrue(plan.translationNotice!!.contains("speed sense"))
            assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, plan.mode)
        }
    }

    @Test fun missingAdverbsAreSpelledAtomicallyRatherThanInventedOrOmitted() {
        val missing = AslAdverbPolicy.entries.filter { it.previewSignId == null }
        assertEquals(15, missing.size)
        for (entry in missing) {
            val plan = planner.plan(entry.english.uppercase())
            assertEquals(entry.english, entry.english.map { "letter_$it" }, plan.queue.map { it.id })
            assertEquals(listOf(entry.english), plan.fingerspelledWords)
            assertTrue(plan.unsupportedTokens.isEmpty())
            assertTrue(plan.translationNotice!!.contains("not a validated ASL sentence"))
            assertTrue(plan.queue.all(AslSingleAvatarPolicy::permits))
        }
    }

    @Test fun adverbsKeepTheirMeaningBearingTokensInCommonSentences() {
        val samples = mapOf("just" to "I just arrived", "already" to "I already ate",
            "still" to "I am still learning ASL", "always" to "I always help",
            "never" to "I never drink coffee", "sometimes" to "I sometimes study",
            "often" to "I often go to school", "only" to "I only want water",
            "even" to "Even you need help", "maybe" to "Maybe we can meet tomorrow",
            "probably" to "I will probably go", "really" to "I really need help",
            "very" to "I am very tired", "there" to "There is water",
            "later" to "See you later")
        for ((word, text) in samples) {
            val plan = planner.plan(text)
            assertTrue(text, plan.isPlayable)
            assertTrue(text, word in plan.fingerspelledWords)
            assertTrue(text, plan.unsupportedTokens.isEmpty())
            assertNotEquals(text, TextToAslPlan.Mode.VALIDATED_PHRASE, plan.mode)
            assertTrue(text, plan.gloss.isEmpty() && plan.nonManualMarkers.isEmpty())
        }
        assertEquals(listOf("never"), planner.plan("I never drink coffee").analysis!!.negationWords)
    }

    @Test fun ambiguousAdverbsDoNotBorrowUnrelatedMotions() {
        for (text in listOf("I just arrived", "I just want water", "I am still learning",
            "Stand still", "I really need help", "Really?", "There is a school", "Go there")) {
            val plan = planner.plan(text)
            assertTrue(text, plan.fingerspelledWords.any { it in setOf("just", "still", "really", "there") })
            assertFalse(text, plan.queue.any { it.id in setOf("single", "finish", "stay", "sure") })
        }
        assertTrue(planner.plan("I am not very tired").queue.any { it.id == "not" })
        assertTrue("very" in planner.plan("I am not very tired").fingerspelledWords)
        assertTrue(planner.plan("Maybe?").analysis!!.isQuestion)
    }

    @Test fun adverbMappingDoesNotAffectNamesAlphabetOrUnrelatedSigns() {
        val names = AslTranslationPlanner(catalog, AslGrammarRegistry(everydayExpressions = listOf(
            EverydayAslExpression("name_introduction", listOf("my name is"), "Introduce a personal name",
                listOf(EverydayAslExpression.RequiredSign("NAME", listOf("name"))),
                listOf("https://www.lifeprint.com/asl101/pages-signs/n/name.htm"), "ASL review pending",
                namePrefixes = listOf("my name is")))))
        assertTrue("slowly" in names.plan("My name is Slowly").fingerspelledWords)
        assertFalse(names.plan("My name is Slowly").queue.any { it.id == "slow" })
        assertEquals(ids("finish"), listOf("finish"))
        assertEquals(ids("library school"), listOf("library", "school"))
        // Standalone English I remains the existing personal-pronoun mapping.
        // The alphabet remains available through the separate letter table.
        for (letter in 'a'..'z') assertEquals("letter_$letter", catalog.findLetter(letter)!!.id)
        assertEquals("i_me", ids("I").single())
        assertTrue(planner.plan("NICOLE").queue.all { it.type == AslAnimationAsset.Type.LETTER })
        assertTrue(planner.plan("ANNA").queue.map { it.id } == listOf("letter_a", "letter_n", "letter_n", "letter_a"))
        assertEquals(AslFingerspellingBundle.SHA256, hash(Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))))
    }

    @Test fun absentSpeedAnimationUsesFallbackOnTheSameRig() {
        val reduced = AslAnimationCatalog.fromAssets(catalog.getAssets().filter { it.id !in setOf("fast", "slow") }, letters)
        val fallback = AslTranslationPlanner(reduced).plan("quickly slowly")
        assertEquals(listOf("quickly", "slowly"), fallback.fingerspelledWords)
        assertTrue(fallback.queue.all { it.type == AslAnimationAsset.Type.LETTER })
        assertFalse(fallback.translationNotice!!.contains("speed sense"))
    }

    @Test fun adverbSentenceCorpusReportsActualPlannerCoverageWithoutValidationClaims() {
        val corpus = json(Path.of("../tools/adverb-preview-cases.json"))
        val rows = com.google.gson.JsonArray()
        assertFalse(corpus.get("qualifiedAslValidation").asBoolean)
        for (raw in corpus.getAsJsonArray("cases")) {
            val entry = raw.asJsonObject
            val word = entry.get("adverb").asString
            val plan = planner.plan(entry.get("english").asString)
            assertTrue(word, plan.isPlayable && plan.unsupportedTokens.isEmpty())
            assertNotEquals(word, TextToAslPlan.Mode.VALIDATED_PHRASE, plan.mode)
            val expected = entry.get("expectedSignId").takeUnless { it.isJsonNull }?.asString
            if (expected == null) assertTrue(word, word in plan.fingerspelledWords)
            else assertTrue(word, plan.queue.any { it.id == expected })
            rows.add(com.google.gson.JsonObject().apply {
                addProperty("english", plan.requestedText)
                addProperty("adverb", word)
                addProperty("mode", plan.mode.name)
                addProperty("adverbLexicalPreviewId", expected)
                addProperty("sentenceStatus", "PARTIALLY_SUPPORTED_REQUIRES_ASL_VALIDATION")
                addProperty("qualifiedAslValidation", false)
                add("queuedIds", com.google.gson.JsonArray().apply { plan.queue.forEach { add(it.id) } })
                add("fingerspelledWords", com.google.gson.JsonArray().apply { plan.fingerspelledWords.forEach { add(it) } })
                addProperty("notice", plan.translationNotice)
            })
        }
        assertEquals(AslAdverbPolicy.entries.map { it.english }.toSet(), rows.map { it.asJsonObject.get("adverb").asString }.toSet())
        val output = Path.of("../../.tmp/text-to-sign/adverbs/planner-results.json")
        Files.createDirectories(output.parent)
        Files.write(output, com.google.gson.GsonBuilder().setPrettyPrinting().create().toJson(rows).toByteArray(Charsets.UTF_8))
    }

    @Test fun firstConversationBatchHasRealScreenedActionsAndExplicitPreviewStatus() {
        val expected=setOf("fine","sign","can","not","with","together","nice","explain","study","communicate")
        val added=words.filter { it.id in expected }
        assertEquals(expected,added.map { it.id }.toSet())
        val gates=JsonParser.parseString(javaClass.getResource("/texttoasl/conversation-mechanical-gates.json")!!.readText()).asJsonObject
        // Preserve the original ten-action screen as historical evidence; the
        // four-placement repair is independently screened against that exact bundle.
        val placements=JsonParser.parseString(javaClass.getResource("/texttoasl/four-placement-gates.json")!!.readText()).asJsonObject
        assertEquals(placements.get("sourceSha256").asString,gates.get("candidateSha256").asString)
        val wrists=JsonParser.parseString(javaClass.getResource("/texttoasl/three-wrist-gates.json")!!.readText()).asJsonObject
        assertEquals(placements.get("candidateSha256").asString,wrists.get("sourceSha256").asString)
        assertEquals(AslFingerspellingBundle.BEFORE_INTEGRATION_SHA256,wrists.get("candidateSha256").asString)
        assertEquals(274,gates.get("preservedActions").asInt)
        assertEquals(10,gates.get("newActions").asInt)
        assertTrue(gates.getAsJsonArray("rows").all { it.asJsonObject.get("technicallyPassed").asBoolean })
        assertFalse(gates.get("qualifiedAslValidation").asBoolean)
        for (id in expected) assertEquals(listOf(id),ids(id))
        assertEquals(listOf("sign"),ids("sign language"))
        assertEquals(listOf("again"),ids("repeat"))
        assertEquals(listOf("eat"),ids("food"))
        for (word in added) assertFalse(catalog.findByAlias(word.english.first())!!.metadata.isLinguisticallyValidated)
    }

    @Test fun userConversationCorpusUsesOnlyRealSameAvatarAssets() {
        val corpus=json(Path.of("../tools/conversation-100-asl.json"))
        val bytes=Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
        val g=JsonParser.parseString(String(bytes,20,ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        val actions=g.getAsJsonArray("animations").map { it.asJsonObject.get("name").asString }.toSet()
        val report=com.google.gson.JsonArray()
        for (raw in corpus.getAsJsonArray("expressions")) {
            val input=raw.asJsonObject.get("english").asString
            val plan=planner.plan(input)
            assertTrue(input,plan.queue.isNotEmpty())
            assertTrue(input,plan.unsupportedTokens.isEmpty())
            assertNotEquals(input,TextToAslPlan.Mode.VALIDATED_PHRASE,plan.mode)
            for (asset in plan.queue) {
                assertTrue(input,AslSingleAvatarPolicy.permits(asset))
                assertTrue(input,asset.replacement!!.animationName in actions)
            }
            report.add(com.google.gson.JsonObject().apply {
                addProperty("english",input);addProperty("mode",plan.mode.name)
                addProperty("isValidatedAslSentence",false)
                add("queueIds",com.google.gson.Gson().toJsonTree(plan.queue.map { it.id }))
                add("fingerspelledWords",com.google.gson.Gson().toJsonTree(plan.fingerspelledWords))
            })
        }
        val out=Path.of("build/reports/text-to-sign/conversation-planner.json")
        Files.createDirectories(out.parent);Files.write(out,report.toString().toByteArray())
    }

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
        assertEquals(AslFingerspellingBundle.ACTION_COUNT, names.size)
        for (word in words) {
            assertTrue(names.contains(word.animationName))
            val folder = if (word.variantOf != null || word.construction == "REFERENCE_AUTHORED_PREVIEW") root else Path.of("src/main/assets")
            assertEquals(word.sourceSha256, hash(Files.readAllBytes(folder.resolve(word.sourceAsset))))
        }
        assertEquals(listOf("you", "you_all", "name", "best", "better", "divorce", "from", "grandma",
            "grandpa", "here", "parents", "prefer", "single", "again", "class", "must", "fingerspell",
            "so_so", "grow_up", "stop", "understand", "hungry", "finish", "tired", "deaf", "hearing", "learn", "rain", "now",
            "bathroom", "doctor", "nurse", "pain", "milk", "coffee", "tea", "orange", "apple", "bread",
            "church", "library", "college", "university", "kitchen", "hotel",
            "fine", "sign", "can", "not", "with", "together", "nice", "explain", "study", "communicate"), words.map { it.id })
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
        assertTrue(thirdBatchWords.all {catalog.findByAlias(it.english.first())!!.metadata.status==SignDictionaryMetadata.Status.MAPPED})
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
        val secondBatchCatalog=AslAnimationCatalog.fromAssets(AslVocabularyExpansion.merge(base,words.take(19)),letters)
        assertNull(secondBatchCatalog.findByAlias("girl"))
        assertEquals(listOf("girl"),AslTranslationPlanner(secondBatchCatalog).plan("girl").fingerspelledWords)
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

    @Test fun tenAuthoredEntriesAreAbsentFromPriorCatalogAndHaveHonestProvenance() {
        val prior = AslAnimationCatalog.fromAssets(AslVocabularyExpansion.merge(base,words.take(19)),letters)
        for(word in thirdBatchWords) {
            assertNull(prior.findByAlias(word.english.first()))
            assertEquals(listOf(word.id),ids("  ${word.id.uppercase()}!  "))
            assertEquals("REFERENCE_AUTHORED_PREVIEW",word.construction)
            val entry=catalog.findByAlias(word.id)!!
            assertEquals(AslAnimationAsset.Type.WORD,entry.type)
            assertEquals("SIGN_${word.id.uppercase()}_HUMAN_AUTHORED_PREVIEW",entry.replacement!!.animationName)
            assertTrue(entry.metadata.usageNotes!!.contains("reference-authored"))
            assertFalse(entry.metadata.isLinguisticallyValidated)
        }
        val audit=registry.getAsJsonObject("everydayExpansion3")
        assertEquals(248,audit.get("preservedActions").asInt)
        assertEquals(10,audit.get("newLexicalActions").asInt)
        assertEquals(0,audit.get("qualifiedAslValidations").asInt)
        // Reference authorship cannot silently masquerade as retargeted/imported motion.
        val word=words.last()
        assertTrue(runCatching { AslVocabularyExpansion.merge(base,listOf(word.copy(construction="RETARGETED_PREVIEW"))) }.isFailure)
        assertTrue(runCatching { AslVocabularyExpansion.merge(base,listOf(word.copy(construction="CERTIFIED"))) }.isFailure)
    }

    @Test fun authoredWordsMixWithSpellingAndPreserveMeaningAndValidationBoundaries() {
        val plan=planner.plan("HELLO DEAF NICOLE")
        assertEquals(listOf("hello","deaf","letter_n","letter_i","letter_c","letter_o","letter_l","letter_e"),plan.queue.map {it.id})
        assertEquals(1,plan.queue.map {it.assetPath}.distinct().size)
        assertTrue(plan.queue.all(AslSingleAvatarPolicy::permits))
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,plan.mode)
        assertEquals(listOf("i_me","hungry"),ids("I hungry"))
        assertEquals(listOf("learn","now"),ids("Learn, now!"))
        assertEquals(listOf("today"),ids("today"))
        assertEquals(listOf("hear"),ids("hear"))
        assertEquals(listOf("now"),ids("now"))
        assertNull(catalog.findByAlias("wish"))
        assertNull(catalog.findByAlias("crave"))
        assertNull(catalog.findByAlias("thirsty"))
        assertEquals(listOf("thirsty"),planner.plan("THIRSTY").fingerspelledWords)
        val negative=planner.plan("don't understand")
        assertTrue(negative.fingerspelledWords.isNotEmpty())
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,negative.mode)
    }

    @Test fun s2r3TenNewEntriesUseActualNamedActionsAndRemainUnreviewed() {
        val expected = setOf("bathroom", "doctor", "nurse", "pain", "milk", "coffee", "tea", "orange", "apple", "bread")
        val batch = words.filter { it.id in expected }
        assertEquals(10, batch.size)
        val previous = AslAnimationCatalog.fromAssets(AslVocabularyExpansion.merge(base, words.filterNot { it.id in expected }), letters)
        val bytes = Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
        val gltf = JsonParser.parseString(String(bytes,20,ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        val names = gltf.getAsJsonArray("animations").map { it.asJsonObject.get("name").asString }
        for (word in batch) {
            assertNull("Not an old entry or alias: ${word.id}", previous.findByAlias(word.id))
            assertEquals(listOf(word.id), ids("  ${word.id.uppercase()}!  "))
            assertTrue(names.contains(word.animationName))
            assertEquals("REFERENCE_AUTHORED_PREVIEW", word.construction)
            assertEquals(3200L, word.durationMs)
            assertEquals(word.sourceSha256, hash(Files.readAllBytes(root.resolve(word.sourceAsset))))
            val entry = catalog.findByAlias(word.id)!!
            assertEquals(AslAnimationAsset.Type.WORD, entry.type)
            assertFalse(entry.metadata.isLinguisticallyValidated)
            assertTrue(entry.metadata.usageNotes!!.contains("Unreviewed"))
            assertTrue(AslSingleAvatarPolicy.permits(entry))
        }
        val audit=registry.getAsJsonObject("s2r3VocabularyExpansion")
        assertEquals(258,audit.get("preservedActions").asInt)
        assertEquals(10,audit.get("newLexicalActions").asInt)
        assertEquals(0,audit.get("qualifiedAslValidations").asInt)
    }

    @Test fun s2r3LexicalWordsAndSpellingShareOneQueueWithoutSentenceCertification() {
        for (word in listOf("bathroom", "doctor", "nurse", "pain", "milk", "coffee", "tea", "orange", "apple", "bread")) {
            val mixed = planner.plan("HELLO, ${word.uppercase()} NICOLE!")
            assertEquals(listOf("hello", word, "letter_n", "letter_i", "letter_c", "letter_o", "letter_l", "letter_e"), mixed.queue.map { it.id })
            assertEquals(listOf("nicole"), mixed.fingerspelledWords)
            assertEquals(1, mixed.queue.map { it.assetPath }.distinct().size)
            assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, mixed.mode)
        }
        assertEquals(listOf("milk", "coffee", "tea", "orange"), ids("Milk, coffee; tea & orange."))
        assertEquals(listOf("doctor", "nurse", "pain"), ids("DOCTOR NURSE PAIN"))
        assertEquals(listOf("unknownword"), planner.plan("unknownword").fingerspelledWords)
        assertNull(catalog.findByAlias("phd"))
        assertNull(catalog.findByAlias("latte"))
        assertNull(catalog.findByAlias("mocha"))
        assertNull(catalog.findByAlias("juice"))
        assertEquals(listOf("juice"), planner.plan("JUICE").fingerspelledWords)
        assertEquals(('a'..'z').map { "letter_$it" }, ids("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner.plan("Where is the bathroom?").mode)
    }

    @Test fun placesHaveDistinctRealActionsAndUnreviewedMeaningMetadata() {
        val ids = setOf("church", "library", "college", "university", "kitchen", "hotel")
        val batch = words.filter { it.id in ids }
        assertEquals(6, batch.size)
        val prior = AslAnimationCatalog.fromAssets(AslVocabularyExpansion.merge(base, words.filterNot { it.id in ids }), letters)
        val bytes = Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
        val g = JsonParser.parseString(String(bytes, 20, ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        val actions = g.getAsJsonArray("animations").map { it.asJsonObject.get("name").asString }
        for (word in batch) {
            assertNull(prior.findByAlias(word.id))
            assertEquals(listOf(word.id), this.ids("  ${word.id.uppercase()}! "))
            assertTrue(actions.contains(word.animationName))
            assertEquals("REFERENCE_AUTHORED_PREVIEW", word.construction)
            assertEquals(word.sourceSha256, hash(Files.readAllBytes(root.resolve(word.sourceAsset))))
            assertFalse(catalog.findByAlias(word.id)!!.metadata.isLinguisticallyValidated)
            assertTrue(AslSingleAvatarPolicy.permits(catalog.findByAlias(word.id)!!))
        }
        assertEquals(6, batch.map { it.animationName }.distinct().size)
        val audit = registry.getAsJsonObject("placesVocabularyExpansion")
        assertEquals(268, audit.get("preservedActions").asInt)
        assertEquals(6, audit.get("newLexicalActions").asInt)
        assertEquals(0, audit.get("qualifiedAslValidations").asInt)
    }

    @Test fun placesCombineWithOldSignsAndNamesWithoutInventingSentenceGrammar() {
        val plan = planner.plan("HELLO, LIBRARY NICOLE!")
        assertEquals(listOf("hello", "library", "letter_n", "letter_i", "letter_c", "letter_o", "letter_l", "letter_e"), plan.queue.map { it.id })
        assertEquals(1, plan.queue.map { it.assetPath }.distinct().size)
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, plan.mode)
        assertEquals(listOf("college", "university", "kitchen", "hotel", "church"), ids("College University Kitchen Hotel Church"))
        for (word in listOf("bank", "park", "airport", "museum")) {
            assertNull(catalog.findByAlias(word))
            assertEquals(listOf(word), planner.plan(word).fingerspelledWords)
        }
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, planner.plan("Where is the library?").mode)
    }
}
