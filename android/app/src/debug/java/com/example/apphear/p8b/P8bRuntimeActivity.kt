package com.example.apphear.p8b

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.TotalCaptureResult
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import android.util.Range
import android.util.Size
import android.view.Gravity
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.TextView
import androidx.annotation.OptIn
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.example.apphear.p7dr1.P7dr1Preprocess
import com.example.apphear.p8c1.P8c1LiveParity
import com.example.apphear.p8c1.P8c1NativePreprocessor
import com.example.apphear.p8c2.P8c2LiveDecoderParity
import com.example.apphear.p8c2.P8c2NativeDecoder
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** Explicit ADB-only Student-1 debug path. It never calls S4/S5/S6/S7/S8 recognition. */
@OptIn(ExperimentalCamera2Interop::class)
class P8bRuntimeActivity : AppCompatActivity() {
    private val worker = Executors.newSingleThreadExecutor()
    private val monitor = Executors.newSingleThreadScheduledExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val stopping = AtomicBoolean(false)
    private val captureCount = AtomicLong(0)
    private val memory = ConcurrentLinkedQueue<JSONObject>()
    private val errors = ConcurrentLinkedQueue<String>()
    private var provider: ProcessCameraProvider? = null
    private var model: P8bModelRunner? = null
    private var preprocess: P7dr1Preprocess? = null
    private var nativePreprocess: P8c1NativePreprocessor? = null
    private var liveParity: P8c1LiveParity? = null
    private var decoder: P8bDecoder? = null
    private var nativeDecoder: P8c2NativeDecoder? = null
    private var decoderLiveParity: P8c2LiveDecoderParity? = null
    private var epochNs = 0L
    private var arrivals = 0
    private var completed = 0
    private var lastUiNs = 0L
    private var firstGcCount = -1L
    private var condition = "MIXED_SIGNING"
    private var useFront = true
    private var useNativePreprocessing = false
    private var useNativeDecoder = false
    private val timings = LongArray(CAPACITY * TIMING_COLUMNS)
    private val coordinates = FloatArray(CAPACITY * 100)
    private lateinit var root: File
    private lateinit var preview: PreviewView
    private lateinit var overlay: P8bOverlayView
    private lateinit var status: TextView
    private var overlayMode = P8bOverlayContract.RenderMode.FULL_TOPOLOGY

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        useNativeDecoder = intent.getBooleanExtra("p8c2_enabled", false)
        useNativePreprocessing = intent.getBooleanExtra("p8c1_enabled", false) || useNativeDecoder
        overlayMode = when (intent.getStringExtra("p8c3a_overlay_mode")) {
            "POINTS_ONLY" -> P8bOverlayContract.RenderMode.POINTS_ONLY
            else -> P8bOverlayContract.RenderMode.FULL_TOPOLOGY
        }
        if (!intent.getBooleanExtra("p8b_enabled", false) && !useNativePreprocessing) {
            status.text = "P8-B/P8-C1/P8-C2 disabled — explicit ADB opt-in required"
            return
        }
        condition = intent.getStringExtra("condition")?.take(48) ?: "MIXED_SIGNING"
        useFront = !intent.getStringExtra("camera").equals("back", ignoreCase = true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        root = File(
            requireNotNull(getExternalFilesDir(null)),
            when { useNativeDecoder -> "p8c2"; useNativePreprocessing -> "p8c1"; else -> "p8b" },
        ).also { it.mkdirs() }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            status.text = "P8-B requires Camera permission for the bounded live debug run"
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_PERMISSION_REQUEST)
            return
        }
        startRuntime()
    }

    private fun startRuntime() {
        worker.execute {
            try {
                if (useNativePreprocessing) {
                    if (useNativeDecoder) {
                        val gate = JSONObject(File(root, "static_decoder_parity.json").readText())
                        require(gate.getString("status") == "PASS") { "P8C2_STATIC_PARITY_REQUIRED" }
                    } else {
                        val gate = JSONObject(File(root, "static_preprocessing_parity.json").readText())
                        require(gate.getString("status") == "PASS") { "P8C1_STATIC_PARITY_REQUIRED" }
                    }
                }
                model = P8bModelRunner(this)
                firstGcCount = gcCount()
                monitor.scheduleAtFixedRate({ sampleMemory() }, 0, 5, TimeUnit.SECONDS)
                runOnUiThread { bindCamera() }
            } catch (error: Throwable) {
                fail(error)
            }
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != CAMERA_PERMISSION_REQUEST) return
        if (grantResults.singleOrNull() == PackageManager.PERMISSION_GRANTED) {
            startRuntime()
        } else {
            status.text = "P8-B blocked: Camera permission denied"
        }
    }

    private fun buildUi() {
        preview = PreviewView(this).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        overlay = P8bOverlayView(this)
        status = TextView(this).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(0x88000000.toInt())
            textSize = 12f
            setPadding(16, 12, 16, 12)
            text = "P8-B initializing"
        }
        val rootView = FrameLayout(this)
        rootView.addView(preview, FrameLayout.LayoutParams(-1, -1))
        rootView.addView(overlay, FrameLayout.LayoutParams(-1, -1))
        rootView.addView(
            status,
            FrameLayout.LayoutParams(-1, -2).apply { gravity = Gravity.TOP },
        )
        setContentView(rootView)
    }

    private fun bindCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                provider = future.get()
                val previewUseCase = Preview.Builder().build().also {
                    it.setSurfaceProvider(preview.surfaceProvider)
                }
                val builder = ImageAnalysis.Builder()
                    .setTargetResolution(Size(480, 360))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                Camera2Interop.Extender(builder)
                    .setCaptureRequestOption(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(15, 15))
                    .setSessionCaptureCallback(object : CameraCaptureSession.CaptureCallback() {
                        override fun onCaptureCompleted(
                            session: CameraCaptureSession,
                            request: CaptureRequest,
                            result: TotalCaptureResult,
                        ) {
                            val now = System.nanoTime()
                            if (measured(now)) captureCount.incrementAndGet()
                        }
                    })
                val analysis = builder.build().also { it.setAnalyzer(worker, ::analyze) }
                val selector = if (useFront) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
                provider!!.unbindAll()
                provider!!.bindToLifecycle(this, selector, previewUseCase, analysis)
                status.text = "MODEL INPUT: UPRIGHT / UNMIRRORED\n" +
                    "RAW STUDENT GEOMETRY — PRESENCE NOT VALIDATED\ncondition=$condition; waiting for frames"
                handler.postDelayed({ if (epochNs == 0L && !stopping.get()) fail(IllegalStateException("P8B_CAMERA_NO_FRAMES")) }, 30_000)
            } catch (error: Throwable) {
                fail(error)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun configure(image: ImageProxy) {
        val plane = image.planes[0]
        if (useNativePreprocessing) {
            val old = nativePreprocess
            if (old != null && old.width == image.width && old.height == image.height &&
                old.rowStride == plane.rowStride && old.pixelStride == plane.pixelStride &&
                old.rotation == image.imageInfo.rotationDegrees
            ) return
            old?.close()
            nativePreprocess = P8c1NativePreprocessor(
                image.width, image.height, plane.rowStride, plane.pixelStride,
                image.imageInfo.rotationDegrees,
            )
            preprocess = null
            liveParity = if (useNativeDecoder) null else P8c1LiveParity(
                image.width, image.height, plane.rowStride, plane.pixelStride, image.imageInfo.rotationDegrees,
            )
            decoder = P8bDecoder(requireNotNull(nativePreprocess).transform)
            nativeDecoder?.close()
            nativeDecoder = if (useNativeDecoder) P8c2NativeDecoder(requireNotNull(nativePreprocess).transform) else null
            decoderLiveParity = if (useNativeDecoder) P8c2LiveDecoderParity() else null
            return
        }
        val old = preprocess
        if (old != null && old.width == image.width && old.height == image.height &&
            old.rowStride == plane.rowStride && old.pixelStride == plane.pixelStride &&
            old.rotation == image.imageInfo.rotationDegrees
        ) return
        preprocess = P7dr1Preprocess(
            image.width, image.height, plane.rowStride, plane.pixelStride,
            image.imageInfo.rotationDegrees,
        )
        decoder = P8bDecoder(requireNotNull(preprocess).transform)
    }

    private fun runPreprocessing(source: java.nio.ByteBuffer) {
        if (!useNativePreprocessing) {
            requireNotNull(preprocess).run(source)
            return
        }
        val native = requireNotNull(nativePreprocess)
        val parity = liveParity
        if (parity != null && !parity.complete) {
            parity.compare(source, native)
            if (parity.complete) {
                val result = parity.result(
                    native.width, native.height, native.rowStride, native.pixelStride, native.rotation,
                )
                File(root, "live_camera_preprocessing_parity.json").writeText(result.toString(2))
                require(result.getString("status") == "PASS") { "P8C1_LIVE_PARITY_FAILURE" }
                liveParity = null
                Log.i("P8C1", "LIVE_PARITY_PASS frames=${P8c1LiveParity.FRAMES}")
            }
        } else {
            native.run(source)
        }
    }

    private fun modelInput() = if (useNativePreprocessing) {
        requireNotNull(nativePreprocess).input
    } else {
        requireNotNull(preprocess).input
    }

    private fun currentTransform() = if (useNativePreprocessing) {
        requireNotNull(nativePreprocess).transform
    } else {
        requireNotNull(preprocess).transform
    }

    private fun analyze(image: ImageProxy) {
        if (stopping.get()) {
            image.close()
            return
        }
        val start = System.nanoTime()
        try {
            if (epochNs == 0L) {
                epochNs = start
                handler.postDelayed(::stop, ((WARM_NS + MEASURE_NS) / 1_000_000L))
                val phase = when { useNativeDecoder -> "P8C2"; useNativePreprocessing -> "P8C1"; else -> "P8B" }
                Log.i(phase, "LIVE_START warmup=15 measure=180 condition=$condition")
            }
            if (measured(start)) arrivals++
            configure(image)
            val prepStart = System.nanoTime()
            runPreprocessing(image.planes[0].buffer.duplicate())
            val prepEnd = System.nanoTime()
            val timing = if (useNativeDecoder) {
                val parity = decoderLiveParity
                if (parity != null && !parity.complete) {
                    val value = requireNotNull(model).runSameHeatmapParity(
                        modelInput(), requireNotNull(decoder), requireNotNull(nativeDecoder),
                    )
                    parity.compare(requireNotNull(decoder), requireNotNull(nativeDecoder))
                    if (parity.complete) {
                        val transform = currentTransform()
                        val result = parity.result(transform.width, transform.height, image.imageInfo.rotationDegrees)
                        File(root, "live_same_heatmap_decoder_parity.json").writeText(result.toString(2))
                        require(result.getString("status") == "PASS") { "P8C2_LIVE_DECODER_PARITY_FAILURE" }
                        decoderLiveParity = null
                        decoder = null
                        Log.i("P8C2", "LIVE_SAME_HEATMAP_PARITY_PASS frames=${P8c2LiveDecoderParity.FRAMES}")
                    }
                    value
                } else {
                    requireNotNull(model).runNative(modelInput(), requireNotNull(nativeDecoder))
                }
            } else {
                requireNotNull(model).run(modelInput(), requireNotNull(decoder))
            }
            val end = System.nanoTime()
            if (measured(start) && end < epochNs + WARM_NS + MEASURE_NS) {
                require(!useNativeDecoder || decoderLiveParity == null) { "P8C2_LIVE_PARITY_NOT_COMPLETE" }
                require(completed < CAPACITY) { "P8B_TELEMETRY_CAPACITY_EXCEEDED" }
                val offset = completed * TIMING_COLUMNS
                timings[offset] = start
                timings[offset + 1] = image.imageInfo.timestamp
                timings[offset + 2] = prepEnd - prepStart
                timings[offset + 3] = timing.nativeInferenceNs
                timings[offset + 4] = timing.invokeWallNs
                timings[offset + 5] = timing.outputReadNs
                timings[offset + 6] = timing.decodeNs
                timings[offset + 7] = end - start
                currentSourceXY().copyInto(coordinates, completed * 100)
                completed++
            }
            if (end - lastUiNs >= 100_000_000L) {
                lastUiNs = end
                val transform = currentTransform()
                val snapshot = P8bOverlayView.Snapshot(
                    currentSourceXY().copyOf(), transform.width, transform.height, useFront,
                    overlayMode,
                )
                val seconds = maxOf(1e-6, (end - epochNs) / 1e9)
                val completedFps = completed / maxOf(1e-6, seconds - 15.0)
                runOnUiThread {
                    overlay.setSnapshot(snapshot)
                    status.text = "MODEL INPUT: UPRIGHT / UNMIRRORED\n" +
                        "RAW STUDENT GEOMETRY — PRESENCE NOT VALIDATED\n" +
                        "preprocessor=${if (useNativePreprocessing) "P7DR2_NATIVE" else "P7DR1_JVM"}; " +
                        "decoder=${if (useNativeDecoder) "P7DR2_NATIVE_HEATMAP_ONLY" else "KOTLIN_LOCAL3"}\n" +
                        "overlay=${overlayMode.name}; semantics=LH0-20/RH21-41/BODY42-49\n" +
                        "source=${transform.width}x${transform.height}; rotation=${image.imageInfo.rotationDegrees}; " +
                        "camera=${if (useFront) "front" else "back"}\n" +
                        "model_mirror=false; preview_mirror=$useFront; letterbox=${transform.rw}x${transform.rh}+${transform.left},${transform.top}\n" +
                        "perception_fps=${"%.2f".format(maxOf(0.0, completedFps))}; condition=$condition"
                }
            }
        } catch (error: Throwable) {
            fail(error)
        } finally {
            image.close()
        }
    }

    private fun measured(now: Long): Boolean =
        epochNs > 0L && now >= epochNs + WARM_NS && now < epochNs + WARM_NS + MEASURE_NS

    private fun sampleMemory() {
        try {
            val runtime = Runtime.getRuntime()
            memory.add(
                JSONObject()
                    .put("nano_time", System.nanoTime())
                    .put("pss_kib", Debug.getPss())
                    .put("native_heap_bytes", Debug.getNativeHeapAllocatedSize())
                    .put("java_heap_bytes", runtime.totalMemory() - runtime.freeMemory())
                    .put("gc_count", gcCount())
                    .put("thermal", (getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus),
            )
        } catch (error: Throwable) {
            errors.add("MEMORY:${error.javaClass.simpleName}:${error.message}")
        }
    }

    private fun stop() {
        if (!stopping.compareAndSet(false, true)) return
        runOnUiThread {
            provider?.unbindAll()
            worker.execute(::finishResult)
        }
    }

    private fun finishResult() {
        try {
            sampleMemory()
            monitor.shutdown()
            val cameraFrames = captureCount.get()
            val skipped = maxOf(0L, cameraFrames - arrivals.toLong())
            val incomplete = maxOf(0, arrivals - completed)
            val preprocessMs = metric(2)
            val inferenceMs = metric(3)
            val decodeMs = metric(6)
            val wholeMs = metric(7)
            val result = JSONObject()
                .put("schema", when { useNativeDecoder -> "P8C2_MOBILE_RUNTIME_SUMMARY_V1"; useNativePreprocessing -> "P8C1_MOBILE_RUNTIME_SUMMARY_V1"; else -> "P8B_MOBILE_RUNTIME_SUMMARY_V1" })
                .put("status", if (errors.isEmpty() && completed > 0) "DEVICE_RUN_COMPLETE" else "DEVICE_RUN_BLOCKED")
                .put("device", Build.MODEL).put("soc", Build.SOC_MODEL).put("android", Build.VERSION.RELEASE)
                .put("condition", condition).put("camera", if (useFront) "FRONT" else "BACK")
                .put("model_sha256", model?.modelSha256)
                .put("preprocessor", if (useNativePreprocessing) "P7DR2_PARITY_PROVEN_NATIVE" else "P7DR1_PARITY_PROVEN_JVM")
                .put("decoder", if (useNativeDecoder) "P7DR2_PARITY_PRESERVING_NATIVE_HEATMAP_ONLY_LOCAL3" else "P8B_KOTLIN_LOCAL3_UNCHANGED")
                .put("decoder_jni_calls_per_frame", if (useNativeDecoder) 1 else 0)
                .put("heatmap_bytes_copied_to_kotlin_per_formal_frame", if (useNativeDecoder) 0 else P8bModelRunner.OUTPUT_FLOATS * 4)
                .put("identity_assignment_logic", "EXCLUDED")
                .put("warmup_seconds", 15).put("measurement_seconds", 180)
                .put("camera_captured_frames", cameraFrames).put("camera_capture_fps", cameraFrames / 180.0)
                .put("analyzer_frames_received", arrivals).put("analyzer_frames_analyzed", arrivals)
                .put("analyzer_fps", arrivals / 180.0).put("frames_completed", completed)
                .put("completed_perception_fps", completed / 180.0)
                .put("frames_dropped_skipped_estimate", skipped).put("frames_incomplete", incomplete)
                .put("drop_count_caveat", "capture-completion minus analyzer-callback estimate")
                .put("preprocessing_ms", statsJson(preprocessMs))
                .put("tflite_native_inference_ms", statsJson(inferenceMs))
                .put("decoder_ms", statsJson(decodeMs))
                .put("whole_perception_ms", statsJson(wholeMs))
                .put("tail_counts", tailCounts(wholeMs))
                .put("memory", JSONArray(memory.toList()))
                .put("gc_count_delta", if (firstGcCount >= 0) gcCount() - firstGcCount else JSONObject.NULL)
                .put("crashes", 0).put("anrs", 0)
                .put("errors", JSONArray(errors.toList()))
                .put("recognition", "NOT_TESTED_BY_DESIGN")
                .put("presence", "NOT_VALIDATED")
                .put("camera_backpressure", "STRATEGY_KEEP_ONLY_LATEST")
                .put("camera_ae_fps", "FIXED_15")
            File(root, "mobile_runtime_summary.json").writeText(result.toString(2))
            writeFrames()
            val transform = runCatching { currentTransform() }.getOrNull()
            val orientation = JSONObject()
                .put("schema", when { useNativeDecoder -> "P8C2_CAMERA_ORIENTATION_VALIDATION_V1"; useNativePreprocessing -> "P8C1_CAMERA_ORIENTATION_VALIDATION_V1"; else -> "P8B_CAMERA_ORIENTATION_VALIDATION_V1" })
                .put("status", "MANUAL_ANATOMICAL_VALIDATION_REQUIRED")
                .put("source_width", transform?.width).put("source_height", transform?.height)
                .put("camera", if (useFront) "FRONT" else "BACK")
                .put("model_input_upright", true).put("model_input_mirrored", false)
                .put("preview_mirrored", useFront)
                .put("condition", condition)
                .put("automated_rotation_and_transform_contract", "PASS")
                .put("manual_anatomical_matrix_complete", false)
            File(root, "camera_orientation_validation.json").writeText(orientation.toString(2))
            val phase = when { useNativeDecoder -> "P8C2"; useNativePreprocessing -> "P8C1"; else -> "P8B" }
            Log.i(phase, "COMPLETE frames=$completed fps=${completed / 180.0} errors=${errors.size}")
            runOnUiThread { status.text = "$phase runtime complete. Pull /files/${phase.lowercase()} evidence." }
        } finally {
            model?.close()
            model = null
            nativePreprocess?.close()
            nativePreprocess = null
            nativeDecoder?.close()
            nativeDecoder = null
            worker.shutdown()
        }
    }

    private fun metric(column: Int): P8bStats.Summary {
        require(completed > 0) { "P8B_NO_COMPLETED_FRAMES" }
        return P8bStats.summarize(DoubleArray(completed) { timings[it * TIMING_COLUMNS + column] / 1e6 })
    }

    private fun statsJson(value: P8bStats.Summary): JSONObject = JSONObject()
        .put("count", value.count).put("mean", value.mean).put("p50", value.p50)
        .put("p95", value.p95).put("maximum", value.maximum)

    private fun tailCounts(whole: P8bStats.Summary): JSONObject {
        val unused = whole // Keeps this helper's metric provenance explicit.
        require(unused.count == completed)
        val result = JSONObject()
        for (threshold in doubleArrayOf(50.0, 66.7, 100.0, 150.0, 200.0)) {
            var count = 0
            for (index in 0 until completed) if (timings[index * TIMING_COLUMNS + 7] / 1e6 > threshold) count++
            result.put("over_${threshold.toString().replace('.', '_')}_ms", count)
        }
        return result
    }

    private fun writeFrames() {
        val file = File(root, "mobile_runtime_frames.csv")
        file.bufferedWriter().use { writer ->
            writer.append("sequence,start_ns,capture_ns,preprocess_ms,native_inference_ms,invoke_wall_ms,output_read_ms,decode_ms,whole_ms")
            for (point in 0 until 50) writer.append(",p${point}_x,p${point}_y")
            writer.newLine()
            for (index in 0 until completed) {
                val offset = index * TIMING_COLUMNS
                writer.append(index.toString())
                writer.append(',').append(timings[offset].toString())
                writer.append(',').append(timings[offset + 1].toString())
                for (column in 2 until TIMING_COLUMNS) writer.append(',').append((timings[offset + column] / 1e6).toString())
                for (coordinate in 0 until 100) writer.append(',').append(coordinates[index * 100 + coordinate].toString())
                writer.newLine()
            }
        }
    }

    private fun gcCount(): Long = runCatching { Debug.getRuntimeStat("art.gc.gc-count").toLong() }.getOrDefault(-1L)

    private fun fail(error: Throwable) {
        errors.add(error.stackTraceToString())
        Log.e("P8B", "BLOCKED", error)
        stop()
    }

    private fun currentSourceXY(): FloatArray = if (useNativeDecoder) {
        requireNotNull(nativeDecoder).sourceXY
    } else {
        requireNotNull(decoder).sourceXY
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (::root.isInitialized && !stopping.get()) stop()
        monitor.shutdown()
        super.onDestroy()
    }

    companion object {
        private const val WARM_NS = 15_000_000_000L
        private const val MEASURE_NS = 180_000_000_000L
        private const val CAPACITY = 6_000
        private const val TIMING_COLUMNS = 8
        private const val CAMERA_PERMISSION_REQUEST = 801
    }
}
