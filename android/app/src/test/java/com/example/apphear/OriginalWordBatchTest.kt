package com.example.apphear

import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.example.apphear.domain.texttoasl.OriginalWordBatchCatalog
import com.example.apphear.domain.texttoasl.AslAvatarCatalogPolicy
import com.example.apphear.domain.texttoasl.SignDictionaryMetadata
import com.example.apphear.domain.texttoasl.AslTranslationPlanner
import com.example.apphear.domain.texttoasl.TextToAslPlan
import com.example.apphear.domain.texttoasl.AslGrammarRegistry
import com.example.apphear.domain.texttoasl.EverydayAslExpression
import com.example.apphear.domain.texttoasl.ExistingAslAlias
import com.example.apphear.domain.texttoasl.AslSingleAvatarPolicy
import com.example.apphear.domain.texttoasl.AslResidentAvatarBundle
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import org.junit.Assert.*
import org.junit.Test

class OriginalWordBatchTest {
    private val assetRoot = Path.of("src/aslOriginalWords/assets")
    private val basePath = Path.of("src/main/assets/asl_animations/manifest.json")
    private val root by lazy { JsonParser.parseString(String(Files.readAllBytes(assetRoot.resolve(OriginalWordBatchCatalog.MANIFEST)))).asJsonObject }
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    private fun originalAsset(clip: JsonObject) = AslAnimationAsset(clip.get("id").asString,
        clip.get("displayText").asString, clip.get("asset").asString,
        AslAnimationAsset.Type.valueOf(clip.get("type").asString.uppercase()),
        clip.getAsJsonArray("aliases").map { it.asString })
    private val base by lazy { JsonParser.parseString(String(Files.readAllBytes(basePath))).asJsonObject
        .getAsJsonArray("clips").map { originalAsset(it.asJsonObject) } }
    private val overrides by lazy { root.getAsJsonArray("replacements").map {
        val c = it.asJsonObject
        OriginalWordBatchCatalog.Override(c.get("id").asString,c.get("asset").asString,
            c.get("fallbackAsset").asString,c.get("animationName").asString,c.get("durationMs").asLong)
    } }
    private val added by lazy { root.getAsJsonArray("newClips").map {
        val c = it.asJsonObject
        originalAsset(c).copy(replacement = AslAnimationAsset.Replacement(null,
            c.get("animationName").asString,c.get("durationMs").asLong))
    } }
    private val merged by lazy { OriginalWordBatchCatalog.merge(base,overrides,added) }

    @Test fun all203PayloadsMatchPinnedManifestAndNamedAnimation() {
        assertEquals(OriginalWordBatchCatalog.MANIFEST_SHA256,hash(Files.readAllBytes(assetRoot.resolve(OriginalWordBatchCatalog.MANIFEST))))
        assertEquals(root.get("baseManifestSha256").asString,hash(Files.readAllBytes(basePath)))
        val entries = (root.getAsJsonArray("replacements") + root.getAsJsonArray("newClips")).map { it.asJsonObject }
        assertEquals(203,entries.size)
        for (clip in entries) {
            val path = clip.get("asset").asString
            OriginalWordBatchCatalog.validatePath(path)
            val bytes = Files.readAllBytes(assetRoot.resolve(path))
            assertEquals(clip.get("bytes").asLong,bytes.size.toLong())
            assertEquals(clip.get("sha256").asString,hash(bytes))
            val header = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
            assertEquals(0x46546c67,header.getInt(0)); assertEquals(2,header.getInt(4))
            assertEquals(bytes.size,header.getInt(8))
            val gltf = JsonParser.parseString(String(bytes,20,header.getInt(12))).asJsonObject
            assertEquals(1,gltf.getAsJsonArray("animations").size())
            assertEquals(clip.get("animationName").asString,gltf.getAsJsonArray("animations")[0].asJsonObject.get("name").asString)
            assertTrue(clip.get("durationMs").asLong in 1..10_000)
        }
    }

