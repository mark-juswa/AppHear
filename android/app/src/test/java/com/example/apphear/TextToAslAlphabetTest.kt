package com.example.apphear

import com.example.apphear.ui.texttoasl.AslAlphabetPilotContract
import com.google.gson.JsonParser
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TextToAslAlphabetTest {
    private val folder = Path.of("src", "aslAlphabet", "assets", "asl_animations", "vnext")

    @Test
    fun allLettersAndPriorAnimationsUseOneVerifiedBundle() {
        val root = JsonParser.parseString(String(Files.readAllBytes(folder.resolve("manifest.json")))).asJsonObject
        assertEquals(3, root.get("schemaVersion").asInt)
        assertEquals(7, root.getAsJsonArray("clips").size())
        assertEquals(20, root.getAsJsonArray("newClips").size())
        val letters = root.getAsJsonArray("letters").map { it.asJsonObject }
        assertEquals(24, letters.size)
        val digest = MessageDigest.getInstance("SHA-256")
        Files.newInputStream(folder.resolve("shared-alphabet.glb")).use { stream ->
            val chunk = ByteArray(64 * 1024)
            while (true) {
                val count = stream.read(chunk)
                if (count < 0) break
                digest.update(chunk, 0, count)
            }
        }
        val hash = digest.digest().joinToString("") { "%02x".format(it) }
        for ((index, clip) in letters.withIndex()) {
            val letter = 'c' + index
            AslAlphabetPilotContract.validateLetter(letter, clip.get("id").asString,
                clip.get("sourceId").asString, clip.get("type").asString,
                clip.get("asset").asString, clip.get("profile").asString,
                clip.get("rigProfile").asString, clip.get("animationName").asString,
                clip.get("durationMs").asLong, clip.get("sha256").asString, hash)
            assertEquals("SIGN_LETTER_${letter.uppercaseChar()}_FEMALEASL",
                clip.get("animationName").asString)
        }
        for (clip in root.getAsJsonArray("clips").map { it.asJsonObject } +
            root.getAsJsonArray("newClips").map { it.asJsonObject } + root.getAsJsonObject("idle")) {
            assertEquals(AslAlphabetPilotContract.ASSET, clip.get("asset").asString)
            assertEquals(hash, clip.get("sha256").asString)
        }
    }

    @Test
    fun rejectLetterIdentityAndHashDrift() {
        val hash = "a".repeat(64)
        fun verify(id: String = "letter_c", source: String = "C", actual: String = hash) =
            AslAlphabetPilotContract.validateLetter('c', id, source, "letter",
                AslAlphabetPilotContract.ASSET, AslAlphabetPilotContract.PROFILE,
                "FemaleASL-full-rig-341-875-342", "SIGN_LETTER_C_FEMALEASL", 1400, hash, actual)
        verify()
        assertTrue(runCatching { verify(id = "letter_d") }.isFailure)
        assertTrue(runCatching { verify(source = "D") }.isFailure)
        assertTrue(runCatching { verify(actual = "b".repeat(64)) }.isFailure)
    }
}
