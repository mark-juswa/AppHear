package com.example.apphear.p6c

import kotlin.math.hypot
import kotlin.math.max

/** Exact debug-only Kotlin port of DWPOSE_REPRESENTATION_V2_238 for P6-C. */
internal object P6cV2Math {
    const val POINTS = 133
    const val FEATURE_WIDTH = 238
    const val SCORE_THRESHOLD = 0.30f
    const val MIN_HAND_POINTS = 11
    private const val MIN_SCALE = 1e-6
    private val body = 0..16
    private val leftHand = 91..111
    private val rightHand = 112..132

    data class Decoded(val xy: FloatArray, val scores: FloatArray)
    data class Normalization(
        val success: Boolean,
        val centerX: Double,
        val centerY: Double,
        val scale: Double,
        val centerMethod: String,
        val scaleMethod: String,
    )
    data class V2Result(
        val features: FloatArray,
        val valid: BooleanArray,
        val leftObserved: Boolean,
        val rightObserved: Boolean,
        val normalization: Normalization,
    )

    fun decode(simccX: Array<FloatArray>, simccY: Array<FloatArray>, center: FloatArray, scale: FloatArray): Decoded {
        require(simccX.size == POINTS && simccY.size == POINTS)
        val xy = FloatArray(POINTS * 2)
        val scores = FloatArray(POINTS)
        for (point in 0 until POINTS) {
            val x = simccX[point]
            val y = simccY[point]
            require(x.size == 384 && y.size == 512)
            var xIndex = 0
            var yIndex = 0
            var xMax = x[0]
            var yMax = y[0]
            for (i in 1 until x.size) if (x[i] > xMax) { xMax = x[i]; xIndex = i }
            for (i in 1 until y.size) if (y[i] > yMax) { yMax = y[i]; yIndex = i }
            val score = minOf(xMax, yMax)
            scores[point] = score
            val inputX = if (score > 0f) xIndex.toFloat() / 2f else -0.5f
            val inputY = if (score > 0f) yIndex.toFloat() / 2f else -0.5f
            xy[point * 2] = inputX / 192f * scale[0] + center[0] - 0.5f * scale[0]
            xy[point * 2 + 1] = inputY / 256f * scale[1] + center[1] - 0.5f * scale[1]
        }
        return Decoded(xy, scores)
    }

    fun build(xy: FloatArray, scores: FloatArray): V2Result {
        require(xy.size == POINTS * 2 && scores.size == POINTS)
        val valid = BooleanArray(POINTS) { i ->
            xy[i * 2].isFinite() && xy[i * 2 + 1].isFinite() && scores[i].isFinite()
        }
        val normalization = normalization(xy, valid)
        val leftPresent = leftHand.count { scores[it] >= SCORE_THRESHOLD } >= MIN_HAND_POINTS
        val rightPresent = rightHand.count { scores[it] >= SCORE_THRESHOLD } >= MIN_HAND_POINTS
        val leftObserved = leftPresent && normalization.success
        val rightObserved = rightPresent && normalization.success
        val output = FloatArray(FEATURE_WIDTH)
        encode(output, 0, leftHand, xy, scores, valid, normalization, leftObserved)
        encode(output, 84, rightHand, xy, scores, valid, normalization, rightObserved)
        encode(output, 168, body, xy, scores, valid, normalization, true)
        output[236] = if (leftObserved) 1f else 0f
        output[237] = if (rightObserved) 1f else 0f
        check(output.all { it.isFinite() })
        return V2Result(output, valid, leftObserved, rightObserved, normalization)
    }

    private fun normalization(xy: FloatArray, valid: BooleanArray): Normalization {
        fun midpoint(a: Int, b: Int): Pair<Double, Double>? = if (valid[a] && valid[b]) {
            Pair((xy[a * 2].toDouble() + xy[b * 2].toDouble()) / 2.0, (xy[a * 2 + 1].toDouble() + xy[b * 2 + 1].toDouble()) / 2.0)
        } else null
        fun distance(a: Pair<Double, Double>, b: Pair<Double, Double>): Double? {
            val value = hypot(a.first - b.first, a.second - b.second)
            return if (value.isFinite() && value > MIN_SCALE) value else null
        }

        val shoulders = midpoint(5, 6)
        val hips = midpoint(11, 12)
        val validBody = body.filter { valid[it] }
        val center: Pair<Double, Double>
        val centerMethod: String
        when {
            shoulders != null -> { center = shoulders; centerMethod = "SHOULDER_PRIMARY" }
            hips != null -> { center = hips; centerMethod = "HIP_FALLBACK" }
            validBody.isNotEmpty() -> {
                center = Pair(validBody.sumOf { xy[it * 2].toDouble() } / validBody.size, validBody.sumOf { xy[it * 2 + 1].toDouble() } / validBody.size)
                centerMethod = "VALID_BODY_MEAN_FALLBACK"
            }
            else -> return Normalization(false, 0.0, 0.0, 0.0, "UNAVAILABLE", "UNAVAILABLE")
        }
        val shoulderDistance = if (valid[5] && valid[6]) distance(Pair(xy[10].toDouble(), xy[11].toDouble()), Pair(xy[12].toDouble(), xy[13].toDouble())) else null
        val torsoDistance = if (shoulders != null && hips != null) distance(shoulders, hips) else null
        val scale: Double
        val scaleMethod: String
        when {
            shoulderDistance != null -> { scale = shoulderDistance; scaleMethod = "SHOULDER_DISTANCE_PRIMARY" }
            torsoDistance != null -> { scale = torsoDistance; scaleMethod = "TORSO_DISTANCE_FALLBACK" }
            validBody.size >= 2 -> {
                val xs = validBody.map { xy[it * 2].toDouble() }
                val ys = validBody.map { xy[it * 2 + 1].toDouble() }
                val envelope = hypot((xs.maxOrNull()!! - xs.minOrNull()!!), (ys.maxOrNull()!! - ys.minOrNull()!!))
                if (!envelope.isFinite() || envelope <= MIN_SCALE) return Normalization(false, center.first, center.second, 0.0, centerMethod, "UNAVAILABLE")
                scale = envelope; scaleMethod = "VALID_BODY_ENVELOPE_FALLBACK"
            }
            else -> return Normalization(false, center.first, center.second, 0.0, centerMethod, "UNAVAILABLE")
        }
        return Normalization(true, center.first, center.second, max(scale, MIN_SCALE), centerMethod, scaleMethod)
    }

    private fun encode(
        output: FloatArray,
        offset: Int,
        indices: IntRange,
        xy: FloatArray,
        scores: FloatArray,
        valid: BooleanArray,
        normalization: Normalization,
        enabled: Boolean,
    ) {
        if (!enabled || !normalization.success) return
        indices.forEachIndexed { local, point ->
            if (valid[point]) {
                val out = offset + local * 4
                output[out] = ((xy[point * 2].toDouble() - normalization.centerX) / normalization.scale).toFloat()
                output[out + 1] = ((xy[point * 2 + 1].toDouble() - normalization.centerY) / normalization.scale).toFloat()
                output[out + 2] = scores[point]
                output[out + 3] = 1f
            }
        }
    }
}
