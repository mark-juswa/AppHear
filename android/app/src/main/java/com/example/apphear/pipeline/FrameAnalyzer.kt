package com.example.apphear.pipeline

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.example.apphear.pipeline.recognition.FeatureFlags
import com.example.apphear.pipeline.recognition.LandmarkAdapter
import com.example.apphear.pipeline.recognition.RecognitionPipeline
import com.example.apphear.pipeline.recognition.RecognitionState
import com.example.apphear.pipeline.recognition.RuntimeConfig
import com.example.apphear.pipeline.diagnostics.RuD1Diagnostics
import com.example.apphear.pipeline.diagnostics.RuD1FrameObservation
import com.example.apphear.pipeline.diagnostics.A1Diagnostics
import com.example.apphear.ui.PhoneOverlayFrame
import com.example.apphear.contextassist.RecognitionEvidence
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.system.measureNanoTime

/** One processed frame plus runtime measurement state surfaced to the UI. */
data class FrameResult(
    val hands: HandLandmarkerResult?,
    val pose: PoseLandmarkerResult?,
    val imageWidth: Int,
    val imageHeight: Int,
    val fps: Double,
    val isFrontCamera: Boolean,
    val qualityLabel: String,
    val poseEveryN: Int,
    val recognition: RecognitionState? = null,
    val cameraFps: Double = 0.0,
    val droppedFrames: Long = 0,
    val lowFpsActive: Boolean = false,
    val phoneOverlay: PhoneOverlayFrame? = null,
    val phoneReady: Boolean? = null,
    val phoneSentence: String? = null,
    val recognitionEvidence: RecognitionEvidence? = null,
)

