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
)

/** S0->S1/S2 bridge with optional profiling ablations. */
class FrameAnalyzer(
    private val landmarkers: LandmarkerBundle,
    private val isFrontCamera: Boolean,
    private val recognizer: RecognitionPipeline?,
    private val runtime: RuntimeConfig,
    private val deviceSummary: String,
    private val onResult: (FrameResult) -> Unit,
) : ImageAnalysis.Analyzer {

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

    override fun analyze(image: ImageProxy) {
        val inputRate = cameraFps.tick()
        if (!busy.compareAndSet(false, true)) {
            droppedFrames++
            image.close()
            return
        }
        val wallStart = System.nanoTime()
        val rotation = image.imageInfo.rotationDegrees
        var convNs = 0L
        val bitmap = try {
            var b: Bitmap
            convNs = measureNanoTime { b = image.toBitmap() }
            b
        } catch (t: Throwable) {
            busy.set(false)
            return
        } finally {
            image.close()
        }

        scope.launch {
            try {
                var rotateNs = 0L
                val upright = run { var u: Bitmap; rotateNs = measureNanoTime { u = rotate(bitmap, rotation) }; u }
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

                var handNs = 0L
                var poseNs = 0L
                val mpImage = BitmapImageBuilder(upright).build()
                val handsDeferred = if (runHands) {
                    async {
                        var h: HandLandmarkerResult
                        handNs = measureNanoTime { h = landmarkers.detectHands(mpImage) }
                        h
                    }
                } else {
                    null
                }
                val poseDeferred = if (runPose) {
                    async {
                        var p: PoseLandmarkerResult
                        poseNs = measureNanoTime { p = landmarkers.detectPose(BitmapImageBuilder(upright).build()) }
                        p
                    }
                } else {
                    null
                }
                val hands = handsDeferred?.await()
                val pose = if (poseDeferred != null) poseDeferred.await().also { lastPose = it } else lastPose
                frameIndex++

                var recognition: RecognitionState? = null
                val low = lowFps.active
                val recogNs = measureNanoTime {
                    if (mode == ProfilingMode.FULL_RECOGNITION && recognizer != null && hands != null && pose != null) {
                        recognition = recognizer.processFrame(
                            LandmarkAdapter.pose(pose), LandmarkAdapter.hands(hands), low,
                        )
                    }
                }

                val f = processedFps.tick()
                processedFrames++
                val lowNow = lowFps.update(f)
                adaptive.update(f)
                val wallNs = System.nanoTime() - wallStart
                if (FeatureFlags.PROFILE_STAGES || mode != ProfilingMode.FULL_RECOGNITION) {
                    profiler.record(
                        RuntimeTiming(convNs, rotateNs, handNs, poseNs, recogNs, wallNs),
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
                        hands, pose, upright.width, upright.height, f, isFrontCamera,
                        adaptive.qualityLabel(), requestedPoseEvery, recognition,
                        inputRate, droppedFrames, lowNow,
                    ),
                )
            } finally {
                busy.set(false)
            }
        }
    }

    fun close() {
        scope.coroutineContext[kotlinx.coroutines.Job]?.cancel()
    }

    private fun rotate(bitmap: Bitmap, degrees: Int): Bitmap {
        if (degrees == 0) return bitmap
        val m = Matrix().apply { postRotate(degrees.toFloat()) }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, m, true)
    }
}
