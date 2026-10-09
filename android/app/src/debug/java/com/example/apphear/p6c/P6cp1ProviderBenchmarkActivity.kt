package com.example.apphear.p6c

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtProvider
import ai.onnxruntime.OrtSession
import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.util.Log
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/**
 * P6C-P1 debug-only/default-off prepared-tensor harness.
 *
 * It tests only the frozen FP32 ONNX graph with XNNPACK or NNAPI. It never opens CameraX,
 * invokes the recognizer, or changes the frozen decoder/V2 contract.
 */
class P6cp1ProviderBenchmarkActivity : Activity() {
    private lateinit var status: TextView
    private val started = AtomicBoolean(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status = TextView(this).apply {
            text = "P6C-P1 provider triage: validating request"
            setPadding(24, 24, 24, 24)
        }
        setContentView(status)
        if (started.compareAndSet(false, true)) {
            thread(name = "p6cp1-provider-runner") { runRequestedMode() }
        }
    }

    private fun runRequestedMode() {
        val root = File(getExternalFilesDir(null), "p6cp1")
        root.mkdirs()
        try {
            val provider = Provider.parse(intent.getStringExtra("provider"))
            val mode = intent.getStringExtra("mode")?.lowercase()
            require(mode == "semantic" || mode == "benchmark") {
                "Only semantic/benchmark modes are authorized"
            }
            val p6cRoot = File(getExternalFilesDir(null), "p6c")
            val model = File(p6cRoot, "frozen_dwpose_l_fp32.onnx")
            require(model.isFile && sha256(model) == EXPECTED_ONNX_SHA) {
                "P6CP1_FROZEN_ONNX_IDENTITY_MISMATCH"
            }
            val manifest = File(File(root, "prepared_tensor_pack"), "semantic_manifest.tsv")
            require(manifest.isFile) { "Missing prepared tensor manifest: $manifest" }
            val fixtures = manifest.readLines().drop(1).filter { it.isNotBlank() }.map(FixtureRow::parse)
            require(fixtures.size == 12) { "Expected 12 frozen semantic fixtures, found ${fixtures.size}" }
            require(fixtures.groupingBy { it.category }.eachCount() == mapOf("ZERO" to 4, "ONE" to 4, "TWO" to 4))

            val available = OrtEnvironment.getAvailableProviders().map { it.name }.sorted()
            val required = if (provider == Provider.XNNPACK) OrtProvider.XNNPACK else OrtProvider.NNAPI
            require(OrtEnvironment.getAvailableProviders().contains(required)) {
                "${provider.id}_PROVIDER_UNAVAILABLE_IN_INSTALLED_ORT_PACKAGE"
            }

            if (mode == "semantic") runSemantic(root, model, provider, fixtures, available)
            else runBenchmark(root, model, provider, fixtures, available)
        } catch (error: Throwable) {
            val provider = intent.getStringExtra("provider")?.uppercase() ?: "UNKNOWN"
            val available = runCatching {
                OrtEnvironment.getAvailableProviders().map { it.name }.sorted()
            }.getOrDefault(emptyList())
            File(root, "${provider.lowercase()}_availability.json").writeText(
                JSONObject()
                    .put("provider", provider)
                    .put("ort_version", runCatching { OrtEnvironment.getEnvironment().version }.getOrDefault("UNKNOWN"))
                    .put("android_api", Build.VERSION.SDK_INT)
                    .put("available_providers", JSONArray(available))
                    .put("registered", false)
                    .put("session_created", false)
                    .put("error", error.toString())
                    .toString(2),
            )
            File(root, "${provider.lowercase()}_run_error.json").writeText(
                JSONObject()
                    .put("provider", provider)
                    .put("mode", intent.getStringExtra("mode") ?: "UNKNOWN")
                    .put("error", error.stackTraceToString())
                    .toString(2),
            )
            show("P6C-P1 blocked: ${error.message}")
            Log.e(TAG, "P6CP1_${provider}_RUN_FAILED", error)
        }
    }

