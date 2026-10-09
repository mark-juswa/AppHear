package com.example.apphear.perceptionvnext

import android.content.Context
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import java.security.MessageDigest
import kotlin.math.exp

internal enum class PhoneS2Package(
    val assetRoot: String,
    val modelAsset: String,
    val normalizationAsset: String,
    val checkpointSha256: String,
    val normalizationSha256: String,
) {
    PHASE7_CONTROL(
        "phone_causal_recognition_01",
        "s2_phase7_fp32.tflite",
        "cadence_aligned_normalization_stats.json",
        "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73",
        "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130",
    ),
    S2_R2_CANDIDATE(
        "phone_causal_recognition_01/s2_r2_candidate",
        "s2_r2_fp32.tflite",
        "normalization.json",
        "b6f8b52cece72f0b6f5b802a4ea583060d923e90a6b951059e7013114c8fc151",
        "65d885f62eaca6f11a596302d304f63149795ddaf01e702f1e6a36dd7da5c005",
    );

    val contractPath: String get() = "$assetRoot/contract.json"
    val modelPath: String get() = "$assetRoot/$modelAsset"
    val normalizationPath: String get() = "$assetRoot/$normalizationAsset"
}

/** Versioned S2 package consumer using only a bounded causal feature prefix. */
internal class PhoneS2Runner(
    context: Context,
    private val packageId: PhoneS2Package = PhoneS2Package.PHASE7_CONTROL,
) : AutoCloseable {
    data class Prediction(
        val probabilities: FloatArray,
        val argmaxState: Int,
        val invocationMs: Double,
        val historyLength: Int,
        val normalizedInputDiagnostic: FloatArray? = null,
    )

    private val contractBytes = context.assets.open(packageId.contractPath).use { it.readBytes() }
    private val contract = JSONObject(contractBytes.toString(Charsets.UTF_8))
    private val normalizationBytes = context.assets.open(packageId.normalizationPath).use { it.readBytes() }
    private val normalization = JSONObject(normalizationBytes.toString(Charsets.UTF_8))
    private val mean = normalization.getJSONArray("mean").toFloatArray()
    private val std = normalization.getJSONArray("std").toFloatArray()
    private val history = ArrayDeque<FloatArray>()
    private val interpreter: Interpreter
    private var allocatedLength = -1

    init {
        require(contract.getString("schema") == CONTRACT_SCHEMA)
        require(contract.getString("feature_schema") == PhoneSegmentationFeatureBuilder.SCHEMA)
        require(contract.getInt("feature_width") == PhoneSegmentationFeatureBuilder.FEATURE_WIDTH)
        require(contract.getString("source_checkpoint_sha256") == packageId.checkpointSha256)
        require(contract.getString("source_normalization_sha256") == packageId.normalizationSha256)
        if (packageId == PhoneS2Package.S2_R2_CANDIDATE) {
            require(contract.getString("package_id") == packageId.name)
        }
        val states = contract.getJSONArray("state_order")
        require(states.length() == 3 && states.getString(0) == "PRE_IDLE" &&
            states.getString(1) == "ACTIVE_SIGN" && states.getString(2) == "POST_RECOVERY")
        require(contract.getInt("receptive_field_observations") == RECEPTIVE_FIELD)
        require(contract.getBoolean("training_executed").not())
        require(sha256(normalizationBytes) == contract.getString("normalization_asset_sha256"))
        require(normalization.getString("feature_schema") == PhoneSegmentationFeatureBuilder.SCHEMA)
        require(normalization.getString("source_sha256") == packageId.normalizationSha256)
        require(mean.size == FEATURE_WIDTH && std.size == FEATURE_WIDTH)
        require(std.all { it.isFinite() && it > 0f })
        require(assetSha256(context, packageId.modelPath) == contract.getString("tflite_sha256"))
        val options = Interpreter.Options().setNumThreads(4).setUseXNNPACK(true).setUseNNAPI(false)
        interpreter = Interpreter(mapAsset(context, packageId.modelPath), options)
        verifyTensorContract()
    }

    fun predict(features: FloatArray, retainNormalizedInputDiagnostic: Boolean = false): Prediction {
        require(features.size == FEATURE_WIDTH && features.all { it.isFinite() })
        val normalized = FloatArray(FEATURE_WIDTH) { (features[it] - mean[it]) / std[it] }
        require(normalized.all { it.isFinite() })
        return predictNormalized(normalized, retainNormalizedInputDiagnostic)
    }

    /** Instrumentation-only entrypoint for the frozen already-normalized CAL fixture. */
    internal fun predictNormalizedFixture(normalized: FloatArray): Prediction {
        require(normalized.size == FEATURE_WIDTH && normalized.all { it.isFinite() })
        return predictNormalized(normalized, false)
    }

    private fun predictNormalized(normalized: FloatArray, retainNormalizedInputDiagnostic: Boolean): Prediction {
        history.addLast(normalized)
        while (history.size > RECEPTIVE_FIELD) history.removeFirst()
        val length = history.size
        if (allocatedLength != length) {
            interpreter.resizeInput(0, intArrayOf(1, length, FEATURE_WIDTH), false)
            interpreter.allocateTensors()
            allocatedLength = length
            verifyAllocatedTensorContract(length)
        }
        val input = Array(1) { Array(length) { FloatArray(FEATURE_WIDTH) } }
        history.forEachIndexed { index, row -> row.copyInto(input[0][index]) }
        val output = Array(1) { FloatArray(STATE_COUNT) }
        val started = System.nanoTime()
        interpreter.run(input, output)
        val elapsedMs = (System.nanoTime() - started) / 1_000_000.0
        val probabilities = softmax(output[0])
        val argmax = probabilities.indices.maxWith(compareBy<Int> { probabilities[it] }.thenBy { -it })
        return Prediction(
            probabilities,
            argmax,
            elapsedMs,
            length,
            if (retainNormalizedInputDiagnostic) normalized.copyOf() else null,
        )
    }

    fun reset() {
        history.clear()
        allocatedLength = -1
    }

    fun identityJson() = JSONObject()
        .put("package_id", packageId.name)
        .put("contract_sha256", sha256(contractBytes))
        .put("source_checkpoint_sha256", packageId.checkpointSha256)
        .put("source_normalization_sha256", packageId.normalizationSha256)
        .put("tflite_sha256", contract.getString("tflite_sha256"))
        .put("feature_schema", PhoneSegmentationFeatureBuilder.SCHEMA)
        .put("feature_width", FEATURE_WIDTH)
        .put("receptive_field_observations", RECEPTIVE_FIELD)
        .put("runtime_precision", "FP32")
        .put("training_executed", false)

    override fun close() = interpreter.close()

    private fun verifyTensorContract() {
        require(interpreter.inputTensorCount == 1 && interpreter.outputTensorCount == 1)
        val input = interpreter.getInputTensor(0)
        val output = interpreter.getOutputTensor(0)
        require(input.dataType() == DataType.FLOAT32)
        require(output.dataType() == DataType.FLOAT32)
        require(input.shapeSignature().contentEquals(intArrayOf(-1, -1, FEATURE_WIDTH)) ||
            input.shapeSignature().contentEquals(intArrayOf(1, -1, FEATURE_WIDTH)))
        require(output.shapeSignature().contentEquals(intArrayOf(-1, STATE_COUNT)) ||
            output.shapeSignature().contentEquals(intArrayOf(1, STATE_COUNT)))
    }

    private fun verifyAllocatedTensorContract(length: Int) {
        require(interpreter.getInputTensor(0).shape().contentEquals(intArrayOf(1, length, FEATURE_WIDTH)))
        require(interpreter.getOutputTensor(0).shape().contentEquals(intArrayOf(1, STATE_COUNT)))
    }

    private fun softmax(logits: FloatArray): FloatArray {
        val maximum = logits.max()
        val values = FloatArray(logits.size) { exp((logits[it] - maximum).toDouble()).toFloat() }
        val total = values.sum()
        return FloatArray(values.size) { values[it] / total }
    }

    private fun mapAsset(context: Context, asset: String): MappedByteBuffer =
        context.assets.openFd(asset).use { descriptor ->
            FileInputStream(descriptor.fileDescriptor).channel.use { channel ->
                channel.map(FileChannel.MapMode.READ_ONLY, descriptor.startOffset, descriptor.declaredLength)
            }
        }

    private fun assetSha256(context: Context, asset: String) =
        sha256(context.assets.open(asset).use { it.readBytes() })

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }

    private fun org.json.JSONArray.toFloatArray() = FloatArray(length()) { getDouble(it).toFloat() }

    companion object {
        const val CONTRACT_SCHEMA = "apphear.phone_causal_recognition.s2_mobile_contract.v1"
        const val ASSET_ROOT = "phone_causal_recognition_01"
        const val CONTRACT_ASSET = "$ASSET_ROOT/contract.json"
        const val MODEL_ASSET = "$ASSET_ROOT/s2_phase7_fp32.tflite"
        const val NORMALIZATION_ASSET = "$ASSET_ROOT/cadence_aligned_normalization_stats.json"
        const val SOURCE_CHECKPOINT_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
        const val SOURCE_NORMALIZATION_SHA = "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe73ed494e9130"
        const val FEATURE_WIDTH = 378
        const val STATE_COUNT = 3
        const val RECEPTIVE_FIELD = 61
    }
}
