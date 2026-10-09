package com.example.apphear.perceptionvnext

import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

/** Four-frame live parity gate; reference work ends before any formal measurement. */
internal class PerceptionVNextNativeParity {
    private var frames = 0
    private var poseElements = 0L
    private var cropElements = 0L
    private var poseSum = 0.0
    private var cropSum = 0.0
    private var poseMax = 0f
    private var cropMax = 0f

    val complete: Boolean get() = frames >= REQUIRED_FRAMES

    fun compare(
        referencePose: FloatArray,
        nativePose: ByteBuffer,
        referenceCrop: FloatArray,
        nativeCrop: ByteBuffer,
    ) {
        require(!complete)
        val pose = nativePose.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer()
        require(pose.remaining() == referencePose.size)
        for (value in referencePose) {
            val difference = abs(value - pose.get())
            require(difference.isFinite()) { "VNEXT_NATIVE_POSE_PARITY_NONFINITE" }
            poseSum += difference
            poseMax = maxOf(poseMax, difference)
            poseElements++
        }
        val crop = nativeCrop.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer()
        require(crop.remaining() == referenceCrop.size)
        for (value in referenceCrop) {
            val difference = abs(value - crop.get())
            require(difference.isFinite()) { "VNEXT_NATIVE_CROP_PARITY_NONFINITE" }
            cropSum += difference
            cropMax = maxOf(cropMax, difference)
            cropElements++
        }
        frames++
    }

    fun result(): JSONObject {
        require(complete)
        val poseMean = poseSum / poseElements
        val cropMean = cropSum / cropElements
        val pass = poseMean <= MEAN_TOLERANCE && cropMean <= MEAN_TOLERANCE &&
            poseMax <= MAX_TOLERANCE && cropMax <= MAX_TOLERANCE
        return JSONObject()
            .put("schema", "APPHEAR_PERCEPTION_VNEXT_NATIVE_LIVE_PARITY_V1")
            .put("status", if (pass) "PASS" else "FAIL")
            .put("frames", frames)
            .put("pose_elements", poseElements)
            .put("pose_mean_absolute", poseMean)
            .put("pose_maximum_absolute", poseMax)
            .put("crop_elements", cropElements)
            .put("crop_mean_absolute", cropMean)
            .put("crop_maximum_absolute", cropMax)
            .put("mean_tolerance", MEAN_TOLERANCE)
            .put("maximum_tolerance", MAX_TOLERANCE)
    }

    companion object {
        const val REQUIRED_FRAMES = 4
        private const val MEAN_TOLERANCE = 1e-6
        private const val MAX_TOLERANCE = 1e-5
    }
}
