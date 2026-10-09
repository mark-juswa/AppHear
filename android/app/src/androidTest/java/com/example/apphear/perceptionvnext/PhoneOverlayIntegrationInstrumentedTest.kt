package com.example.apphear.perceptionvnext

import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.ui.OverlayView
import com.example.apphear.ui.PhoneOverlayFrame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Presentation-only parity: the real UI must draw the exact validated Candidate01 geometry. */
@RunWith(AndroidJUnit4::class)
class PhoneOverlayIntegrationInstrumentedTest {
    @Test
    fun normalAppOverlayMatchesValidatedDebugOverlayAndClearsOnNavigation() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val leftXy = FloatArray(42)
        val rightXy = FloatArray(42)
        for (point in 0 until 21) {
            leftXy[point * 2] = 120f + point * 3f
            leftXy[point * 2 + 1] = 300f + point * 5f
            rightXy[point * 2] = 440f - point * 2f
            rightXy[point * 2 + 1] = 480f + point * 4f
        }
        val bodyXy = floatArrayOf(
            220f, 160f, 380f, 160f, 180f, 260f, 420f, 260f,
            160f, 390f, 440f, 390f, 240f, 530f, 360f, 530f,
        )
        val leftRoi = PerceptionVNextMath.HandRoi(160f, 360f, 150f, 600, 800, 5)
        val rightRoi = PerceptionVNextMath.HandRoi(410f, 520f, 140f, 600, 800, 5)
        val snapshot = PerceptionVNextOverlayView.Snapshot(
            600, 800,
            PerceptionVNextOverlayView.Hand(leftXy, BooleanArray(21) { true }, true, 0.95f, leftRoi),
            PerceptionVNextOverlayView.Hand(rightXy, BooleanArray(21) { true }, true, 0.87f, rightRoi),
            bodyXy, FloatArray(8) { 0.9f },
        )
        val frame = FrameResult(
            hands = null, pose = null, imageWidth = 600, imageHeight = 800,
            fps = 15.0, isFrontCamera = true, qualityLabel = "S2_R2_CANDIDATE", poseEveryN = 1,
            phoneOverlay = PhoneOverlayFrame(
                600, 800,
                arrayOf(leftXy, rightXy), arrayOf(BooleanArray(21) { true }, BooleanArray(21) { true }),
                booleanArrayOf(true, true), floatArrayOf(0.95f, 0.87f),
                arrayOf(floatArrayOf(160f, 360f, 150f), floatArrayOf(410f, 520f, 140f)),
                bodyXy, FloatArray(8) { 0.9f }, BooleanArray(8) { true },
            ),
        )
        InstrumentationRegistry.getInstrumentation().runOnMainSync {
            val main = OverlayView(context, null).apply { layout(0, 0, 1080, 1920); setResult(frame) }
            val debug = PerceptionVNextOverlayView(context).apply {
                layout(0, 0, 1080, 1920)
                setSnapshot(snapshot)
            }
            val mainBitmap = Bitmap.createBitmap(1080, 1920, Bitmap.Config.ARGB_8888)
            val debugBitmap = Bitmap.createBitmap(1080, 1920, Bitmap.Config.ARGB_8888)
            try {
                main.draw(Canvas(mainBitmap))
                debug.draw(Canvas(debugBitmap))
                assertTrue("real-app/debug Candidate01 overlay pixels differ", mainBitmap.sameAs(debugBitmap))
                main.clear()
                mainBitmap.eraseColor(android.graphics.Color.TRANSPARENT)
                main.draw(Canvas(mainBitmap))
                debugBitmap.eraseColor(android.graphics.Color.TRANSPARENT)
                assertTrue("stale overlay remained after clear", mainBitmap.sameAs(debugBitmap))
            } finally {
                mainBitmap.recycle()
                debugBitmap.recycle()
            }
        }
    }
}
