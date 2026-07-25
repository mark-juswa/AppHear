package com.example.apphear.ui.settings

import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.example.apphear.R
import com.example.apphear.ui.speech.SpeechInputHelper

class SettingsFragment : Fragment(R.layout.fragment_settings) {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        renderSettings(view)
    }

    private fun renderSettings(view: View) {
        val supabaseConfigured = AppConfiguration.supabaseConfigured
        val elevenLabsConfigured = AppConfiguration.elevenLabsConfigured
        val speechInputAvailable = SpeechInputHelper.isAvailable(requireContext())

        view.findViewById<TextView>(R.id.tvAccountType).text =
            if (supabaseConfigured) "Supabase" else "Guest"
        view.findViewById<TextView>(R.id.tvAccountBody).text =
            if (supabaseConfigured) {
                "Remote profile config is present for ${AppConfiguration.supabaseHost}. Auth UI can be enabled after schema/RLS verification."
            } else {
                "Remote profile config is missing. The app stays in guest/local mode."
            }

        view.findViewById<TextView>(R.id.tvVoiceValue).text =
            if (elevenLabsConfigured) "ElevenLabs" else "Android TTS"
        view.findViewById<TextView>(R.id.tvVoiceBody).text =
            if (elevenLabsConfigured) {
                "Cloud voice is configured; Android TextToSpeech remains the fallback."
            } else {
                "Android TextToSpeech is active because ElevenLabs is not configured."
            }

        view.findViewById<TextView>(R.id.tvSpeechInputValue).text =
            if (speechInputAvailable) "Available" else "Unavailable"
        view.findViewById<TextView>(R.id.tvSpeechInputBody).text =
            if (speechInputAvailable) {
                "Text-to-ASL can use the device speech recognizer."
            } else {
                "No compatible Android speech recognizer was found on this device."
            }

        view.findViewById<TextView>(R.id.tvPrivacyValue).text = "Protected"
        view.findViewById<TextView>(R.id.tvPrivacyBody).text =
            "Camera frames, landmarks, temporal buffers, confirmation, and model inference stay in the AppHear3 on-device runtime."

        view.findViewById<TextView>(R.id.tvAboutValue).text = "AppHear3"
        view.findViewById<TextView>(R.id.tvAboutBody).text =
            "Native Kotlin/XML app shell with protected CameraX, MediaPipe, and TFLite recognition."
    }
}