package com.example.apphear.pipeline.recognition

import android.content.Context
import com.example.apphear.pipeline.features.FEATURE_DIM
import org.json.JSONObject

/**
 * The model contract (assets/model_manifest.json) + runtime operating config. The runtime refuses a
 * model whose schema/shape doesn't match what this build expects; a mismatched contract silently
 * corrupts recognition.
 */
data class ModelManifest(
    val schemaVersion: String,
    val timeWindow: Int,
    val featureDim: Int,
    val numClasses: Int,
) {
    fun validateOrThrow() {
        require(schemaVersion == EXPECTED_SCHEMA) {
            "model schema_version $schemaVersion != expected $EXPECTED_SCHEMA"
        }
        require(featureDim == FEATURE_DIM) { "model feature_dim $featureDim != $FEATURE_DIM" }
        require(timeWindow > 0) { "model time_window must be > 0" }
        require(numClasses > 1) { "model num_classes must be > 1" }
    }

    companion object {
        const val EXPECTED_SCHEMA = "3.0"

        fun load(context: Context): ModelManifest {
            val o = JSONObject(
                context.assets.open("model_manifest.json").bufferedReader().use { it.readText() },
            )
            return ModelManifest(
                schemaVersion = o.getString("schema_version"),
                timeWindow = o.getInt("time_window"),
                featureDim = o.getInt("feature_dim"),
                numClasses = o.getInt("num_classes"),
            )
        }
    }
}

/** S7 confirmation operating point (parity-locked with model/config/confirm*.yaml + report). */
data class RecognitionConfig(
    val thetaConf: Double,
    val thetaMargin: Double,
    val kStability: Int,
    val temperature: Double,
    val enableLowFpsConfirmation: Boolean,
    val lowFpsKStability: Int,
    val lowFpsThetaConf: Double,
    val lowFpsThetaMargin: Double,
    val lowFpsMinCommitFrame: Int,
) {
    companion object {
        fun load(context: Context): RecognitionConfig {
            val o = JSONObject(
                context.assets.open("recognition_config.json").bufferedReader().use { it.readText() },
            )
            val low = o.optJSONObject("low_fps_confirmation")
            return RecognitionConfig(
                thetaConf = o.getDouble("theta_conf"),
                thetaMargin = o.getDouble("theta_margin"),
                kStability = o.getInt("k_stability"),
                temperature = o.getDouble("temperature"),
                enableLowFpsConfirmation = low?.optBoolean("enabled", false) ?: false,
                lowFpsKStability = low?.optInt("k_stability", o.getInt("k_stability"))
                    ?: o.getInt("k_stability"),
                lowFpsThetaConf = low?.optDouble("theta_conf", o.getDouble("theta_conf"))
                    ?: o.getDouble("theta_conf"),
                lowFpsThetaMargin = low?.optDouble("theta_margin", o.getDouble("theta_margin"))
                    ?: o.getDouble("theta_margin"),
                lowFpsMinCommitFrame = low?.optInt("min_commit_frame", 0)?.coerceAtLeast(0) ?: 0,
            )
        }
    }
}

/** Runtime-only tuning knobs. These do not change the v3.0 258-feature schema or model artifact. */
data class RuntimeConfig(
    val lowFpsEnterBelow: Double,
    val lowFpsExitAbove: Double,
    val lowFpsConsecutiveFrames: Int,
    val enablePreOnsetBuffer: Boolean,
    val preOnsetFrames: Int,
    val enableLowFpsS5Tuning: Boolean,
    val lowFpsKOn: Int,
    val lowFpsKOff: Int,
    val lowFpsSmoothingWindow: Int,
    val enableRecognitionPoseCadence: Boolean,
    val recognitionPoseEveryN: Int,
) {
    companion object {
        fun defaults(): RuntimeConfig = RuntimeConfig(
            lowFpsEnterBelow = 10.0,
            lowFpsExitAbove = 12.0,
            lowFpsConsecutiveFrames = 20,
            enablePreOnsetBuffer = true,
            preOnsetFrames = 3,
            enableLowFpsS5Tuning = false,
            lowFpsKOn = 3,
            lowFpsKOff = 4,
            lowFpsSmoothingWindow = 5,
            enableRecognitionPoseCadence = false,
            recognitionPoseEveryN = 1,
        )

        fun load(context: Context): RuntimeConfig {
            val o = JSONObject(
                context.assets.open("recognition_config.json").bufferedReader().use { it.readText() },
            )
            val low = o.optJSONObject("low_fps") ?: JSONObject()
            val pre = o.optJSONObject("pre_onset") ?: JSONObject()
            val s5 = o.optJSONObject("low_fps_s5") ?: JSONObject()
            val pose = o.optJSONObject("pose_cadence_experiment") ?: JSONObject()
            return RuntimeConfig(
                lowFpsEnterBelow = low.optDouble("enter_below_fps", 10.0),
                lowFpsExitAbove = low.optDouble("exit_above_fps", 12.0),
                lowFpsConsecutiveFrames = low.optInt("consecutive_frames", 20),
                enablePreOnsetBuffer = pre.optBoolean("enabled", true),
                preOnsetFrames = pre.optInt("frames", 3).coerceAtLeast(0),
                enableLowFpsS5Tuning = s5.optBoolean("enabled", false),
                lowFpsKOn = s5.optInt("k_on", 3).coerceAtLeast(1),
                lowFpsKOff = s5.optInt("k_off", 4).coerceAtLeast(1),
                lowFpsSmoothingWindow = s5.optInt("smoothing_window", 5).coerceAtLeast(1),
                enableRecognitionPoseCadence = pose.optBoolean("enabled", false),
                recognitionPoseEveryN = pose.optInt("pose_every_n", 1).coerceAtLeast(1),
            )
        }
    }
}