    @Test fun actualHumanCatalogSupportsRequestedSequencesWithoutLegacyFallback() {
        val selected = AslAvatarCatalogPolicy.originalHuman(merged)
        assertEquals(204, selected.size)
        val planner = AslPhrasePlanner(AslAnimationCatalog.fromAssets(selected), dictionarySequenceMode = true)
        for (input in listOf("hello beautiful", "HELLO BEAUTIFUL", "hello, beautiful!")) {
            val plan=planner.plan(input)
            assertEquals(listOf("hello", "beautiful"), plan.queue.map { it.id })
            assertTrue(plan.unsupportedTokens.isEmpty())
            assertTrue(plan.queue.all { it.metadata.avatarProfile == SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN })
            assertTrue(plan.queue.all { it.originalFallback() == null })
        }
        assertEquals(listOf("thank_you"), planner.plan("thank you").queue.map { it.id })
        val partial=planner.plan("hello unknownword")
        assertEquals(listOf("hello"), partial.queue.map { it.id })
        assertEquals(listOf("unknownword"), partial.unsupportedTokens)
    }

    @Test fun residentAvatarCopiesAll203MotionsWithoutChangingSkeletonOrKeyframes() {
        val bundleBytes = Files.readAllBytes(assetRoot.resolve(AslResidentAvatarBundle.PATH))
        assertEquals(AslResidentAvatarBundle.SHA256, hash(bundleBytes))
        fun json(bytes: ByteArray) = JsonParser.parseString(String(bytes,20,
            ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        val bundle = json(bundleBytes)
        val named = bundle.getAsJsonArray("animations").associateBy { it.asJsonObject.get("name").asString }
        assertEquals(203,named.size)
        fun accessorBytes(bytes: ByteArray, document: JsonObject, index: Int): ByteArray {
            val accessor = document.getAsJsonArray("accessors")[index].asJsonObject
            val view = document.getAsJsonArray("bufferViews")[accessor.get("bufferView").asInt].asJsonObject
            val binStart = 28 + ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12)
            val start = binStart + (view.get("byteOffset")?.asInt ?: 0)
            return bytes.copyOfRange(start,start+view.get("byteLength").asInt)
        }
        for (entry in (root.getAsJsonArray("replacements") + root.getAsJsonArray("newClips"))) {
            val clip=entry.asJsonObject
            val bytes=Files.readAllBytes(assetRoot.resolve(clip.get("asset").asString))
            val source=json(bytes)
            for (key in listOf("nodes","skins","meshes","materials","textures","images","samplers","scenes","scene"))
                assertEquals(key,source.get(key),bundle.get(key))
            val before=source.getAsJsonArray("animations")[0].asJsonObject
            val after=named.getValue(clip.get("animationName").asString).asJsonObject
            assertEquals(before.get("channels"),after.get("channels"))
            val beforeSamplers=before.getAsJsonArray("samplers")
            val afterSamplers=after.getAsJsonArray("samplers")
            assertEquals(beforeSamplers.size(),afterSamplers.size())
            for (i in 0 until beforeSamplers.size()) {
                val a=beforeSamplers[i].asJsonObject; val b=afterSamplers[i].asJsonObject
                assertEquals(a.get("interpolation"),b.get("interpolation"))
                for (key in listOf("input","output")) {
                    val oldIndex=a.get(key).asInt; val newIndex=b.get(key).asInt
                    val old=source.getAsJsonArray("accessors")[oldIndex].asJsonObject.deepCopy()
                    val new=bundle.getAsJsonArray("accessors")[newIndex].asJsonObject.deepCopy()
                    old.remove("bufferView"); new.remove("bufferView")
                    assertEquals(old,new)
                    assertArrayEquals(accessorBytes(bytes,source,oldIndex),accessorBytes(bundleBytes,bundle,newIndex))
                }
            }
        }
        val registry=JsonParser.parseString(String(Files.readAllBytes(assetRoot.resolve(AslResidentAvatarBundle.MANIFEST))))
            .asJsonObject.getAsJsonArray("animations").map { e -> val c=e.asJsonObject
                AslResidentAvatarBundle.Motion(c.get("id").asString,c.get("animationName").asString,
                    c.get("durationMs").asLong,c.get("sourceAsset").asString) }
        val human=AslAvatarCatalogPolicy.originalHuman(merged)
        val resident=AslResidentAvatarBundle.map(human,registry)
        assertEquals(1,resident.map { it.assetPath }.distinct().size)
        assertEquals(human.map { it.metadata },resident.map { it.metadata })
        assertEquals(human.map { it.replacement!!.animationName },resident.map { it.replacement!!.animationName })
        assertTrue(resident.all { it.originalFallback()==null })
        assertEquals(0.0,resident.single { it.id=="idle" }.neutralFrameSeconds)
        assertThrows(IllegalArgumentException::class.java) { AslResidentAvatarBundle.map(human,registry.dropLast(1)) }
    }

    @Test fun goodbyeUsesRealByeMotionAndNameNeverUsesCallingOrLegacyPhrases() {
        val human = AslAvatarCatalogPolicy.originalHuman(merged)
        val entries = JsonParser.parseString(String(Files.readAllBytes(Path.of(
            "src/main/assets/asl_animations/existing_aliases_asl.json")))).asJsonObject.getAsJsonArray("aliases")
        var selected = human
        for (entry in entries) {
            val e = entry.asJsonObject
            val alias = ExistingAslAlias(e.get("signId").asString, e.getAsJsonArray("english").map { it.asString },
                e.get("asset").asString, e.get("sha256").asString, e.get("reference").asString)
            selected = alias.apply(selected, hash(Files.readAllBytes(assetRoot.resolve(alias.assetPath))))
        }
        assertEquals(human.size, selected.size)
        val planner = AslPhrasePlanner(AslAnimationCatalog.fromAssets(selected), dictionarySequenceMode = true)
        for (text in listOf("bye", "goodbye", "GOODBYE!")) {
            val queue = planner.plan(text).queue
            assertEquals(listOf("bye"), queue.map { it.id })
            assertEquals("SIGN_BYE",queue.single().replacement!!.animationName)
            assertTrue(AslSingleAvatarPolicy.permits(queue.single()))
            assertNull(queue.single().originalFallback())
        }
        assertTrue(planner.plan("name").queue.isEmpty())
        assertEquals(listOf("name"),planner.plan("name").unsupportedTokens)
        assertEquals(listOf("hello","beautiful","bye"),planner.plan("hello beautiful goodbye").queue.map { it.id })
        assertTrue(planner.plan("name").queue.none { it.id == "call__to_call_someone_s_name" })
    }

    @Test fun everydayExpressionsUseActualSelectedHumanCatalogWithoutInventedAssets() {
        val entries = JsonParser.parseString(String(Files.readAllBytes(Path.of("src/main/assets/asl_animations/everyday_asl.json"))))
            .asJsonObject.getAsJsonArray("expressions").map { Gson().fromJson(it, EverydayAslExpression::class.java) }
        val catalog = AslAnimationCatalog.fromAssets(AslAvatarCatalogPolicy.originalHuman(merged))
        val planner = AslTranslationPlanner(catalog, AslGrammarRegistry(everydayExpressions = entries))
        for (entry in entries) for (input in entry.english) {
            val plan = planner.plan(input)
            assertEquals(input, entry.id, plan.ruleId)
            assertNotEquals(TextToAslPlan.Mode.VALIDATED_PHRASE, plan.mode)
            if (entry.previewSignId == null) assertTrue(input, plan.queue.isEmpty())
            else assertEquals(listOf(entry.previewSignId), plan.queue.map { it.id })
            for (asset in plan.queue) {
                assertTrue(Files.exists(assetRoot.resolve(asset.assetPath)))
                assertNull(asset.originalFallback())
                assertEquals(SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN, asset.metadata.avatarProfile)
            }
            println("APPHEAR_EVERYDAY_RESULT=" + Gson().toJson(mapOf("input" to input, "id" to plan.ruleId,
                "mode" to plan.mode.name, "assetIds" to plan.queue.map { it.id },
                "missingCompatibleSigns" to plan.unsupportedTokens, "notice" to plan.translationNotice,
                "linguisticallyValidated" to false)))
        }
        assertEquals(listOf("hello", "beautiful"),planner.plan("HELLO BEAUTIFUL").queue.map { it.id })
        assertTrue(planner.plan("It's hot today!").queue.isEmpty())
        assertTrue(planner.plan("My name is Nicole").queue.isEmpty())
    }

    @Test fun requestedExpressionsExposeRealAssetsAndUnvalidatedSentenceLimits() {
        val catalog = AslAnimationCatalog.fromAssets(AslAvatarCatalogPolicy.originalHuman(merged))
        val planner = AslTranslationPlanner(catalog)
        val expressions = listOf("Hello", "Beautiful", "Hello beautiful", "What is your name?", "How are you?",
            "Where are you going?", "Thank you", "Good morning", "I need help", "I am hungry", "I am a student",
            "Can you help me?", "What time is it?", "Nice to meet you", "See you tomorrow")
        for (text in expressions) {
            val plan = planner.plan(text)
            assertNotEquals(text,TextToAslPlan.Mode.VALIDATED_PHRASE,plan.mode)
            assertTrue(text,plan.queue.all { Files.exists(assetRoot.resolve(it.assetPath)) })
            assertTrue(text,plan.queue.all { !it.metadata.isLinguisticallyValidated })
            if (text.contains('?')) assertTrue(text,plan.translationNotice!!.contains("not validated"))
            println("APPHEAR_EXPRESSION_RESULT=" + Gson().toJson(mapOf("input" to text,
                "mode" to plan.mode.name, "intent" to plan.analysis?.intent?.name,
                "assetIds" to plan.queue.map { it.id }, "unsupportedWords" to plan.unsupportedTokens,
                "notice" to plan.translationNotice, "linguisticallyValidated" to false)))
        }
        assertEquals(listOf("hello"),planner.plan("Hi!").queue.map { it.id })
        assertEquals(listOf("hello","beautiful"),planner.plan("HELLO,   BEAUTIFUL!").queue.map { it.id })
        assertEquals(listOf("good","morning"),planner.plan("Good morning").queue.map { it.id })
        assertEquals(listOf("i_me","need","help"),planner.plan("I need help").queue.map { it.id })
        val nameQuestion = planner.plan("What is your name?")
        assertTrue(nameQuestion.unsupportedTokens.contains("name"))
        assertTrue(planner.plan("I am not a student").queue.isEmpty())
    }

    @Test fun approvedMeaningsStaySeparateAndLongestMatchingUsesExactClip() {
        val planner = AslPhrasePlanner(AslAnimationCatalog.fromAssets(merged),completeWordFallback=true)
        val cases = mapOf("right" to "right", "right direction" to "right_direction",
            "father" to "father", "dad" to "dad", "mother" to "mother", "mom" to "mom",
            "big" to "big", "large" to "large", "go" to "go", "go to" to "go_to",
            "hard" to "hard", "hard solid" to "hard_solid", "letter" to "letter",
            "letter mail" to "letter_mail", "call" to "call", "call someone's name" to "call_someones_name",
            "play" to "play", "play a game" to "play_game", "turn" to "turn", "turn around" to "turn_around")
        for ((text,id) in cases) {
            val plan=planner.plan(text)
            assertEquals(text,listOf(id),plan.queue.map { it.id })
            assertTrue(text,plan.unsupportedTokens.isEmpty())
        }
        for (entry in added) for (alias in entry.aliases) {
            assertEquals(alias,listOf(entry.id),planner.plan(alias).queue.map { it.id })
        }
    }

    @Test fun replacementFallbackAndAllOriginalAliasesArePreserved() {
        assertEquals(273,merged.size)
        val catalog=AslAnimationCatalog.fromAssets(merged)
        for (entry in base) {
            val active=merged.single { it.id==entry.id }
            assertEquals(entry.aliases,active.aliases)
            if (overrides.any { it.id==entry.id }) {
                assertEquals(entry,active.originalFallback())
                assertTrue(active.assetPath.startsWith(OriginalWordBatchCatalog.PREFIX))
            } else assertEquals(entry,active)
            for (alias in entry.aliases) assertEquals(entry.id,catalog.findByAlias(alias)?.id)
        }
        assertEquals(base.single { it.id=="idle" },catalog.findByAlias("stand"))
        assertFalse(Files.exists(assetRoot.resolve(OriginalWordBatchCatalog.PREFIX+"stand.glb")))
        assertEquals(2,merged.count { it.type==AslAnimationAsset.Type.LETTER })
    }

    @Test fun missingAndDuplicateReplacementCannotExposePartialCatalog() {
        assertThrows(IllegalArgumentException::class.java) { OriginalWordBatchCatalog.merge(base,overrides.dropLast(1),added) }
        assertThrows(IllegalArgumentException::class.java) { OriginalWordBatchCatalog.merge(base,overrides.dropLast(1)+overrides.first(),added) }
        assertThrows(IllegalArgumentException::class.java) { OriginalWordBatchCatalog.merge(base,overrides,added.dropLast(1)) }
    }

    @Test fun aliasCollisionAndUntrustedPathAreRejected() {
        val collision=added.dropLast(1)+added.last().copy(aliases=listOf("hello"))
        assertThrows(IllegalArgumentException::class.java) { OriginalWordBatchCatalog.merge(base,overrides,collision) }
        for(path in listOf("../hello.glb",OriginalWordBatchCatalog.PREFIX+"../hello.glb","asl_animations/vnext/shared-alphabet.glb")) {
            assertThrows(IllegalArgumentException::class.java) { OriginalWordBatchCatalog.validatePath(path) }
        }
    }
}
