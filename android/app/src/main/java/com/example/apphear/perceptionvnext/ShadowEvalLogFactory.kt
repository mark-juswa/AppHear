package com.example.apphear.perceptionvnext

import android.content.Context
import android.os.Build
import com.example.apphear.BuildConfig
import java.io.File
import java.security.SecureRandom

/**
 * Android wiring for [ShadowEvalLog]; only ever called when `BuildConfig.SHADOW_EVAL_ENABLED` (a `-PshadowEval=true`
 * debug build). Files live in `noBackupFilesDir`, so Android backup / device transfer never copies them.
 * Returns null (recognition continues unchanged) if anything about setup fails.
 */
internal fun createShadowEvalLog(
    context: Context,
    configuration: PhoneRecognitionConfiguration,
    packageId: PhoneS2Package,
): ShadowEvalLog? = try {
    val dir = File(context.noBackupFilesDir, "shadow_eval")
    dir.mkdirs()
    val bytes = ByteArray(8).also { SecureRandom().nextBytes(it) }
    val sid = bytes.joinToString("") { "%02x".format(it) } // random per session; no user or device identifier
    val labelFile = File(dir, "run_label.txt")
    ShadowEvalLog(
        sink = RotatingFileShadowSink(dir, sid),
        sessionId = sid,
        // Re-read at every camera generation so the coordinator can relabel a run without rebuilding the app.
        runLabelProvider = { runCatching { if (labelFile.length() in 1..256) labelFile.readText() else "" }.getOrDefault("") },
        sessionMeta = mapOf(
            "app_version" to BuildConfig.VERSION_NAME,
            "sdk_int" to Build.VERSION.SDK_INT.toString(),
            "device_model" to Build.MODEL.take(40),
            "configuration" to configuration.name,
            "s2_package" to packageId.name,
            "gate_enabled" to BuildConfig.WORD_COMMIT_GATE_ENABLED.toString(),
        ),
    )
} catch (_: Throwable) {
    null
}
