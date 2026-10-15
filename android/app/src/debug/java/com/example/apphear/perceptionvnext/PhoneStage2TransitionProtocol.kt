package com.example.apphear.perceptionvnext

import org.json.JSONObject
import java.security.MessageDigest

/** Debug navigation/review contract only. No marker changes inference or recovery. */
internal data class PhoneStage2TransitionProtocol(
    val profileId: String,
    val milestone: String,
    val comparisonBaselineSha: String,
    val labelSchema: String,
    val blocks: List<Block>,
    val sha256: String,
) {
    data class Block(val id: String, val glosses: List<String>, val reviewNegative: Boolean, val instruction: String)

    init {
        require(profileId == PROFILE_ID && milestone == MILESTONE)
        require(comparisonBaselineSha == COMPARISON_BASELINE && labelSchema == LABEL_SCHEMA)
        require(sha256.matches(Regex("[0-9a-f]{64}")))
        require(blocks.map { it.id } == BLOCK_IDS)
        require(blocks.map { it.glosses } == listOf(
            listOf("HELLO", "HOME"), listOf("HELLO", "HOME"), listOf("HELLO", "HELLO"),
            listOf("HELLO"), emptyList<String>(),
        ))
        require(blocks.map { it.reviewNegative } == listOf(false, false, false, true, true))
        require(blocks.all { it.instruction.isNotBlank() })
    }

    companion object {
        const val ASSET = "phone_causal_recognition_01/stage2_transition_protocol.json"
        const val PROFILE_ID = "V3_STAGE2_COMPACT_01"
        const val MILESTONE = "RECOGNITION_V3_STAGE2_TRANSITION_CAPTURE_01"
        const val COMPARISON_BASELINE = "e196a8d501386091eae52f59df0fa349e26b43e2"
        const val LABEL_SCHEMA = "apphear.continuous_transition.human_boundaries.v2"
        val BLOCK_IDS = listOf("A_HANDS_DOWN", "B_HANDS_UP", "C_REPEAT_HANDS_UP", "D_SIGN_THEN_HOLD", "E_ORDINARY_MOVEMENT")
        val PROFICIENCY_VALUES = setOf("UNKNOWN", "NONEXPERT_ENGINEERING_SMOKE", "ASL_PROFICIENT")

        fun validateCaptureOptions(transitionEnabled: Boolean, causalEnabled: Boolean,
            parallelHands: Boolean, proficiency: String) {
            require(transitionEnabled && causalEnabled) { "STAGE2_REQUIRES_TRANSITION_DIAGNOSTICS" }
            require(!parallelHands) { "STAGE2_REQUIRES_SERIAL_BASELINE" }
            require(proficiency in PROFICIENCY_VALUES) { "INVALID_SIGNER_PROFICIENCY" }
        }

        fun parse(bytes: ByteArray): PhoneStage2TransitionProtocol {
            val document = JSONObject(bytes.toString(Charsets.UTF_8))
            require(document.getString("schema") == "apphear.word_transition_protocol.v1")
            require(document.getString("protected_baseline_sha") == PhoneTransitionDiagnosticCohort.BASELINE_SHA)
            val rows = document.getJSONArray("blocks")
            val blocks = (0 until rows.length()).map { index ->
                val row = rows.getJSONObject(index)
                val glosses = row.getJSONArray("glosses")
                Block(row.getString("id"), (0 until glosses.length()).map { glosses.getString(it) },
                    row.getBoolean("review_negative"), row.getString("instruction"))
            }
            val sha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            return PhoneStage2TransitionProtocol(document.getString("profile_id"), document.getString("milestone"),
                document.getString("comparison_baseline_sha"), document.getString("label_schema"), blocks, sha)
        }
    }
}
