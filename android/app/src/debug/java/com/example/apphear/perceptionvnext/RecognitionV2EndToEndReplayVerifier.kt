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

/**
 * Gate-3 integration verifier. The primary path starts from frozen raw-v1 JSON, derives V2 with
 * RecognitionV2.kt, and immediately invokes the authorized ordinary V2 FP32 TFLite recognizer.
 * It never opens CameraX and never reads DEV or protected TEST.
 */
object RecognitionV2EndToEndReplayVerifier {
    private const val CONTRACT = "phase4a_gate3_known_train_replay/manifest.json"
    private const val EXPECTED_MILESTONE = "PHASE_4A_GATE_3_KNOWN_TRAIN_END_TO_END_REPLAY_01"
    private const val EXPECTED_RAW_SCHEMA = "apphear.perception_vnext.raw.v1"
    private const val EXPECTED_FEATURE_SCHEMA = "apphear.perception_vnext.recognition.v2"
    private const val GATE1_MANIFEST_SHA =
        "01fd271c25df2d0b7a64e803fabe0b745d51be1ac8f7c6f646546e2a3aa055b3"
    private const val GATE2_MANIFEST_SHA =
        "bfe8bec13a646eb6fa733c3bee6a421a44b5e58ed6dbb0dd59d88804e397d019"
    private const val MODEL_SHA =
        "1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c"
    private const val VOCAB_SHA =
        "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b"
    private const val FEATURE_ELEMENTS = 96 * 350
    private const val OUTPUTS = 236

    private data class ViewInput(
        val fixtureId: String,
        val sampleId: String,
        val conditionName: String,
        val truthClass: Int,
        val truthGloss: String,
        val view: RecognitionV2.TemporalView,
        val expectedFeatures: FloatArray,
        val expectedOutput: FloatArray,
    ) {
        val key: String get() = "$fixtureId:$conditionName"
    }

    private data class RuntimeIo(val featureInput: Int, val maskInput: Int, val output: Int)

    private class ErrorStats(private val capacity: Int) {
        private val values = DoubleArray(capacity)
        private var count = 0
        var maximum = 0.0
            private set
        var worstFixture = ""
            private set
        var worstCondition = ""
            private set
        var worstIndex = -1
            private set
        var reference = 0.0
            private set
        var actual = 0.0
            private set

        fun add(
            value: Double,
            fixture: String,
            condition: String,
            index: Int,
            expected: Double,
            observed: Double,
        ) {
            require(count < values.size)
            values[count++] = value
            if (value > maximum) {
                maximum = value
                worstFixture = fixture
                worstCondition = condition
                worstIndex = index
                reference = expected
                actual = observed
            }
        }

        fun json(indexName: String): JSONObject {
            val sorted = values.copyOf(count).also { it.sort() }
            return JSONObject()
                .put("count", count)
                .put("max_abs", maximum)
                .put("p95_abs", percentile(sorted, 0.95))
                .put("mean_abs", if (count == 0) 0.0 else values.take(count).average())
                .put("worst_fixture", worstFixture)
                .put("worst_condition", worstCondition)
                .put(indexName, worstIndex)
                .put("reference_value", reference)
                .put("android_value", actual)
        }
    }

    /** Reuses every runtime buffer but clears and fully rewrites it before each invocation. */
    private class ReusableRunner(
        private val interpreter: Interpreter,
        private val io: RuntimeIo,
    ) {
        private val featureBuffer = ByteBuffer.allocateDirect(FEATURE_ELEMENTS * 4)
            .order(ByteOrder.nativeOrder())
        private val maskBuffer = ByteBuffer.allocateDirect(96).order(ByteOrder.nativeOrder())
        private val outputBuffer = ByteBuffer.allocateDirect(OUTPUTS * 4)
            .order(ByteOrder.nativeOrder())
        private val inputs = Array<Any>(interpreter.inputTensorCount) { ByteBuffer.allocateDirect(0) }
        private val outputs = mutableMapOf<Int, Any>(io.output to outputBuffer)

        fun invoke(features: FloatArray, mask: BooleanArray, featureSchema: String): FloatArray {
            require(featureSchema == EXPECTED_FEATURE_SCHEMA) { "GATE3_CONSUMER_SCHEMA_MISMATCH" }
            require(featureSchema == RecognitionV2.FEATURE_SCHEMA)
            require(features.size == FEATURE_ELEMENTS && mask.size == 96)

            featureBuffer.clear()
            featureBuffer.asFloatBuffer().put(features)
            featureBuffer.position(0)
            featureBuffer.limit(featureBuffer.capacity())

            maskBuffer.clear()
            mask.forEach { maskBuffer.put(if (it) 1 else 0) }
            maskBuffer.flip()

            outputBuffer.clear()
            outputBuffer.asFloatBuffer().put(FloatArray(OUTPUTS))
            outputBuffer.position(0)
            outputBuffer.limit(outputBuffer.capacity())

            inputs[io.featureInput] = featureBuffer
            inputs[io.maskInput] = maskBuffer
            interpreter.runForMultipleInputsOutputs(inputs, outputs)

            outputBuffer.position(0)
            return FloatArray(OUTPUTS).also { outputBuffer.asFloatBuffer().get(it) }
        }
    }