    private fun runSemantic(
        root: File,
        model: File,
        provider: Provider,
        fixtures: List<FixtureRow>,
        available: List<String>,
    ) {
        val environment = OrtEnvironment.getEnvironment()
        val profilePrefix = File(root, "${provider.id.lowercase()}_ort_profile").absolutePath
        val options = configuredOptions(provider, enableProfiling = true, profilePrefix = profilePrefix)
        val loadStarted = System.nanoTime()
        environment.createSession(model.absolutePath, options).use { session ->
            val loadMs = elapsedMs(loadStarted)
            val output = File(root, "${provider.id.lowercase()}_semantic_outputs.jsonl")
            output.bufferedWriter().use { writer ->
                fixtures.forEachIndexed { index, row ->
                    val input = loadInput(root, row)
                    val inferenceStarted = System.nanoTime()
                    val decoded = runDecoded(environment, session, input, row)
                    val inferenceMs = elapsedMs(inferenceStarted)
                    val v2 = P6cV2Math.build(decoded.xy, decoded.scores)
                    writer.append(semanticJson(provider, row, decoded, v2, inferenceMs, loadMs).toString())
                        .append('\n')
                    writer.flush()
                    show("P6C-P1 ${provider.id} semantic ${index + 1}/12")
                }
            }
            val profilePath = session.endProfiling()
            val deterministicProfile = File(root, "${provider.id.lowercase()}_ort_profile.json")
            val generatedProfile = File(profilePath)
            if (generatedProfile.isFile) {
                generatedProfile.copyTo(deterministicProfile, overwrite = true)
            }
            val availability = JSONObject()
                .put("provider", provider.id)
                .put("ort_version", environment.version)
                .put("android_api", Build.VERSION.SDK_INT)
                .put("available_providers", JSONArray(available))
                .put("registered", true)
                .put("session_created", true)
                .put("model_load_ms", loadMs)
                .put("profile_path", profilePath)
                .put("deterministic_profile_path", deterministicProfile.absolutePath)
                .put("profiling_available", deterministicProfile.isFile)
                .put("configuration", providerConfiguration(provider))
            File(root, "${provider.id.lowercase()}_availability.json").writeText(availability.toString(2))
        }
        options.close()
        show("P6C-P1 ${provider.id} semantic run complete")
        Log.i(TAG, "P6CP1_${provider.id}_SEMANTIC_COMPLETE")
    }

