package com.example.apphear

import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.example.apphear.domain.texttoasl.AslIntegratedVocabulary
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

/** Binds the new preview to independently checked mesh/source evidence, not ASL certification. */
class AslContactVocabularyExpansionTest {
    private val folder = Path.of("src/aslOriginalWords/assets/asl_animations/original_words_v1")
    private val fixture = JsonParser.parseString(
        javaClass.getResource("/texttoasl/contact-vocabulary-gates.json")!!.readText()
    ).asJsonObject
    private val bytes = Files.readAllBytes(folder.resolve("fingerspelling-avatar.glb"))
    private val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    private val g = JsonParser.parseString(String(bytes, 20, buffer.getInt(12))).asJsonObject
    private val manifest = JsonParser.parseString(
        String(Files.readAllBytes(folder.resolve("integration-manifest.json")))
    ).asJsonObject

    @Test fun onlyExplicitlyResolvedMotionIsAppendedAndProtectedSourceTracksSurvive() {
        val added = g.getAsJsonArray("animations").drop(fixture.get("baselineActions").asInt)
        assertEquals(1, added.size)
        val action = added.single().asJsonObject
        assertEquals(fixture.get("animationName").asString, action.get("name").asString)
        assertEquals(fixture.get("sha256").asString, WordHandRepairEvidence.digest(g, bytes, action))
        val edited = fixture.getAsJsonArray("editedBones").map { it.asString }.toSet()
        assertEquals(
            fixture.get("sourceProtectedChannelsSha256").asString,
            WordHandRepairEvidence.digest(g, bytes, action, "protected", edited)
        )
        assertEquals(863, AslFingerspellingBundle.ACTION_COUNT)
        assertEquals(785, AslIntegratedVocabulary.ENTRIES)
        for (channel in action.getAsJsonArray("channels")) {
            val target = channel.asJsonObject.getAsJsonObject("target")
            assertEquals("rotation", target.get("path").asString)
            val bone = g.getAsJsonArray("nodes")[target.get("node").asInt]
                .asJsonObject.get("name").asString
            val expected = fixture.getAsJsonObject("fingerPoses").get(bone) ?: continue
            val sample = action.getAsJsonArray("samplers")[channel.asJsonObject.get("sampler").asInt].asJsonObject
            val accessor = g.getAsJsonArray("accessors")[sample.get("output").asInt].asJsonObject
            val view = g.getAsJsonArray("bufferViews")[accessor.get("bufferView").asInt].asJsonObject
            val start = 28 + buffer.getInt(12) + (view.get("byteOffset")?.asInt ?: 0) +
                (accessor.get("byteOffset")?.asInt ?: 0)
            val stride = view.get("byteStride")?.asInt ?: 16
            for (key in 1 until accessor.get("count").asInt - 1) {
                val dot = (0..3).sumOf { component ->
                    buffer.getFloat(start + key * stride + component * 4).toDouble() *
                        expected.asJsonArray[component].asDouble
                }
                assertTrue("Full flat-hand pose must be reached: $bone", kotlin.math.abs(dot) > 1 - 1e-5)
            }
        }
    }

    @Test fun meshEvidenceAndSourceAttributionDoNotBecomeLinguisticCertification() {
        val entry = manifest.getAsJsonArray("entries").map { it.asJsonObject }
            .single { it.get("id").asString == "arrive" }
        assertEquals(fixture.get("sourceSha256").asString, entry.get("sourceSha256").asString)
        assertEquals("ASL", entry.get("sourceLanguage").asString)
        assertEquals("UNREVIEWED", entry.get("linguisticValidationStatus").asString)
        assertEquals(0, manifest.get("qualifiedAslValidations").asInt)
        val correction = entry.getAsJsonObject("handCorrection")
        assertTrue(correction.get("sourceThumbsPreserved").asBoolean)
        assertTrue(correction.get("maxWristShiftMm").asDouble < 40.0)
        assertTrue(correction.get("maximumHandOrientationMatrixError").asDouble < 1e-5)
        val evidence = correction.getAsJsonObject("technicalEvidence")
        assertEquals(347, evidence.get("sampledTrianglePoses").asInt)
        assertEquals(0, evidence.get("transverseCrossingFrames").asInt)
        assertEquals("NOT_TESTED", evidence.get("nativePlaybackAtRegistration").asString)
        val change = manifest.getAsJsonObject("contactVocabularyRepair")
        assertEquals(listOf("arrive"), change.getAsJsonArray("addedIds").map { it.asString })
        assertEquals(862, change.get("preservedActions").asInt)
        val ids = manifest.getAsJsonArray("entries").map { it.asJsonObject.get("id").asString }.toSet()
        for (held in listOf("proof", "divide", "blood", "believe", "escape", "express", "game", "conflict", "star", "cannot", "discuss")) {
            assertFalse("Unresolved preview must not be enabled: $held", held in ids)
        }
    }
}
