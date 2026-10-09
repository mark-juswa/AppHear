package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class PhoneS2ExactParityRecorderTest {
    @Test fun serializesCompleteExactWidthRowsAndManifest() {
        val root = Files.createTempDirectory("phone-s2-exact-parity").toFile()
        try {
            val recorder = PhoneS2ExactParityRecorder(root, maximumObservations = 2)
            val raw = PhoneRawObservation(
                sourceIndex = 0,
                timestampMs = 1234.5,
                sourceWidth = 480,
                sourceHeight = 640,
                handXy = Array(2) { FloatArray(42) { index -> index + it * 100f } },
                handJointValid = Array(2) { BooleanArray(21) { it % 2 == 0 } },
                handProposalSupport = Array(2) { FloatArray(21) { index -> index / 21f } },
                handPresence = floatArrayOf(Float.NaN, 0.75f),
                handObserved = booleanArrayOf(false, true),
                handProposalPresent = booleanArrayOf(true, true),
                handRoiCenterSide = arrayOf(floatArrayOf(1f, 2f, 3f), floatArrayOf(4f, 5f, 6f)),
                bodyXy = FloatArray(16) { it.toFloat() },
                bodySupport = FloatArray(8) { it / 8f },
                bodyValid = BooleanArray(8) { true },
                bodyAvailable = true,
            )
            recorder.record(
                raw,
                FloatArray(378) { it / 378f },
                FloatArray(378) { -it / 378f },
                floatArrayOf(0.1f, 0.8f, 0.1f),
                historyLength = 1,
                argmaxState = 1,
                attemptId = 3,
                expectedGloss = "HOME",
            )
            recorder.close()
            recorder.close()

            assertEquals(378L * 4, root.resolve("android_features.f32").length())
            assertEquals(378L * 4, root.resolve("android_normalized.f32").length())
            assertEquals(84L * 4, root.resolve("raw_hand_xy.f32").length())
            assertEquals(3L * 4, root.resolve("android_probabilities.f32").length())
            val manifest = root.resolve("manifest.json").readText()
            assertTrue(manifest.contains("\"observation_count\": 1"))
            assertTrue(manifest.contains("apphear.phone_s2_exact_parity_capture.v1"))
            assertTrue(root.resolve("linkage.csv").readText().contains("3,\"HOME\""))
        } finally {
            root.deleteRecursively()
        }
    }
}