    fun verify(context: Context): JSONObject {
        val contract = JSONObject(context.assets.open(CONTRACT).bufferedReader().readText())
        require(contract.getString("milestone") == EXPECTED_MILESTONE)
        require(contract.getString("raw_schema") == EXPECTED_RAW_SCHEMA)
        require(contract.getString("feature_schema") == EXPECTED_FEATURE_SCHEMA)
        require(RecognitionV2.RAW_SCHEMA == EXPECTED_RAW_SCHEMA)
        require(RecognitionV2.FEATURE_SCHEMA == EXPECTED_FEATURE_SCHEMA)
        require(contract.getJSONArray("feature_shape").intArray().contentEquals(intArrayOf(96, 350)))
        require(contract.getJSONArray("mask_shape").intArray().contentEquals(intArrayOf(96)))
        require(contract.getInt("output_count") == OUTPUTS)
        require(!contract.getBoolean("dev_accessed") && !contract.getBoolean("protected_test_accessed"))

        val tolerances = contract.getJSONObject("tolerances")
        val featureTolerance = tolerances.getDouble("android_v2_max_abs")
        val outputTolerance = tolerances.getDouble("keras_vs_android_composed_max_abs")
        val stateTolerance = tolerances.getDouble("state_replay_max_abs")
        require(featureTolerance == 1e-5 && outputTolerance == 1e-4 && stateTolerance == 1e-6)

        val gate1Asset = contract.getString("gate1_manifest_asset")
        val gate2Asset = contract.getString("gate2_manifest_asset")
        val gate1Bytes = context.assets.open(gate1Asset).use { it.readBytes() }
        val gate2Bytes = context.assets.open(gate2Asset).use { it.readBytes() }
        require(sha256(gate1Bytes) == GATE1_MANIFEST_SHA) { "GATE3_GATE1_MANIFEST_HASH_MISMATCH" }
        require(sha256(gate2Bytes) == GATE2_MANIFEST_SHA) { "GATE3_GATE2_MANIFEST_HASH_MISMATCH" }
        val gate1 = JSONObject(gate1Bytes.toString(Charsets.UTF_8))
        val gate2 = JSONObject(gate2Bytes.toString(Charsets.UTF_8))
        require(gate1.getString("raw_schema") == EXPECTED_RAW_SCHEMA)
        require(gate1.getString("feature_schema") == EXPECTED_FEATURE_SCHEMA)
        require(gate1.getJSONArray("fixtures").length() == 10)
        require(gate2.getString("feature_schema") == EXPECTED_FEATURE_SCHEMA)
        require(gate2.getString("model_sha256") == MODEL_SHA)
        require(gate2.getString("vocabulary_sha256") == VOCAB_SHA)
        require(gate2.getJSONArray("class_index_to_gloss").length() == OUTPUTS)
        require(gate2.getJSONArray("output_shape").intArray().contentEquals(intArrayOf(1, OUTPUTS)))
        require(gate2.getString("output_semantics") == "probabilities_softmax")
        require(!gate2.getBoolean("dev_accessed") && !gate2.getBoolean("protected_test_accessed"))

        val modelAsset = gate2.getString("model_asset")
        require(assetSha256(context, modelAsset) == MODEL_SHA) { "GATE3_MODEL_HASH_MISMATCH" }
        val glosses = gate2.getJSONArray("class_index_to_gloss")
        val truthByFixture = readTruth(contract, glosses)
        val gate2Views = indexGate2Views(gate2)

        val viewInputs = ArrayList<ViewInput>(20)
        val buildLatency = DoubleArray(20)
        var buildLatencyIndex = 0
        val gate1Fixtures = gate1.getJSONArray("fixtures")
        for (fixtureIndex in 0 until gate1Fixtures.length()) {
            val fixture = gate1Fixtures.getJSONObject(fixtureIndex)
            val fixtureId = fixture.getString("fixture_id")
            val truth = truthByFixture.getValue(fixtureId)
            require(fixture.getString("sample_id") == truth.getString("sample_id"))
            val raw = readRaw(
                readVerified(
                    context,
                    fixture.getString("raw_asset"),
                    fixture.getString("raw_sha256"),
                ).toString(Charsets.UTF_8),
            )
            require(raw.schema == EXPECTED_RAW_SCHEMA)
            val expectedViews = fixture.getJSONObject("views")
            for (conditionName in listOf("dense", "phone_01_sparse")) {
                val condition = if (conditionName == "dense") {
                    RecognitionV2.TemporalCondition.DENSE
                } else {
                    RecognitionV2.TemporalCondition.PHONE_01_SPARSE
                }
                val start = System.nanoTime()
                val view = RecognitionV2.temporalView(
                    raw,
                    condition,
                    gate1.getDouble("phone_completed_fps"),
                )
                buildLatency[buildLatencyIndex++] = (System.nanoTime() - start) / 1_000_000.0
                val expectedView = expectedViews.getJSONObject(conditionName)
                require(view.sourceIndices.contentEquals(expectedView.getJSONArray("source_indices").intArray()))
                require(view.sourceTimestampsMs.contentEquals(
                    expectedView.getJSONArray("source_timestamps_ms").doubleArray(),
                ))
                require(view.mask.contentEquals(expectedView.getJSONArray("mask").booleanArray()))
                val gate2View = gate2Views.getValue("$fixtureId:$conditionName")
                require(gate2View.getString("sample_id") == fixture.getString("sample_id"))
                viewInputs.add(
                    ViewInput(
                        fixtureId = fixtureId,
                        sampleId = fixture.getString("sample_id"),
                        conditionName = conditionName,
                        truthClass = truth.getInt("class_id"),
                        truthGloss = truth.getString("canonical_gloss"),
                        view = view,
                        expectedFeatures = readVerifiedFloats(
                            context,
                            expectedView.getString("tensor_asset"),
                            expectedView.getString("tensor_sha256"),
                        ),
                        expectedOutput = readVerifiedFloats(
                            context,
                            gate2View.getString("keras_output_asset"),
                            gate2View.getString("keras_output_sha256"),
                        ),
                    ),
                )
            }
        }
        require(viewInputs.size == 20 && buildLatencyIndex == 20)

        val featureErrors = ErrorStats(viewInputs.size * FEATURE_ELEMENTS)
        var discreteMismatches = 0
        for (item in viewInputs) {
            require(item.expectedFeatures.size == FEATURE_ELEMENTS)
            for (element in item.expectedFeatures.indices) {
                val expected = item.expectedFeatures[element]
                val actual = item.view.features[element]
                val difference = abs(expected - actual).toDouble()
                featureErrors.add(
                    difference,
                    item.fixtureId,
                    item.conditionName,
                    element,
                    expected.toDouble(),
                    actual.toDouble(),
                )
                val channel = element % RecognitionV2.FEATURE_WIDTH
                if (channel in discreteChannels && expected != actual) discreteMismatches++
            }
        }

        val runtime = gate2.getJSONObject("runtime")
        require(runtime.getInt("cpu_threads") == 4)
        require(runtime.getBoolean("xnnpack_requested"))
        require(!runtime.getBoolean("nnapi") && !runtime.getBoolean("gpu"))
        val interpreter = newInterpreter(context, modelAsset, runtime.getInt("cpu_threads"))
        val outputErrors = ErrorStats(viewInputs.size * OUTPUTS)
        val perView = JSONArray()
        val fullOutputs = JSONArray()
        val canonicalOutputs = linkedMapOf<String, FloatArray>()
        val inferenceLatency = DoubleArray(viewInputs.size)
        var top1Mismatches = 0
        var top5MembershipMismatches = 0
        var top5OrderMismatches = 0
        var denseTruthCorrect = 0
        var sparseTruthCorrect = 0
        try {
            val io = inspectIo(interpreter)
            val runner = ReusableRunner(interpreter, io)
            for ((viewIndex, item) in viewInputs.withIndex()) {
                val start = System.nanoTime()
                val actual = runner.invoke(item.view.features, item.view.mask, EXPECTED_FEATURE_SCHEMA)
                inferenceLatency[viewIndex] = (System.nanoTime() - start) / 1_000_000.0
                canonicalOutputs[item.key] = actual
                val local = ErrorStats(OUTPUTS)
                for (outputIndex in 0 until OUTPUTS) {
                    require(actual[outputIndex].isFinite())
                    val difference = abs(item.expectedOutput[outputIndex] - actual[outputIndex]).toDouble()
                    outputErrors.add(
                        difference,
                        item.fixtureId,
                        item.conditionName,
                        outputIndex,
                        item.expectedOutput[outputIndex].toDouble(),
                        actual[outputIndex].toDouble(),
                    )
                    local.add(
                        difference,
                        item.fixtureId,
                        item.conditionName,
                        outputIndex,
                        item.expectedOutput[outputIndex].toDouble(),
                        actual[outputIndex].toDouble(),
                    )
                }
                val expectedTop = topK(item.expectedOutput)
                val actualTop = topK(actual)
                if (expectedTop[0] != actualTop[0]) top1Mismatches++
                if (expectedTop.toSet() != actualTop.toSet()) top5MembershipMismatches++
                if (!expectedTop.contentEquals(actualTop)) top5OrderMismatches++
                if (actualTop[0] == item.truthClass) {
                    if (item.conditionName == "dense") denseTruthCorrect++ else sparseTruthCorrect++
                }
                val tensorFile = persistTensor(context, item)
                perView.put(
                    local.json("worst_output_index")
                        .put("fixture_id", item.fixtureId)
                        .put("sample_id", item.sampleId)
                        .put("condition", item.conditionName)
                        .put("truth_class", item.truthClass)
                        .put("truth_gloss", item.truthGloss)
                        .put("source_indices", JSONArray(item.view.sourceIndices.toList()))
                        .put("source_timestamps_ms", JSONArray(item.view.sourceTimestampsMs.toList()))
                        .put("mask", JSONArray(item.view.mask.toList()))
                        .put("v2_tensor_file", tensorFile.absolutePath)
                        .put("v2_tensor_sha256", sha256(tensorFile.readBytes()))
                        .put("keras_top5_indices", JSONArray(expectedTop.toList()))
                        .put("android_top5_indices", JSONArray(actualTop.toList()))
                        .put("keras_top5_glosses", glossArray(glosses, expectedTop))
                        .put("android_top5_glosses", glossArray(glosses, actualTop))
                        .put("top1_match", expectedTop[0] == actualTop[0])
                        .put("top5_membership_match", expectedTop.toSet() == actualTop.toSet())
                        .put("top5_order_match", expectedTop.contentEquals(actualTop))
                        .put("ground_truth_correct", actualTop[0] == item.truthClass),
                )
                fullOutputs.put(
                    JSONObject()
                        .put("fixture_id", item.fixtureId)
                        .put("condition", item.conditionName)
                        .put("android_composed_probabilities", JSONArray(actual.toList())),
                )
            }

            val stateAudit = runStateAudit(
                context,
                modelAsset,
                runtime.getInt("cpu_threads"),
                viewInputs,
                canonicalOutputs,
                stateTolerance,
            )
            val featurePass = featureErrors.maximum <= featureTolerance && discreteMismatches == 0
            val outputPass = outputErrors.maximum <= outputTolerance && top1Mismatches == 0 &&
                top5MembershipMismatches == 0 && top5OrderMismatches == 0
            val pass = featurePass && outputPass && stateAudit.getString("status") == "PASS"
            val combinedLatency = DoubleArray(20) { buildLatency[it] + inferenceLatency[it] }
            val result = JSONObject()
                .put("milestone", EXPECTED_MILESTONE)
                .put("status", if (pass) "PASS" else "FAIL")
                .put("classification", if (pass) {
                    "KNOWN_TRAIN_END_TO_END_REPLAY_PASS"
                } else {
                    "KNOWN_TRAIN_END_TO_END_REPLAY_FAIL"
                })
                .put("device_manufacturer", android.os.Build.MANUFACTURER)
                .put("device_model", android.os.Build.MODEL)
                .put("android_version", android.os.Build.VERSION.RELEASE)
                .put("tflite_runtime_version", TensorFlowLite.runtimeVersion())
                .put("runtime_configuration", JSONObject()
                    .put("precision", "FP32")
                    .put("cpu_threads", runtime.getInt("cpu_threads"))
                    .put("xnnpack_requested", true)
                    .put("nnapi", false)
                    .put("gpu", false)
                    .put("buffers", "reused; cleared and fully rewritten every invocation"))
                .put("raw_schema", EXPECTED_RAW_SCHEMA)
                .put("feature_schema", EXPECTED_FEATURE_SCHEMA)
                .put("feature_shape", JSONArray(listOf(96, 350)))
                .put("mask_shape", JSONArray(listOf(96)))
                .put("model_output_count", OUTPUTS)
                .put("model_sha256", MODEL_SHA)
                .put("vocabulary_sha256", VOCAB_SHA)
                .put("fixtures", 10)
                .put("dense_views", 10)
                .put("sparse_views", 10)
                .put("android_v2_intermediate_parity", featureErrors.json("worst_flat_element")
                    .put("tolerance", featureTolerance)
                    .put("discrete_mismatches", discreteMismatches)
                    .put("status", if (featurePass) "PASS" else "FAIL"))
                .put("end_to_end_output_parity", outputErrors.json("worst_output_index")
                    .put("worst_gloss", if (outputErrors.worstIndex >= 0) {
                        glosses.getString(outputErrors.worstIndex)
                    } else "")
                    .put("tolerance", outputTolerance)
                    .put("top1_mismatches", top1Mismatches)
                    .put("top5_membership_mismatches", top5MembershipMismatches)
                    .put("top5_order_mismatches", top5OrderMismatches)
                    .put("documented_numerical_ties", 0)
                    .put("status", if (outputPass) "PASS" else "FAIL"))
                .put("semantic_correctness_diagnostic_only", JSONObject()
                    .put("dense_ground_truth_correct", denseTruthCorrect)
                    .put("dense_total", 10)
                    .put("sparse_ground_truth_correct", sparseTruthCorrect)
                    .put("sparse_total", 10)
                    .put("used_for_gate_decision", false))
                .put("state_buffer_replay", stateAudit)
                .put("latency", JSONObject()
                    .put("scope", "saved raw-v1 -> V2; V2 -> TFLite; composed sum")
                    .put("measurements", 20)
                    .put("v2_construction_p50_ms", percentile(buildLatency.sortedArray(), 0.50))
                    .put("v2_construction_p95_ms", percentile(buildLatency.sortedArray(), 0.95))
                    .put("tflite_p50_ms", percentile(inferenceLatency.sortedArray(), 0.50))
                    .put("tflite_p95_ms", percentile(inferenceLatency.sortedArray(), 0.95))
                    .put("combined_p50_ms", percentile(combinedLatency.sortedArray(), 0.50))
                    .put("combined_p95_ms", percentile(combinedLatency.sortedArray(), 0.95)))
                .put("per_view", perView)
                .put("full_output_vectors", fullOutputs)
                .put("dev_accessed", false)
                .put("protected_test_accessed", false)
                .put("training_executed", false)
                .put("live_camera_recognition_executed", false)
            val root = outputRoot(context)
            File(root, "gate3_android_replay.json").writeText(result.toString(2))
            return result
        } finally {
            interpreter.close()
        }
    }

