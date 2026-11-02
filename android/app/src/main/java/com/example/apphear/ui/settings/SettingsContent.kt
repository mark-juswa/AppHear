package com.example.apphear.ui.settings

import android.content.Context
import android.view.View
import android.widget.TextView
import androidx.core.view.isVisible
import androidx.appcompat.app.AlertDialog
import com.example.apphear.R
import com.example.apphear.data.settings.AslCharacterSettings
import com.example.apphear.domain.texttoasl.AslCharacterChoice
import com.example.apphear.ui.speech.SpeechInputHelper
import com.example.apphear.data.profile.AccountServices

class SettingsContent(private val context: Context, private val view: View) {
    private var characterDialog: AlertDialog? = null
    private var recognitionDialog: AlertDialog? = null
    private var engineDialog: AlertDialog? = null
    private var nameDialog: AlertDialog? = null

    fun render() {
        renderSettings(view)
        setupCharacterChoice(view)
        setupRecognitionChoice()
        setupRecognitionEngineChoice()
        setupRemoteConversation()
    }

    /** remoteConversation: connect a second phone, offline-only, and the name the other phone sees. */
    private fun setupRemoteConversation() {
        val group = view.findViewById<View>(R.id.remoteSettingsGroup) ?: return
        group.isVisible = com.example.apphear.remote.RemoteSession.enabled
        if (!group.isVisible) return
        val preferences = com.example.apphear.remote.RemotePreferences(context)
        val offline = view.findViewById<TextView>(R.id.remoteOfflineValue)
        val name = view.findViewById<TextView>(R.id.remoteNameValue)
        fun renderValues() {
            offline.setText(if (preferences.offlineOnly) R.string.remote_settings_on else R.string.remote_settings_off)
            name.text = preferences.displayName.ifBlank { context.getString(R.string.remote_settings_no_name) }
        }
        renderValues()
        view.findViewById<TextView>(R.id.remoteConnectValue).setText(R.string.remote_settings_open)
        view.findViewById<View>(R.id.remoteConnectRow).setOnClickListener { row ->
            androidx.navigation.Navigation.findNavController(row).navigate(R.id.textToAslFragment,
                android.os.Bundle().apply { putBoolean(com.example.apphear.TextToAslArgument.OPEN_CONNECT, true) })
        }
        view.findViewById<View>(R.id.remoteOfflineRow).setOnClickListener {
            preferences.offlineOnly = !preferences.offlineOnly
            renderValues()
        }
        view.findViewById<View>(R.id.remoteNameRow).setOnClickListener {
            val input = android.widget.EditText(context).apply {
                setText(preferences.displayName)
                setSingleLine()
                filters = arrayOf(android.text.InputFilter.LengthFilter(com.example.apphear.remote.RemotePreferences.MAX_NAME))
                inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_CAP_WORDS
            }
            nameDialog?.dismiss()
            nameDialog = AlertDialog.Builder(context).setTitle(R.string.remote_settings_name_title)
                .setView(android.widget.FrameLayout(context).apply {
                    val pad = (20 * context.resources.displayMetrics.density).toInt()
                    setPadding(pad, pad / 2, pad, 0)
                    addView(input)
                })
                .setPositiveButton(android.R.string.ok) { _, _ -> preferences.displayName = input.text.toString(); renderValues() }
                .setNegativeButton(android.R.string.cancel, null).show()
        }
    }

