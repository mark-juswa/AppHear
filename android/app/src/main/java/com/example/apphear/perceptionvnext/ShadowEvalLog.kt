package com.example.apphear.perceptionvnext

import java.io.File
import java.io.IOException
import java.util.Locale
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

/**
 * Phase 1.1 shadow evaluation log. For every emitted sign event it records, side by side, what the original
 * behaviour would have done (commit every top-1) and what the Phase 1 commit gate decided, together with the
 * numbers needed to evaluate it later against INDEPENDENT human labels.
 *
 * Hard guarantees (each has a test in `ShadowEvalLogTest`):
 *  - OBSERVE ONLY: it receives an immutable [ShadowEventRecord] built from values the session has already
 *    computed. It has no reference to the sentence, the committer, the decoder or any model, so it cannot
 *    change recognition output and adds NO inference.
 *  - NEVER BLOCKS the camera thread: [record] is a non-blocking `offer` into a bounded queue; serialisation and
 *    file I/O run on a separate minimum-priority daemon thread. A full queue drops the record and counts it.
 *  - NEVER THROWS into the caller: every failure is swallowed and counted. After repeated sink failures the log
 *    disables itself (records are dropped, nothing accumulates) until the next [generationReset].
 *  - BOUNDED: queue capacity, per-file bytes, file count and file age are all capped ([RotatingFileShadowSink]).
 *  - PRIVACY: no images, video, landmarks, tensors, user or device identifiers. Content is limited to the
 *    fields in [ALLOWED_EVENT_KEYS] (predicted gloss names, probabilities, timings, configuration). The session
 *    id is random per process. The default build never creates this object (see `SHADOW_EVAL_ENABLED`).
 */
internal data class ShadowEventRecord(
    val wallClockUtcMs: Long,
    val configuration: String,
    val s2Package: String,
    val fallback: Boolean,
    val gateEnabled: Boolean,
    val floor: Double?,
    val handRule: Boolean,
    val eventId: Int,
    val top5Glosses: List<String>,
    val top1Probability: Float,
    val top2Probability: Float,
    val handSpanFraction: Double,
    val spanObservations: Int,
    val windowObservations: Int,
    /** Camera-clock ms from the start / end of the LOGICAL sign span back to the commit observation. */
    val spanStartAgoMs: Double,
    val spanEndAgoMs: Double,
    val s2InvocationMs: Double,
    val recognitionInvocationMs: Double,
    /** Camera timestamp of the commit observation -> decision, when the camera clock is verifiably comparable. */
    val captureToDecisionMs: Double?,
    /** What the Phase 1 policy decides for this event (computed even when the gate flag is off). */
    val gatedOutcome: CommitOutcome,
    val gatedReason: String,
    /** What the app actually did: COMMIT (a word entered the sentence) or WITHHELD. */
    val actuallyCommitted: Boolean,
)

internal interface ShadowSink {
    /** May throw; the caller isolates and counts failures. One call = one complete JSON line (no newline). */
    fun append(line: String)
    fun close()
}

