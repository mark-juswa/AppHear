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
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.example.apphear.databinding.ActivityRecognitionBinding
import com.example.apphear.pipeline.FrameAnalyzer
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.pipeline.LandmarkerBundle
import com.example.apphear.pipeline.LandmarkerConfig
import com.example.apphear.pipeline.recognition.FeatureFlags
import com.example.apphear.pipeline.recognition.Handedness
import com.example.apphear.pipeline.recognition.RecognitionPipeline
import com.example.apphear.pipeline.recognition.RuntimeConfig
import com.example.apphear.ui.recognition.RecognitionUiSnapshot
import com.example.apphear.ui.speech.AppHearSpeechPlayer
import com.example.apphear.ui.speech.SpeechInputHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class RecognitionActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRecognitionBinding
    private lateinit var cameraExecutor: ExecutorService

    private var landmarkers: LandmarkerBundle? = null
    private var recognizer: RecognitionPipeline? = null
    private var runtimeConfig: RuntimeConfig? = null
    private var analyzer: FrameAnalyzer? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var frameCount = 0
    private var frontCamera = true
    private var modelLoadError: String? = null
    private var degradedBannerDismissed = false
    private lateinit var speechPlayer: AppHearSpeechPlayer

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
        speechPlayer = AppHearSpeechPlayer(this)
        binding.btnBack.setOnClickListener { finish() }
        binding.dragHandleWrapper.setOnClickListener {
            binding.expandableContent.visibility =
                if (binding.expandableContent.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }
        cameraExecutor = Executors.newSingleThreadExecutor()
        logPerformanceSupport()

        binding.handToggle.setOnClickListener {
            val next = if (currentHandedness() == Handedness.RIGHT) Handedness.LEFT else Handedness.RIGHT
            prefs.edit().putString(KEY_HAND, next.name).apply()
            applyHandedness(next)
            toastHandedness(next, Toast.LENGTH_SHORT)
        }
        applyHandedness(currentHandedness())
        toastHandedness(currentHandedness(), Toast.LENGTH_LONG)

        binding.clearButton.setOnClickListener {
            recognizer?.clearSentence()
            binding.sentenceText.text = getString(R.string.sentence_placeholder)
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
        val sentence = recognizer?.sentenceText?.trim().orEmpty()
            .ifBlank { binding.sentenceText.text?.toString()?.trim().orEmpty() }
        if (sentence.isBlank() || sentence == getString(R.string.sentence_placeholder)) {
            Toast.makeText(this, R.string.speech_no_text_to_speak, Toast.LENGTH_SHORT).show()
            return
        }
        speechPlayer.speak(sentence)
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
            runtimeConfig = RuntimeConfig.load(applicationContext)
            val bundle = withContext(Dispatchers.IO) { LandmarkerBundle.create(applicationContext) }
            landmarkers = bundle
            if (FeatureFlags.RECOGNITION_ENABLED) {
                val loadResult = withContext(Dispatchers.IO) {
                    runCatching { RecognitionPipeline.load(applicationContext) }
                }
                recognizer = loadResult.getOrElse {
                    modelLoadError = it.message ?: getString(R.string.recognition_model_load_failed)
                    renderRuntimeError(getString(R.string.recognition_model_load_failed), modelLoadError.orEmpty())
                    Toast.makeText(
                        this@RecognitionActivity,
                        getString(R.string.recognition_model_load_failed),
                        Toast.LENGTH_LONG,
                    ).show()
                    null
                }
                if (recognizer != null) {
                    modelLoadError = null
                    applyHandedness(currentHandedness())
                }
            }
            bindCamera()
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
        val bundle = landmarkers ?: return
        val runtime = runtimeConfig ?: RuntimeConfig.load(applicationContext)
        val selector = if (frontCamera) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA

        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }

        analyzer?.close()
        val frameAnalyzer = FrameAnalyzer(
            bundle,
            frontCamera,
            recognizer,
            runtime,
            deviceSummary(),
            ::onFrame,
        ).also { analyzer = it }
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

    private fun onFrame(r: FrameResult) {
        runOnUiThread {
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

            val snapshot = RecognitionUiSnapshot.from(
                state = r.recognition,
                sentence = recognizer?.sentenceText.orEmpty(),
                idleText = getString(R.string.gloss_placeholder),
                signingText = getString(R.string.signing),
                sentencePlaceholder = getString(R.string.sentence_placeholder),
            )
            renderRecognitionSnapshot(snapshot)
        }
    }

    private fun renderRecognitionSnapshot(snapshot: RecognitionUiSnapshot) {
        binding.glossText.text = snapshot.primaryText
        binding.altText.text = snapshot.candidatesText
        binding.altText.visibility = if (snapshot.showCandidates) View.VISIBLE else View.GONE
        binding.sentenceText.text = snapshot.sentenceText
    }

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
            "battery_saver=${batterySaverEnabled()} profiling_mode=${FeatureFlags.PROFILING_MODE}"

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
        analyzer?.close()
        cameraExecutor.shutdown()
        landmarkers?.close()
        recognizer?.close()
        if (::speechPlayer.isInitialized) speechPlayer.close()
    }

    private companion object {
        const val TAG = "AppHearRecognition"
        const val KEY_HAND = "handedness"
    }
}