    /** Debug builds only: Stable (production) or Experimental live recognition. */
    private fun setupRecognitionEngineChoice() {
        val settings = com.example.apphear.data.settings.RecognitionEngineSettings(context)
        val row = view.findViewById<View>(R.id.recognitionEngineRow) ?: return
        row.isVisible = settings.selectionAvailable
        if (!settings.selectionAvailable) return
        val choices = com.example.apphear.perceptionvnext.PhoneRecognitionConfiguration.entries
        val labels = arrayOf(context.getString(R.string.recognition_engine_stable),
            context.getString(R.string.recognition_engine_experimental),
            context.getString(R.string.recognition_engine_experimental_blend),
            context.getString(R.string.recognition_engine_experimental_blend_02),
            context.getString(R.string.recognition_engine_experimental_mirror_blend),
            context.getString(R.string.recognition_engine_experimental_word_v4),
            context.getString(R.string.recognition_engine_experimental_word_v4_hybrid))
        check(labels.size == choices.size) { "one label per recognition engine" }
        val value = view.findViewById<TextView>(R.id.recognitionEngineValue)
        fun renderChoice() {
            value.text = labels[choices.indexOf(settings.current())]
            row.contentDescription = context.getString(R.string.recognition_engine_accessibility, value.text)
        }
        renderChoice()
        row.setOnClickListener {
            engineDialog?.dismiss()
            engineDialog = AlertDialog.Builder(context).setTitle(R.string.recognition_engine_title)
                .setSingleChoiceItems(labels, choices.indexOf(settings.current())) { dialog, index ->
                    settings.select(choices[index]); renderChoice(); dialog.dismiss()
                }.setNegativeButton(android.R.string.cancel, null).show()
        }
    }

    private fun setupCharacterChoice(view: View) {
        val settings = AslCharacterSettings(context)
        val row = view.findViewById<View>(R.id.aslCharacterRow)
        row.isVisible = settings.selectionAvailable
        if (!settings.selectionAvailable) return
        val choices = listOf(AslCharacterChoice.ORIGINAL, AslCharacterChoice.NEW)
        val labels = arrayOf(context.getString(R.string.asl_character_original), context.getString(R.string.asl_character_new))
        val value = view.findViewById<TextView>(R.id.aslCharacterValue)
        fun renderChoice() {
            val label = labels[choices.indexOf(settings.current())]
            value.text = label
            row.contentDescription = context.getString(R.string.asl_character_accessibility, label)
        }
        renderChoice()
        row.setOnClickListener {
            characterDialog?.dismiss()
            characterDialog = AlertDialog.Builder(context)
                .setTitle(R.string.asl_character_title)
                .setSingleChoiceItems(labels, choices.indexOf(settings.current())) { dialog, index ->
                    settings.select(choices[index])
                    renderChoice()
                    dialog.dismiss()
                }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
        }
    }

    private fun setupRecognitionChoice() {
        val settings = com.example.apphear.data.settings.RecognitionModeSettings(context)
        val row = view.findViewById<View>(R.id.recognitionModeRow)
        row.isVisible = settings.selectionAvailable
        if (!settings.selectionAvailable) return
        val choices = com.example.apphear.fingerspelling.RecognitionMode.entries
        val labels = arrayOf(context.getString(R.string.recognition_mode_word), context.getString(R.string.recognition_mode_fingerspell))
        val value = view.findViewById<TextView>(R.id.recognitionModeValue)
        fun renderChoice() {
            value.text = labels[choices.indexOf(settings.current())]
            row.contentDescription = context.getString(R.string.recognition_mode_accessibility, value.text)
        }
        renderChoice()
        row.setOnClickListener {
            recognitionDialog?.dismiss()
            recognitionDialog = AlertDialog.Builder(context).setTitle(R.string.recognition_mode_title)
                .setSingleChoiceItems(labels, choices.indexOf(settings.current())) { dialog,index ->
                    settings.select(choices[index]); renderChoice(); dialog.dismiss()
                }.setNegativeButton(android.R.string.cancel,null).show()
        }
    }

    private fun renderSettings(view: View) {
        val elevenLabsConfigured = AppConfiguration.elevenLabsConfigured
        val speechInputAvailable = SpeechInputHelper.isAvailable(context)

        val signedIn = AccountServices.enabled && AccountServices.repository(context).profile.value != null
        view.findViewById<TextView>(R.id.tvAccountType).setText(
            if (signedIn) R.string.profile_account_member else R.string.profile_account_guest)
        view.findViewById<TextView>(R.id.tvAccountBody).setText(
            if (signedIn) R.string.profile_account_member_body else if (AccountServices.enabled)
                R.string.profile_account_guest_body else R.string.profile_account_disabled_body)

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

    fun close() {
        characterDialog?.dismiss()
        characterDialog = null
        recognitionDialog?.dismiss(); recognitionDialog = null
        engineDialog?.dismiss(); engineDialog = null
        nameDialog?.dismiss(); nameDialog = null
    }
}
