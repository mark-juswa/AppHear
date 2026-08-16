package com.example.apphear.pipeline.recognition

import com.example.apphear.pipeline.features.FEATURE_DIM
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/**
 * Observation-only snapshot of the exact S4-S7 state used for one processed frame. RU-D1 keeps
 * this separate from [RecognitionState] so diagnostics cannot become a recognition input.
 */
data class RuD1PipelineTrace(
    val frameId: Long,
    val feature: FloatArray,
    val mirrored: Boolean,
    val signingEvent: SigningEvent,
    val signing: Boolean,
    val s5: SigningDiagnostics,
    val inferenceIndex: Int?,
    val windowSourceFrames: LongArray,
    val windowSha256: String?,
    val probabilities: FloatArray?,
    val s7: ConfirmationSnapshot,
    val committedClass: Int?,
)

/** Source-frame bookkeeping for the fixed [96,258] model window; it never changes feature data. */
internal class RuD1WindowSources(private val size: Int) {
    private val sourceFrames = LongArray(size) { PAD_FRAME }

    fun set(row: Int, frameId: Long) {
        sourceFrames[row] = frameId
    }

    fun clear() {
        java.util.Arrays.fill(sourceFrames, PAD_FRAME)
    }

    fun copy(): LongArray = sourceFrames.copyOf()

    companion object {
        const val PAD_FRAME = -1L
    }
}

/** Hashes the exact little-endian float32 bytes submitted to TFLite. */
internal fun ruD1WindowSha256(window: Array<FloatArray>): String {
    val digest = MessageDigest.getInstance("SHA-256")
    val bytes = ByteBuffer.allocate(FEATURE_DIM * Float.SIZE_BYTES).order(ByteOrder.LITTLE_ENDIAN)
    for (row in window) {
        bytes.clear()
        for (value in row) bytes.putFloat(value)
        digest.update(bytes.array())
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}
