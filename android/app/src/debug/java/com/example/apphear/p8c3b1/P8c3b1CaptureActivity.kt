package com.example.apphear.p8c3b1

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.TotalCaptureResult
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.Range
import android.util.Size
import android.view.Gravity
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
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
import com.example.apphear.p8b.P8bModelRunner
import com.example.apphear.p8b.P8bOverlayContract
import com.example.apphear.p8b.P8bOverlayView
import com.example.apphear.p8c1.P8c1NativePreprocessor
import com.example.apphear.p8c2.P8c2NativeDecoder
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

/**
 * P8-C3B1 debug-only controlled capture. It preserves the P8-C2 inference path and never
 * calls recognition, DWPose, smoothing, filtering, tracking, or presence logic.
 */
@OptIn(ExperimentalCamera2Interop::class)
class P8c3b1CaptureActivity : AppCompatActivity() {
    private data class Condition(
        val id: String,
        val label: String,
        val instruction: String,
        val durationMs: Long,
        val targetFrames: Int,
        val personVisible: Boolean,
        val leftVisible: Boolean,
        val rightVisible: Boolean,
        val operatorNote: String = "",
    )

    private data class Truth(
        val personVisible: Boolean,
        val leftVisible: Boolean,
        val rightVisible: Boolean,
        val handsCrossed: Boolean,
        val movement: String,
        val note: String,
    )

    private data class PendingFrame(
        val analyzerSequenceId: Long,
        val retainedSequenceId: Int,
        val sensorTimestampNs: Long,
        val monotonicTimestampNs: Long,
        val wallClockUtc: String,
        val condition: Condition,
        val conditionElapsedMs: Long,
        val truth: Truth,
        val cameraWidth: Int,
        val cameraHeight: Int,
        val rowStride: Int,
        val pixelStride: Int,
        val rotationDegrees: Int,
        val sourceWidth: Int,
        val sourceHeight: Int,
        val resizedWidth: Int,
        val resizedHeight: Int,
        val letterboxLeft: Int,
        val letterboxTop: Int,
        val rgba: ByteArray,
        val inputXY: FloatArray,
        val sourceXY: FloatArray,
        val peakCells: IntArray,
        val peakMaxLogits: FloatArray,
    )

    private val conditions = listOf(
        Condition("C0_EMPTY_FRAME_NO_PERSON", "EMPTY FRAME / NO PERSON", "Leave the camera view completely. Keep the background still.", 5_000, 20, false, false, false),
        Condition("C1_PERSON_HANDS_DOWN", "PERSON PRESENT / HANDS DOWN", "Torso and head visible. Keep both hands outside the frame/signing region.", 5_000, 20, true, false, false),
        Condition("C2_LEFT_HAND_ONLY", "ANATOMICAL LEFT HAND ONLY", "RIGHT hand fully out of frame. Hold LEFT still 3 s, then move it slowly 3 s.", 6_000, 30, true, true, false),
        Condition("C3_RIGHT_HAND_ONLY", "ANATOMICAL RIGHT HAND ONLY", "LEFT hand fully out of frame. Hold RIGHT still 3 s, then move it slowly 3 s.", 6_000, 30, true, false, true),
        Condition("C4_BOTH_WIDELY_SEPARATED", "BOTH HANDS WIDELY SEPARATED", "Hold both separated and still 3 s, then move both slowly and symmetrically 3 s.", 6_000, 30, true, true, true),
        Condition("C5_BOTH_HANDS_CROSSING", "BOTH HANDS CROSS ONCE", "Start separated, approach, cross once, hold briefly, uncross, then separate.", 8_000, 50, true, true, true),
        Condition("C6L_HAND_NEAR_FACE_LEFT", "LEFT HAND NEAR FACE", "Only anatomical LEFT hand visible near the face. Hold still.", 5_000, 25, true, true, false),
        Condition("C6R_HAND_NEAR_FACE_RIGHT", "RIGHT HAND NEAR FACE", "Only anatomical RIGHT hand visible near the face. Hold still.", 5_000, 25, true, false, true),
        Condition("C7L_HAND_NEAR_TORSO_LEFT", "LEFT HAND NEAR TORSO", "Only anatomical LEFT hand visible near the torso. Hold still.", 5_000, 25, true, true, false),
        Condition("C7R_HAND_NEAR_TORSO_RIGHT", "RIGHT HAND NEAR TORSO", "Only anatomical RIGHT hand visible near the torso. Hold still.", 5_000, 25, true, false, true),
        Condition("C8_FINGER_ARTICULATION", "FINGER POSE: OPEN PALMS", "Arrange both hands as OPEN PALMS, then press START and hold still.", 2_000, 10, true, true, true, "open_palm"),
        Condition("C8_FINGER_ARTICULATION", "FINGER POSE: CLOSED FISTS", "Arrange both hands as CLOSED FISTS, then press START and hold still.", 2_000, 10, true, true, true, "closed_fist"),
        Condition("C8_FINGER_ARTICULATION", "FINGER POSE: INDEX EXTENDED", "Extend only each INDEX finger, then press START and hold still.", 2_000, 10, true, true, true, "index_extended"),
        Condition("C8_FINGER_ARTICULATION", "FINGER POSE: TWO FINGERS", "Extend two fingers on each hand, then press START and hold still.", 2_000, 10, true, true, true, "two_fingers_extended"),
    )

