package com.example.apphear.fingerspelling

import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.ln1p

/** Exact CTC singleton grammar, NOT a newly trained isolated-letter classifier. */
object FingerspellSingleLetterDecoder {
    const val VERSION = "apphear.fingerspelling.single_letter_ctc.v1"
    data class Result(val text: String, val bestLetter: String, val letterLogMasses: DoubleArray,
                      val emptyLogMass: Double, val spaceLogMass: Double)
    private fun logAdd(a: Double, b: Double): Double {
        if (a == Double.NEGATIVE_INFINITY) return b
        if (b == Double.NEGATIVE_INFINITY) return a
        val high = maxOf(a,b)
        return high + ln1p(exp(minOf(a,b)-high))
    }
    fun decode(logits: Array<FloatArray>, blankPenalty: Float = 0.5f): Result {
        require(blankPenalty == 0.5f) { "Frozen blank penalty must remain 0.5" }
        val before = DoubleArray(27)
        val letter = DoubleArray(27) { Double.NEGATIVE_INFINITY }
        val after = DoubleArray(27) { Double.NEGATIVE_INFINITY }
        var empty = 0.0
        for (row in logits) {
            require(row.size == 28 && row.all { it.isFinite() })
            // Same float32 subtraction as frozen Python and Android beam.
            val logp = DoubleArray(28) { (row[it] - if(it==27) blankPenalty else 0f).toDouble() }
            val maximum = logp.maxOrNull()!!
            var sum = 0.0
            for (c in 0..27) { logp[c] -= maximum; sum += exp(logp[c]) }
            val denominator = ln(sum)
            for (c in 0..27) logp[c] -= denominator
            empty += logp[27]
            for (c in 0..26) {
                val nextBefore = before[c] + logp[27]
                val nextLetter = logAdd(before[c],letter[c]) + logp[c]
                val nextAfter = logAdd(letter[c],after[c]) + logp[27]
                before[c]=nextBefore; letter[c]=nextLetter; after[c]=nextAfter
            }
        }
        val mass = DoubleArray(27) { logAdd(letter[it],after[it]) }
        var best = 0
        for (c in 1..25) if (mass[c] > mass[best]) best=c
        val bestLetter = ('A'.code+best).toChar().toString()
        return Result(if(mass[best]>maxOf(empty,mass[26])) bestLetter else "", bestLetter,
            mass.copyOfRange(0,26),empty,mass[26])
    }
}

/** Internal experimental/rollback flag. Only frozen V2.1 geometry uses this flow. */
object FingerspellCapturePolicy {
    const val SINGLE_LETTER_ENABLED = true
    const val CANDIDATE = "SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY"
}

/** Exact no-input guard, matching Python input_evidence.v1; no guessed ratio cutoff. */
class FingerspellInputEvidence {
    var observations = 0; private set
    var accepted = 0; private set
    var usable = 0; private set
    fun reset() { observations=0; accepted=0; usable=0 }
    fun record(observation: CommonObservation): Boolean {
        val hasAccepted = observation.observed.any { it }
        val hasUsable = (0..1).any { observation.observed[it] && observation.valid[it].any { it } }
        observations++
        if (hasAccepted) accepted++
        if (hasUsable) usable++
        return hasUsable
    }
    fun refusal(): String? = when {
        accepted==0 -> "NO_ACCEPTED_HAND_OBSERVATIONS"
        usable==0 -> "NO_VALID_HAND_GEOMETRY"
        else -> null
    }
}
