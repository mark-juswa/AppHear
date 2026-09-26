package com.example.apphear.perceptionvnext

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.TensorFlowLite
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import java.security.MessageDigest
import kotlin.math.abs

/** Gate-2 verifier for the frozen ordinary V2 TCN. It never invokes CameraX or Candidate 01. */
object RecognitionV2TfliteParityVerifier {
    private const val MANIFEST = "phase4a_gate2_recognizer_parity/manifest.json"
    private const val MILESTONE = "PHASE_4A_GATE_2_RECOGNIZER_RUNTIME_PARITY_01"
    private const val FEATURES = 96 * 350
    private const val OUTPUTS = 236

    private data class ErrorStats(
        val values: MutableList<Double> = ArrayList(),
        var max: Double = 0.0,
        var worstFixture: String = "",
        var worstCondition: String = "",
        var worstClass: Int = -1,
        var reference: Double = 0.0,
        var actual: Double = 0.0,
    ) {
        fun add(
            value: Double,
            fixture: String,
            condition: String,
            outputClass: Int,
            expected: Double,
            observed: Double,
        ) {
            values.add(value)
            if (value > max) {
                max = value
                worstFixture = fixture
                worstCondition = condition
                worstClass = outputClass
                reference = expected
                actual = observed
            }
        }

        fun json(glosses: JSONArray): JSONObject {
            val sorted = values.sorted()
            val p95 = if (sorted.isEmpty()) 0.0 else sorted[((sorted.size - 1) * 0.95).toInt()]
            return JSONObject()
                .put("count", values.size)
                .put("max_abs", max)
                .put("p95_abs", p95)
                .put("mean_abs", if (values.isEmpty()) 0.0 else values.sum() / values.size)
                .put("worst_fixture", worstFixture)
                .put("worst_condition", worstCondition)
                .put("worst_output_index", worstClass)
                .put("worst_gloss", if (worstClass >= 0) glosses.getString(worstClass) else "")
                .put("reference_value", reference)
                .put("tflite_value", actual)
        }
    }

    private data class RuntimeIo(
        val featureInput: Int,
        val maskInput: Int,
        val output: Int,
        val inputContract: JSONArray,
        val outputContract: JSONArray,
    )