    private val analyzer = Executors.newSingleThreadExecutor()
    private val writer = Executors.newSingleThreadExecutor()
    private val finalizer = Executors.newSingleThreadExecutor()
    private val writerSlots = Semaphore(16)
    private val handler = Handler(Looper.getMainLooper())
    private val stopping = AtomicBoolean(false)
    private val analyzerSequence = AtomicLong(0)
    private val retainedSequence = AtomicInteger(0)
    private val writtenFrames = AtomicInteger(0)
    private val writeErrors = mutableListOf<String>()
    private val stateLock = Any()
    private var captureStartStep = 0
    private var captureEndStep = 0
    private var sessionTargetFrames = TARGET_TOTAL
    private var conditionIndex = 0
    private var conditionActive = false
    private var conditionStartNs = 0L
    private var conditionRetained = 0
    private var provider: ProcessCameraProvider? = null
    private var model: P8bModelRunner? = null
    private var preprocessor: P8c1NativePreprocessor? = null
    private var decoder: P8c2NativeDecoder? = null
    private lateinit var sessionRoot: File
    private lateinit var framesRoot: File
    private lateinit var preview: PreviewView
    private lateinit var overlay: P8bOverlayView
    private lateinit var status: TextView
    private lateinit var instruction: TextView
    private lateinit var action: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        if (!intent.getBooleanExtra(EXTRA_ENABLED, false)) {
            status.text = "P8-C3B1 disabled — explicit ADB opt-in required"
            action.isEnabled = false
            return
        }
        captureStartStep = intent.getIntExtra(EXTRA_START_STEP, 0).coerceIn(0, conditions.lastIndex)
        captureEndStep = intent.getIntExtra(EXTRA_END_STEP_EXCLUSIVE, conditions.size)
            .coerceIn(captureStartStep + 1, conditions.size)
        conditionIndex = captureStartStep
        sessionTargetFrames = conditions.subList(captureStartStep, captureEndStep).sumOf { it.targetFrames }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val base = File(requireNotNull(getExternalFilesDir(null)), "p8c3b1")
        val sessionName = "session_${utcCompact()}"
        sessionRoot = File(base, sessionName).also { require(it.mkdirs()) { "P8C3B1_SESSION_CREATE_FAILED" } }
        framesRoot = File(sessionRoot, "frames").also { require(it.mkdirs()) { "P8C3B1_FRAMES_CREATE_FAILED" } }
        File(base, "latest_session.txt").writeText(sessionName)
        File(sessionRoot, "session_identity.json").writeText(
            JSONObject()
                .put("schema", "P8C3B1_DEVICE_SESSION_IDENTITY_V1")
                .put("phase_id", "P8C3B1_CONTROLLED_LIVE_STUDENT_GEOMETRY_CAPTURE_01")
                .put("session", sessionName)
                .put("created_utc", utcNow())
                .put("model_sha256", P8bModelRunner.MODEL_SHA256)
                .put("preprocessor", "P7DR2_PARITY_PROVEN_NATIVE_PREPROCESSOR")
                .put("decoder", "P8C2_NATIVE_HEATMAP_ONLY_LOCAL3_DECODER")
                .put("model_input_mirrored", false)
                .put("preview_mirrored", true)
                .put("recognition_connected", false)
                .put("teacher_run", false)
                .put("capture_start_step", captureStartStep)
                .put("capture_end_step_exclusive", captureEndStep)
                .put("session_target_frames", sessionTargetFrames)
                .toString(2),
        )
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_PERMISSION_REQUEST)
        } else {
            startRuntime()
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_PERMISSION_REQUEST && grantResults.singleOrNull() == PackageManager.PERMISSION_GRANTED) {
            startRuntime()
        } else if (requestCode == CAMERA_PERMISSION_REQUEST) {
            fail(IllegalStateException("P8C3B1_CAMERA_PERMISSION_DENIED"))
        }
    }

    private fun buildUi() {
        preview = PreviewView(this).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        overlay = P8bOverlayView(this)
        status = TextView(this).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(0x99000000.toInt())
            textSize = 12f
            setPadding(16, 12, 16, 12)
            text = "P8-C3B1 initializing"
        }
        instruction = TextView(this).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(0xBB102030.toInt())
            textSize = 17f
            setPadding(20, 18, 20, 18)
        }
        action = Button(this).apply {
            text = "WAITING FOR CAMERA"
            isEnabled = false
            setOnClickListener { startCurrentCondition() }
        }
        val controls = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(12, 12, 12, 20)
            addView(instruction, LinearLayout.LayoutParams(-1, -2))
            addView(action, LinearLayout.LayoutParams(-1, -2))
        }
        val root = FrameLayout(this)
        root.addView(preview, FrameLayout.LayoutParams(-1, -1))
        root.addView(overlay, FrameLayout.LayoutParams(-1, -1))
        root.addView(status, FrameLayout.LayoutParams(-1, -2).apply { gravity = Gravity.TOP })
        root.addView(controls, FrameLayout.LayoutParams(-1, -2).apply { gravity = Gravity.BOTTOM })
        setContentView(root)
        renderConditionUi()
    }

    private fun startRuntime() {
        analyzer.execute {
            try {
                model = P8bModelRunner(this)
                runOnUiThread { bindCamera() }
            } catch (error: Throwable) {
                fail(error)
            }
        }
    }

    private fun bindCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                provider = future.get()
                val previewUseCase = Preview.Builder().build().also { it.setSurfaceProvider(preview.surfaceProvider) }
                val builder = ImageAnalysis.Builder()
                    .setTargetResolution(Size(480, 360))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                Camera2Interop.Extender(builder)
                    .setCaptureRequestOption(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(15, 15))
                    .setSessionCaptureCallback(object : CameraCaptureSession.CaptureCallback() {
                        override fun onCaptureCompleted(session: CameraCaptureSession, request: CaptureRequest, result: TotalCaptureResult) = Unit
                    })
                val analysis = builder.build().also { it.setAnalyzer(analyzer, ::analyze) }
                provider!!.unbindAll()
                provider!!.bindToLifecycle(this, CameraSelector.DEFAULT_FRONT_CAMERA, previewUseCase, analysis)
                status.text = "MODEL INPUT: UPRIGHT / UNMIRRORED\nRAW STUDENT GEOMETRY — PRESENCE NOT VALIDATED\nP8-C2 stack ready; recognition disconnected"
                action.isEnabled = true
                action.text = "START / CONFIRM THIS CONDITION"
                renderConditionUi()
            } catch (error: Throwable) {
                fail(error)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun startCurrentCondition() {
        synchronized(stateLock) {
            if (conditionActive || stopping.get() || conditionIndex >= conditions.size) return
            conditionActive = true
            conditionStartNs = System.nanoTime() + OPERATOR_COUNTDOWN_NS
            conditionRetained = 0
            action.isEnabled = false
        }
        renderConditionUi()
    }

    private fun configure(image: ImageProxy) {
        val plane = image.planes[0]
        val old = preprocessor
        if (old != null && old.width == image.width && old.height == image.height &&
            old.rowStride == plane.rowStride && old.pixelStride == plane.pixelStride &&
            old.rotation == image.imageInfo.rotationDegrees
        ) return
        old?.close()
        decoder?.close()
        preprocessor = P8c1NativePreprocessor(
            image.width, image.height, plane.rowStride, plane.pixelStride, image.imageInfo.rotationDegrees,
        )
        decoder = P8c2NativeDecoder(requireNotNull(preprocessor).transform)
    }

    private fun analyze(image: ImageProxy) {
        if (stopping.get()) {
            image.close()
            return
        }
        val sequence = analyzerSequence.incrementAndGet()
        try {
            configure(image)
            val pre = requireNotNull(preprocessor)
            val nativeDecoder = requireNotNull(decoder)
            val source = image.planes[0].buffer.duplicate()
            pre.run(source.duplicate())
            requireNotNull(model).runNative(pre.input, nativeDecoder)

            val nowNs = System.nanoTime()
            val snapshot = P8bOverlayView.Snapshot(
                nativeDecoder.sourceXY.copyOf(), pre.transform.width, pre.transform.height, true,
                P8bOverlayContract.RenderMode.POINTS_ONLY,
            )
            runOnUiThread { overlay.setSnapshot(snapshot) }

            val state = synchronized(stateLock) {
                val condition = conditions.getOrNull(conditionIndex)
                if (!conditionActive || condition == null) null else {
                    val elapsedMs = (nowNs - conditionStartNs) / 1_000_000L
                    val scheduledMs = conditionRetained.toDouble() * condition.durationMs / condition.targetFrames
                    if (elapsedMs >= 0L && elapsedMs + 1e-6 >= scheduledMs &&
                        conditionRetained < condition.targetFrames && writerSlots.tryAcquire()
                    ) {
                        conditionRetained++
                        Triple(condition, elapsedMs, conditionRetained)
                    } else null
                }
            }
            if (state != null) {
                val (condition, elapsedMs, _) = state
                val retained = retainedSequence.incrementAndGet()
                val plane = image.planes[0]
                val bytes = copyPlane(source)
                val peaks = nativeDecoder.peaks.copyOf()
                val logits = peakLogits(requireNotNull(model).directOutputBuffer(), peaks)
                val pending = PendingFrame(
                    sequence, retained, image.imageInfo.timestamp, nowNs, utcNow(), condition, elapsedMs,
                    truthFor(condition, elapsedMs), image.width, image.height, plane.rowStride,
                    plane.pixelStride, image.imageInfo.rotationDegrees, pre.transform.width,
                    pre.transform.height, pre.transform.rw, pre.transform.rh, pre.transform.left,
                    pre.transform.top, bytes, nativeDecoder.inputXY.copyOf(), nativeDecoder.sourceXY.copyOf(),
                    peaks, logits,
                )
                writer.execute {
                    try {
                        writeFrame(pending)
                        writtenFrames.incrementAndGet()
                    } catch (error: Throwable) {
                        synchronized(writeErrors) { writeErrors.add("${pending.analyzerSequenceId}:${error.stackTraceToString()}") }
                    } finally {
                        writerSlots.release()
                    }
                }
            }
            updateAndAdvance(nowNs)
        } catch (error: Throwable) {
            fail(error)
        } finally {
            image.close()
        }
    }

    private fun updateAndAdvance(nowNs: Long) {
        var completedCondition: Condition? = null
        var allComplete = false
        synchronized(stateLock) {
            val condition = conditions.getOrNull(conditionIndex)
            if (conditionActive && condition != null) {
                val elapsedMs = (nowNs - conditionStartNs) / 1_000_000L
                if (elapsedMs >= condition.durationMs && conditionRetained >= condition.targetFrames) {
                    conditionActive = false
                    completedCondition = condition
                    conditionIndex++
                    allComplete = conditionIndex >= captureEndStep
                }
            }
        }
        runOnUiThread { renderConditionUi() }
        if (completedCondition != null) Log.i(TAG, "CONDITION_COMPLETE ${completedCondition!!.id}")
        if (allComplete) finishCapture()
    }

    private fun renderConditionUi() {
        val snapshot = synchronized(stateLock) {
            val current = if (conditionIndex < captureEndStep) conditions.getOrNull(conditionIndex) else null
            val elapsed = if (conditionActive) (System.nanoTime() - conditionStartNs) / 1_000_000L else 0L
            arrayOf(current, conditionActive, elapsed, conditionRetained)
        }
        val current = snapshot[0] as Condition?
        val active = snapshot[1] as Boolean
        val elapsed = snapshot[2] as Long
        val retained = snapshot[3] as Int
        if (current == null) {
            instruction.text = "SELECTED CAPTURE STEPS COMPLETE\nWriting and sealing synchronized evidence…"
            action.text = "CAPTURE COMPLETE"
            action.isEnabled = false
            return
        }
        val progress = conditionIndex - captureStartStep + 1
        val total = captureEndStep - captureStartStep
        val phase = if (!active) {
            "READY — confirm pose, then press START"
        } else if (elapsed < 0L) {
            "GET READY · capture begins in ${"%.1f".format(-elapsed / 1000.0)} s"
        } else {
            "ACTIVE"
        }
        instruction.text = "$progress/$total: ${current.label}\n${current.instruction}\n" +
            "$phase · ${maxOf(0L, elapsed) / 1000.0}s · $retained/${current.targetFrames} frames"
        action.text = if (active) "CAPTURING ${current.id}" else "START / CONFIRM ${current.label}"
        action.isEnabled = !active && model != null && provider != null && !stopping.get()
    }

    private fun finishCapture() {
        if (!stopping.compareAndSet(false, true)) return
        runOnUiThread { provider?.unbindAll() }
        writer.shutdown()
        finalizer.execute {
            val writerFinished = writer.awaitTermination(5, TimeUnit.MINUTES)
            val errors = synchronized(writeErrors) { writeErrors.toList() }
            val selectedConditions = conditions.subList(captureStartStep, captureEndStep)
            val complete = JSONObject()
                .put("schema", "P8C3B1_DEVICE_CAPTURE_COMPLETE_V1")
                .put("status", if (writerFinished && errors.isEmpty() && writtenFrames.get() == sessionTargetFrames) "PASS" else "FAIL")
                .put("session", sessionRoot.name)
                .put("analyzer_frames_seen", analyzerSequence.get())
                .put("frames_enqueued", retainedSequence.get())
                .put("frames_written", writtenFrames.get())
                .put("target_frames", sessionTargetFrames)
                .put("operator_confirmed_steps_completed", selectedConditions.size)
                .put("logical_conditions_completed", selectedConditions.map { it.id }.distinct().size)
                .put("writer_finished", writerFinished)
                .put("write_errors", JSONArray(errors))
                .put("completed_utc", utcNow())
                .put("model_sha256", requireNotNull(model).modelSha256)
                .put("model_input_mirrored", false)
                .put("preview_mirrored", true)
                .put("teacher_run", false)
                .put("recognition_run", false)
            File(sessionRoot, "capture_complete.json").writeText(complete.toString(2))
            runOnUiThread {
                status.text = "P8-C3B1 DEVICE CAPTURE ${complete.getString("status")}\nframes=${writtenFrames.get()}/$sessionTargetFrames\n${sessionRoot.absolutePath}"
                instruction.text = "Capture sealed. Leave this screen open until evidence is pulled."
            }
            Log.i(TAG, "CAPTURE_COMPLETE ${complete}")
        }
    }

    private fun writeFrame(frame: PendingFrame) {
        val imageName = "frame_${frame.retainedSequenceId.toString().padStart(4, '0')}_${frame.condition.id}.png"
        val imageFile = File(framesRoot, imageName)
        writeUprightPng(frame, imageFile)
        val imageSha = sha256(imageFile)
        val record = JSONObject()
            .put("schema", "P8C3B1_STUDENT_LIVE_FRAME_V1")
            .put("analyzer_sequence_id", frame.analyzerSequenceId)
            .put("retained_sequence_id", frame.retainedSequenceId)
            .put("sensor_timestamp_ns", frame.sensorTimestampNs)
            .put("monotonic_timestamp_ns", frame.monotonicTimestampNs)
            .put("wall_clock_utc", frame.wallClockUtc)
            .put("condition_id", frame.condition.id)
            .put("condition_label", frame.condition.label)
            .put("condition_elapsed_ms", frame.conditionElapsedMs)
            .put("image_filename", "frames/$imageName")
            .put("image_sha256", imageSha)
            .put("image_semantics", "UPRIGHT_UNMIRRORED_SOURCE_RGB")
            .put("source_width", frame.sourceWidth)
            .put("source_height", frame.sourceHeight)
            .put("camera_width", frame.cameraWidth)
            .put("camera_height", frame.cameraHeight)
            .put("row_stride", frame.rowStride)
            .put("pixel_stride", frame.pixelStride)
            .put("rotation_degrees", frame.rotationDegrees)
            .put("model_mirrored", false)
            .put("preview_mirrored", true)
            .put("letterbox", JSONObject().put("resized_width", frame.resizedWidth).put("resized_height", frame.resizedHeight).put("left", frame.letterboxLeft).put("top", frame.letterboxTop))
            .put("source_xy_50", floatArrayJson(frame.sourceXY))
            .put("model_384_xy_50", floatArrayJson(frame.inputXY))
            .put("peak_cell_xy_50", peakJson(frame.peakCells))
            .put("peak_max_logits_50", floatArrayJson(frame.peakMaxLogits))
            .put("max_logit_semantics", "RAW_UNCALIBRATED_ADMISSIBLE_PEAK_LOGIT")
            .put("physical_left_visible", frame.truth.leftVisible)
            .put("physical_right_visible", frame.truth.rightVisible)
            .put("person_visible", frame.truth.personVisible)
            .put("hands_crossed", frame.truth.handsCrossed)
            .put("movement", frame.truth.movement)
            .put("operator_note", frame.truth.note)
        appendLine(File(sessionRoot, "student_live_frames.jsonl"), record.toString())
        val csv = listOf(
            frame.retainedSequenceId, frame.analyzerSequenceId, frame.sensorTimestampNs, frame.condition.id,
            frame.conditionElapsedMs, "frames/$imageName", imageSha, frame.sourceWidth, frame.sourceHeight,
            frame.rotationDegrees, false, true, frame.truth.personVisible, frame.truth.leftVisible,
            frame.truth.rightVisible, frame.truth.handsCrossed, frame.truth.movement, frame.truth.note,
        ).joinToString(",") { csv(it.toString()) }
        val manifest = File(sessionRoot, "capture_manifest.csv")
        synchronized(MANIFEST_LOCK) {
            if (!manifest.exists()) manifest.writeText(MANIFEST_HEADER + "\n")
            manifest.appendText(csv + "\n")
        }
    }

    private fun writeUprightPng(frame: PendingFrame, target: File) {
        val pixels = IntArray(frame.sourceWidth * frame.sourceHeight)
        for (y in 0 until frame.sourceHeight) for (x in 0 until frame.sourceWidth) {
            val sx: Int
            val sy: Int
            when (frame.rotationDegrees) {
                90 -> { sx = y; sy = frame.cameraHeight - 1 - x }
                180 -> { sx = frame.cameraWidth - 1 - x; sy = frame.cameraHeight - 1 - y }
                270 -> { sx = frame.cameraWidth - 1 - y; sy = x }
                else -> { sx = x; sy = y }
            }
            val offset = sy * frame.rowStride + sx * frame.pixelStride
            val r = frame.rgba[offset].toInt() and 255
            val g = frame.rgba[offset + 1].toInt() and 255
            val b = frame.rgba[offset + 2].toInt() and 255
            pixels[y * frame.sourceWidth + x] = Color.rgb(r, g, b)
        }
        val bitmap = Bitmap.createBitmap(pixels, frame.sourceWidth, frame.sourceHeight, Bitmap.Config.ARGB_8888)
        val temporary = File(target.parentFile, target.name + ".tmp")
        temporary.outputStream().buffered().use { output ->
            require(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) { "P8C3B1_PNG_COMPRESS_FAILED" }
        }
        bitmap.recycle()
        require(temporary.renameTo(target)) { "P8C3B1_PNG_COMMIT_FAILED" }
    }

    private fun copyPlane(source: ByteBuffer): ByteArray {
        val copy = source.duplicate()
        val bytes = ByteArray(copy.remaining())
        copy.get(bytes)
        return bytes
    }

    private fun peakLogits(output: ByteBuffer, peaks: IntArray): FloatArray {
        val values = output.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer()
        return FloatArray(50) { channel -> values.get(peaks[channel] * 50 + channel) }
    }

    private fun truthFor(condition: Condition, elapsedMs: Long): Truth {
        val conditionId = condition.id
        val seconds = elapsedMs / 1000.0
        var movement = "stationary"
        var crossed = false
        var note = ""
        when (conditionId) {
            "C2_LEFT_HAND_ONLY", "C3_RIGHT_HAND_ONLY" -> movement = if (seconds < 3.0) "stationary" else "slow"
            "C4_BOTH_WIDELY_SEPARATED" -> movement = if (seconds < 3.0) "stationary" else "slow_symmetric"
            "C5_BOTH_HANDS_CROSSING" -> {
                movement = "crossing"
                crossed = seconds in 3.2..4.8
                note = when {
                    seconds < 1.5 -> "separated_start"
                    seconds < 3.2 -> "moving_toward_center"
                    seconds <= 4.8 -> "crossed_hold"
                    seconds < 6.5 -> "uncrossing"
                    else -> "separated_return"
                }
            }
            "C8_FINGER_ARTICULATION" -> note = condition.operatorNote
        }
        return Truth(condition.personVisible, condition.leftVisible, condition.rightVisible, crossed, movement, note)
    }

    private fun appendLine(file: File, line: String) = synchronized(JSONL_LOCK) { file.appendText(line + "\n") }
    private fun floatArrayJson(values: FloatArray) = JSONArray().also { out -> values.forEach { out.put(it.toDouble()) } }
    private fun peakJson(peaks: IntArray) = JSONArray().also { out -> peaks.forEach { out.put(JSONArray().put(it % 96).put(it / 96)) } }
    private fun csv(value: String) = "\"${value.replace("\"", "\"\"")}\""

    private fun fail(error: Throwable) {
        Log.e(TAG, "P8C3B1 failure", error)
        stopping.set(true)
        runOnUiThread {
            action.isEnabled = false
            status.text = "P8C3B1 FAILURE\n${error.javaClass.simpleName}: ${error.message}"
        }
        if (::sessionRoot.isInitialized) File(sessionRoot, "capture_failure.txt").writeText(error.stackTraceToString())
    }

    override fun onDestroy() {
        stopping.set(true)
        provider?.unbindAll()
        analyzer.shutdown()
        if (!writer.isShutdown) writer.shutdown()
        finalizer.shutdown()
        decoder?.close()
        preprocessor?.close()
        model?.close()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_ENABLED = "p8c3b1_enabled"
        const val EXTRA_START_STEP = "p8c3b1_start_step"
        const val EXTRA_END_STEP_EXCLUSIVE = "p8c3b1_end_step_exclusive"
        const val TARGET_TOTAL = 320
        private const val OPERATOR_COUNTDOWN_NS = 3_000_000_000L
        private const val CAMERA_PERMISSION_REQUEST = 8301
        private const val TAG = "P8C3B1"
        private val JSONL_LOCK = Any()
        private val MANIFEST_LOCK = Any()
        private const val MANIFEST_HEADER = "retained_sequence_id,analyzer_sequence_id,sensor_timestamp_ns,condition_id,condition_elapsed_ms,image_filename,image_sha256,source_width,source_height,rotation_degrees,model_mirrored,preview_mirrored,person_visible,physical_left_visible,physical_right_visible,hands_crossed,movement,operator_note"

        private fun utcNow(): String = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(Date())

        private fun utcCompact(): String = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(Date())

        private fun sha256(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            FileInputStream(file).use { input ->
                val block = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(block)
                    if (count < 0) break
                    digest.update(block, 0, count)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
