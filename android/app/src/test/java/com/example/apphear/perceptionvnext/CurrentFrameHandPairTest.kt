package com.example.apphear.perceptionvnext

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class CurrentFrameHandPairTest {
    @Test fun overlapsHandsAndPreservesAnatomicalOrder() {
        CurrentFrameHandPair().use { pair ->
            val leftStarted = CountDownLatch(1)
            val rightStarted = CountDownLatch(1)
            val result = pair.run({
                leftStarted.countDown()
                check(rightStarted.await(5, TimeUnit.SECONDS))
                "anatomical-left"
            }, {
                check(leftStarted.await(5, TimeUnit.SECONDS))
                rightStarted.countDown()
                "anatomical-right"
            })
            assertEquals(Pair("anatomical-left", "anatomical-right"), result)
        }
    }

    @Test fun rightFailureStillDrainsNativeLeftWorkBeforeReturning() {
        CurrentFrameHandPair().use { pair ->
            val rightFailed = CountDownLatch(1)
            val leftFinished = AtomicBoolean()
            val expected = IllegalArgumentException("right model")
            val actual = runCatching {
                pair.run({
                    check(rightFailed.await(5, TimeUnit.SECONDS))
                    leftFinished.set(true)
                }, { rightFailed.countDown(); throw expected })
            }.exceptionOrNull()
            assertSame(expected, actual)
            assertTrue(leftFinished.get())
        }
    }

    @Test fun leftFailureAndRightFailureAreBothReported() {
        CurrentFrameHandPair().use { pair ->
            val left = IllegalStateException("left model")
            val right = IllegalArgumentException("right model")
            val error = runCatching { pair.run({ throw left }, { throw right }) }.exceptionOrNull()
            assertSame(right, error)
            assertArrayEquals(arrayOf(left), requireNotNull(error).suppressed)
        }
    }

    @Test fun interruptionIsRestoredOnlyAfterWorkerDrains() {
        CurrentFrameHandPair().use { pair ->
            val completed = AtomicBoolean()
            try {
                Thread.currentThread().interrupt()
                val error = runCatching { pair.run({ completed.set(true) }, { Unit }) }.exceptionOrNull()
                assertTrue(error is InterruptedException)
                assertTrue(completed.get())
                assertTrue(Thread.currentThread().isInterrupted)
            } finally { Thread.interrupted() }
        }
    }

    @Test fun repeatedFramesNeverReuseResultsAndCloseRejectsNewWork() {
        val pair = CurrentFrameHandPair()
        repeat(100) { frame ->
            assertEquals(Pair(frame * 2, frame * 2 + 1), pair.run({ frame * 2 }, { frame * 2 + 1 }))
        }
        pair.close()
        pair.close()
        assertTrue(runCatching { pair.run({ 1 }, { 2 }) }.exceptionOrNull() is IllegalStateException)
    }
}
