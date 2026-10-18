package com.example.apphear

import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

class AslFingerspellingPostureTest {
    private val manifest = JsonParser.parseString(String(Files.readAllBytes(
        Path.of("src/aslOriginalWords/assets").resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject

    @Test fun everyLetterHasAuditedSigningWindowAndRetainsMovingLetterDuration() {
        val entries = manifest.getAsJsonObject("signingPosture").getAsJsonArray("letters")
        assertEquals(26, entries.size())
        assertEquals(('a'..'z').map { it.toString() }.toSet(), entries.map { it.asJsonObject.get("letter").asString }.toSet())
        for (entry in entries) {
            val e=entry.asJsonObject
            assertEquals(.50,e.get("sourceStartSeconds").asDouble,0.0)
            assertEquals(.18,e.get("holdSeconds").asDouble,0.0)
            assertTrue(e.get("sourceEndSeconds").asDouble > 1.2)
            val letter = manifest.getAsJsonArray("letters").single { it.asJsonObject.get("letter") == e.get("letter") }.asJsonObject
            assertEquals(kotlin.math.round(e.get("durationSeconds").asDouble*1000).toLong(), letter.get("durationMs").asLong)
            if (e.get("letter").asString in listOf("j","z")) assertTrue(letter.get("durationMs").asLong > 2000)
        }
    }

    @Test fun correctionRemainsUnreviewedAndPreservesLoveCorrectionProvenance() {
        assertEquals("UNREVIEWED_SIGNING_WINDOW",manifest.getAsJsonObject("signingPosture").get("status").asString)
        assertEquals("UNREVIEWED_CONTACT_CORRECTION",manifest.getAsJsonObject("loveCorrection").get("status").asString)
        assertEquals("bcd0e4b634b267baf3979f3193958520469ba91f69cd265406b76e9873d07d11",
            manifest.getAsJsonObject("signingPosture").get("sourceSha256").asString)
    }
}
