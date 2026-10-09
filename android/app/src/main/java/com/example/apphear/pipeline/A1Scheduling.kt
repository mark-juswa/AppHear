package com.example.apphear.pipeline

import java.util.ArrayDeque
import java.util.concurrent.Semaphore
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

enum class A1DiscardReason {
    SUPERSEDED,
    SHUTDOWN,
}

/**
 * A blocking, capacity-one, latest-only mailbox. A producer never waits. Replacing or closing a
 * pending item invokes [onDiscard], which is also where owned frame references are released.
 */
class LatestOnlyMailbox<T>(
    private val onDiscard: (T, A1DiscardReason) -> Unit,
) {
    private val pending = AtomicReference<T?>(null)
    private val available = Semaphore(0)
    private val closed = AtomicBoolean(false)

    fun offer(item: T): Boolean {
        if (closed.get()) {
            onDiscard(item, A1DiscardReason.SHUTDOWN)
            return false
        }
        val previous = pending.getAndSet(item)
        previous?.let { onDiscard(it, A1DiscardReason.SUPERSEDED) }
        if (closed.get()) {
            // close() may already have removed and discarded item. If not, this offer owns it.
            if (pending.compareAndSet(item, null)) onDiscard(item, A1DiscardReason.SHUTDOWN)
            return false
        }
        if (previous == null) {
            available.release()
        }
        return true
    }

    /** Returns null after close. An item already dequeued remains owned by the caller. */
    @Throws(InterruptedException::class)
    fun take(): T? {
        while (true) {
            available.acquire()
            if (closed.get()) return null
            pending.getAndSet(null)?.let { return it }
        }
    }

    fun close() {
        if (!closed.compareAndSet(false, true)) return
        pending.getAndSet(null)?.let { onDiscard(it, A1DiscardReason.SHUTDOWN) }
        available.release()
    }

    fun isClosed(): Boolean = closed.get()
}

data class TimestampedValue<T>(
    val sourceTimestampNs: Long,
    val value: T,
)

enum class CausalJoinStatus {
    VALID,
    NO_CAUSAL_POSE,
    POSE_TOO_OLD,
}

data class CausalJoin<T>(
    val status: CausalJoinStatus,
    val pose: TimestampedValue<T>? = null,
    val poseAgeNs: Long? = null,
)

/** Bounded pose history that can select a causal pose even when a newer future pose is present. */
class CausalPoseStore<T>(private val capacity: Int = 16) {
    init {
        require(capacity > 0)
    }

    private val poses = ArrayDeque<TimestampedValue<T>>(capacity)

    @Synchronized
    fun publish(pose: TimestampedValue<T>) {
        if (poses.isNotEmpty() && pose.sourceTimestampNs <= poses.last.sourceTimestampNs) return
        poses.addLast(pose)
        while (poses.size > capacity) poses.removeFirst()
    }

    @Synchronized
    fun join(handTimestampNs: Long, maxPoseAgeNs: Long): CausalJoin<T> {
        require(maxPoseAgeNs >= 0L)
        val pose = poses.lastOrNull { it.sourceTimestampNs <= handTimestampNs }
            ?: return CausalJoin(CausalJoinStatus.NO_CAUSAL_POSE)
        val age = handTimestampNs - pose.sourceTimestampNs
        return if (age <= maxPoseAgeNs) {
            CausalJoin(CausalJoinStatus.VALID, pose, age)
        } else {
            CausalJoin(CausalJoinStatus.POSE_TOO_OLD, pose, age)
        }
    }

    @Synchronized
    fun clear() = poses.clear()
}
