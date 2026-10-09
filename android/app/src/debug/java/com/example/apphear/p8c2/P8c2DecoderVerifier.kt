package com.example.apphear.p8c2

import android.content.Context
import com.example.apphear.p7d.P7dMath
import com.example.apphear.p8b.P8bDecoder
import com.example.apphear.p8b.P8bModelRunner
import com.example.apphear.p8b.P8bStats
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.hypot

/** Untimed P8-C2 device gate. No optimizer, recognition, camera, or model mutation. */
object P8c2DecoderVerifier {
    private const val MANIFEST = "p8b/android_golden_test_manifest.json"
    private const val FLOATS = 96 * 96 * 50

    fun verify(context: Context): JSONObject {
        val realRows = JSONArray()
        val boundaryRows = JSONArray()
        val inputErrors = ArrayList<Double>()
        val sourceErrors = ArrayList<Double>()
        var peakDifferences = 0
        var lhMaximum = 0.0
        var rhMaximum = 0.0
        var bodyMaximum = 0.0

        val manifest = JSONObject(context.assets.open(MANIFEST).bufferedReader().readText())
        val fixtures = manifest.getJSONArray("fixtures")
        P8bModelRunner(context).use { runner ->
            for (index in 0 until fixtures.length()) {
                val fixture = fixtures.getJSONObject(index)
                val bytes = context.assets.open(fixture.getString("input_file")).use { it.readBytes() }
                val input = ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.LITTLE_ENDIAN)
                    .put(bytes).also { it.rewind() }
                val transform = P7dMath.Transform(fixture.getInt("source_width"), fixture.getInt("source_height"))
                val kotlin = P8bDecoder(transform)
                P8c2NativeDecoder(transform).use { native ->
                    runner.runSameHeatmapParity(input, kotlin, native)
                    val row = compare("real_${fixture.getString("fixture_id")}", kotlin, native)
                    collect(row, inputErrors, sourceErrors)
                    peakDifferences += row.getInt("peak_cell_differences")
                    lhMaximum = maxOf(lhMaximum, row.getDouble("lh_max_input_px"))
                    rhMaximum = maxOf(rhMaximum, row.getDouble("rh_max_input_px"))
                    bodyMaximum = maxOf(bodyMaximum, row.getDouble("body_max_input_px"))
                    realRows.put(row)
                }
            }
        }

        val transform = P7dMath.Transform(384, 384)
        val heatmap = ByteBuffer.allocateDirect(FLOATS * 4).order(ByteOrder.nativeOrder())
        val patterns = listOf(
            "center", "top_edge", "bottom_edge", "left_edge", "right_edge", "corners",
            "equal_tie", "strong_peak", "weak_peak", "adjacent_competing", "all_zero",
        )
        for (pattern in patterns) {
            fillPattern(heatmap, pattern)
            val kotlin = P8bDecoder(transform)
            val values = FloatArray(FLOATS)
            heatmap.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer().get(values)
            kotlin.decode(values)
            P8c2NativeDecoder(transform).use { native ->
                heatmap.rewind()
                native.decode(heatmap)
                val row = compare("synthetic_$pattern", kotlin, native)
                collect(row, inputErrors, sourceErrors)
                peakDifferences += row.getInt("peak_cell_differences")
                lhMaximum = maxOf(lhMaximum, row.getDouble("lh_max_input_px"))
                rhMaximum = maxOf(rhMaximum, row.getDouble("rh_max_input_px"))
                bodyMaximum = maxOf(bodyMaximum, row.getDouble("body_max_input_px"))
                boundaryRows.put(row)
            }
        }

        var nonfiniteCases = 0
        var nonfiniteMismatches = 0
        for (bad in floatArrayOf(Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY)) {
            for (index in intArrayOf(0, FLOATS / 2, FLOATS - 1)) {
                heatmap.clear()
                for (cell in 0 until FLOATS) heatmap.putFloat(if (cell == index) bad else 0f)
                heatmap.rewind()
                val values = FloatArray(FLOATS)
                heatmap.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer().get(values)
                val kotlinRejected = rejected { P8bDecoder(transform).decode(values) }
                val nativeRejected = P8c2NativeDecoder(transform).use { native ->
                    rejected { native.decode(heatmap) }
                }
                if (!kotlinRejected || !nativeRejected) nonfiniteMismatches++
                nonfiniteCases++
            }
        }

