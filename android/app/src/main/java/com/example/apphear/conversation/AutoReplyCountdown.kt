package com.example.apphear.conversation

/**
 * D2: the countdown shown after the avatar finishes signing. It ticks once a second with the
 * seconds left, then fires (opens Reply) unless [cancel] is called first. Scheduling is injected so
 * the logic runs in plain JVM tests; in the app it is a main-thread Handler. Not thread safe.
 */
class AutoReplyCountdown(
    private val delayMs: Long,
    private val schedule: (delayMs: Long, task: Runnable) -> Unit,
    private val unschedule: (task: Runnable) -> Unit,
    private val onTick: (secondsLeft: Int) -> Unit,
    private val onFire: () -> Unit,
) {
    private var remainingMs = 0L
    private var pending: Runnable? = null

    val running: Boolean get() = pending != null

    /** Starts (or restarts) the countdown from the full delay. */
    fun start() {
        stop()
        remainingMs = delayMs
        onTick(secondsLeft())
        scheduleNext()
    }

    /** Stops without firing. Returns whether a countdown was running. */
    fun cancel(): Boolean {
        val wasRunning = running
        stop()
        return wasRunning
    }

    private fun stop() {
        pending?.let(unschedule)
        pending = null
    }

    private fun scheduleNext() {
        // Step to the next whole second so the label counts 3, 2, 1 even for a 2.5 s delay.
        val step = (remainingMs - (secondsLeft() - 1) * 1_000L).coerceIn(1L, 1_000L)
        val task = Runnable {
            pending = null
            remainingMs -= step
            if (remainingMs <= 0L) {
                onFire()
            } else {
                onTick(secondsLeft())
                scheduleNext()
            }
        }
        pending = task
        schedule(step, task)
    }

    private fun secondsLeft(): Int = ((remainingMs + 999L) / 1_000L).toInt()
}
