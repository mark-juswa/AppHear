package com.example.apphear.p8c1

import android.content.Context
import com.example.apphear.p8b.P8bStats
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.abs

/** P8-C1 static gate: unchanged P8-B raw fixtures through the native P7D-R2 preprocessor. */
internal object P8c1StaticVerifier {
    private const val MANIFEST = "p8b/android_preprocessing_fixture_manifest.json"

    fun verify(context: Context): JSONObject {
        val manifest = JSONObject(context.assets.open(MANIFEST).bufferedReader().readText())
        val fixtures = manifest.getJSONArray("fixtures")
        val aggregate = DoubleArray(fixtures.length() * FLOATS)
        val rows = JSONArray()
        var aggregateOffset = 0
        var allPass = true
        for (fixtureIndex in 0 until fixtures.length()) {
            val fixture = fixtures.getJSONObject(fixtureIndex)
            val width = fixture.getInt("width")
            val height = fixture.getInt("height")
            val rgb = readVerified(context, fixture.getString("rgb_asset"), fixture.getString("rgb_sha256"))
            val expected = readFloats(
                readVerified(
                    context,
                    fixture.getString("expected_tensor_asset"),
                    fixture.getString("expected_tensor_sha256"),
                ),
            )
            val rgba = ByteBuffer.allocateDirect(width * height * 4).order(ByteOrder.nativeOrder())
            var source = 0
            repeat(width * height) {
                rgba.put(rgb[source++]).put(rgb[source++]).put(rgb[source++]).put(0xff.toByte())
            }
            rgba.rewind()
            P8c1NativePreprocessor(width, height, width * 4, 4, 0).use { native ->
                native.run(rgba)
                val actual = FloatArray(FLOATS)
                native.input.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer().get(actual)
                val differences = DoubleArray(FLOATS)
                var changed = 0
                var finite = true
                for (index in actual.indices) {
                    val difference = abs(actual[index] - expected[index]).toDouble()
                    differences[index] = difference
                    aggregate[aggregateOffset + index] = difference
                    if (difference != 0.0) changed++
                    if (!actual[index].isFinite() || !difference.isFinite()) finite = false
                }
                aggregateOffset += FLOATS
                val stats = P8bStats.summarize(differences)
                val geometryExact = native.transform.rw == fixture.getInt("resized_width") &&
                    native.transform.rh == fixture.getInt("resized_height") &&
                    native.transform.left == fixture.getInt("left") &&
                    native.transform.top == fixture.getInt("top")
                val pass = finite && geometryExact && stats.mean <= 1e-6 && stats.p95 <= 2e-6 &&
                    stats.maximum <= 1e-5
                allPass = allPass && pass
                rows.put(
                    JSONObject().put("fixture_id", fixture.getString("fixture_id"))
                        .put("source", fixture.getString("source"))
                        .put("shape", JSONArray(listOf(1, 384, 384, 3)))
                        .put("mean_absolute", stats.mean).put("p95_absolute", stats.p95)
                        .put("maximum_absolute", stats.maximum)
                        .put("different_elements", changed)
                        .put("different_fraction", changed.toDouble() / FLOATS)
                        .put("finite", finite).put("letterbox_geometry_exact", geometryExact)
                        .put("resized_width", native.transform.rw).put("resized_height", native.transform.rh)
                        .put("left", native.transform.left).put("top", native.transform.top)
                        .put("status", if (pass) "PASS" else "FAIL"),
                )
            }
        }
        val aggregateStats = P8bStats.summarize(aggregate)
        val result = JSONObject().put("schema", "P8C1_STATIC_PREPROCESSING_PARITY_V1")
            .put("status", if (allPass) "PASS" else "FAIL")
            .put("fixtures", fixtures.length()).put("elements", aggregate.size)
            .put("mean_absolute", aggregateStats.mean).put("p95_absolute", aggregateStats.p95)
            .put("maximum_absolute", aggregateStats.maximum)
            .put("letterbox_geometry_all_exact", (0 until rows.length()).all {
                rows.getJSONObject(it).getBoolean("letterbox_geometry_exact")
            })
            .put("finite", (0 until rows.length()).all { rows.getJSONObject(it).getBoolean("finite") })
            .put("tolerances", JSONObject().put("mean", 1e-6).put("p95", 2e-6).put("maximum", 1e-5))
            .put("per_fixture", rows)
        val root = File(requireNotNull(context.getExternalFilesDir(null)), "p8c1").also { it.mkdirs() }
        File(root, "static_preprocessing_parity.json").writeText(result.toString(2))
        return result
    }

    private fun readVerified(context: Context, asset: String, expected: String): ByteArray {
        val bytes = context.assets.open(asset).use { it.readBytes() }
        val actual = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
        require(actual == expected) { "P8C1_FIXTURE_HASH_MISMATCH:$asset" }
        return bytes
    }

    private fun readFloats(bytes: ByteArray): FloatArray {
        val view = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(view.remaining()).also { view.get(it) }
    }

    private const val FLOATS = 384 * 384 * 3
}
