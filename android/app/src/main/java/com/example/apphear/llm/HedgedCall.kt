package com.example.apphear.llm

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.selects.select
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Primary-first race with a delayed backup ("hedged request"). The primary starts at once. If it
 * fails, or has not answered after [hedgeAfterMs], the secondary starts too, and the first usable
 * answer (non-null) wins. Calls run in a detached [scope] so a slow blocking network call never
 * holds up the answer; the losing call is cancelled (best effort) and its result ignored.
 */
class HedgedCall(
    private val hedgeAfterMs: Long,
    private val clockMs: () -> Long,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) {
    class Attempt<T : Any>(val source: String, val call: suspend () -> T?)
    data class Answer<T : Any>(val value: T, val source: String, val latencyMs: Long)

    private class Done<T : Any>(val value: T?)

    suspend fun <T : Any> run(primary: Attempt<T>, secondary: Attempt<T>?): Answer<T>? {
        val started = clockMs()
        fun answer(value: T?, source: String) = value?.let { Answer(it, source, clockMs() - started) }
        val first = start(primary)
        var second: Deferred<T?>? = null
        try {
            val early = withTimeoutOrNull(hedgeAfterMs) { Done(first.await()) }
            if (early != null) {
                early.value?.let { return answer(it, primary.source) }
                if (secondary == null) return null
                return answer(start(secondary).also { second = it }.await(), secondary.source)
            }
            if (secondary == null) return answer(first.await(), primary.source)
            val backup = start(secondary).also { second = it }
            val firstWon = select<Pair<Boolean, T?>> {
                first.onAwait { true to it }
                backup.onAwait { false to it }
            }
            firstWon.second?.let { return answer(it, if (firstWon.first) primary.source else secondary.source) }
            return if (firstWon.first) answer(backup.await(), secondary.source)
            else answer(first.await(), primary.source)
        } finally {
            first.cancel()
            second?.cancel()
        }
    }

    private fun <T : Any> start(attempt: Attempt<T>): Deferred<T?> = scope.async {
        try {
            attempt.call()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            null
        }
    }
}
