package com.example.apphear.perceptionvnext

import java.util.Locale

/**
 * Phase 2 detection observability: counters plus per-stage latency distributions for the live analyzer.
 *
 * Design constraints, each tested in `DetectionMetricsTest`:
 *  - CHEAP ON THE CAMERA THREAD: every `record` is an array write under an uncontended monitor into a
 *    PREALLOCATED ring (no allocation per frame). Percentiles/formatting happen only in [snapshot], which the
 *    debug reporter calls from its own thread.
 *  - BOUNDED: [ringSize] samples per stage; at most [MAX_FAULT_CODES] distinct fault codes are tracked.
 *  - NO USER DATA: only numbers, stage names, and fault CODES (stable identifiers such as
 *    `APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP`). No messages, no frames, no landmarks, no words.
 *
 * Definitions (all measured by the app itself; none is a physical-device result until someone runs it on one):
 *  - input frames      : frames delivered to `analyze` (after CameraX's KEEP_ONLY_LATEST dropped the rest).
 *  - processed frames  : frames that completed without a fault.
 *  - estimated camera drops: frames CameraX never delivered because the analyzer was busy (or the sensor skipped),
 *    ESTIMATED from gaps in the camera's own sensor timestamps: a gap of >= 1.5x the reference interval counts
 *    `round(gap/interval) - 1` missing frames. The reference is the REQUESTED camera rate when known
 *    ([nominalFps]; the app fixes the front camera at 15 fps). Without it the reference is learned from the
 *    stream, which UNDER-counts once the analyzer is saturated: delivered frames are then spaced by processing time,
 *    so the sensor interval is not observable from them (found by running the app on an emulator). An estimate,
 *    not a count.
 *  - frame age         : camera timestamp -> analyzer start, only when the camera clock is plausibly comparable
 *    to elapsed-realtime (0..10 s), else not recorded.
 */
internal enum class DetectionStage {
    FRAME_AGE, PREPROCESS, POSE, POSE_DECODE, HAND_CROP, LEFT_HAND, RIGHT_HAND, HANDS_WALL, SEGMENTER, RECOGNIZER,
    FRAME_TOTAL, UI_HOP, END_TO_END,
}

internal data class StageStats(val n: Int, val p50: Double?, val p95: Double?, val max: Double?)

internal data class DetectionSnapshot(
    val inputFrames: Long,
    val processedFrames: Long,
    val estimatedCameraDrops: Long,
    val faults: Long,
    val faultsKnownCode: Long,
    val faultsUnknownCode: Long,
    val recoveryAttempts: Long,
    val recoverySuccesses: Long,
    val fatalStops: Long,
    val framesAfterFatal: Long,
    /** Frames per second from the camera's own timestamps of recently DELIVERED frames. */
    val deliveredFps: Double?,
    /** Frames per second of recently COMPLETED frames. */
    val processedFps: Double?,
    /** Share of wall time the analyzer spent processing frames over the recent window, 0..1. */
    val busyRatio: Double?,
    val faultCodes: Map<String, Long>,
    val stages: Map<DetectionStage, StageStats>,
) {
    fun toLogLine(): String {
        fun f(v: Double?) = if (v == null) "na" else String.format(Locale.ROOT, "%.1f", v)
        val sb = StringBuilder(384)
        sb.append("in=").append(inputFrames).append(" ok=").append(processedFrames)
            .append(" camDropEst=").append(estimatedCameraDrops)
            .append(" faults=").append(faults).append(" recov=").append(recoverySuccesses).append('/')
            .append(recoveryAttempts).append(" fatal=").append(fatalStops)
            .append(" fpsIn=").append(f(deliveredFps)).append(" fpsOk=").append(f(processedFps))
            .append(" busy=").append(f(busyRatio?.times(100.0))).append('%')
        for ((stage, s) in stages) if (s.n > 0) {
            sb.append(' ').append(stage.name.lowercase(Locale.ROOT)).append('=').append(f(s.p50)).append('/').append(f(s.p95))
        }
        if (faultCodes.isNotEmpty()) sb.append(" codes=").append(faultCodes.entries.joinToString(",") { "${it.key}:${it.value}" })
        return sb.toString()
    }
}