    private fun runStateAudit(
        context: Context,
        modelAsset: String,
        threads: Int,
        views: List<ViewInput>,
        canonical: Map<String, FloatArray>,
        tolerance: Double,
    ): JSONObject {
        var maximum = 0.0
        var comparisons = 0
        var failures = 0

        fun compare(item: ViewInput, actual: FloatArray) {
            val expected = canonical.getValue(item.key)
            for (index in 0 until OUTPUTS) {
                val difference = abs(expected[index] - actual[index]).toDouble()
                maximum = maxOf(maximum, difference)
                comparisons++
                if (difference > tolerance) failures++
            }
        }

        // Reverse order on one reused interpreter catches state leaked between arbitrary fixtures.
        newInterpreter(context, modelAsset, threads).use { interpreter ->
            val runner = ReusableRunner(interpreter, inspectIo(interpreter))
            for (item in views.asReversed()) {
                compare(item, runner.invoke(item.view.features, item.view.mask, EXPECTED_FEATURE_SCHEMA))
            }
        }

        // Each fixture gets fresh runtimes in both condition orders. This isolates dense/sparse
        // adjacency and proves either view is independent of the immediately preceding view.
        for (fixtureId in views.map { it.fixtureId }.distinct()) {
            val dense = views.first { it.fixtureId == fixtureId && it.conditionName == "dense" }
            val sparse = views.first {
                it.fixtureId == fixtureId && it.conditionName == "phone_01_sparse"
            }
            newInterpreter(context, modelAsset, threads).use { interpreter ->
                val runner = ReusableRunner(interpreter, inspectIo(interpreter))
                compare(dense, runner.invoke(dense.view.features, dense.view.mask, EXPECTED_FEATURE_SCHEMA))
                compare(sparse, runner.invoke(sparse.view.features, sparse.view.mask, EXPECTED_FEATURE_SCHEMA))
            }
            newInterpreter(context, modelAsset, threads).use { interpreter ->
                val runner = ReusableRunner(interpreter, inspectIo(interpreter))
                compare(sparse, runner.invoke(sparse.view.features, sparse.view.mask, EXPECTED_FEATURE_SCHEMA))
                compare(dense, runner.invoke(dense.view.features, dense.view.mask, EXPECTED_FEATURE_SCHEMA))
            }
        }
        return JSONObject()
            .put("status", if (failures == 0) "PASS" else "FAIL")
            .put("tolerance", tolerance)
            .put("comparisons", comparisons)
            .put("values_over_tolerance", failures)
            .put("max_abs", maximum)
            .put("forward_vs_reverse", if (failures == 0) "PASS" else "FAIL")
            .put("dense_then_sparse", if (failures == 0) "PASS" else "FAIL")
            .put("sparse_then_dense", if (failures == 0) "PASS" else "FAIL")
            .put("feature_buffer_fully_rewritten", true)
            .put("mask_buffer_fully_rewritten", true)
            .put("output_buffer_zeroed_before_invoke", true)
    }

