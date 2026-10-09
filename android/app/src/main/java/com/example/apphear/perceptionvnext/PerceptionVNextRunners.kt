package com.example.apphear.perceptionvnext

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import org.tensorflow.lite.Interpreter
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

internal class DWPoseTRunner(context: Context) : AutoCloseable {
    data class Result(
        val decoded: PerceptionVNextMath.Decoded,
        val inferenceMs: Double,
        val decodeMs: Double,
    )

    private val environment = OrtEnvironment.getEnvironment()
    private val modelFile = File(context.codeCacheDir, "perception_vnext_dwpose_t.onnx")
    private val session: OrtSession

    init {
        if (!modelFile.isFile || sha256(modelFile) != MODEL_SHA256) {
            context.assets.open(MODEL_ASSET).use { input ->
                modelFile.outputStream().use { output -> input.copyTo(output) }
            }
        }
        require(sha256(modelFile) == MODEL_SHA256) { "VNEXT_DWPOSE_T_ASSET_DRIFT" }
        val options = OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(2)
            setInterOpNumThreads(1)
            setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        }
        session = environment.createSession(modelFile.absolutePath, options)
        require(session.inputNames == setOf("input")) { "VNEXT_DWPOSE_T_INPUT_CONTRACT" }
        require(session.outputNames.containsAll(setOf("simcc_x", "simcc_y"))) {
            "VNEXT_DWPOSE_T_OUTPUT_CONTRACT"
        }
    }

    fun run(input: ByteBuffer, transform: PerceptionVNextMath.Transform): Result {
        require(input.capacity() == 3 * 256 * 192 * 4)
        val inferenceStarted = System.nanoTime()
        val outputs = OnnxTensor.createTensor(
            environment,
            input.duplicate().order(ByteOrder.nativeOrder()).asFloatBuffer(),
            longArrayOf(1, 3, 256, 192),
        ).use { tensor ->
            session.run(mapOf("input" to tensor)).use { result ->
                @Suppress("UNCHECKED_CAST")
                val x =
                    (result.get("simcc_x").orElseThrow().value as Array<Array<FloatArray>>)[0]
                @Suppress("UNCHECKED_CAST")
                val y =
                    (result.get("simcc_y").orElseThrow().value as Array<Array<FloatArray>>)[0]
                Pair(x, y)
            }
        }
        val inferenceEnded = System.nanoTime()
        val decoded = PerceptionVNextMath.decode(outputs.first, outputs.second, transform)
        val decodeEnded = System.nanoTime()
        return Result(
            decoded,
            (inferenceEnded - inferenceStarted) / 1_000_000.0,
            (decodeEnded - inferenceEnded) / 1_000_000.0,
        )
    }

    override fun close() {
        session.close()
    }

    companion object {
        const val MODEL_ASSET = "perception_vnext/dwpose_t_singlepass.onnx"
        const val MODEL_SHA256 =
            "37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0"
    }
}

internal class HandRefinerRunner(context: Context) : AutoCloseable {
    data class Result(
        val xySource: FloatArray,
        val valid: BooleanArray,
        val presence: Float,
        val handednessDiagnostic: Float,
        val observed: Boolean,
        val inferenceMs: Double,
    )

    private val modelBuffer = context.assets.openFd(MODEL_ASSET).use { descriptor ->
        FileInputStream(descriptor.fileDescriptor).channel.use { channel ->
            channel.map(
                java.nio.channels.FileChannel.MapMode.READ_ONLY,
                descriptor.startOffset,
                descriptor.declaredLength,
            )
        }
    }
    private val interpreter = Interpreter(
        modelBuffer,
        Interpreter.Options().setNumThreads(2).setUseXNNPACK(true).setUseNNAPI(false),
    )
    private val landmarks = Array(1) { FloatArray(63) }
    private val presence = Array(1) { FloatArray(1) }
    private val handedness = Array(1) { FloatArray(1) }
    private val world = Array(1) { FloatArray(63) }
    private val outputIndices: Map<String, Int>

    init {
        require(assetSha256(context, MODEL_ASSET) == MODEL_SHA256) {
            "VNEXT_HAND_REFINER_ASSET_DRIFT"
        }
        interpreter.allocateTensors()
        require(interpreter.inputTensorCount == 1 && interpreter.outputTensorCount == 4)
        require(interpreter.getInputTensor(0).shape().contentEquals(intArrayOf(1, 224, 224, 3)))
        val outputs = (0 until interpreter.outputTensorCount).associate { index ->
            interpreter.getOutputTensor(index).name() to interpreter.getOutputTensor(index)
        }
        require(outputs["Identity"]?.shape()?.contentEquals(intArrayOf(1, 63)) == true)
        require(outputs["Identity_1"]?.shape()?.contentEquals(intArrayOf(1, 1)) == true)
        require(outputs["Identity_2"]?.shape()?.contentEquals(intArrayOf(1, 1)) == true)
        require(outputs["Identity_3"]?.shape()?.contentEquals(intArrayOf(1, 63)) == true)
        outputIndices = (0 until interpreter.outputTensorCount).associateBy {
            interpreter.getOutputTensor(it).name()
        }
    }

    fun run(values: ByteBuffer, roi: PerceptionVNextMath.HandRoi): Result {
        require(values.capacity() == 224 * 224 * 3 * 4)
        val input = values.duplicate().order(ByteOrder.nativeOrder()).apply { rewind() }
        val started = System.nanoTime()
        val outputMap = mutableMapOf<Int, Any>(
            requireNotNull(outputIndices["Identity"]) to landmarks,
            requireNotNull(outputIndices["Identity_1"]) to presence,
            requireNotNull(outputIndices["Identity_2"]) to handedness,
            requireNotNull(outputIndices["Identity_3"]) to world,
        )
        interpreter.runForMultipleInputsOutputs(
            arrayOf(input),
            outputMap,
        )
        val ended = System.nanoTime()
        val xy = FloatArray(42)
        val valid = BooleanArray(21)
        for (point in 0 until 21) {
            val cropX = landmarks[0][point * 3]
            val cropY = landmarks[0][point * 3 + 1]
            xy[point * 2] = roi.left + cropX / 223f * roi.side
            xy[point * 2 + 1] = roi.top + cropY / 223f * roi.side
            valid[point] = cropX.isFinite() && cropY.isFinite() &&
                cropX >= 0f && cropX < 224f && cropY >= 0f && cropY < 224f
        }
        val observed = presence[0][0] >= 0.50f && valid.count { it } >= 18
        return Result(
            xy,
            valid,
            presence[0][0],
            handedness[0][0],
            observed,
            (ended - started) / 1_000_000.0,
        )
    }

    override fun close() {
        interpreter.close()
    }

    companion object {
        const val MODEL_ASSET = "perception_vnext/hand_landmarks_detector.tflite"
        const val MODEL_SHA256 =
            "6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9"
    }
}

private fun sha256(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().use { input ->
        val block = ByteArray(1024 * 1024)
        while (true) {
            val count = input.read(block)
            if (count <= 0) break
            digest.update(block, 0, count)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}

private fun assetSha256(context: Context, asset: String): String {
    val digest = MessageDigest.getInstance("SHA-256")
    context.assets.open(asset).use { input ->
        val block = ByteArray(64 * 1024)
        while (true) {
            val count = input.read(block)
            if (count < 0) break
            digest.update(block, 0, count)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}
