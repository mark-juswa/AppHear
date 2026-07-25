package com.example.apphear.ui.speech

import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import java.util.Locale

object TtsVoiceHelper {
    fun applyNaturalEnglishVoice(tts: TextToSpeech) {
        val languageResult = tts.setLanguage(Locale.US)
        if (
            languageResult == TextToSpeech.LANG_MISSING_DATA ||
            languageResult == TextToSpeech.LANG_NOT_SUPPORTED
        ) {
            return
        }

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) return

        findBestVoice(tts.voices)?.let { tts.voice = it }
    }

    private fun findBestVoice(voices: Set<Voice>?): Voice? {
        if (voices.isNullOrEmpty()) return null

        return voices
            .filter { voice -> voice.locale?.language.equals("en", ignoreCase = true) }
            .maxByOrNull(::scoreVoice)
    }

    private fun scoreVoice(voice: Voice): Int {
        val country = voice.locale?.country.orEmpty()
        val name = voice.name.orEmpty().lowercase(Locale.US)

        var score = 0
        if (country.equals("US", ignoreCase = true)) score += 100
        score += voice.quality * 20
        score -= voice.latency * 3
        if (voice.isNetworkConnectionRequired) score += 35
        if ("enhanced" in name) score += 30
        if ("premium" in name) score += 30
        if ("natural" in name) score += 30
        if ("female" in name) score += 8
        if ("local" in name) score += 5
        return score
    }
}
