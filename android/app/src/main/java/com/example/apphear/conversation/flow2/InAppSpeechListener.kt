package com.example.apphear.conversation.flow2

import android.speech.SpeechRecognizer

/** Seam over Android's SpeechRecognizer so the listening rules can be unit-tested. Main thread only. */
interface SpeechBackend {
    fun isAvailable(): Boolean
    fun start(preferOffline: Boolean, events: SpeechEvents)
    /** The phone has working internet, so the (more accurate) online recognizer can be used. */
    fun hasInternet(): Boolean = false
    /** Abandon the current session; no result follows. */
    fun cancel()
    fun destroy()
}

interface SpeechEvents {
    fun onPartial(text: String)
    fun onLevel(rmsDb: Float)
    fun onFinal(text: String)
    fun onError(code: Int)
}

/**
 * In-app reply listening for conversationFlowV2: no system dialog, live partial text. Reports
 * every outcome against the caller's ticket so [ConversationFlow] can drop stale ones.
 *
 * With internet the online recognizer is used (the on-device one mishears more, e.g. "course" as
 * "horse"); if it fails for network reasons it retries once offline. Without internet offline is tried
 * first; if the phone lacks the offline language it retries once online. A missing permission or recognizer is reported as such so the caller can fall back to
 * the existing system speech dialog.
 *
 * The recognizer gives up within about two seconds if nobody has started talking, which is too soon
 * for a hearing person answering a message that was just spoken. Until something is heard, such a
 * give-up quietly restarts listening, up to [patienceMs] after [start]; then it is reported.
 */
class InAppSpeechListener(
    private val backend: SpeechBackend,
    private val hasPermission: () -> Boolean,
    private val clockMs: () -> Long = { android.os.SystemClock.elapsedRealtime() },
    private val patienceMs: Long = WAIT_FOR_SPEECH_MS,
) {
    interface Callback {
        fun partial(ticket: Long, text: String)
        fun level(ticket: Long, rmsDb: Float)
        fun heard(ticket: Long, text: String)
        fun failed(ticket: Long, failure: ListenFailure)
    }

    private var session: Any? = null
    private var startedAtMs = 0L
    private var heardSomething = false

    val isListening: Boolean get() = session != null

    fun start(ticket: Long, callback: Callback) {
        cancel()
        when {
            !hasPermission() -> callback.failed(ticket, ListenFailure.NO_PERMISSION)
            !backend.isAvailable() -> callback.failed(ticket, ListenFailure.UNAVAILABLE)
            else -> {
                startedAtMs = clockMs()
                heardSomething = false
                begin(ticket, preferOffline = !backend.hasInternet(), callback)
            }
        }
    }

    fun cancel() {
        if (session == null) return
        session = null
        backend.cancel()
    }

    fun destroy() {
        session = null
        backend.destroy()
    }

    private fun begin(ticket: Long, preferOffline: Boolean, callback: Callback) {
        val token = Any()
        session = token
        backend.start(preferOffline, object : SpeechEvents {
            private val current get() = session === token

            override fun onPartial(text: String) {
                if (!current || text.isBlank()) return
                heardSomething = true
                callback.partial(ticket, text)
            }

            override fun onLevel(rmsDb: Float) {
                if (current) callback.level(ticket, rmsDb)
            }

            override fun onFinal(text: String) {
                if (!current) return
                session = null
                when {
                    text.isNotBlank() -> callback.heard(ticket, text)
                    keepWaiting() -> begin(ticket, preferOffline, callback)
                    else -> callback.failed(ticket, ListenFailure.NOT_HEARD)
                }
            }

            override fun onError(code: Int) {
                if (!current) return
                session = null
                when {
                    preferOffline && code in OFFLINE_LANGUAGE_MISSING -> begin(ticket, preferOffline = false, callback)
                    !preferOffline && code in NETWORK_FAILED -> begin(ticket, preferOffline = true, callback)
                    failureFor(code) == ListenFailure.NOT_HEARD && keepWaiting() -> begin(ticket, preferOffline, callback)
                    else -> callback.failed(ticket, failureFor(code))
                }
            }
        })
    }

    /** Nothing heard yet and still inside the patience window: listen again instead of giving up. */
    private fun keepWaiting() = !heardSomething && clockMs() - startedAtMs < patienceMs

    companion object {
        /** How long to keep listening for someone to start talking (the system dialog waits about as long). */
        const val WAIT_FOR_SPEECH_MS = 8_000L

        private val NETWORK_FAILED = setOf(SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT,
            SpeechRecognizer.ERROR_SERVER, 11 /* ERROR_SERVER_DISCONNECTED, API 31 */)

        private val OFFLINE_LANGUAGE_MISSING = setOf(
            SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED, SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE)

        fun failureFor(code: Int): ListenFailure = when (code) {
            SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> ListenFailure.NOT_HEARD
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> ListenFailure.NO_PERMISSION
            SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED, SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE ->
                ListenFailure.UNAVAILABLE
            else -> ListenFailure.ERROR
        }
    }
}
