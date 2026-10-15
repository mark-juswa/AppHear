package com.example.apphear.perceptionvnext

import com.google.gson.JsonParser
import java.io.File
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PhoneStage2TransitionProtocolTest {
    private fun protocol(): PhoneStage2TransitionProtocol {
        val bytes = File("src/debug/assets/" + PhoneStage2TransitionProtocol.ASSET).readBytes()
        val json = JsonParser.parseString(bytes.toString(Charsets.UTF_8)).asJsonObject
        val blocks = json.getAsJsonArray("blocks").map { item ->
            val row = item.asJsonObject
            PhoneStage2TransitionProtocol.Block(row["id"].asString,
                row.getAsJsonArray("glosses").map { it.asString }, row["review_negative"].asBoolean,
                row["instruction"].asString)
        }
        return PhoneStage2TransitionProtocol(json["profile_id"].asString, json["milestone"].asString,
            json["comparison_baseline_sha"].asString, json["label_schema"].asString, blocks,
            MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })
    }

    @Test fun canonicalAssetContainsTheMissingAdjacentRepeatAndHoldControls() {
        val profile = protocol()
        assertEquals(5, profile.blocks.size)
        assertEquals(7, profile.blocks.sumOf { it.glosses.size })
        assertEquals(listOf("HELLO", "HELLO"), profile.blocks[2].glosses)
        assertTrue(profile.blocks[3].reviewNegative)
        assertEquals(listOf("HELLO"), profile.blocks[3].glosses)
        assertTrue(profile.blocks[4].reviewNegative)
        assertTrue(profile.blocks[4].glosses.isEmpty())
        assertEquals(7, PhoneTransitionDiagnosticCohort.blocks.size)
        assertFalse(PhoneTransitionDiagnosticCohort.blocks.contains("C_REPEAT_HANDS_UP"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun protocolCannotSilentlyChangeItsPhysicalSequence() {
        val profile = protocol()
        profile.copy(blocks = profile.blocks.mapIndexed { index, block ->
            if (index == 2) block.copy(glosses = listOf("HELLO", "HOME")) else block
        })
    }

    @Test fun scopeValidationAllowsUnknownWithoutClaimingSignerQualification() {
        PhoneStage2TransitionProtocol.validateCaptureOptions(true, true, false, "UNKNOWN")
        PhoneStage2TransitionProtocol.validateCaptureOptions(true, true, false, "ASL_PROFICIENT")
    }

    @Test(expected = IllegalArgumentException::class)
    fun compactCaptureRefusesConcurrentHandCandidate() {
        PhoneStage2TransitionProtocol.validateCaptureOptions(true, true, true, "UNKNOWN")
    }

    @Test(expected = IllegalArgumentException::class)
    fun compactCaptureRequiresExplicitCausalDiagnosticOptIn() {
        PhoneStage2TransitionProtocol.validateCaptureOptions(false, true, false, "UNKNOWN")
    }

    @Test(expected = IllegalArgumentException::class)
    fun compactCaptureRefusesUnknownProficiencyLabels() {
        PhoneStage2TransitionProtocol.validateCaptureOptions(true, true, false, "PROVEN_ACCURATE")
    }
}
