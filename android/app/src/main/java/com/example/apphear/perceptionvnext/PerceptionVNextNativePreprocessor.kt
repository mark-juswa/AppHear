package com.example.apphear.perceptionvnext

import androidx.camera.core.ImageProxy
import java.nio.ByteBuffer
import java.nio.ByteOrder

internal object PerceptionVNextNative {
    init {
        System.loadLibrary("perceptionvnext")
    }

    external fun create(
        width: Int,
        height: Int,
        rowStride: Int,
        pixelStride: Int,
        rotation: Int,
    ): Long

    external fun destroy(handle: Long)
    external fun preprocess(
        handle: Long,
        source: ByteBuffer,
        base: Int,
        remaining: Int,
        output: ByteBuffer,
    )
    external fun crop(
        handle: Long,
        centerX: Float,
        centerY: Float,
        side: Float,
        output: ByteBuffer,
    )
    external fun geometry(handle: Long): IntArray
}

internal class PerceptionVNextNativePreprocessor(image: ImageProxy) : AutoCloseable {
    private val width = image.width
    private val height = image.height
    private val rowStride = image.planes[0].rowStride
    private val pixelStride = image.planes[0].pixelStride
    private val rotation = image.imageInfo.rotationDegrees
    private val sourceBytes = image.planes[0].buffer.remaining()
    private var handle = PerceptionVNextNative.create(width, height, rowStride, pixelStride, rotation)
    val poseInput: ByteBuffer =
        ByteBuffer.allocateDirect(3 * 256 * 192 * 4).order(ByteOrder.nativeOrder())
    val handInput: ByteBuffer =
        ByteBuffer.allocateDirect(224 * 224 * 3 * 4).order(ByteOrder.nativeOrder())
    val transform = PerceptionVNextMath.transform(image)

    init {
        require(handle != 0L) { "VNEXT_NATIVE_CREATE_FAILED" }
        require(
            PerceptionVNextNative.geometry(handle).contentEquals(
                intArrayOf(transform.sourceWidth, transform.sourceHeight),
            ),
        ) { "VNEXT_NATIVE_SOURCE_GEOMETRY_MISMATCH" }
    }

    fun compatible(image: ImageProxy): Boolean =
        image.width == width && image.height == height &&
            image.planes[0].rowStride == rowStride &&
            image.planes[0].pixelStride == pixelStride &&
            image.imageInfo.rotationDegrees == rotation &&
            image.planes[0].buffer.remaining() == sourceBytes

    fun preprocess(image: ImageProxy) {
        check(handle != 0L)
        require(compatible(image)) { "VNEXT_NATIVE_CAMERA_GEOMETRY_CHANGED" }
        val source = image.planes[0].buffer.duplicate()
        PerceptionVNextNative.preprocess(
            handle,
            source,
            source.position(),
            source.remaining(),
            poseInput,
        )
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
