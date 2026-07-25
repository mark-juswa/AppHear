package com.example.apphear.ui.speech

import android.content.Context
import android.content.Intent
import android.speech.RecognizerIntent
import java.util.Locale

object SpeechInputHelper {
    fun createSpeechIntent(prompt: String): Intent {
        return Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US.toString())
            putExtra(RecognizerIntent.EXTRA_PROMPT, prompt)
        }
    }

    fun isAvailable(context: Context): Boolean {
        return createSpeechIntent(prompt = "").resolveActivity(context.packageManager) != null
    }
}