    private fun runBenchmark(
        root: File,
        model: File,
        provider: Provider,
        fixtures: List<FixtureRow>,
        available: List<String>,
    ) {
        val passMarker = File(root, "${provider.id.lowercase()}_semantic_host_pass.json")
        require(passMarker.isFile && passMarker.readText().contains("\"semantic_parity\": \"PASS\"")) {
            "P6CP1_${provider.id}_BENCHMARK_BLOCKED_SEMANTIC_HOST_PASS_REQUIRED"
        }
        val warmupSeconds = intent.getIntExtra("warmup_seconds", 30)
        val measuredSeconds = intent.getIntExtra("measured_seconds", 180)
        require(warmupSeconds == 30 && measuredSeconds == 180) {
            "P6C-P1 protocol is frozen at 30s warm-up + 180s measured"
        }

        val environment = OrtEnvironment.getEnvironment()
        val options = configuredOptions(provider, enableProfiling = false, profilePrefix = null)
        val loadStarted = System.nanoTime()
        environment.createSession(model.absolutePath, options).use { session ->
            val loadMs = elapsedMs(loadStarted)
            val tensors = fixtures.map { row ->
                OnnxTensor.createTensor(
                    environment,
                    FloatBuffer.wrap(loadInput(root, row)),
                    longArrayOf(1, 3, 256, 192),
                )
            }
            try {
                val warmupDeadline = System.nanoTime() + warmupSeconds * 1_000_000_000L
                var cursor = 0
                while (System.nanoTime() < warmupDeadline) {
                    session.run(mapOf("input" to tensors[cursor % tensors.size])).use { }
                    cursor++
                    if (cursor % 10 == 0) show("P6C-P1 ${provider.id} warm-up: $cursor inferences")
                }

                val latencies = ArrayList<Double>()
                val thermal = ArrayList<Int>()
                var peakPssKb = 0L
                val measuredStarted = System.nanoTime()
                val measuredDeadline = measuredStarted + measuredSeconds * 1_000_000_000L
                cursor = 0
                while (System.nanoTime() < measuredDeadline) {
                    val inferenceStarted = System.nanoTime()
                    session.run(mapOf("input" to tensors[cursor % tensors.size])).use { }
                    latencies.add(elapsedMs(inferenceStarted))
                    peakPssKb = maxOf(peakPssKb, Debug.getPss())
                    thermal.add((getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus)
                    cursor++
                    if (cursor % 10 == 0) show("P6C-P1 ${provider.id} measured: $cursor inferences")
                }
                val elapsedSeconds = (System.nanoTime() - measuredStarted) / 1_000_000_000.0
                require(latencies.isNotEmpty()) { "No measured inference completed" }
                val result = JSONObject()
                    .put("provider", provider.id)
                    .put("ort_version", environment.version)
                    .put("available_providers", JSONArray(available))
                    .put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
                    .put("soc", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else "UNKNOWN")
                    .put("android_version", Build.VERSION.RELEASE)
                    .put("model_load_ms", loadMs)
                    .put("warmup_seconds", warmupSeconds)
                    .put("measured_seconds_requested", measuredSeconds)
                    .put("measured_seconds_actual", elapsedSeconds)
                    .put("inference_count", latencies.size)
                    .put("sustained_backend_fps", latencies.size / elapsedSeconds)
                    .put("backend_p50_ms", percentile(latencies, 0.50))
                    .put("backend_p90_ms", percentile(latencies, 0.90))
                    .put("backend_p95_ms", percentile(latencies, 0.95))
                    .put("backend_max_ms", latencies.maxOrNull())
                    .put("peak_pss_kb", peakPssKb)
                    .put("java_heap_bytes", Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory())
                    .put("native_heap_bytes", Debug.getNativeHeapAllocatedSize())
                    .put("thermal_status_samples", JSONArray(thermal))
                    .put("runtime_errors", JSONArray())
                    .put("crashes", 0)
                    .put("oom", false)
                    .put("batch_size", 1)
                    .put("single_stream", true)
                    .put("prepared_tensor_input", true)
                    .put("configuration", providerConfiguration(provider))
                File(root, "${provider.id.lowercase()}_backend_benchmark.json").writeText(result.toString(2))
            } finally {
                tensors.forEach { it.close() }
            }
        }
        options.close()
        show("P6C-P1 ${provider.id} backend benchmark complete")
        Log.i(TAG, "P6CP1_${provider.id}_BENCHMARK_COMPLETE")
    }

    private fun configuredOptions(
        provider: Provider,
        enableProfiling: Boolean,
        profilePrefix: String?,
    ): OrtSession.SessionOptions = OrtSession.SessionOptions().apply {
        setIntraOpNumThreads(1)
        setInterOpNumThreads(1)
        setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        when (provider) {
            Provider.XNNPACK -> {
                addConfigEntry("session.intra_op.allow_spinning", "0")
                addXnnpack(mapOf("intra_op_num_threads" to physicalCoreCount().toString()))
            }
            Provider.NNAPI -> addNnapi()
        }
        if (enableProfiling) enableProfiling(requireNotNull(profilePrefix))
    }

    private fun providerConfiguration(provider: Provider): JSONObject = when (provider) {
        Provider.XNNPACK -> JSONObject()
            .put("ort_intra_op_threads", 1)
            .put("ort_inter_op_threads", 1)
            .put("ort_intra_op_spinning", false)
            .put("xnnpack_intra_op_threads", physicalCoreCount())
            .put("device_reported_physical_cores", physicalCoreCount())
        Provider.NNAPI -> JSONObject()
            .put("flags", "DEFAULT_EMPTY")
            .put("fp16_relaxation", false)
            .put("cpu_fallback", "ORT_DEFAULT")
            .put("ort_intra_op_threads", 1)
            .put("ort_inter_op_threads", 1)
    }

    private fun loadInput(root: File, row: FixtureRow): FloatArray {
        val file = File(File(root, "prepared_tensor_pack"), row.tensorFile)
        require(file.isFile && sha256(file) == row.tensorSha256) { "Input hash mismatch: ${row.fixtureId}" }
        require(file.length() == INPUT_FLOATS * 4L) { "Input byte count mismatch: ${row.fixtureId}" }
        val buffer = ByteBuffer.wrap(file.readBytes()).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(INPUT_FLOATS).also { buffer.get(it) }
    }

    private fun runDecoded(
        environment: OrtEnvironment,
        session: OrtSession,
        input: FloatArray,
        row: FixtureRow,
    ): P6cV2Math.Decoded = OnnxTensor.createTensor(
        environment,
        FloatBuffer.wrap(input),
        longArrayOf(1, 3, 256, 192),
    ).use { tensor ->
        session.run(mapOf("input" to tensor)).use { result ->
            @Suppress("UNCHECKED_CAST")
            val x = (result.get("simcc_x").orElseThrow().value as Array<Array<FloatArray>>)[0]
            @Suppress("UNCHECKED_CAST")
            val y = (result.get("simcc_y").orElseThrow().value as Array<Array<FloatArray>>)[0]
            P6cV2Math.decode(
                x,
                y,
                floatArrayOf(row.centerX, row.centerY),
                floatArrayOf(row.scaleX, row.scaleY),
            )
        }
    }

    private fun semanticJson(
        provider: Provider,
        row: FixtureRow,
        decoded: P6cV2Math.Decoded,
        v2: P6cV2Math.V2Result,
        inferenceMs: Double,
        modelLoadMs: Double,
    ): JSONObject = JSONObject()
        .put("fixture_id", row.fixtureId)
        .put("category", row.category)
        .put("provider", provider.id)
        .put("model_load_ms", modelLoadMs)
        .put("backend_inference_ms", inferenceMs)
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
        val tensorFile: String,
        val tensorSha256: String,
        val centerX: Float,
        val centerY: Float,
        val scaleX: Float,
        val scaleY: Float,
    ) {
        companion object {
            fun parse(line: String): FixtureRow {
                val values = line.split('\t')
                require(values.size == 8)
                return FixtureRow(
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4].toFloat(),
                    values[5].toFloat(),
                    values[6].toFloat(),
                    values[7].toFloat(),
                )
            }
        }
    }

    private enum class Provider(val id: String) {
        XNNPACK("XNNPACK"),
        NNAPI("NNAPI");

        companion object {
            fun parse(value: String?): Provider = when (value?.uppercase()) {
                "XNNPACK" -> XNNPACK
                "NNAPI" -> NNAPI
                else -> error("Only XNNPACK and NNAPI are authorized")
            }
        }
    }

    companion object {
        private const val TAG = "P6CP1"
        private const val INPUT_FLOATS = 1 * 3 * 256 * 192
        private const val EXPECTED_ONNX_SHA = "870c84ddbf396282c415854b233ba972a772ac35f1eebe26b6ce185a19579965"

        private fun elapsedMs(startNanos: Long): Double = (System.nanoTime() - startNanos) / 1_000_000.0

        private fun percentile(values: List<Double>, quantile: Double): Double {
            val sorted = values.sorted()
            return sorted[(quantile * (sorted.size - 1)).toInt()]
        }

        private fun physicalCoreCount(): Int = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)

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
