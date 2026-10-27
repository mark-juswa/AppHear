package com.example.apphear

import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

/** Original actions have their own 821-action gate. This separately pins the new source-derived tracks. */
class AslFbxVocabularyExpansionTest {
    private val folder = Path.of("src/aslOriginalWords/assets/asl_animations/original_words_v1")
    private val fixture = JsonParser.parseString(javaClass.getResource("/texttoasl/fbx-expansion-gates.json")!!.readText()).asJsonObject
    private val expected = fixture.getAsJsonArray("entries").map { it.asJsonObject }
    private val manifest = JsonParser.parseString(String(Files.readAllBytes(folder.resolve("integration-manifest.json")))).asJsonObject
    private val bytes = Files.readAllBytes(folder.resolve("fingerspelling-avatar.glb"))
    private val g = JsonParser.parseString(String(bytes,20,ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject

    @Test fun onlyScreenedAdditionsAreRegisteredAndTheirRealTracksMatch() {
        val actions = g.getAsJsonArray("animations").map { it.asJsonObject }
        val names = actions.map { it.get("name").asString }
        val additions = actions.drop(fixture.get("baselineActions").asInt).take(expected.size)
        assertEquals(41, expected.size)
        assertEquals(expected.map { it.get("animationName").asString }, additions.map { it.get("name").asString })
        assertEquals(862, fixture.get("baselineActions").asInt+expected.size)
        assertEquals(AslFingerspellingBundle.ACTION_COUNT, actions.size)
        assertEquals(names.size,names.toSet().size)
        for(e in expected) {
            val name=e.get("animationName").asString
            val action=additions.single { it.get("name").asString==name }
            assertEquals(name,e.get("sha256").asString,WordHandRepairEvidence.digest(g,bytes,action))
            assertTrue(action.getAsJsonArray("channels").all { it.asJsonObject.getAsJsonObject("target").get("path").asString=="rotation" })
        }
    }
    @Test fun sourceProvenanceCannotBeMistakenForLinguisticValidation() {
        val byId=manifest.getAsJsonArray("entries").map { it.asJsonObject }.associateBy { it.get("id").asString }
        assertEquals(0,fixture.get("qualifiedASLValidations").asInt)
        for(e in expected) {
            val row=byId.getValue(e.get("id").asString)
            assertEquals(e.get("sourceSha256").asString,row.get("sourceSha256").asString)
            assertEquals("ASL",row.get("sourceLanguage").asString)
            assertEquals("FBX",row.get("sourceFormat").asString)
            assertEquals("CC-BY-4.0",row.get("license").asString)
            assertEquals("UNREVIEWED",row.get("linguisticValidationStatus").asString)
            assertTrue(row.get("sourceSkeletalKeyTimesPreserved").asBoolean)
            val checks=row.getAsJsonObject("checks")
            assertTrue(checks.get("max_direction_error").asDouble < .00001)
            assertTrue(checks.get("max_inner_rotation_step_degrees").asDouble < 90.0)
        }
        for(id in fixture.getAsJsonArray("heldForContactReview"))assertFalse(byId.containsKey(id.asString))
        assertEquals(784, fixture.get("baselineLexicalEntries").asInt+expected.size)
        assertEquals(com.example.apphear.domain.texttoasl.AslIntegratedVocabulary.ENTRIES,manifest.get("totalLexicalEntries").asInt)
    }
}
