package com.example.apphear.conversation

import android.content.Context
import org.json.JSONObject

/** Tunable conversation-flow timings, shipped as [ASSET] so they can change without code edits. */
data class ConversationFlowPolicy(val autoReplyDelayMs: Long) {
    init {
        require(autoReplyDelayMs in MIN_AUTO_REPLY_DELAY_MS..MAX_AUTO_REPLY_DELAY_MS) {
            "[conversation/policy] autoReplyDelayMs out of range"
        }
    }

    companion object {
        const val ASSET = "conversation/flow_policy_v1.json"
        const val SCHEMA_VERSION = 1
        const val MIN_AUTO_REPLY_DELAY_MS = 1_000L
        const val MAX_AUTO_REPLY_DELAY_MS = 10_000L

        /** Fails loudly on a schema mismatch instead of guessing at the fields. */
        fun parse(schemaVersion: Int, autoReplyDelayMs: Long): ConversationFlowPolicy {
            require(schemaVersion == SCHEMA_VERSION) { "[conversation/policy] schema mismatch" }
            return ConversationFlowPolicy(autoReplyDelayMs)
        }

        fun load(context: Context): ConversationFlowPolicy {
            val json = JSONObject(context.assets.open(ASSET).bufferedReader().use { it.readText() })
            return parse(json.getInt("schemaVersion"), json.getLong("autoReplyDelayMs"))
        }
    }
}
