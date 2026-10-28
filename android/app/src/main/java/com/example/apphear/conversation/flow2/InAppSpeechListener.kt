package com.example.apphear.conversation.flow2

import android.speech.SpeechRecognizer

/** Seam over Android's SpeechRecognizer so the listening rules can be unit-tested. Main thread only. */
interface SpeechBackend {
    fun isAvailable(): Boolean
    fun start(preferOffline: Boolean, events: SpeechEvents)
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
 * Offline recognition is tried first; if the phone lacks the offline language it retries once
 * online. A missing permission or recognizer is reported as such so the caller can fall back to
 * the existing system speech dialog.
 */
class InAppSpeechListener(
    private val backend: SpeechBackend,
    private val hasPermission: () -> Boolean,
) {
    interface Callback {
        fun partial(ticket: Long, text: String)
        fun level(ticket: Long, rmsDb: Float)
        fun heard(ticket: Long, text: String)
        fun failed(ticket: Long, failure: ListenFailure)
    }

    private var session: Any? = null

    val isListening: Boolean get() = session != null

    fun start(ticket: Long, callback: Callback) {
        cancel()
        when {
            !hasPermission() -> callback.failed(ticket, ListenFailure.NO_PERMISSION)
            !backend.isAvailable() -> callback.failed(ticket, ListenFailure.UNAVAILABLE)
            else -> begin(ticket, preferOffline = true, callback)
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
                if (current && text.isNotBlank()) callback.partial(ticket, text)
            }

            override fun onLevel(rmsDb: Float) {
                if (current) callback.level(ticket, rmsDb)
            }

            override fun onFinal(text: String) {
                if (!current) return
                session = null
                if (text.isBlank()) callback.failed(ticket, ListenFailure.NOT_HEARD) else callback.heard(ticket, text)
            }

            override fun onError(code: Int) {
                if (!current) return
                session = null
                if (preferOffline && code in OFFLINE_LANGUAGE_MISSING) {
                    begin(ticket, preferOffline = false, callback)
                } else callback.failed(ticket, failureFor(code))
            }
        })
    }

    companion object {
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
