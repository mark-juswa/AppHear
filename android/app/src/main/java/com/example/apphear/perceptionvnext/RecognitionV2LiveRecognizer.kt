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

/**
 * Debug-only, fail-closed consumer for the already-authorized Gate-2 recognizer.
 *
 * A package manifest may also declare a `short_model` (same weights, fewer input rows, e.g. WORD_V4's
 * 32-row model). It is used only when every valid mask entry sits in its first rows, where its output
 * equals the 96-row model's (padded rows are masked out; host parity in the manifest). Its hash is
 * pinned through the manifest hash. Packages without one behave exactly as before.
 */
internal class RecognitionV2LiveRecognizer(
    context: Context,
    private val spec: RecognizerPackageSpec = FROZEN_GATE2,
) : AutoCloseable {
    data class Prediction(
        val probabilities: FloatArray,
        val top5: IntArray,
        val invocationMs: Double,
        /** Input rows of the model that ran: 96, or the short model's rows. */
        val modelRows: Int = RecognitionV2.MAX_SEQUENCE_LENGTH,
    )

    private class ShortModel(val rows: Int, val sha256: String, val interpreter: Interpreter) {
        val features: ByteBuffer = ByteBuffer.allocateDirect(rows * 350 * 4).order(ByteOrder.nativeOrder())
        val mask: ByteBuffer = ByteBuffer.allocateDirect(rows).order(ByteOrder.nativeOrder())
        var featureInput = -1
        var maskInput = -1
        lateinit var inputs: Array<Any>
    }

    private val contractBytes = context.assets.open(CONTRACT_ASSET).use { it.readBytes() }
    private val contract = JSONObject(contractBytes.toString(Charsets.UTF_8))
    private val gate2Bytes = context.assets.open(spec.manifestAsset).use { it.readBytes() }
    private val gate2 = JSONObject(gate2Bytes.toString(Charsets.UTF_8))
    val glosses: List<String>
    private val modelAsset: String
    private val appContext = context.applicationContext
    private var fullInterpreter: Interpreter? = null
    private val shortModel: ShortModel?
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
        modelAsset = gate2.getString("model_asset")
        require(assetSha256(context, modelAsset) == spec.modelSha256) { "GATE4A1_MODEL_DRIFT" }
        shortModel = gate2.optJSONObject("short_model")?.let { loadShort(context, it) }
        // With a short model the 96-row model is only needed for long windows: load it on first use.
        if (shortModel == null) full()
    }

    private fun options() = Interpreter.Options().setNumThreads(4).setUseXNNPACK(true).setUseNNAPI(false)

    private fun full(): Interpreter = fullInterpreter ?: Interpreter(mapAsset(appContext, modelAsset), options())
        .also {
            it.allocateTensors()
            fullInterpreter = it
            inspectIo(it)
        }

    private fun loadShort(context: Context, json: JSONObject): ShortModel {
        val rows = json.getInt("rows")
        require(rows in 1 until RecognitionV2.MAX_SEQUENCE_LENGTH) { "SHORT_MODEL_ROWS" }
        val asset = json.getString("model_asset")
        val sha = json.getString("model_sha256")
        require(assetSha256(context, asset) == sha) { "SHORT_MODEL_DRIFT" }
        val model = ShortModel(rows, sha, Interpreter(mapAsset(context, asset), options()).also { it.allocateTensors() })
        val interpreter = model.interpreter
        for (index in 0 until interpreter.inputTensorCount) {
            val tensor = interpreter.getInputTensor(index)
            if (tensor.dataType() == DataType.FLOAT32 && tensor.shape().contentEquals(intArrayOf(1, rows, 350))) model.featureInput = index
            if (tensor.dataType() == DataType.BOOL && tensor.shape().contentEquals(intArrayOf(1, rows))) model.maskInput = index
        }
        require(model.featureInput >= 0 && model.maskInput >= 0 && interpreter.outputTensorCount == 1)
        val output = interpreter.getOutputTensor(0)
        require(output.dataType() == DataType.FLOAT32 && output.shape().contentEquals(intArrayOf(1, OUTPUTS)))
        model.inputs = Array(interpreter.inputTensorCount) { ByteBuffer.allocateDirect(0) }
        return model
    }

    /** Rows needed by this view if its valid entries are a prefix of the mask, else null. */
    private fun prefixLength(mask: BooleanArray): Int? {
        val n = mask.count { it }
        return if ((0 until n).all { mask[it] }) n else null
    }

    fun invoke(view: RecognitionV2.TemporalView, featureSchema: String): Prediction {
        require(featureSchema == RecognitionV2.FEATURE_SCHEMA) { "GATE4A1_CONSUMER_SCHEMA_MISMATCH" }
        require(view.features.size == FEATURE_ELEMENTS && view.mask.size == 96)
        val short = shortModel
        val valid = prefixLength(view.mask)
        if (short != null && valid != null && valid <= short.rows) return invokeShort(short, view)
        val interpreter = full()
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

    private fun invokeShort(short: ShortModel, view: RecognitionV2.TemporalView): Prediction {
        short.features.clear()
        short.features.asFloatBuffer().put(view.features, 0, short.rows * 350)
        short.features.position(0)
        short.features.limit(short.features.capacity())
        short.mask.clear()
        for (i in 0 until short.rows) short.mask.put(if (view.mask[i]) 1 else 0)
        short.mask.flip()
        outputBuffer.clear()
        outputBuffer.asFloatBuffer().put(FloatArray(OUTPUTS))
        outputBuffer.position(0)
        outputBuffer.limit(outputBuffer.capacity())
        short.inputs[short.featureInput] = short.features
        short.inputs[short.maskInput] = short.mask
        val started = System.nanoTime()
        short.interpreter.runForMultipleInputsOutputs(short.inputs, mutableMapOf<Int, Any>(0 to outputBuffer))
        val elapsed = (System.nanoTime() - started) / 1_000_000.0
        outputBuffer.position(0)
        val probabilities = FloatArray(OUTPUTS).also { outputBuffer.asFloatBuffer().get(it) }
        require(probabilities.all { it.isFinite() })
        return Prediction(probabilities, topK(probabilities), elapsed, short.rows)
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
        .also { json -> shortModel?.let { json.put("short_model_sha256", it.sha256).put("short_model_rows", it.rows) } }

    override fun close() {
        fullInterpreter?.close()
        shortModel?.interpreter?.close()
    }

    private fun inspectIo(interpreter: Interpreter) {
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
