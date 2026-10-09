package com.example.apphear.perceptionvnext

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.TotalCaptureResult
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
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
import com.example.apphear.BuildConfig
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/**
 * PERCEPTION_VNEXT_PHONE_01: debug-only live candidate and governed-condition capture.
 * No code in this activity can invoke recognition, S5, S7, sentence generation, or UI output.
 */
@OptIn(ExperimentalCamera2Interop::class)
class PerceptionVNextActivity : AppCompatActivity() {
    private data class Condition(
        val id: String,
        val label: String,
        val instruction: String,
        val durationMs: Long,
        val targetFrames: Int,
        val personVisible: Boolean,
        val leftVisible: Boolean,
        val rightVisible: Boolean,
        val note: String = "",
        val crossed: Boolean = false,
    )

    private data class FrameMetric(
        val conditionId: String,
        val note: String,
        val personVisible: Boolean,
        val physicalLeftVisible: Boolean,
        val physicalRightVisible: Boolean,
        val crossed: Boolean,
        val bodyAvailable: Boolean,
        val leftObserved: Boolean,
        val rightObserved: Boolean,
        val leftPresence: Float?,
        val rightPresence: Float?,
        val leftXY: FloatArray,
        val leftValid: BooleanArray,
        val rightXY: FloatArray,
        val rightValid: BooleanArray,
        val leftRoi: PerceptionVNextMath.HandRoi?,
        val rightRoi: PerceptionVNextMath.HandRoi?,
        val bodyXY: FloatArray,
        val bodySupport: FloatArray,
        val bodyValid: BooleanArray,
        val preprocessMs: Double,
        val dwposeMs: Double,
        val decodeMs: Double,
        val cropMs: Double,
        val leftRefinerMs: Double?,
        val rightRefinerMs: Double?,
        val totalMs: Double,
        val sensorTimestampNs: Long,
        val thermalStatus: Int,
        val pssKb: Long,
    )

    private data class HandStage(
        val overlay: PerceptionVNextOverlayView.Hand,
        val cropMs: Double,
        val refinerMs: Double?,
    )

    private val conditions = listOf(
        Condition("C0_EMPTY_FRAME_NO_PERSON", "NO PERSON / NO HANDS", "Leave the camera view completely; keep the background still.", 5_000, 20, false, false, false),
        Condition("C1_PERSON_HANDS_DOWN", "PERSON / HANDS DOWN", "Head and torso visible; keep both hands outside the signing region.", 5_000, 20, true, false, false),
        Condition("C2_LEFT_HAND_ONLY", "ANATOMICAL LEFT ONLY", "Keep RIGHT out of frame. Hold LEFT, then move it slowly.", 6_000, 30, true, true, false),
        Condition("C3_RIGHT_HAND_ONLY", "ANATOMICAL RIGHT ONLY", "Keep LEFT out of frame. Hold RIGHT, then move it slowly.", 6_000, 30, true, false, true),
        Condition("C4_BOTH_WIDELY_SEPARATED", "BOTH SEPARATED", "Hold both separated, then move both slowly.", 6_000, 30, true, true, true),
        Condition("C5_BOTH_HANDS_CROSSING", "CROSSING / CONTACT", "Start separated, cross/contact once, hold, uncross, separate.", 8_000, 50, true, true, true, crossed = true),
        Condition("C6L_HAND_NEAR_FACE_LEFT", "LEFT NEAR FACE", "Only anatomical LEFT visible near the face.", 5_000, 25, true, true, false),
        Condition("C6R_HAND_NEAR_FACE_RIGHT", "RIGHT NEAR FACE", "Only anatomical RIGHT visible near the face.", 5_000, 25, true, false, true),
        Condition("C7L_HAND_NEAR_TORSO_LEFT", "LEFT NEAR TORSO", "Only anatomical LEFT visible near the torso.", 5_000, 25, true, true, false),
        Condition("C7R_HAND_NEAR_TORSO_RIGHT", "RIGHT NEAR TORSO", "Only anatomical RIGHT visible near the torso.", 5_000, 25, true, false, true),
        Condition("C8_FINGER_ARTICULATION", "OPEN PALMS", "Show open palms and hold.", 2_000, 10, true, true, true, "open_palm"),
        Condition("C8_FINGER_ARTICULATION", "CLOSED FISTS", "Show closed fists and hold.", 2_000, 10, true, true, true, "closed_fist"),
        Condition("C8_FINGER_ARTICULATION", "INDEX EXTENDED", "Extend only each index finger and hold.", 2_000, 10, true, true, true, "index_extended"),
        Condition("C8_FINGER_ARTICULATION", "TWO FINGERS", "Extend two fingers on each hand and hold.", 2_000, 10, true, true, true, "two_fingers_extended"),
    )

