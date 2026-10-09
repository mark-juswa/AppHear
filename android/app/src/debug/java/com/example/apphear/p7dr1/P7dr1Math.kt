package com.example.apphear.p7dr1

import com.example.apphear.p7d.P7dMath
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.exp
import kotlin.math.floor

/** Beside, never instead of, P7dMath. Fixed-geometry caches contain no frame evidence. */
class P7dr1Preprocess(val width: Int, val height: Int, val rowStride: Int,
                     val pixelStride: Int, val rotation: Int) {
    init {
        require(width > 0 && height > 0 && pixelStride >= 4)
        require(rowStride >= (width - 1) * pixelStride + 4)
        require(rotation == 0 || rotation == 90 || rotation == 180 || rotation == 270)
    }
    val transform = P7dMath.Transform(if (rotation == 90 || rotation == 270) height else width,
                                    if (rotation == 90 || rotation == 270) width else height)
    // Last-row padding is not guaranteed accessible by CameraX. Copy only through last RGB.
    val sourceBytes = (height - 1) * rowStride + (width - 1) * pixelStride + 3
    private val raw = ByteArray(sourceBytes)
    private val a = IntArray(384 * 384) { -1 }
    private val b = IntArray(384 * 384)
    private val d = IntArray(384 * 384)
    private val e = IntArray(384 * 384)
    private val wx = FloatArray(384)
    private val wy = FloatArray(384)
    val input: ByteBuffer = ByteBuffer.allocateDirect(384 * 384 * 3 * 4).order(ByteOrder.nativeOrder())
    private val floats = input.asFloatBuffer()

    init {
        val t = transform
        for (y in t.top until t.top + t.rh) {
            val sy = t.inverseY(y.toDouble()).coerceIn(0.0, (t.height - 1).toDouble())
            val y0 = floor(sy).toInt(); val y1 = minOf(y0 + 1, t.height - 1)
            wy[y] = (sy - y0).toFloat()
            for (x in t.left until t.left + t.rw) {
                val sx = t.inverseX(x.toDouble()).coerceIn(0.0, (t.width - 1).toDouble())
                val x0 = floor(sx).toInt(); val x1 = minOf(x0 + 1, t.width - 1)
                wx[x] = (sx - x0).toFloat()
                val k = y * 384 + x
                a[k] = offset(x0, y0); b[k] = offset(x1, y0)
                d[k] = offset(x0, y1); e[k] = offset(x1, y1)
            }
        }
    }

    private fun offset(x: Int, y: Int): Int = when (rotation) {
        90 -> (height - 1 - x) * rowStride + y * pixelStride
        180 -> (height - 1 - y) * rowStride + (width - 1 - x) * pixelStride
        270 -> x * rowStride + (width - 1 - y) * pixelStride
        else -> y * rowStride + x * pixelStride
    }

    /** No allocation for unchanged geometry. Restore caller position; never retain source pixels. */
    fun run(source: ByteBuffer) {
        val base = source.position()
        require(source.remaining() >= sourceBytes)
        source.get(raw, 0, sourceBytes)
        source.position(base)
        floats.clear()
        var y = 0
        while (y < 384) {
            val fy = wy[y]
            var x = 0
            while (x < 384) {
                val k = y * 384 + x
                val aa = a[k]
                if (aa < 0) {
                    floats.put(0f); floats.put(0f); floats.put(0f)
                } else {
                    val bb = b[k]; val dd = d[k]; val ee = e[k]; val fx = wx[x]
                    var c = 0
                    while (c < 3) {
                        val av = (raw[aa+c].toInt() and 255).toFloat()
                        val bv = (raw[bb+c].toInt() and 255).toFloat()
                        val dv = (raw[dd+c].toInt() and 255).toFloat()
                        val ev = (raw[ee+c].toInt() and 255).toFloat()
                        val v = (av*(1-fx)+bv*fx)*(1-fy)+(dv*(1-fx)+ev*fx)*fy
                        floats.put((v-127.5f)/127.5f)
                        c++
                    }
                }
                x++
            }
            y++
        }
        input.rewind()
    }

    fun content(x: Int, y: Int): Boolean = a[y * 384 + x] >= 0
}

/** Buffers are owned by one worker; returned diagnostics expire at the next decode. */
class P7dr1Decoder(val transform: P7dMath.Transform) {
    val allowed = BooleanArray(96 * 96) { transform.admissible(it % 96, it / 96) }
    val peaks = IntArray(50)
    private val maxima = FloatArray(50)
    val inputXY = FloatArray(100)
    val confidence = FloatArray(50)
    val identity = FloatArray(2)
    val sourceXY = FloatArray(100)
    init { require(allowed.any { it }) { "INPUT_TRANSFORM_INVALID" } }

    fun decode(heat: FloatArray, identityLogits: FloatArray) {
        require(heat.size == 460800 && identityLogits.size == 2)
        require(identityLogits[0].isFinite() && identityLogits[1].isFinite()) { "NATIVE_OUTPUT_INVALID" }
        maxima.fill(Float.NEGATIVE_INFINITY); peaks.fill(-1)
        var cell = 0
        var k = 0
        while (cell < 9216) {
            val use = allowed[cell]
            var p = 0
            while (p < 50) {
                val v = heat[k++]
                // Check discarded padding too: the reference rejects ANY nonfinite native value.
                require(v.isFinite()) { "NATIVE_OUTPUT_INVALID" }
                if (use && v > maxima[p]) { maxima[p] = v; peaks[p] = cell }
                p++
            }
            cell++
        }
        var p = 0
        while (p < 50) {
            val px = peaks[p] % 96; val py = peaks[p] / 96
            var sum = 0.0; var sx = 0.0; var sy = 0.0
            var i = maxOf(0, py - 1)
            val endI = minOf(95, py + 1); val endJ = minOf(95, px + 1)
            while (i <= endI) {
                var j = maxOf(0, px - 1)
                while (j <= endJ) {
                    if (allowed[i * 96 + j]) {
                        val weight = exp(heat[(i * 96 + j) * 50 + p].toDouble() - maxima[p])
                        sum += weight; sx += j * weight; sy += i * weight
                    }
                    j++
                }
                i++
            }
            inputXY[p*2] = (4*(sx/sum+.5)-.5).toFloat()
            inputXY[p*2+1] = (4*(sy/sum+.5)-.5).toFloat()
            confidence[p] = P7dMath.sigmoid(maxima[p].toDouble())
            p++
        }
        identity[0] = P7dMath.sigmoid(identityLogits[0].toDouble())
        identity[1] = P7dMath.sigmoid(identityLogits[1].toDouble())
    }

    fun restore() {
        var p = 0
        while (p < 50) {
            sourceXY[p*2] = transform.inverseX(inputXY[p*2].toDouble()).toFloat()
            sourceXY[p*2+1] = transform.inverseY(inputXY[p*2+1].toDouble()).toFloat()
            require(sourceXY[p*2].isFinite() && sourceXY[p*2+1].isFinite()) { "SOURCE_OUTPUT_NONFINITE" }
            p++
        }
    }
}
