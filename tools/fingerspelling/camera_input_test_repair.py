"""Correct preexisting live-camera test assumptions; bound debug metadata retention."""
# Exact Kotlin migration literals preserve source layout.
# ruff: noqa: E501

from tools.fingerspelling.camera_input_port import APP, JAVA, ROOT


def main():
    p = (
        APP
        / "android/app/src/androidTest/java/com/example/apphear/fingerspelling/ContinuousFingerspellInstrumentedTest.kt"
    )
    s = p.read_text()
    s = s.replace("TimeUnit.SECONDS.toNanos(30)", "TimeUnit.SECONDS.toNanos(45)", 1)
    needle = '            val executor=field("cameraExecutor") as ExecutorService'
    assert needle in s
    s = s.replace(
        needle,
        """            while (((field("cameraSwitching") as Boolean) || (field("cameraInputFrames") as Int)<1) &&
                System.nanoTime()<deadline) Thread.sleep(50)
            assertFalse("Camera binding completed before synthetic pause",field("cameraSwitching") as Boolean)
"""
        + needle,
        1,
    )
    s = s.replace(
        """                repeat(15){engine.consume(observation(10000.0+it*200.0,false))}""",
        """                val beforeMissing=calls()
                repeat(15){engine.consume(observation(10000.0+it*200.0,false))}""",
        1,
    )
    s = s.replace(
        """                assertEquals(0,calls()) // entirely missing input must not reach the model.""",
        """                assertEquals(beforeMissing,calls()) // Missing input adds no inference calls; live startup may already have calls.""",
        1,
    )
    p.write_text(s)
    p = APP / JAVA / "RecognitionActivity.kt"
    s = p.read_text()
    s = s.replace(
        """                            val rotation = image.imageInfo.rotationDegrees""",
        """                            if(cameraInputFramesJson.length() >= 120) cameraInputFramesJson.remove(0)
                            val rotation = image.imageInfo.rotationDegrees""",
        1,
    )
    p.write_text(s)
    p = (
        APP
        / "android/app/src/androidTest/java/com/example/apphear/camera/CameraSwitchInstrumentedTest.kt"
    )
    p.write_bytes(
        (ROOT / "tools/fingerspelling/camera_android/CameraSwitchInstrumentedTest.kt").read_bytes()
    )


if __name__ == "__main__":
    main()
