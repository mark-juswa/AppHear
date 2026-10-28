package com.example.apphear.conversation.flow2

import android.speech.SpeechRecognizer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InAppSpeechListenerTest {
    private class FakeBackend(var available: Boolean = true) : SpeechBackend {
        val starts = mutableListOf<Boolean>()
        var events: SpeechEvents? = null
        var cancels = 0
        var destroyed = false
        override fun isAvailable() = available
        override fun start(preferOffline: Boolean, events: SpeechEvents) {
            starts += preferOffline
            this.events = events
        }
        override fun cancel() { cancels++ }
        override fun destroy() { destroyed = true }
    }

    private class Recorder : InAppSpeechListener.Callback {
        val log = mutableListOf<String>()
        override fun partial(ticket: Long, text: String) { log += "partial $ticket $text" }
        override fun level(ticket: Long, rmsDb: Float) { log += "level $ticket" }
        override fun heard(ticket: Long, text: String) { log += "heard $ticket $text" }
        override fun failed(ticket: Long, failure: ListenFailure) { log += "failed $ticket $failure" }
    }

    private val backend = FakeBackend()
    private var permitted = true
    private val listener = InAppSpeechListener(backend) { permitted }
    private val recorder = Recorder()

    @Test fun `partial then final result are reported with the ticket`() {
        listener.start(4, recorder)
        assertEquals(listOf(true), backend.starts)
        assertTrue(listener.isListening)
        backend.events!!.onPartial("hello")
        backend.events!!.onPartial("  ")
        backend.events!!.onLevel(3f)
        backend.events!!.onFinal("hello there")
        assertEquals(listOf("partial 4 hello", "level 4", "heard 4 hello there"), recorder.log)
        assertFalse(listener.isListening)
    }

    @Test fun `empty final result is not heard`() {
        listener.start(1, recorder)
        backend.events!!.onFinal(" ")
        assertEquals(listOf("failed 1 NOT_HEARD"), recorder.log)
    }

    @Test fun `missing permission or recognizer is reported without starting`() {
        permitted = false
        listener.start(1, recorder)
        permitted = true
        backend.available = false
        listener.start(2, recorder)
        assertEquals(listOf("failed 1 NO_PERMISSION", "failed 2 UNAVAILABLE"), recorder.log)
        assertTrue(backend.starts.isEmpty())
    }

    @Test fun `missing offline language retries online once`() {
        listener.start(7, recorder)
        backend.events!!.onError(SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE)
        assertEquals(listOf(true, false), backend.starts)
        assertTrue(recorder.log.isEmpty())

        backend.events!!.onError(SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE)
        assertEquals(listOf("failed 7 UNAVAILABLE"), recorder.log)
        assertEquals(2, backend.starts.size)
    }

    @Test fun `events after cancel or from an earlier session are ignored`() {
        listener.start(1, recorder)
        val old = backend.events!!
        listener.cancel()
        assertEquals(1, backend.cancels)
        old.onFinal("late")
        old.onError(SpeechRecognizer.ERROR_CLIENT)

        listener.start(2, recorder)
        old.onPartial("stale")
        backend.events!!.onFinal("fresh")
        assertEquals(listOf("heard 2 fresh"), recorder.log)
    }

    @Test fun `starting again cancels the running session`() {
        listener.start(1, recorder)
        listener.start(2, recorder)
        assertEquals(1, backend.cancels)
    }

    @Test fun `cancel without a session does nothing and destroy releases the recognizer`() {
        listener.cancel()
        assertEquals(0, backend.cancels)
        listener.destroy()
        assertTrue(backend.destroyed)
    }

    @Test fun `recognizer errors map to the flow's failures`() {
        assertEquals(ListenFailure.NOT_HEARD, InAppSpeechListener.failureFor(SpeechRecognizer.ERROR_NO_MATCH))
        assertEquals(ListenFailure.NOT_HEARD, InAppSpeechListener.failureFor(SpeechRecognizer.ERROR_SPEECH_TIMEOUT))
        assertEquals(ListenFailure.NO_PERMISSION,
            InAppSpeechListener.failureFor(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS))
        assertEquals(ListenFailure.UNAVAILABLE,
            InAppSpeechListener.failureFor(SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED))
        assertEquals(ListenFailure.ERROR, InAppSpeechListener.failureFor(SpeechRecognizer.ERROR_NETWORK))
        assertEquals(ListenFailure.ERROR, InAppSpeechListener.failureFor(SpeechRecognizer.ERROR_AUDIO))
    }

    @Test fun `other errors are reported directly`() {
        listener.start(3, recorder)
        backend.events!!.onError(SpeechRecognizer.ERROR_NETWORK)
        assertEquals(listOf("failed 3 ERROR"), recorder.log)
        assertEquals(1, backend.starts.size)
    }
}
