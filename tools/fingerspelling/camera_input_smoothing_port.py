"""Apply one measured rear-preview FPS correction without changing the front baseline."""
# Exact Kotlin migration literals retain source layout.
# ruff: noqa: E501

from tools.fingerspelling.camera_input_port import APP, JAVA, ROOT


def main():
    p = APP / JAVA / "RecognitionActivity.kt"
    s = p.read_text()
    old = """                val timing = if(BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED)
                    com.example.apphear.camera.CameraTimingProbe(boundFront,ticket) else null"""
    assert old in s
    s = s.replace(
        old,
        """                // Front reference stays at 15. Rear preview uses 30 only when the camera
                // explicitly advertises the exact range; analysis still keeps only latest.
                val rearRanges = if(!boundFront) androidx.camera.camera2.interop.Camera2CameraInfo
                    .from(selector.filter(provider.availableCameraInfos).first())
                    .getCameraCharacteristic(android.hardware.camera2.CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES)
                    .orEmpty() else emptyArray()
                val requestedFps = if(!boundFront && rearRanges.any { it.lower == 30 && it.upper == 30 }) 30 else 15
                val timing = if(BuildConfig.RECOGNITION_REAR_CAMERA_ENABLED)
                    com.example.apphear.camera.CameraTimingProbe(boundFront,ticket,requestedFps) else null""",
        1,
    )
    s = s.replace(
        """                    CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(15, 15),""",
        """                    CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(requestedFps, requestedFps),""",
        1,
    )
    s = s.replace(
        """                        val sourceTimestamp=image.imageInfo.timestamp""",
        """                        val processingMode=if(fingerspellRuntime?.fingerspellOwnsFrames==true) "FINGERSPELL" else "WORD"
                        val sourceTimestamp=image.imageInfo.timestamp""",
        1,
    )
    s = s.replace(
        """timing.report(selectedRecognitionMode.name)""", """timing.report(processingMode)""", 1
    )
    p.write_text(s)
    target = APP / JAVA / "camera/CameraTimingProbe.kt"
    target.write_bytes(
        (ROOT / "tools/fingerspelling/camera_android/CameraTimingProbe.kt").read_bytes()
    )


if __name__ == "__main__":
    main()
