package com.example.apphear.p8b

import android.content.Context
import com.example.apphear.p7d.P7dMath
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.abs
import kotlin.math.hypot

/** Deterministic device-only P8B-1 and P8B-2 gates. */
object P8bGoldenVerifier {
    private const val GOLDEN_MANIFEST = "p8b/android_golden_test_manifest.json"
    private const val PREPROCESS_MANIFEST = "p8b/android_preprocessing_fixture_manifest.json"

    fun verifyModelAndDecoder(context: Context): JSONObject {
        val manifest = JSONObject(context.assets.open(GOLDEN_MANIFEST).bufferedReader().readText())
        val fixtures = manifest.getJSONArray("fixtures")
        val rows = JSONArray()
        val csv = StringBuilder(
            "fixture_id,source,sample_id,mean_input_px,p95_input_px,max_input_px," +
                "mean_source_px,p95_source_px,max_source_px,lh_max_px,rh_max_px,body_max_px,nan_inf,status\n",
        )
        val allInput = DoubleArray(fixtures.length() * 50)
        val allSource = DoubleArray(fixtures.length() * 50)
        var aggregateOffset = 0
        var anyNonFinite = false
        var pass = true
        P8bModelRunner(context).use { runner ->
            for (index in 0 until fixtures.length()) {
                val fixture = fixtures.getJSONObject(index)
                val inputBytes = readVerified(
                    context,
                    fixture.getString("input_file"),
                    fixture.getString("input_sha256"),
                )
                // P8-A fixtures are explicitly little-endian FP32. Android/ARM TFLite is
                // little-endian too, but keeping this explicit catches contract drift.
                val input = ByteBuffer.allocateDirect(inputBytes.size).order(ByteOrder.LITTLE_ENDIAN)
                    .put(inputBytes).also { it.rewind() }
                val transform = P7dMath.Transform(
                    fixture.getInt("source_width"),
                    fixture.getInt("source_height"),
                )
                val decoder = P8bDecoder(transform)
                runner.run(input, decoder)
                val expectedInput = readFloatArray(
                    readVerified(
                        context,
                        fixture.getString("expected_input_xy_file"),
                        fixture.getString("expected_input_xy_sha256"),
                    ),
                )
                val expectedSource = readFloatArray(
                    readVerified(
                        context,
                        fixture.getString("expected_source_xy_file"),
                        fixture.getString("expected_source_xy_sha256"),
                    ),
                )
                val inputErrors = DoubleArray(50)
                val sourceErrors = DoubleArray(50)
                var nonFinite = false
                for (point in 0 until 50) {
                    val inputError = hypot(
                        (decoder.inputXY[point * 2] - expectedInput[point * 2]).toDouble(),
                        (decoder.inputXY[point * 2 + 1] - expectedInput[point * 2 + 1]).toDouble(),
                    )
                    val sourceError = hypot(
                        (decoder.sourceXY[point * 2] - expectedSource[point * 2]).toDouble(),
                        (decoder.sourceXY[point * 2 + 1] - expectedSource[point * 2 + 1]).toDouble(),
                    )
                    inputErrors[point] = inputError
                    sourceErrors[point] = sourceError
                    allInput[aggregateOffset + point] = inputError
                    allSource[aggregateOffset + point] = sourceError
                    if (!inputError.isFinite() || !sourceError.isFinite()) nonFinite = true
                }
                aggregateOffset += 50
                anyNonFinite = anyNonFinite || nonFinite
                val inputStats = P8bStats.summarize(inputErrors)
                val sourceStats = P8bStats.summarize(sourceErrors)
                val lhMax = inputErrors.copyOfRange(0, 21).max()
                val rhMax = inputErrors.copyOfRange(21, 42).max()
                val bodyMax = inputErrors.copyOfRange(42, 50).max()
                val fixturePass = !nonFinite && inputStats.maximum <= 1.0
                pass = pass && fixturePass
                val row = JSONObject()
                    .put("fixture_id", fixture.getString("fixture_id"))
                    .put("source", fixture.getString("source"))
                    .put("sample_id", fixture.getString("sample_id"))
                    .put("input_plane_px", statsJson(inputStats))
                    .put("source_plane_px", statsJson(sourceStats))
                    .put("lh_max_input_px", lhMax)
                    .put("rh_max_input_px", rhMax)
                    .put("body_max_input_px", bodyMax)
                    .put("nan_inf", nonFinite)
                    .put("status", if (fixturePass) "PASS" else "FAIL")
                rows.put(row)
                csv.append(
                    listOf(
                        fixture.getString("fixture_id"), fixture.getString("source"),
                        fixture.getString("sample_id"), inputStats.mean, inputStats.p95,
                        inputStats.maximum, sourceStats.mean, sourceStats.p95, sourceStats.maximum,
                        lhMax, rhMax, bodyMax, nonFinite, if (fixturePass) "PASS" else "FAIL",
                    ).joinToString(","),
                ).append('\n')
            }
            val inputStats = P8bStats.summarize(allInput)
            val sourceStats = P8bStats.summarize(allSource)
            val result = JSONObject()
                .put("schema", "P8B_ANDROID_GOLDEN_RUNTIME_PARITY_V1")
                .put("status", if (pass) "PASS" else "FAIL")
                .put("fixtures", fixtures.length())
                .put("landmarks", allInput.size)
                .put("model_sha256", runner.modelSha256)
                .put("input_shape", JSONArray(listOf(1, 384, 384, 3)))
                .put("output_shape", JSONArray(listOf(1, 96, 96, 50)))
                .put("output_dtype", "FLOAT32")
                .put("input_plane_px", statsJson(inputStats))
                .put("source_plane_px", statsJson(sourceStats))
                .put("lh_max_input_px", regionMax(rows, "lh_max_input_px"))
                .put("rh_max_input_px", regionMax(rows, "rh_max_input_px"))
                .put("body_max_input_px", regionMax(rows, "body_max_input_px"))
                .put("peak_cell_differences", "NOT_AVAILABLE_IN_P8A_GOLDEN_PACKAGE")
                .put("nan_inf", anyNonFinite)
                .put("hard_gate_input_plane_max_px", 1.0)
                .put("per_fixture", rows)
            val root = outputRoot(context)
            File(root, "android_golden_runtime_parity.json").writeText(result.toString(2))
            File(root, "android_golden_per_fixture.csv").writeText(csv.toString())
            return result
        }
    }

