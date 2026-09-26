package com.example.apphear.perceptionvnext

import androidx.camera.core.ImageProxy
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

internal object PerceptionVNextMath {
    const val POINTS = 133
    const val LEFT_HAND_START = 91
    const val RIGHT_HAND_START = 112
    const val HAND_POINTS = 21
    const val BODY_POINTS = 8
    val bodyIndices = intArrayOf(5, 6, 7, 8, 9, 10, 11, 12)

    data class Transform(
        val sourceWidth: Int,
        val sourceHeight: Int,
        val centerX: Float,
        val centerY: Float,
        val scaleX: Float,
        val scaleY: Float,
    )

    data class Decoded(val xy: FloatArray, val support: FloatArray)

    data class HandRoi(
        val centerX: Float,
        val centerY: Float,
        val side: Float,
        val sourceWidth: Int,
        val sourceHeight: Int,
        val supportCount: Int,
    ) {
        val left: Float get() = centerX - side * 0.5f
        val top: Float get() = centerY - side * 0.5f
        val right: Float get() = centerX + side * 0.5f
        val bottom: Float get() = centerY + side * 0.5f
    }

    fun transform(image: ImageProxy): Transform {
        val rotation = image.imageInfo.rotationDegrees
        val sourceWidth = if (rotation == 90 || rotation == 270) image.height else image.width
        val sourceHeight = if (rotation == 90 || rotation == 270) image.width else image.height
        return transform(sourceWidth, sourceHeight)
    }

    fun transform(sourceWidth: Int, sourceHeight: Int): Transform {
        val centerX = sourceWidth * 0.5f
        val centerY = sourceHeight * 0.5f
        var scaleX = sourceWidth * 1.25f
        var scaleY = sourceHeight * 1.25f
        val aspect = 192f / 256f
        if (scaleX > scaleY * aspect) {
            scaleY = scaleX / aspect
        } else {
            scaleX = scaleY * aspect
        }
        return Transform(sourceWidth, sourceHeight, centerX, centerY, scaleX, scaleY)
    }

    fun decode(
        simccX: Array<FloatArray>,
        simccY: Array<FloatArray>,
        transform: Transform,
    ): Decoded {
        require(simccX.size == POINTS && simccY.size == POINTS)
        val xy = FloatArray(POINTS * 2)
        val support = FloatArray(POINTS)
        for (point in 0 until POINTS) {
            require(simccX[point].size == 384 && simccY[point].size == 512)
            var xIndex = 0
            var yIndex = 0
            var xMax = simccX[point][0]
            var yMax = simccY[point][0]
            for (index in 1 until 384) {
                if (simccX[point][index] > xMax) {
                    xMax = simccX[point][index]
                    xIndex = index
                }
            }
            for (index in 1 until 512) {
                if (simccY[point][index] > yMax) {
                    yMax = simccY[point][index]
                    yIndex = index
                }
            }
            val score = min(xMax, yMax)
            support[point] = score
            val inputX = if (score > 0f) xIndex / 2f else -0.5f
            val inputY = if (score > 0f) yIndex / 2f else -0.5f
            xy[point * 2] =
                inputX / 192f * transform.scaleX + transform.centerX - transform.scaleX * 0.5f
            xy[point * 2 + 1] =
                inputY / 256f * transform.scaleY + transform.centerY - transform.scaleY * 0.5f
        }
        return Decoded(xy, support)
    }

    fun handRoi(decoded: Decoded, start: Int, transform: Transform): HandRoi? {
        require(start == LEFT_HAND_START || start == RIGHT_HAND_START)
        val xs = ArrayList<Float>(HAND_POINTS)
        val ys = ArrayList<Float>(HAND_POINTS)
        for (local in 0 until HAND_POINTS) {
            val point = start + local
            val x = decoded.xy[point * 2]
            val y = decoded.xy[point * 2 + 1]
            val valid = x.isFinite() && y.isFinite() &&
                x >= 0f && x < transform.sourceWidth &&
                y >= 0f && y < transform.sourceHeight &&
                decoded.support[point].isFinite() && decoded.support[point] >= 0.10f
            if (valid) {
                xs.add(x)
                ys.add(y)
            }
        }
        if (xs.size < 5) return null
        xs.sort()
        ys.sort()
        val centerX = quantile(xs, 0.50f)
        val centerY = quantile(ys, 0.50f)
        val extent = max(quantile(xs, 0.95f) - quantile(xs, 0.05f), quantile(ys, 0.95f) - quantile(ys, 0.05f))
        val minimumSide = min(transform.sourceWidth, transform.sourceHeight) * 0.12f
        val maximumSide = min(transform.sourceWidth, transform.sourceHeight) * 0.50f
        val side = (extent * 1.8f).coerceIn(minimumSide, maximumSide)
        return HandRoi(
            centerX,
            centerY,
            side,
            transform.sourceWidth,
            transform.sourceHeight,
            xs.size,
        )
    }

    /** Current-frame validity behind the existing PHONE_01 body-availability rule. */
    fun bodyPointValid(
        x: Float,
        y: Float,
        support: Float,
        transform: Transform,
    ): Boolean =
        x.isFinite() && y.isFinite() && support.isFinite() && support >= 0.30f &&
            x >= 0f && x < transform.sourceWidth &&
            y >= 0f && y < transform.sourceHeight

    private fun quantile(sorted: List<Float>, q: Float): Float {
        val position = q * (sorted.size - 1)
        val low = floor(position).toInt()
        val high = min(low + 1, sorted.lastIndex)
        val fraction = position - low
        return sorted[low] + (sorted[high] - sorted[low]) * fraction
    }
}
