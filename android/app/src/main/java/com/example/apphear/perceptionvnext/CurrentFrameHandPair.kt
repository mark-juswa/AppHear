package com.example.apphear.perceptionvnext

import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.Callable
import java.util.concurrent.ExecutionException
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

/** At most one frame in flight; both hands finish before the caller can release its frame. */
internal class CurrentFrameHandPair : AutoCloseable {
    private val worker = ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS,
        ArrayBlockingQueue(1), { task -> Thread(task, "AppHearV3Hand") },
        ThreadPoolExecutor.AbortPolicy())
    private var closed = false

    @Synchronized
    fun <T> run(left: () -> T, right: () -> T): Pair<T, T> {
        check(!closed) { "V3_HAND_PAIR_CLOSED" }
        val pending = worker.submit(Callable { left() })
        var interrupted = Thread.interrupted()
        var failure: Throwable? = null
        var rightValue: T? = null
        try { rightValue = right() } catch (error: Throwable) { failure = error }
        var leftValue: T? = null
        // Cancellation does not guarantee native inference has stopped. Always drain the worker.
        while (true) {
            try {
                leftValue = pending.get()
                break
            } catch (_: InterruptedException) {
                interrupted = true
            } catch (error: ExecutionException) {
                val cause = error.cause ?: error
                if (failure == null) failure = cause else if (failure !== cause) failure.addSuppressed(cause)
                break
            }
        }
        if (interrupted) {
            Thread.currentThread().interrupt()
            val error = InterruptedException("V3_HAND_PAIR_INTERRUPTED_AFTER_DRAIN")
            if (failure == null) failure = error else failure.addSuppressed(error)
        }
        failure?.let { throw it }
        @Suppress("UNCHECKED_CAST")
        return Pair(leftValue as T, rightValue as T)
    }

    @Synchronized
    override fun close() {
        if (closed) return
        closed = true
        // run() is serialized with close(), so no model or frame is still in use here.
        worker.shutdown()
    }
}
