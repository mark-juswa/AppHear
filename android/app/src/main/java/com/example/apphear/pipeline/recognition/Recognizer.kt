package com.example.apphear.pipeline.recognition

import android.content.Context
import android.util.Log
import com.example.apphear.pipeline.features.FEATURE_DIM
import org.tensorflow.lite.Interpreter
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel

/**
 * S6 — the INT8 streaming recognizer (streaming.tflite). Fixed window: input (1, T, 258) float32,
 * output (1, T, numClasses) float32 per-frame softmax. Per the F19 decision, we RE-RUN the full
 * window each recognition tick and read the current frame's posterior — exact parity with the
 * offline pipeline (the TCN is tiny next to the landmarkers, so this is effectively free), no
 * stateful re-export. Load is expensive (~model init) so `load()` must run off the main thread
 * (v2 lesson h).
 */
class Recognizer private constructor(
    private val interpreter: Interpreter,
    val timeWindow: Int,
    val numClasses: Int,
) {
    private val input = Array(1) { Array(timeWindow) { FloatArray(FEATURE_DIM) } }
    private val output = Array(1) { Array(timeWindow) { FloatArray(numClasses) } }

    /**
     * Run the full [window] (already post-padded to timeWindow; padded rows zero) and return the
     * per-frame softmax posterior at frame [index] (the current real frame). Not thread-safe —
     * call from a single inference thread.
     */
    fun infer(window: Array<FloatArray>, index: Int): FloatArray {
        for (t in 0 until timeWindow) {
            System.arraycopy(window[t], 0, input[0][t], 0, FEATURE_DIM)
        }
        interpreter.run(input, output)
        return output[0][index].copyOf()
    }

    fun close() = interpreter.close()

    companion object {
        fun load(context: Context, timeWindow: Int, numClasses: Int): Recognizer {
            val model = mapModel(context, "streaming.tflite")
            val options = Interpreter.Options().apply { numThreads = 2 } // CPU/XNNPACK (no GPU — v2 lesson g)
            val interpreter = Interpreter(model, options)
            // Pin the input to a fixed [1, T, 258] so the batch dim is never ambiguous.
            interpreter.resizeInput(0, intArrayOf(1, timeWindow, FEATURE_DIM))
            interpreter.allocateTensors()
            Log.i("AppHearRecog", "recognizer loaded: window=$timeWindow classes=$numClasses")
            return Recognizer(interpreter, timeWindow, numClasses)
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
