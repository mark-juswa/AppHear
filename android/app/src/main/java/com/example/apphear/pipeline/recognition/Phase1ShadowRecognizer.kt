package com.example.apphear.pipeline.recognition

import android.content.Context
import com.example.apphear.BuildConfig
import com.example.apphear.pipeline.RuntimeLog
import com.example.apphear.pipeline.features.FEATURE_DIM
import org.json.JSONObject
import org.tensorflow.lite.Interpreter
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import java.security.MessageDigest
import kotlin.system.measureNanoTime

private const val SHADOW_TAG = "AppHearShadow"

data class Phase1ShadowConfig(
    val enabled: Boolean,
    val logEveryNFrames: Int,
) {
    companion object {
        fun load(context: Context): Phase1ShadowConfig {
            val root = JSONObject(
                context.assets.open("recognition_config.json").bufferedReader().use { it.readText() },
            )
            val shadow = root.optJSONObject("phase1_shadow") ?: JSONObject()
            return Phase1ShadowConfig(
                enabled = shadow.optBoolean("enabled", false) || BuildConfig.PHASE1_SHADOW_ENABLED,
                logEveryNFrames = shadow.optInt("log_every_n_frames", 5).coerceAtLeast(1),
            )
        }
    }
}

internal fun meanPosteriors(posteriors: List<FloatArray>): FloatArray {
    require(posteriors.isNotEmpty()) { "shadow ensemble requires at least one posterior" }
    val size = posteriors.first().size
    require(posteriors.all { it.size == size }) { "shadow posterior sizes differ" }
    return FloatArray(size) { classId ->
        posteriors.sumOf { it[classId].toDouble() }.div(posteriors.size).toFloat()
    }
}

internal fun posteriorTop1(posterior: FloatArray): Int {
    require(posterior.isNotEmpty()) { "posterior is empty" }
    var best = 0
    for (index in 1 until posterior.size) {
        if (posterior[index] > posterior[best]) best = index
    }
    return best
}

/**
 * Default-off Phase 1 evaluator. It can only log predictions and timing; it has no access to
 * confirmation, sentence state, or UI state and therefore cannot commit a word.
 */
class Phase1ShadowRecognizer private constructor(
    private val interpreters: List<Interpreter>,
    private val config: Phase1ShadowConfig,
    private val timeWindow: Int,
    private val numClasses: Int,
) {
    private val input = Array(1) { Array(timeWindow) { FloatArray(FEATURE_DIM) } }
    private val output = Array(1) { Array(timeWindow) { FloatArray(numClasses) } }
    private var observedFrames = 0L

    fun evaluateAndLog(
        window: Array<FloatArray>,
        index: Int,
        activePosterior: FloatArray,
        vocab: Vocab,
        sourceFrame: Long,
    ) {
        observedFrames++
        val seedPosteriors = ArrayList<FloatArray>(interpreters.size)
        val elapsedNs = measureNanoTime {
            for (t in 0 until timeWindow) {
                System.arraycopy(window[t], 0, input[0][t], 0, FEATURE_DIM)
            }
            for (interpreter in interpreters) {
                interpreter.run(input, output)
                seedPosteriors.add(output[0][index].copyOf())
            }
        }
        if (observedFrames % config.logEveryNFrames != 0L) return

        val candidate = meanPosteriors(seedPosteriors)
        val activeTop1 = posteriorTop1(activePosterior)
        val candidateTop1 = posteriorTop1(candidate)
        val message = (
            "frame=$sourceFrame observed=$observedFrames active=$activeTop1:${vocab.gloss(activeTop1)} " +
                "active_p=%.4f shadow=$candidateTop1:${vocab.gloss(candidateTop1)} shadow_p=%.4f " +
                "agree=${activeTop1 == candidateTop1} ensemble_ms=%.3f may_commit=false"
            ).format(
            activePosterior[activeTop1],
            candidate[candidateTop1],
            elapsedNs / 1_000_000.0,
        )
        RuntimeLog.i(
            SHADOW_TAG,
            message,
        )
    }

    fun close() = interpreters.forEach { it.close() }

    companion object {
        private const val MANIFEST_ASSET = "phase1_shadow_manifest.json"

        fun loadIfEnabled(context: Context): Phase1ShadowRecognizer? {
            val config = Phase1ShadowConfig.load(context)
            if (!config.enabled) {
                RuntimeLog.i(SHADOW_TAG, "disabled; production recognizer unchanged")
                return null
            }
            val manifestText = context.assets.open(MANIFEST_ASSET).bufferedReader().use { it.readText() }
            val manifest = JSONObject(manifestText)
            require(manifest.getBoolean("shadow_only")) { "shadow manifest is not shadow-only" }
            require(!manifest.getBoolean("may_commit")) { "shadow manifest permits commits" }
            require(!manifest.getBoolean("may_update_sentence_or_ui")) {
                "shadow manifest permits sentence/UI updates"
            }
            require(manifest.getBoolean("passed")) { "shadow manifest parity gate did not pass" }
            require(manifest.getString("schema_version") == ModelManifest.EXPECTED_SCHEMA) {
                "shadow schema mismatch"
            }
            val timeWindow = manifest.getInt("time_window")
            val featureDim = manifest.getInt("feature_dim")
            val numClasses = manifest.getInt("num_classes")
            require(timeWindow == 96 && featureDim == FEATURE_DIM && numClasses == 236) {
                "shadow tensor contract mismatch"
            }
            require(manifest.getString("vocab_sha256") == assetSha256(context, "vocab.json")) {
                "shadow/active vocabulary mismatch"
            }

            val models = manifest.getJSONArray("models")
            require(models.length() == 3) { "shadow ensemble must contain three models" }
            val interpreters = ArrayList<Interpreter>(models.length())
            try {
                for (index in 0 until models.length()) {
                    val model = models.getJSONObject(index)
                    val name = model.getString("asset_name")
                    require(model.getString("tflite_sha256") == assetSha256(context, name)) {
                        "shadow model hash mismatch: $name"
                    }
                    val options = Interpreter.Options().apply { numThreads = 2 }
                    val interpreter = Interpreter(mapModel(context, name), options)
                    interpreter.resizeInput(0, intArrayOf(1, timeWindow, featureDim))
                    interpreter.allocateTensors()
                    interpreters.add(interpreter)
                }
                RuntimeLog.i(
                    SHADOW_TAG,
                    "loaded models=${interpreters.size} quantization=${manifest.getString("quantization")} " +
                        "window=$timeWindow classes=$numClasses may_commit=false",
                )
                return Phase1ShadowRecognizer(interpreters, config, timeWindow, numClasses)
            } catch (error: Throwable) {
                interpreters.forEach { it.close() }
                throw error
            }
        }

        private fun assetSha256(context: Context, name: String): String {
            val digest = MessageDigest.getInstance("SHA-256")
            context.assets.open(name).use { stream ->
                val buffer = ByteArray(1024 * 1024)
                while (true) {
                    val read = stream.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                }
            }
            return digest.digest().joinToString("") { "%02X".format(it) }
        }

        private fun mapModel(context: Context, name: String): MappedByteBuffer {
            context.assets.openFd(name).use { fd ->
                fd.createInputStream().channel.use { channel ->
                    return channel.map(FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
                }
            }
        }
    }
}