/** Counters are monotonic for the lifetime of the log; read them for diagnostics and tests. */
internal class ShadowEvalLog(
    private val sink: ShadowSink,
    private val sessionId: String,
    private val runLabelProvider: () -> String = { "" },
    private val sessionMeta: Map<String, String> = emptyMap(),
    private val capacity: Int = DEFAULT_CAPACITY,
    private val maxConsecutiveFailures: Int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
) : AutoCloseable {
    private sealed interface Item {
        class Event(val seq: Long, val generation: Int, val label: String, val record: ShadowEventRecord) : Item
        class Marker(val type: String, val generation: Int, val label: String, val wallMs: Long) : Item
        object Stop : Item
    }

    private val queue = ArrayBlockingQueue<Item>(capacity)
    private val pending = AtomicInteger(0)
    private val closed = AtomicBoolean(false)
    @Volatile private var disabled = false
    @Volatile private var generation = 0
    @Volatile private var label = sanitizeRunLabel(runLabelProvider())
    private val seq = AtomicLong(0)
    private var consecutiveFailures = 0 // writer thread only

    val dropped = AtomicLong(0)
    val written = AtomicLong(0)
    val writeFailures = AtomicLong(0)
    val internalErrors = AtomicLong(0)
    val isDisabled: Boolean get() = disabled

    private val writer = Thread({ writerLoop() }, "apphear-shadow-eval").apply {
        isDaemon = true
        priority = Thread.MIN_PRIORITY
    }

    init {
        enqueue(Item.Marker("session_start", generation, label, System.currentTimeMillis()))
        writer.start()
    }

    /** Camera-thread entry point. Non-blocking, never throws. */
    fun record(record: ShadowEventRecord) {
        try {
            if (closed.get() || disabled) {
                dropped.incrementAndGet()
                return
            }
            if (!enqueue(Item.Event(seq.incrementAndGet(), generation, label, record))) dropped.incrementAndGet()
        } catch (_: Throwable) {
            internalErrors.incrementAndGet()
        }
    }

    /** A new camera generation: events restart at id 1, so mark the boundary; also re-enables a disabled log. */
    fun generationReset() {
        try {
            if (closed.get()) return
            generation++
            label = sanitizeRunLabel(runLabelProvider())
            disabled = false
            enqueue(Item.Marker("generation_reset", generation, label, System.currentTimeMillis()))
        } catch (_: Throwable) {
            internalErrors.incrementAndGet()
        }
    }

    /** Waits (bounded) until everything accepted so far has been handled. For tests and orderly shutdown. */
    fun flush(timeoutMs: Long): Boolean {
        val deadline = System.nanoTime() + timeoutMs * 1_000_000
        while (pending.get() > 0) {
            if (System.nanoTime() > deadline) return false
            Thread.sleep(2)
        }
        return true
    }

    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        try {
            // Best effort: summary line, then stop. Never blocks longer than the join timeout.
            val summary = Item.Marker("session_end", generation, label, System.currentTimeMillis())
            if (!queue.offer(summary)) dropped.incrementAndGet() else pending.incrementAndGet()
            queue.offer(Item.Stop)
            writer.join(CLOSE_JOIN_MS)
            if (writer.isAlive) writer.interrupt()
        } catch (_: Throwable) {
            internalErrors.incrementAndGet()
        } finally {
            try { sink.close() } catch (_: Throwable) { internalErrors.incrementAndGet() }
        }
    }

    internal fun isWriterAlive(): Boolean = writer.isAlive

    private fun enqueue(item: Item): Boolean {
        if (!queue.offer(item)) return false
        pending.incrementAndGet()
        return true
    }

    private fun writerLoop() {
        while (true) {
            val item = try { queue.take() } catch (_: InterruptedException) { return }
            if (item === Item.Stop) return
            try {
                write(item)
            } finally {
                pending.decrementAndGet()
            }
        }
    }

    private fun write(item: Item) {
        // A generation boundary is a recovery point: the writer-side failure streak starts over.
        if (item is Item.Marker && item.type == "generation_reset") consecutiveFailures = 0
        if (disabled && item is Item.Event) {
            dropped.incrementAndGet()
            return
        }
        val line = try {
            when (item) {
                is Item.Event -> eventJson(item)
                is Item.Marker -> markerJson(item)
                Item.Stop -> return
            }
        } catch (_: Throwable) {
            internalErrors.incrementAndGet()
            return
        }
        try {
            sink.append(line)
            written.incrementAndGet()
            consecutiveFailures = 0
        } catch (_: Throwable) {
            writeFailures.incrementAndGet()
            if (++consecutiveFailures >= maxConsecutiveFailures) disabled = true
        }
    }

    private fun markerJson(m: Item.Marker): String {
        val b = StringBuilder(256).append('{')
        b.str("schema", SCHEMA).append(',').str("type", m.type).append(',').str("sid", sessionId)
        b.append(',').num("gen", m.generation).append(',').str("run", m.label).append(',').num("wall_ms", m.wallMs)
        if (m.type == "session_start") for ((k, v) in sessionMeta) b.append(',').str("meta_$k", v)
        if (m.type == "session_end") {
            b.append(',').num("written", written.get()).append(',').num("dropped", dropped.get())
            b.append(',').num("write_failures", writeFailures.get()).append(',').num("internal_errors", internalErrors.get())
        }
        return b.append('}').toString()
    }

    private fun eventJson(i: Item.Event): String {
        val r = i.record
        val b = StringBuilder(512).append('{')
        b.str("schema", SCHEMA).append(',').str("type", "event").append(',').str("sid", sessionId)
        b.append(',').num("gen", i.generation).append(',').str("run", i.label).append(',').num("seq", i.seq)
        b.append(',').num("wall_ms", r.wallClockUtcMs)
        b.append(',').str("cfg", r.configuration).append(',').str("s2", r.s2Package)
        b.append(',').bool("fallback", r.fallback).append(',').bool("gate_on", r.gateEnabled)
        b.append(',').dec("floor", r.floor).append(',').bool("hand_rule", r.handRule)
        b.append(',').num("event", r.eventId)
        b.append(',').str("top1", r.top5Glosses.firstOrNull().orEmpty())
        b.append(",\"top5\":[").append(r.top5Glosses.joinToString(",") { "\"" + escape(it) + "\"" }).append(']')
        b.append(',').dec("p1", r.top1Probability.toDouble()).append(',').dec("p2", r.top2Probability.toDouble())
        b.append(',').dec("margin", (r.top1Probability - r.top2Probability).toDouble())
        b.append(',').dec("hand_frac", r.handSpanFraction)
        b.append(',').num("span_obs", r.spanObservations).append(',').num("win_obs", r.windowObservations)
        b.append(',').dec("start_ago_ms", r.spanStartAgoMs).append(',').dec("end_ago_ms", r.spanEndAgoMs)
        b.append(',').dec("s2_ms", r.s2InvocationMs).append(',').dec("rec_ms", r.recognitionInvocationMs)
        b.append(',').dec("lag_ms", r.captureToDecisionMs)
        b.append(',').str("legacy", "COMMIT")
        b.append(',').str("gated", r.gatedOutcome.name).append(',').str("reason", r.gatedReason)
        b.append(',').str("actual", if (r.actuallyCommitted) "COMMIT" else "WITHHELD")
        return b.append('}').toString()
    }

    private fun StringBuilder.str(k: String, v: String) = append('"').append(k).append("\":\"").append(escape(v)).append('"')
    private fun StringBuilder.num(k: String, v: Number) = append('"').append(k).append("\":").append(v.toString())
    private fun StringBuilder.bool(k: String, v: Boolean) = append('"').append(k).append("\":").append(v)
    private fun StringBuilder.dec(k: String, v: Double?): StringBuilder {
        append('"').append(k).append("\":")
        return if (v == null || !v.isFinite()) append("null") else append(String.format(Locale.ROOT, "%.4f", v))
    }

    companion object {
        const val SCHEMA = "apphear.shadow_event.v1"
        const val DEFAULT_CAPACITY = 256
        const val DEFAULT_MAX_CONSECUTIVE_FAILURES = 5
        private const val CLOSE_JOIN_MS = 1_000L

        /** The complete set of keys an `event` line may contain. A privacy test pins this list. */
        val ALLOWED_EVENT_KEYS: Set<String> = setOf(
            "schema", "type", "sid", "gen", "run", "seq", "wall_ms", "cfg", "s2", "fallback", "gate_on", "floor",
            "hand_rule", "event", "top1", "top5", "p1", "p2", "margin", "hand_frac", "span_obs", "win_obs",
            "start_ago_ms", "end_ago_ms", "s2_ms", "rec_ms", "lag_ms", "legacy", "gated", "reason", "actual",
        )

        /** Only [A-Za-z0-9_-], at most 64 characters: a run label can never carry free text or a path. */
        fun sanitizeRunLabel(raw: String): String = raw.trim().filter { it.isLetterOrDigit() && it.code < 128 || it == '_' || it == '-' }.take(64)

        fun escape(s: String): String {
            val b = StringBuilder(s.length + 8)
            for (c in s) when {
                c == '"' -> b.append("\\\"")
                c == '\\' -> b.append("\\\\")
                c.code < 0x20 -> b.append(String.format(Locale.ROOT, "\\u%04x", c.code))
                else -> b.append(c)
            }
            return b.toString()
        }

        /** Camera clock vs. elapsed-realtime clock is only comparable on some devices; reject nonsense. */
        fun plausibleLagMs(lagMs: Double): Double? = lagMs.takeIf { it.isFinite() && it >= 0.0 && it <= 10_000.0 }
    }
}

