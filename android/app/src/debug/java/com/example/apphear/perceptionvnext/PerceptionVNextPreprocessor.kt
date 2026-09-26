package com.example.apphear.perceptionvnext

import androidx.camera.core.ImageProxy
import kotlin.math.floor

/** Upright/unmirrored current-frame preprocessing shared by both candidate stages. */
internal class PerceptionVNextPreprocessor(image: ImageProxy) {
    private val width = image.width
    private val height = image.height
    private val rowStride = image.planes[0].rowStride
    private val pixelStride = image.planes[0].pixelStride
    private val rotation = image.imageInfo.rotationDegrees
    val transform = PerceptionVNextMath.transform(image)
    private val raw = ByteArray(image.planes[0].buffer.remaining())
    private val dwposeOutput = FloatArray(3 * 256 * 192)
    private val handOutput = FloatArray(224 * 224 * 3)

    init {
        update(image)
    }

    fun compatible(image: ImageProxy): Boolean =
        image.width == width && image.height == height &&
            image.planes[0].rowStride == rowStride &&
            image.planes[0].pixelStride == pixelStride &&
            image.imageInfo.rotationDegrees == rotation &&
            image.planes[0].buffer.remaining() == raw.size

    fun update(image: ImageProxy) {
        require(compatible(image)) { "VNEXT_CAMERA_GEOMETRY_CHANGED" }
        image.planes[0].buffer.duplicate().get(raw)
    }

    /** Exact DWPose affine: the 192-wide source square is centered in a 192x256 tensor. */
    fun dwposeInput(): FloatArray {
        val mean = floatArrayOf(123.675f, 116.28f, 103.53f)
        val std = floatArrayOf(58.395f, 57.12f, 57.375f)
        for (destinationY in 0 until 256) {
            val sourceY = transform.centerY +
                (destinationY - 128f) * transform.scaleX / 192f
            for (destinationX in 0 until 192) {
                val sourceX = transform.centerX +
                    (destinationX - 96f) * transform.scaleX / 192f
                val pixel = destinationY * 192 + destinationX
                for (channel in 0..2) {
                    dwposeOutput[channel * 256 * 192 + pixel] =
                        (bilinear(sourceX, sourceY, channel) - mean[channel]) / std[channel]
                }
            }
        }
        return dwposeOutput
    }

    fun handInput(roi: PerceptionVNextMath.HandRoi): FloatArray {
        for (destinationY in 0 until 224) {
            val sourceY = roi.top + destinationY / 223f * roi.side
            for (destinationX in 0 until 224) {
                val sourceX = roi.left + destinationX / 223f * roi.side
                val outputBase = (destinationY * 224 + destinationX) * 3
                for (channel in 0..2) {
                    handOutput[outputBase + channel] = bilinear(sourceX, sourceY, channel) / 255f
                }
            }
        }
        return handOutput
    }

    private fun bilinear(x: Float, y: Float, channel: Int): Float {
        val x0 = floor(x).toInt()
        val y0 = floor(y).toInt()
        val x1 = x0 + 1
        val y1 = y0 + 1
        val weightX = x - x0
        val weightY = y - y0
        val top = pixel(x0, y0, channel) * (1f - weightX) + pixel(x1, y0, channel) * weightX
        val bottom = pixel(x0, y1, channel) * (1f - weightX) + pixel(x1, y1, channel) * weightX
        return top * (1f - weightY) + bottom * weightY
    }

    private fun pixel(orientedX: Int, orientedY: Int, channel: Int): Float {
        if (orientedX !in 0 until transform.sourceWidth || orientedY !in 0 until transform.sourceHeight) {
            return 0f
        }
        val rawX: Int
        val rawY: Int
        when (rotation) {
            90 -> {
                rawX = orientedY
                rawY = height - 1 - orientedX
            }
            180 -> {
                rawX = width - 1 - orientedX
                rawY = height - 1 - orientedY
            }
            270 -> {
                rawX = width - 1 - orientedY
                rawY = orientedX
            }
            else -> {
                rawX = orientedX
                rawY = orientedY
            }
        }
        val offset = rawY * rowStride + rawX * pixelStride + channel
        return (raw[offset].toInt() and 0xff).toFloat()
    }
}
