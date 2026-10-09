package com.example.apphear.p8b

import android.content.Context
import com.example.apphear.p8c2.P8c2NativeDecoder
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/** Single-worker-owned FP32 Student-1 runner. No production recognition connection. */
class P8bModelRunner(context: Context) : AutoCloseable {
    data class Timing(
        val invokeWallNs: Long,
        val nativeInferenceNs: Long,
        val outputReadNs: Long,
        val decodeNs: Long,
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
    private val output = ByteBuffer.allocateDirect(OUTPUT_FLOATS * 4).order(ByteOrder.nativeOrder())
    private val outputView = output.asFloatBuffer()
    val heatmaps = FloatArray(OUTPUT_FLOATS)
    val modelSha256 = assetSha256(context, MODEL_ASSET)

    init {
        require(modelSha256 == MODEL_SHA256) { "P8B_MODEL_ASSET_DRIFT" }
        interpreter.allocateTensors()
        require(interpreter.inputTensorCount == 1 && interpreter.outputTensorCount == 1)
        require(interpreter.getInputTensor(0).shape().contentEquals(intArrayOf(1, 384, 384, 3)))
        require(interpreter.getInputTensor(0).dataType().toString() == "FLOAT32")
        require(interpreter.getOutputTensor(0).shape().contentEquals(intArrayOf(1, 96, 96, 50)))
        require(interpreter.getOutputTensor(0).dataType().toString() == "FLOAT32")
    }

    fun run(input: ByteBuffer, decoder: P8bDecoder): Timing {
        input.rewind()
        output.clear()
        val invokeStart = System.nanoTime()
        interpreter.run(input, output)
        val invokeEnd = System.nanoTime()
        val nativeNs = interpreter.lastNativeInferenceDurationNanoseconds ?: (invokeEnd - invokeStart)
        outputView.rewind()
        outputView.get(heatmaps)
        val readEnd = System.nanoTime()
        decoder.decode(heatmaps)
        val decodeEnd = System.nanoTime()
        return Timing(invokeEnd - invokeStart, nativeNs, readEnd - invokeEnd, decodeEnd - readEnd)
    }

    /** P8-C2 formal path: TFLite writes the reusable direct buffer consumed by one JNI call. */
    fun runNative(input: ByteBuffer, decoder: P8c2NativeDecoder): Timing {
        input.rewind()
        output.clear()
        val invokeStart = System.nanoTime()
        interpreter.run(input, output)
        val invokeEnd = System.nanoTime()
        val nativeNs = interpreter.lastNativeInferenceDurationNanoseconds ?: (invokeEnd - invokeStart)
        output.rewind()
        decoder.decode(output)
        val decodeEnd = System.nanoTime()
        return Timing(invokeEnd - invokeStart, nativeNs, 0L, decodeEnd - invokeEnd)
    }

    /** P8-C2 parity-only path: one inference, then the exact same output feeds both decoders. */
    fun runSameHeatmapParity(
        input: ByteBuffer,
        kotlinDecoder: P8bDecoder,
        nativeDecoder: P8c2NativeDecoder,
    ): Timing {
        input.rewind()
        output.clear()
        val invokeStart = System.nanoTime()
        interpreter.run(input, output)
        val invokeEnd = System.nanoTime()
        val nativeNs = interpreter.lastNativeInferenceDurationNanoseconds ?: (invokeEnd - invokeStart)
        outputView.rewind()
        outputView.get(heatmaps)
        val readEnd = System.nanoTime()
        kotlinDecoder.decode(heatmaps)
        output.rewind()
        nativeDecoder.decode(output)
        val decodeEnd = System.nanoTime()
        return Timing(invokeEnd - invokeStart, nativeNs, readEnd - invokeEnd, decodeEnd - readEnd)
    }

    /** Static synthetic parity helper; no model invocation. */
    fun directOutputBuffer(): ByteBuffer = output.duplicate().order(ByteOrder.nativeOrder())

    override fun close() {
        interpreter.close()
    }

    companion object {
        const val MODEL_ASSET = "p8b/student1_fp32.tflite"
        const val MODEL_SHA256 = "f49a66e80241d67f9ef06729c01670190dd63a7eeb552d2737f46856e8670b43"
        const val OUTPUT_FLOATS = 96 * 96 * 50

        fun assetSha256(context: Context, asset: String): String {
            val digest = MessageDigest.getInstance("SHA-256")
            context.assets.open(asset).use { stream ->
                val block = ByteArray(64 * 1024)
                while (true) {
                    val count = stream.read(block)
                    if (count < 0) break
                    digest.update(block, 0, count)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
