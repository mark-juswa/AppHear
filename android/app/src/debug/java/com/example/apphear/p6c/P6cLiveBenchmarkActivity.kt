package com.example.apphear.p6c

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.Manifest
import android.app.ActivityManager
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.util.Log
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.FloatBuffer
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.ceil
import kotlin.math.floor

/** P6-C Stage-B live CameraX benchmark. It refuses to start without a host-issued Stage-A pass. */
class P6cLiveBenchmarkActivity : AppCompatActivity() {
    private lateinit var status: TextView
    private val executor = Executors.newSingleThreadExecutor()
    private val running = AtomicBoolean(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status = TextView(this).apply { text = "P6-C live benchmark: validating gate"; setPadding(24, 24, 24, 24) }
        setContentView(status)
        val root = File(getExternalFilesDir(null), "p6c")
        val marker = File(root, "stage_a_host_pass.json")
        if (!marker.isFile || !marker.readText().contains("\"stage_a\": \"PASS\"")) {
            fail(root, "P6C_STAGE_B_BLOCKED_STAGE_A_HOST_PASS_REQUIRED")
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CAMERA), CAMERA_REQUEST)
        } else {
            start(root)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_REQUEST && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            start(File(getExternalFilesDir(null), "p6c"))
        } else fail(File(getExternalFilesDir(null), "p6c"), "CAMERA_PERMISSION_DENIED")
    }

    private fun start(root: File) {
        if (!running.compareAndSet(false, true)) return
        val model = File(root, "frozen_dwpose_l_fp32.onnx")
        if (!model.isFile || sha256(model) != EXPECTED_ONNX_SHA) {
            fail(root, "P6C_FROZEN_ONNX_IDENTITY_MISMATCH")
            return
        }
        val warmupSeconds = intent.getIntExtra("warmup_seconds", 30)
        val measuredSeconds = intent.getIntExtra("measured_seconds", 180)
        require(warmupSeconds == 30 && measuredSeconds == 180) { "P6-C protocol is frozen at 30s warm-up + 180s measured" }
        executor.execute {
            try {
                val environment = OrtEnvironment.getEnvironment()
                val options = OrtSession.SessionOptions().apply {
                    setIntraOpNumThreads(1); setInterOpNumThreads(1)
                    setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
                }
                val loadStarted = System.nanoTime()
                val session = environment.createSession(model.absolutePath, options)
                val loadMs = (System.nanoTime() - loadStarted) / 1_000_000.0
                runOnUiThread { bindCamera(root, environment, session, loadMs, warmupSeconds, measuredSeconds) }
            } catch (error: Throwable) { fail(root, error.stackTraceToString()) }
        }
    }

    private fun bindCamera(root: File, environment: OrtEnvironment, session: OrtSession, loadMs: Double, warmupSeconds: Int, measuredSeconds: Int) {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                val provider = future.get()
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                    .build()
                val state = BenchmarkState(root, loadMs, warmupSeconds, measuredSeconds)
                analysis.setAnalyzer(executor) { image -> analyze(image, environment, session, state, provider) }
                provider.unbindAll()
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_FRONT_CAMERA, analysis)
                show("P6-C warm-up: ${warmupSeconds}s")
            } catch (error: Throwable) { fail(root, error.stackTraceToString()) }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun analyze(image: ImageProxy, environment: OrtEnvironment, session: OrtSession, state: BenchmarkState, provider: ProcessCameraProvider) {
        if (state.isFinished()) {
            image.close()
            return
        }
        val frameStarted = System.nanoTime()
        try {
            val preprocessStarted = System.nanoTime()
            val input = preprocess(image)
            val preprocessMs = (System.nanoTime() - preprocessStarted) / 1_000_000.0
            val inferenceStarted = System.nanoTime()
            val decoded = OnnxTensor.createTensor(environment, FloatBuffer.wrap(input.values), longArrayOf(1, 3, 256, 192)).use { tensor ->
                session.run(mapOf("input" to tensor)).use { result ->
                    @Suppress("UNCHECKED_CAST") val x = (result.get("simcc_x").orElseThrow().value as Array<Array<FloatArray>>)[0]
                    @Suppress("UNCHECKED_CAST") val y = (result.get("simcc_y").orElseThrow().value as Array<Array<FloatArray>>)[0]
                    P6cV2Math.decode(x, y, input.center, input.scale)
                }
            }
            val inferenceDecodeMs = (System.nanoTime() - inferenceStarted) / 1_000_000.0
            val v2Started = System.nanoTime()
            P6cV2Math.build(decoded.xy, decoded.scores)
            val v2Ms = (System.nanoTime() - v2Started) / 1_000_000.0
            state.record(preprocessMs, inferenceDecodeMs, v2Ms, (System.nanoTime() - frameStarted) / 1_000_000.0)
            if (state.done() && state.markFinished()) {
                state.writeResult()
                runOnUiThread {
                    provider.unbindAll()
                    session.close()
                    show("P6-C live benchmark complete; pull device_runtime_summary.json")
                    Log.i("P6C", "P6C_LIVE_BENCHMARK_COMPLETE")
                }
            } else show(state.status())
        } catch (error: Throwable) {
            state.errors.add(error.toString())
            if (state.markFinished()) state.writeResult()
            runOnUiThread { provider.unbindAll(); session.close(); fail(state.root, error.stackTraceToString()) }
        } finally { image.close() }
    }

    private data class Prepared(val values: FloatArray, val center: FloatArray, val scale: FloatArray)

    private fun preprocess(image: ImageProxy): Prepared {
        val rotation = image.imageInfo.rotationDegrees
        val sourceWidth = if (rotation == 90 || rotation == 270) image.height else image.width
        val sourceHeight = if (rotation == 90 || rotation == 270) image.width else image.height
        val center = floatArrayOf(sourceWidth * 0.5f, sourceHeight * 0.5f)
        val scale = floatArrayOf(sourceWidth * 1.25f, sourceHeight * 1.25f)
        val aspect = 192f / 256f
        if (scale[0] > scale[1] * aspect) scale[1] = scale[0] / aspect else scale[0] = scale[1] * aspect
        val plane = image.planes[0]
        val bytes = ByteArray(plane.buffer.remaining()).also { plane.buffer.get(it) }
        val mean = floatArrayOf(123.675f, 116.28f, 103.53f)
        val std = floatArrayOf(58.395f, 57.12f, 57.375f)
        val output = FloatArray(3 * 256 * 192)
        for (dy in 0 until 256) for (dx in 0 until 192) {
            val sx = (dx.toFloat() / 192f * scale[0] + center[0] - 0.5f * scale[0])
            val sy = (dy.toFloat() / 256f * scale[1] + center[1] - 0.5f * scale[1])
            val rgb = bilinearRgba(bytes, image.width, image.height, plane.rowStride, plane.pixelStride, rotation, sx, sy)
            val pixel = dy * 192 + dx
            for (channel in 0..2) output[channel * 256 * 192 + pixel] = (rgb[channel] - mean[channel]) / std[channel]
        }
        return Prepared(output, center, scale)
    }

    private fun bilinearRgba(bytes: ByteArray, width: Int, height: Int, rowStride: Int, pixelStride: Int, rotation: Int, x: Float, y: Float): FloatArray {
        val x0 = floor(x).toInt(); val y0 = floor(y).toInt(); val x1 = x0 + 1; val y1 = y0 + 1
        val wx = x - x0; val wy = y - y0
        fun pixel(orientedX: Int, orientedY: Int, channel: Int): Float {
            val (rawX, rawY) = when (rotation) {
                90 -> Pair(orientedY, height - 1 - orientedX)
                180 -> Pair(width - 1 - orientedX, height - 1 - orientedY)
                270 -> Pair(width - 1 - orientedY, orientedX)
                else -> Pair(orientedX, orientedY)
            }
            if (rawX !in 0 until width || rawY !in 0 until height) return 0f
            return (bytes[rawY * rowStride + rawX * pixelStride + channel].toInt() and 0xff).toFloat()
        }
        return FloatArray(3) { channel ->
            val top = pixel(x0, y0, channel) * (1f - wx) + pixel(x1, y0, channel) * wx
            val bottom = pixel(x0, y1, channel) * (1f - wx) + pixel(x1, y1, channel) * wx
            top * (1f - wy) + bottom * wy
        }
    }

    private inner class BenchmarkState(val root: File, val modelLoadMs: Double, warmupSeconds: Int, measuredSeconds: Int) {
        private val started = System.nanoTime(); private val warmupNanos = warmupSeconds * 1_000_000_000L; private val endNanos = (warmupSeconds + measuredSeconds) * 1_000_000_000L
        private val finished = AtomicBoolean(false)
        private val preprocess = mutableListOf<Double>(); private val backend = mutableListOf<Double>(); private val v2 = mutableListOf<Double>(); private val total = mutableListOf<Double>()
        val errors = mutableListOf<String>(); private var peakPssKb = 0L; private val thermal = mutableListOf<Int>()
        fun record(pre: Double, back: Double, v2Ms: Double, totalMs: Double) {
            val elapsed = System.nanoTime() - started
            if (elapsed >= warmupNanos) { preprocess.add(pre); backend.add(back); v2.add(v2Ms); total.add(totalMs); peakPssKb = maxOf(peakPssKb, Debug.getPss()); thermal.add((getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus) }
        }
        fun done() = System.nanoTime() - started >= endNanos
        fun markFinished() = finished.compareAndSet(false, true)
        fun isFinished() = finished.get()
        fun status(): String = if (System.nanoTime() - started < warmupNanos) "P6-C warm-up" else "P6-C measured frames: ${total.size}"
        fun writeResult() {
            fun percentile(values: List<Double>, q: Double): Double? { if (values.isEmpty()) return null; val sorted=values.sorted(); return sorted[(q*(sorted.size-1)).toInt()] }
            val measuredDuration = 180.0
            val result = JSONObject()
                .put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
                .put("soc", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else "UNKNOWN")
                .put("android_version", Build.VERSION.RELEASE)
                .put("ort_version", "1.22.0").put("execution_provider", "CPUExecutionProvider")
                .put("model_load_ms", modelLoadMs).put("processed_frames", total.size)
                .put("sustained_fps", total.size / measuredDuration)
                .put("preprocessing_p50_ms", percentile(preprocess,.50)).put("backend_p50_ms", percentile(backend,.50))
                .put("backend_p90_ms", percentile(backend,.90)).put("backend_p95_ms", percentile(backend,.95)).put("backend_max_ms", backend.maxOrNull())
                .put("v2_build_p50_ms", percentile(v2,.50)).put("end_to_end_p50_ms", percentile(total,.50)).put("end_to_end_p95_ms", percentile(total,.95))
                .put("peak_pss_kb", peakPssKb).put("java_heap_bytes", Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory())
                .put("native_heap_bytes", Debug.getNativeHeapAllocatedSize()).put("thermal_status_samples", JSONArray(thermal))
                .put("errors", JSONArray(errors)).put("warmup_seconds",30).put("measured_seconds",180)
                .put("dropped_overwritten_frames", "NOT_DIRECTLY_OBSERVABLE_WITH_KEEP_ONLY_LATEST")
            File(root,"device_runtime_summary.json").writeText(result.toString(2))
        }
    }

    private fun show(value: String) = runOnUiThread { status.text = value }
    private fun fail(root: File, value: String) { root.mkdirs(); File(root,"live_benchmark_error.txt").writeText(value); show("P6-C blocked: ${value.lineSequence().first()}"); Log.e("P6C", value) }
    private fun sha256(file: File): String { val d=MessageDigest.getInstance("SHA-256"); file.inputStream().use { input -> val b=ByteArray(1024*1024); while(true){val n=input.read(b); if(n<=0)break; d.update(b,0,n)} }; return d.digest().joinToString(""){"%02x".format(it)} }
    override fun onDestroy() { executor.shutdownNow(); super.onDestroy() }
    companion object { private const val CAMERA_REQUEST=610; private const val EXPECTED_ONNX_SHA="870c84ddbf396282c415854b233ba972a772ac35f1eebe26b6ce185a19579965" }
}
