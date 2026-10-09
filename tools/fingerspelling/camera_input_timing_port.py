"""Add bounded camera timing evidence to diagnose supervisor-reported rear lag."""
# Exact Kotlin migration literals retain source layout.
# ruff: noqa: E501

from tools.fingerspelling.camera_input_port import APP, JAVA, ROOT


def main():
    destination = APP / JAVA / "camera/CameraTimingProbe.kt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(
        (ROOT / "tools/fingerspelling/camera_android/CameraTimingProbe.kt").read_bytes()
    )
    p = APP / JAVA / "RecognitionActivity.kt"
    s = p.read_text()
    assert "CameraTimingProbe" not in s
    s = s.replace(
        """                Camera2Interop.Extender(builder).setCaptureRequestOption(""",
        """                val timing = if(BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED)
                    com.example.apphear.camera.CameraTimingProbe(boundFront,ticket) else null
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
                interop.setCaptureRequestOption(""",
        1,
    )
    s = s.replace(
        """                        frameAnalyzer.analyze(image)""",
        """                        val sourceTimestamp=image.imageInfo.timestamp
                        val analysisStarted=android.os.SystemClock.elapsedRealtimeNanos()
                        frameAnalyzer.analyze(image)
                        if(timing?.analyzed(sourceTimestamp,
                            (android.os.SystemClock.elapsedRealtimeNanos()-analysisStarted)/1e6)==true) {
                            java.io.File(filesDir,"camera_timing_${ticket}_${if(boundFront) "front" else "back"}.json")
                                .writeText(timing.report(selectedRecognitionMode.name).toString(2))
                        }""",
        1,
    )
    p.write_text(s)


if __name__ == "__main__":
    main()
