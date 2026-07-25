package com.apphear.reactprototype

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.Build
import android.os.Looper
import android.os.SystemClock
import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.WritableMap
import com.facebook.react.bridge.WritableNativeArray
import com.facebook.react.bridge.WritableNativeMap
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

class RN02HandBenchmarkModule(
  private val reactContext: ReactApplicationContext,
) : ReactContextBaseJavaModule(reactContext) {
  private val lock = Any()
  private var handLandmarker: HandLandmarker? = null
  private var cameraProvider: ProcessCameraProvider? = null
  private var analysisExecutor: ExecutorService? = null
  private var startedAtMs: Long? = null
  private var endedAtMs: Long? = null
  private var lastSampleAtMs = 0L
  private var frameWidth: Int? = null
  private var frameHeight: Int? = null
  private var processedFrames = 0
  private var skippedFrames = 0
  private var handHitFrames = 0
  private var twoHandHitFrames = 0
  private val latenciesMs = mutableListOf<Double>()
  private val samples = mutableListOf<RN02Sample>()
  private var notes = listOf<String>()

  override fun getName(): String = "RN02HandBenchmarkModule"

  @ReactMethod
  fun startHandBenchmark(promise: Promise) {
    try {
      if (ContextCompat.checkSelfPermission(reactContext, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
        promise.reject("rn02_android_camera_permission", "Camera permission is required for RN02 hand benchmark")
        return
      }

      val activity = reactContext.currentActivity
      val lifecycleOwner = activity as? LifecycleOwner
      if (activity == null || lifecycleOwner == null) {
        promise.reject("rn02_android_no_lifecycle", "Current React activity is not ready for CameraX binding")
        return
      }

      closeRuntime()
      resetStats()
      handLandmarker = createHandLandmarker()
      analysisExecutor = Executors.newSingleThreadExecutor()
      val providerFuture = ProcessCameraProvider.getInstance(reactContext)
      providerFuture.addListener(
        {
          try {
            val provider = providerFuture.get()
            val analyzer = buildImageAnalysis()
            analyzer.setAnalyzer(analysisExecutor ?: ContextCompat.getMainExecutor(reactContext)) { imageProxy ->
              analyzeFrame(imageProxy)
            }
            provider.unbindAll()
            provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_FRONT_CAMERA, analyzer)
            cameraProvider = provider
            synchronized(lock) {
              notes = listOf(
                "RN02 Android CameraX ImageAnalysis is running.",
                "HandLandmarker detects frames natively in IMAGE mode.",
                "React Native receives compact benchmark samples only.",
                "This is not recognition and does not exercise the 258-feature contract.",
              )
            }
            promise.resolve(null)
          } catch (error: Throwable) {
            closeRuntime()
            promise.reject("rn02_android_camera_bind_failed", error.message, error)
          }
        },
        ContextCompat.getMainExecutor(reactContext),
      )
    } catch (error: Throwable) {
      closeRuntime()
      promise.reject("rn02_android_start_failed", error.message, error)
    }
  }

  @ReactMethod
  fun stopHandBenchmark(promise: Promise) {
    try {
      val started = synchronized(lock) { startedAtMs }
      if (started == null) {
        promise.reject("rn02_android_not_started", "RN02 hand benchmark has not been started")
        return
      }

      closeRuntime()
      synchronized(lock) {
        endedAtMs = System.currentTimeMillis()
        notes = notes + "RN02 Android stopped after native hand-only CameraX benchmark."
      }
      promise.resolve(makeSession())
    } catch (error: Throwable) {
      promise.reject("rn02_android_stop_failed", error.message, error)
    }
  }

  @ReactMethod
  fun getLatestHandBenchmark(promise: Promise) {
    synchronized(lock) {
      promise.resolve(if (startedAtMs == null && endedAtMs == null) null else makeSessionLocked())
    }
  }

  override fun invalidate() {
    closeRuntime()
    super.invalidate()
  }

  private fun createHandLandmarker(): HandLandmarker {
    val baseOptions = BaseOptions.builder()
      .setModelAssetPath(MODEL_ASSET)
      .build()
    val options = HandLandmarker.HandLandmarkerOptions.builder()
      .setBaseOptions(baseOptions)
      .setRunningMode(RunningMode.IMAGE)
      .setNumHands(2)
      .setMinHandDetectionConfidence(0.5f)
      .setMinHandPresenceConfidence(0.5f)
      .setMinTrackingConfidence(0.5f)
      .build()
    return HandLandmarker.createFromOptions(reactContext, options)
  }

  private fun buildImageAnalysis(): ImageAnalysis {
    return ImageAnalysis.Builder()
      .setTargetResolution(Size(480, 854))
      .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
      .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
      .build()
  }

  private fun analyzeFrame(imageProxy: ImageProxy) {
    try {
      val landmarker = synchronized(lock) { handLandmarker } ?: return
      val bitmap = imageProxy.toBitmapArgb8888()
      val rotatedBitmap = bitmap.rotate(imageProxy.imageInfo.rotationDegrees)
      frameWidth = rotatedBitmap.width
      frameHeight = rotatedBitmap.height
      val mpImage = BitmapImageBuilder(rotatedBitmap).build()
      val startedNs = SystemClock.elapsedRealtimeNanos()
      val result = landmarker.detect(mpImage)
      val latencyMs = (SystemClock.elapsedRealtimeNanos() - startedNs) / 1_000_000.0

      synchronized(lock) {
        processedFrames += 1
        latenciesMs.add(latencyMs)
        val hands = result.landmarks().size
        if (hands > 0) handHitFrames += 1
        if (hands >= 2) twoHandHitFrames += 1
        val now = System.currentTimeMillis()
        val started = startedAtMs ?: now
        if (now - lastSampleAtMs >= SAMPLE_PERIOD_MS) {
          lastSampleAtMs = now
          samples.add(makeSampleLocked(now - started))
        }
      }
    } catch (_: Throwable) {
      synchronized(lock) { skippedFrames += 1 }
    } finally {
      imageProxy.close()
    }
  }

  private fun ImageProxy.toBitmapArgb8888(): Bitmap {
    val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
    val buffer = planes[0].buffer
    buffer.rewind()
    bitmap.copyPixelsFromBuffer(buffer)
    return bitmap
  }

  private fun Bitmap.rotate(rotationDegrees: Int): Bitmap {
    if (rotationDegrees == 0) return this
    val matrix = Matrix().apply { postRotate(rotationDegrees.toFloat()) }
    return Bitmap.createBitmap(this, 0, 0, width, height, matrix, true)
  }

  private fun resetStats() {
    synchronized(lock) {
      val now = System.currentTimeMillis()
      startedAtMs = now
      endedAtMs = null
      lastSampleAtMs = now
      frameWidth = null
      frameHeight = null
      processedFrames = 0
      skippedFrames = 0
      handHitFrames = 0
      twoHandHitFrames = 0
      latenciesMs.clear()
      samples.clear()
      notes = listOf("RN02 Android native module loaded hand_landmarker.task; camera binding pending.")
    }
  }

  private fun closeRuntime() {
    val provider = cameraProvider
    cameraProvider = null
    if (provider != null) {
      if (Looper.myLooper() == Looper.getMainLooper()) {
        provider.unbindAll()
      } else {
        val latch = CountDownLatch(1)
        ContextCompat.getMainExecutor(reactContext).execute {
          try {
            provider.unbindAll()
          } finally {
            latch.countDown()
          }
        }
        latch.await(2, TimeUnit.SECONDS)
      }
    }
    handLandmarker?.close()
    handLandmarker = null
    analysisExecutor?.shutdownNow()
    analysisExecutor = null
  }

  private fun makeSession(): WritableMap {
    synchronized(lock) {
      return makeSessionLocked()
    }
  }

  private fun makeSessionLocked(): WritableMap {
    val started = startedAtMs ?: System.currentTimeMillis()
    val map = WritableNativeMap()
    map.putString("schema", SCHEMA)
    map.putString("mode", MODE)
    map.putString("startedAtIso", iso(started))
    endedAtMs?.let { map.putString("endedAtIso", iso(it)) }
    map.putString("devicePlatform", "android")
    map.putString("deviceModel", "${Build.MANUFACTURER} ${Build.MODEL}")
    map.putString("runningMode", "image")
    map.putString("modelAsset", MODEL_ASSET)
    val sampleArray = WritableNativeArray()
    samples.forEach { sampleArray.pushMap(it.toMap()) }
    map.putArray("samples", sampleArray)
    val noteArray = WritableNativeArray()
    notes.forEach { noteArray.pushString(it) }
    map.putArray("notes", noteArray)
    return map
  }

  private fun makeSampleLocked(elapsedMs: Long): RN02Sample {
    val p50 = percentile(latenciesMs, 50.0)
    val p95 = percentile(latenciesMs, 95.0)
    val elapsedSec = elapsedMs.coerceAtLeast(1) / 1000.0
    return RN02Sample(
      elapsedMs = elapsedMs.toInt(),
      processedFrames = processedFrames,
      skippedFrames = skippedFrames,
      handLatencyMsP50 = p50,
      handLatencyMsP95 = p95,
      processedFps = processedFrames / elapsedSec,
      handHitRate = if (processedFrames == 0) 0.0 else handHitFrames.toDouble() / processedFrames,
      twoHandHitRate = if (processedFrames == 0) 0.0 else twoHandHitFrames.toDouble() / processedFrames,
      frameWidth = frameWidth,
      frameHeight = frameHeight,
    )
  }

  private fun percentile(values: List<Double>, percentile: Double): Double {
    if (values.isEmpty()) return 0.0
    val sorted = values.sorted()
    val rank = ((percentile / 100.0) * (sorted.size - 1)).roundToInt()
    return sorted[rank.coerceIn(sorted.indices)]
  }

  private fun iso(timestampMs: Long): String {
    return isoFormatter.get().format(Date(timestampMs))
  }

  private data class RN02Sample(
    val elapsedMs: Int,
    val processedFrames: Int,
    val skippedFrames: Int,
    val handLatencyMsP50: Double,
    val handLatencyMsP95: Double,
    val processedFps: Double,
    val handHitRate: Double,
    val twoHandHitRate: Double,
    val frameWidth: Int?,
    val frameHeight: Int?,
  ) {
    fun toMap(): WritableMap {
      val map = WritableNativeMap()
      map.putInt("elapsedMs", elapsedMs)
      map.putInt("processedFrames", processedFrames)
      map.putInt("skippedFrames", skippedFrames)
      map.putDouble("handLatencyMsP50", handLatencyMsP50)
      map.putDouble("handLatencyMsP95", handLatencyMsP95)
      map.putDouble("processedFps", processedFps)
      map.putDouble("handHitRate", handHitRate)
      map.putDouble("twoHandHitRate", twoHandHitRate)
      frameWidth?.let { map.putInt("frameWidth", it) }
      frameHeight?.let { map.putInt("frameHeight", it) }
      return map
    }
  }

  companion object {
    private const val SCHEMA = "apphear.rn02.hand_landmarker.v1"
    private const val MODE = "rn02_android_hand_only"
    private const val MODEL_ASSET = "hand_landmarker.task"
    private const val SAMPLE_PERIOD_MS = 1000L

    private val isoFormatter = object : ThreadLocal<SimpleDateFormat>() {
      override fun initialValue(): SimpleDateFormat {
        return SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
          timeZone = TimeZone.getTimeZone("UTC")
        }
      }
    }
  }
}