    fun verify(context: Context): JSONObject {
        val manifestBytes = context.assets.open(MANIFEST).use { it.readBytes() }
        val manifest = JSONObject(manifestBytes.toString(Charsets.UTF_8))
        require(manifest.getString("milestone") == MILESTONE)
        require(manifest.getString("feature_schema") == RecognitionV2.FEATURE_SCHEMA)
        require(manifest.getString("source_checkpoint_sha256") ==
            "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340")
        require(manifest.getString("vocabulary_sha256") ==
            "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b")
        require(manifest.getJSONArray("class_index_to_gloss").length() == OUTPUTS)
        require(manifest.getJSONArray("input_shape").intArray().contentEquals(intArrayOf(1, 96, 350)))
        require(manifest.getJSONArray("mask_shape").intArray().contentEquals(intArrayOf(1, 96)))
        require(manifest.getJSONArray("output_shape").intArray().contentEquals(intArrayOf(1, OUTPUTS)))
        require(manifest.getString("output_semantics") == "probabilities_softmax")
        require(!manifest.getBoolean("dev_accessed"))
        require(!manifest.getBoolean("protected_test_accessed"))

        val runtime = manifest.getJSONObject("runtime")
        val threads = runtime.getInt("cpu_threads")
        require(threads == 4)
        require(runtime.getBoolean("xnnpack_requested"))
        require(!runtime.getBoolean("nnapi"))
        require(!runtime.getBoolean("gpu"))
        val modelAsset = manifest.getString("model_asset")
        val expectedModelSha = manifest.getString("model_sha256")
        val actualModelSha = assetSha256(context, modelAsset)
        require(actualModelSha == expectedModelSha) { "GATE2_MODEL_HASH_MISMATCH" }

        val options = Interpreter.Options()
            .setNumThreads(threads)
            .setUseXNNPACK(true)
            .setUseNNAPI(false)
        val interpreter = Interpreter(mapAsset(context, modelAsset), options)
        try {
            interpreter.allocateTensors()
            val io = inspectIo(interpreter)
            val tolerance = manifest.getJSONObject("tolerances")
                .getDouble("keras_vs_android_tflite_max_abs")
            val maskTolerance = manifest.getJSONObject("tolerances")
                .getDouble("mask_padding_invariance_max_abs")
            require(tolerance == 1e-4)
            require(maskTolerance == 1e-6)

            val glosses = manifest.getJSONArray("class_index_to_gloss")
            val errors = ErrorStats()
            var top1Mismatches = 0
            var top5MembershipMismatches = 0
            var top5OrderMismatches = 0
            val fullOutputs = JSONArray()
            val perView = JSONArray()
            val views = manifest.getJSONArray("views")
            for (index in 0 until views.length()) {
                val item = views.getJSONObject(index)
                val fixture = item.getString("fixture_id")
                val condition = item.getString("condition")
                val features = readVerifiedFloats(
                    context,
                    item.getString("feature_asset"),
                    item.getString("feature_sha256"),
                )
                require(features.size == FEATURES)
                val mask = item.getJSONArray("mask").booleanArray()
                require(mask.size == 96)
                val expected = readVerifiedFloats(
                    context,
                    item.getString("keras_output_asset"),
                    item.getString("keras_output_sha256"),
                )
                require(expected.size == OUTPUTS)
                val actual = invoke(interpreter, io, features, mask)
                val local = ErrorStats()
                for (outputClass in 0 until OUTPUTS) {
                    val difference = abs(expected[outputClass] - actual[outputClass]).toDouble()
                    require(actual[outputClass].isFinite())
                    errors.add(
                        difference, fixture, condition, outputClass,
                        expected[outputClass].toDouble(), actual[outputClass].toDouble(),
                    )
                    local.add(
                        difference, fixture, condition, outputClass,
                        expected[outputClass].toDouble(), actual[outputClass].toDouble(),
                    )
                }
                val expectedTop = topK(expected)
                val actualTop = topK(actual)
                if (expectedTop[0] != actualTop[0]) top1Mismatches++
                if (expectedTop.toSet() != actualTop.toSet()) top5MembershipMismatches++
                if (!expectedTop.contentEquals(actualTop)) top5OrderMismatches++
                perView.put(
                    local.json(glosses)
                        .put("fixture_id", fixture)
                        .put("sample_id", item.getString("sample_id"))
                        .put("condition", condition)
                        .put("keras_top5_indices", JSONArray(expectedTop.toList()))
                        .put("android_top5_indices", JSONArray(actualTop.toList()))
                        .put("keras_top5_glosses", glossArray(glosses, expectedTop))
                        .put("android_top5_glosses", glossArray(glosses, actualTop))
                        .put("top1_match", expectedTop[0] == actualTop[0])
                        .put("top5_membership_match", expectedTop.toSet() == actualTop.toSet())
                        .put("top5_order_match", expectedTop.contentEquals(actualTop)),
                )
                fullOutputs.put(
                    JSONObject()
                        .put("fixture_id", fixture)
                        .put("condition", condition)
                        .put("android_tflite_output", JSONArray(actual.toList())),
                )
            }

            val maskResults = JSONArray()
            var maskFailures = 0
            val maskViews = manifest.getJSONArray("mask_padding_views")
            for (index in 0 until maskViews.length()) {
                val item = maskViews.getJSONObject(index)
                val mask = item.getJSONArray("mask").booleanArray()
                require(mask.any { !it })
                val baseline = readVerifiedFloats(
                    context,
                    item.getString("feature_asset"),
                    item.getString("feature_sha256"),
                )
                val garbage = readVerifiedFloats(
                    context,
                    item.getString("garbage_feature_asset"),
                    item.getString("garbage_feature_sha256"),
                )
                for (row in mask.indices) if (mask[row]) {
                    val start = row * 350
                    require((start until start + 350).all { baseline[it] == garbage[it] })
                }
                val baselineOutput = invoke(interpreter, io, baseline, mask)
                val garbageOutput = invoke(interpreter, io, garbage, mask)
                val differences = DoubleArray(OUTPUTS) {
                    abs(baselineOutput[it] - garbageOutput[it]).toDouble()
                }
                val maximum = differences.maxOrNull() ?: 0.0
                val pass = maximum <= maskTolerance &&
                    topK(baselineOutput).contentEquals(topK(garbageOutput))
                if (!pass) maskFailures++
                maskResults.put(
                    JSONObject()
                        .put("fixture_id", item.getString("fixture_id"))
                        .put("condition", item.getString("condition"))
                        .put("padded_rows", mask.count { !it })
                        .put("max_abs", maximum)
                        .put("p95_abs", percentile(differences, 0.95))
                        .put("mean_abs", differences.average())
                        .put("top5_order_unchanged", topK(baselineOutput).contentEquals(topK(garbageOutput)))
                        .put("pass", pass),
                )
            }

            // The first full-length fixture is fixed by the frozen manifest order for latency.
            val latencyView = (0 until views.length())
                .map { views.getJSONObject(it) }
                .first { it.getInt("real_length") == 96 }
            val latencyFeatures = readVerifiedFloats(
                context,
                latencyView.getString("feature_asset"),
                latencyView.getString("feature_sha256"),
            )
            val latencyMask = latencyView.getJSONArray("mask").booleanArray()
            val warmups = runtime.getInt("warmup_iterations")
            val measurements = runtime.getInt("measured_iterations")
            repeat(warmups) { invoke(interpreter, io, latencyFeatures, latencyMask) }
            val latencyMs = DoubleArray(measurements)
            repeat(measurements) { iteration ->
                val start = System.nanoTime()
                invoke(interpreter, io, latencyFeatures, latencyMask)
                latencyMs[iteration] = (System.nanoTime() - start) / 1_000_000.0
            }

            val numericalPass = errors.max <= tolerance && top1Mismatches == 0 &&
                top5MembershipMismatches == 0
            val pass = numericalPass && maskFailures == 0
            val result = JSONObject()
                .put("milestone", MILESTONE)
                .put("status", if (pass) "PASS" else "FAIL")
                .put("device_manufacturer", android.os.Build.MANUFACTURER)
                .put("device_model", android.os.Build.MODEL)
                .put("android_version", android.os.Build.VERSION.RELEASE)
                .put("tflite_runtime_version", TensorFlowLite.runtimeVersion())
                .put("runtime_configuration", JSONObject()
                    .put("precision", "FP32")
                    .put("cpu_threads", threads)
                    .put("xnnpack_requested", true)
                    .put("nnapi", false)
                    .put("gpu", false)
                    .put("input_allocation", "direct native-order ByteBuffer; reused contract")
                    .put("output_allocation", "direct native-order ByteBuffer per invocation"))
                .put("model_sha256", actualModelSha)
                .put("model_bytes", context.assets.openFd(modelAsset).length)
                .put("input_contract", io.inputContract)
                .put("output_contract", io.outputContract)
                .put("views", views.length())
                .put("dense_views", (0 until views.length()).count {
                    views.getJSONObject(it).getString("condition") == "dense"
                })
                .put("sparse_views", (0 until views.length()).count {
                    views.getJSONObject(it).getString("condition") == "phone_01_sparse"
                })
                .put("preregistered_max_abs_tolerance", tolerance)
                .put("parity", errors.json(glosses))
                .put("top1_mismatches", top1Mismatches)
                .put("top5_membership_mismatches", top5MembershipMismatches)
                .put("top5_order_mismatches", top5OrderMismatches)
                .put("per_view", perView)
                .put("full_output_vectors", fullOutputs)
                .put("mask_padding_invariance", JSONObject()
                    .put("status", if (maskFailures == 0) "PASS" else "FAIL")
                    .put("preregistered_max_abs_tolerance", maskTolerance)
                    .put("views", maskResults))
                .put("latency", JSONObject()
                    .put("fixture_id", latencyView.getString("fixture_id"))
                    .put("condition", latencyView.getString("condition"))
                    .put("scope", "Interpreter.runForMultipleInputsOutputs only")
                    .put("warmups", warmups)
                    .put("measurements", measurements)
                    .put("p50_ms", percentile(latencyMs, 0.50))
                    .put("p95_ms", percentile(latencyMs, 0.95))
                    .put("max_ms", latencyMs.maxOrNull() ?: 0.0))
                .put("dev_accessed", false)
                .put("protected_test_accessed", false)
                .put("training_executed", false)
                .put("live_phone_recognition_executed", false)
            val root = File(
                requireNotNull(context.getExternalFilesDir(null)),
                "phase4a_gate2_recognizer_runtime_parity_01",
            ).also { it.mkdirs() }
            File(root, "android_tflite_parity.json").writeText(result.toString(2))
            return result
        } finally {
            interpreter.close()
        }
    }

