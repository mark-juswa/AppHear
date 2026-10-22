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
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.webkit.WebView
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
import com.example.apphear.conversation.AutoReplyCountdown
import com.example.apphear.conversation.ConversationFlowPolicy
import com.example.apphear.conversation.ConversationScreens
import com.example.apphear.conversation.ConversationTimeline
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
    /** The avatar WebView in use; replaced if its renderer process dies. */
    private var avatarWebView: WebView? = null
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
    /**
     * conversationFlowV1: false from onStop until the avatar has drawn a frame after the screen
     * returns. A sign started earlier played against the hidden page's stale animation clock and
     * reported finished at once, so a spoken reply is held until this is true.
     */
    private var avatarVisibleSinceStart: Boolean = false
    private var visibleFrameRequest: Long = 0
    /** D2 (conversationAutoReply); null when the flag is off or the policy asset is unusable. */
    private var autoReply: AutoReplyCountdown? = null
    private var activeCharacter: AslCharacterChoice? = null
    private var engineJob: Job? = null

    private val speechLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val fragmentBinding = binding ?: return@registerForActivityResult
        if (result.resultCode == Activity.RESULT_OK) {
            val matches = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            val spokenText = matches?.firstOrNull()?.trim().orEmpty()
            ConversationTimeline.mark("speech_result", "screen" to "text_to_asl", "ok" to spokenText.isNotEmpty(),
                "chars" to spokenText.length)
            if (spokenText.isNotEmpty()) {
                fragmentBinding.tvSpeechStatus.text = spokenText
                fragmentBinding.inputText.setText(spokenText)
                submitInput(ConversationSource.SPEECH)
                return@registerForActivityResult
            }
        } else {
            ConversationTimeline.mark("speech_result", "screen" to "text_to_asl", "ok" to false, "chars" to 0)
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
        ConversationTimeline.screenCreated("text_to_asl")
        speechPlayer = AppHearSpeechPlayer(requireContext())
        if (ConversationScreens.autoReply) setupAutoReply(fragmentBinding)
        pendingAutoSubmitText = savedInstanceState?.getString(KEY_PENDING_AUTO_SUBMIT_TEXT)
            ?: arguments?.getString(TextToAslArgument.INCOMING_TEXT)?.trim()?.takeIf { it.isNotBlank() }
        consumedAutoSubmitText = savedInstanceState?.getString(KEY_CONSUMED_AUTO_SUBMIT_TEXT)

        setupTextToAslEngine(fragmentBinding)
        setupListeners(fragmentBinding)
        // conversationFlowV1: a spoken reply for this already-open screen arrives here instead of
        // recreating the screen; it uses the same auto-submit path as a reply passed at creation.
        parentFragmentManager.setFragmentResultListener(ConversationScreens.INCOMING_TRANSCRIPT_RESULT,
            viewLifecycleOwner) { _, result ->
            val transcript = result.getString(ConversationScreens.INCOMING_TRANSCRIPT_TEXT)?.trim()
                ?.takeIf { it.isNotBlank() } ?: return@setFragmentResultListener
            ConversationTimeline.mark("incoming_transcript_live", "chars" to transcript.length)
            consumedAutoSubmitText = null // the same words can legitimately be said twice in a row
            pendingAutoSubmitText = transcript
            consumePendingAutoSubmitIfReady()
        }
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
                val webView = avatarWebView ?: fragmentBinding.avatarWebView.also { avatarWebView = it }
                avatarController = TextToAslPlaybackController(requireContext(), webView, profile).also { controller ->
                    controller.onRendererGone = { recoverAvatarWebView(fragmentBinding) }
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
                                    ConversationTimeline.mark("avatar_ready")
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
                                if (currentIndex == 0) ConversationTimeline.mark("signing_started", "signs" to currentQueue.size)
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
                ConversationTimeline.mark("catalog_ready", "ms" to SystemClock.elapsedRealtime() - catalogStartMs,
                    "entries" to catalog.getAssets().size)
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
            ConversationTimeline.tap("text_to_asl", "sign_it")
            if (fragmentBinding.speechDeferredSection.isVisible) replayCurrentPlan() else submitInput()
        }
        fragmentBinding.btnMic.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "mic")
            startSpeechInput()
        }
        fragmentBinding.replayButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "repeat")
            replayCurrentPlan()
        }
        fragmentBinding.clearButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "clear")
            clearPlayback()
        }
        fragmentBinding.replyButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "reply")
            openReply()
        }
        fragmentBinding.modeTextButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "text_mode")
            setSpeechMode(false)
        }
        fragmentBinding.modeSpeechButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "talk_mode")
            setSpeechMode(true)
            if (ConversationScreens.oneTapTalk) startSpeechInput()
        }
        fragmentBinding.signedText.setOnClickListener {
            if (!fragmentBinding.expandableContent.isVisible) setSpeechMode(false)
        }
        fragmentBinding.modeTextShortcut.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "text_mode_shortcut")
            setSpeechMode(false)
        }
        fragmentBinding.modeTalkShortcut.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "talk_mode_shortcut")
            setSpeechMode(true)
            if (ConversationScreens.oneTapTalk) startSpeechInput()
        }
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
        if (ConversationScreens.reuseScreens && !avatarVisibleSinceStart) return // onResume submits it
        if (incomingText == consumedAutoSubmitText) {
            pendingAutoSubmitText = null
            return
        }

        fragmentBinding.inputText.setText(incomingText)
        fragmentBinding.signedText.text = incomingText
        fragmentBinding.signedText.isVisible = true
        consumedAutoSubmitText = incomingText
        pendingAutoSubmitText = null
        ConversationTimeline.mark("incoming_transcript_submit", "chars" to incomingText.length)
        submitInput(ConversationSource.SPEECH)
    }

    private fun startSpeechInput() {
        val fragmentBinding = binding ?: return
        cancelAutoReply("talk")
        if (!SpeechInputHelper.isAvailable(requireContext())) {
            fragmentBinding.tvSpeechStatus.setText(R.string.speech_unavailable)
            Toast.makeText(requireContext(), R.string.speech_unavailable, Toast.LENGTH_SHORT).show()
            return
        }
        fragmentBinding.tvSpeechStatus.setText(R.string.speech_listening)
        ConversationTimeline.mark("speech_launch", "screen" to "text_to_asl")
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
        cancelAutoReply("new_message")
        val requestedText = fragmentBinding.inputText.text?.toString()?.trim().orEmpty()
        if (requestedText.isEmpty()) {
            fragmentBinding.currentProgressText.setText(R.string.text_to_asl_empty_warning)
            return
        }

        if (BuildConfig.ASL_ASSET_PILOT_ENABLED && !avatarReady) {
            queuedSubmitUntilReady = true
            ConversationTimeline.mark("submit_waiting_for_avatar")
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
        ConversationTimeline.mark("plan_ready", "source" to source.name, "signs" to plan.queue.size,
            "unsupported" to plan.unsupportedTokens.size)
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
        cancelAutoReply("repeat")
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
        cancelAutoReply("clear")
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

        fragmentBinding.currentSignText.text = currentSignLabel(asset)
        fragmentBinding.currentProgressText.text = progressWithUnsupported("${currentIndex + 1} / ${currentQueue.size}")

        playHandler.removeCallbacks(advanceRunnable)
        if (!BuildConfig.ASL_ASSET_PILOT_ENABLED) {
            playHandler.postDelayed(advanceRunnable, PLAYBACK_SAFETY_TIMEOUT_MS)
        }
    }

    /**
     * The avatar renderer died: drop the dead WebView, put a fresh one in the same place and
     * reload the avatar. The current plan stays available for Repeat.
     */
    private fun recoverAvatarWebView(fragmentBinding: FragmentTextToAslBinding) {
        if (binding !== fragmentBinding) return
        val dead = avatarWebView ?: return
        ConversationTimeline.mark("avatar_renderer_gone")
        playHandler.removeCallbacks(advanceRunnable)
        avatarController?.abandonAfterRendererGone()
        avatarController = null
        avatarReady = false
        val parent = dead.parent as? ViewGroup ?: return
        val index = parent.indexOfChild(dead)
        val params = dead.layoutParams
        parent.removeView(dead)
        dead.destroy()
        val fresh = WebView(requireContext())
        parent.addView(fresh, index, params)
        avatarWebView = fresh
        cancelAutoReplyOnAvatarTouch(fresh)
        fragmentBinding.currentProgressText.text = "Reloading avatar…"
        setupTextToAslEngine(fragmentBinding)
    }

    private fun failPlayback(message: String) {
        ConversationTimeline.mark("signing_failed", "index" to currentIndex, "signs" to currentQueue.size)
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
            ConversationTimeline.mark("signing_complete", "signs" to currentQueue.size)
            showIdleAvatar()
            startAutoReply()
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

    private fun openReply() {
        startActivity(Intent(requireContext(), RecognitionActivity::class.java)
            .addFlags(ConversationScreens.reuseFlags()))
    }

    /** D2: Reply now / Repeat / Stay, plus cancelling when the user touches the avatar or types. */
    private fun setupAutoReply(fragmentBinding: FragmentTextToAslBinding) {
        val policy = runCatching { ConversationFlowPolicy.load(requireContext()) }
            .onFailure { Log.w("TextToAslAutoReply", "[conversation/autoreply] disabled: policy unavailable", it) }
            .getOrNull() ?: return
        autoReply = AutoReplyCountdown(
            delayMs = policy.autoReplyDelayMs,
            schedule = { delayMs, task -> playHandler.postDelayed(task, delayMs) },
            unschedule = { task -> playHandler.removeCallbacks(task) },
            onTick = { seconds ->
                binding?.autoReplyCountdownText?.text = getString(R.string.auto_reply_countdown, seconds)
            },
            onFire = {
                binding?.autoReplyOverlay?.isVisible = false
                ConversationTimeline.mark("auto_reply_fired")
                if (isResumed) openReply()
            },
        )
        fragmentBinding.autoReplyNowButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "auto_reply_now")
            cancelAutoReply("reply_now")
            openReply()
        }
        fragmentBinding.autoReplyRepeatButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "auto_reply_repeat")
            replayCurrentPlan()
        }
        fragmentBinding.autoReplyStayButton.setOnClickListener {
            ConversationTimeline.tap("text_to_asl", "auto_reply_stay")
            cancelAutoReply("stay")
        }
        cancelAutoReplyOnAvatarTouch(avatarWebView ?: fragmentBinding.avatarWebView)
        fragmentBinding.inputText.setOnFocusChangeListener { _, hasFocus -> if (hasFocus) cancelAutoReply("typing") }
    }

    /** Touching the avatar (for example to watch it again) stops the countdown; the WebView still gets the touch. */
    private fun cancelAutoReplyOnAvatarTouch(webView: WebView) {
        if (autoReply == null) return
        webView.setOnTouchListener { _, event ->
            if (event.actionMasked == MotionEvent.ACTION_DOWN) cancelAutoReply("avatar_touch")
            false
        }
    }

    /** After a full message has been signed on the visible screen, typed or spoken. */
    private fun startAutoReply() {
        val countdown = autoReply ?: return
        val fragmentBinding = binding ?: return
        if (!isResumed || currentQueue.isEmpty()) return
        countdown.start()
        fragmentBinding.autoReplyOverlay.isVisible = true
        fragmentBinding.autoReplyOverlay.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
        ConversationTimeline.mark("auto_reply_armed")
    }

    private fun cancelAutoReply(reason: String) {
        val countdown = autoReply ?: return
        binding?.autoReplyOverlay?.isVisible = false
        if (countdown.cancel()) ConversationTimeline.mark("auto_reply_cancelled", "reason" to reason)
    }

    /** A fingerspelled letter shows just the letter, without the "Fingerspelling WORD:" prefix. */
    private fun currentSignLabel(asset: AslAnimationAsset): String {
        val letter = asset.id.removePrefix("letter_")
        return if (asset.type == AslAnimationAsset.Type.LETTER && asset.id.startsWith("letter_") && letter.length == 1) {
            letter.uppercase(Locale.US)
        } else {
            asset.displayText.uppercase(Locale.US)
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

    override fun onResume() {
        super.onResume()
        if (ConversationScreens.reuseScreens) awaitVisibleAvatarFrame()
    }

    /**
     * Marks the avatar visible once the WebView has drawn a frame on screen, then submits any held
     * reply. The fallback covers a WebView that never reports a frame (for example, while hidden).
     */
    private fun awaitVisibleAvatarFrame() {
        val request = ++visibleFrameRequest
        val markVisible = Runnable {
            if (request != visibleFrameRequest || !isResumed || avatarVisibleSinceStart) return@Runnable
            avatarVisibleSinceStart = true
            ConversationTimeline.mark("avatar_visible", "held_reply" to (pendingAutoSubmitText != null))
            consumePendingAutoSubmitIfReady()
        }
        val webView = avatarWebView
        if (webView == null) {
            markVisible.run()
            return
        }
        webView.postVisualStateCallback(request, object : WebView.VisualStateCallback() {
            override fun onComplete(requestId: Long) {
                playHandler.post(markVisible)
            }
        })
        playHandler.postDelayed(markVisible, VISIBLE_FRAME_FALLBACK_MS)
    }

    override fun onStop() {
        cancelAutoReply("left_screen")
        avatarVisibleSinceStart = false
        visibleFrameRequest++
        if (BuildConfig.ASL_ASSET_PILOT_ENABLED) {
            resumeColdIdle = BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED &&
                activeCharacter == AslCharacterChoice.NEW && !avatarReady
            playHandler.removeCallbacks(advanceRunnable)
            avatarController?.pause()
        }
        super.onStop()
    }

    override fun onDestroyView() {
        ConversationTimeline.screenDestroyed("text_to_asl")
        playHandler.removeCallbacks(advanceRunnable)
        engineJob?.cancel()
        engineJob = null
        avatarController?.destroy()
        avatarController = null
        avatarWebView = null
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
        const val VISIBLE_FRAME_FALLBACK_MS = 1_000L
        const val KEY_PENDING_AUTO_SUBMIT_TEXT = "pending_auto_submit_text"
        const val KEY_CONSUMED_AUTO_SUBMIT_TEXT = "consumed_auto_submit_text"
    }
}
