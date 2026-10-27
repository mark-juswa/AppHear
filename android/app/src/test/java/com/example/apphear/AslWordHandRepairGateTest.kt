package com.example.apphear

import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

/** Asset scope and regression evidence, not linguistic certification. */
class AslWordHandRepairGateTest {
    @Test fun replacementPaddingAppliesToLexicalAliasesAndCannotConsumeOrAlterLetters() {
        fun word(id: String) = AslAnimationAsset(id, id, "human.glb", AslAnimationAsset.Type.WORD,
            emptyList(), AslAnimationAsset.Replacement(null, "SAME", 2000))
        val words = listOf(word("first"), word("alias"))
        val result = AslFingerspellingBundle.withDurations(words, mapOf("SAME" to 3000L), mapOf("SAME" to .2))
        assertTrue(result.all { it.syntheticPaddingSeconds == .2 && it.replacement!!.durationMs == 3000L })
        assertThrows(IllegalArgumentException::class.java) {
            AslFingerspellingBundle.withDurations(words, emptyMap(), mapOf("MISSING" to .2))
        }
        assertThrows(IllegalArgumentException::class.java) {
            AslFingerspellingBundle.withDurations(words, mapOf("SAME" to 100L), mapOf("SAME" to .2))
        }
        assertThrows(IllegalArgumentException::class.java) {
            AslFingerspellingBundle.withDurations(words.map { it.copy(type = AslAnimationAsset.Type.LETTER) }, emptyMap(), mapOf("SAME" to .2))
        }
    }
    @Test fun original821ActionsMatchReviewedRepairOrUnchangedBaselineEvidence() {
        val bytes = Files.readAllBytes(Path.of("src/aslOriginalWords/assets").resolve(AslFingerspellingBundle.PATH))
        val g = JsonParser.parseString(String(bytes, 20, ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        val evidence = WordHandRepairEvidence
        assertEquals("7c6d930e077ba9d1be75c709153f98c1e9af4ca33c99fb2bfb96731288150a20", evidence.fixture.get("sourceBundleSha256").asString)
        assertFalse(evidence.fixture.get("qualifiedASLValidation").asBoolean)
        assertEquals(821, evidence.actions.size)
        var changed = 0
        var alphabet = 0
        var replacements = 0
        assertEquals(AslFingerspellingBundle.ACTION_COUNT, g.getAsJsonArray("animations").size())
        for (item in g.getAsJsonArray("animations").take(evidence.actions.size)) {
            val a = item.asJsonObject
            val name = a.get("name").asString
            val expected = evidence.actions.getValue(name)
            assertEquals(name, expected.get("sha256").asString, evidence.digest(g, bytes, a))
            if (expected.get("changed").asBoolean) {
                changed++
                if (expected.get("fullReplacement").asBoolean) replacements++ else {
                    val excluded = expected.getAsJsonArray("excludedFingerBones").map { it.asString }.toSet()
                    assertTrue(excluded.all { "Hand" in it && it.last().isDigit() })
                    assertEquals("Only scoped fingers change: $name", expected.get("protectedSha256").asString,
                        evidence.digest(g, bytes, a, "protected", excluded))
                    assertEquals("Original clocks: $name", expected.get("clockSha256").asString,
                        evidence.digest(g, bytes, a, "clock"))
                }
            }
            if (name.matches(Regex("SIGN_LETTER_[A-Z]_WOLF3D_PREVIEW"))) {
                assertFalse(expected.get("changed").asBoolean)
                alphabet++
            }
        }
        assertEquals(74, changed)
        assertEquals(38, replacements)
        assertEquals(26, alphabet)
    }
}
