package com.example.apphear

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.speech.RecognizerIntent
import android.util.Log
import android.util.Size
import android.util.Base64
import android.util.Range
import android.hardware.camera2.CaptureRequest
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import android.widget.LinearLayout
import android.widget.TextView
import com.google.android.material.button.MaterialButton
import com.example.apphear.fingerspelling.FingerspellModels
import com.example.apphear.fingerspelling.FingerspellRuntime
import com.example.apphear.fingerspelling.FingerspellSnapshot
import com.example.apphear.fingerspelling.FingerspellPhase
import com.example.apphear.data.settings.RecognitionModeSettings
import com.example.apphear.fingerspelling.RecognitionMode
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.example.apphear.databinding.ActivityRecognitionBinding
import com.example.apphear.pipeline.FrameAnalyzer
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.pipeline.CloseableFrameAnalyzer
import com.example.apphear.pipeline.IndependentClockFrameAnalyzer
import com.example.apphear.pipeline.diagnostics.A1Diagnostics
import com.example.apphear.pipeline.diagnostics.RuD1AttemptSpec
import com.example.apphear.pipeline.diagnostics.RuD1Diagnostics
import com.example.apphear.pipeline.LandmarkerBundle
import com.example.apphear.pipeline.LandmarkerConfig
import com.example.apphear.pipeline.recognition.FeatureFlags
import com.example.apphear.pipeline.recognition.Handedness
import com.example.apphear.pipeline.recognition.RecognitionPipeline
import com.example.apphear.pipeline.recognition.RuntimeConfig
import com.example.apphear.perceptionvnext.Candidate01FrameAnalyzer
import com.example.apphear.perceptionvnext.PhoneProductionSession
import com.example.apphear.contextassist.ConversationPhraseAssist
import com.example.apphear.contextassist.EvidenceAwareReplies
import com.example.apphear.contextassist.PhraseAssistUiState
import com.example.apphear.contextassist.SigningTurnBuffer
import com.example.apphear.conversation.ConversationScreens
import com.example.apphear.conversation.ConversationTimeline
import com.example.apphear.sentenceassist.AiStatus
import com.example.apphear.sentenceassist.SentenceAssistMode
import com.example.apphear.sentenceassist.SentenceAssistShadow
import com.example.apphear.contextassist.Stage3Diagnostics
import com.example.apphear.ui.recognition.RecognitionUiSnapshot
import com.example.apphear.ui.speech.AppHearSpeechPlayer
import com.example.apphear.ui.speech.SpeechInputHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.Future

class RecognitionActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRecognitionBinding
    private lateinit var cameraExecutor: ExecutorService
    private lateinit var a1ShutdownExecutor: ExecutorService

    private var landmarkers: LandmarkerBundle? = null
    private var recognizer: RecognitionPipeline? = null
    private var phoneSession: PhoneProductionSession? = null
    private var phoneAnalyzer: Candidate01FrameAnalyzer? = null
    @Volatile private var fingerspellRuntime: FingerspellRuntime? = null
    private var coordination: com.example.apphear.coordination.RecognitionCoordinationBridge? = null
    private val recognitionSettings by lazy { RecognitionModeSettings(this) }
    @Volatile private var selectedRecognitionMode = RecognitionMode.WORD
    private var fingerspellStatus: TextView? = null
    private val fingerspellButtons = mutableMapOf<String, MaterialButton>()
    private val signingTurn = SigningTurnBuffer()
    private var evidenceInterrupted = false
    private var signingVisible = false
    private var signingInProgress = false
    /** D3 (conversationAutoListen): signs committed so far, and the current Hear's auto-listen ticket. */
    private var signsCommitted = 0L
    private var autoListenTicket = 0L
    private var timelineAwaitingFrame = false
    private var sentenceShadow: SentenceAssistShadow? = null
    private var displayedHearingTurnId: Long? = null
    private var openingHearingTurnId: Long? = null
    private var renderedHints: List<EvidenceAwareReplies.Hint> = emptyList()
    private var lastPulsedEventId: Int? = null
    private var runtimeConfig: RuntimeConfig? = null
    private var analyzer: CloseableFrameAnalyzer? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var frameCount = 0
    private var phoneAnalysis: ImageAnalysis? = null
    @Volatile private var cameraGeneration = 0
    private var processingCameraGeneration = 0
    private var processingFrontCamera = true
    @Volatile private var cameraSwitching = false
    @Volatile private var cameraInputFrames = 0
    private val cameraInputFramesJson = org.json.JSONArray()
    private var frontCamera = true
    private var a1Active = false
    private var a1ShutdownFuture: Future<*>? = null
    private var a1ResumePending = false
    private var modelLoadError: String? = null
    private var degradedBannerDismissed = false
    private lateinit var speechPlayer: AppHearSpeechPlayer
    private var speakSentence: (String) -> Unit = { speechPlayer.speak(it) }
    private lateinit var ruD1: RuD1Diagnostics
    private var ruD1Transitioning = false
    private var ruD1DisplayState = RuD1DisplayState.READY

    private val prefs by lazy { getSharedPreferences("apphear", MODE_PRIVATE) }

    private val requestCamera = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) start() else binding.fpsText.setText(R.string.camera_permission_needed)
    }

    private val replySpeechLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        if (result.resultCode != Activity.RESULT_OK) {
            ConversationTimeline.mark("speech_result", "screen" to "recognition", "ok" to false, "chars" to 0)
            Toast.makeText(this, R.string.reply_speech_cancelled, Toast.LENGTH_SHORT).show()
            return@registerForActivityResult
        }

        val transcript = result.data
            ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            ?.firstOrNull()
            ?.trim()
            .orEmpty()
        ConversationTimeline.mark("speech_result", "screen" to "recognition", "ok" to transcript.isNotBlank(),
            "chars" to transcript.length)
        if (transcript.isBlank()) {
            Toast.makeText(this, R.string.reply_speech_empty, Toast.LENGTH_SHORT).show()
            return@registerForActivityResult
        }

        openTextToAslReply(transcript)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        binding = ActivityRecognitionBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ConversationTimeline.screenCreated("recognition")
        ConversationScreens.recognitionCreated(this)
        sentenceShadow = SentenceAssistShadow.create(this, lifecycleScope)
        sentenceShadow?.onRendered = { refreshSentenceAssistDisplay() }
        selectedRecognitionMode = recognitionSettings.current()
        openingHearingTurnId = ConversationPhraseAssist.presentationState.value.hearingTurnId
        displayedHearingTurnId = openingHearingTurnId
        binding.sentenceCard.visibility = View.GONE
        speechPlayer = AppHearSpeechPlayer(this)
        ruD1 = RuD1Diagnostics.create(applicationContext)
        binding.btnBack.setOnClickListener {
            ConversationTimeline.tap("recognition", "back")
            finish()
        }
        binding.dragHandleWrapper.setOnClickListener {
            binding.expandableContent.visibility =
                if (binding.expandableContent.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }
        cameraExecutor = Executors.newSingleThreadExecutor()
        if(BuildConfig.RECOGNITION_COORDINATION_ENABLED) {
            coordination = runCatching {
                com.example.apphear.coordination.RecognitionCoordinationBridge(this,binding.root,
                    runtime={fingerspellRuntime},
                    dispatch={task -> if(!cameraExecutor.isShutdown) cameraExecutor.execute { task() }},
                    main={task -> runOnUiThread { if(!isFinishing && !isDestroyed) task() }},
                    selected={mode ->
                        selectedRecognitionMode=mode
                        runOnUiThread {
                            if(!isFinishing && !isDestroyed) {
                                onCoordinatedMode(mode)
                                if(mode==RecognitionMode.FINGERSPELL && signingTurn.snapshot().isNotEmpty()) evidenceInterrupted=true
                                if(mode==RecognitionMode.WORD) renderRecognitionSnapshot(RecognitionUiSnapshot.from(
                                    com.example.apphear.pipeline.recognition.RecognitionState.Idle,
                                    phoneSession?.sentenceText.orEmpty(),getString(R.string.gloss_placeholder),
                                    getString(R.string.signing),getString(R.string.sentence_placeholder)))
                            }
                        }
                    }, speak={speechPlayer.speak(it)}, initial=selectedRecognitionMode)
            }.onFailure { Log.w(TAG,"Context routing unavailable; existing manual recognition preserved",it) }.getOrNull()
        }
        if (BuildConfig.RECOGNITION_MODE_TOOLBAR_ENABLED && recognitionSettings.selectionAvailable) installModeToolbar()
        a1ShutdownExecutor = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "apphear-a1-lifecycle-shutdown")
        }
        logPerformanceSupport()

        binding.handToggle.setOnClickListener {
            val next = if (currentHandedness() == Handedness.RIGHT) Handedness.LEFT else Handedness.RIGHT
            prefs.edit().putString(KEY_HAND, next.name).apply()
            applyHandedness(next)
            toastHandedness(next, Toast.LENGTH_SHORT)
        }
        applyHandedness(currentHandedness())
        // Candidate01 estimates both hands; legacy handedness and rear-camera controls have no
        // validated meaning for this causal path. Keep the existing UI but disable these actions.
        binding.handToggle.isEnabled = false
        binding.handToggle.alpha = 0.5f
        binding.handToggle.contentDescription = "Hand selection unavailable in causal recognition"

        binding.clearButton.setOnClickListener {
            ConversationTimeline.tap("recognition", "clear")
            clearRecognized()
        }
        if (ruD1.config.enabled) {
            binding.clearButton.setOnLongClickListener {
                toggleRuD1Attempt()
                true
            }
        }

        binding.speakButton.setOnClickListener {
            ConversationTimeline.tap("recognition", "speak")
            autoListenTicket++
            startReplySpeechInput()
        }

        binding.hearButton.setOnClickListener {
            ConversationTimeline.tap("recognition", "hear")
            speakRecognizedSentence()
        }

        binding.degradedBannerClose.setOnClickListener {
            degradedBannerDismissed = true
            binding.degradedBanner.visibility = View.GONE
        }

        binding.cameraToggle.setOnClickListener {
            if (phoneSession != null) {
                if (!BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED || cameraSwitching) return@setOnClickListener
                val provider = cameraProvider ?: return@setOnClickListener
                val requested = if (frontCamera) CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
                if (!provider.hasCamera(requested)) {
                    Toast.makeText(this, "Requested camera unavailable", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
            }
            frontCamera = !frontCamera
            applyCameraLabel()
            recognizer?.resetSession()
            rebindCamera()
            Toast.makeText(
                this,
                getString(if (frontCamera) R.string.camera_front_hint else R.string.camera_back_hint),
                Toast.LENGTH_SHORT,
            ).show()
        }
        applyCameraLabel()
        binding.cameraToggle.isEnabled = false
        binding.cameraToggle.alpha = 0.5f
        binding.cameraToggle.contentDescription = "Front camera only in causal recognition"
        renderRuD1QueueStatus()
        binding.recognizedLabel.setText(R.string.recognized_label)
        if (ConversationPhraseAssist.enabled) {
            renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
            lifecycleScope.launch {
                repeatOnLifecycle(Lifecycle.State.STARTED) {
                    ConversationPhraseAssist.presentationState.collect(::renderPhraseAssist)
                }
            }
        }

        if (hasCameraPermission()) start() else requestCamera.launch(Manifest.permission.CAMERA)
    }

    /** The Clear button's reset; also used when a reused screen starts a new hearing turn. */
    private fun clearRecognized() {
        autoListenTicket++
        if (fingerspellRuntime?.snapshot?.mode == RecognitionMode.FINGERSPELL) {
            cameraExecutor.execute { fingerspellRuntime?.clear() }
            return
        }
        phoneSession?.clearSentence()
        recognizer?.clearSentence()
        signingTurn.clear()
        sentenceShadow?.reset()
        binding.signedDetailGroup.visibility = View.GONE
        evidenceInterrupted = false
        signingVisible = false
        signingInProgress = false
        lastPulsedEventId = null
        ConversationPhraseAssist.clearDisplayedInterpretation()
        renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
        if (ruD1.config.enabled && ruD1QueueGloss().isNotBlank()) {
            renderRuD1QueueStatus()
        } else {
            binding.sentenceText.text = getString(R.string.sentence_placeholder)
        }
        updateSentenceCardVisibility()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (!ConversationScreens.reuseScreens) return
        // Brought back for a reply (conversationFlowV1). A new hearing turn starts from the same
        // clean state a newly created screen has, so Context Assist matching is not marked as
        // interrupted by the previous reply's words.
        val turnId = ConversationPhraseAssist.presentationState.value.hearingTurnId
        val newTurn = turnId != openingHearingTurnId
        ConversationTimeline.mark("recognition_reused", "new_turn" to newTurn)
        if (newTurn) {
            openingHearingTurnId = turnId
            clearRecognized()
        }
    }

    /**
     * D3: speak the reply, then open speech input for the hearing person's answer. Skipped when
     * there is no hearing turn to answer, the signer started signing again, or the screen left.
     */
    private fun speakThenListen(text: String) {
        val ticket = ++autoListenTicket
        val committedAtHear = signsCommitted
        speechPlayer.speak(text) {
            if (ticket != autoListenTicket || isFinishing || isDestroyed ||
                !lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) return@speak
            val skipped = when {
                ConversationPhraseAssist.presentationState.value.hearingTurnId == null -> "no_hearing_turn"
                signsCommitted != committedAtHear || signingInProgress -> "signing_again"
                else -> null
            }
            if (skipped != null) {
                ConversationTimeline.mark("auto_listen_skipped", "reason" to skipped)
                return@speak
            }
            ConversationTimeline.mark("auto_listen")
            startReplySpeechInput()
        }
    }

    private fun startReplySpeechInput() {
        if (!SpeechInputHelper.isAvailable(this)) {
            Toast.makeText(this, R.string.speech_unavailable, Toast.LENGTH_SHORT).show()
            return
        }

        try {
            ConversationTimeline.mark("speech_launch", "screen" to "recognition")
            replySpeechLauncher.launch(SpeechInputHelper.createSpeechIntent(getString(R.string.reply_speech_prompt)))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, R.string.speech_unavailable, Toast.LENGTH_SHORT).show()
        }
    }

    private fun speakRecognizedSentence() {
        if(coordination?.hear()==true) return
        fingerspellRuntime?.snapshot?.takeIf { it.mode == RecognitionMode.FINGERSPELL }?.let {
            if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED && it.preview.isNotBlank()) {
                val draft = it.preview
                androidx.appcompat.app.AlertDialog.Builder(this)
                    .setTitle("Confirm spelling")
                    .setMessage(it.confirmed + draft)
                    .setPositiveButton("Confirm and hear") { _, _ ->
                        cameraExecutor.execute {
                            val runtime = fingerspellRuntime ?: return@execute
                            val current = runtime.snapshot
                            if (current.mode == RecognitionMode.FINGERSPELL && current.preview == draft && current.confirmed == it.confirmed) {
                                runtime.confirm()
                                val confirmed = runtime.snapshot.confirmed
                                runOnUiThread { if (!isFinishing && !isDestroyed) speechPlayer.speak(confirmed) }
                            } else runOnUiThread {
                                Toast.makeText(this, "Spelling changed. Tap Hear to review again.", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                    .setNegativeButton(android.R.string.cancel, null).show()
            } else if (it.confirmed.isBlank()) Toast.makeText(this, "No spelling to speak", Toast.LENGTH_SHORT).show()
            else speechPlayer.speak(it.confirmed)
            return
        }
        val sentence = (phoneSession?.sentenceText ?: recognizer?.sentenceText)?.trim().orEmpty()
            .ifBlank { binding.sentenceText.text?.toString()?.trim().orEmpty() }
        if (sentence.isBlank() || sentence == getString(R.string.sentence_placeholder)) {
            Toast.makeText(this, R.string.speech_no_text_to_speak, Toast.LENGTH_SHORT).show()
            return
        }
        // VISIBLE mode speaks exactly the grounded wording shown under RECOGNIZED; otherwise the raw words.
        // VISIBLE mode speaks exactly what RECOGNIZED shows: the AI sentence or the plain words.
        val displayed = if (SentenceAssistMode.current == SentenceAssistMode.VISIBLE) {
            sentenceShadow?.displayState(sentence, ConversationPhraseAssist.presentationState.value.hearingTurnId)
        } else null
        val shownAi = (displayed as? SentenceAssistShadow.DisplayState.Done)?.outcome
            ?.takeIf { it.aiStatus == AiStatus.ACCEPTED }
        val spoken = when (displayed) {
            is SentenceAssistShadow.DisplayState.Done -> displayed.outcome.chosenSentence
            is SentenceAssistShadow.DisplayState.Plain -> displayed.sentence
            else -> sentence
        }
        if (ConversationScreens.autoListen) speakThenListen(spoken) else speakSentence(spoken)
        sentenceShadow?.let { shadow ->
            val hearing = ConversationPhraseAssist.presentationState.value
            shadow.hearTapped(sentence, signingTurn.snapshot(), !(evidenceInterrupted || signingTurn.overflowed),
                hearing.hearingText, hearing.hearingTurnId, spokeAi = shownAi != null)
        }
        ConversationTimeline.mark("hear_spoken", "words" to sentence.split(' ').count { it.isNotBlank() })
        if (ConversationPhraseAssist.enabled &&
            (signingTurn.snapshot().isNotEmpty() || evidenceInterrupted)) {
            val evidence = signingTurn.snapshot()
            val incomplete = evidenceInterrupted || signingTurn.overflowed
            signingTurn.clear()
            evidenceInterrupted = false
            runCatching { ConversationPhraseAssist.evaluateShadowTurn(evidence, sentence, incomplete) }
                .onFailure { Log.w(TAG, "Shadow evaluation unavailable", it) }
            renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
        }
    }

    private fun renderPhraseAssist(state: PhraseAssistUiState) {
        coordination?.context(state)
        if (fingerspellRuntime?.snapshot?.mode == RecognitionMode.FINGERSPELL) {
            // WORD advisory remains cached; spelling never feeds its matcher/provider.
            binding.possibleRepliesGroup.visibility = View.GONE
            binding.contextSupportedGroup.visibility = View.GONE
            return
        }
        if (!ConversationPhraseAssist.enabled) {
            binding.possibleRepliesGroup.visibility = View.GONE
            binding.contextSupportedGroup.visibility = View.GONE
            return
        }
        if (displayedHearingTurnId != state.hearingTurnId) {
            displayedHearingTurnId = state.hearingTurnId
            signingVisible = false
            signingInProgress = false
            signingTurn.clear()
            sentenceShadow?.reset()
            binding.signedDetailGroup.visibility = View.GONE
            lastPulsedEventId = null
            // Existing raw words belong to an earlier response. Keep them untouched, but
            // do not match new predictions against a mixed, un-cleared sentence.
            val rawSentence = (phoneSession?.sentenceText ?: recognizer?.sentenceText)
                ?.takeIf { it.isNotBlank() } ?: binding.sentenceText.text?.toString().orEmpty()
            evidenceInterrupted = rawSentence.isNotBlank() &&
                rawSentence != getString(R.string.sentence_placeholder)
        }
        val evidence = signingTurn.snapshot()
        val hints = ConversationPhraseAssist.replyHintsForEvidence(evidence).take(5)
        if (renderedHints != hints) {
            renderedHints = hints
            binding.replyChipContainer.removeAllViews()
            val centered = listOf(hints.getOrNull(1), hints.firstOrNull(), hints.getOrNull(2)) +
                hints.drop(3)
            // Preserve the compact three-suggestion row; phrases wrap inside each slot.
            val slotWidth = ((resources.displayMetrics.widthPixels - 86.dp) / 3).coerceAtLeast(70.dp)
            centered.forEachIndexed { index, hint ->
                val leading = index == 1
                val chip = TextView(this).apply {
                    text = hint?.naturalText.orEmpty()
                    contentDescription = hint?.naturalText?.let {
                        getString(R.string.context_predicted_reply_accessibility, it)
                    }
                    setTextColor(when {
                        leading && hint?.latestSignSupportsAnchor == true -> 0xFFB7FFF0.toInt()
                        leading -> getColor(R.color.white)
                        else -> 0xD8FFFFFF.toInt()
                    })
                    textSize = if (leading) {
                        if (hint?.latestSignSupportsAnchor == true) 16f else 15f
                    } else 12f
                    typeface = resources.getFont(if (leading) R.font.inter_semibold
                        else R.font.inter_regular)
                    gravity = android.view.Gravity.CENTER
                    minHeight = 40.dp
                    setPadding(3.dp, 3.dp, 3.dp, 3.dp)
                    if (leading && hint?.latestSignSupportsAnchor == true) {
                        setShadowLayer(6.dp.toFloat(), 0f, 0f, 0x9935D9BE.toInt())
                    }
                }
                binding.replyChipContainer.addView(chip,
                    android.widget.LinearLayout.LayoutParams(
                        slotWidth,
                        android.widget.LinearLayout.LayoutParams.WRAP_CONTENT,
                    ))
            }
            binding.replyScroll.post { binding.replyScroll.scrollTo(0, 0) }
        }
        val latestEventId = evidence.lastOrNull()?.eventId
        if (hints.firstOrNull()?.latestSignSupportsAnchor == true && latestEventId != null &&
            lastPulsedEventId != latestEventId) {
            lastPulsedEventId = latestEventId
            (binding.replyChipContainer.getChildAt(1) as? TextView)?.post {
                val leading = binding.replyChipContainer.getChildAt(1) as? TextView ?: return@post
                if (isFinishing || isDestroyed) return@post
                leading.animate().cancel()
                leading.animate().scaleX(1.10f).scaleY(1.10f).setDuration(140)
                    .withEndAction {
                        leading.animate().scaleX(1f).scaleY(1f).setDuration(180).start()
                    }.start()
            }
        }
        binding.possibleRepliesGroup.visibility =
            if (signingVisible && hints.isNotEmpty()) View.VISIBLE else View.GONE
        val supported = state.contextSupported
        binding.contextSupportedGroup.visibility =
            if (signingVisible && supported != null) View.VISIBLE else View.GONE
        binding.contextSupportedText.text = supported.orEmpty()
    }

    private val Int.dp: Int get() = (this * resources.displayMetrics.density).toInt()

    /**
     * VISIBLE mode: RECOGNIZED becomes the sentence builder for [raw] (the words as recognized).
     * The plain words appear at once ("Improving..." while the AI works on 2+ signs) and are
     * replaced by the grounded AI sentence when it arrives. The signed words stay on a line beneath.
     */
    private fun sentenceAssistDisplay(raw: CharSequence): CharSequence {
        val shadow = sentenceShadow
        val words = raw.toString().trim()
        val state = if (SentenceAssistMode.current != SentenceAssistMode.VISIBLE || shadow == null ||
            words.isEmpty() || words == getString(R.string.sentence_placeholder)) {
            SentenceAssistShadow.DisplayState.Idle
        } else {
            shadow.displayState(words, ConversationPhraseAssist.presentationState.value.hearingTurnId)
        }
        val shown: String
        val notes: List<String>
        when (state) {
            is SentenceAssistShadow.DisplayState.Idle -> {
                binding.signedDetailGroup.visibility = View.GONE
                return raw
            }
            is SentenceAssistShadow.DisplayState.Plain -> {
                shown = state.sentence
                notes = if (state.improving) listOf(getString(R.string.sentence_assist_improving)) else emptyList()
            }
            is SentenceAssistShadow.DisplayState.Done -> {
                val outcome = state.outcome
                shown = outcome.chosenSentence
                notes = listOfNotNull(
                    outcome.inferredWords.takeIf { it.isNotEmpty() }
                        ?.let { getString(R.string.sentence_assist_added, it.joinToString(", ")) },
                    outcome.changedSigns.takeIf { it.isNotEmpty() }
                        ?.let { getString(R.string.sentence_assist_changed, it.joinToString(", ")) },
                )
            }
        }
        binding.signedDetailGroup.visibility = View.VISIBLE
        binding.signedWordsText.text = getString(R.string.sentence_assist_signed, words)
        binding.assistNoteText.text = notes.joinToString(" \u00b7 ")
        binding.assistNoteText.visibility = if (notes.isEmpty()) View.GONE else View.VISIBLE
        return shown
    }

    /** A rendering finished: show it now rather than waiting for the next camera frame. */
    private fun refreshSentenceAssistDisplay() {
        val raw = (phoneSession?.sentenceText ?: recognizer?.sentenceText).orEmpty()
        if (raw.isBlank()) return
        binding.sentenceText.text = sentenceAssistDisplay(raw)
        updateSentenceCardVisibility()
    }

    private fun updateSentenceCardVisibility() {
        val text = binding.sentenceText.text?.toString()?.trim().orEmpty()
        binding.sentenceCard.visibility = if (text.isNotEmpty() &&
            text != getString(R.string.sentence_placeholder)) View.VISIBLE else View.GONE
    }

    private fun openTextToAslReply(transcript: String) {
        ConversationTimeline.mark("open_text_to_asl", "chars" to transcript.length)
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(ConversationScreens.reuseFlags())
            putExtra(MainActivity.EXTRA_OPEN_TEXT_TO_ASL, true)
            putExtra(MainActivity.EXTRA_TEXT_TO_ASL_INPUT, transcript)
        }
        startActivity(intent)
    }

    private fun currentHandedness(): Handedness =
        if (prefs.getString(KEY_HAND, Handedness.RIGHT.name) == Handedness.LEFT.name) {
            Handedness.LEFT
        } else {
            Handedness.RIGHT
        }

    private fun applyHandedness(h: Handedness) {
        recognizer?.handedness = h
        binding.handToggle.setText(if (h == Handedness.LEFT) R.string.hand_left else R.string.hand_right)
    }

    private fun applyCameraLabel() {
        binding.cameraToggle.setText(if (frontCamera) R.string.camera_front else R.string.camera_back)
    }

    private fun toastHandedness(h: Handedness, length: Int) {
        val hand = getString(if (h == Handedness.LEFT) R.string.hand_left_short else R.string.hand_right_short)
        Toast.makeText(this, getString(R.string.hand_hint, hand), length).show()
    }

    private fun hasCameraPermission() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    private fun start() {
        lifecycleScope.launch {
            val loaded = withContext(Dispatchers.IO) {
                runCatching {
                    val session = PhoneProductionSession.load(applicationContext)
                    try {
                        val spellingModels = if (BuildConfig.FINGERSPELL_EXPERIMENT_ENABLED) {
                            runCatching { FingerspellModels(applicationContext) }.onFailure {
                                Log.e(TAG, "Fingerspell unavailable; WORD preserved", it)
                            }.getOrNull()
                        } else null
                        Triple(session, Candidate01FrameAnalyzer(
                            applicationContext, session, ::onFrame,
                            ownsObservation = if (BuildConfig.FINGERSPELL_EXPERIMENT_ENABLED) { observation, image ->
                                // Routing policy reads current visibility/idle only; Candidate01 and WORD are unchanged.
                                coordination?.observation(session.isReady,(0..1).any { s ->
                                    observation.handObserved[s] && observation.handJointValid[s].any { it } })
                                val spelling = fingerspellRuntime
                                if (spelling?.fingerspellOwnsFrames == true) {
                                    spelling.consume(observation, image)
                                    true
                                } else {
                                    if (spelling == null && selectedRecognitionMode == RecognitionMode.FINGERSPELL) true
                                    else { spelling?.recordWordCadence(observation); false }
                                }
                            } else null,
                        ) { failure ->
                            runOnUiThread {
                                if (!isFinishing && !isDestroyed) {
                                    cameraProvider?.unbindAll()
                                    renderRuntimeError("Causal recognition stopped", failure.message.orEmpty())
                                }
                            }
                        }, spellingModels)
                    } catch (failure: Throwable) {
                        session.close()
                        throw failure
                    }
                }
            }
            loaded.onSuccess { (session, frameAnalyzer, spellingModels) ->
                if (isFinishing || isDestroyed) {
                    frameAnalyzer.close()
                    session.close()
                    spellingModels?.close()
                    return@launch
                }
                phoneSession = session
                phoneAnalyzer = frameAnalyzer
                if (spellingModels != null) {
                    fingerspellRuntime = FingerspellRuntime(applicationContext, spellingModels,
                        { frameAnalyzer.resetTemporalSession() }, ::onFingerspell,
                        continuousEnabled = BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED,
                        dispatch = { task -> if (!cameraExecutor.isShutdown) cameraExecutor.execute { task() } })
                    installFingerspellControls()
                    cameraExecutor.execute { fingerspellRuntime?.select(selectedRecognitionMode) }
                } else if (selectedRecognitionMode == RecognitionMode.FINGERSPELL) {
                    renderRuntimeError("Fingerspell unavailable", "Select WORD in Settings to use word recognition.")
                }
                Log.i(TAG, "normal backend=Candidate01 package=${session.packageId}")
                if (BuildConfig.DEBUG) Toast.makeText(this@RecognitionActivity, "Recognition: ${session.displayLabel}", Toast.LENGTH_LONG).show()
                bindCamera()
            }.onFailure { failure ->
                modelLoadError = failure.message ?: "Causal recognition unavailable"
                renderRuntimeError("Causal recognition unavailable", modelLoadError.orEmpty())
                Log.e(TAG, "No legacy backend fallback", failure)
            }
        }
    }

    private fun bindCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            cameraProvider = future.get()
            rebindCamera()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun rebindCamera() {
        val provider = cameraProvider ?: return
        if (phoneSession != null) {
            bindPhoneCamera(provider)
            return
        }
        val bundle = landmarkers ?: return
        val runtime = runtimeConfig ?: RuntimeConfig.load(applicationContext)
        val selector = if (frontCamera) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
        val a1Requested = intent.getStringExtra(EXTRA_A1_MODE).equals(A1_MODE, ignoreCase = true)
        val a1Enabled = FeatureFlags.A1_INDEPENDENT_CLOCK_AVAILABLE && a1Requested

        if (a1Enabled && a1Active && analyzer == null && a1ShutdownFuture != null) {
            resumeAfterA1Shutdown(checkNotNull(a1ShutdownFuture))
            return
        }
        if (a1Enabled && a1Active && analyzer != null) {
            // Camera switch: detach immediately, then rebuild only after the old workers have
            // joined. The shared LandmarkerBundle is never touched by two analyzer generations.
            closeA1AnalyzerAsync(rebindWhenStarted = true)
            return
        }

        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }

        analyzer?.close()
        a1Active = a1Enabled
        val diagnostics = if (FeatureFlags.A1_INDEPENDENT_CLOCK_AVAILABLE) {
            A1Diagnostics(
                mode = if (a1Enabled) A1_MODE else BASELINE_MODE,
                runId = intent.getStringExtra(EXTRA_A1_RUN_ID) ?: "manual",
            )
        } else {
            null
        }
        val frameAnalyzer: CloseableFrameAnalyzer = if (a1Enabled) {
            val maxPoseAgeMs = intent.getLongExtra(EXTRA_A1_MAX_POSE_AGE_MS, 0L)
            require(maxPoseAgeMs > 0L) {
                "A1 requires --el $EXTRA_A1_MAX_POSE_AGE_MS derived from the Baseline trace"
            }
            IndependentClockFrameAnalyzer(
                bundle,
                frontCamera,
                recognizer,
                runtime,
                TimeUnit.MILLISECONDS.toNanos(maxPoseAgeMs),
                ruD1,
                checkNotNull(diagnostics),
                ::onFrame,
            )
        } else {
            FrameAnalyzer(
                bundle,
                frontCamera,
                recognizer,
                runtime,
                deviceSummary(),
                ruD1,
                diagnostics,
                ::onFrame,
            )
        }.also { analyzer = it }
        val analysisSize = cameraAnalysisSize()
        Log.i(TAG, "camera_analysis target=${analysisSize.width}x${analysisSize.height}")
        val resolution = ResolutionSelector.Builder()
            .setResolutionStrategy(
                ResolutionStrategy(
                    analysisSize,
                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER,
                ),
            )
            .build()
        val analysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
            .setResolutionSelector(resolution)
            .build()
            .also { it.setAnalyzer(cameraExecutor, frameAnalyzer) }

        try {
            provider.unbindAll()
            provider.bindToLifecycle(this, selector, preview, analysis)
        } catch (e: Exception) {
            Toast.makeText(this, "Camera bind failed: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun bindPhoneCamera(provider: ProcessCameraProvider) {
        val frameAnalyzer = phoneAnalyzer ?: return
        val boundFront = frontCamera
        val selector = if (boundFront) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
        val ticket = ++cameraGeneration
        cameraSwitching = true
        binding.cameraToggle.isEnabled = false
        phoneAnalysis?.clearAnalyzer()
        provider.unbindAll()
        binding.overlayView.clear()
        cameraExecutor.execute {
            // Drain old camera callbacks and invalidate any in-flight spelling result before binding.
            fingerspellRuntime?.let { it.pause(); it.select(selectedRecognitionMode) }
                ?: frameAnalyzer.resetTemporalSession()
            cameraInputFrames = 0
            runOnUiThread {
                if (ticket != cameraGeneration || isFinishing || isDestroyed) return@runOnUiThread
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(binding.previewView.surfaceProvider)
                }
                // Identical front-baseline input settings. rotationDegrees is handled by the
                // existing native preprocessor; neither lens adds any pixel reflection.
                val builder = ImageAnalysis.Builder()
                    .setTargetResolution(Size(480, 360))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                // Front reference stays at 15. Rear preview uses 30 only when the camera
                // explicitly advertises the exact range; analysis still keeps only latest.
                val rearRanges = if(!boundFront) androidx.camera.camera2.interop.Camera2CameraInfo
                    .from(selector.filter(provider.availableCameraInfos).first())
                    .getCameraCharacteristic(android.hardware.camera2.CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES)
                    .orEmpty() else emptyArray()
                val requestedFps = if(!boundFront && rearRanges.any { it.lower == 30 && it.upper == 30 }) 30 else 15
                val timing = if(BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED)
                    com.example.apphear.camera.CameraTimingProbe(boundFront,ticket,requestedFps) else null
                val interop = Camera2Interop.Extender(builder)
                timing?.let { probe -> interop.setSessionCaptureCallback(object :
                    android.hardware.camera2.CameraCaptureSession.CaptureCallback() {
                    override fun onCaptureCompleted(session:android.hardware.camera2.CameraCaptureSession,
                        request:android.hardware.camera2.CaptureRequest,
                        result:android.hardware.camera2.TotalCaptureResult) {
                        probe.capture(result.get(android.hardware.camera2.CaptureResult.SENSOR_TIMESTAMP),
                            result.get(android.hardware.camera2.CaptureResult.SENSOR_EXPOSURE_TIME))
                    }
                }) }
                interop.setCaptureRequestOption(
                    CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(requestedFps, requestedFps),
                )
                val analysis = builder.build().also { next ->
                    next.setAnalyzer(cameraExecutor) { image ->
                        if (ticket != cameraGeneration) { image.close(); return@setAnalyzer }
                        processingCameraGeneration = ticket
                        processingFrontCamera = boundFront
                        cameraInputFrames++
                        if (BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED && cameraInputFrames <= 12) {
                            if(cameraInputFramesJson.length() >= 120) cameraInputFramesJson.remove(0)
                            val rotation = image.imageInfo.rotationDegrees
                            cameraInputFramesJson.put(org.json.JSONObject()
                                .put("generation",ticket).put("front",boundFront)
                                .put("rotation_degrees",rotation).put("raw_width",image.width)
                                .put("raw_height",image.height)
                                .put("upright_width",if(rotation == 90 || rotation == 270) image.height else image.width)
                                .put("upright_height",if(rotation == 90 || rotation == 270) image.width else image.height)
                                .put("row_stride",image.planes[0].rowStride)
                                .put("pixel_stride",image.planes[0].pixelStride)
                                .put("timestamp_ns",image.imageInfo.timestamp)
                                .put("mode",selectedRecognitionMode.name)
                                .put("input_contract","UPRIGHT_UNMIRRORED_SOURCE_RGB"))
                            if(cameraInputFrames == 12) java.io.File(filesDir,"camera_input_01.json")
                                .writeText(org.json.JSONObject().put("frames",cameraInputFramesJson)
                                    .put("accuracy_claim","NONE").toString(2))
                        }
                        val processingMode=if(fingerspellRuntime?.fingerspellOwnsFrames==true) "FINGERSPELL" else "WORD"
                        val sourceTimestamp=image.imageInfo.timestamp
                        val analysisStarted=android.os.SystemClock.elapsedRealtimeNanos()
                        frameAnalyzer.analyze(image)
                        if(timing?.analyzed(sourceTimestamp,
                            (android.os.SystemClock.elapsedRealtimeNanos()-analysisStarted)/1e6)==true) {
                            java.io.File(filesDir,"camera_timing_${ticket}_${if(boundFront) "front" else "back"}.json")
                                .writeText(timing.report(processingMode).toString(2))
                        }
                    }
                }
                phoneAnalysis = analysis
                try {
                    provider.bindToLifecycle(this, selector, preview, analysis)
                    cameraSwitching = false
                    val enabled = BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED &&
                        provider.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA) &&
                        provider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)
                    binding.cameraToggle.isEnabled = enabled
                    binding.cameraToggle.alpha = if(enabled) 1f else 0.5f
                    binding.cameraToggle.contentDescription = if(enabled) "Switch front or rear camera" else "Front camera only"
                    binding.glossText.text = "Initializing recognition�"
                } catch (failure: Throwable) {
                    cameraSwitching = false
                    renderRuntimeError("Camera unavailable", failure.message.orEmpty())
                    Log.e(TAG, "Camera bind failed; no recognition fallback", failure)
                }
            }
        }
    }

    private fun onFrame(frame: FrameResult) {
        val ticket = if (phoneSession != null) processingCameraGeneration else cameraGeneration
        // Lens identity is display metadata only. Candidate01 source coordinates stay unchanged.
        val r = if(phoneSession != null) frame.copy(isFrontCamera = processingFrontCamera) else frame
        runOnUiThread {
            if (ticket != cameraGeneration || isFinishing || isDestroyed) return@runOnUiThread
            if (ConversationTimeline.enabled) {
                if (timelineAwaitingFrame) {
                    timelineAwaitingFrame = false
                    ConversationTimeline.mark("recognition_ready")
                }
                ConversationTimeline.recognitionFps(r.fps)
            }
            if(r.recognitionEvidence!=null || r.recognition is com.example.apphear.pipeline.recognition.RecognitionState.Signing)
                coordination?.wordActivity(committed = r.recognitionEvidence != null)
            val spelling = fingerspellRuntime?.snapshot
            if (spelling?.mode == RecognitionMode.FINGERSPELL) {
                frameCount++
                binding.overlayView.setResult(r)
                binding.fpsText.text = getString(R.string.fps_hud, r.fps, r.qualityLabel)
                renderFingerspell(spelling)
                return@runOnUiThread
            }
            if (r.qualityLabel == "FINGERSPELL") return@runOnUiThread
            if (ConversationPhraseAssist.enabled && lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
                val nowSigning = r.recognition is com.example.apphear.pipeline.recognition.RecognitionState.Signing
                if (nowSigning && !signingInProgress) {
                    signingInProgress = true
                    signingVisible = true
                    ConversationPhraseAssist.signingStarted()
                    renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
                } else if (!nowSigning) {
                    signingInProgress = false
                }
                r.recognitionEvidence?.let { evidence ->
                    if (signingTurn.add(evidence)) {
                        ConversationTimeline.mark("sign_committed", "event" to evidence.eventId)
                        signsCommitted++
                        signingVisible = true
                        ConversationPhraseAssist.signingStarted()
                        Stage3Diagnostics.committed(evidence)
                        ConversationPhraseAssist.previewSupportedTurn(signingTurn.snapshot(),
                            r.phoneSentence.orEmpty(), evidenceInterrupted || signingTurn.overflowed)
                        sentenceShadow?.let { shadow ->
                            val hearing = ConversationPhraseAssist.presentationState.value
                            shadow.signsChanged(r.phoneSentence.orEmpty(), signingTurn.snapshot(),
                                !(evidenceInterrupted || signingTurn.overflowed), hearing.hearingText, hearing.hearingTurnId)
                        }
                        renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
                    }
                }
            }
            frameCount++
            binding.overlayView.setResult(r)
            binding.fpsText.text = getString(R.string.fps_hud, r.fps, r.qualityLabel)
            val maxedOut = r.poseEveryN >= 4 && r.fps < LandmarkerConfig.MIN_PIPELINE_FPS
            val struggling = frameCount > 60 && (maxedOut || r.lowFpsActive)
            binding.degradedBanner.visibility = if (struggling && !degradedBannerDismissed) View.VISIBLE else View.GONE

            modelLoadError?.let {
                renderRuntimeError(getString(R.string.recognition_model_load_failed), it)
                return@runOnUiThread
            }

            if (r.phoneReady == false && r.recognition is com.example.apphear.pipeline.recognition.RecognitionState.Idle) {
                binding.glossText.text = "Initializing recognition…"
                binding.altText.visibility = View.GONE
                binding.sentenceText.text = sentenceAssistDisplay(r.phoneSentence.orEmpty()
                    .ifBlank { getString(R.string.sentence_placeholder) })
                updateSentenceCardVisibility()
                return@runOnUiThread
            }

            val snapshot = RecognitionUiSnapshot.from(
                state = r.recognition,
                sentence = r.phoneSentence ?: recognizer?.sentenceText.orEmpty(),
                idleText = getString(R.string.gloss_placeholder),
                signingText = getString(R.string.signing),
                sentencePlaceholder = getString(R.string.sentence_placeholder),
            )
            renderRecognitionSnapshot(snapshot)
        }
    }

    private fun renderRecognitionSnapshot(snapshot: RecognitionUiSnapshot) {
        if (renderRuD1QueueStatus()) return
        binding.glossText.text = snapshot.primaryText
        binding.altText.text = snapshot.candidatesText
        binding.altText.visibility = if (snapshot.showCandidates) View.VISIBLE else View.GONE
        binding.sentenceText.text = sentenceAssistDisplay(snapshot.sentenceText)
        updateSentenceCardVisibility()
    }

    /**
     * recognitionModeToolbar: a toggle under Hear shows or hides WORD / FINGERSPELL buttons, so the
     * mode can change without leaving for Settings. The choice is saved like the Settings option and
     * goes through Context Assist's coordinator when it is running, as automatic switching does.
     */
    private fun installModeToolbar() {
        binding.modeToolsToggle.visibility = View.VISIBLE
        binding.modeToolsToggle.setOnClickListener {
            val open = binding.modeToolsGroup.visibility != View.VISIBLE
            ConversationTimeline.tap("recognition", if (open) "mode_tools_open" else "mode_tools_close")
            setModeToolbarOpen(open)
        }
        binding.modeWordButton.setOnClickListener { requestRecognitionMode(RecognitionMode.WORD) }
        binding.modeSpellButton.setOnClickListener { requestRecognitionMode(RecognitionMode.FINGERSPELL) }
        binding.modeWordButton.tooltipText = getString(R.string.mode_toolbar_word)
        binding.modeSpellButton.tooltipText = getString(R.string.mode_toolbar_spell)
        renderModeToolbar(currentRecognitionMode())
    }

    private fun setModeToolbarOpen(open: Boolean) {
        binding.modeToolsGroup.visibility = if (open) View.VISIBLE else View.GONE
        binding.modeToolsToggle.setBackgroundResource(if (open) R.drawable.circle_btn_selected else R.drawable.circle_btn_white)
        binding.modeToolsToggle.contentDescription =
            getString(if (open) R.string.mode_toolbar_hide else R.string.mode_toolbar_show)
        renderModeToolbar(currentRecognitionMode())
    }

    /**
     * A mode chosen by Context Assist's coordinator. When a hearing question (name, place, spelling)
     * switched to FINGERSPELL by itself, the mode buttons open so the signer sees it and can tap back.
     */
    private fun onCoordinatedMode(mode: RecognitionMode) {
        val bridge = coordination ?: return
        if (mode == RecognitionMode.FINGERSPELL && bridge.automaticSwitch) {
            ConversationTimeline.mark("mode_auto_switch", "to" to "fingerspell", "reason" to bridge.switchReason)
            if (BuildConfig.RECOGNITION_MODE_TOOLBAR_ENABLED && recognitionSettings.selectionAvailable) setModeToolbarOpen(true)
        }
        renderModeToolbar(mode)
    }

    private fun currentRecognitionMode(): RecognitionMode = fingerspellRuntime?.snapshot?.mode ?: selectedRecognitionMode

    private fun requestRecognitionMode(mode: RecognitionMode) {
        val current = currentRecognitionMode()
        if (mode == current) return
        if (mode == RecognitionMode.FINGERSPELL && fingerspellRuntime == null) {
            Toast.makeText(this, R.string.mode_toolbar_spell_loading, Toast.LENGTH_SHORT).show()
            return
        }
        val spelled = fingerspellRuntime?.snapshot?.takeIf { it.mode == RecognitionMode.FINGERSPELL }
            ?.let { it.confirmed + it.preview }.orEmpty()
        if (mode == RecognitionMode.WORD && spelled.isNotBlank()) {
            androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle(R.string.mode_toolbar_leave_spelling_title)
                .setMessage(R.string.mode_toolbar_leave_spelling_message)
                .setPositiveButton(R.string.mode_toolbar_leave_spelling_confirm) { _, _ -> switchRecognitionMode(mode) }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
            return
        }
        switchRecognitionMode(mode)
    }

    private fun switchRecognitionMode(mode: RecognitionMode) {
        ConversationTimeline.tap("recognition", if (mode == RecognitionMode.WORD) "mode_word" else "mode_fingerspell")
        recognitionSettings.select(mode)
        val bridge = coordination
        if (bridge != null) {
            bridge.manual(mode)
        } else {
            selectedRecognitionMode = mode
            if (!cameraExecutor.isShutdown) cameraExecutor.execute { fingerspellRuntime?.select(mode) }
        }
        renderModeToolbar(mode)
        Toast.makeText(this, if (mode == RecognitionMode.WORD) R.string.mode_toolbar_switched_word
            else R.string.mode_toolbar_switched_spell, Toast.LENGTH_SHORT).show()
    }

    private fun renderModeToolbar(mode: RecognitionMode) {
        if (!BuildConfig.RECOGNITION_MODE_TOOLBAR_ENABLED) return
        val word = mode == RecognitionMode.WORD
        binding.modeWordButton.setBackgroundResource(if (word) R.drawable.circle_btn_selected else R.drawable.circle_btn_white)
        binding.modeSpellButton.setBackgroundResource(if (word) R.drawable.circle_btn_white else R.drawable.circle_btn_selected)
        binding.modeWordButton.isSelected = word
        binding.modeSpellButton.isSelected = !word
    }

    /** Added only in the opt-in debug build; default/release layout and WORD controls unchanged. */
    private fun installFingerspellControls() {
        if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) {
            fingerspellRuntime?.snapshot?.let(::renderFingerspell)
            return
        }
        val container = binding.expandableContent.getChildAt(0) as LinearLayout
        val panel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        fingerspellStatus = TextView(this).apply { text = "Experimental fingerspelling • select a mode"; textSize = 14f; setTextColor(getColor(R.color.color_text_primary)) }
        panel.addView(fingerspellStatus)
        panel.addView(TextView(this).apply {
            text = if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) "Hold one letter until it appears. Lower your hand to repeat a letter. Review, then Use." else "One attempt: Start → spell → Done → review → Use"
            textSize = 12f; setTextColor(getColor(R.color.color_text_secondary))
        })
        fun row(vararg labels: String) {
            val line = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            for (label in labels) {
                val button = MaterialButton(this).apply {
                    setTextColor(android.content.res.ColorStateList(
                        arrayOf(intArrayOf(android.R.attr.state_enabled), intArrayOf()),
                        intArrayOf(getColor(R.color.color_text_on_brand), getColor(R.color.color_text_secondary))))
                    text = label; contentDescription = "Fingerspell $label"; textSize = 12f
                    layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                    setOnClickListener { cameraExecutor.execute {
                        val runtime = fingerspellRuntime ?: return@execute
                        when (label) {
                            "WORD", "FINGERSPELL" -> {
                                val mode = RecognitionMode.valueOf(label)
                                runtime.select(mode)
                                selectedRecognitionMode = mode
                                recognitionSettings.select(mode)
                            }
                            "Start" -> runtime.start()
                            "Done" -> runtime.finish()
                            "Use" -> runtime.confirm()
                            "Retry" -> runtime.retry()
                            "Clear" -> runtime.clear()
                        }
                    } }
                }
                fingerspellButtons[label] = button; line.addView(button)
            }
            panel.addView(line)
        }
        row("WORD", "FINGERSPELL")
        if (!BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) row("Start", "Done")
        row("Use", "Retry", "Clear")
        container.addView(panel, 0)
        fingerspellRuntime?.snapshot?.let(::renderFingerspell)
    }

    private fun onFingerspell(snapshot: FingerspellSnapshot) {
        runOnUiThread {
            if (isFinishing || isDestroyed || !lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) return@runOnUiThread
            // Reject stale queued snapshots after mode/session/lifecycle transitions.
            if (fingerspellRuntime?.snapshot !== snapshot) return@runOnUiThread
            renderFingerspell(snapshot)
            renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
        }
    }

    private fun renderFingerspell(s: FingerspellSnapshot) {
        coordination?.recognitionChanged()
        renderModeToolbar(s.mode)
        val active = s.mode == RecognitionMode.FINGERSPELL
        val busy = s.phase == FingerspellPhase.CAPTURING || s.phase == FingerspellPhase.DECODING
        fingerspellStatus?.text = if (active) "${s.message} • ${s.observations} observations" else "WORD mode • experimental fingerspelling available"
        fingerspellButtons["WORD"]?.isEnabled = active && (!busy || BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED)
        fingerspellButtons["FINGERSPELL"]?.isEnabled = !active
        fingerspellButtons["Start"]?.isEnabled = active && !busy
        fingerspellButtons["Done"]?.isEnabled = active && s.phase == FingerspellPhase.CAPTURING
        fingerspellButtons["Use"]?.isEnabled = active && s.phase == FingerspellPhase.PREVIEW && s.preview.isNotBlank()
        fingerspellButtons["Retry"]?.isEnabled = active && s.phase != FingerspellPhase.DECODING
        fingerspellButtons["Clear"]?.isEnabled = active && s.phase != FingerspellPhase.DECODING
        if (BuildConfig.FINGERSPELL_CONTINUOUS_ENABLED) {
            // CURRENT SIGN is the live letter; RECOGNIZED is the accumulated spelling.
            (binding.glossText.parent as View).visibility = View.VISIBLE
            if (active) {
                binding.glossText.text = s.currentLetter.ifBlank { getString(R.string.gloss_placeholder) }
                binding.altText.visibility = View.GONE
                val spelling = s.confirmed + s.preview
                binding.sentenceText.text = spelling.ifBlank { getString(R.string.sentence_placeholder) }
                binding.sentenceText.contentDescription = if (s.preview.isNotEmpty())
                    "Detected spelling: $spelling. Tap Hear to review and confirm." else spelling.ifBlank { "Waiting for letters" }
                // This empty FINGERSPELL card remains visible; WORD still uses its original visibility rule.
                binding.sentenceCard.visibility = View.VISIBLE
            }
            return
        }
        if (active) {
            binding.glossText.text = s.preview.ifBlank { when(s.phase) { FingerspellPhase.CAPTURING -> "Spelling…"; FingerspellPhase.DECODING -> "Decoding…"; FingerspellPhase.ERROR -> "Retry needed"; else -> "Ready" } }
            binding.altText.visibility = View.GONE
            binding.sentenceText.text = s.confirmed.ifBlank { "Confirm spelling with Use" }
            updateSentenceCardVisibility()
        }
    }

    /**
     * Diagnostic-only queue prompt. It deliberately changes display text only; recognition,
     * frame timing, S1-S7 state, and the production build remain untouched. Keeping READY on
     * screen makes queue advancement safe: launching the next item never starts its capture.
     */
    private fun renderRuD1QueueStatus(): Boolean {
        if (!ruD1.config.enabled) return false
        val gloss = ruD1QueueGloss()
        if (gloss.isBlank()) return false
        val repetition = intent.getStringExtra(EXTRA_RU_D1_REPETITION_ID).orEmpty().trim()
        val order = intent.getIntExtra(EXTRA_RU_D1_CAPTURE_ORDER, 0)
        val total = intent.getIntExtra(EXTRA_RU_D1_TOTAL_ATTEMPTS, 0)
        val position = if (order > 0 && total > 0) "%02d/%02d".format(order, total) else "RU-D1"
        val attempt = listOf(gloss, repetition).filter { it.isNotBlank() }.joinToString(" • ")
        val instruction = intent.getStringExtra(EXTRA_RU_D1_INSTRUCTION_B64)
            ?.let { encoded ->
                runCatching { String(Base64.decode(encoded, Base64.NO_WRAP), Charsets.UTF_8) }.getOrDefault("")
            }
            .orEmpty()
            .trim()

        when (ruD1DisplayState) {
            RuD1DisplayState.READY -> {
                binding.glossText.text = "READY: $attempt"
                binding.altText.text = "$position • Long-press CLEAR to start"
                binding.sentenceText.text = instruction.ifBlank { "Return to rest before starting" }
            }
            RuD1DisplayState.RECORDING -> {
                binding.glossText.text = "RECORDING: $attempt"
                binding.altText.text = "$position • Sign once, return to rest, then long-press CLEAR to save"
                binding.sentenceText.text = "Capture active"
            }
            RuD1DisplayState.SAVING -> {
                binding.glossText.text = "SAVING: $attempt"
                binding.altText.text = "$position • Please wait"
                binding.sentenceText.text = "Finalizing evidence"
            }
            RuD1DisplayState.SAVED -> {
                binding.glossText.text = "SAVED: $attempt"
                binding.altText.text = "$position • Preparing the next queued attempt"
                binding.sentenceText.text = "Keep resting; do not start yet"
            }
        }
        binding.altText.visibility = View.VISIBLE
        return true
    }

    private fun ruD1QueueGloss(): String =
        intent.getStringExtra(EXTRA_RU_D1_GLOSS).orEmpty().trim().uppercase()

    private fun renderRuntimeError(title: String, details: String) {
        binding.glossText.text = title
        binding.altText.text = details
        binding.altText.visibility = if (details.isBlank()) View.GONE else View.VISIBLE
        binding.degradedBannerText.text = title
        binding.degradedBanner.visibility = if (degradedBannerDismissed) View.GONE else View.VISIBLE
    }

    private fun logPerformanceSupport() {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val saver = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) pm.isPowerSaveMode else false
        Log.i(TAG, "performance_support ${deviceSummary()} keep_screen_awake=true battery_saver=$saver")
        if (saver) {
            Log.w(TAG, "Battery Saver is enabled; profiling FPS may be lower than normal.")
        }
    }

    private fun deviceSummary(): String =
        "device='${Build.MANUFACTURER} ${Build.MODEL}' android=${Build.VERSION.RELEASE} sdk=${Build.VERSION.SDK_INT} " +
            "battery_saver=${batterySaverEnabled()} profiling_mode=${FeatureFlags.PROFILING_MODE} " +
            "ru_d10_a=${FeatureFlags.RU_D10_OBSERVATION_CONTINUITY} " +
            "ru_d10_b=${FeatureFlags.RU_D10_S5_ONE_SHORT_GAP} " +
            "a1_available=${FeatureFlags.A1_INDEPENDENT_CLOCK_AVAILABLE}"

    private fun batterySaverEnabled(): Boolean {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) pm.isPowerSaveMode else false
    }

    private fun cameraAnalysisSize(): Size {
        val fallback = Size(640, 480)
        return try {
            val text = assets.open("recognition_config.json").bufferedReader().use { it.readText() }
            val camera = JSONObject(text).optJSONObject("camera_analysis") ?: return fallback
            val width = camera.optInt("target_width", fallback.width).coerceAtLeast(160)
            val height = camera.optInt("target_height", fallback.height).coerceAtLeast(120)
            Size(width, height)
        } catch (t: Throwable) {
            Log.w(TAG, "failed to read camera_analysis config, using ${fallback.width}x${fallback.height}: ${t.message}")
            fallback
        }
    }

    override fun onDestroy() {
        ConversationTimeline.screenDestroyed("recognition")
        ConversationScreens.recognitionDestroyed(this)
        sentenceShadow?.reset()
        super.onDestroy()
        cameraProvider?.unbindAll()
        cameraExecutor.shutdown()
        val closingPhoneAnalyzer = phoneAnalyzer
        val closingPhoneSession = phoneSession
        val closingFingerspell = fingerspellRuntime
        if (closingPhoneAnalyzer != null || closingPhoneSession != null) {
            phoneAnalyzer = null
            phoneSession = null
            fingerspellRuntime = null
            a1ShutdownExecutor.submit {
                try {
                    if (cameraExecutor.awaitTermination(10, TimeUnit.SECONDS)) {
                        closingPhoneAnalyzer?.close()
                        closingPhoneSession?.close()
                        closingFingerspell?.close()
                    } else {
                        Log.e(TAG, "Camera worker did not stop; keeping native runtime open to avoid use-after-free")
                    }
                } catch (failure: Throwable) {
                    Log.e(TAG, "Causal runtime shutdown failed", failure)
                } finally {
                    a1ShutdownExecutor.shutdown()
                }
            }
            if (::ruD1.isInitialized) ruD1.close()
            if (::speechPlayer.isInitialized) speechPlayer.close()
            return
        }
        if (a1Active) {
            val currentAnalyzer = analyzer
            analyzer = null
            val previousShutdown = a1ShutdownFuture
            a1ShutdownExecutor.submit {
                try {
                    // Tasks on this single executor are FIFO; get() also documents the required
                    // happens-before edge when an earlier pause/switch shutdown exists.
                    previousShutdown?.get()
                    currentAnalyzer?.close()
                    landmarkers?.close()
                    recognizer?.close()
                    if (::ruD1.isInitialized) ruD1.close()
                    Log.i(TAG, "A1 lifecycle resources closed after worker join")
                } catch (t: Throwable) {
                    // Never close the shared landmarker/recognizer after a failed worker join. A
                    // bounded process-lifetime leak is safer than native use-after-free.
                    Log.e(TAG, "A1 lifecycle shutdown failed; shared runtime left open", t)
                } finally {
                    a1ShutdownExecutor.shutdown()
                }
            }
        } else {
            analyzer?.close()
            landmarkers?.close()
            recognizer?.close()
            if (::ruD1.isInitialized) ruD1.close()
            a1ShutdownExecutor.shutdown()
        }
        if (::speechPlayer.isInitialized) speechPlayer.close()
    }

    override fun onStop() {
        autoListenTicket++
        ConversationTimeline.mark("recognition_stopped")
        coordination?.stopped()
        binding.overlayView.clear()
        signingVisible = false
        signingInProgress = false
        ConversationPhraseAssist.recognitionScreenStopped(openingHearingTurnId)
        renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
        if (ConversationPhraseAssist.enabled && signingTurn.snapshot().isNotEmpty()) evidenceInterrupted = true
        signingTurn.clear()
        val spelling = fingerspellRuntime
        if (spelling != null && !cameraExecutor.isShutdown) cameraExecutor.execute { spelling.pause() }
        else phoneAnalyzer?.resetTemporalSession()
        if (a1Active) {
            closeA1AnalyzerAsync(rebindWhenStarted = false)
        }
        super.onStop()
    }

    override fun onStart() {
        super.onStart()
        timelineAwaitingFrame = ConversationTimeline.enabled
        ConversationTimeline.mark("recognition_started")
        selectedRecognitionMode = recognitionSettings.current()
        renderModeToolbar(selectedRecognitionMode)
        coordination?.started(selectedRecognitionMode)
        if (::cameraExecutor.isInitialized && fingerspellRuntime != null && !cameraExecutor.isShutdown) {
            cameraExecutor.execute { fingerspellRuntime?.select(selectedRecognitionMode) }
        }
        if (a1Active && analyzer == null && landmarkers != null && cameraProvider != null) {
            val shutdown = a1ShutdownFuture
            if (shutdown == null) rebindCamera() else resumeAfterA1Shutdown(shutdown)
        }
    }

    private fun closeA1AnalyzerAsync(rebindWhenStarted: Boolean) {
        val closing = analyzer ?: return
        analyzer = null
        cameraProvider?.unbindAll()
        val shutdown = a1ShutdownExecutor.submit { closing.close() }
        a1ShutdownFuture = shutdown
        if (rebindWhenStarted) resumeAfterA1Shutdown(shutdown)
    }

    private fun resumeAfterA1Shutdown(shutdown: Future<*>) {
        if (a1ResumePending) return
        a1ResumePending = true
        lifecycleScope.launch {
            val outcome = withContext(Dispatchers.IO) { runCatching { shutdown.get() } }
            a1ResumePending = false
            if (a1ShutdownFuture === shutdown) a1ShutdownFuture = null
            outcome.onFailure { failure ->
                Log.e(TAG, "A1 worker shutdown failed; camera will not rebind", failure)
                renderRuntimeError("A1 shutdown failed", failure.message.orEmpty())
            }
            if (
                outcome.isSuccess &&
                !isFinishing &&
                !isDestroyed &&
                lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED) &&
                analyzer == null
            ) {
                rebindCamera()
            }
        }
    }

    companion object {
        const val TAG = "AppHearRecognition"
        const val KEY_HAND = "handedness"
        const val EXTRA_RU_D1_GLOSS = "ru_d1_gloss"
        const val EXTRA_RU_D1_EXPECTED_HANDS = "ru_d1_expected_hands"
        const val EXTRA_RU_D1_SIGNER_ID = "ru_d1_signer_id"
        const val EXTRA_RU_D1_VARIANT = "ru_d1_variant"
        const val EXTRA_RU_D1_SESSION_ID = "ru_d1_session_id"
        const val EXTRA_A1_MODE = "a1_mode"
        const val EXTRA_A1_RUN_ID = "a1_run_id"
        const val EXTRA_A1_MAX_POSE_AGE_MS = "a1_max_pose_age_ms"
        const val BASELINE_MODE = "BASELINE"
        const val A1_MODE = "A1"
        const val EXTRA_RU_D1_REPETITION_ID = "ru_d1_repetition_id"
        const val EXTRA_RU_D1_CAPTURE_ORDER = "ru_d1_capture_order"
        const val EXTRA_RU_D1_TOTAL_ATTEMPTS = "ru_d1_total_attempts"
        const val EXTRA_RU_D1_INSTRUCTION_B64 = "ru_d1_instruction_b64"
    }

    private fun toggleRuD1Attempt() {
        if (ruD1Transitioning) return
        val pipeline = recognizer
        if (pipeline == null) {
            Toast.makeText(this, "RU-D1 unavailable: recognizer not loaded", Toast.LENGTH_LONG).show()
            return
        }
        if (ruD1.isActive) {
            pipeline.ruD1Enabled = false
            ruD1Transitioning = true
            ruD1DisplayState = RuD1DisplayState.SAVING
            renderRuD1QueueStatus()
            lifecycleScope.launch {
                val directory = withContext(Dispatchers.IO) { ruD1.stopAttempt() }
                ruD1Transitioning = false
                ruD1DisplayState = RuD1DisplayState.SAVED
                renderRuD1QueueStatus()
                Toast.makeText(
                    this@RecognitionActivity,
                    "RU-D1 saved: ${directory?.name}",
                    Toast.LENGTH_LONG,
                ).show()
            }
            return
        }
        val gloss = intent.getStringExtra(EXTRA_RU_D1_GLOSS).orEmpty().trim().uppercase()
        val expectedHands = intent.getStringExtra(EXTRA_RU_D1_EXPECTED_HANDS).orEmpty().trim().lowercase()
        val signerId = intent.getStringExtra(EXTRA_RU_D1_SIGNER_ID).orEmpty().trim()
        val variant = intent.getStringExtra(EXTRA_RU_D1_VARIANT).orEmpty().trim()
        val sessionId = intent.getStringExtra(EXTRA_RU_D1_SESSION_ID).orEmpty().trim()
        val repetitionId = intent.getStringExtra(EXTRA_RU_D1_REPETITION_ID).orEmpty().trim()
        val captureOrder = intent.getIntExtra(EXTRA_RU_D1_CAPTURE_ORDER, 0)
        val spec = runCatching {
            RuD1AttemptSpec(
                gloss,
                expectedHands,
                signerId,
                variant,
                sessionId,
                repetitionId,
                captureOrder,
            )
        }.getOrElse {
            Toast.makeText(
                this,
                "RU-D1 extras required: gloss, expected hands, signer id",
                Toast.LENGTH_LONG,
            ).show()
            return
        }
        ruD1Transitioning = true
        lifecycleScope.launch {
            val result = withContext(Dispatchers.IO) { runCatching { ruD1.startAttempt(spec) } }
            result.onSuccess { directory ->
                pipeline.ruD1Enabled = true
                pipeline.prepareRuD1Attempt()
                ruD1Transitioning = false
                ruD1DisplayState = RuD1DisplayState.RECORDING
                renderRuD1QueueStatus()
                Toast.makeText(
                    this@RecognitionActivity,
                    "RU-D1 recording ${spec.gloss}; long-press CLEAR to stop (${directory.name})",
                    Toast.LENGTH_LONG,
                ).show()
            }.onFailure {
                pipeline.ruD1Enabled = false
                ruD1Transitioning = false
                ruD1DisplayState = RuD1DisplayState.READY
                renderRuD1QueueStatus()
                Toast.makeText(
                    this@RecognitionActivity,
                    "RU-D1 start failed: ${it.message}",
                    Toast.LENGTH_LONG,
                ).show()
            }
        }
    }

    private enum class RuD1DisplayState { READY, RECORDING, SAVING, SAVED }
}
