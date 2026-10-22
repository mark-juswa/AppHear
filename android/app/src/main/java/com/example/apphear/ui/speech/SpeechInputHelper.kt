package com.example.apphear.ui.speech

import android.content.Context
import android.content.Intent
import android.speech.RecognizerIntent
import com.example.apphear.conversation.ConversationScreens
import java.util.Locale

object SpeechInputHelper {
    /** conversationFlowV1: ask the recognizer to finish after this much silence. */
    private const val END_OF_SPEECH_SILENCE_MS = 1_500L

    fun createSpeechIntent(prompt: String): Intent {
        return Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US.toString())
            putExtra(RecognizerIntent.EXTRA_PROMPT, prompt)
            if (ConversationScreens.oneTapTalk) {
                // A request only: the system speech screen may ignore these and use its own timing.
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, END_OF_SPEECH_SILENCE_MS)
                putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS,
                    END_OF_SPEECH_SILENCE_MS)
            }
        }
    }

    fun isAvailable(context: Context): Boolean {
        return createSpeechIntent(prompt = "").resolveActivity(context.packageManager) != null
    }
}
