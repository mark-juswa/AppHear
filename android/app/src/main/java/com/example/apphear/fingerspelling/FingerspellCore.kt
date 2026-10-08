package com.example.apphear.fingerspelling

enum class RecognitionMode { WORD, FINGERSPELL }

/** Camera-executor confined owner. Entry/exit reset is supplied by the existing WORD API. */
class RecognitionModeController(private val resetWord: () -> Unit) {
    var mode = RecognitionMode.WORD; private set
    var generation = 0; private set
    fun select(next: RecognitionMode) {
        if (next != mode) { resetWord(); generation++; mode = next }
    }
    fun pause() { resetWord(); generation++ }
}

class FingerspellBuffer {
    var preview = ""; private set
    var confirmed = ""; private set
    fun show(text: String) { preview = text }
    fun clear() { preview = ""; confirmed = "" }
    fun retry() { preview = "" }
    fun confirmLetter(): String {
        require(preview.length==1 && preview[0] in 'A'..'Z') { "One letter required" }
        confirmed += preview
        preview = ""
        return confirmed
    }
    fun confirm(): String {
        require(preview.isNotBlank()) { "No spelling to confirm" }
        confirmed = listOf(confirmed, preview).filter { it.isNotEmpty() }.joinToString(" ")
        preview = ""
        return confirmed
    }
}

object FingerspellCtcDecoder {
    fun decode(logits: Array<FloatArray>, blankPenalty: Float): String {
        var previous = -1; val text = StringBuilder()
        for (row in logits) {
            require(row.size == 28 && row.all { it.isFinite() })
            var best = 0; var score = row[0]
            for (c in 1..27) {
                val value = row[c] - if (c == 27) blankPenalty else 0f
                if (value > score) { best = c; score = value }
            }
            if (best != previous && best != 27) text.append(if (best == 26) ' ' else ('A'.code+best).toChar())
            previous = best
        }
        return text.toString()
    }
}

enum class FingerspellPhase { READY, CAPTURING, DECODING, PREVIEW, ERROR }

/** Resource cap refuses an overlong attempt; never silently truncates a CTC sequence. */
class FingerspellSession(private val maximumFrames: Int, private val maximumSeconds: Double,
                        val inputWidth: Int = 1559) {
    init { require(inputWidth == 405 || inputWidth == 1559) }
    var phase = FingerspellPhase.READY; private set
    val buffer = FingerspellBuffer()
    private val frames = mutableListOf<FloatArray>()
    private val timestamps = mutableListOf<Double>()
    var token = 0; private set
    val count get() = timestamps.size
    fun start() { token++; frames.clear(); timestamps.clear(); buffer.retry(); phase = FingerspellPhase.CAPTURING }
    fun consume(timestampMs: Double, packed: FloatArray) {
        check(phase == FingerspellPhase.CAPTURING)
        require(packed.size == inputWidth && packed.all { it.isFinite() })
        require(timestampMs.isFinite() && (timestamps.isEmpty() || timestampMs > timestamps.last()))
        if (frames.size >= maximumFrames || (timestamps.isNotEmpty() && timestampMs-timestamps.first() > maximumSeconds*1000)) {
            cancel(); phase = FingerspellPhase.ERROR
            throw IllegalStateException("Session limit reached; retry a shorter spelling")
        }
        frames.add(packed.copyOf()); timestamps.add(timestampMs)
    }
    fun finish(): Pair<Int, List<FloatArray>> {
        check(phase == FingerspellPhase.CAPTURING)
        if (frames.isEmpty()) { phase = FingerspellPhase.ERROR; throw IllegalStateException("No observations; retry") }
        phase = FingerspellPhase.DECODING
        return token to frames.toList()
    }
    fun complete(generation: Int, text: String): Boolean {
        if (generation != token || phase != FingerspellPhase.DECODING) return false
        buffer.show(text); phase = FingerspellPhase.PREVIEW; frames.clear()
        return true
    }
    fun fail() { cancel(); phase = FingerspellPhase.ERROR }
    fun cancel() { token++; frames.clear(); timestamps.clear(); buffer.retry(); phase = FingerspellPhase.READY }
    fun clear() { cancel(); buffer.clear() }
}
