package com.example.apphear.fingerspelling

import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.ln1p

/** Language-free, fixed width-10 port of the validated Python prefix decoder. */
object FingerspellPrefixBeamDecoder {
    const val BEAM_WIDTH = 10
    const val BLANK = 27
    const val BLANK_PENALTY = 0.5f
    data class Result(val text: String, val logCtcMassPruned: Double)
    private class Mass(var blank: Double = Double.NEGATIVE_INFINITY,
                       var nonblank: Double = Double.NEGATIVE_INFINITY)
    private data class Ranked(val prefix: String, val mass: Mass, val total: Double)

    private fun logAdd(a: Double, b: Double): Double {
        if (a == Double.NEGATIVE_INFINITY) return b
        if (b == Double.NEGATIVE_INFINITY) return a
        val high = maxOf(a, b); val low = minOf(a, b)
        return high + ln1p(exp(low - high))
    }

    fun decode(logits: Array<FloatArray>, blankPenalty: Float): Result {
        require(blankPenalty == BLANK_PENALTY) { "Frozen blank penalty must remain 0.5" }
        var beams = linkedMapOf("" to Mass(0.0))
        for (row in logits) {
            require(row.size == 28 && row.all { it.isFinite() })
            // Float subtraction precedes Double scoring, exactly as Python float32.
            val probabilities = DoubleArray(28) { symbol ->
                (row[symbol] - if (symbol == BLANK) blankPenalty else 0f).toDouble()
            }
            val maximum = probabilities.maxOrNull()!!
            var sum = 0.0
            for (symbol in probabilities.indices) {
                probabilities[symbol] -= maximum
                sum += exp(probabilities[symbol])
            }
            val denominator = ln(sum)
            for (symbol in probabilities.indices) probabilities[symbol] -= denominator
            // Ordered maps preserve reference accumulation order as well as ranking.
            val next = linkedMapOf<String, Mass>()
            for ((prefix, mass) in beams) {
                val total = logAdd(mass.blank, mass.nonblank)
                val same = next.getOrPut(prefix) { Mass() }
                same.blank = logAdd(same.blank, total + probabilities[BLANK])
                for (symbol in 0 until BLANK) {
                    // Internal A..[ encodes token IDs 0..26. '[' represents SPACE;
                    // its lexical order matches Python token tuples, not ASCII space.
                    val token = ('A'.code + symbol).toChar()
                    val extension = if (prefix.isNotEmpty() && token == prefix.last()) {
                        same.nonblank = logAdd(same.nonblank, mass.nonblank + probabilities[symbol])
                        mass.blank + probabilities[symbol]
                    } else total + probabilities[symbol]
                    if (extension == Double.NEGATIVE_INFINITY) continue
                    val extended = next.getOrPut(prefix + token) { Mass() }
                    extended.nonblank = logAdd(extended.nonblank, extension)
                }
            }
            val ranked = next.map { (prefix, mass) -> Ranked(prefix, mass, logAdd(mass.blank, mass.nonblank)) }
                .sortedWith(compareByDescending<Ranked> { it.total }.thenBy { it.prefix })
                .take(BEAM_WIDTH)
            beams = linkedMapOf<String, Mass>().apply { ranked.forEach { put(it.prefix, it.mass) } }
        }
        val best = beams.map { (prefix, mass) -> Ranked(prefix, mass, logAdd(mass.blank, mass.nonblank)) }
            .sortedWith(compareByDescending<Ranked> { it.total }.thenBy { it.prefix }).first()
        return Result(best.prefix.replace('[', ' '), best.total)
    }
}

/** Kept internal: explicit rollback/reference, no additional user-facing mode or suggestions. */
enum class FingerspellDecoderMode { PREFIX_BEAM_TOP1, GREEDY }
