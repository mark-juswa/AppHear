package com.example.apphear.coordination

import com.example.apphear.fingerspelling.RecognitionMode
import java.util.Locale

enum class SpellingIntent { NAME, PLACE, SPELL }
data class ContextModeRule(val kind: SpellingIntent, val pattern: Regex)
data class CoordinationState(
    val mode: RecognitionMode, val hearingTurnId: Long?, val hint: SpellingIntent?,
    val automatic: Boolean, val responseStarted: Boolean, val lastConfirmedSpelling: String,
    val boundHearingTurnId: Long?,
)

/** Pure camera-executor policy. Never reads recognizer scores or supplies recognition text. */
class RecognitionCoordinator(private val rules: List<ContextModeRule>, initial: RecognitionMode) {
    private var mode = initial
    private var turnId: Long? = null
    private var highestTurn = 0L
    private var closedThrough = 0L
    private var consumedThrough = 0L
    private var hint: SpellingIntent? = null
    private var boundTurn: Long? = null
    private var bindInitialContext = initial == RecognitionMode.FINGERSPELL
    private var readySeen = false
    private var started = false
    private var automatic = false
    private var lastConfirmed = ""
    @Volatile var state = snapshot(); private set

    fun classify(text: String): SpellingIntent? {
        val normalized = text.lowercase(Locale.ROOT).replace('’','\'').trim()
            .replace(Regex("[?!.]+$"), "").replace(Regex("\\s+"), " ")
        return rules.firstOrNull { it.pattern.matches(normalized) }?.kind
    }

    fun context(id: Long?, text: String) {
        if (id == null) {
            closedThrough = maxOf(closedThrough, highestTurn)
            turnId = null; hint = null; bindInitialContext = false; publish(); return
        }
        if (id < highestTurn || id <= closedThrough) return
        if (id != turnId) {
            highestTurn = id; turnId = id; hint = classify(text)
            started = mode == RecognitionMode.FINGERSPELL
        }
        if (bindInitialContext) { boundTurn = id; bindInitialContext = false }
        publish()
    }

    /** Uses only existing idle state + current real input visibility, with no new timeout. */
    fun observation(wordIdle: Boolean, usableHand: Boolean): RecognitionMode? {
        if (mode != RecognitionMode.WORD) return null
        if (wordIdle) readySeen = true
        if (readySeen && (usableHand || !wordIdle)) started = true
        val id = turnId
        if (wordIdle && !usableHand && !started && hint != null && id != null && id > consumedThrough) {
            consumedThrough = id; boundTurn = id; automatic = true; mode = RecognitionMode.FINGERSPELL
            publish(); return mode
        }
        publish(); return null
    }

    fun wordActivity(committed: Boolean = false) {
        if (mode == RecognitionMode.WORD && (readySeen || committed)) { started = true; publish() }
    }

    /** Explicit override wins for the entire current turn, including delayed provider updates. */
    fun manual(next: RecognitionMode): RecognitionMode? {
        turnId?.let { consumedThrough = maxOf(consumedThrough, it) }
        bindInitialContext = false; automatic = false
        if (next == mode) { publish(); return null }
        mode = next; boundTurn = if (next == RecognitionMode.FINGERSPELL) turnId else null
        started = true; readySeen = false; publish(); return next
    }

    fun complete(actualConfirmedText: String): RecognitionMode {
        require(mode == RecognitionMode.FINGERSPELL && actualConfirmedText.isNotBlank())
        require(actualConfirmedText.all { it in 'A'..'Z' || it == ' ' })
        lastConfirmed = actualConfirmedText
        turnId?.let { consumedThrough = maxOf(consumedThrough, it) }
        mode = RecognitionMode.WORD; automatic = false; started = true; boundTurn = null
        readySeen = false; publish(); return mode
    }

    fun pause() { readySeen = false; started = true; publish() }
    private fun snapshot() = CoordinationState(mode,turnId,hint,automatic,started,lastConfirmed,boundTurn)
    private fun publish() { state = snapshot() }
}
