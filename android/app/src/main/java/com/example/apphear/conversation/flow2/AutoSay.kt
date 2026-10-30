package com.example.apphear.conversation.flow2

import android.content.Context
import com.example.apphear.conversation.AutoReplyCountdown
import org.json.JSONObject

/** conversationAutoSay timings, shipped as [ASSET] so they can be tuned on the phone without code edits. */
data class AutoSayPolicy(
    /** How long the signer must be still after their last sign before the countdown starts. */
    val stillnessMs: Long,
    /** The visible "SAYING IN 3, 2, 1" countdown before the message is spoken. */
    val countdownMs: Long,
) {
    init {
        require(stillnessMs in MIN_STILLNESS_MS..MAX_STILLNESS_MS) { "[conversation/autosay] stillnessMs out of range" }
        require(countdownMs in MIN_COUNTDOWN_MS..MAX_COUNTDOWN_MS) { "[conversation/autosay] countdownMs out of range" }
    }

    companion object {
        const val ASSET = "conversation/auto_say_policy_v1.json"
        const val SCHEMA_VERSION = 1
        const val MIN_STILLNESS_MS = 1_000L
        const val MAX_STILLNESS_MS = 8_000L
        const val MIN_COUNTDOWN_MS = 1_000L
        const val MAX_COUNTDOWN_MS = 5_000L

        fun parse(schemaVersion: Int, stillnessMs: Long, countdownMs: Long): AutoSayPolicy {
            require(schemaVersion == SCHEMA_VERSION) { "[conversation/autosay] schema mismatch" }
            return AutoSayPolicy(stillnessMs, countdownMs)
        }

        fun load(context: Context): AutoSayPolicy {
            val json = JSONObject(context.assets.open(ASSET).bufferedReader().use { it.readText() })
            return parse(json.getInt("schemaVersion"), json.getLong("stillnessMs"), json.getLong("countdownMs"))
        }
    }
}

/**
 * conversationAutoSay: speaks the signer's message once they stop signing, without a tap.
 *
 * When there is a message the signer may say and they have been still for [AutoSayPolicy.stillnessMs],
 * a visible countdown runs and then [onFire] says the message. Signing again resets the wait (new words
 * are added, nothing is cut off); WAIT holds this message until its words change; a message that was
 * already said is never said again automatically. Scheduling is injected so this runs in plain JVM
 * tests; in the app it is a main-thread Handler. Not thread safe.
 */
class AutoSay(
    policy: AutoSayPolicy,
    private val schedule: (delayMs: Long, task: Runnable) -> Unit,
    private val unschedule: (task: Runnable) -> Unit,
    /** Seconds left in the visible countdown, or null when none is showing. */
    private val onCountdown: (secondsLeft: Int?) -> Unit,
    private val onFire: () -> Unit,
) {
    private val stillnessMs = policy.stillnessMs
    private val countdown = AutoReplyCountdown(policy.countdownMs, schedule, unschedule,
        onTick = { onCountdown(it) },
        onFire = {
            onCountdown(null)
            heldWords = words
            onFire()
        },
    )
    private var words: String? = null
    private var canSay = false
    /** Words that must not be said automatically: WAIT was tapped, or they were already said. */
    private var heldWords: String? = null
    private var stillness: Runnable? = null

    val counting: Boolean get() = countdown.running

    /**
     * The current message ([words], null when none) and whether it may be said now: the signer's
     * turn, word signing (not spelling) and no text box open.
     */
    fun update(words: String?, canSay: Boolean) {
        val changed = words != this.words
        this.words = words
        this.canSay = canSay
        if (changed && heldWords != words) heldWords = null
        when {
            !armed() -> reset()
            changed || (stillness == null && !countdown.running) -> restartWait()
        }
    }

    /** The signer is signing right now: whatever was pending waits for them to stop again. */
    fun activity() {
        if (armed()) restartWait()
    }

    /** WAIT, or the message was said by hand: do not say these words automatically. */
    fun hold() {
        heldWords = words
        reset()
    }

    fun cancel() = reset()

    private fun armed() = canSay && words != null && words != heldWords

    private fun restartWait() {
        reset()
        val task = Runnable {
            stillness = null
            if (armed()) countdown.start()
        }
        stillness = task
        schedule(stillnessMs, task)
    }

    private fun reset() {
        stillness?.let(unschedule)
        stillness = null
        if (countdown.cancel()) onCountdown(null)
    }
}