/** S0->S1/S2 bridge with optional profiling ablations. */
class FrameAnalyzer(
    private val landmarkers: LandmarkerBundle,
    private val isFrontCamera: Boolean,
    private val recognizer: RecognitionPipeline?,
    private val runtime: RuntimeConfig,
    private val deviceSummary: String,
    private val ruD1: RuD1Diagnostics? = null,
    private val a1Diagnostics: A1Diagnostics? = null,
    private val onResult: (FrameResult) -> Unit,
) : CloseableFrameAnalyzer {

    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private val processedFps = FpsTracker()
    private val cameraFps = FpsTracker()
    private val busy = AtomicBoolean(false)
    private val adaptive = AdaptiveController()
    private val lowFps = LowFpsMonitor(
        runtime.lowFpsEnterBelow,
        runtime.lowFpsExitAbove,
        runtime.lowFpsConsecutiveFrames,
    )
    private val profiler = RuntimeProfiler(FeatureFlags.PROFILING_MODE, deviceSummary)
    private var frameIndex = 0L
    private var processedFrames = 0L
    private var droppedFrames = 0L
    private var lastPose: PoseLandmarkerResult? = null
    private var lastPoseSourceTimestampNs: Long? = null
    private var lastProcessedStartNs = 0L

    override fun analyze(image: ImageProxy) {
        val sourceTimestampNs = image.imageInfo.timestamp
        val analyzerArrivalNs = a1Diagnostics?.nowNs() ?: 0L
        a1Diagnostics?.event(
            "CAMERA_DELIVERED",
            "source_ns" to sourceTimestampNs,
            "arrival_ns" to analyzerArrivalNs,
        )
        val inputRate = cameraFps.tick()
        if (!busy.compareAndSet(false, true)) {
            droppedFrames++
            a1Diagnostics?.event("ANALYZER_DROP", "source_ns" to sourceTimestampNs, "reason" to "BUSY")
            image.close()
            return
        }
        a1Diagnostics?.event("ANALYZER_ACCEPT", "source_ns" to sourceTimestampNs)
        val wallStart = System.nanoTime()
        val interFrameNs = if (lastProcessedStartNs == 0L) 0L else wallStart - lastProcessedStartNs
        lastProcessedStartNs = wallStart
        val rotation = image.imageInfo.rotationDegrees
        var convNs = 0L
        val bitmap = try {
            var b: Bitmap
            a1Diagnostics?.event("CONVERSION_START", "source_ns" to sourceTimestampNs)
            convNs = measureNanoTime { b = image.toBitmap() }
            a1Diagnostics?.event("CONVERSION_END", "source_ns" to sourceTimestampNs, "duration_ns" to convNs)
            b
        } catch (t: Throwable) {
            a1Diagnostics?.event(
                "ANALYZER_DROP",
                "source_ns" to sourceTimestampNs,
                "reason" to "CONVERSION_EXCEPTION",
                "error" to t.javaClass.simpleName,
            )
            busy.set(false)
            return
        } finally {
            image.close()
        }

        scope.launch {
            var upright: Bitmap? = null
            try {
                var rotateNs = 0L
                val analysisBitmap = run {
                    var rotated: Bitmap
                    a1Diagnostics?.event("ROTATION_START", "source_ns" to sourceTimestampNs)
                    rotateNs = measureNanoTime { rotated = rotate(bitmap, rotation) }
                    a1Diagnostics?.event("ROTATION_END", "source_ns" to sourceTimestampNs, "duration_ns" to rotateNs)
                    rotated.also { upright = it }
                }
                val mode = FeatureFlags.PROFILING_MODE
                val runHands = mode == ProfilingMode.HAND_ONLY || mode == ProfilingMode.HAND_AND_POSE ||
                    mode == ProfilingMode.FULL_RECOGNITION
                val requestedPoseEvery = when {
                    mode == ProfilingMode.POSE_ONLY || mode == ProfilingMode.HAND_AND_POSE -> 1
                    mode == ProfilingMode.FULL_RECOGNITION && recognizer != null -> recognizer.poseCadenceEveryN
                    else -> adaptive.poseEveryN
                }.coerceAtLeast(1)
                val runPose = when (mode) {
                    ProfilingMode.CAMERA_ONLY, ProfilingMode.HAND_ONLY -> false
                    ProfilingMode.POSE_ONLY, ProfilingMode.HAND_AND_POSE -> true
                    ProfilingMode.FULL_RECOGNITION -> recognizer != null && frameIndex % requestedPoseEvery == 0L
                }
                a1Diagnostics?.event(
                    "POSE_ELIGIBILITY",
                    "source_ns" to sourceTimestampNs,
                    "eligible" to runPose,
                    "pose_every" to requestedPoseEvery,
                )

                var handNs = 0L
                var poseNs = 0L
                val handImage = if (runHands) BitmapImageBuilder(analysisBitmap).build() else null
                val poseImage = if (runPose) BitmapImageBuilder(analysisBitmap).build() else null
                val handsDeferred = if (runHands) {
                    a1Diagnostics?.event("HAND_MAILBOX_ENQUEUE", "source_ns" to sourceTimestampNs)
                    async {
                        var h: HandLandmarkerResult
                        try {
                            val startNs = a1Diagnostics?.nowNs() ?: 0L
                            a1Diagnostics?.event("HAND_WORKER_DEQUEUE", "source_ns" to sourceTimestampNs)
                            a1Diagnostics?.event("HAND_INFERENCE_START", "source_ns" to sourceTimestampNs, "start_ns" to startNs)
                            handNs = measureNanoTime { h = landmarkers.detectHands(checkNotNull(handImage)) }
                            val endNs = a1Diagnostics?.nowNs() ?: 0L
                            a1Diagnostics?.event(
                                "HAND_INFERENCE_END",
                                "source_ns" to sourceTimestampNs,
                                "start_ns" to startNs,
                                "end_ns" to endNs,
                                "duration_ns" to handNs,
                            )
                            h
                        } finally {
                            if (FeatureFlags.RU_D10_OBSERVATION_CONTINUITY) handImage?.close()
                        }
                    }
                } else {
                    null
                }
                val poseDeferred = if (runPose) {
                    a1Diagnostics?.event("POSE_MAILBOX_ENQUEUE", "source_ns" to sourceTimestampNs)
                    async {
                        var p: PoseLandmarkerResult
                        try {
                            val startNs = a1Diagnostics?.nowNs() ?: 0L
                            a1Diagnostics?.event("POSE_WORKER_DEQUEUE", "source_ns" to sourceTimestampNs)
                            a1Diagnostics?.event("POSE_INFERENCE_START", "source_ns" to sourceTimestampNs, "start_ns" to startNs)
                            poseNs = measureNanoTime { p = landmarkers.detectPose(checkNotNull(poseImage)) }
                            val endNs = a1Diagnostics?.nowNs() ?: 0L
                            a1Diagnostics?.event(
                                "POSE_INFERENCE_END",
                                "source_ns" to sourceTimestampNs,
                                "start_ns" to startNs,
                                "end_ns" to endNs,
                                "duration_ns" to poseNs,
                            )
                            p
                        } finally {
                            if (FeatureFlags.RU_D10_OBSERVATION_CONTINUITY) poseImage?.close()
                        }
                    }
                } else {
                    null
                }
                val hands = handsDeferred?.await()
                val handPublishNs = a1Diagnostics?.nowNs() ?: 0L
                if (hands != null) {
                    a1Diagnostics?.event(
                        "HAND_PUBLICATION",
                        "source_ns" to sourceTimestampNs,
                        "publish_ns" to handPublishNs,
                    )
                }
                val poseFresh = poseDeferred != null
                val pose = if (poseDeferred != null) {
                    poseDeferred.await().also {
                        lastPose = it
                        lastPoseSourceTimestampNs = sourceTimestampNs
                        a1Diagnostics?.event(
                            "POSE_PUBLICATION",
                            "source_ns" to sourceTimestampNs,
                            "publish_ns" to a1Diagnostics?.nowNs(),
                        )
                    }
                } else {
                    lastPose
                }
                frameIndex++

                var recognition: RecognitionState? = null
                val low = lowFps.active
                val poseArray = LandmarkAdapter.pose(pose)
                val handsArray = LandmarkAdapter.hands(hands)
                val consumerStartNs = a1Diagnostics?.nowNs() ?: 0L
                val poseSourceNs = lastPoseSourceTimestampNs
                val poseAgeNs = poseSourceNs?.let { sourceTimestampNs - it }
                a1Diagnostics?.event(
                    "SYNCHRONIZER_JOIN",
                    "hand_source_ns" to sourceTimestampNs,
                    "pose_source_ns" to poseSourceNs,
                    "pose_age_ns" to poseAgeNs,
                    "pose_fresh" to poseFresh,
                    "status" to if (pose != null) "VALID" else "NO_CAUSAL_POSE",
                )
                a1Diagnostics?.event(
                    "CONSUMER_START",
                    "source_ns" to sourceTimestampNs,
                    "consumer_ns" to consumerStartNs,
                    "hand_result_age_ns" to if (handPublishNs > 0L) consumerStartNs - handPublishNs else null,
                    "source_to_s4_ns" to if (analyzerArrivalNs > 0L) consumerStartNs - analyzerArrivalNs else null,
                )
                val recogNs = measureNanoTime {
                    if (mode == ProfilingMode.FULL_RECOGNITION && recognizer != null && hands != null && pose != null) {
                        recognition = recognizer.processFrame(poseArray, handsArray, low)
                    }
                }
                a1Diagnostics?.event(
                    "CONSUMER_END",
                    "source_ns" to sourceTimestampNs,
                    "duration_ns" to recogNs,
                    "s4_observation" to (hands != null && pose != null),
                )

                val f = processedFps.tick()
                processedFrames++
                val lowNow = lowFps.update(f)
                adaptive.update(f)
                val trace = recognizer?.lastRuD1Trace
                if (trace != null && ruD1?.isActive == true) {
                    ruD1.record(
                        RuD1FrameObservation(
                            timestampNs = wallStart,
                            processedFps = f,
                            lowFpsUsed = low,
                            poseFresh = poseFresh,
                            handCount = detectedHandCount(handsArray),
                            leftHandPresent = slotPresent(handsArray, 0),
                            rightHandPresent = slotPresent(handsArray, 1),
                            posePresent = poseArray.any { !it.isNaN() },
                            leftWristVisibility = poseVisibility(poseArray, 15),
                            rightWristVisibility = poseVisibility(poseArray, 16),
                            leftElbowVisibility = poseVisibility(poseArray, 13),
                            rightElbowVisibility = poseVisibility(poseArray, 14),
                            leftShoulderVisibility = poseVisibility(poseArray, 11),
                            rightShoulderVisibility = poseVisibility(poseArray, 12),
                            pipeline = trace,
                        ),
                        analysisBitmap,
                    )
                }
                val wallNs = System.nanoTime() - wallStart
                if (FeatureFlags.PROFILE_STAGES || mode != ProfilingMode.FULL_RECOGNITION) {
                    profiler.record(
                        RuntimeTiming(convNs, rotateNs, handNs, poseNs, recogNs, wallNs, interFrameNs),
                        inputRate,
                        f,
                        processedFrames,
                        droppedFrames,
                        lowNow,
                        requestedPoseEvery,
                    )
                }

                onResult(
                    FrameResult(
                        hands, pose, analysisBitmap.width, analysisBitmap.height, f, isFrontCamera,
                        adaptive.qualityLabel(), requestedPoseEvery, recognition,
                        inputRate, droppedFrames, lowNow,
                    ),
                )
            } finally {
                if (FeatureFlags.RU_D10_OBSERVATION_CONTINUITY) {
                    upright?.takeUnless { it.isRecycled }?.recycle()
                    if (upright !== bitmap && !bitmap.isRecycled) bitmap.recycle()
                }
                busy.set(false)
            }
        }
    }

    override fun close() {
        scope.coroutineContext[kotlinx.coroutines.Job]?.cancel()
    }

    private fun rotate(bitmap: Bitmap, degrees: Int): Bitmap {
        if (degrees == 0) return bitmap
        val m = Matrix().apply { postRotate(degrees.toFloat()) }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, m, true)
    }

    private fun slotPresent(hands: FloatArray, slot: Int): Boolean = !hands[slot * 21 * 3].isNaN()

    private fun detectedHandCount(hands: FloatArray): Int =
        (if (slotPresent(hands, 0)) 1 else 0) + (if (slotPresent(hands, 1)) 1 else 0)

    private fun poseVisibility(pose: FloatArray, landmark: Int): Float? =
        pose[landmark * 4 + 3].takeIf { it.isFinite() }
}
