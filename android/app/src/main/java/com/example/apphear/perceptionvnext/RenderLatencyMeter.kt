package com.example.apphear.perceptionvnext

/**
 * Capture-to-render accounting for the landmark overlay (bug: "overlay lags the real hand").
 *
 * The overlay draws the result of whichever analyzed frame finished last, while the preview behind it is live, so the visible
 * lag is (camera capture -> analyzer start) + analyzer time + (analyzer delivery -> UI draw). The first two were already
 * measured (Phase 2: FRAME_AGE, FRAME_TOTAL); this adds the last hop and the sum:
 *  - UI_HOP     : analyzer delivered the result -> overlay `onDraw` (UI-thread congestion shows up here).
 *  - END_TO_END : camera sensor timestamp -> overlay `onDraw`. Recorded only when the camera clock is plausibly comparable to
 *                 elapsed-realtime (same guard as FRAME_AGE); otherwise not recorded rather than guessed.
 * Also counted: frames analyzed but never drawn (sequence gaps), older results drawn after newer ones (out of order), and
 * redraws of an already drawn frame (not counted as new samples).
 *
 * Observation only. Numbers only (no landmarks, no frames).
 */
internal data class RenderLatencySnapshot(val rendered: Long, val skippedBeforeRender: Long, val outOfOrder: Long, val redraws: Long) {
    fun toLogFragment() = "render[n=$rendered skipped=$skippedBeforeRender stale=$outOfOrder redraw=$redraws]"
}

internal class RenderLatencyMeter(private val metrics: DetectionMetrics) {
    private var lastSequence = -1
    private var rendered = 0L
    private var skipped = 0L
    private var outOfOrder = 0L
    private var redraws = 0L

    /** [sequence] < 0 means the frame carries no timing (ignored). Times are `elapsedRealtimeNanos`-based, camera clock aside. */
    @Synchronized
    fun rendered(sequence: Int, sourceTimestampNs: Long, deliveredNs: Long, renderedNs: Long) {
        if (sequence < 0) return
        when {
            sequence == lastSequence -> { redraws++; return }
            sequence < lastSequence -> { outOfOrder++; return }
        }
        if (lastSequence >= 0) skipped += (sequence - lastSequence - 1)
        lastSequence = sequence
        rendered++
        metrics.record(DetectionStage.UI_HOP, (renderedNs - deliveredNs) / 1_000_000.0)
        DetectionMetrics.plausibleAgeMs((renderedNs - sourceTimestampNs) / 1_000_000.0)
            ?.let { metrics.record(DetectionStage.END_TO_END, it) }
    }

    @Synchronized
    fun snapshot() = RenderLatencySnapshot(rendered, skipped, outOfOrder, redraws)
}

/** UI-thread entry point; a no-op unless the analyzer installed a meter (debug builds). */
internal object RenderLatencyProbe {
    @Volatile var meter: RenderLatencyMeter? = null

    fun rendered(sequence: Int, sourceTimestampNs: Long, deliveredNs: Long, renderedNs: Long) {
        meter?.rendered(sequence, sourceTimestampNs, deliveredNs, renderedNs)
    }
}
