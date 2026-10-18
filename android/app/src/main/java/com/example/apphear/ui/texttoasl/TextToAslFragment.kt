package com.example.apphear.ui.texttoasl

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.speech.RecognizerIntent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.navigation.fragment.findNavController
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.Lifecycle
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.TextToAslArgument
import com.example.apphear.databinding.FragmentTextToAslBinding
import com.example.apphear.contextassist.ConversationPhraseAssist
import com.example.apphear.contextassist.ConversationSource
import com.example.apphear.domain.texttoasl.AslSingleAvatarPolicy
import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.example.apphear.domain.texttoasl.AslResidentAvatarBundle
import com.example.apphear.domain.texttoasl.AslCharacterChoice
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.example.apphear.domain.texttoasl.SignDictionaryMetadata
import com.example.apphear.domain.texttoasl.AslTranslationPlanner
import com.example.apphear.domain.texttoasl.AslGrammarRegistry
import com.example.apphear.ui.speech.AppHearSpeechPlayer
import com.example.apphear.ui.speech.SpeechInputHelper
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job

class TextToAslFragment : Fragment(R.layout.fragment_text_to_asl) {
    private var binding: FragmentTextToAslBinding? = null
    private var animationCatalog: AslAnimationCatalog? = null
    private var phrasePlanner: AslPhrasePlanner? = null
    private var translationPlanner: AslTranslationPlanner? = null
    private var avatarController: TextToAslPlaybackController? = null
    private var idleAsset: AslAnimationAsset? = null
    private var currentQueue: List<AslAnimationAsset> = emptyList()
    private var unsupportedWords: List<String> = emptyList()
    private var currentIndex: Int = 0
    private var lastInputText: String = ""
    private var translationNotice: String? = null
    private var speechPlayer: AppHearSpeechPlayer? = null
    private var avatarReady: Boolean = false
    private var queuedSubmitUntilReady: Boolean = false
    private var queuedSubmitSource: ConversationSource = ConversationSource.TYPED_TEXT
    private var queuedSubmitRecordTurn: Boolean = true
    private var resumeColdIdle: Boolean = false
    private var pendingAutoSubmitText: String? = null
    private var consumedAutoSubmitText: String? = null
    private var activeCharacter: AslCharacterChoice? = null
    private var engineJob: Job? = null

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
                submitInput(ConversationSource.SPEECH)
                return@registerForActivityResult
            }
        }
        fragmentBinding.tvSpeechStatus.setText(R.string.speech_tap_mic)
    }

    private val playHandler = Handler(Looper.getMainLooper())
    private val advanceRunnable = Runnable {
        if (BuildConfig.ASL_ASSET_PILOT_ENABLED) {
            failPlayback("Playback stopped responding. Tap Repeat to retry.")
        } else {
            advancePlayback()
        }
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
        // Keep existing settings/storage intact; this module uses one human avatar only.
        val choice = AslSingleAvatarPolicy.choice
        if (activeCharacter != null && activeCharacter != choice) {
            resetQueueForCharacterChange(fragmentBinding)
        }
        activeCharacter = choice
        engineJob?.cancel()
        engineJob = viewLifecycleOwner.lifecycleScope.launch {
            try {
                require(BuildConfig.ASL_ASSET_PILOT_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED) {
                    "Single human avatar requires the existing OriginalWords build configuration"
                }
                val appContext = requireContext().applicationContext
                val profile = if (choice == AslCharacterChoice.NEW) SignDictionaryMetadata.AvatarProfile.NEW_HUMAN
                    else SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN
                avatarController = TextToAslPlaybackController(requireContext(), fragmentBinding.avatarWebView, profile).also { controller ->
                    controller.setReadyCallback(
                        object : TextToAslPlaybackController.ReadyCallback {
                            override fun onReady() {
                                val loadingNewIdle = BuildConfig.ASL_NEW_IDLE_ENABLED &&
                                    choice == AslCharacterChoice.NEW
                                binding?.avatarPlaceholder?.isVisible = loadingNewIdle
                                if (loadingNewIdle) {
                                    binding?.avatarPlaceholder?.setText(R.string.asl_character_loading)
                                }
                                binding?.currentProgressText?.text = "Ready"
                                avatarReady = !BuildConfig.ASL_ASSET_PILOT_ENABLED
                                if (!BuildConfig.ASL_ASSET_PILOT_ENABLED ||
                                    viewLifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
                                    showIdleAvatar()
                                    consumePendingAutoSubmitIfReady()
                                }
                            }
                        },
                    )
                    controller.setPlaybackCallback(
                        object : TextToAslPlaybackController.PlaybackCallback {
                            override fun onStarted(asset: AslAnimationAsset) {
                                if (BuildConfig.ASL_NEW_IDLE_ENABLED && activeCharacter == AslCharacterChoice.NEW) {
                                    binding?.avatarPlaceholder?.isVisible = false
                                }
                                if (BuildConfig.ASL_ASSET_PILOT_ENABLED && asset.id == "idle" && !avatarReady) {
                                    avatarReady = true
                                    resumeColdIdle = false
                                    if (queuedSubmitUntilReady) {
                                        queuedSubmitUntilReady = false
                                        submitInput(queuedSubmitSource, queuedSubmitRecordTurn)
                                    } else {
                                        consumePendingAutoSubmitIfReady()
                                    }
                                }
                                if (!BuildConfig.ASL_ASSET_PILOT_ENABLED ||
                                    currentQueue.getOrNull(currentIndex)?.id != asset.id) return
                                playHandler.removeCallbacks(advanceRunnable)
                                val timeout = asset.replacement?.durationMs?.plus(2_000L)
                                    ?: PLAYBACK_SAFETY_TIMEOUT_MS
                                playHandler.postDelayed(advanceRunnable, timeout)
                            }

                            override fun onFailed(asset: AslAnimationAsset) {
                                if (asset.id == "idle") {
                                    binding?.currentProgressText?.text = "Selected avatar unavailable. Tap Repeat to retry."
                                    avatarReady = false
                                }
                                if (currentQueue.getOrNull(currentIndex)?.id == asset.id) {
                                    failPlayback("Unable to play " + asset.displayText + ". Tap Repeat to retry.")
                                }
                            }

                            override fun onFinished(asset: AslAnimationAsset) {
                                if (currentQueue.getOrNull(currentIndex)?.id == asset.id) {
                                    advancePlayback()
                                }
                            }
                        },
                    )
                }
                // Start the viewer and the resident avatar download while the catalog verifies.
                avatarController?.warmUp(if (BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED) AslFingerspellingBundle.PATH
                    else AslResidentAvatarBundle.PATH)
                val catalogStartMs = SystemClock.elapsedRealtime()
                val (catalog, grammar) = withContext(Dispatchers.IO) {
                    AndroidAssetAslCatalogLoader(appContext, choice == AslCharacterChoice.NEW).load() to
                        if (BuildConfig.ASL_ASSET_PILOT_ENABLED) AndroidAslGrammarLoader(appContext).load()
                        else AslGrammarRegistry(enabled = false)
                }
                if (binding !== fragmentBinding) return@launch
                animationCatalog = catalog
                phrasePlanner = AslPhrasePlanner(catalog,
                    completeWordFallback = BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED,
                    dictionarySequenceMode = BuildConfig.ASL_ASSET_PILOT_ENABLED)
                translationPlanner = AslTranslationPlanner(catalog, grammar, requireNotNull(phrasePlanner))
                idleAsset = catalog.findByAlias("idle")
                Log.d("TextToAslAssets", "Character=${choice.preferenceValue} entries=${catalog.getAssets().size} " +
                    "catalogMs=${SystemClock.elapsedRealtime() - catalogStartMs}")
                // The viewer may already be ready; the idle pose needed the catalog.
                if (avatarController?.isReady == true &&
                    viewLifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
                    showIdleAvatar()
                    consumePendingAutoSubmitIfReady()
                }
            } catch (exception: Exception) {
                if (exception is CancellationException) throw exception
                if (binding !== fragmentBinding) return@launch
                fragmentBinding.avatarPlaceholder.isVisible = true
                fragmentBinding.avatarPlaceholder.text = "Avatar assets unavailable"
                fragmentBinding.currentProgressText.text = "Animation catalog failed to load"
                avatarReady = false
                Toast.makeText(requireContext(), "Failed to load ASL animations.", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun setupListeners(fragmentBinding: FragmentTextToAslBinding) {
        fragmentBinding.btnBack.setOnClickListener { findNavController().navigate(R.id.homeFragment) }
        fragmentBinding.btnSpeak.setOnClickListener { speakCurrentText() }
        fragmentBinding.dragHandleWrapper.setOnClickListener {
            showInputPanel(!fragmentBinding.expandableContent.isVisible)
        }
        fragmentBinding.signItButton.setOnClickListener {
            if (fragmentBinding.speechDeferredSection.isVisible) replayCurrentPlan() else submitInput()
        }
        fragmentBinding.btnMic.setOnClickListener { startSpeechInput() }
        fragmentBinding.replayButton.setOnClickListener { replayCurrentPlan() }
        fragmentBinding.clearButton.setOnClickListener { clearPlayback() }
        fragmentBinding.replyButton.setOnClickListener {
            startActivity(Intent(requireContext(), RecognitionActivity::class.java))
        }
        fragmentBinding.modeTextButton.setOnClickListener { setSpeechMode(false) }
        fragmentBinding.modeSpeechButton.setOnClickListener { setSpeechMode(true) }
        fragmentBinding.signedText.setOnClickListener {
            if (!fragmentBinding.expandableContent.isVisible) setSpeechMode(false)
        }
        fragmentBinding.modeTextShortcut.setOnClickListener { setSpeechMode(false) }
        fragmentBinding.modeTalkShortcut.setOnClickListener { setSpeechMode(true) }
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
        fragmentBinding.signedText.isVisible = true
        consumedAutoSubmitText = incomingText
        pendingAutoSubmitText = null
        submitInput(ConversationSource.SPEECH)
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

    private fun submitInput(
        source: ConversationSource = ConversationSource.TYPED_TEXT,
        recordTurn: Boolean = true,
    ) {
        val fragmentBinding = binding ?: return
        val requestedText = fragmentBinding.inputText.text?.toString()?.trim().orEmpty()
        if (requestedText.isEmpty()) {
            fragmentBinding.currentProgressText.setText(R.string.text_to_asl_empty_warning)
            return
        }

        if (BuildConfig.ASL_ASSET_PILOT_ENABLED && !avatarReady) {
            queuedSubmitUntilReady = true
            queuedSubmitSource = source
            queuedSubmitRecordTurn = recordTurn
            fragmentBinding.currentProgressText.setText(R.string.asl_character_loading)
            avatarController?.let { if (it.isReady) showIdleAvatar() }
            return
        }

        val planner = phrasePlanner
        if (planner == null) {
            fragmentBinding.currentProgressText.text = "Animation catalog unavailable"
            return
        }

        playHandler.removeCallbacks(advanceRunnable)
        avatarController?.pause() // Invalidate the old request before replacing its queue.
        val plan = if (BuildConfig.ASL_ASSET_PILOT_ENABLED) translationPlanner?.plan(requestedText)
            ?: planner.plan(requestedText) else planner.plan(requestedText)
        translationNotice = plan.translationNotice
        if (recordTurn) ConversationPhraseAssist.recordHearingMessage(
            requireContext().applicationContext, requestedText, source)
        lastInputText = requestedText
        currentQueue = plan.queue
        unsupportedWords = plan.unsupportedTokens
        currentIndex = 0
        fragmentBinding.signedText.text = requestedText
        fragmentBinding.signedText.isVisible = true

        if (plan.unsupportedTokens.isNotEmpty()) {
            fragmentBinding.currentProgressText.text = "Unsupported: ${plan.unsupportedTokens.joinToString(", ")}"
        }

        if (currentQueue.isEmpty()) {
            fragmentBinding.currentSignText.setText(R.string.text_to_asl_current_sign_placeholder)
            if (translationNotice != null) {
                fragmentBinding.currentProgressText.text = progressWithUnsupported("Unavailable")
            } else if (plan.unsupportedTokens.isEmpty()) {
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
                submitInput(recordTurn = false)
            }
            return
        }
        playHandler.removeCallbacks(advanceRunnable)
        avatarController?.pause()
        currentIndex = 0
        playCurrentAsset()
    }

    private fun clearPlayback() {
        val fragmentBinding = binding ?: return
        ConversationPhraseAssist.clearPendingHearingReply()
        playHandler.removeCallbacks(advanceRunnable)
        avatarController?.pause()
        currentQueue = emptyList()
        unsupportedWords = emptyList()
        queuedSubmitUntilReady = false
        queuedSubmitSource = ConversationSource.TYPED_TEXT
        queuedSubmitRecordTurn = true
        currentIndex = 0
        lastInputText = ""
        translationNotice = null
        fragmentBinding.inputText.text?.clear()
        fragmentBinding.signedText.setText(R.string.text_to_asl_idle_text)
        fragmentBinding.signedText.isVisible = !fragmentBinding.expandableContent.isVisible
        fragmentBinding.tvSpeechStatus.setText(R.string.speech_tap_mic)
        fragmentBinding.currentSignText.setText(R.string.text_to_asl_current_sign_placeholder)
        fragmentBinding.currentProgressText.text = "Ready"
        if (avatarReady || !BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED) showIdleAvatar()
    }

    private fun playCurrentAsset() {
        val fragmentBinding = binding ?: return
        val asset = currentQueue.getOrNull(currentIndex) ?: return
        avatarController?.play(asset)
        currentQueue.getOrNull(currentIndex + 1)?.let { avatarController?.preload(it) }

        fragmentBinding.currentSignText.text = asset.displayText.uppercase(Locale.US)
        fragmentBinding.currentProgressText.text = progressWithUnsupported("${currentIndex + 1} / ${currentQueue.size}")

        playHandler.removeCallbacks(advanceRunnable)
        if (!BuildConfig.ASL_ASSET_PILOT_ENABLED) {
            playHandler.postDelayed(advanceRunnable, PLAYBACK_SAFETY_TIMEOUT_MS)
        }
    }

    private fun failPlayback(message: String) {
        playHandler.removeCallbacks(advanceRunnable)
        avatarController?.pause()
        binding?.currentProgressText?.text = progressWithUnsupported(message)
        // Keep the plan for the existing Repeat action; failure never means success.
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
            binding?.currentProgressText?.text = progressWithUnsupported("Complete")
        }
    }

    private fun progressWithUnsupported(progress: String): String {
        // The status pill shows playback progress only; preview/notice labels stay out of the UI.
        return if (unsupportedWords.isNotEmpty()) {
            "$progress • Unsupported: ${unsupportedWords.joinToString(", ")}"
        } else {
            progress
        }
    }

    private fun setSpeechMode(enabled: Boolean) {
        val fragmentBinding = binding ?: return
        showInputPanel(true)
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

    private fun showInputPanel(expanded: Boolean) {
        val fragmentBinding = binding ?: return
        fragmentBinding.expandableContent.isVisible = expanded
        fragmentBinding.modeSelector.isVisible = !expanded
        fragmentBinding.translatorModeHeading.setText(
            if (expanded) R.string.text_to_asl_signing_label else R.string.text_to_asl_sign_label,
        )
        fragmentBinding.signedText.isVisible = !expanded || lastInputText.isNotBlank()
        fragmentBinding.signedText.isClickable = !expanded
        fragmentBinding.signedText.isFocusable = !expanded
        fragmentBinding.signedText.contentDescription =
            if (expanded) null else getString(R.string.text_to_asl_open_text_input)
    }

    override fun onStart() {
        super.onStart()
        val fragmentBinding = binding ?: return
        // Returning from settings must not recreate the resident engine or change its rig.
        if (resumeColdIdle && BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED &&
            activeCharacter == AslCharacterChoice.NEW && idleAsset != null) {
            resumeColdIdle = false
            showIdleAvatar()
        }
        if (BuildConfig.ASL_ASSET_PILOT_ENABLED && avatarReady) {
            if (currentQueue.getOrNull(currentIndex) != null) playCurrentAsset() else showIdleAvatar()
            consumePendingAutoSubmitIfReady()
        }
    }

    override fun onStop() {
        if (BuildConfig.ASL_ASSET_PILOT_ENABLED) {
            resumeColdIdle = BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED &&
                activeCharacter == AslCharacterChoice.NEW && !avatarReady
            playHandler.removeCallbacks(advanceRunnable)
            avatarController?.pause()
        }
        super.onStop()
    }

    override fun onDestroyView() {
        playHandler.removeCallbacks(advanceRunnable)
        engineJob?.cancel()
        engineJob = null
        avatarController?.destroy()
        avatarController = null
        avatarReady = false
        queuedSubmitUntilReady = false
        resumeColdIdle = false
        animationCatalog = null
        phrasePlanner = null
        translationPlanner = null
        idleAsset = null
        speechPlayer?.close()
        speechPlayer = null
        binding = null
        super.onDestroyView()
    }

    private fun resetQueueForCharacterChange(fragmentBinding: FragmentTextToAslBinding) {
        playHandler.removeCallbacks(advanceRunnable)
        currentQueue = emptyList()
        unsupportedWords = emptyList()
        queuedSubmitUntilReady = false
        resumeColdIdle = false
        currentIndex = 0
        lastInputText = ""
        pendingAutoSubmitText = null
        fragmentBinding.currentSignText.setText(R.string.text_to_asl_current_sign_placeholder)
    }

    private companion object {
        // The imported batch tops out at about 5.71 seconds. The model-viewer completion event
        // normally advances immediately; this only prevents a malformed asset from stalling forever.
        const val PLAYBACK_SAFETY_TIMEOUT_MS = 7_000L
        const val KEY_PENDING_AUTO_SUBMIT_TEXT = "pending_auto_submit_text"
        const val KEY_CONSUMED_AUTO_SUBMIT_TEXT = "consumed_auto_submit_text"
    }
}
