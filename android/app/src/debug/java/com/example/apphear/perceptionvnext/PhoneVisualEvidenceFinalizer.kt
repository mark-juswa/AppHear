package com.example.apphear.perceptionvnext

import java.io.File
import java.util.concurrent.Future

/** Waits for every queued visual write and refuses to certify an incomplete session. */
internal object PhoneVisualEvidenceFinalizer {
    fun awaitVerifiedOriginals(futures: List<Future<*>>, originals: File, expected: Int): Int {
        futures.forEach { it.get() }
        val saved = originals.listFiles { file ->
            file.isFile && file.name.matches(Regex("frame_\\d+_original\\.jpg"))
        }?.size ?: 0
        require(saved == expected) {
            "PHONE_CAUSAL_VISUAL_DRAIN_INCOMPLETE: saved=$saved expected=$expected"
        }
        return saved
    }
}