    private fun inspectIo(interpreter: Interpreter): RuntimeIo {
        var feature = -1
        var mask = -1
        val inputs = JSONArray()
        for (index in 0 until interpreter.inputTensorCount) {
            val tensor = interpreter.getInputTensor(index)
            val shape = tensor.shape()
            inputs.put(JSONObject()
                .put("array_index", index)
                .put("name", tensor.name())
                .put("dtype", tensor.dataType().toString())
                .put("shape", JSONArray(shape.toList())))
            if (shape.contentEquals(intArrayOf(1, 96, 350)) && tensor.dataType() == DataType.FLOAT32) {
                feature = index
            }
            if (shape.contentEquals(intArrayOf(1, 96)) && tensor.dataType() == DataType.BOOL) {
                mask = index
            }
        }
        require(feature >= 0 && mask >= 0 && interpreter.outputTensorCount == 1)
        val outputTensor = interpreter.getOutputTensor(0)
        require(outputTensor.shape().contentEquals(intArrayOf(1, OUTPUTS)))
        require(outputTensor.dataType() == DataType.FLOAT32)
        val outputs = JSONArray().put(JSONObject()
            .put("array_index", 0)
            .put("name", outputTensor.name())
            .put("dtype", outputTensor.dataType().toString())
            .put("shape", JSONArray(outputTensor.shape().toList())))
        return RuntimeIo(feature, mask, 0, inputs, outputs)
    }

