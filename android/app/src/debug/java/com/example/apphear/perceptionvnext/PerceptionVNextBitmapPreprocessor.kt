package com.example.apphear.perceptionvnext

import android.graphics.Bitmap
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Exact-fixture adapter over the same native PHONE_01 preprocess/crop kernel. */
internal class PerceptionVNextBitmapPreprocessor(bitmap: Bitmap) : AutoCloseable {
    private val width = bitmap.width
    private val height = bitmap.height
    private var handle = PerceptionVNextNative.create(width, height, width * 4, 4, 0)
    private val rgba = ByteBuffer.allocateDirect(width * height * 4).order(ByteOrder.nativeOrder())
    val poseInput: ByteBuffer =
        ByteBuffer.allocateDirect(3 * 256 * 192 * 4).order(ByteOrder.nativeOrder())
    val handInput: ByteBuffer =
        ByteBuffer.allocateDirect(224 * 224 * 3 * 4).order(ByteOrder.nativeOrder())
    val transform = PerceptionVNextMath.transform(width, height)

    init {
        require(handle != 0L) { "VNEXT_FIXTURE_NATIVE_CREATE_FAILED" }
        update(bitmap)
    }

    fun update(bitmap: Bitmap) {
        require(bitmap.width == width && bitmap.height == height) {
            "VNEXT_FIXTURE_BITMAP_GEOMETRY_CHANGED"
        }
        val pixels = IntArray(width * height)
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
        rgba.clear()
        for (pixel in pixels) {
            rgba.put(((pixel shr 16) and 0xff).toByte())
            rgba.put(((pixel shr 8) and 0xff).toByte())
            rgba.put((pixel and 0xff).toByte())
            rgba.put(((pixel ushr 24) and 0xff).toByte())
        }
        rgba.flip()
        PerceptionVNextNative.preprocess(handle, rgba, 0, rgba.remaining(), poseInput)
        poseInput.rewind()
    }

    fun crop(roi: PerceptionVNextMath.HandRoi): ByteBuffer {
        check(handle != 0L)
        PerceptionVNextNative.crop(handle, roi.centerX, roi.centerY, roi.side, handInput)
        handInput.rewind()
        return handInput
    }

    override fun close() {
        if (handle != 0L) {
            PerceptionVNextNative.destroy(handle)
            handle = 0L
        }
    }
}
