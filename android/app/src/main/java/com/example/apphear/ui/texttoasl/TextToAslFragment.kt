package com.example.apphear.ui.texttoasl

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognizerIntent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.navigation.fragment.findNavController
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.TextToAslArgument
import com.example.apphear.databinding.FragmentTextToAslBinding
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.example.apphear.ui.speech.AppHearSpeechPlayer
import com.example.apphear.ui.speech.SpeechInputHelper
import java.util.Locale

class TextToAslFragment : Fragment(R.layout.fragment_text_to_asl) {
    private var binding: FragmentTextToAslBinding? = null
    private var animationCatalog: AslAnimationCatalog? = null
    private var phrasePlanner: AslPhrasePlanner? = null
    private var avatarController: TextToAslPlaybackController? = null
    private var idleAsset: AslAnimationAsset? = null
    private var currentQueue: List<AslAnimationAsset> = emptyList()
    private var currentIndex: Int = 0
    private var lastInputText: String = ""
    private var speechPlayer: AppHearSpeechPlayer? = null
    private var avatarReady: Boolean = false
    private var pendingAutoSubmitText: String? = null
    private var consumedAutoSubmitText: String? = null

    private val speechLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val fragmentBinding = binding ?: return@registerForActivityResult
        if (result.resultCode == Activity.RESULT_OK) {
            val matches = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            val spokenText = matches?.firstOrNull()?.trim().orEmpty()
            if (spokenText.isNotEmpty()) {
                fragmentBinding.tvSpeechStatus.text = spokenText
                fragmentBinding.inputText.setText(spokenText)
                submitInput()
                return@registerForActivityResult
            }
        }
        fragmentBinding.tvSpeechStatus.setText(R.string.speech_tap_mic)
    }

    private val playHandler = Handler(Looper.getMainLooper())
    private val advanceRunnable = Runnable {
        advancePlayback()
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val fragmentBinding = FragmentTextToAslBinding.bind(view)
        binding = fragmentBinding
        speechPlayer = AppHearSpeechPlayer(requireContext())
        pendingAutoSubmitText = savedInstanceState?.getString(KEY_PENDING_AUTO_SUBMIT_TEXT)
            ?: arguments?.getString(TextToAslArgument.INCOMING_TEXT)?.trim()?.takeIf { it.isNotBlank() }
        consumedAutoSubmitText = savedInstanceState?.getString(KEY_CONSUMED_AUTO_SUBMIT_TEXT)

        setupTextToAslEngine(fragmentBinding)
        setupListeners(fragmentBinding)
    }

    private fun setupTextToAslEngine(fragmentBinding: FragmentTextToAslBinding) {
        try {
            val catalog = AndroidAssetAslCatalogLoader(requireContext()).load()
            animationCatalog = catalog
            phrasePlanner = AslPhrasePlanner(catalog)
            idleAsset = catalog.findByAlias("idle")
            avatarController = TextToAslPlaybackController(requireContext(), fragmentBinding.avatarWebView).also { controller ->
                controller.setReadyCallback(
                    object : TextToAslPlaybackController.ReadyCallback {
                        override fun onReady() {
                            binding?.avatarPlaceholder?.isVisible = false
                            binding?.currentProgressText?.text = "Ready"
                            avatarReady = true
                            showIdleAvatar()
                            consumePendingAutoSubmitIfReady()
                        }
                    },
                )
                controller.setPlaybackCallback(
                    object : TextToAslPlaybackController.PlaybackCallback {
                        override fun onFinished(asset: AslAnimationAsset) {
                            if (currentQueue.getOrNull(currentIndex)?.id == asset.id) {
                                advancePlayback()
                            }
                        }
                    },
                )
            }
        } catch (exception: Exception) {
            fragmentBinding.avatarPlaceholder.isVisible = true
            fragmentBinding.avatarPlaceholder.text = "Avatar assets unavailable"
            fragmentBinding.currentProgressText.text = "Animation catalog failed to load"
            avatarReady = false
            Toast.makeText(requireContext(), "Failed to load ASL animations.", Toast.LENGTH_LONG).show()
        }
    }

    private fun setupListeners(fragmentBinding: FragmentTextToAslBinding) {
        fragmentBinding.btnBack.setOnClickListener { findNavController().navigate(R.id.homeFragment) }
        fragmentBinding.btnSpeak.setOnClickListener { speakCurrentText() }
        fragmentBinding.dragHandleWrapper.setOnClickListener {
            fragmentBinding.expandableContent.isVisible = !fragmentBinding.expandableContent.isVisible
        }
        fragmentBinding.signItButton.setOnClickListener { submitInput() }
        fragmentBinding.btnMic.setOnClickListener { startSpeechInput() }
        fragmentBinding.replayButton.setOnClickListener { replayCurrentPlan() }
        fragmentBinding.clearButton.setOnClickListener { clearPlayback() }
        fragmentBinding.replyButton.setOnClickListener {
            startActivity(Intent(requireContext(), RecognitionActivity::class.java))
        }
        fragmentBinding.modeTextButton.setOnClickListener { setSpeechMode(false) }
        fragmentBinding.modeSpeechButton.setOnClickListener { setSpeechMode(true) }
        fragmentBinding.inputText.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE) {
                submitInput()
                true
            } else {
                false
            }
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(KEY_PENDING_AUTO_SUBMIT_TEXT, pendingAutoSubmitText)
        outState.putString(KEY_CONSUMED_AUTO_SUBMIT_TEXT, consumedAutoSubmitText)
    }

    private fun consumePendingAutoSubmitIfReady() {
        val fragmentBinding = binding ?: return
        val incomingText = pendingAutoSubmitText?.trim()?.takeIf { it.isNotBlank() } ?: return
        if (!avatarReady || phrasePlanner == null || avatarController == null) return
        if (incomingText == consumedAutoSubmitText) {
            pendingAutoSubmitText = null
            return
        }

        fragmentBinding.inputText.setText(incomingText)
        fragmentBinding.signedText.text = incomingText
        consumedAutoSubmitText = incomingText
        pendingAutoSubmitText = null
        submitInput()
    }

    private fun startSpeechInput() {
        val fragmentBinding = binding ?: return
        if (!SpeechInputHelper.isAvailable(requireContext())) {
            fragmentBinding.tvSpeechStatus.setText(R.string.speech_unavailable)
            Toast.makeText(requireContext(), R.string.speech_unavailable, Toast.LENGTH_SHORT).show()
            return
        }
        fragmentBinding.tvSpeechStatus.setText(R.string.speech_listening)
        try {
            speechLauncher.launch(SpeechInputHelper.createSpeechIntent(getString(R.string.text_to_asl_speech_prompt)))
        } catch (_: ActivityNotFoundException) {
            fragmentBinding.tvSpeechStatus.setText(R.string.speech_unavailable)
            Toast.makeText(requireContext(), R.string.speech_unavailable, Toast.LENGTH_SHORT).show()
        }
    }

    private fun speakCurrentText() {
        val fragmentBinding = binding ?: return
        val speakableText = lastInputText
            .ifBlank { fragmentBinding.inputText.text?.toString()?.trim().orEmpty() }
            .ifBlank {
                fragmentBinding.signedText.text?.toString()?.trim().orEmpty()
                    .takeUnless { it == getString(R.string.text_to_asl_idle_text) }
                    .orEmpty()
            }
        if (speakableText.isBlank()) {
            Toast.makeText(requireContext(), R.string.speech_no_text_to_speak, Toast.LENGTH_SHORT).show()
            return
        }
        speechPlayer?.speak(speakableText)
    }

    private fun submitInput() {
        val fragmentBinding = binding ?: return
        val requestedText = fragmentBinding.inputText.text?.toString()?.trim().orEmpty()
        if (requestedText.isEmpty()) {
            fragmentBinding.currentProgressText.setText(R.string.text_to_asl_empty_warning)
            return
        }

        val planner = phrasePlanner
        if (planner == null) {
            fragmentBinding.currentProgressText.text = "Animation catalog unavailable"
            return
        }

        playHandler.removeCallbacks(advanceRunnable)
        val plan = planner.plan(requestedText)
        lastInputText = requestedText
        currentQueue = plan.queue
        currentIndex = 0
        fragmentBinding.signedText.text = requestedText

        if (plan.unsupportedTokens.isNotEmpty()) {
            fragmentBinding.currentProgressText.text = "Unsupported: ${plan.unsupportedTokens.joinToString(", ")}"
        }

        if (currentQueue.isEmpty()) {
            fragmentBinding.currentSignText.setText(R.string.text_to_asl_current_sign_placeholder)
            if (plan.unsupportedTokens.isEmpty()) {
                fragmentBinding.currentProgressText.setText(R.string.text_to_asl_no_animation)
            }
            showIdleAvatar()
            return
        }

        playCurrentAsset()
    }

    private fun replayCurrentPlan() {
        val fragmentBinding = binding ?: return
        if (currentQueue.isEmpty()) {
            if (lastInputText.isEmpty()) {
                fragmentBinding.currentProgressText.setText(R.string.text_to_asl_empty_warning)
            } else {
                submitInput()
            }
            return
        }
        playHandler.removeCallbacks(advanceRunnable)
        currentIndex = 0
        playCurrentAsset()
    }

    private fun clearPlayback() {
        val fragmentBinding = binding ?: return
        playHandler.removeCallbacks(advanceRunnable)
        currentQueue = emptyList()
        currentIndex = 0
        lastInputText = ""
        fragmentBinding.inputText.text?.clear()
        fragmentBinding.signedText.setText(R.string.text_to_asl_idle_text)
        fragmentBinding.currentSignText.setText(R.string.text_to_asl_current_sign_placeholder)
        fragmentBinding.currentProgressText.text = "Ready"
        showIdleAvatar()
    }

    private fun playCurrentAsset() {
        val fragmentBinding = binding ?: return
        val asset = currentQueue.getOrNull(currentIndex) ?: return
        avatarController?.play(asset)
        currentQueue.getOrNull(currentIndex + 1)?.let { avatarController?.preload(it) }

        fragmentBinding.currentSignText.text = asset.displayText.uppercase(Locale.US)
        fragmentBinding.currentProgressText.text = "${currentIndex + 1} / ${currentQueue.size}"

        playHandler.removeCallbacks(advanceRunnable)
        playHandler.postDelayed(advanceRunnable, PLAYBACK_SAFETY_TIMEOUT_MS)
    }

    private fun advancePlayback() {
        playHandler.removeCallbacks(advanceRunnable)
        currentIndex++
        if (currentIndex < currentQueue.size) {
            playCurrentAsset()
        } else {
            showIdleAvatar()
        }
    }

    private fun showIdleAvatar() {
        playHandler.removeCallbacks(advanceRunnable)
        avatarController?.play(idleAsset)
        binding?.currentSignText?.setText(R.string.text_to_asl_current_sign_placeholder)
        if (currentQueue.isNotEmpty()) {
            binding?.currentProgressText?.text = "Complete"
        }
    }

    private fun setSpeechMode(enabled: Boolean) {
        val fragmentBinding = binding ?: return
        fragmentBinding.textInputSection.isVisible = !enabled
        fragmentBinding.speechDeferredSection.isVisible = enabled
        if (enabled) fragmentBinding.tvSpeechStatus.setText(R.string.speech_tap_mic)
        fragmentBinding.modeTextButton.setBackgroundResource(
            if (enabled) R.drawable.bg_toggle_inactive else R.drawable.bg_toggle_active,
        )
        fragmentBinding.modeSpeechButton.setBackgroundResource(
            if (enabled) R.drawable.bg_toggle_active else R.drawable.bg_toggle_inactive,
        )
        fragmentBinding.modeTextLabel.setTextColor(
            resources.getColor(
                if (enabled) R.color.color_action_dark else R.color.white,
                requireContext().theme,
            ),
        )
        fragmentBinding.modeSpeechLabel.setTextColor(
            resources.getColor(
                if (enabled) R.color.white else R.color.color_action_dark,
                requireContext().theme,
            ),
        )
    }

    override fun onDestroyView() {
        playHandler.removeCallbacks(advanceRunnable)
        avatarController?.destroy()
        avatarController = null
        avatarReady = false
        speechPlayer?.close()
        speechPlayer = null
        binding = null
        super.onDestroyView()
    }

    private companion object {
        // The imported batch tops out at about 5.71 seconds. The model-viewer completion event
        // normally advances immediately; this only prevents a malformed asset from stalling forever.
        const val PLAYBACK_SAFETY_TIMEOUT_MS = 7_000L
        const val KEY_PENDING_AUTO_SUBMIT_TEXT = "pending_auto_submit_text"
        const val KEY_CONSUMED_AUTO_SUBMIT_TEXT = "consumed_auto_submit_text"
    }
}