    private fun readTruth(contract: JSONObject, glosses: JSONArray): Map<String, JSONObject> {
        val result = linkedMapOf<String, JSONObject>()
        val fixtures = contract.getJSONArray("fixtures")
        require(fixtures.length() == 10)
        for (index in 0 until fixtures.length()) {
            val item = fixtures.getJSONObject(index)
            require(item.getString("split") == "train")
            val classId = item.getInt("class_id")
            require(classId in 0 until OUTPUTS)
            require(glosses.getString(classId) == item.getString("canonical_gloss"))
            result[item.getString("fixture_id")] = item
        }
        return result
    }

    private fun indexGate2Views(gate2: JSONObject): Map<String, JSONObject> {
        val result = linkedMapOf<String, JSONObject>()
        val views = gate2.getJSONArray("views")
        require(views.length() == 20)
        for (index in 0 until views.length()) {
            val item = views.getJSONObject(index)
            result["${item.getString("fixture_id")}:${item.getString("condition")}"] = item
        }
        return result
    }

    private fun readRaw(text: String): RecognitionV2.RawSequence {
        val value = JSONObject(text)
        return RecognitionV2.RawSequence(
            schema = value.getString("schema"),
            imageSemantics = value.getString("image_semantics"),
            frameIndex = value.getJSONArray("frame_index").intArray(),
            timestampMs = value.getJSONArray("timestamp_ms").doubleArray(),
            sourceSize = value.getJSONArray("source_size").intArray(),
            handXy = value.getJSONArray("hand_xy").floatArray(),
            handProposalSupport = value.getJSONArray("hand_proposal_support").floatArray(),
            handJointValid = value.getJSONArray("hand_joint_valid").booleanArray(),
            handPresence = value.getJSONArray("hand_presence").floatArray(),
            handObserved = value.getJSONArray("hand_observed").booleanArray(),
            bodyXy = value.getJSONArray("body_xy").floatArray(),
            bodySupport = value.getJSONArray("body_support").floatArray(),
            bodyValid = value.getJSONArray("body_valid").booleanArray(),
            bodyAvailable = value.getJSONArray("body_available").booleanArray(),
        ).also { it.validate() }
    }

