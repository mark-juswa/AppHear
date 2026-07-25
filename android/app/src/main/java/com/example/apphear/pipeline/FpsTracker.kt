package com.example.apphear.pipeline

/**
 * Rolling landmarker throughput (S1+S2 pipeline fps) over a time window. Thread-safe: ticked from
 * the analysis thread. Reports fps as processed-frames per second across the buffered span, so it
 * converges to the true sustained rate. This is the number the >=15 fps gate measures.
 */
class FpsTracker(private val windowMs: Long = 1500L) {
    private val stamps = ArrayDeque<Long>()

    @Synchronized
    fun tick(now: Long = System.currentTimeMillis()): Double {
        stamps.addLast(now)
        while (stamps.isNotEmpty() && now - stamps.first() > windowMs) stamps.removeFirst()
        val span = now - (stamps.firstOrNull() ?: now)
        return if (span <= 0L || stamps.size < 2) 0.0 else (stamps.size - 1) * 1000.0 / span
    }

    @Synchronized
    fun frames(): Int = stamps.size
}
