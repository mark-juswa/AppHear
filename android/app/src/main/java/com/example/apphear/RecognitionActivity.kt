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
import android.widget.TextView
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
    private val signingTurn = SigningTurnBuffer()
    private var evidenceInterrupted = false
    private var signingVisible = false
    private var signingInProgress = false
    private var displayedHearingTurnId: Long? = null
    private var openingHearingTurnId: Long? = null
    private var renderedHints: List<EvidenceAwareReplies.Hint> = emptyList()
    private var lastPulsedEventId: Int? = null
    private var runtimeConfig: RuntimeConfig? = null
    private var analyzer: CloseableFrameAnalyzer? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var frameCount = 0
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
            Toast.makeText(this, R.string.reply_speech_cancelled, Toast.LENGTH_SHORT).show()
            return@registerForActivityResult
        }

        val transcript = result.data
            ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            ?.firstOrNull()
            ?.trim()
            .orEmpty()
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
        openingHearingTurnId = ConversationPhraseAssist.presentationState.value.hearingTurnId
        displayedHearingTurnId = openingHearingTurnId
        binding.sentenceCard.visibility = View.GONE
        speechPlayer = AppHearSpeechPlayer(this)
        ruD1 = RuD1Diagnostics.create(applicationContext)
        binding.btnBack.setOnClickListener { finish() }
        binding.dragHandleWrapper.setOnClickListener {
            binding.expandableContent.visibility =
                if (binding.expandableContent.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }
        cameraExecutor = Executors.newSingleThreadExecutor()
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
            phoneSession?.clearSentence()
            recognizer?.clearSentence()
            signingTurn.clear()
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
        if (ruD1.config.enabled) {
            binding.clearButton.setOnLongClickListener {
                toggleRuD1Attempt()
                true
            }
        }

        binding.speakButton.setOnClickListener {
            startReplySpeechInput()
        }

        binding.hearButton.setOnClickListener {
            speakRecognizedSentence()
        }

        binding.degradedBannerClose.setOnClickListener {
            degradedBannerDismissed = true
            binding.degradedBanner.visibility = View.GONE
        }

        binding.cameraToggle.setOnClickListener {
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

    private fun startReplySpeechInput() {
        if (!SpeechInputHelper.isAvailable(this)) {
            Toast.makeText(this, R.string.speech_unavailable, Toast.LENGTH_SHORT).show()
            return
        }

        try {
            replySpeechLauncher.launch(SpeechInputHelper.createSpeechIntent(getString(R.string.reply_speech_prompt)))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, R.string.speech_unavailable, Toast.LENGTH_SHORT).show()
        }
    }

    private fun speakRecognizedSentence() {
        val sentence = (phoneSession?.sentenceText ?: recognizer?.sentenceText)?.trim().orEmpty()
            .ifBlank { binding.sentenceText.text?.toString()?.trim().orEmpty() }
        if (sentence.isBlank() || sentence == getString(R.string.sentence_placeholder)) {
            Toast.makeText(this, R.string.speech_no_text_to_speak, Toast.LENGTH_SHORT).show()
            return
        }
        speakSentence(sentence)
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

    private fun updateSentenceCardVisibility() {
        val text = binding.sentenceText.text?.toString()?.trim().orEmpty()
        binding.sentenceCard.visibility = if (text.isNotEmpty() &&
            text != getString(R.string.sentence_placeholder)) View.VISIBLE else View.GONE
    }

    private fun openTextToAslReply(transcript: String) {
        val intent = Intent(this, MainActivity::class.java).apply {
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
                        session to Candidate01FrameAnalyzer(
                            applicationContext, session, ::onFrame,
                        ) { failure ->
                            runOnUiThread {
                                if (!isFinishing && !isDestroyed) {
                                    cameraProvider?.unbindAll()
                                    renderRuntimeError("Causal recognition stopped", failure.message.orEmpty())
                                }
                            }
                        }
                    } catch (failure: Throwable) {
                        session.close()
                        throw failure
                    }
                }
            }
            loaded.onSuccess { (session, frameAnalyzer) ->
                if (isFinishing || isDestroyed) {
                    frameAnalyzer.close()
                    session.close()
                    return@launch
                }
                phoneSession = session
                phoneAnalyzer = frameAnalyzer
                Log.i(TAG, "normal backend=Candidate01 package=${session.packageId}")
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
        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }
        val builder = ImageAnalysis.Builder()
            .setTargetResolution(Size(480, 360))
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
        Camera2Interop.Extender(builder).setCaptureRequestOption(
            CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(15, 15),
        )
        val analysis = builder.build().also { it.setAnalyzer(cameraExecutor, frameAnalyzer) }
        try {
            provider.unbindAll()
            frameAnalyzer.resetTemporalSession()
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_FRONT_CAMERA, preview, analysis)
            binding.glossText.text = "Initializing recognition…"
        } catch (failure: Throwable) {
            renderRuntimeError("Front camera unavailable", failure.message.orEmpty())
            Log.e(TAG, "Causal camera bind failed; no legacy fallback", failure)
        }
    }

    private fun onFrame(r: FrameResult) {
        runOnUiThread {
            if (isFinishing || isDestroyed) return@runOnUiThread
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
                        signingVisible = true
                        ConversationPhraseAssist.signingStarted()
                        Stage3Diagnostics.committed(evidence)
                        ConversationPhraseAssist.previewSupportedTurn(signingTurn.snapshot(),
                            r.phoneSentence.orEmpty(), evidenceInterrupted || signingTurn.overflowed)
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
                binding.sentenceText.text = r.phoneSentence.orEmpty()
                    .ifBlank { getString(R.string.sentence_placeholder) }
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
        binding.sentenceText.text = snapshot.sentenceText
        updateSentenceCardVisibility()
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
        super.onDestroy()
        cameraProvider?.unbindAll()
        cameraExecutor.shutdown()
        val closingPhoneAnalyzer = phoneAnalyzer
        val closingPhoneSession = phoneSession
        if (closingPhoneAnalyzer != null || closingPhoneSession != null) {
            phoneAnalyzer = null
            phoneSession = null
            a1ShutdownExecutor.submit {
                try {
                    if (cameraExecutor.awaitTermination(10, TimeUnit.SECONDS)) {
                        closingPhoneAnalyzer?.close()
                        closingPhoneSession?.close()
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
        binding.overlayView.clear()
        signingVisible = false
        signingInProgress = false
        ConversationPhraseAssist.recognitionScreenStopped(openingHearingTurnId)
        renderPhraseAssist(ConversationPhraseAssist.presentationState.value)
        if (ConversationPhraseAssist.enabled && signingTurn.snapshot().isNotEmpty()) evidenceInterrupted = true
        signingTurn.clear()
        phoneAnalyzer?.resetTemporalSession()
        if (a1Active) {
            closeA1AnalyzerAsync(rebindWhenStarted = false)
        }
        super.onStop()
    }

    override fun onStart() {
        super.onStart()
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