        val inputStats = P8bStats.summarize(inputErrors.toDoubleArray())
        val sourceStats = P8bStats.summarize(sourceErrors.toDoubleArray())
        val pass = inputStats.maximum <= 1e-4 && sourceStats.maximum <= 1e-3 &&
            peakDifferences == 0 && nonfiniteMismatches == 0
        val boundary = JSONObject()
            .put("schema", "P8C2_DECODER_BOUNDARY_FIXTURE_RESULTS_V1")
            .put("status", if (pass) "PASS" else "FAIL")
            .put("fixtures", patterns.size).put("rows", boundaryRows)
            .put("nonfinite_cases", nonfiniteCases)
            .put("nonfinite_policy_mismatches", nonfiniteMismatches)
            .put("strict_tie_behavior", "FIRST_CELL_IN_CELL_MAJOR_ORDER")
        val result = JSONObject()
            .put("schema", "P8C2_STATIC_DECODER_PARITY_V1")
            .put("status", if (pass) "PASS" else "FAIL")
            .put("real_model_fixtures", fixtures.length())
            .put("synthetic_boundary_fixtures", patterns.size)
            .put("points_compared", inputErrors.size)
            .put("input_plane_px", stats(inputStats))
            .put("source_plane_px", stats(sourceStats))
            .put("lh_max_input_px", lhMaximum).put("rh_max_input_px", rhMaximum)
            .put("body_max_input_px", bodyMaximum)
            .put("peak_cell_differences", peakDifferences)
            .put("nonfinite_cases", nonfiniteCases)
            .put("nonfinite_policy_mismatches", nonfiniteMismatches)
            .put("identity_assignment_logic_excluded", true)
            .put("real_rows", realRows)
            .put("tolerances", JSONObject().put("input_max_px", 1e-4).put("source_max_px", 1e-3))
        val root = File(requireNotNull(context.getExternalFilesDir(null)), "p8c2").also { it.mkdirs() }
        File(root, "decoder_boundary_fixture_results.json").writeText(boundary.toString(2))
        File(root, "static_decoder_parity.json").writeText(result.toString(2))
        return result
    }

    private fun fillPattern(buffer: ByteBuffer, pattern: String) {
        buffer.clear()
        for (index in 0 until FLOATS) buffer.putFloat(if (pattern == "all_zero") 0f else -10f)
        fun set(cell: Int, point: Int, value: Float) = buffer.putFloat((cell * 50 + point) * 4, value)
        for (point in 0 until 50) when (pattern) {
            "center" -> set(48 * 96 + 48, point, 8f)
            "top_edge" -> set(48, point, 8f)
            "bottom_edge" -> set(95 * 96 + 48, point, 8f)
            "left_edge" -> set(48 * 96, point, 8f)
            "right_edge" -> set(48 * 96 + 95, point, 8f)
            "corners" -> set(intArrayOf(0, 95, 95 * 96, 96 * 96 - 1)[point % 4], point, 8f)
            "equal_tie" -> { set(10 * 96 + 10, point, 8f); set(80 * 96 + 80, point, 8f) }
            "strong_peak" -> set(33 * 96 + 44, point, 30f)
            "weak_peak" -> set(55 * 96 + 22, point, -9f)
            "adjacent_competing" -> { set(47 * 96 + 47, point, 2f); set(47 * 96 + 48, point, 1f) }
        }
        buffer.rewind()
    }

    private fun compare(id: String, kotlin: P8bDecoder, native: P8c2NativeDecoder): JSONObject {
        val input = DoubleArray(50)
        val source = DoubleArray(50)
        var peaks = 0
        for (point in 0 until 50) {
            input[point] = hypot(
                (kotlin.inputXY[point * 2] - native.inputXY[point * 2]).toDouble(),
                (kotlin.inputXY[point * 2 + 1] - native.inputXY[point * 2 + 1]).toDouble(),
            )
            source[point] = hypot(
                (kotlin.sourceXY[point * 2] - native.sourceXY[point * 2]).toDouble(),
                (kotlin.sourceXY[point * 2 + 1] - native.sourceXY[point * 2 + 1]).toDouble(),
            )
            if (kotlin.peaks[point] != native.peaks[point]) peaks++
        }
        return JSONObject().put("fixture", id)
            .put("input_errors", JSONArray(input.toList())).put("source_errors", JSONArray(source.toList()))
            .put("input_max_px", input.max()).put("source_max_px", source.max())
            .put("lh_max_input_px", input.copyOfRange(0, 21).max())
            .put("rh_max_input_px", input.copyOfRange(21, 42).max())
            .put("body_max_input_px", input.copyOfRange(42, 50).max())
            .put("peak_cell_differences", peaks)
    }

    private fun collect(row: JSONObject, input: MutableList<Double>, source: MutableList<Double>) {
        val a = row.getJSONArray("input_errors")
        val b = row.getJSONArray("source_errors")
        for (index in 0 until a.length()) { input.add(a.getDouble(index)); source.add(b.getDouble(index)) }
    }

    private fun rejected(block: () -> Unit): Boolean = try { block(); false } catch (_: IllegalArgumentException) { true }

    private fun stats(value: P8bStats.Summary) = JSONObject()
        .put("count", value.count).put("mean", value.mean).put("p50", value.p50)
        .put("p95", value.p95).put("maximum", value.maximum)
}
