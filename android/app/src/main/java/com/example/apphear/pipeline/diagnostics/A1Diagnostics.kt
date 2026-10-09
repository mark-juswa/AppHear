package com.example.apphear.pipeline.diagnostics

import android.os.SystemClock
import com.example.apphear.pipeline.RuntimeLog
import java.util.concurrent.atomic.AtomicLong

/** Raw, debug-only A1 event stream. Parsing and gate decisions happen off-device. */
class A1Diagnostics(
    val mode: String,
    val runId: String,
) {
    private val sequence = AtomicLong(0L)

    fun nowNs(): Long = SystemClock.elapsedRealtimeNanos()

    fun event(name: String, vararg fields: Pair<String, Any?>) {
        val body = buildString {
            append("event=").append(name)
            append(" mode=").append(mode)
            append(" run_id=").append(sanitize(runId))
            append(" seq=").append(sequence.incrementAndGet())
            append(" event_ns=").append(nowNs())
            fields.forEach { (key, value) ->
                append(' ').append(key).append('=').append(sanitize(value?.toString() ?: "null"))
            }
        }
        RuntimeLog.i(TAG, body)
    }

    private fun sanitize(value: String): String = value.replace(Regex("\\s+"), "_")

    companion object {
        const val TAG = "AppHearA1"
    }
}
