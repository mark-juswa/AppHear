"""Stage isolated camera-binding/presentation changes in the approved app checkout."""
# Exact Kotlin source migration literals intentionally retain their original layout.
# ruff: noqa: E501

import hashlib
import json
from pathlib import Path

APP = Path(r"C:\Users\Gigabyte\.codex\worktrees\fingerspell-continuous-oct05\5. Apphear3")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/camera_input_01"
JAVA = "android/app/src/main/java/com/example/apphear/"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = OUT / "before.json"
    if before.exists():
        raise RuntimeError("Camera port already staged; do not reapply")
    inventory = {
        str(p.relative_to(APP)).replace("\\", "/"): sha(p)
        for p in (APP / "android/app/src").rglob("*")
        if p.is_file()
    }
    inventory["android/app/build.gradle.kts"] = sha(APP / "android/app/build.gradle.kts")
    before.write_text(json.dumps(inventory, indent=2))
    p = APP / "android/app/build.gradle.kts"
    s = p.read_text()
    s = s.replace(
        "    val fingerspellContinuous =",
        '    val recognitionRearCamera = providers.gradleProperty("recognitionRearCamera").map { it.equals("true", ignoreCase=true) }.getOrElse(false)\n    val fingerspellContinuous =',
        1,
    )
    s = s.replace(
        '            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", (',
        '            buildConfigField("boolean", "RECOGNITION_REAR_CAMERA_ENABLED", recognitionRearCamera.toString())\n            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", (',
        1,
    )
    s = s.replace(
        '            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", "false")',
        '            buildConfigField("boolean", "RECOGNITION_REAR_CAMERA_ENABLED", "false")\n            buildConfigField("boolean", "FINGERSPELL_CONTINUOUS_ENABLED", "false")',
        1,
    )
    p.write_text(s)
    p = APP / JAVA / "RecognitionActivity.kt"
    s = p.read_text()
    s = s.replace(
        "    private var frontCamera = true",
        """    private var phoneAnalysis: ImageAnalysis? = null
    @Volatile private var cameraGeneration = 0
    private var processingCameraGeneration = 0
    private var processingFrontCamera = true
    @Volatile private var cameraSwitching = false
    @Volatile private var cameraInputFrames = 0
    private val cameraInputFramesJson = org.json.JSONArray()
    private var frontCamera = true""",
        1,
    )
    s = s.replace(
        """            frontCamera = !frontCamera
            applyCameraLabel()""",
        """            if (phoneSession != null) {
                if (!BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED || cameraSwitching) return@setOnClickListener
                val provider = cameraProvider ?: return@setOnClickListener
                val requested = if (frontCamera) CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
                if (!provider.hasCamera(requested)) {
                    Toast.makeText(this, "Requested camera unavailable", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
            }
            frontCamera = !frontCamera
            applyCameraLabel()""",
        1,
    )
    start = s.index("    private fun bindPhoneCamera(")
    end = s.index("    private fun onFrame(", start)
    s = (
        s[:start]
        + """    private fun bindPhoneCamera(provider: ProcessCameraProvider) {
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
                Camera2Interop.Extender(builder).setCaptureRequestOption(
                    CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(15, 15),
                )
                val analysis = builder.build().also { next ->
                    next.setAnalyzer(cameraExecutor) { image ->
                        if (ticket != cameraGeneration) { image.close(); return@setAnalyzer }
                        processingCameraGeneration = ticket
                        processingFrontCamera = boundFront
                        cameraInputFrames++
                        if (BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED && cameraInputFrames <= 12) {
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
                        frameAnalyzer.analyze(image)
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
                    binding.glossText.text = "Initializing recognition…"
                } catch (failure: Throwable) {
                    cameraSwitching = false
                    renderRuntimeError("Camera unavailable", failure.message.orEmpty())
                    Log.e(TAG, "Camera bind failed; no recognition fallback", failure)
                }
            }
        }
    }

"""
        + s[end:]
    )
    s = s.replace(
        """    private fun onFrame(r: FrameResult) {
        runOnUiThread {
            if (isFinishing || isDestroyed) return@runOnUiThread""",
        """    private fun onFrame(frame: FrameResult) {
        val ticket = if (phoneSession != null) processingCameraGeneration else cameraGeneration
        // Lens identity is display metadata only. Candidate01 source coordinates stay unchanged.
        val r = if(phoneSession != null) frame.copy(isFrontCamera = processingFrontCamera) else frame
        runOnUiThread {
            if (ticket != cameraGeneration || isFinishing || isDestroyed) return@runOnUiThread""",
        1,
    )
    p.write_text(s)
    p = APP / JAVA / "perceptionvnext/PerceptionVNextOverlayView.kt"
    s = p.read_text().replace(
        "fun draw(canvas: Canvas, width: Int, height: Int, value: PerceptionVNextOverlayView.Snapshot) {",
        "fun draw(canvas: Canvas, width: Int, height: Int, value: PerceptionVNextOverlayView.Snapshot, mirrorPreview: Boolean = true) {",
    )
    s = s.replace("            true,\n        )", "            mirrorPreview,\n        )", 1)
    s = s.replace(
        """            val left = x(roi.right)
            val right = x(roi.left)""",
        """            val left = minOf(x(roi.right), x(roi.left))
            val right = maxOf(x(roi.right), x(roi.left))""",
    )
    p.write_text(s)
    p = APP / JAVA / "ui/OverlayView.kt"
    s = p.read_text().replace(
        """                    phone.bodyXy, phone.bodySupport,
                ),""",
        """                    phone.bodyXy, phone.bodySupport,
                ), r.isFrontCamera,""",
        1,
    )
    p.write_text(s)
    for src in (ROOT / "tools/fingerspelling/camera_android").glob("*InstrumentedTest.kt"):
        target = APP / "android/app/src/androidTest/java/com/example/apphear/camera" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())
    changed = {p: sha(APP / p) for p, h in inventory.items() if sha(APP / p) != h}
    (OUT / "changes.json").write_text(json.dumps(changed, indent=2))
    print(json.dumps(changed, indent=2))


if __name__ == "__main__":
    main()