    fun verifyPreprocessing(context: Context): JSONObject {
        val manifest = JSONObject(context.assets.open(PREPROCESS_MANIFEST).bufferedReader().readText())
        val fixtures = manifest.getJSONArray("fixtures")
        val rows = JSONArray()
        val aggregate = DoubleArray(fixtures.length() * 384 * 384 * 3)
        var aggregateOffset = 0
        var pass = true
        for (index in 0 until fixtures.length()) {
            val fixture = fixtures.getJSONObject(index)
            val rgb = readVerified(
                context,
                fixture.getString("rgb_asset"),
                fixture.getString("rgb_sha256"),
            )
            val expectedBytes = readVerified(
                context,
                fixture.getString("expected_tensor_asset"),
                fixture.getString("expected_tensor_sha256"),
            )
            val expected = readFloatArray(expectedBytes)
            val transform = P7dMath.Transform(fixture.getInt("width"), fixture.getInt("height"))
            val actualBuffer = ByteBuffer.allocateDirect(expectedBytes.size).order(ByteOrder.LITTLE_ENDIAN)
            P7dMath.letterbox(rgb, transform, actualBuffer)
            val actual = FloatArray(expected.size)
            actualBuffer.asFloatBuffer().get(actual)
            val differences = DoubleArray(expected.size)
            var changed = 0
            for (element in expected.indices) {
                val difference = abs(actual[element] - expected[element]).toDouble()
                differences[element] = difference
                aggregate[aggregateOffset + element] = difference
                if (difference != 0.0) changed++
            }
            aggregateOffset += differences.size
            val stats = P8bStats.summarize(differences)
            val geometryExact = transform.rw == fixture.getInt("resized_width") &&
                transform.rh == fixture.getInt("resized_height") &&
                transform.left == fixture.getInt("left") && transform.top == fixture.getInt("top")
            val fixturePass = geometryExact && stats.mean <= 1e-6 && stats.p95 <= 2e-6 &&
                stats.maximum <= 1e-5 && actual.all { it.isFinite() }
            pass = pass && fixturePass
            rows.put(
                JSONObject()
                    .put("fixture_id", fixture.getString("fixture_id"))
                    .put("source", fixture.getString("source"))
                    .put("mean_absolute", stats.mean)
                    .put("p95_absolute", stats.p95)
                    .put("maximum_absolute", stats.maximum)
                    .put("different_elements", changed)
                    .put("different_fraction", changed.toDouble() / expected.size)
                    .put("letterbox_geometry_exact", geometryExact)
                    .put("nan_inf", !actual.all { it.isFinite() })
                    .put("status", if (fixturePass) "PASS" else "FAIL"),
            )
        }
        val stats = P8bStats.summarize(aggregate)
        val result = JSONObject()
            .put("schema", "P8B_ANDROID_PREPROCESSING_PARITY_V1")
            .put("status", if (pass) "PASS" else "FAIL")
            .put("fixtures", fixtures.length())
            .put("elements", aggregate.size)
            .put("mean_absolute", stats.mean)
            .put("p95_absolute", stats.p95)
            .put("maximum_absolute", stats.maximum)
            .put("letterbox_geometry_all_exact", pass && (0 until rows.length()).all {
                rows.getJSONObject(it).getBoolean("letterbox_geometry_exact")
            })
            .put("tolerances", JSONObject().put("mean", 1e-6).put("p95", 2e-6).put("maximum", 1e-5))
            .put("per_fixture", rows)
        File(outputRoot(context), "android_preprocessing_parity.json").writeText(result.toString(2))
        return result
    }

    private fun outputRoot(context: Context): File =
        File(requireNotNull(context.getExternalFilesDir(null)), "p8b").also { it.mkdirs() }

    private fun readVerified(context: Context, asset: String, expectedSha256: String): ByteArray {
        val bytes = context.assets.open(asset).use { it.readBytes() }
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
        require(digest == expectedSha256) { "P8B_FIXTURE_HASH_MISMATCH:$asset" }
        return bytes
    }

    private fun readFloatArray(bytes: ByteArray): FloatArray {
        require(bytes.size % 4 == 0)
        val view = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(view.remaining()).also { view.get(it) }
    }

    private fun statsJson(stats: P8bStats.Summary): JSONObject = JSONObject()
        .put("count", stats.count).put("mean", stats.mean).put("p50", stats.p50)
        .put("p95", stats.p95).put("maximum", stats.maximum)

    private fun regionMax(rows: JSONArray, key: String): Double {
        var maximum = 0.0
        for (index in 0 until rows.length()) maximum = maxOf(maximum, rows.getJSONObject(index).getDouble(key))
        return maximum
    }
}