    private fun newInterpreter(context: Context, modelAsset: String, threads: Int): Interpreter {
        val options = Interpreter.Options()
            .setNumThreads(threads)
            .setUseXNNPACK(true)
            .setUseNNAPI(false)
        return Interpreter(mapAsset(context, modelAsset), options).also { it.allocateTensors() }
    }

    private fun inspectIo(interpreter: Interpreter): RuntimeIo {
        var feature = -1
        var mask = -1
        for (index in 0 until interpreter.inputTensorCount) {
            val tensor = interpreter.getInputTensor(index)
            if (tensor.shape().contentEquals(intArrayOf(1, 96, 350)) &&
                tensor.dataType() == DataType.FLOAT32
            ) feature = index
            if (tensor.shape().contentEquals(intArrayOf(1, 96)) &&
                tensor.dataType() == DataType.BOOL
            ) mask = index
        }
        require(feature >= 0 && mask >= 0 && interpreter.outputTensorCount == 1)
        val output = interpreter.getOutputTensor(0)
        require(output.shape().contentEquals(intArrayOf(1, OUTPUTS)))
        require(output.dataType() == DataType.FLOAT32)
        return RuntimeIo(feature, mask, 0)
    }

    private fun persistTensor(context: Context, item: ViewInput): File {
        val directory = File(outputRoot(context), "v2_tensors").also { it.mkdirs() }
        val file = File(directory, "${item.fixtureId}_${item.conditionName}.f32")
        val bytes = ByteBuffer.allocate(item.view.features.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        bytes.asFloatBuffer().put(item.view.features)
        file.writeBytes(bytes.array())
        return file
    }

    private fun outputRoot(context: Context) = File(
        requireNotNull(context.getExternalFilesDir(null)),
        "phase4a_gate3_known_train_end_to_end_replay_01",
    ).also { it.mkdirs() }

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

    private fun readVerified(context: Context, asset: String, expectedSha: String): ByteArray {
        val bytes = context.assets.open(asset).use { it.readBytes() }
        require(sha256(bytes) == expectedSha) { "GATE3_ASSET_HASH_MISMATCH:$asset" }
        return bytes
    }

    private fun readVerifiedFloats(context: Context, asset: String, expectedSha: String): FloatArray {
        val bytes = readVerified(context, asset, expectedSha)
        require(bytes.size % 4 == 0)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    private fun assetSha256(context: Context, asset: String): String =
        sha256(context.assets.open(asset).use { it.readBytes() })

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }

    private fun topK(values: FloatArray): IntArray = values.indices
        .sortedWith(compareByDescending<Int> { values[it] }.thenBy { it })
        .take(5)
        .toIntArray()

    private fun glossArray(glosses: JSONArray, indices: IntArray) =
        JSONArray(indices.map { glosses.getString(it) })

    private fun percentile(sorted: DoubleArray, fraction: Double): Double {
        if (sorted.isEmpty()) return 0.0
        return sorted[((sorted.size - 1) * fraction).toInt()]
    }

    private fun JSONArray.intArray() = IntArray(length()) { getInt(it) }
    private fun JSONArray.doubleArray() = DoubleArray(length()) { getDouble(it) }
    private fun JSONArray.floatArray() = FloatArray(length()) { getDouble(it).toFloat() }
    private fun JSONArray.booleanArray() = BooleanArray(length()) { getBoolean(it) }

    private val discreteChannels: Set<Int> = buildSet {
        for (handStart in intArrayOf(0, 130)) {
            addAll((handStart + 40 until handStart + 60).toList())
            addAll((handStart + 90 until handStart + 105).toList())
            addAll((handStart + 115 until handStart + 120).toList())
            add(handStart + 127)
            add(handStart + 129)
        }
        addAll((272 until 278).toList())
        addAll((286 until 296).toList())
        add(302)
        addAll((317 until 324).toList())
        addAll((338 until 345).toList())
        add(347)
    }
}
