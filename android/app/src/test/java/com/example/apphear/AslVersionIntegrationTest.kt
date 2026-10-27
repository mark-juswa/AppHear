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

/** Catalog union, actual packaged actions and real planner regression; never ASL certification. */
class AslVersionIntegrationTest {
    private val folder = Path.of("src/aslOriginalWords/assets")
    private val manifestBytes = Files.readAllBytes(folder.resolve(AslIntegratedVocabulary.MANIFEST))
    private val manifest = JsonParser.parseString(String(manifestBytes)).asJsonObject
    private val bundle = Files.readAllBytes(folder.resolve(AslFingerspellingBundle.PATH))
    private val g = JsonParser.parseString(String(bundle,20,ByteBuffer.wrap(bundle).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
    private val old = JsonParser.parseString(String(Files.readAllBytes(folder.resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject
    private val base = manifest.getAsJsonArray("baseEntries").map { raw -> val e=raw.asJsonObject
        AslAnimationAsset(e.get("id").asString,e.getAsJsonArray("english")[0].asString,AslFingerspellingBundle.PATH,
            AslAnimationAsset.Type.WORD,e.getAsJsonArray("english").map{it.asString},
            AslAnimationAsset.Replacement(null,e.get("animationName").asString,e.get("durationMs").asLong),
            SignDictionaryMetadata(avatarProfile=AslSingleAvatarPolicy.profile)) }
    private val letters=AslFingerspellingBundle.letters(old.getAsJsonArray("letters").map { raw -> val e=raw.asJsonObject
        AslFingerspellingBundle.Letter(e.get("letter").asString.single(),e.get("animationName").asString,e.get("durationMs").asLong) })
    private val words=manifest.getAsJsonArray("entries").map { raw -> val e=raw.asJsonObject
        AslIntegratedVocabulary.Word(e.get("id").asString,e.getAsJsonArray("english").map{it.asString},e.get("animationName").asString,
            e.get("durationMs").asLong,e.get("sourceSha256").asString,e.get("motionSha256").asString) }
    private val aliases=manifest.getAsJsonArray("aliases").map { raw -> val e=raw.asJsonObject
        AslIntegratedVocabulary.Alias(e.get("signId").asString,e.getAsJsonArray("english").map{it.asString}) }
    private val catalog=AslIntegratedVocabulary.merge(AslAnimationCatalog.fromAssets(base,letters),words,aliases)
    private fun hash(b:ByteArray)=MessageDigest.getInstance("SHA-256").digest(b).joinToString(""){"%02x".format(it)}

    @Test fun exactUnionHasRealNamedActionsAndNoAvatarSubstitution() {
        assertEquals(AslIntegratedVocabulary.MANIFEST_SHA256,hash(manifestBytes))
        assertEquals(AslFingerspellingBundle.SHA256,hash(bundle))
        assertEquals(AslIntegratedVocabulary.ENTRIES,catalog.getAssets().size)
        assertEquals(AslIntegratedVocabulary.ADDITIONS,words.size)
        val names=g.getAsJsonArray("animations").map{it.asJsonObject.get("name").asString}.toSet()
        assertEquals(AslFingerspellingBundle.ACTION_COUNT,names.size)
        for(asset in catalog.getAssets()) {
            assertTrue(asset.id,names.contains(asset.replacement!!.animationName))
            assertEquals(AslFingerspellingBundle.PATH,asset.assetPath)
            assertTrue(AslSingleAvatarPolicy.permits(asset))
            assertFalse(asset.metadata.isLinguisticallyValidated)
        }
        assertEquals(16,manifest.getAsJsonArray("externalReviewAlternatives").size())
        assertEquals(0,manifest.get("qualifiedAslValidations").asInt)
    }
    @Test fun allEnglishFormsSelectTheirMappedLexicalAction() {
        val planner=AslPhrasePlanner(catalog,completeWordFallback=true,dictionarySequenceMode=true)
        val forms=catalog.getAssets().flatMap{a->a.aliases.map{it to a.id}}.toMap()
        assertEquals(manifest.get("explicitEnglishForms").asInt,forms.size)
        for((form,id) in forms) assertEquals(form,listOf(id),planner.plan(form).queue.map{it.id})
    }
    @Test fun alphabetMixedWordsRepeatedLettersAndUnknownsKeepTheirQueue() {
        val planner=AslTranslationPlanner(catalog)
        for(word in listOf("NICOLE","ANNA","JAZZ","ACTION","QZXUNKNOWN")) {
            val result=planner.plan(word)
            if(catalog.findByAlias(word)==null) assertEquals(word,word.lowercase().map{"letter_$it"},result.queue.map{it.id})
        }
        val mixed=planner.plan("HELLO NICOLE")
        assertEquals(listOf("hello")+"nicole".map{"letter_$it"},mixed.queue.map{it.id})
        for(c in 'a'..'z') assertNotNull(catalog.findLetter(c))
        assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE,planner.plan("WHAT IS YOUR NAME?").mode)
        assertEquals("SIGN_YOUR",catalog.findByAlias("your")!!.replacement!!.animationName)
        assertEquals("SIGN_FINISH_HUMAN_AUTHORED_PREVIEW",catalog.findByAlias("finish")!!.replacement!!.animationName)
    }
    @Test fun duplicateIdsOrAliasesFailRatherThanSilentlyReplacingAMotion() {
        assertThrows(IllegalArgumentException::class.java) { AslIntegratedVocabulary.merge(AslAnimationCatalog.fromAssets(base,letters),words.dropLast(1),aliases) }
        assertThrows(IllegalArgumentException::class.java) { AslIntegratedVocabulary.merge(AslAnimationCatalog.fromAssets(base,letters),words,
            aliases+AslIntegratedVocabulary.Alias("love",listOf("hello"))) }
    }
    @Test fun onlyImportedWordsDeclareAuditedSyntheticRestPadding() {
        val addedIds=words.map{it.id}.toSet()
        for(asset in catalog.getAssets()) assertEquals(asset.id,
            if(asset.id in addedIds) .2 else 0.0, asset.syntheticPaddingSeconds, 0.0)
        for(c in 'a'..'z') assertEquals(0.0,catalog.findLetter(c)!!.syntheticPaddingSeconds,0.0)
    }
    @Test fun recoveredExportFramesDoNotBecomeInventedVocabularyOrValidatedSigns() {
        val previous = manifest.getAsJsonArray("previousDirect3dLexExpansions")
        assertEquals(49, previous[0].asJsonObject.get("newEntries").asInt)
        val recovered = manifest.getAsJsonArray("entries").map { it.asJsonObject }.filter {
            val checks = it.getAsJsonObject("checks") ?: return@filter false
            val reset = checks.get("excluded_export_reset")?.takeIf { value -> value.isJsonObject }
                ?.asJsonObject ?: return@filter false
            reset.getAsJsonObject("terminalHipReset")?.get("signature")?.asString == "PARTIALLY_BAKED_CONTAINER_RESET"
        }
        assertEquals(32, recovered.size)
        for (entry in recovered) {
            assertEquals("UNREVIEWED", entry.get("linguisticValidationStatus").asString)
            val checks = entry.getAsJsonObject("checks")
            assertTrue(checks.get("max_inner_rotation_step_degrees").asDouble < 90.0)
            assertTrue(checks.get("max_direction_error").asDouble < .01745)
            val reset = checks.getAsJsonObject("excluded_export_reset")
            assertTrue(reset.get("sourceBytesUnchanged").asBoolean)
            assertTrue(reset.get("retainedThroughSeconds").asDouble < reset.get("firstExcludedSeconds").asDouble)
        }
        assertNull(catalog.findByAlias("action")) // Static source data remains spelling fallback.
        assertEquals(785, manifest.get("totalLexicalEntries").asInt)
    }
}
