package com.example.apphear.conversation

import android.os.SystemClock
import android.util.Log
import com.example.apphear.BuildConfig
import java.util.concurrent.ConcurrentHashMap

/**
 * Debug-only conversation-flow timing log (Phase 0 baseline). Every call is a no-op unless the
 * `conversationTimeline` build flag is on, and no call ever changes app behavior. Events carry
 * counts and durations only: never transcripts, glosses or other conversation content.
 */
object ConversationTimeline {
    const val TAG = "AppHearTurn"
    private const val FPS_SAMPLE_INTERVAL_MS = 1_000L

    private val liveScreens = ConcurrentHashMap<String, Int>()
    @Volatile private var lastFpsSampleMs = 0L

    val enabled: Boolean get() = BuildConfig.CONVERSATION_TIMELINE_ENABLED

    fun mark(event: String, vararg fields: Pair<String, Any?>) {
        if (!enabled) return
        Log.i(TAG, format(event, SystemClock.elapsedRealtime(), System.currentTimeMillis(), fields.toList()))
    }

    fun tap(screen: String, control: String) = mark("tap", "screen" to screen, "control" to control)

    fun screenCreated(screen: String) {
        if (!enabled) return
        val live = liveScreens.merge(screen, 1, Int::plus)
        mark("screen_created", "screen" to screen, "live" to live, "all_live" to liveSummary())
    }

    fun screenDestroyed(screen: String) {
        if (!enabled) return
        val live = liveScreens.merge(screen, -1, Int::plus)
        mark("screen_destroyed", "screen" to screen, "live" to live, "all_live" to liveSummary())
    }

    /** Called from the existing UI-thread frame callback; logs at most once per second. */
    fun recognitionFps(fps: Double) {
        if (!enabled) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastFpsSampleMs < FPS_SAMPLE_INTERVAL_MS) return
        lastFpsSampleMs = now
        mark("recognition_fps", "fps" to fps)
    }

    private fun liveSummary(): String =
        liveScreens.entries.sortedBy { it.key }.joinToString(",") { "${it.key}=${it.value}" }

    /** One JSON object per line so host tooling can parse logcat directly. */
    internal fun format(event: String, elapsedMs: Long, wallMs: Long, fields: List<Pair<String, Any?>>): String =
        buildString {
            append("{\"e\":").append(quote(event))
            append(",\"t\":").append(elapsedMs)
            append(",\"w\":").append(wallMs)
            for ((key, value) in fields) {
                append(',').append(quote(key)).append(':')
                append(
                    when (value) {
                        null -> "null"
                        is Boolean, is Int, is Long -> value.toString()
                        is Float -> if (value.isFinite()) value.toString() else "null"
                        is Double -> if (value.isFinite()) value.toString() else "null"
                        else -> quote(value.toString())
                    },
                )
            }
            append('}')
        }

    private fun quote(value: String): String = buildString {
        append('"')
        for (c in value) {
            when {
                c == '"' -> append("\\\"")
                c == '\\' -> append("\\\\")
                c < ' ' -> append("\\u%04x".format(c.code))
                else -> append(c)
            }
        }
        append('"')
    }
}
