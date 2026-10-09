package com.example.apphear.pipeline

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class A1SchedulingTest {
    @Test
    fun mailboxKeepsOnlyNewestPendingItem() {
        val discarded = mutableListOf<Pair<Int, A1DiscardReason>>()
        val mailbox = LatestOnlyMailbox<Int> { item, reason -> discarded += item to reason }

        assertTrue(mailbox.offer(1))
        assertTrue(mailbox.offer(2))

        assertEquals(2, mailbox.take())
        assertEquals(listOf(1 to A1DiscardReason.SUPERSEDED), discarded)
        mailbox.close()
    }

    @Test
    fun closeDiscardsPendingAndUnblocksConsumer() {
        val discarded = mutableListOf<Pair<Int, A1DiscardReason>>()
        val mailbox = LatestOnlyMailbox<Int> { item, reason -> discarded += item to reason }
        val finished = CountDownLatch(1)
        var result: Int? = 99
        val consumer = Thread {
            result = mailbox.take()
            finished.countDown()
        }
        consumer.start()

        mailbox.close()

        assertTrue(finished.await(1, TimeUnit.SECONDS))
        assertNull(result)
        assertFalse(mailbox.offer(3))
        assertEquals(listOf(3 to A1DiscardReason.SHUTDOWN), discarded)
        consumer.join()
    }

    @Test
    fun causalStoreNeverUsesFuturePose() {
        val store = CausalPoseStore<String>()
        store.publish(TimestampedValue(100, "old"))
        store.publish(TimestampedValue(300, "future"))

        val join = store.join(handTimestampNs = 200, maxPoseAgeNs = 150)

        assertEquals(CausalJoinStatus.VALID, join.status)
        assertEquals("old", join.pose?.value)
        assertEquals(100L, join.poseAgeNs)
    }

    @Test
    fun causalStoreRejectsMissingAndExpiredPose() {
        val store = CausalPoseStore<String>()
        store.publish(TimestampedValue(300, "future"))
        assertEquals(CausalJoinStatus.NO_CAUSAL_POSE, store.join(200, 100).status)

        store.publish(TimestampedValue(400, "latest"))
        val expired = store.join(600, 150)
        assertEquals(CausalJoinStatus.POSE_TOO_OLD, expired.status)
        assertEquals(200L, expired.poseAgeNs)
    }

    @Test
    fun causalStoreIgnoresOutOfOrderPosePublication() {
        val store = CausalPoseStore<String>()
        store.publish(TimestampedValue(200, "new"))
        store.publish(TimestampedValue(100, "stale"))

        assertEquals("new", store.join(250, 100).pose?.value)
    }

    @Test
    fun dequeuedItemSurvivesShutdownAndIsNotDiscarded() {
        val discarded = mutableListOf<Pair<Int, A1DiscardReason>>()
        val mailbox = LatestOnlyMailbox<Int> { item, reason -> discarded += item to reason }
        mailbox.offer(7)

        val inFlight = mailbox.take()
        mailbox.close()

        assertEquals(7, inFlight)
        assertTrue(discarded.isEmpty())
    }

    @Test
    fun concurrentProducerAndConsumerTerminateWithoutQueueGrowth() {
        val discarded = mutableListOf<Int>()
        val mailbox = LatestOnlyMailbox<Int> { item, _ -> synchronized(discarded) { discarded += item } }
        val consumed = mutableListOf<Int>()
        val consumer = Thread {
            while (true) {
                val item = mailbox.take() ?: break
                synchronized(consumed) { consumed += item }
            }
        }
        consumer.start()
        repeat(1_000) { mailbox.offer(it) }
        mailbox.close()
        consumer.join(1_000)

        assertFalse(consumer.isAlive)
        assertTrue(consumed.zipWithNext().all { (left, right) -> right > left })
        assertEquals(1_000, consumed.size + discarded.size)
    }
}
