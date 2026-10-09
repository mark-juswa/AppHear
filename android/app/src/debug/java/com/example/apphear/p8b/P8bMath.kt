package com.example.apphear.p8b

import com.example.apphear.p7d.P7dMath
import kotlin.math.exp

/** Frozen heatmap-only P7C decoder for the P8-B debug path. */
class P8bDecoder(val transform: P7dMath.Transform) {
    val allowed = BooleanArray(P7dMath.GRID * P7dMath.GRID) {
        transform.admissible(it % P7dMath.GRID, it / P7dMath.GRID)
    }
    val peaks = IntArray(P7dMath.POINTS)
    private val maxima = FloatArray(P7dMath.POINTS)
    val inputXY = FloatArray(P7dMath.POINTS * 2)
    val sourceXY = FloatArray(P7dMath.POINTS * 2)

    init {
        require(allowed.any { it }) { "P8B_INPUT_TRANSFORM_INVALID" }
    }

    fun decode(heat: FloatArray) {
        require(heat.size == P7dMath.GRID * P7dMath.GRID * P7dMath.POINTS)
        maxima.fill(Float.NEGATIVE_INFINITY)
        peaks.fill(-1)
        var cell = 0
        var offset = 0
        while (cell < P7dMath.GRID * P7dMath.GRID) {
            val use = allowed[cell]
            var point = 0
            while (point < P7dMath.POINTS) {
                val value = heat[offset++]
                require(value.isFinite()) { "P8B_NATIVE_OUTPUT_INVALID" }
                if (use && value > maxima[point]) {
                    maxima[point] = value
                    peaks[point] = cell
                }
                point++
            }
            cell++
        }

        var point = 0
        while (point < P7dMath.POINTS) {
            val peakX = peaks[point] % P7dMath.GRID
            val peakY = peaks[point] / P7dMath.GRID
            var total = 0.0
            var weightedX = 0.0
            var weightedY = 0.0
            var y = maxOf(0, peakY - 1)
            val endY = minOf(P7dMath.GRID - 1, peakY + 1)
            val endX = minOf(P7dMath.GRID - 1, peakX + 1)
            while (y <= endY) {
                var x = maxOf(0, peakX - 1)
                while (x <= endX) {
                    if (allowed[y * P7dMath.GRID + x]) {
                        val weight = exp(
                            heat[(y * P7dMath.GRID + x) * P7dMath.POINTS + point].toDouble() -
                                maxima[point],
                        )
                        total += weight
                        weightedX += x * weight
                        weightedY += y * weight
                    }
                    x++
                }
                y++
            }
            val inputX = 4.0 * (weightedX / total + 0.5) - 0.5
            val inputY = 4.0 * (weightedY / total + 0.5) - 0.5
            inputXY[point * 2] = inputX.toFloat()
            inputXY[point * 2 + 1] = inputY.toFloat()
            sourceXY[point * 2] = transform.inverseX(inputX).toFloat()
            sourceXY[point * 2 + 1] = transform.inverseY(inputY).toFloat()
            require(sourceXY[point * 2].isFinite() && sourceXY[point * 2 + 1].isFinite()) {
                "P8B_SOURCE_OUTPUT_NONFINITE"
            }
            point++
        }
    }
}

internal object P8bStats {
    data class Summary(val count: Int, val mean: Double, val p50: Double, val p95: Double, val maximum: Double)

    fun summarize(values: DoubleArray, count: Int = values.size): Summary {
        require(count > 0 && count <= values.size)
        val sorted = values.copyOf(count).also { it.sort() }
        return Summary(
            count = count,
            mean = sorted.average(),
            p50 = quantile(sorted, 0.50),
            p95 = quantile(sorted, 0.95),
            maximum = sorted.last(),
        )
    }

    private fun quantile(sorted: DoubleArray, fraction: Double): Double {
        val index = fraction * (sorted.size - 1)
        val low = index.toInt()
        val high = minOf(low + 1, sorted.lastIndex)
        return sorted[low] + (sorted[high] - sorted[low]) * (index - low)
    }
}
