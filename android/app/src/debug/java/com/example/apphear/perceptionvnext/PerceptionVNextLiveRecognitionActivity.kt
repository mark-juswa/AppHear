package com.example.apphear.perceptionvnext

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.TotalCaptureResult
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.SystemClock
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
import androidx.activity.OnBackPressedCallback
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
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/**
 * PHASE_4A_GATE_4A1B_CONTROLLED_LIVE_INPUT_RECOVERY_01.
 *
 * Debug-only START -> one isolated sign -> STOP -> classify. Candidate 01 stays warm before
 * START. Membership is based solely on ImageProxy source timestamps. The first processed frame
 * newer than T_stop is a deterministic drain sentinel, so eligible work that completes after STOP
 * is retained. Actual live observations use the frozen DENSE selection path; PHONE_01 simulation
 * is never applied to already-sparse live data.
 */
@OptIn(ExperimentalCamera2Interop::class)
class PerceptionVNextLiveRecognitionActivity : AppCompatActivity() {
    private data class Target(
        val classId: Int,
        val gloss: String,
        val fixtureId: String,
        val repetition: Int,
    )
    private enum class CaptureState { IDLE, CAPTURING, DRAINING, COMPLETE, FAILED }

    private data class HandFrame(
        val xy: FloatArray,
        val valid: BooleanArray,
        val observed: Boolean,
        val presence: Float,
        val handedness: Float,
        val proposalPresent: Boolean,
        val proposalSupport: FloatArray,
        val roi: PerceptionVNextMath.HandRoi?,
        val cropMs: Double,
        val refinerMs: Double?,
    )

    private data class LiveRawFrame(
        val sourceTimestampNs: Long,
        val completionTimestampNs: Long,
        val sourceWidth: Int,
        val sourceHeight: Int,
        val left: HandFrame,
        val right: HandFrame,
        val bodyXy: FloatArray,
        val bodySupport: FloatArray,
        val bodyValid: BooleanArray,
        val bodyAvailable: Boolean,
        val preprocessMs: Double,
        val dwposeMs: Double,
        val decodeMs: Double,
        val totalMs: Double,
        val cameraFrameCount: Long,
        val analyzedFrameCount: Long,
        val thermalStatus: Int,
        val pssKb: Long,
    )

    private data class Attempt(
        val attemptOrdinal: Int,
        val targetOrdinal: Int,
        val target: Target,
        val startedNs: Long,
        var stoppedNs: Long? = null,
        val frames: MutableList<LiveRawFrame> = mutableListOf(),
        var rejectedOutsideInterval: Int = 0,
        var inFlightCompletedAfterStop: Int = 0,
        val cameraFramesAtStart: Long,
        val analyzedFramesAtStart: Long,
        val warmObservationsAtStart: Int,
        val nativeParityCompleteAtStart: Boolean,
        val referenceAcknowledged: Boolean,
        val diagnosticFutures: MutableList<Future<Gate4A1bVisualDiagnostics.Saved>> = mutableListOf(),
        val savedDiagnosticOrdinals: MutableSet<Int> = mutableSetOf(),
        var lastDiagnostic: Pair<Int, Gate4A1bVisualDiagnostics.Frame>? = null,
        var previousHandState: String? = null,
    )

    private val analyzer = Executors.newSingleThreadExecutor()
    private val diagnosticWriter = Executors.newSingleThreadExecutor()
    private val running = AtomicBoolean(false)
    private val cameraFrames = AtomicLong(0)
    private val analyzedFrames = AtomicLong(0)
    private val stateLock = Any()
    private var provider: ProcessCameraProvider? = null
    private var dwpose: DWPoseTRunner? = null
    private var refiner: HandRefinerRunner? = null
    private var recognizer: RecognitionV2LiveRecognizer? = null
    private var preprocessor: PerceptionVNextNativePreprocessor? = null
    private val nativeParity = PerceptionVNextNativeParity()
    private var warmObservations = 0
    private var state = CaptureState.IDLE
    private var activeAttempt: Attempt? = null
    private var attemptOrdinal = 0
    private var targetOrdinal = 0
    private var validAttempts = 0
    private var invalidAttempts = 0
    private var lastSourceTimestampNs = Long.MIN_VALUE
    private lateinit var sessionRoot: File
    private lateinit var preview: PreviewView
    private lateinit var overlay: PerceptionVNextOverlayView
    private lateinit var status: TextView
    private lateinit var targetText: TextView
    private lateinit var resultText: TextView
    private lateinit var referenceButton: Button
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private var referenceAcknowledgedForTarget = -1
    private var phoneCausalMode = false
    private var phoneCausal: PhoneCausalController? = null
    private var phoneRearmPolicy = PhoneRearmPolicy.PRE_ONLY
    private var phoneS2Package = PhoneS2Package.PHASE7_CONTROL
    private var phoneS2ExactParityCaptureEnabled = false
    private var phoneEvidenceOrdinal = 0
    private val phoneEvidenceRing = ArrayDeque<Pair<Int, Gate4A1bVisualDiagnostics.Frame>>()
    private val phoneEvidenceFutures = mutableListOf<Future<*>>()
    private val phoneEvidenceFinalizing = AtomicBoolean(false)
    private val phoneEvidenceFinalized = AtomicBoolean(false)
    private var phoneEventEvidenceId: Int? = null
    private var phoneEventPostFramesRemaining = 0

