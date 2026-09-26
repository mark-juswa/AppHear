package com.example.apphear.p6c

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.app.Activity
import android.os.Bundle
import android.util.Log
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.FloatBuffer
import java.security.MessageDigest
import kotlin.concurrent.thread

/** ADB-only P6-C Stage-A runner. No launcher intent and no production-pipeline references. */
class P6cFixtureParityActivity : Activity() {
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status = TextView(this).apply { text = "P6-C fixture harness: starting"; setPadding(24, 24, 24, 24) }
        setContentView(status)
        thread(name = "p6c-fixture-runner") { runFixtureMode() }
    }

    private fun runFixtureMode() {
        val root = File(getExternalFilesDir(null), "p6c")
        val pack = File(root, "fixture_pack")
        val manifest = File(pack, "fixture_manifest.tsv")
        val model = File(root, "frozen_dwpose_l_fp32.onnx")
        val output = File(root, "android_fixture_outputs.jsonl")
        try {
            val mode = intent.getStringExtra("mode")?.lowercase()
            if (mode == "prepare") {
                require(pack.mkdirs() || pack.isDirectory)
                show("P6-C device directory prepared. Push the frozen model and fixture pack.")
                return
            }
            require(mode == "fixture") { "Only --es mode prepare/fixture is authorized before Stage-A host verification" }
            require(manifest.isFile) { "Missing $manifest" }
            require(model.isFile) { "Missing $model" }
            require(sha256(model) == EXPECTED_ONNX_SHA) { "P6C_FROZEN_ONNX_IDENTITY_MISMATCH" }
            val rows = manifest.readLines().drop(1).filter { it.isNotBlank() }.map { FixtureRow.parse(it) }
            require(rows.size == 60) { "Expected 60 fixtures, found ${rows.size}" }
            val environment = OrtEnvironment.getEnvironment()
            val options = OrtSession.SessionOptions().apply {
                setIntraOpNumThreads(1)
                setInterOpNumThreads(1)
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            }
            val loadStart = System.nanoTime()
            environment.createSession(model.absolutePath, options).use { session ->
                val modelLoadMs = (System.nanoTime() - loadStart) / 1_000_000.0
                output.bufferedWriter().use { writer ->
                    rows.forEachIndexed { index, row ->
                        val inputFile = File(pack, row.rgbFile)
                        require(sha256(inputFile) == row.rgbSha256) { "Input hash mismatch: ${row.fixtureId}" }
                        val input = normalizedNchw(inputFile)
                        val started = System.nanoTime()
                        val decoded = runOne(environment, session, input, row)
                        val latencyMs = (System.nanoTime() - started) / 1_000_000.0
                        val v2 = P6cV2Math.build(decoded.xy, decoded.scores)
                        writer.append(toJson(row, decoded, v2, latencyMs, modelLoadMs).toString()).append('\n')
                        writer.flush()
                        show("P6-C fixture ${index + 1}/60: ${row.fixtureId}")
                    }
                }
            }
            File(root, "fixture_run_complete.json").writeText(JSONObject().put("status", "COMPLETE").put("fixtures", 60).put("onnx_sha256", EXPECTED_ONNX_SHA).toString(2))
            show("P6-C Stage-A device run complete. Pull outputs and run host comparison.")
            Log.i(TAG, "P6C_FIXTURE_RUN_COMPLETE outputs=${output.absolutePath}")
        } catch (error: Throwable) {
            File(root, "fixture_run_error.txt").apply { parentFile?.mkdirs(); writeText(error.stackTraceToString()) }
            show("P6-C FAILED: ${error.message}")
            Log.e(TAG, "P6C_FIXTURE_RUN_FAILED", error)
        }
    }

    private fun runOne(environment: OrtEnvironment, session: OrtSession, input: FloatArray, row: FixtureRow): P6cV2Math.Decoded {
        OnnxTensor.createTensor(environment, FloatBuffer.wrap(input), longArrayOf(1, 3, 256, 192)).use { tensor ->
            session.run(mapOf("input" to tensor)).use { result ->
                @Suppress("UNCHECKED_CAST")
                val x = (result.get("simcc_x").orElseThrow().value as Array<Array<FloatArray>>)[0]
                @Suppress("UNCHECKED_CAST")
                val y = (result.get("simcc_y").orElseThrow().value as Array<Array<FloatArray>>)[0]
                return P6cV2Math.decode(x, y, floatArrayOf(row.centerX, row.centerY), floatArrayOf(row.scaleX, row.scaleY))
            }
        }
    }

    private fun toJson(row: FixtureRow, decoded: P6cV2Math.Decoded, v2: P6cV2Math.V2Result, latencyMs: Double, modelLoadMs: Double): JSONObject = JSONObject()
        .put("fixture_id", row.fixtureId)
        .put("category", row.category)
        .put("runtime", "ONNX_RUNTIME_ANDROID_FP32_CPU")
        .put("ort_version", "1.22.0")
        .put("execution_provider", "CPUExecutionProvider")
        .put("model_load_ms", modelLoadMs)
        .put("inference_decode_v2_ms", latencyMs)
        .put("xy", JSONArray(decoded.xy.toList()))
        .put("scores", JSONArray(decoded.scores.toList()))
        .put("valid", JSONArray(v2.valid.toList()))
        .put("left_observed", v2.leftObserved)
        .put("right_observed", v2.rightObserved)
        .put("center", JSONArray(listOf(v2.normalization.centerX, v2.normalization.centerY)))
        .put("scale", v2.normalization.scale)
        .put("center_method", v2.normalization.centerMethod)
        .put("scale_method", v2.normalization.scaleMethod)
        .put("v2", JSONArray(v2.features.toList()))

    private fun show(value: String) = runOnUiThread { status.text = value }

    private data class FixtureRow(
        val fixtureId: String,
        val category: String,
        val rgbFile: String,
        val rgbSha256: String,
        val centerX: Float,
        val centerY: Float,
        val scaleX: Float,
        val scaleY: Float,
    ) {
        companion object {
            fun parse(line: String): FixtureRow {
                val v = line.split('\t')
                require(v.size == 8)
                return FixtureRow(v[0], v[1], v[2], v[3], v[4].toFloat(), v[5].toFloat(), v[6].toFloat(), v[7].toFloat())
            }
        }
    }

    companion object {
        private const val TAG = "P6C"
        private const val EXPECTED_ONNX_SHA = "870c84ddbf396282c415854b233ba972a772ac35f1eebe26b6ce185a19579965"
        private fun normalizedNchw(file: File): FloatArray {
            val bytes = file.readBytes()
            require(bytes.size == 192 * 256 * 3)
            val mean = floatArrayOf(123.675f, 116.28f, 103.53f)
            val std = floatArrayOf(58.395f, 57.12f, 57.375f)
            val output = FloatArray(3 * 256 * 192)
            for (pixel in 0 until 192 * 256) {
                for (channel in 0..2) {
                    val unsigned = bytes[pixel * 3 + channel].toInt() and 0xff
                    output[channel * 256 * 192 + pixel] = (unsigned.toFloat() - mean[channel]) / std[channel]
                }
            }
            return output
        }
        private fun sha256(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(1024 * 1024)
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    digest.update(buffer, 0, read)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