internal class DetectionMetrics(
    private val ringSize: Int = 256,
    private val recentFrames: Int = 64,
    /** Camera rate the app REQUESTED (not measured); null = learn the interval from the stream (weaker). */
    nominalFps: Double? = null,
) {
    private val nominalIntervalNs: Double? = nominalFps?.takeIf { it > 0.0 }?.let { 1e9 / it }

    private class Ring(size: Int) {
        val values = DoubleArray(size)
        var count = 0
        var next = 0
        fun add(v: Double) {
            values[next] = v
            next = (next + 1) % values.size
            if (count < values.size) count++
        }
        /** Order does not matter for percentiles: when full, the ring holds the newest `size` samples rotated. */
        fun copy(): DoubleArray = values.copyOf(count)
    }

    private val stages = DetectionStage.entries.associateWith { Ring(ringSize) }
    private val deliveredTimes = LongArray(recentFrames)   // camera timestamps (ns) of delivered frames
    private var deliveredCount = 0
    private var deliveredNext = 0
    private val completedTimes = LongArray(recentFrames)   // System.nanoTime of completed frames
    private val completedBusyMs = DoubleArray(recentFrames)
    private var completedCount = 0
    private var completedNext = 0
    private var intervalNs = 0.0
    private var lastTimestampNs = Long.MIN_VALUE
    private val codes = LinkedHashMap<String, Long>()

    private var inputFrames = 0L
    private var processed = 0L
    private var drops = 0L
    private var faults = 0L
    private var faultsKnown = 0L
    private var faultsUnknown = 0L
    private var recoveryAttempts = 0L
    private var recoverySuccesses = 0L
    private var fatalStops = 0L
    private var afterFatal = 0L

    /** Call once per delivered frame with the camera's sensor timestamp. */
    @Synchronized
    fun inputFrame(sourceTimestampNs: Long) {
        inputFrames++
        if (lastTimestampNs != Long.MIN_VALUE && sourceTimestampNs > lastTimestampNs) {
            val gap = (sourceTimestampNs - lastTimestampNs).toDouble()
            val reference = nominalIntervalNs ?: intervalNs
            if (reference > 0.0 && gap >= 1.5 * reference) {
                drops += Math.round(gap / reference) - 1
            } else if (nominalIntervalNs == null) {
                // Only plain intervals update the running estimate, so drops do not inflate it.
                intervalNs = if (intervalNs == 0.0) gap else 0.9 * intervalNs + 0.1 * gap
            }
        }
        if (sourceTimestampNs > lastTimestampNs) lastTimestampNs = sourceTimestampNs
        deliveredTimes[deliveredNext] = sourceTimestampNs
        deliveredNext = (deliveredNext + 1) % recentFrames
        if (deliveredCount < recentFrames) deliveredCount++
    }

    @Synchronized
    fun record(stage: DetectionStage, valueMs: Double) {
        if (valueMs.isFinite() && valueMs >= 0.0) stages.getValue(stage).add(valueMs)
    }

    /** A frame completed successfully; [totalMs] is its analyzer time. */
    @Synchronized
    fun frameProcessed(totalMs: Double = 0.0, nowNs: Long = System.nanoTime()) {
        processed++
        completedTimes[completedNext] = nowNs
        completedBusyMs[completedNext] = totalMs
        completedNext = (completedNext + 1) % recentFrames
        if (completedCount < recentFrames) completedCount++
    }

    @Synchronized
    fun fault(code: String, known: Boolean) {
        faults++
        if (known) faultsKnown++ else faultsUnknown++
        val key = if (codes.containsKey(code) || codes.size < MAX_FAULT_CODES) code else "OTHER"
        codes[key] = (codes[key] ?: 0L) + 1
    }

    @Synchronized fun recoveryAttempt(success: Boolean) {
        recoveryAttempts++
        if (success) recoverySuccesses++
    }

    @Synchronized fun fatal() { fatalStops++ }
    @Synchronized fun frameAfterFatal() { afterFatal++ }

    @Synchronized
    fun snapshot(): DetectionSnapshot {
        val statsByStage = stages.mapValues { (_, ring) ->
            val v = ring.copy().also { it.sort() }
            if (v.isEmpty()) StageStats(0, null, null, null)
            else StageStats(v.size, nearestRank(v, 0.5), nearestRank(v, 0.95), v.last())
        }
        return DetectionSnapshot(
            inputFrames, processed, drops, faults, faultsKnown, faultsUnknown, recoveryAttempts, recoverySuccesses,
            fatalStops, afterFatal, deliveredFps(), processedFps(), busyRatio(), LinkedHashMap(codes), statsByStage,
        )
    }

    private fun deliveredFps(): Double? {
        if (deliveredCount < 2) return null
        val newest = deliveredTimes[(deliveredNext - 1 + recentFrames) % recentFrames]
        val oldest = deliveredTimes[(deliveredNext - deliveredCount + recentFrames) % recentFrames]
        val span = newest - oldest
        return if (span <= 0) null else (deliveredCount - 1) * 1e9 / span
    }

    private fun processedFps(): Double? {
        if (completedCount < 2) return null
        val newest = completedTimes[(completedNext - 1 + recentFrames) % recentFrames]
        val oldest = completedTimes[(completedNext - completedCount + recentFrames) % recentFrames]
        val span = newest - oldest
        return if (span <= 0) null else (completedCount - 1) * 1e9 / span
    }

    private fun busyRatio(): Double? {
        if (completedCount < 2) return null
        val newest = completedTimes[(completedNext - 1 + recentFrames) % recentFrames]
        val oldest = completedTimes[(completedNext - completedCount + recentFrames) % recentFrames]
        val spanMs = (newest - oldest) / 1e6
        if (spanMs <= 0) return null
        var busy = 0.0
        // Busy time of every completed frame in the window except the oldest (its interval starts before the window).
        for (i in 1 until completedCount) busy += completedBusyMs[(completedNext - completedCount + i + recentFrames) % recentFrames]
        return (busy / spanMs).coerceIn(0.0, 1.0)
    }

    companion object {
        const val MAX_FAULT_CODES = 16

        /** Camera clock vs elapsed-realtime clock is only comparable on some devices; reject nonsense. */
        fun plausibleAgeMs(ageMs: Double): Double? = ageMs.takeIf { it.isFinite() && it >= 0.0 && it <= 10_000.0 }

        private fun nearestRank(sorted: DoubleArray, q: Double): Double =
            sorted[minOf(sorted.size - 1, maxOf(0, Math.ceil(q * sorted.size).toInt() - 1))]
    }
}
