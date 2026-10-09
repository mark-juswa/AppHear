package com.example.apphear.p8c2

import com.example.apphear.p8b.P8bDecoder
import com.example.apphear.p8b.P8bStats
import org.json.JSONObject
import kotlin.math.hypot

/** Eight-frame same-heatmap parity gate. Model inference is performed exactly once per frame. */
class P8c2LiveDecoderParity {
    private val inputErrors = DoubleArray(FRAMES * 50)
    private val sourceErrors = DoubleArray(FRAMES * 50)
    private var frames = 0
    private var peakDifferences = 0
    private var finite = true

    val complete: Boolean get() = frames == FRAMES

    fun compare(kotlin: P8bDecoder, native: P8c2NativeDecoder) {
        require(!complete)
        for (point in 0 until 50) {
            val offset = frames * 50 + point
            inputErrors[offset] = hypot(
                (kotlin.inputXY[point * 2] - native.inputXY[point * 2]).toDouble(),
                (kotlin.inputXY[point * 2 + 1] - native.inputXY[point * 2 + 1]).toDouble(),
            )
            sourceErrors[offset] = hypot(
                (kotlin.sourceXY[point * 2] - native.sourceXY[point * 2]).toDouble(),
                (kotlin.sourceXY[point * 2 + 1] - native.sourceXY[point * 2 + 1]).toDouble(),
            )
            if (kotlin.peaks[point] != native.peaks[point]) peakDifferences++
            if (!inputErrors[offset].isFinite() || !sourceErrors[offset].isFinite()) finite = false
        }
        frames++
    }

    fun result(width: Int, height: Int, rotation: Int): JSONObject {
        require(complete)
        val input = P8bStats.summarize(inputErrors)
        val source = P8bStats.summarize(sourceErrors)
        val lh = regionMaximum(0, 21)
        val rh = regionMaximum(21, 42)
        val body = regionMaximum(42, 50)
        val pass = finite && input.maximum <= 1e-4 && source.maximum <= 1e-3 && peakDifferences == 0
        return JSONObject()
            .put("schema", "P8C2_LIVE_SAME_HEATMAP_DECODER_PARITY_V1")
            .put("status", if (pass) "PASS" else "FAIL")
            .put("frames", frames).put("points", frames * 50)
            .put("source_width", width).put("source_height", height)
            .put("rotation_degrees", rotation)
            .put("model_input_plane", "UPRIGHT_UNMIRRORED_SOURCE_RGB")
            .put("model_invocations_per_frame", 1)
            .put("same_heatmap_fed_to_both_decoders", true)
            .put("input_plane_px", stats(input))
            .put("source_plane_px", stats(source))
            .put("lh_max_input_px", lh).put("rh_max_input_px", rh).put("body_max_input_px", body)
            .put("peak_cell_differences", peakDifferences)
            .put("nonfinite_mismatches", if (finite) 0 else 1)
            .put("kotlin_decoder_disabled_after_gate", true)
            .put("tolerances", JSONObject().put("input_max_px", 1e-4).put("source_max_px", 1e-3))
    }

    private fun regionMaximum(start: Int, end: Int): Double {
        var maximum = 0.0
        for (frame in 0 until frames) for (point in start until end) {
            maximum = maxOf(maximum, inputErrors[frame * 50 + point])
        }
        return maximum
    }

    private fun stats(value: P8bStats.Summary) = JSONObject()
        .put("count", value.count).put("mean", value.mean).put("p50", value.p50)
        .put("p95", value.p95).put("maximum", value.maximum)

    companion object { const val FRAMES = 8 }
}
