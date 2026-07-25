package com.example.apphear.pipeline

import android.content.Context
import android.util.Log
import org.json.JSONObject
import com.example.apphear.pipeline.recognition.FeatureFlags
import com.google.mediapipe.framework.image.MPImage
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarker
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult

/**
 * S1 (hand) + S2 (pose) MediaPipe landmarkers, both in IMAGE mode, configured for parity with
 * offline extraction. `create()` is expensive (~1s of model loading) - call it OFF the main
 * thread (v2 lesson h: loading models on the main thread ANR'd v2).
 */
class LandmarkerBundle private constructor(
    private val hand: HandLandmarker,
    private val pose: PoseLandmarker,
) {
    fun detectHands(image: MPImage): HandLandmarkerResult = hand.detect(image)

    fun detectPose(image: MPImage): PoseLandmarkerResult = pose.detect(image)

    fun close() {
        hand.close()
        pose.close()
    }

    companion object {
        private const val TAG = "AppHearLandmarker"

        fun create(context: Context): LandmarkerBundle {
            // Keep both landmarkers on the same delegate so behavior is uniform. The default remains
            // GPU-with-CPU-fallback, but recognition_config.json can force CPU for measured A/B runs.
            val mode = delegateMode(context)
            val tryGpu = mode == "gpu"
            Log.i(TAG, "landmarker delegate mode=$mode")
            if (tryGpu) {
                try {
                    val bundle = LandmarkerBundle(
                        buildHand(context, Delegate.GPU), buildPose(context, Delegate.GPU),
                    )
                    Log.i(TAG, "landmarkers on GPU delegate")
                    return bundle
                } catch (t: Throwable) {
                    Log.w(TAG, "GPU delegate init failed, falling back to CPU: ${t.message}")
                }
            }
            val bundle = LandmarkerBundle(
                buildHand(context, Delegate.CPU), buildPose(context, Delegate.CPU),
            )
            Log.i(TAG, "landmarkers on CPU delegate")
            return bundle
        }

        private fun delegateMode(context: Context): String {
            val fallback = if (FeatureFlags.LANDMARKER_TRY_GPU) "gpu" else "cpu"
            return try {
                val text = context.assets.open("recognition_config.json").bufferedReader().use { it.readText() }
                val mode = JSONObject(text)
                    .optJSONObject("mediapipe_delegate")
                    ?.optString("mode", fallback)
                    ?.lowercase()
                    ?: fallback
                when (mode) {
                    "gpu", "cpu" -> mode
                    else -> fallback
                }
            } catch (t: Throwable) {
                Log.w(TAG, "failed to read landmarker delegate config, using $fallback: ${t.message}")
                fallback
            }
        }

        private fun buildHand(context: Context, delegate: Delegate): HandLandmarker =
            HandLandmarker.createFromOptions(
                context,
                HandLandmarker.HandLandmarkerOptions.builder()
                    .setBaseOptions(
                        BaseOptions.builder()
                            .setModelAssetPath(LandmarkerConfig.HAND_TASK)
                            .setDelegate(delegate)
                            .build(),
                    )
                    .setRunningMode(RunningMode.IMAGE)
                    .setNumHands(LandmarkerConfig.NUM_HANDS)
                    .setMinHandDetectionConfidence(LandmarkerConfig.MIN_HAND_DETECTION_CONFIDENCE)
                    .setMinHandPresenceConfidence(LandmarkerConfig.MIN_HAND_PRESENCE_CONFIDENCE)
                    .setMinTrackingConfidence(LandmarkerConfig.MIN_HAND_TRACKING_CONFIDENCE)
                    .build(),
            )

        private fun buildPose(context: Context, delegate: Delegate): PoseLandmarker =
            PoseLandmarker.createFromOptions(
                context,
                PoseLandmarker.PoseLandmarkerOptions.builder()
                    .setBaseOptions(
                        BaseOptions.builder()
                            .setModelAssetPath(LandmarkerConfig.POSE_TASK)
                            .setDelegate(delegate)
                            .build(),
                    )
                    .setRunningMode(RunningMode.IMAGE)
                    .setNumPoses(LandmarkerConfig.NUM_POSES)
                    .setMinPoseDetectionConfidence(LandmarkerConfig.MIN_POSE_DETECTION_CONFIDENCE)
                    .setMinPosePresenceConfidence(LandmarkerConfig.MIN_POSE_PRESENCE_CONFIDENCE)
                    .setMinTrackingConfidence(LandmarkerConfig.MIN_POSE_TRACKING_CONFIDENCE)
                    .build(),
            )
    }
}