    private val analyzer = Executors.newSingleThreadExecutor()
    private val running = AtomicBoolean(false)
    private val cameraFrames = AtomicLong(0)
    private val analyzedFrames = AtomicLong(0)
    private val stateLock = Any()
    private var provider: ProcessCameraProvider? = null
    private var dwpose: DWPoseTRunner? = null
    private var refiner: HandRefinerRunner? = null
    private var preprocessor: PerceptionVNextNativePreprocessor? = null
    private val nativeParity = PerceptionVNextNativeParity()
    private var conditionIndex = 0
    private var conditionActive = false
    private var conditionStartNs = 0L
    private var conditionFrames = 0
    private var firstAnalyzedNs = 0L
    private var lastAnalyzedNs = 0L
    private val measurements = mutableListOf<FrameMetric>()
    private val rolling = ArrayDeque<FrameMetric>()
    private lateinit var sessionRoot: File
    private lateinit var preview: PreviewView
    private lateinit var overlay: PerceptionVNextOverlayView
    private lateinit var status: TextView
    private lateinit var instruction: TextView
    private lateinit var action: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        if (!BuildConfig.PERCEPTION_VNEXT_ENABLED || !intent.getBooleanExtra(EXTRA_ENABLED, false)) {
            status.text = "PERCEPTION VNEXT DISABLED\nUse debug build flag + explicit ADB opt-in"
            action.isEnabled = false
            return
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val base = File(requireNotNull(getExternalFilesDir(null)), "perception_vnext_phone_01")
        sessionRoot = File(base, "session_${utcCompact()}").also {
            require(it.mkdirs()) { "VNEXT_SESSION_CREATE_FAILED" }
        }
        File(base, "latest_session.txt").writeText(sessionRoot.name)
        writeIdentity()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_REQUEST)
        } else {
            startRuntime()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_REQUEST && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            startRuntime()
        } else if (requestCode == CAMERA_REQUEST) {
            fail("VNEXT_CAMERA_PERMISSION_DENIED")
        }
    }

    private fun buildUi() {
        preview = PreviewView(this).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        overlay = PerceptionVNextOverlayView(this)
        status = TextView(this).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(0xA0000000.toInt())
            textSize = 12f
            setPadding(16, 12, 16, 12)
            text = "PERCEPTION VNEXT loading"
        }
        instruction = TextView(this).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(0xC0102030.toInt())
            textSize = 17f
            setPadding(20, 18, 20, 18)
        }
        action = Button(this).apply {
            isEnabled = false
            text = "WAITING FOR MODELS"
            setOnClickListener { startCondition() }
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
        renderCondition()
    }

    private fun startRuntime() {
        if (!running.compareAndSet(false, true)) return
        analyzer.execute {
            try {
                dwpose = DWPoseTRunner(this)
                refiner = HandRefinerRunner(this)
                runOnUiThread { bindCamera() }
            } catch (error: Throwable) {
                fail(error.stackTraceToString())
            }
        }
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
                    .setCaptureRequestOption(
                        CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE,
                        Range(15, 15),
                    )
                    .setSessionCaptureCallback(
                        object : CameraCaptureSession.CaptureCallback() {
                            override fun onCaptureCompleted(
                                session: CameraCaptureSession,
                                request: CaptureRequest,
                                result: TotalCaptureResult,
                            ) {
                                cameraFrames.incrementAndGet()
                            }
                        },
                    )
                val analysis = builder.build().also { it.setAnalyzer(analyzer, ::analyze) }
                provider!!.unbindAll()
                provider!!.bindToLifecycle(
                    this,
                    CameraSelector.DEFAULT_FRONT_CAMERA,
                    previewUseCase,
                    analysis,
                )
                status.text = "VNEXT READY — LIVE CURRENT-FRAME OBSERVATIONS\nRecognition/S5/S7/UI disconnected"
                action.isEnabled = true
                action.text = "START THIS CONDITION"
            } catch (error: Throwable) {
                fail(error.stackTraceToString())
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun startCondition() {
        synchronized(stateLock) {
            if (conditionActive || conditionIndex >= conditions.size) return
            conditionActive = true
            conditionFrames = 0
            conditionStartNs = System.nanoTime() + 2_000_000_000L
            action.isEnabled = false
        }
        renderCondition()
    }

    private fun analyze(image: ImageProxy) {
        val frameStarted = System.nanoTime()
        try {
            val preprocessStarted = System.nanoTime()
            val prepared = preprocessor?.takeIf { it.compatible(image) }
                ?: PerceptionVNextNativePreprocessor(image).also { preprocessor = it }
            prepared.preprocess(image)
            val preprocessMs = (System.nanoTime() - preprocessStarted) / 1_000_000.0
            if (!nativeParity.complete) {
                val reference = PerceptionVNextPreprocessor(image)
                val parityRoi = PerceptionVNextMath.HandRoi(
                    prepared.transform.centerX,
                    prepared.transform.centerY,
                    minOf(prepared.transform.sourceWidth, prepared.transform.sourceHeight) * 0.30f,
                    prepared.transform.sourceWidth,
                    prepared.transform.sourceHeight,
                    21,
                )
                val nativeCrop = prepared.crop(parityRoi)
                nativeParity.compare(
                    reference.dwposeInput(),
                    prepared.poseInput,
                    reference.handInput(parityRoi),
                    nativeCrop,
                )
                if (nativeParity.complete) {
                    val parity = nativeParity.result()
                    File(sessionRoot, "native_live_parity.json").writeText(parity.toString(2))
                    require(parity.getString("status") == "PASS") {
                        "VNEXT_NATIVE_LIVE_PARITY_FAILED"
                    }
                }
            }
            val pose = requireNotNull(dwpose).run(prepared.poseInput, prepared.transform)
            val left = runHand(prepared, pose.decoded, PerceptionVNextMath.LEFT_HAND_START)
            val right = runHand(prepared, pose.decoded, PerceptionVNextMath.RIGHT_HAND_START)
            val bodyXY = FloatArray(PerceptionVNextMath.BODY_POINTS * 2)
            val bodySupport = FloatArray(PerceptionVNextMath.BODY_POINTS)
            val bodyValid = BooleanArray(PerceptionVNextMath.BODY_POINTS)
            var bodySupported = 0
            for ((local, point) in PerceptionVNextMath.bodyIndices.withIndex()) {
                val x = pose.decoded.xy[point * 2]
                val y = pose.decoded.xy[point * 2 + 1]
                bodyXY[local * 2] = x
                bodyXY[local * 2 + 1] = y
                bodySupport[local] = pose.decoded.support[point]
                bodyValid[local] = PerceptionVNextMath.bodyPointValid(
                    x,
                    y,
                    bodySupport[local],
                    prepared.transform,
                )
                if (bodyValid[local]) {
                    bodySupported++
                }
            }
            val bodyAvailable = bodySupported >= 6
            runOnUiThread {
                overlay.setSnapshot(
                    PerceptionVNextOverlayView.Snapshot(
                        prepared.transform.sourceWidth,
                        prepared.transform.sourceHeight,
                        left.overlay,
                        right.overlay,
                        bodyXY,
                        bodySupport,
                    ),
                )
            }
            val now = System.nanoTime()
            if (firstAnalyzedNs == 0L) firstAnalyzedNs = now
            lastAnalyzedNs = now
            analyzedFrames.incrementAndGet()
            val metric = FrameMetric(
                conditionId = "LIVE",
                note = "",
                personVisible = false,
                physicalLeftVisible = false,
                physicalRightVisible = false,
                crossed = false,
                bodyAvailable = bodyAvailable,
                leftObserved = left.overlay.observed,
                rightObserved = right.overlay.observed,
                leftPresence = left.overlay.presence,
                rightPresence = right.overlay.presence,
                leftXY = left.overlay.xy.copyOf(),
                leftValid = left.overlay.valid.copyOf(),
                rightXY = right.overlay.xy.copyOf(),
                rightValid = right.overlay.valid.copyOf(),
                leftRoi = left.overlay.roi,
                rightRoi = right.overlay.roi,
                bodyXY = bodyXY.copyOf(),
                bodySupport = bodySupport.copyOf(),
                bodyValid = bodyValid.copyOf(),
                preprocessMs = preprocessMs,
                dwposeMs = pose.inferenceMs,
                decodeMs = pose.decodeMs,
                cropMs = left.cropMs + right.cropMs,
                leftRefinerMs = left.refinerMs,
                rightRefinerMs = right.refinerMs,
                totalMs = (now - frameStarted) / 1_000_000.0,
                sensorTimestampNs = image.imageInfo.timestamp,
                thermalStatus = (getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus,
                pssKb = Debug.getPss(),
            )
            rolling.addLast(metric)
            while (rolling.size > 60) rolling.removeFirst()
            maybeRecordCondition(metric)
            if (analyzedFrames.get() % 30L == 0L) writeLiveRuntimeSnapshot()
            showLive(metric)
        } catch (error: Throwable) {
            fail(error.stackTraceToString())
            runOnUiThread { provider?.unbindAll() }
        } finally {
            image.close()
        }
    }

    private fun runHand(
        prepared: PerceptionVNextNativePreprocessor,
        decoded: PerceptionVNextMath.Decoded,
        start: Int,
    ): HandStage {
        val roi = PerceptionVNextMath.handRoi(decoded, start, prepared.transform)
        if (roi == null) {
            return HandStage(
                PerceptionVNextOverlayView.Hand(
                    FloatArray(42),
                    BooleanArray(21),
                    false,
                    null,
                    null,
                ),
                0.0,
                null,
            )
        }
        val cropStarted = System.nanoTime()
        val input = prepared.crop(roi)
        val cropMs = (System.nanoTime() - cropStarted) / 1_000_000.0
        val result = requireNotNull(refiner).run(input, roi)
        return HandStage(
            PerceptionVNextOverlayView.Hand(
                result.xySource,
                result.valid,
                result.observed,
                result.presence,
                roi,
            ),
            cropMs,
            result.inferenceMs,
        )
    }

    private fun maybeRecordCondition(live: FrameMetric) {
        val completion: Boolean
        synchronized(stateLock) {
            val condition = conditions.getOrNull(conditionIndex) ?: return
            if (!conditionActive) return
            val elapsedMs = (System.nanoTime() - conditionStartNs) / 1_000_000.0
            val scheduledMs = conditionFrames.toDouble() * condition.durationMs / condition.targetFrames
            if (elapsedMs < 0 || elapsedMs + 1e-6 < scheduledMs) return
            measurements.add(
                live.copy(
                    conditionId = condition.id,
                    note = condition.note,
                    personVisible = condition.personVisible,
                    physicalLeftVisible = condition.leftVisible,
                    physicalRightVisible = condition.rightVisible,
                    crossed = condition.crossed,
                ),
            )
            conditionFrames++
            completion = conditionFrames >= condition.targetFrames
            if (completion) {
                conditionActive = false
                conditionIndex++
            }
        }
        if (completion) {
            writeEvidence()
            runOnUiThread {
                renderCondition()
                if (conditionIndex < conditions.size) {
                    action.isEnabled = true
                    action.text = "START NEXT CONDITION"
                } else {
                    action.isEnabled = false
                    action.text = "PHONE_01 CAPTURE COMPLETE"
                }
            }
        }
    }

    private fun showLive(metric: FrameMetric) {
        val analyzerFps = if (lastAnalyzedNs > firstAnalyzedNs) {
            (analyzedFrames.get() - 1) * 1_000_000_000.0 / (lastAnalyzedNs - firstAnalyzedNs)
        } else {
            0.0
        }
        val message = String.format(
            Locale.US,
            "PERCEPTION VNEXT — LH %s %.2f  RH %s %.2f  BODY %s\n" +
                "FPS %.1f | pre %.1f | DWPose-t %.1f | crop %.1f | hand %.1f | total %.1f ms\n" +
                "Current-frame only · recognition/S5/S7/UI disconnected",
            if (metric.leftObserved) "ON" else "--",
            metric.leftPresence ?: 0f,
            if (metric.rightObserved) "ON" else "--",
            metric.rightPresence ?: 0f,
            if (metric.bodyAvailable) "ON" else "--",
            analyzerFps,
            percentile(rolling.map { it.preprocessMs }, 0.5) ?: 0.0,
            percentile(rolling.map { it.dwposeMs }, 0.5) ?: 0.0,
            percentile(rolling.map { it.cropMs }, 0.5) ?: 0.0,
            percentile(rolling.flatMap { listOfNotNull(it.leftRefinerMs, it.rightRefinerMs) }, 0.5)
                ?: 0.0,
            percentile(rolling.map { it.totalMs }, 0.5) ?: 0.0,
        )
        runOnUiThread { status.text = message }
    }

    private fun renderCondition() {
        val condition = conditions.getOrNull(conditionIndex)
        instruction.text = if (condition == null) {
            "All 320 governed frames captured. Evidence saved on device."
        } else {
            val state = if (conditionActive) "CAPTURING ${conditionFrames}/${condition.targetFrames}" else "READY"
            "${conditionIndex + 1}/${conditions.size} · $state · ${condition.label}\n${condition.instruction}"
        }
    }

    private fun writeIdentity() {
        val identity = JSONObject()
            .put("schema", "APPHEAR_PERCEPTION_VNEXT_PHONE_SESSION_IDENTITY_V1")
            .put("milestone", "PERCEPTION_VNEXT_PHONE_01")
            .put("created_utc", utcNow())
            .put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
            .put("android_version", Build.VERSION.RELEASE)
            .put("dwpose_t_sha256", DWPoseTRunner.MODEL_SHA256)
            .put("hand_refiner_sha256", HandRefinerRunner.MODEL_SHA256)
            .put("source_semantics", "UPRIGHT_UNMIRRORED_SOURCE_RGB")
            .put("preview_mirrored", true)
            .put("current_frame_only", true)
            .put("carry_forward", false)
            .put("synthetic_depth", false)
            .put("preprocessor", "PARITY_GATED_NATIVE_REUSABLE_RGBA_TO_DWPOSE_AND_HAND_CROPS")
            .put("recognizer_connected", false)
            .put("s5_s7_ui_connected", false)
        File(sessionRoot, "session_identity.json").writeText(identity.toString(2))
    }

    private fun writeEvidence() {
        val frames = File(sessionRoot, "frame_measurements.jsonl")
        frames.bufferedWriter().use { writer ->
            for (row in measurements) {
                writer.appendLine(
                    JSONObject()
                        .put("condition_id", row.conditionId)
                        .put("operator_note", row.note)
                        .put("person_visible", row.personVisible)
                        .put("physical_left_visible", row.physicalLeftVisible)
                        .put("physical_right_visible", row.physicalRightVisible)
                        .put("hands_crossed", row.crossed)
                        .put("body_available", row.bodyAvailable)
                        .put("left_observed", row.leftObserved)
                        .put("right_observed", row.rightObserved)
                        .put("left_presence", row.leftPresence ?: JSONObject.NULL)
                        .put("right_presence", row.rightPresence ?: JSONObject.NULL)
                        .put("left_xy_source", json(row.leftXY))
                        .put("left_valid", json(row.leftValid))
                        .put("right_xy_source", json(row.rightXY))
                        .put("right_valid", json(row.rightValid))
                        .put("left_roi", json(row.leftRoi))
                        .put("right_roi", json(row.rightRoi))
                        .put("body_indices", JSONArray(PerceptionVNextMath.bodyIndices.toList()))
                        .put("body_xy_source", json(row.bodyXY))
                        .put("body_support", json(row.bodySupport))
                        .put("body_valid", json(row.bodyValid))
                        .put("preprocessing_ms", row.preprocessMs)
                        .put("dwpose_t_ms", row.dwposeMs)
                        .put("decode_ms", row.decodeMs)
                        .put("hand_crop_ms", row.cropMs)
                        .put("left_refiner_ms", row.leftRefinerMs ?: JSONObject.NULL)
                        .put("right_refiner_ms", row.rightRefinerMs ?: JSONObject.NULL)
                        .put("total_perception_ms", row.totalMs)
                        .put("sensor_timestamp_ns", row.sensorTimestampNs)
                        .put("thermal_status", row.thermalStatus)
                        .put("pss_kb", row.pssKb)
                        .toString(),
                )
            }
        }
        val grouped = measurements.groupBy { Pair(it.conditionId, it.note) }
        val conditionRows = JSONArray()
        for ((key, rows) in grouped) {
            val visibleLeft = rows.filter { it.physicalLeftVisible }
            val visibleRight = rows.filter { it.physicalRightVisible }
            val expectedTwo = rows.filter { it.physicalLeftVisible && it.physicalRightVisible }
            val falseSlots = rows.sumOf {
                (if (it.leftObserved && !it.physicalLeftVisible) 1 else 0) +
                    (if (it.rightObserved && !it.physicalRightVisible) 1 else 0)
            }
            conditionRows.put(
                JSONObject()
                    .put("condition_id", key.first)
                    .put("operator_note", key.second)
                    .put("frames", rows.size)
                    .put("left_observed_rate", rate(visibleLeft.count { it.leftObserved }, visibleLeft.size))
                    .put("right_observed_rate", rate(visibleRight.count { it.rightObserved }, visibleRight.size))
                    .put("complete_two_rate", rate(expectedTwo.count { it.leftObserved && it.rightObserved }, expectedTwo.size))
                    .put("false_slot_rate", falseSlots.toDouble() / (2 * rows.size))
                    .put("body_available_rate", rows.count { it.bodyAvailable }.toDouble() / rows.size),
            )
        }
        val durationSeconds = if (lastAnalyzedNs > firstAnalyzedNs) {
            (lastAnalyzedNs - firstAnalyzedNs) / 1_000_000_000.0
        } else {
            0.0
        }
        val cameraCount = cameraFrames.get()
        val analyzerCount = analyzedFrames.get()
        val summary = JSONObject()
            .put("schema", "APPHEAR_PERCEPTION_VNEXT_PHONE_RESULT_V1")
            .put("milestone", "PERCEPTION_VNEXT_PHONE_01")
            .put("status", if (measurements.size == 320) "CONTROLLED_CAPTURE_COMPLETE" else "PARTIAL")
            .put("controlled_frames", measurements.size)
            .put("camera_capture_callbacks", cameraCount)
            .put("analyzed_frames", analyzerCount)
            .put("estimated_keep_only_latest_skips", maxOf(0L, cameraCount - analyzerCount))
            .put("analyzer_completed_fps", if (durationSeconds > 0) analyzerCount / durationSeconds else JSONObject.NULL)
            .put("preprocessing_p50_ms", percentile(measurements.map { it.preprocessMs }, 0.50))
            .put("preprocessing_p95_ms", percentile(measurements.map { it.preprocessMs }, 0.95))
            .put("dwpose_t_p50_ms", percentile(measurements.map { it.dwposeMs }, 0.50))
            .put("dwpose_t_p95_ms", percentile(measurements.map { it.dwposeMs }, 0.95))
            .put("per_hand_refiner_p50_ms", percentile(measurements.flatMap { listOfNotNull(it.leftRefinerMs, it.rightRefinerMs) }, 0.50))
            .put("per_hand_refiner_p95_ms", percentile(measurements.flatMap { listOfNotNull(it.leftRefinerMs, it.rightRefinerMs) }, 0.95))
            .put("total_perception_p50_ms", percentile(measurements.map { it.totalMs }, 0.50))
            .put("total_perception_p95_ms", percentile(measurements.map { it.totalMs }, 0.95))
            .put("peak_pss_kb", measurements.maxOfOrNull { it.pssKb } ?: JSONObject.NULL)
            .put("maximum_thermal_status", measurements.maxOfOrNull { it.thermalStatus } ?: JSONObject.NULL)
            .put("condition_metrics", conditionRows)
            .put("recognizer_connected", false)
            .put("s5_s7_ui_connected", false)
        File(sessionRoot, "phone_result.json").writeText(summary.toString(2))
    }

    private fun writeLiveRuntimeSnapshot() {
        if (rolling.isEmpty()) return
        val durationSeconds = if (lastAnalyzedNs > firstAnalyzedNs) {
            (lastAnalyzedNs - firstAnalyzedNs) / 1_000_000_000.0
        } else {
            0.0
        }
        val snapshot = JSONObject()
            .put("schema", "APPHEAR_PERCEPTION_VNEXT_NATIVE_RUNTIME_SNAPSHOT_V1")
            .put("analyzed_frames", analyzedFrames.get())
            .put(
                "analyzer_completed_fps",
                if (durationSeconds > 0) analyzedFrames.get() / durationSeconds else JSONObject.NULL,
            )
            .put("rolling_frames", rolling.size)
            .put("preprocessing_p50_ms", percentile(rolling.map { it.preprocessMs }, 0.50))
            .put("preprocessing_p95_ms", percentile(rolling.map { it.preprocessMs }, 0.95))
            .put("dwpose_t_p50_ms", percentile(rolling.map { it.dwposeMs }, 0.50))
            .put("dwpose_t_p95_ms", percentile(rolling.map { it.dwposeMs }, 0.95))
            .put("hand_crop_p50_ms", percentile(rolling.map { it.cropMs }, 0.50))
            .put("hand_crop_p95_ms", percentile(rolling.map { it.cropMs }, 0.95))
            .put(
                "per_hand_refiner_p50_ms",
                percentile(
                    rolling.flatMap { listOfNotNull(it.leftRefinerMs, it.rightRefinerMs) },
                    0.50,
                ),
            )
            .put("total_perception_p50_ms", percentile(rolling.map { it.totalMs }, 0.50))
            .put("total_perception_p95_ms", percentile(rolling.map { it.totalMs }, 0.95))
            .put("peak_pss_kb", rolling.maxOf { it.pssKb })
            .put("maximum_thermal_status", rolling.maxOf { it.thermalStatus })
            .put("recognizer_connected", false)
        File(sessionRoot, "live_runtime_snapshot.json").writeText(snapshot.toString(2))
    }

    private fun rate(numerator: Int, denominator: Int): Any =
        if (denominator == 0) JSONObject.NULL else numerator.toDouble() / denominator

    private fun json(values: FloatArray): JSONArray =
        JSONArray().also { output -> values.forEach { output.put(it.toDouble()) } }

    private fun json(values: BooleanArray): JSONArray =
        JSONArray().also { output -> values.forEach { output.put(it) } }

    private fun json(roi: PerceptionVNextMath.HandRoi?): Any =
        if (roi == null) {
            JSONObject.NULL
        } else {
            JSONObject()
                .put("center_x", roi.centerX)
                .put("center_y", roi.centerY)
                .put("side", roi.side)
                .put("left", roi.left)
                .put("top", roi.top)
                .put("right", roi.right)
                .put("bottom", roi.bottom)
                .put("support_count_0p10", roi.supportCount)
        }

    private fun percentile(values: List<Double>, q: Double): Double? {
        if (values.isEmpty()) return null
        val sorted = values.sorted()
        val position = q * (sorted.size - 1)
        val low = position.toInt()
        val high = minOf(low + 1, sorted.lastIndex)
        return sorted[low] + (sorted[high] - sorted[low]) * (position - low)
    }

    private fun fail(value: String) {
        if (::sessionRoot.isInitialized) {
            File(sessionRoot, "failure.txt").writeText(value)
        }
        Log.e(TAG, value)
        runOnUiThread {
            status.text = "PERCEPTION VNEXT FAILED\n${value.lineSequence().first()}"
            action.isEnabled = false
        }
    }

    override fun onDestroy() {
        provider?.unbindAll()
        analyzer.execute {
            dwpose?.close()
            refiner?.close()
            preprocessor?.close()
        }
        analyzer.shutdown()
        super.onDestroy()
    }

    private fun utcNow(): String =
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(Date())

    private fun utcCompact(): String =
        SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(Date())

    companion object {
        const val EXTRA_ENABLED = "perception_vnext_enabled"
        private const val CAMERA_REQUEST = 901
        private const val TAG = "PerceptionVNext"
    }
}