/**
 * Bounded JSONL file sink: at most [maxFiles] files of at most [maxFileBytes] each (default 8 x 256 KiB = 2 MiB),
 * files older than [maxAgeMs] are deleted when the sink opens. Oldest files go first. Throws [IOException] on any
 * I/O problem; [ShadowEvalLog] isolates that.
 */
internal class RotatingFileShadowSink(
    private val dir: File,
    private val sessionId: String,
    private val maxFileBytes: Long = 256 * 1024,
    private val maxFiles: Int = 8,
    private val maxAgeMs: Long = 14L * 24 * 3600 * 1000,
    private val maxLineChars: Int = 4096,
    private val nowMs: () -> Long = System::currentTimeMillis,
) : ShadowSink {
    private var writer: java.io.BufferedWriter? = null
    private var currentBytes = 0L
    private var index = 0

    override fun append(line: String) {
        if (line.length > maxLineChars) throw IOException("shadow line too long")
        val bytes = line.toByteArray(Charsets.UTF_8).size + 1
        if (writer == null || currentBytes + bytes > maxFileBytes) rotate()
        val w = writer ?: throw IOException("no writer")
        w.write(line)
        w.newLine()
        w.flush()
        currentBytes += bytes
    }

    override fun close() {
        writer?.close()
        writer = null
    }

    private fun rotate() {
        writer?.close()
        writer = null
        if (!dir.isDirectory && !dir.mkdirs() && !dir.isDirectory) throw IOException("cannot create $dir")
        prune()
        val file = File(dir, "shadow_${sessionId}_${index++}.jsonl")
        writer = file.bufferedWriter(Charsets.UTF_8)
        currentBytes = 0
    }

    private fun prune() {
        val files = dir.listFiles { f -> f.isFile && f.name.startsWith("shadow_") && f.name.endsWith(".jsonl") }
            ?.sortedWith(compareBy<File>({ it.lastModified() }, { it.name.length }, { it.name })).orEmpty().toMutableList()
        val cutoff = nowMs() - maxAgeMs
        files.filter { it.lastModified() < cutoff }.forEach { it.delete(); files.remove(it) }
        // Leave room for the file about to be created.
        while (files.size >= maxFiles) files.removeAt(0).delete()
    }
}
