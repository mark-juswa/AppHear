package com.example.apphear.perceptionvnext

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import java.security.MessageDigest

/** Hash-pinned identity of one recognition-v2 [96,350] -> 236 TFLite package. */
internal data class RecognizerPackageSpec(
    val packageId: String,
    val manifestAsset: String,
    val manifestSha256: String,
    val modelSha256: String,
)

/** Debug-only, fail-closed consumer for the already-authorized Gate-2 recognizer. */
internal class RecognitionV2LiveRecognizer(
    context: Context,
    private val spec: RecognizerPackageSpec = FROZEN_GATE2,
) : AutoCloseable {
    data class Prediction(
        val probabilities: FloatArray,
        val top5: IntArray,
        val invocationMs: Double,
    )

    private val contractBytes = context.assets.open(CONTRACT_ASSET).use { it.readBytes() }
    private val contract = JSONObject(contractBytes.toString(Charsets.UTF_8))
    private val gate2Bytes = context.assets.open(spec.manifestAsset).use { it.readBytes() }
    private val gate2 = JSONObject(gate2Bytes.toString(Charsets.UTF_8))
    val glosses: List<String>
    private val interpreter: Interpreter
    private val featureBuffer = ByteBuffer.allocateDirect(FEATURE_ELEMENTS * 4)
        .order(ByteOrder.nativeOrder())
    private val maskBuffer = ByteBuffer.allocateDirect(RecognitionV2.MAX_SEQUENCE_LENGTH)
        .order(ByteOrder.nativeOrder())
    private val outputBuffer = ByteBuffer.allocateDirect(OUTPUTS * 4).order(ByteOrder.nativeOrder())
    private lateinit var inputs: Array<Any>
    private lateinit var outputs: MutableMap<Int, Any>
    private var featureInput = -1
    private var maskInput = -1
    private var outputIndex = -1

    init {
        require(contract.getString("milestone") == MILESTONE)
        require(contract.getString("raw_schema") == RecognitionV2.RAW_SCHEMA)
        require(contract.getString("feature_schema") == RecognitionV2.FEATURE_SCHEMA)
        require(contract.getJSONArray("feature_shape").ints().contentEquals(intArrayOf(96, 350)))
        require(contract.getJSONArray("mask_shape").ints().contentEquals(intArrayOf(96)))
        require(contract.getInt("output_count") == OUTPUTS)
        require(contract.getJSONObject("tolerances").getDouble("android_vs_python_v2_max_abs") == 1e-5)
        require(contract.getJSONObject("tolerances").getDouble("android_vs_keras_probability_max_abs") == 1e-4)
        require(sha256(gate2Bytes) == spec.manifestSha256) { "GATE4A1_GATE2_MANIFEST_DRIFT" }
        require(gate2.getString("feature_schema") == RecognitionV2.FEATURE_SCHEMA)
        require(gate2.getString("model_sha256") == spec.modelSha256)
        require(gate2.getString("vocabulary_sha256") == VOCAB_SHA)
        val labels = gate2.getJSONArray("class_index_to_gloss")
        require(labels.length() == OUTPUTS)
        glosses = List(OUTPUTS) { labels.getString(it) }
        val modelAsset = gate2.getString("model_asset")
        require(assetSha256(context, modelAsset) == spec.modelSha256) { "GATE4A1_MODEL_DRIFT" }
        val options = Interpreter.Options().setNumThreads(4).setUseXNNPACK(true).setUseNNAPI(false)
        interpreter = Interpreter(mapAsset(context, modelAsset), options).also { it.allocateTensors() }
        inspectIo()
    }

    fun invoke(view: RecognitionV2.TemporalView, featureSchema: String): Prediction {
        require(featureSchema == RecognitionV2.FEATURE_SCHEMA) { "GATE4A1_CONSUMER_SCHEMA_MISMATCH" }
        require(view.features.size == FEATURE_ELEMENTS && view.mask.size == 96)
        featureBuffer.clear()
        featureBuffer.asFloatBuffer().put(view.features)
        featureBuffer.position(0)
        featureBuffer.limit(featureBuffer.capacity())
        maskBuffer.clear()
        view.mask.forEach { maskBuffer.put(if (it) 1 else 0) }
        maskBuffer.flip()
        outputBuffer.clear()
        outputBuffer.asFloatBuffer().put(FloatArray(OUTPUTS))
        outputBuffer.position(0)
        outputBuffer.limit(outputBuffer.capacity())
        inputs[featureInput] = featureBuffer
        inputs[maskInput] = maskBuffer
        val started = System.nanoTime()
        interpreter.runForMultipleInputsOutputs(inputs, outputs)
        val elapsed = (System.nanoTime() - started) / 1_000_000.0
        outputBuffer.position(0)
        val probabilities = FloatArray(OUTPUTS).also { outputBuffer.asFloatBuffer().get(it) }
        require(probabilities.all { it.isFinite() })
        return Prediction(probabilities, topK(probabilities), elapsed)
    }

    fun identityJson(): JSONObject = JSONObject()
        .put("contract_asset", CONTRACT_ASSET)
        .put("contract_sha256", sha256(contractBytes))
        .put("gate2_manifest_sha256", sha256(gate2Bytes))
        .put("model_sha256", spec.modelSha256)
        .put("vocabulary_sha256", VOCAB_SHA)
        .put("feature_schema", RecognitionV2.FEATURE_SCHEMA)
        .put("input_shape", JSONArray(listOf(96, 350)))
        .put("mask_shape", JSONArray(listOf(96)))
        .put("output_count", OUTPUTS)
        .put("runtime", JSONObject().put("precision", "FP32").put("cpu_threads", 4)
            .put("xnnpack", true).put("nnapi", false).put("gpu", false))
        .also { if (spec != FROZEN_GATE2) it.put("package_id", spec.packageId) }

    override fun close() = interpreter.close()

    private fun inspectIo() {
        for (index in 0 until interpreter.inputTensorCount) {
            val tensor = interpreter.getInputTensor(index)
            if (tensor.dataType() == DataType.FLOAT32 && tensor.shape().contentEquals(intArrayOf(1, 96, 350))) featureInput = index
            if (tensor.dataType() == DataType.BOOL && tensor.shape().contentEquals(intArrayOf(1, 96))) maskInput = index
        }
        require(featureInput >= 0 && maskInput >= 0 && interpreter.outputTensorCount == 1)
        outputIndex = 0
        val output = interpreter.getOutputTensor(outputIndex)
        require(output.dataType() == DataType.FLOAT32 && output.shape().contentEquals(intArrayOf(1, OUTPUTS)))
        inputs = Array(interpreter.inputTensorCount) { ByteBuffer.allocateDirect(0) }
        outputs = mutableMapOf(outputIndex to outputBuffer)
    }

    private fun mapAsset(context: Context, asset: String): MappedByteBuffer =
        context.assets.openFd(asset).use { descriptor ->
            FileInputStream(descriptor.fileDescriptor).channel.use { channel ->
                channel.map(FileChannel.MapMode.READ_ONLY, descriptor.startOffset, descriptor.declaredLength)
            }
        }

    private fun assetSha256(context: Context, asset: String) =
        sha256(context.assets.open(asset).use { it.readBytes() })

    private fun topK(values: FloatArray) = values.indices
        .sortedWith(compareByDescending<Int> { values[it] }.thenBy { it }).take(5).toIntArray()

    private fun JSONArray.ints() = IntArray(length()) { getInt(it) }

    companion object {
        const val MILESTONE = "PHASE_4A_GATE_4A1_LIVE_PLUMBING_VALIDATION_01"
        const val CONTRACT_ASSET = "phase4a_gate4a1_live/contract.json"
        const val GATE2_MANIFEST = "phase4a_gate2_recognizer_parity/manifest.json"
        const val MODEL_SHA = "1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c"
        const val VOCAB_SHA = "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b"
        const val GATE2_MANIFEST_SHA = "bfe8bec13a646eb6fa733c3bee6a421a44b5e58ed6dbb0dd59d88804e397d019"
        const val OUTPUTS = 236
        val FROZEN_GATE2 = RecognizerPackageSpec("GATE2_FROZEN", GATE2_MANIFEST, GATE2_MANIFEST_SHA, MODEL_SHA)
        const val FEATURE_ELEMENTS = 96 * 350

        fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
            .digest(bytes).joinToString("") { "%02x".format(it) }
    }
}