    private fun invoke(
        interpreter: Interpreter,
        io: RuntimeIo,
        features: FloatArray,
        mask: BooleanArray,
    ): FloatArray {
        val featureBuffer = ByteBuffer.allocateDirect(features.size * 4).order(ByteOrder.nativeOrder())
        featureBuffer.asFloatBuffer().put(features)
        val maskBuffer = ByteBuffer.allocateDirect(mask.size).order(ByteOrder.nativeOrder())
        mask.forEach { maskBuffer.put(if (it) 1 else 0) }
        maskBuffer.rewind()
        val outputBuffer = ByteBuffer.allocateDirect(OUTPUTS * 4).order(ByteOrder.nativeOrder())
        val inputs = Array<Any>(interpreter.inputTensorCount) { ByteBuffer.allocateDirect(0) }
        inputs[io.featureInput] = featureBuffer
        inputs[io.maskInput] = maskBuffer
        val outputs = mutableMapOf<Int, Any>(io.output to outputBuffer)
        interpreter.runForMultipleInputsOutputs(inputs, outputs)
        outputBuffer.rewind()
        return FloatArray(OUTPUTS).also { outputBuffer.asFloatBuffer().get(it) }
    }

    private fun topK(values: FloatArray): IntArray = values.indices
        .sortedWith(compareByDescending<Int> { values[it] }.thenBy { it })
        .take(5)
        .toIntArray()

    private fun glossArray(glosses: JSONArray, indices: IntArray) =
        JSONArray(indices.map { glosses.getString(it) })

    private fun percentile(values: DoubleArray, fraction: Double): Double {
        if (values.isEmpty()) return 0.0
        val sorted = values.sorted()
        return sorted[((sorted.size - 1) * fraction).toInt()]
    }

    private fun mapAsset(context: Context, asset: String): MappedByteBuffer {
        val descriptor = context.assets.openFd(asset)
        FileInputStream(descriptor.fileDescriptor).use { stream ->
            return stream.channel.map(
                FileChannel.MapMode.READ_ONLY,
                descriptor.startOffset,
                descriptor.declaredLength,
            )
        }
    }

    private fun assetSha256(context: Context, asset: String): String =
        sha256(context.assets.open(asset).use { it.readBytes() })

    private fun readVerifiedFloats(context: Context, asset: String, expectedSha: String): FloatArray {
        val bytes = context.assets.open(asset).use { it.readBytes() }
        require(sha256(bytes) == expectedSha) { "GATE2_ASSET_HASH_MISMATCH:$asset" }
        require(bytes.size % 4 == 0)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }

    private fun JSONArray.intArray() = IntArray(length()) { getInt(it) }
    private fun JSONArray.booleanArray() = BooleanArray(length()) { getBoolean(it) }
}