    private val repeatedRecognitionTargets = listOf(
        Target(80, "HELLO", "p4a_v2_02", 1),
        Target(80, "HELLO", "p4a_v2_02", 2),
        Target(8, "AT", "p4a_v2_03", 1),
        Target(8, "AT", "p4a_v2_03", 2),
        Target(83, "HOME", "p4a_v2_05", 1),
        Target(83, "HOME", "p4a_v2_05", 2),
        Target(179, "STREET", "p4a_v2_06", 1),
        Target(179, "STREET", "p4a_v2_06", 2),
        Target(183, "TABLE", "p4a_v2_07", 1),
        Target(183, "TABLE", "p4a_v2_07", 2),
    )
    private val restedAdmissionEvidenceTargets = listOf(
        Target(80, "HELLO", "p4a_v2_02", 1),
        Target(80, "HELLO", "p4a_v2_02", 2),
        Target(83, "HOME", "p4a_v2_05", 1),
        Target(83, "HOME", "p4a_v2_05", 2),
        Target(183, "TABLE", "p4a_v2_07", 1),
        Target(183, "TABLE", "p4a_v2_07", 2),
    )
    private val targets: List<Target>
        get() = if (
            phoneCausalMode &&
            (intent.getBooleanExtra(EXTRA_RESTED_ADMISSION_EVIDENCE_COHORT, false) ||
                intent.getBooleanExtra(EXTRA_S2_R2_VALIDATION_COHORT, false))
        ) {
            restedAdmissionEvidenceTargets
        } else {
            repeatedRecognitionTargets
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        phoneCausalMode = intent.getBooleanExtra(EXTRA_PHONE_CAUSAL_ENABLED, false)
        phoneS2ExactParityCaptureEnabled = intent.getBooleanExtra(EXTRA_S2_EXACT_PARITY_CAPTURE, false)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (phoneCausalMode && state == CaptureState.COMPLETE && !phoneEvidenceFinalized.get()) {
                    finalizePhoneSession()
                    return
                }
                isEnabled = false
                onBackPressedDispatcher.onBackPressed()
            }
        })
        phoneRearmPolicy = intent.getStringExtra(EXTRA_PHONE_REARM_POLICY)?.let {
            requireNotNull(PhoneRearmPolicy.entries.firstOrNull { value -> value.name == it }) {
                "PHONE_CAUSAL_UNKNOWN_REARM_POLICY: $it"
            }
        } ?: PhoneRearmPolicy.PRE_ONLY
        phoneS2Package = intent.getStringExtra(EXTRA_PHONE_S2_PACKAGE)?.let {
            requireNotNull(PhoneS2Package.entries.firstOrNull { value -> value.name == it }) {
                "PHONE_CAUSAL_UNKNOWN_S2_PACKAGE: $it"
            }
        } ?: PhoneS2Package.PHASE7_CONTROL
        if (phoneCausalMode && phoneS2Package == PhoneS2Package.S2_R2_CANDIDATE) {
            require(intent.getBooleanExtra(EXTRA_S2_R2_VALIDATION_COHORT, false)) {
                "S2_R2_VALIDATION_COHORT_REQUIRED"
            }
            require(phoneS2ExactParityCaptureEnabled) { "S2_R2_EXACT_EVIDENCE_REQUIRED" }
            require(phoneRearmPolicy == PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL) {
                "S2_R2_FROZEN_REARM_POLICY_REQUIRED"
            }
            require(!intent.getStringExtra(EXTRA_VALIDATION_SIGNER_ID).isNullOrBlank()) {
                "S2_R2_DECLARED_VALIDATION_SIGNER_REQUIRED"
            }
        }
        buildUi()
        val phoneAllowed = !phoneCausalMode || BuildConfig.PHONE_CAUSAL_RECOGNITION_ENABLED
        if (
            !BuildConfig.PERCEPTION_VNEXT_ENABLED ||
            !intent.getBooleanExtra(EXTRA_ENABLED, false) ||
            !phoneAllowed
        ) {
            fail("GATE4A1_DISABLED: debug build flag and explicit ADB opt-in required")
            return
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        sessionRoot = File(
            requireNotNull(getExternalFilesDir(null)),
            "${if (phoneCausalMode) PHONE_CAUSAL_ROOT_NAME else ROOT_NAME}/session_${utcCompact()}",
        ).also { require(it.mkdirs()) }
        File(sessionRoot.parentFile, "latest_session.txt").writeText(sessionRoot.name)
        writeSessionIdentity()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_REQUEST)
        } else startRuntime()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_REQUEST && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) startRuntime()
        else if (requestCode == CAMERA_REQUEST) fail("GATE4A1_CAMERA_PERMISSION_DENIED")
    }

    private fun buildUi() {
        preview = PreviewView(this).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        overlay = PerceptionVNextOverlayView(this)
        status = TextView(this).apply {
            setTextColor(Color.WHITE); setBackgroundColor(0xB0000000.toInt()); textSize = 12f
            setPadding(16, 12, 16, 12); text = "Loading frozen Candidate 01 + recognizer…"
        }
        targetText = TextView(this).apply {
            setTextColor(Color.WHITE); setBackgroundColor(0xD0203040.toInt()); textSize = 22f
            setPadding(20, 14, 20, 14); text = "Target: waiting"
        }
        resultText = TextView(this).apply {
            setTextColor(Color.WHITE); setBackgroundColor(0xD0101820.toInt()); textSize = 14f
            setPadding(20, 12, 20, 12); text = "Watch the exact TRAIN clip on the PC before every attempt."
        }
        referenceButton = Button(this).apply {
            text = if (phoneCausalMode) "PHONE CAUSAL MODE" else "REFERENCE WATCHED"
            isEnabled = false
            setOnClickListener {
                if (state == CaptureState.IDLE && targetOrdinal < targets.size) {
                    referenceAcknowledgedForTarget = targetOrdinal
                    resultText.text = "Reference acknowledged. Confirm lighting/framing, then START."
                    renderReadyButtons()
                }
            }
        }
        startButton = Button(this).apply {
            text = "WAITING FOR WARMUP"
            isEnabled = false
            setOnClickListener {
                if (phoneCausalMode && state == CaptureState.COMPLETE) finalizePhoneSession()
                else if (phoneCausalMode) startPhoneAttempt()
                else startAttempt()
            }
        }
        stopButton = Button(this).apply {
            text = "STOP"
            isEnabled = false
            setOnClickListener { if (phoneCausalMode) stopPhoneAttempt() else stopAttempt() }
        }
        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(startButton, LinearLayout.LayoutParams(0, -2, 1f))
            addView(stopButton, LinearLayout.LayoutParams(0, -2, 1f))
        }
        val controls = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setPadding(12, 12, 12, 18)
            addView(targetText); addView(resultText); addView(referenceButton); addView(buttons)
        }
        val root = FrameLayout(this)
        root.addView(preview, FrameLayout.LayoutParams(-1, -1))
        root.addView(overlay, FrameLayout.LayoutParams(-1, -1))
        root.addView(status, FrameLayout.LayoutParams(-1, -2).apply { gravity = Gravity.TOP })
        root.addView(controls, FrameLayout.LayoutParams(-1, -2).apply { gravity = Gravity.BOTTOM })
        setContentView(root)
        renderTarget()
        if (phoneCausalMode) {
            referenceButton.visibility = android.view.View.GONE
            renderTarget()
            resultText.text = "Warming Candidate01 + frozen S2. Press START ATTEMPT only after READY."
        }
    }

    private fun startRuntime() {
        if (!running.compareAndSet(false, true)) return
        analyzer.execute {
            try {
                verifyFrozenIdentity()
                dwpose = DWPoseTRunner(this)
                refiner = HandRefinerRunner(this)
                recognizer = RecognitionV2LiveRecognizer(this)
                if (phoneCausalMode) {
                    phoneCausal = PhoneCausalController(
                        this,
                        requireNotNull(recognizer),
                        sessionRoot,
                        intent.getStringExtra(EXTRA_EXPECTED_GLOSS)?.trim()?.ifBlank { null },
                        PhoneDecoderConfig(
                            rearmPolicy = phoneRearmPolicy,
                            admissionPolicy = PhoneSignAdmissionPolicy.PASS_THROUGH,
                        ),
                        exactParityCaptureEnabled = phoneS2ExactParityCaptureEnabled,
                        s2Package = phoneS2Package,
                    )
                }
                runOnUiThread { bindCamera() }
            } catch (error: Throwable) { fail(error.stackTraceToString()) }
        }
    }

    private fun bindCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                provider = future.get()
                val previewUseCase = Preview.Builder().build().also { it.setSurfaceProvider(preview.surfaceProvider) }
                val builder = ImageAnalysis.Builder().setTargetResolution(Size(480, 360))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                Camera2Interop.Extender(builder)
                    .setCaptureRequestOption(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(15, 15))
                    .setSessionCaptureCallback(object : CameraCaptureSession.CaptureCallback() {
                        override fun onCaptureCompleted(session: CameraCaptureSession, request: CaptureRequest, result: TotalCaptureResult) {
                            cameraFrames.incrementAndGet()
                        }
                    })
                val analysis = builder.build().also { it.setAnalyzer(analyzer, ::analyze) }
                provider!!.unbindAll()
                provider!!.bindToLifecycle(this, CameraSelector.DEFAULT_FRONT_CAMERA, previewUseCase, analysis)
                status.text = if (phoneCausalMode) {
                    "Camera bound; causal pipeline warming. Wait for READY before signing."
                } else {
                    "Camera bound; perception warming. START remains locked until live parity and observations are ready."
                }
            } catch (error: Throwable) { fail(error.stackTraceToString()) }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun analyze(image: ImageProxy) {
        if (phoneEvidenceFinalizing.get()) {
            image.close()
            return
        }
        val frameStarted = SystemClock.elapsedRealtimeNanos()
        val sourceTimestampNs = image.imageInfo.timestamp
        try {
            require(sourceTimestampNs > lastSourceTimestampNs) { "GATE4A1_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP" }
            lastSourceTimestampNs = sourceTimestampNs
            val diagnosticPixels = if (phoneCausalMode || isPotentiallyEligible(sourceTimestampNs)) {
                Gate4A1bVisualDiagnostics.capture(image)
            } else {
                null
            }
            val preprocessStarted = SystemClock.elapsedRealtimeNanos()
            val prepared = preprocessor?.takeIf { it.compatible(image) }
                ?: PerceptionVNextNativePreprocessor(image).also { preprocessor = it }
            prepared.preprocess(image)
            val preprocessMs = (SystemClock.elapsedRealtimeNanos() - preprocessStarted) / 1_000_000.0
            if (!nativeParity.complete) {
                val reference = PerceptionVNextPreprocessor(image)
                val parityRoi = PerceptionVNextMath.HandRoi(
                    prepared.transform.centerX, prepared.transform.centerY,
                    minOf(prepared.transform.sourceWidth, prepared.transform.sourceHeight) * 0.30f,
                    prepared.transform.sourceWidth, prepared.transform.sourceHeight, 21,
                )
                nativeParity.compare(reference.dwposeInput(), prepared.poseInput, reference.handInput(parityRoi), prepared.crop(parityRoi))
                if (nativeParity.complete) {
                    val parity = nativeParity.result()
                    File(sessionRoot, "native_live_parity.json").writeText(parity.toString(2))
                    require(parity.getString("status") == "PASS") { "GATE4A1_NATIVE_PREPROCESS_PARITY_FAILED" }
                }
            }
            val pose = requireNotNull(dwpose).run(prepared.poseInput, prepared.transform)
            val left = runHand(prepared, pose.decoded, PerceptionVNextMath.LEFT_HAND_START)
            val right = runHand(prepared, pose.decoded, PerceptionVNextMath.RIGHT_HAND_START)
            val bodyXy = FloatArray(16)
            val bodySupport = FloatArray(8)
            val bodyValid = BooleanArray(8)
            var bodySupported = 0
            for ((local, point) in PerceptionVNextMath.bodyIndices.withIndex()) {
                val x = pose.decoded.xy[point * 2]; val y = pose.decoded.xy[point * 2 + 1]
                bodyXy[local * 2] = x; bodyXy[local * 2 + 1] = y
                bodySupport[local] = pose.decoded.support[point]
                bodyValid[local] = PerceptionVNextMath.bodyPointValid(x, y, bodySupport[local], prepared.transform)
                if (bodyValid[local]) bodySupported++
            }
            val completionNs = SystemClock.elapsedRealtimeNanos()
            val frame = LiveRawFrame(
                sourceTimestampNs, completionNs, prepared.transform.sourceWidth, prepared.transform.sourceHeight,
                left, right, bodyXy, bodySupport, bodyValid, bodySupported >= 6,
                preprocessMs, pose.inferenceMs, pose.decodeMs,
                (completionNs - frameStarted) / 1_000_000.0, cameraFrames.get(), analyzedFrames.incrementAndGet(),
                (getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus, Debug.getPss(),
            )
            val phoneResult = if (phoneCausalMode) {
                requireNotNull(phoneCausal).consume(frame.toPhoneRawObservation())
            } else null
            runOnUiThread {
                overlay.setSnapshot(PerceptionVNextOverlayView.Snapshot(
                    frame.sourceWidth, frame.sourceHeight,
                    PerceptionVNextOverlayView.Hand(left.xy, left.valid, left.observed, left.presence.takeIf { it.isFinite() }, left.roi),
                    PerceptionVNextOverlayView.Hand(right.xy, right.valid, right.observed, right.presence.takeIf { it.isFinite() }, right.roi),
                    bodyXy, bodySupport,
                ))
                if (phoneResult != null) {
                    resultText.text = "${phoneResult.gloss}  ${"%.3f".format(phoneResult.top1Probability)} | " +
                        "event=${phoneResult.event.eventId} obs=${phoneResult.window.observations.size} | " +
                        "recognizer=${"%.1f".format(phoneResult.recognitionInvocationMs)} ms"
                }
            }
            if (phoneCausalMode) {
                recordPhoneAuditFrame(frame, diagnosticPixels, pose.decoded, phoneResult)
            } else {
                admitOrDrain(frame, diagnosticPixels, pose.decoded)
            }
            warmObservations++
            updateWarmUi(frame)
        } catch (error: Throwable) {
            fail(error.stackTraceToString()); runOnUiThread { provider?.unbindAll() }
        } finally { image.close() }
    }

    private fun isPotentiallyEligible(sourceTimestampNs: Long): Boolean = synchronized(stateLock) {
        val attempt = activeAttempt ?: return@synchronized false
        val stop = attempt.stoppedNs
        sourceTimestampNs >= attempt.startedNs && (stop == null || sourceTimestampNs <= stop)
    }

    private fun runHand(prepared: PerceptionVNextNativePreprocessor, decoded: PerceptionVNextMath.Decoded, start: Int): HandFrame {
        val support = FloatArray(21) { decoded.support[start + it] }
        val roi = PerceptionVNextMath.handRoi(decoded, start, prepared.transform)
        if (roi == null) return HandFrame(
            FloatArray(42), BooleanArray(21), false, Float.NaN, Float.NaN, false,
            support, null, 0.0, null,
        )
        val cropStarted = SystemClock.elapsedRealtimeNanos()
        val input = prepared.crop(roi)
        val cropMs = (SystemClock.elapsedRealtimeNanos() - cropStarted) / 1_000_000.0
        val result = requireNotNull(refiner).run(input, roi)
        return HandFrame(result.xySource, result.valid, result.observed, result.presence,
            result.handednessDiagnostic, true, support, roi, cropMs, result.inferenceMs)
    }

    private fun startAttempt() {
        synchronized(stateLock) {
            if (
                state != CaptureState.IDLE || targetOrdinal >= targets.size || !isWarm() ||
                referenceAcknowledgedForTarget != targetOrdinal
            ) return
            attemptOrdinal++
            val start = SystemClock.elapsedRealtimeNanos()
            activeAttempt = Attempt(attemptOrdinal, targetOrdinal + 1, targets[targetOrdinal], start,
                cameraFramesAtStart = cameraFrames.get(), analyzedFramesAtStart = analyzedFrames.get(),
                warmObservationsAtStart = warmObservations,
                nativeParityCompleteAtStart = nativeParity.complete,
                referenceAcknowledged = true)
            referenceAcknowledgedForTarget = -1
            state = CaptureState.CAPTURING
            referenceButton.isEnabled = false; startButton.isEnabled = false; stopButton.isEnabled = true
            resultText.text = "CAPTURING ${targets[targetOrdinal].gloss} repetition ${targets[targetOrdinal].repetition}/2… perform one sign, then press STOP"
        }
    }

    private fun stopAttempt() {
        synchronized(stateLock) {
            if (state != CaptureState.CAPTURING) return
            activeAttempt!!.stoppedNs = SystemClock.elapsedRealtimeNanos()
            state = CaptureState.DRAINING
            stopButton.isEnabled = false
            resultText.text = "STOP recorded. Draining eligible Candidate 01 work by source timestamp…"
        }
    }

    private fun startPhoneAttempt() {
        synchronized(stateLock) {
            if (state != CaptureState.IDLE || targetOrdinal >= targets.size || !isWarm()) return
            attemptOrdinal++
            val start = SystemClock.elapsedRealtimeNanos()
            activeAttempt = Attempt(
                attemptOrdinal,
                targetOrdinal + 1,
                targets[targetOrdinal],
                start,
                cameraFramesAtStart = cameraFrames.get(),
                analyzedFramesAtStart = analyzedFrames.get(),
                warmObservationsAtStart = warmObservations,
                nativeParityCompleteAtStart = nativeParity.complete,
                referenceAcknowledged = false,
            )
            state = CaptureState.CAPTURING
            requireNotNull(phoneCausal).beginAttempt(attemptOrdinal, targets[targetOrdinal].gloss, start)
            startButton.isEnabled = false
            stopButton.isEnabled = true
            resultText.text = "CAPTURING ${targets[targetOrdinal].gloss}. Perform one sign, return to rest, then STOP."
        }
    }

    private fun stopPhoneAttempt() {
        synchronized(stateLock) {
            if (state != CaptureState.CAPTURING) return
            activeAttempt!!.stoppedNs = SystemClock.elapsedRealtimeNanos()
            state = CaptureState.DRAINING
            stopButton.isEnabled = false
            resultText.text = "STOP recorded; draining the last genuine Candidate01 observation…"
        }
    }

    private fun recordPhoneAuditFrame(
        frame: LiveRawFrame,
        pixels: Gate4A1bVisualDiagnostics.Pixels?,
        decoded: PerceptionVNextMath.Decoded,
        phoneResult: PhoneCausalResult?,
    ) {
        val diagnostic = Gate4A1bVisualDiagnostics.Frame(
            pixels = requireNotNull(pixels) { "PHONE_CAUSAL_AUDIT_PIXELS_MISSING" },
            sourceTimestampNs = frame.sourceTimestampNs,
            completionTimestampNs = frame.completionTimestampNs,
            sourceWidth = frame.sourceWidth,
            sourceHeight = frame.sourceHeight,
            dwposeXy = decoded.xy.copyOf(),
            dwposeSupport = decoded.support.copyOf(),
            bodyXy = frame.bodyXy.copyOf(),
            bodySupport = frame.bodySupport.copyOf(),
            left = diagnosticHand(frame.left),
            right = diagnosticHand(frame.right),
        )
        recordContinuousPhoneEvidence(diagnostic, phoneResult?.event?.eventId)
        var finalize: Attempt? = null
        synchronized(stateLock) {
            val attempt = activeAttempt ?: return
            val stop = attempt.stoppedNs
            val eligible = frame.sourceTimestampNs >= attempt.startedNs && (stop == null || frame.sourceTimestampNs <= stop)
            if (eligible) {
                attempt.frames.add(frame)
                val ordinal = attempt.frames.size
                attempt.lastDiagnostic = ordinal to diagnostic
                scheduleDiagnostic(attempt, ordinal, diagnostic, listOf("PHONE_CAUSAL_HUMAN_AUDIT"))
            } else if (state == CaptureState.DRAINING && stop != null && frame.sourceTimestampNs > stop) {
                activeAttempt = null
                finalize = attempt
            }
        }
        finalize?.let(::finalizePhoneAttempt)
    }

    private fun recordContinuousPhoneEvidence(
        diagnostic: Gate4A1bVisualDiagnostics.Frame,
        emittedEventId: Int?,
    ) {
        phoneEvidenceOrdinal++
        require(phoneEvidenceOrdinal <= MAX_CONTINUOUS_PHONE_EVIDENCE_FRAMES) {
            "PHONE_CAUSAL_CONTINUOUS_EVIDENCE_LIMIT_REACHED"
        }
        val ordinal = phoneEvidenceOrdinal
        val originals = File(sessionRoot, "continuous_visual/originals")
        phoneEvidenceFutures += diagnosticWriter.submit<JSONObject> {
            Gate4A1bVisualDiagnostics.writeOriginal(originals, ordinal, diagnostic)
        }

        phoneEvidenceRing.addLast(ordinal to diagnostic)
        while (phoneEvidenceRing.size > EVENT_EVIDENCE_PRE_OBSERVATIONS) phoneEvidenceRing.removeFirst()

        if (emittedEventId != null) {
            phoneEventEvidenceId = emittedEventId
            phoneEventPostFramesRemaining = EVENT_EVIDENCE_POST_OBSERVATIONS
            val eventDirectory = eventEvidenceDirectory(emittedEventId)
            phoneEvidenceRing.forEach { (savedOrdinal, savedFrame) ->
                phoneEvidenceFutures += diagnosticWriter.submit<Gate4A1bVisualDiagnostics.Saved> {
                    Gate4A1bVisualDiagnostics.write(
                        eventDirectory,
                        savedOrdinal,
                        listOf("EVENT_${emittedEventId}_PRE_OR_COMMIT"),
                        savedFrame,
                    )
                }
            }
        } else if (phoneEventPostFramesRemaining > 0) {
            val eventId = checkNotNull(phoneEventEvidenceId)
            val eventDirectory = eventEvidenceDirectory(eventId)
            phoneEvidenceFutures += diagnosticWriter.submit<Gate4A1bVisualDiagnostics.Saved> {
                Gate4A1bVisualDiagnostics.write(
                    eventDirectory,
                    ordinal,
                    listOf("EVENT_${eventId}_POST_COMMIT"),
                    diagnostic,
                )
            }
            phoneEventPostFramesRemaining--
            if (phoneEventPostFramesRemaining == 0) phoneEventEvidenceId = null
        }
    }

    private fun eventEvidenceDirectory(eventId: Int) = File(
        sessionRoot,
        "continuous_visual/events/event_${eventId.toString().padStart(3, '0')}",
    ).also { require(it.exists() || it.mkdirs()) }

    private fun flushContinuousPhoneEvidence() {
        val savedOriginals = PhoneVisualEvidenceFinalizer.awaitVerifiedOriginals(
            phoneEvidenceFutures,
            File(sessionRoot, "continuous_visual/originals"),
            phoneEvidenceOrdinal,
        )
        File(sessionRoot, "continuous_visual/evidence_summary.json").apply {
            require(parentFile?.exists() == true || parentFile?.mkdirs() == true)
            writeText(
                JSONObject()
                    .put("schema", "apphear.phone_continuous_visual_evidence.v1")
                    .put("observation_frames_saved", phoneEvidenceOrdinal)
                    .put("verified_original_files", savedOriginals)
                    .put("finalized_after_capture_stop", true)
                    .put("maximum_frames", MAX_CONTINUOUS_PHONE_EVIDENCE_FRAMES)
                    .put("event_pre_observations", EVENT_EVIDENCE_PRE_OBSERVATIONS)
                    .put("event_post_observations", EVENT_EVIDENCE_POST_OBSERVATIONS)
                    .put("full_session_originals", true)
                    .put("event_centered_diagnostics", true)
                    .toString(2),
            )
        }
    }

    private fun finalizePhoneSession() {
        if (!phoneCausalMode || state != CaptureState.COMPLETE ||
            !phoneEvidenceFinalizing.compareAndSet(false, true)) return
        startButton.isEnabled = false
        resultText.text = "Stopping camera and draining all visual evidence. Keep AppHear open."
        provider?.unbindAll()
        // The analyzer is single-threaded: this barrier runs after every already-admitted frame.
        analyzer.execute {
            try {
                phoneCausal?.finalizeDiagnostics()
                flushContinuousPhoneEvidence()
                phoneEvidenceFinalized.set(true)
                runOnUiThread {
                    startButton.text = "VISUAL EVIDENCE SAVED"
                    resultText.text = "Session finalized: $phoneEvidenceOrdinal originals verified. You may close AppHear."
                }
            } catch (error: Throwable) { fail(error.stackTraceToString()) }
        }
    }

    private fun finalizePhoneAttempt(attempt: Attempt) {
        try {
            val diagnostics = flushDiagnostics(attempt)
            requireNotNull(phoneCausal).completeAttempt(attempt.attemptOrdinal, requireNotNull(attempt.stoppedNs))
            val value = baseAttemptJson(attempt, "PHONE_CAUSAL_ATTEMPT_COMPLETE")
                .put("visual_audit_frames", diagnostics)
                .put("automatic_pipeline_continuous_across_attempt_boundary", true)
            File(attemptDirectory(attempt), "phone_attempt.json").writeText(value.toString(2))
            validAttempts++
            targetOrdinal++
            synchronized(stateLock) {
                state = if (targetOrdinal >= targets.size) CaptureState.COMPLETE else CaptureState.IDLE
            }
            if (state == CaptureState.COMPLETE) {
                // Preserve the historical last-attempt writer barrier, but do not mark a still-running
                // continuous capture as finally complete.
                PhoneVisualEvidenceFinalizer.awaitVerifiedOriginals(
                    phoneEvidenceFutures,
                    File(sessionRoot, "continuous_visual/originals"),
                    phoneEvidenceOrdinal,
                )
            }
            runOnUiThread {
                renderTarget()
                renderReadyButtons()
                if (state == CaptureState.COMPLETE) {
                    resultText.text = "Attempts complete. Tap FINALIZE & SAVE EVIDENCE before closing."
                }
            }
        } catch (error: Throwable) {
            fail(error.stackTraceToString())
        }
    }

    private fun admitOrDrain(
        frame: LiveRawFrame,
        pixels: Gate4A1bVisualDiagnostics.Pixels?,
        decoded: PerceptionVNextMath.Decoded,
    ) {
        var finalize: Attempt? = null
        synchronized(stateLock) {
            val attempt = activeAttempt ?: return
            val stop = attempt.stoppedNs
            val eligible = frame.sourceTimestampNs >= attempt.startedNs && (stop == null || frame.sourceTimestampNs <= stop)
            if (eligible) {
                require(attempt.frames.lastOrNull()?.sourceTimestampNs?.let { frame.sourceTimestampNs > it } ?: true)
                attempt.frames.add(frame)
                val acceptedOrdinal = attempt.frames.size
                val diagnostic = Gate4A1bVisualDiagnostics.Frame(
                    pixels = requireNotNull(pixels) { "GATE4A1B_ELIGIBLE_FRAME_PIXELS_MISSING" },
                    sourceTimestampNs = frame.sourceTimestampNs,
                    completionTimestampNs = frame.completionTimestampNs,
                    sourceWidth = frame.sourceWidth,
                    sourceHeight = frame.sourceHeight,
                    dwposeXy = decoded.xy.copyOf(),
                    dwposeSupport = decoded.support.copyOf(),
                    bodyXy = frame.bodyXy.copyOf(),
                    bodySupport = frame.bodySupport.copyOf(),
                    left = diagnosticHand(frame.left),
                    right = diagnosticHand(frame.right),
                )
                attempt.lastDiagnostic = acceptedOrdinal to diagnostic
                val handState = "${frame.left.proposalPresent}:${frame.left.observed}:" +
                    "${frame.right.proposalPresent}:${frame.right.observed}"
                val reasons = mutableListOf<String>()
                if (acceptedOrdinal == 1) reasons += "FIRST_ACCEPTED"
                if (acceptedOrdinal % DIAGNOSTIC_EVERY_N == 0) reasons += "EVERY_10TH_ACCEPTED"
                if (attempt.previousHandState != null && attempt.previousHandState != handState) {
                    reasons += "HAND_STATE_TRANSITION"
                }
                attempt.previousHandState = handState
                if (reasons.isNotEmpty()) scheduleDiagnostic(attempt, acceptedOrdinal, diagnostic, reasons)
                if (stop != null && frame.completionTimestampNs > stop) attempt.inFlightCompletedAfterStop++
            } else {
                attempt.rejectedOutsideInterval++
                if (state == CaptureState.DRAINING && stop != null && frame.sourceTimestampNs > stop) {
                    // Source timestamps are strictly increasing. Seeing this first post-stop frame
                    // proves no future callback can belong to the stopped interval.
                    activeAttempt = null
                    finalize = attempt
                }
            }
        }
        finalize?.let { finalizeAttempt(it) }
    }

    private fun diagnosticHand(hand: HandFrame) = Gate4A1bVisualDiagnostics.Hand(
        refinedXy = hand.xy.copyOf(),
        refinedValid = hand.valid.copyOf(),
        observed = hand.observed,
        presence = hand.presence,
        proposalPresent = hand.proposalPresent,
        proposalSupport = hand.proposalSupport.copyOf(),
        roi = hand.roi,
    )

    private fun LiveRawFrame.toPhoneRawObservation(): PhoneRawObservation {
        fun roi(hand: HandFrame) = hand.roi?.let { floatArrayOf(it.centerX, it.centerY, it.side) }
            ?: FloatArray(3)
        return PhoneRawObservation(
            sourceIndex = analyzedFrameCount.toInt() - 1,
            timestampMs = sourceTimestampNs / 1_000_000.0,
            sourceWidth = sourceWidth,
            sourceHeight = sourceHeight,
            handXy = arrayOf(left.xy.copyOf(), right.xy.copyOf()),
            handJointValid = arrayOf(left.valid.copyOf(), right.valid.copyOf()),
            handProposalSupport = arrayOf(left.proposalSupport.copyOf(), right.proposalSupport.copyOf()),
            handPresence = floatArrayOf(left.presence, right.presence),
            handObserved = booleanArrayOf(left.observed, right.observed),
            handProposalPresent = booleanArrayOf(left.proposalPresent, right.proposalPresent),
            handRoiCenterSide = arrayOf(roi(left), roi(right)),
            bodyXy = bodyXy.copyOf(),
            bodySupport = bodySupport.copyOf(),
            bodyValid = bodyValid.copyOf(),
            bodyAvailable = bodyAvailable,
            candidatePreprocessMs = preprocessMs,
            candidatePoseInferenceMs = dwposeMs,
            candidatePoseDecodeMs = decodeMs,
            candidateTotalMs = totalMs,
        )
    }

    private fun scheduleDiagnostic(
        attempt: Attempt,
        acceptedOrdinal: Int,
        diagnostic: Gate4A1bVisualDiagnostics.Frame,
        reasons: List<String>,
    ) {
        if (!attempt.savedDiagnosticOrdinals.add(acceptedOrdinal)) return
        val directory = attemptDirectory(attempt)
        attempt.diagnosticFutures += diagnosticWriter.submit<Gate4A1bVisualDiagnostics.Saved> {
            Gate4A1bVisualDiagnostics.write(directory, acceptedOrdinal, reasons, diagnostic)
        }
    }

    private fun flushDiagnostics(attempt: Attempt): JSONArray {
        attempt.lastDiagnostic?.let { (ordinal, diagnostic) ->
            if (ordinal !in attempt.savedDiagnosticOrdinals) {
                scheduleDiagnostic(attempt, ordinal, diagnostic, listOf("LAST_ACCEPTED"))
            }
        }
        return JSONArray(attempt.diagnosticFutures.map { it.get().json })
    }

    private fun finalizeAttempt(attempt: Attempt) {
        try {
            val stopped = requireNotNull(attempt.stoppedNs)
            if (attempt.frames.isEmpty()) {
                invalidAttempts++
                persistInvalidAttempt(attempt, "CAPTURE_INVALID_NO_OBSERVATION")
                synchronized(stateLock) { state = CaptureState.IDLE }
                runOnUiThread {
                    resultText.text = "INVALID: no eligible completed observation. Evidence saved; retry ${attempt.target.gloss}."
                    renderReadyButtons()
                }
                writeSessionSummary()
                return
            }
            val diagnostics = flushDiagnostics(attempt)
            val raw = toRawSequence(attempt.frames)
            val v2Started = SystemClock.elapsedRealtimeNanos()
            // Live data is already at actual phone cadence. DENSE here means preserve every real,
            // unique chronological observation, truncating only if count exceeds frozen max 96.
            val view = RecognitionV2.temporalView(raw, RecognitionV2.TemporalCondition.DENSE)
            val v2Ms = (SystemClock.elapsedRealtimeNanos() - v2Started) / 1_000_000.0
            require(view.realLength == minOf(attempt.frames.size, RecognitionV2.MAX_SEQUENCE_LENGTH))
            val prediction = requireNotNull(recognizer).invoke(view, RecognitionV2.FEATURE_SCHEMA)
            val resultNs = SystemClock.elapsedRealtimeNanos()
            persistValidAttempt(
                attempt,
                raw,
                view,
                prediction,
                diagnostics,
                v2Ms,
                (resultNs - stopped) / 1_000_000.0,
            )
            validAttempts++
            val expectedInTop5 = prediction.top5.contains(attempt.target.classId)
            val top1 = prediction.top5.first()
            targetOrdinal++
            synchronized(stateLock) { state = if (validAttempts >= targets.size) CaptureState.COMPLETE else CaptureState.IDLE }
            runOnUiThread {
                resultText.text = "Top-1: ${requireNotNull(recognizer).glosses[top1]}  ${"%.4f".format(prediction.probabilities[top1])}\n" +
                    "Top-5: ${prediction.top5.joinToString { requireNotNull(recognizer).glosses[it] }}\n" +
                    "Expected in Top-5: $expectedInTop5 | obs=${attempt.frames.size} | STOP→result=${"%.1f".format((resultNs - stopped) / 1_000_000.0)} ms"
                renderTarget(); renderReadyButtons()
            }
            writeSessionSummary()
        } catch (error: Throwable) { fail(error.stackTraceToString()) }
    }

    private fun toRawSequence(frames: List<LiveRawFrame>): RecognitionV2.RawSequence {
        val t = frames.size
        return RecognitionV2.RawSequence(
            schema = RecognitionV2.RAW_SCHEMA,
            imageSemantics = IMAGE_SEMANTICS,
            frameIndex = IntArray(t) { it },
            timestampMs = DoubleArray(t) { frames[it].sourceTimestampNs / 1_000_000.0 },
            sourceSize = IntArray(t * 2).also { out -> frames.forEachIndexed { i, f -> out[i * 2] = f.sourceWidth; out[i * 2 + 1] = f.sourceHeight } },
            handXy = FloatArray(t * 84).also { out -> frames.forEachIndexed { i, f -> f.left.xy.copyInto(out, i * 84); f.right.xy.copyInto(out, i * 84 + 42) } },
            handProposalSupport = FloatArray(t * 42).also { out -> frames.forEachIndexed { i, f -> f.left.proposalSupport.copyInto(out, i * 42); f.right.proposalSupport.copyInto(out, i * 42 + 21) } },
            handJointValid = BooleanArray(t * 42).also { out -> frames.forEachIndexed { i, f -> f.left.valid.copyInto(out, i * 42); f.right.valid.copyInto(out, i * 42 + 21) } },
            handPresence = FloatArray(t * 2).also { out -> frames.forEachIndexed { i, f -> out[i * 2] = f.left.presence; out[i * 2 + 1] = f.right.presence } },
            handObserved = BooleanArray(t * 2).also { out -> frames.forEachIndexed { i, f -> out[i * 2] = f.left.observed; out[i * 2 + 1] = f.right.observed } },
            bodyXy = FloatArray(t * 16).also { out -> frames.forEachIndexed { i, f -> f.bodyXy.copyInto(out, i * 16) } },
            bodySupport = FloatArray(t * 8).also { out -> frames.forEachIndexed { i, f -> f.bodySupport.copyInto(out, i * 8) } },
            bodyValid = BooleanArray(t * 8).also { out -> frames.forEachIndexed { i, f -> f.bodyValid.copyInto(out, i * 8) } },
            bodyAvailable = BooleanArray(t) { frames[it].bodyAvailable },
        ).also { it.validate() }
    }

    private fun persistValidAttempt(
        attempt: Attempt, raw: RecognitionV2.RawSequence, view: RecognitionV2.TemporalView,
        prediction: RecognitionV2LiveRecognizer.Prediction,
        diagnostics: JSONArray,
        v2Ms: Double,
        stopToResultMs: Double,
    ) {
        val directory = attemptDirectory(attempt)
        val rawFile = File(directory, "raw_v1.json")
        rawFile.writeText(rawJson(raw, attempt.frames).toString(2))
        val tensorFile = File(directory, "recognition_v2.f32").also { it.writeBytes(floatBytes(view.features)) }
        val maskFile = File(directory, "frame_mask.u8").also { it.writeBytes(ByteArray(96) { index -> if (view.mask[index]) 1 else 0 }) }
        val probabilityFile = File(directory, "probabilities.f32").also { it.writeBytes(floatBytes(prediction.probabilities)) }
        val top1 = prediction.top5.first()
        val summary = baseAttemptJson(attempt, "VALID")
            .put("raw_file", rawFile.name).put("raw_sha256", sha256(rawFile))
            .put("v2_tensor_file", tensorFile.name).put("v2_tensor_sha256", sha256(tensorFile))
            .put("mask_file", maskFile.name).put("mask_sha256", sha256(maskFile))
            .put("probabilities_file", probabilityFile.name).put("probabilities_sha256", sha256(probabilityFile))
            .put("selected_source_indices", JSONArray(view.sourceIndices.toList()))
            .put("selected_source_timestamps_ms", JSONArray(view.sourceTimestampsMs.toList()))
            .put("selected_observation_count", view.realLength)
            .put("frame_mask_true", view.mask.count { it })
            .put("live_temporal_policy", "DENSE_ACTUAL_LIVE_OBSERVATIONS_NO_PHONE_01_RESAMPLING")
            .put("top1_index", top1).put("top1_gloss", requireNotNull(recognizer).glosses[top1])
            .put("top1_probability", prediction.probabilities[top1])
            .put("top5_indices", JSONArray(prediction.top5.toList()))
            .put("top5_glosses", JSONArray(prediction.top5.map { requireNotNull(recognizer).glosses[it] }))
            .put("expected_in_top5", prediction.top5.contains(attempt.target.classId))
            .put("semantic_top1_correct", top1 == attempt.target.classId)
            .put("diagnostic_sampling_rule", "FIRST + EVERY_10TH + HAND_STATE_TRANSITION + LAST")
            .put("diagnostic_last_accepted_ordinal", attempt.frames.size)
            .put("visual_diagnostics", diagnostics)
            .put("latency_ms", JSONObject().put("v2_construction", v2Ms)
                .put("tflite_invocation", prediction.invocationMs).put("stop_to_result", stopToResultMs))
        File(directory, "attempt.json").writeText(summary.toString(2))
    }

    private fun persistInvalidAttempt(attempt: Attempt, classification: String) {
        val directory = attemptDirectory(attempt)
        File(directory, "attempt.json").writeText(baseAttemptJson(attempt, classification).toString(2))
    }

    private fun baseAttemptJson(attempt: Attempt, classification: String): JSONObject {
        val stop = requireNotNull(attempt.stoppedNs)
        return JSONObject().put("milestone", MILESTONE)
            .put("classification", classification).put("session_id", sessionRoot.name)
            .put("attempt_id", "attempt_${attempt.attemptOrdinal.toString().padStart(3, '0')}")
            .put("attempt_ordinal", attempt.attemptOrdinal).put("target_ordinal", attempt.targetOrdinal)
            .put("expected_class_id", attempt.target.classId).put("expected_gloss", attempt.target.gloss)
            .put("fixture_id", attempt.target.fixtureId).put("repetition", attempt.target.repetition)
            .put("exact_train_reference_acknowledged", attempt.referenceAcknowledged)
            .put("controlled_capture_conditions_acknowledged", attempt.referenceAcknowledged)
            .put("tester_signer_status", TESTER_STATUS).put("t_start_ns", attempt.startedNs)
            .put("t_stop_ns", stop).put("capture_duration_ms", (stop - attempt.startedNs) / 1_000_000.0)
            .put("accepted_source_timestamps_ns", JSONArray(attempt.frames.map { it.sourceTimestampNs }))
            .put("completion_timestamps_ns", JSONArray(attempt.frames.map { it.completionTimestampNs }))
            .put("observation_count", attempt.frames.size)
            .put("in_flight_completions_after_stop", attempt.inFlightCompletedAfterStop)
            .put("rejected_outside_interval", attempt.rejectedOutsideInterval)
            .put("camera_frames_during_attempt", cameraFrames.get() - attempt.cameraFramesAtStart)
            .put("analyzed_frames_during_attempt", analyzedFrames.get() - attempt.analyzedFramesAtStart)
            .put("candidate01_warm_before_start", attempt.warmObservationsAtStart >= WARM_OBSERVATIONS && attempt.nativeParityCompleteAtStart)
            .put("warm_observations_at_start", attempt.warmObservationsAtStart)
            .put("native_preprocess_parity_complete_at_start", attempt.nativeParityCompleteAtStart)
            .put("source_timestamp_membership", "t_start <= source_timestamp <= t_stop")
            .put("callback_completion_time_used_for_membership", false)
            .put("drain_sentinel", "first strictly chronological processed source timestamp > t_stop")
    }

    private fun rawJson(raw: RecognitionV2.RawSequence, frames: List<LiveRawFrame>) = JSONObject()
        .put("schema", raw.schema).put("image_semantics", raw.imageSemantics)
        .put("frame_index", JSONArray(raw.frameIndex.toList()))
        .put("timestamp_ms", JSONArray(raw.timestampMs.toList()))
        .put("source_size", JSONArray(raw.sourceSize.toList()))
        .put("hand_xy", floatJson(raw.handXy)).put("hand_proposal_support", floatJson(raw.handProposalSupport))
        .put("hand_joint_valid", JSONArray(raw.handJointValid.toList()))
        .put("hand_presence", floatJson(raw.handPresence)).put("hand_observed", JSONArray(raw.handObserved.toList()))
        .put("hand_proposal_present", JSONArray(frames.flatMap { listOf(it.left.proposalPresent, it.right.proposalPresent) }))
        .put("hand_roi_center_side", floatJson(frames.flatMap { f -> listOf(f.left, f.right).flatMap { h -> listOf(h.roi?.centerX ?: Float.NaN, h.roi?.centerY ?: Float.NaN, h.roi?.side ?: Float.NaN) } }.toFloatArray()))
        .put("hand_handedness_diagnostic", floatJson(frames.flatMap { listOf(it.left.handedness, it.right.handedness) }.toFloatArray()))
        .put("body_xy", floatJson(raw.bodyXy)).put("body_support", floatJson(raw.bodySupport))
        .put("body_valid", JSONArray(raw.bodyValid.toList())).put("body_available", JSONArray(raw.bodyAvailable.toList()))
        .put("frame_runtime", JSONArray(frames.map { f -> JSONObject()
            .put("source_timestamp_ns", f.sourceTimestampNs).put("completion_timestamp_ns", f.completionTimestampNs)
            .put("preprocess_ms", f.preprocessMs).put("dwpose_ms", f.dwposeMs).put("decode_ms", f.decodeMs)
            .put("left_refiner_ms", finiteOrNull(f.left.refinerMs)).put("right_refiner_ms", finiteOrNull(f.right.refinerMs))
            .put("crop_ms", f.left.cropMs + f.right.cropMs).put("total_perception_ms", f.totalMs)
            .put("camera_frame_count", f.cameraFrameCount).put("analyzed_frame_count", f.analyzedFrameCount)
            .put("thermal_status", f.thermalStatus).put("pss_kb", f.pssKb) }))
        .put("current_frame_only", true).put("synthetic_depth", false).put("stale_carry_forward", false)

    private fun writeSessionIdentity() {
        val contractBytes = assets.open(RecognitionV2LiveRecognizer.CONTRACT_ASSET).use { it.readBytes() }
        val experimentContractBytes = assets.open(EXPERIMENT_CONTRACT_ASSET).use { it.readBytes() }
        val value = JSONObject().put("milestone", if (phoneCausalMode) PHONE_CAUSAL_MILESTONE else MILESTONE)
            .put("session_id", sessionRoot.name).put("created_utc", utcNow())
            .put("device_manufacturer", android.os.Build.MANUFACTURER).put("device_model", android.os.Build.MODEL)
            .put("android_version", android.os.Build.VERSION.RELEASE).put("tester_signer_status", TESTER_STATUS)
            .put("contract_asset", RecognitionV2LiveRecognizer.CONTRACT_ASSET)
            .put("contract_sha256", RecognitionV2LiveRecognizer.sha256(contractBytes))
            .put("experiment_contract_asset", EXPERIMENT_CONTRACT_ASSET)
            .put("experiment_contract_sha256", RecognitionV2LiveRecognizer.sha256(experimentContractBytes))
            .put("s2_exact_parity_capture_enabled", phoneS2ExactParityCaptureEnabled)
            .put("s2_package_id", if (phoneCausalMode) phoneS2Package.name else JSONObject.NULL)
            .put("declared_validation_signer_id", intent.getStringExtra(EXTRA_VALIDATION_SIGNER_ID) ?: JSONObject.NULL)
            .put("targets", JSONArray(targets.mapIndexed { index, t -> JSONObject().put("ordinal", index + 1).put("class_id", t.classId).put("gloss", t.gloss).put("fixture_id", t.fixtureId).put("repetition", t.repetition) }))
            .put(
                "diagnostic_sampling_rule",
                if (phoneCausalMode) {
                    "EVERY_PROCESSED_OBSERVATION_ORIGINAL + EVENT_CENTERED_DIAGNOSTIC_OVERLAY"
                } else "FIRST + EVERY_10TH + HAND_STATE_TRANSITION + LAST",
            )
            .put("phone_rearm_policy", if (phoneCausalMode) phoneRearmPolicy.name else JSONObject.NULL)
            .put(
                "phone_target_cohort",
                if (
                    phoneCausalMode &&
                    intent.getBooleanExtra(EXTRA_S2_R2_VALIDATION_COHORT, false)
                ) {
                    "S2_R2_VALIDATION_6"
                } else if (
                    phoneCausalMode &&
                    intent.getBooleanExtra(EXTRA_RESTED_ADMISSION_EVIDENCE_COHORT, false)
                ) {
                    "RESTED_ADMISSION_EVIDENCE_6"
                } else if (phoneCausalMode) {
                    "REPEATED_RECOGNITION_10"
                } else {
                    JSONObject.NULL
                },
            )
            .put(
                "phone_admission_policy",
                if (phoneCausalMode) PhoneSignAdmissionPolicy.PASS_THROUGH.name else JSONObject.NULL,
            )
            .put("evidence_retention", "pull entire session to host before uninstall/cleanup/reinstall")
            .put("dev_accessed", false).put("protected_test_accessed", false).put("training_executed", false)
        File(sessionRoot, "session_identity.json").writeText(value.toString(2))
    }

    private fun writeSessionSummary() {
        val attempts = sessionRoot.listFiles()?.filter { it.isDirectory && it.name.startsWith("attempt_") }?.sortedBy { it.name } ?: emptyList()
        val value = JSONObject().put("milestone", if (phoneCausalMode) PHONE_CAUSAL_MILESTONE else MILESTONE)
            .put("status", if (validAttempts == targets.size) "CAPTURE_COMPLETE_AWAITING_HOST_REPLAY" else "IN_PROGRESS")
            .put("valid_attempts", validAttempts).put("invalid_attempts", invalidAttempts)
            .put("attempt_directories", JSONArray(attempts.map { it.name }))
            .put("host_pull_required_before_cleanup", true)
            .put("dev_accessed", false).put("protected_test_accessed", false).put("training_executed", false)
        File(sessionRoot, "session_summary.json").writeText(value.toString(2))
    }

    private fun verifyFrozenIdentity() {
        val contract = JSONObject(assets.open(RecognitionV2LiveRecognizer.CONTRACT_ASSET).bufferedReader().readText())
        require(contract.getString("raw_schema") == RecognitionV2.RAW_SCHEMA)
        require(contract.getString("feature_schema") == RecognitionV2.FEATURE_SCHEMA)
        require(contract.getString("live_temporal_condition") == "DENSE_ACTUAL_LIVE_OBSERVATIONS_NO_PHONE_01_RESAMPLING")
        if (phoneCausalMode) {
            val phone = JSONObject(assets.open(phoneS2Package.contractPath).bufferedReader().readText())
            require(phone.getString("source_checkpoint_sha256") == phoneS2Package.checkpointSha256)
            require(phone.getString("source_normalization_sha256") == phoneS2Package.normalizationSha256)
            require(phone.getString("feature_schema") == PhoneSegmentationFeatureBuilder.SCHEMA)
        } else {
            val experiment = JSONObject(assets.open(EXPERIMENT_CONTRACT_ASSET).bufferedReader().readText())
            require(targets.map { it.classId } == listOf(80, 80, 8, 8, 83, 83, 179, 179, 183, 183))
            require(experiment.getString("milestone") == MILESTONE)
            require(experiment.getString("raw_schema") == RecognitionV2.RAW_SCHEMA)
            require(experiment.getString("feature_schema") == RecognitionV2.FEATURE_SCHEMA)
            require(experiment.getInt("valid_attempts_required") == targets.size)
            require(experiment.getBoolean("reference_acknowledgement_required_before_each_attempt"))
        }
        require(DWPoseTRunner.MODEL_SHA256 == "37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0")
        require(HandRefinerRunner.MODEL_SHA256 == "6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9")
    }

    private fun updateWarmUi(frame: LiveRawFrame) {
        val warm = isWarm()
        runOnUiThread {
            status.text = "Candidate01 ${if (warm) "READY" else "WARMING"} | " +
                "processed=${analyzedFrames.get()} | last=${"%.1f".format(frame.totalMs)} ms | " +
                "body=${frame.bodyAvailable} | LH=${frame.left.observed} RH=${frame.right.observed}" +
                if (phoneCausalMode) " | state=${phoneCausal?.snapshotJson()?.optString("event_state")}" else ""
            if (warm && state == CaptureState.IDLE) renderReadyButtons()
        }
    }

    private fun isWarm() = warmObservations >= WARM_OBSERVATIONS && nativeParity.complete && recognizer != null

    private fun renderTarget() {
        if (phoneCausalMode) {
            targetText.text = if (targetOrdinal < targets.size) {
                val target = targets[targetOrdinal]
                "Phone attempt ${targetOrdinal + 1}/${targets.size}: ${target.gloss} " +
                    "repetition ${target.repetition}/2"
            } else {
                "Phone causal cohort complete"
            }
            return
        }
        targetText.text = if (targetOrdinal < targets.size) {
            val target = targets[targetOrdinal]
            "Target ${targetOrdinal + 1}/${targets.size}: ${target.gloss} repetition ${target.repetition}/2\n" +
                "Watch ${target.fixtureId}; front light; upper body + hands fully visible"
        } else {
            "Gate 4A-1B capture complete"
        }
    }

    private fun renderReadyButtons() {
        if (phoneCausalMode) {
            when (state) {
                CaptureState.IDLE -> {
                    val decoderReady = phoneCausal?.snapshotJson()
                        ?.optString("event_state") == PhoneDecoderState.IDLE.name
                    startButton.text = when {
                        !isWarm() -> "WAITING FOR WARMUP"
                        !decoderReady -> "WAITING FOR RE-ARM"
                        else -> "START ATTEMPT"
                    }
                    startButton.isEnabled = isWarm() && decoderReady && targetOrdinal < targets.size
                    stopButton.isEnabled = false
                }
                CaptureState.CAPTURING -> {
                    startButton.isEnabled = false
                    stopButton.isEnabled = true
                }
                CaptureState.COMPLETE -> {
                    startButton.text = if (phoneEvidenceFinalized.get()) "VISUAL EVIDENCE SAVED" else "FINALIZE & SAVE EVIDENCE"
                    startButton.isEnabled = !phoneEvidenceFinalizing.get()
                    stopButton.isEnabled = false
                }
                else -> Unit
            }
            return
        }
        when (state) {
            CaptureState.IDLE -> {
                referenceButton.isEnabled = isWarm() && targetOrdinal < targets.size
                startButton.text = if (referenceAcknowledgedForTarget == targetOrdinal) "START" else "WATCH REFERENCE FIRST"
                startButton.isEnabled = isWarm() && referenceAcknowledgedForTarget == targetOrdinal
                stopButton.isEnabled = false
            }
            CaptureState.COMPLETE -> {
                referenceButton.isEnabled = false
                startButton.text = "10 VALID ATTEMPTS SAVED"
                startButton.isEnabled = false
                stopButton.isEnabled = false
            }
            else -> Unit
        }
    }

    private fun attemptDirectory(attempt: Attempt) = File(sessionRoot, "attempt_${attempt.attemptOrdinal.toString().padStart(3, '0')}").also { require(it.exists() || it.mkdirs()) }

    private fun floatBytes(values: FloatArray): ByteArray = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN).apply { asFloatBuffer().put(values) }.array()
    private fun floatJson(values: FloatArray) = JSONArray().also { output -> values.forEach { output.put(if (it.isFinite()) it else JSONObject.NULL) } }
    private fun finiteOrNull(value: Double?): Any = if (value != null && value.isFinite()) value else JSONObject.NULL

    private fun sha256(file: File): String = MessageDigest.getInstance("SHA-256").let { digest ->
        file.inputStream().use { input -> val block = ByteArray(64 * 1024); while (true) { val count = input.read(block); if (count < 0) break; digest.update(block, 0, count) } }
        digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun fail(value: String) {
        synchronized(stateLock) { state = CaptureState.FAILED }
        if (::sessionRoot.isInitialized) File(sessionRoot, "failure.txt").writeText(value)
        Log.e(TAG, value)
        runOnUiThread { status.text = "GATE 4A-1B FAILED\n${value.lineSequence().first()}"; startButton.isEnabled = false; stopButton.isEnabled = false }
    }

    override fun onDestroy() {
        if (phoneCausalMode && !phoneEvidenceFinalized.get()) {
            Log.e(TAG, "PHONE_CAUSAL_VISUAL_EVIDENCE_NOT_FINALIZED: use FINALIZE & SAVE EVIDENCE")
        }
        provider?.unbindAll()
        analyzer.execute {
            phoneCausal?.close()
            dwpose?.close(); refiner?.close(); recognizer?.close(); preprocessor?.close()
        }
        analyzer.shutdown()
        diagnosticWriter.shutdown()
        if (phoneCausalMode) diagnosticWriter.awaitTermination(30, TimeUnit.SECONDS)
        super.onDestroy()
    }

    private fun utcNow() = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())
    private fun utcCompact() = SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())

    companion object {
        const val EXTRA_ENABLED = "perception_vnext_enabled"
        const val EXTRA_PHONE_CAUSAL_ENABLED = "phone_causal_enabled"
        const val EXTRA_PHONE_REARM_POLICY = "phone_rearm_policy"
        const val EXTRA_RESTED_ADMISSION_EVIDENCE_COHORT = "rested_admission_evidence_cohort"
        const val EXTRA_S2_EXACT_PARITY_CAPTURE = "s2_exact_parity_capture"
        const val EXTRA_PHONE_S2_PACKAGE = "phone_s2_package"
        const val EXTRA_S2_R2_VALIDATION_COHORT = "s2_r2_validation_cohort"
        const val EXTRA_VALIDATION_SIGNER_ID = "validation_signer_id"
        const val EXTRA_EXPECTED_GLOSS = "expected_gloss"
        const val ROOT_NAME = "phase4a_gate4a1b_controlled_live_input_recovery_01"
        const val PHONE_CAUSAL_ROOT_NAME = "phone_repeated_recognition_integration_01"
        const val TESTER_STATUS = "UNKNOWN"
        const val IMAGE_SEMANTICS = "UPRIGHT_UNMIRRORED_SOURCE_RGB"
        private const val MILESTONE = "PHASE_4A_GATE_4A1B_CONTROLLED_LIVE_INPUT_RECOVERY_01"
        private const val PHONE_CAUSAL_MILESTONE = "PHONE_REPEATED_RECOGNITION_INTEGRATION_01"
        private const val EXPERIMENT_CONTRACT_ASSET = "phase4a_gate4a1b_controlled/contract.json"
        private const val DIAGNOSTIC_EVERY_N = 10
        private const val CAMERA_REQUEST = 9041
        private const val WARM_OBSERVATIONS = 4
        private const val MAX_CONTINUOUS_PHONE_EVIDENCE_FRAMES = 3600
        private const val EVENT_EVIDENCE_PRE_OBSERVATIONS = 24
        private const val EVENT_EVIDENCE_POST_OBSERVATIONS = 12
        private const val TAG = "Gate4A1Live"
    }
}
