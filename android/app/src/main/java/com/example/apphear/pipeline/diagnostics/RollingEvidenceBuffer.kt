package com.example.apphear.pipeline.diagnostics

/**
 * Bounded diagnostic-only ring. It freezes shortly after an observed S5 release; when S5 never
 * releases, it remains rolling until the attempt is stopped so late-starting signs stay visible.
 */
internal class RollingEvidenceBuffer<T : Any>(
    private val capacity: Int,
    private val postReleaseFrames: Int,
    private val dispose: (T) -> Unit,
) {
    data class Entry<T>(val frameId: Long, val payload: T)

    private val entries = ArrayDeque<Entry<T>>()
    private var freezeAfterFrame: Long? = null

    var frozen: Boolean = false
        private set

    init {
        require(capacity > 0)
        require(postReleaseFrames >= 0)
    }

    fun observe(frameId: Long, releaseObserved: Boolean, payload: T?) {
        if (releaseObserved && freezeAfterFrame == null) {
            freezeAfterFrame = frameId + postReleaseFrames
        }
        if (frozen) {
            if (payload != null) dispose(payload)
            return
        }
        if (payload != null) {
            entries.addLast(Entry(frameId, payload))
            while (entries.size > capacity) dispose(entries.removeFirst().payload)
        }
        if (freezeAfterFrame?.let { frameId >= it } == true) frozen = true
    }

    fun drain(): List<Entry<T>> = entries.toList().also { entries.clear() }

    fun clear() {
        entries.forEach { dispose(it.payload) }
        entries.clear()
        freezeAfterFrame = null
        frozen = false
    }
}
