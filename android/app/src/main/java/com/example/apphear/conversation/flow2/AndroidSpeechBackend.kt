package com.example.apphear.conversation.flow2

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import com.example.apphear.ui.speech.SpeechInputHelper
import java.util.Locale

/** [SpeechBackend] on Android's SpeechRecognizer. Create, use and destroy on the main thread. */
class AndroidSpeechBackend(private val context: Context) : SpeechBackend {
    private var recognizer: SpeechRecognizer? = null

    /**
     * Picks the final text from the recognizer's alternatives (most likely first). Null keeps the first;
     * the guided demo sets it to prefer an alternative that matches its questions.
     */
    var pickResult: ((List<String>) -> String)? = null

    override fun hasInternet(): Boolean {
        val connectivity = context.getSystemService(android.net.ConnectivityManager::class.java) ?: return false
        val capabilities = connectivity.getNetworkCapabilities(connectivity.activeNetwork) ?: return false
        return capabilities.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    override fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    override fun start(preferOffline: Boolean, events: SpeechEvents) {
        val target = recognizer ?: SpeechRecognizer.createSpeechRecognizer(context).also { recognizer = it }
        target.setRecognitionListener(object : RecognitionListener {
            override fun onPartialResults(partialResults: Bundle?) = events.onPartial(first(partialResults))
            override fun onResults(results: Bundle?) = events.onFinal(chosen(results))
            override fun onError(error: Int) = events.onError(error)
            override fun onRmsChanged(rmsdB: Float) = events.onLevel(rmsdB)
            override fun onReadyForSpeech(params: Bundle?) = Unit
            override fun onBeginningOfSpeech() = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit
            override fun onEndOfSpeech() = Unit
            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })
        target.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US.toString())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, preferOffline)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
            // Requests only; the recognizer may use its own end-of-speech timing.
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS,
                SpeechInputHelper.END_OF_SPEECH_SILENCE_MS)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS,
                SpeechInputHelper.END_OF_SPEECH_SILENCE_MS)
        })
    }

    override fun cancel() {
        recognizer?.cancel()
    }

    override fun destroy() {
        recognizer?.destroy()
        recognizer = null
    }

    private fun chosen(bundle: Bundle?): String {
        val all = bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty().filter { it.isNotBlank() }
        if (all.isEmpty()) return ""
        return pickResult?.invoke(all)?.takeIf { it in all } ?: all.first()
    }

    private fun first(bundle: Bundle?): String =
        bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
}
