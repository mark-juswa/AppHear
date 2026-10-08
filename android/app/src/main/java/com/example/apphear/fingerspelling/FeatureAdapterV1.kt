// Production port of the frozen JVM reference; exact Adapter.v1 math.
package com.example.apphear.fingerspelling

import kotlin.math.sqrt

data class CommonObservation(
    val timestampMs: Double, val width: Int, val height: Int,
    val xy: Array<FloatArray>, val valid: Array<BooleanArray>, val support: Array<FloatArray>,
    val presence: FloatArray, val observed: BooleanArray, val proposal: BooleanArray,
    val roi: Array<FloatArray>, val bodyXy: FloatArray, val bodySupport: FloatArray,
    val bodyValid: BooleanArray, val bodyAvailable: Boolean,
)

/** Future PhoneRawObservation port must preserve this exact ordering and float arithmetic. */
class FingerspellingFeatureAdapterV1(private val scaleEpsilon: Float, private val maxGap: Float) {
    private var previous: CommonObservation? = null
    fun reset() { previous = null }
    fun derive(c: CommonObservation): FloatArray {
        require(c.timestampMs.isFinite() && c.width > 0 && c.height > 0)
        val old = previous
        require(old == null || c.timestampMs > old.timestampMs)
        val o = FloatArray(405)
        val w = c.width.toFloat(); val h = c.height.toFloat(); val short = minOf(w, h)
        if (old != null) { o[0] = ((c.timestampMs - old.timestampMs) / 1000.0).toFloat(); o[1] = 1f }
        for (s in 0..1) {
            fun valid(j: Int) = c.observed[s] && c.valid[s][j]
            var scale = 0f
            for (j in intArrayOf(5, 9, 13, 17)) {
                val x = c.xy[s][j * 2] - c.xy[s][0]
                val y = c.xy[s][j * 2 + 1] - c.xy[s][1]
                scale += sqrt((x * x + y * y).toDouble()).toFloat()
            }
            scale /= 4f
            val scaleValid = valid(0) && intArrayOf(5, 9, 13, 17).all { valid(it) } &&
                scale.isFinite() && scale > short * scaleEpsilon
            val start = 2 + s * 181
            for (j in 0 until 21) {
                val p = start + j * 8
                if (valid(j)) {
                    require(c.xy[s][2 * j].isFinite() && c.xy[s][2 * j + 1].isFinite())
                    o[p] = c.xy[s][j * 2] / w; o[p + 1] = c.xy[s][j * 2 + 1] / h
                    o[p + 4] = 1f
                    if (scaleValid) {
                        o[p + 2] = (c.xy[s][j * 2] - c.xy[s][0]) / scale
                        o[p + 3] = (c.xy[s][j * 2 + 1] - c.xy[s][1]) / scale
                        o[p + 5] = 1f
                    }
                }
                if (c.support[s][j].isFinite()) { o[p + 6] = c.support[s][j]; o[p + 7] = 1f }
            }
            val e = start + 168
            if (c.presence[s].isFinite()) { o[e] = c.presence[s]; o[e + 1] = 1f }
            o[e + 2] = if (c.observed[s]) 1f else 0f
            o[e + 3] = if (c.proposal[s]) 1f else 0f
            if (c.proposal[s] && c.roi[s].all { it.isFinite() } && c.roi[s][2] > 0f) {
                o[e + 4] = c.roi[s][0] / w; o[e + 5] = c.roi[s][1] / h
                o[e + 6] = c.roi[s][2] / short; o[e + 7] = 1f
            }
            if (scaleValid) { o[e + 8] = scale / short; o[e + 9] = 1f }
            if (old != null && valid(0) && old.observed[s] && old.valid[s][0] &&
                c.width == old.width && c.height == old.height && o[0] <= maxGap) {
                o[e + 10] = (c.xy[s][0] - old.xy[s][0]) / short
                o[e + 11] = (c.xy[s][1] - old.xy[s][1]) / short
                o[e + 12] = 1f
            }
        }
        for (p in 0 until 8) {
            val i = 364 + p * 5
            if (c.bodyValid[p]) {
                require(c.bodyXy[2 * p].isFinite() && c.bodyXy[2 * p + 1].isFinite())
                o[i] = c.bodyXy[2 * p] / w; o[i + 1] = c.bodyXy[2 * p + 1] / h; o[i + 3] = 1f
            }
            if (c.bodySupport[p].isFinite()) { o[i + 2] = c.bodySupport[p]; o[i + 4] = 1f }
        }
        o[404] = if (c.bodyAvailable) 1f else 0f
        require(o.all { it.isFinite() })
        previous = c
        return o
    }
}

