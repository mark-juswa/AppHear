package com.example.apphear.p8c1

import com.example.apphear.p7d.P7dMath
import com.example.apphear.p7dr1.P7dr1Preprocess
import com.example.apphear.p7dr2.P7dr2Kernel
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

/** Thin P8-C1 adapter around the unchanged parity-proven P7D-R2 native kernel. */
internal class P8c1NativePreprocessor(
    val width: Int,
    val height: Int,
    val rowStride: Int,
    val pixelStride: Int,
    val rotation: Int,
) : AutoCloseable {
    private val kernel = P7dr2Kernel(width, height, rowStride, pixelStride, rotation)
    val input: ByteBuffer = kernel.input
    val transform = P7dMath.Transform(
        if (rotation == 90 || rotation == 270) height else width,
        if (rotation == 90 || rotation == 270) width else height,
    )

    init {
        val geometry = kernel.geometry()
        require(
            geometry.contentEquals(
                intArrayOf(
                    transform.width, transform.height, transform.rw, transform.rh,
                    transform.left, transform.top,
                ),
            ),
        ) { "P8C1_NATIVE_GEOMETRY_MISMATCH" }
    }

    fun run(source: ByteBuffer) = kernel.preprocess(source)

    override fun close() = kernel.close()
}

/** Eight same-frame comparisons run only before the formal measurement interval. */
internal class P8c1LiveParity(
    width: Int,
    height: Int,
    rowStride: Int,
    pixelStride: Int,
    rotation: Int,
) {
    private val reference = P7dr1Preprocess(width, height, rowStride, pixelStride, rotation)
    private val referenceValues = FloatArray(FLOATS)
    private val nativeValues = FloatArray(FLOATS)
    private var differences: FloatArray? = FloatArray(FRAMES * FLOATS)
    private var frames = 0
    private var differing = 0L
    private var finite = true

    val complete: Boolean get() = frames == FRAMES

    fun compare(source: ByteBuffer, native: P8c1NativePreprocessor) {
        require(!complete)
        reference.run(source.duplicate())
        native.run(source.duplicate())
        reference.input.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer().get(referenceValues)
        native.input.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer().get(nativeValues)
        val target = requireNotNull(differences)
        val offset = frames * FLOATS
        for (index in 0 until FLOATS) {
            val difference = abs(referenceValues[index] - nativeValues[index])
            target[offset + index] = difference
            if (difference != 0f) differing++
            if (!difference.isFinite() || !nativeValues[index].isFinite()) finite = false
        }
        native.input.rewind()
        frames++
    }

    fun result(
        width: Int,
        height: Int,
        rowStride: Int,
        pixelStride: Int,
        rotation: Int,
    ): JSONObject {
        require(complete)
        val sorted = requireNotNull(differences).also { it.sort() }
        var sum = 0.0
        for (value in sorted) sum += value
        val p95Index = 0.95 * (sorted.size - 1)
        val low = p95Index.toInt()
        val high = minOf(low + 1, sorted.lastIndex)
        val p95 = sorted[low] + (sorted[high] - sorted[low]) * (p95Index - low)
        val mean = sum / sorted.size
        val maximum = sorted.last().toDouble()
        val pass = finite && mean <= 1e-6 && p95 <= 2e-6 && maximum <= 1e-5
        differences = null
        return JSONObject()
            .put("schema", "P8C1_LIVE_CAMERA_PREPROCESSING_PARITY_V1")
            .put("status", if (pass) "PASS" else "FAIL")
            .put("frames", frames)
            .put("elements", FRAMES.toLong() * FLOATS)
            .put("camera_width", width).put("camera_height", height)
            .put("row_stride", rowStride).put("pixel_stride", pixelStride)
            .put("rotation_degrees", rotation)
            .put("model_input_mirrored", false)
            .put("mean_absolute", mean).put("p95_absolute", p95)
            .put("maximum_absolute", maximum)
            .put("different_elements", differing)
            .put("different_fraction", differing.toDouble() / (FRAMES.toLong() * FLOATS))
            .put("finite", finite)
            .put(
                "tolerances",
                JSONObject().put("mean", 1e-6).put("p95", 2e-6).put("maximum", 1e-5),
            )
            .put("duplicated_work_in_formal_measurement", false)
    }

    companion object {
        const val FRAMES = 8
        private const val FLOATS = 384 * 384 * 3
    }
}
