package com.example.apphear.p8c2

import com.example.apphear.p7d.P7dMath
import java.nio.ByteBuffer

internal object P8c2Native {
    init { System.loadLibrary("p8c2decoder") }
    external fun create(width: Int, height: Int): Long
    external fun destroy(handle: Long)
    external fun decode(
        handle: Long,
        heatmap: ByteBuffer,
        inputXY: FloatArray,
        sourceXY: FloatArray,
        peaks: IntArray,
    )
}

/** Heatmap-only JNI adapter for the unchanged P7D-R2 local-3 geometry mathematics. */
class P8c2NativeDecoder(val transform: P7dMath.Transform) : AutoCloseable {
    private var handle = P8c2Native.create(transform.width, transform.height)
    val inputXY = FloatArray(P7dMath.POINTS * 2)
    val sourceXY = FloatArray(P7dMath.POINTS * 2)
    val peaks = IntArray(P7dMath.POINTS)

    init { require(handle != 0L) { "P8C2_NATIVE_CREATE_FAILED" } }

    fun decode(heatmap: ByteBuffer) {
        check(handle != 0L) { "P8C2_NATIVE_DECODER_CLOSED" }
        require(heatmap.isDirect && heatmap.capacity() == 96 * 96 * 50 * 4)
        P8c2Native.decode(handle, heatmap, inputXY, sourceXY, peaks)
    }

    override fun close() {
        if (handle != 0L) {
            P8c2Native.destroy(handle)
            handle = 0L
        }
    }
}
