package com.example.apphear

import com.example.apphear.pipeline.features.Topology.LEFT_HIP
import com.example.apphear.pipeline.features.Topology.LEFT_SHOULDER
import com.example.apphear.pipeline.features.Topology.LEFT_WRIST
import com.example.apphear.pipeline.features.Topology.RIGHT_HIP
import com.example.apphear.pipeline.features.Topology.RIGHT_SHOULDER
import com.example.apphear.pipeline.features.Topology.RIGHT_WRIST
import com.example.apphear.pipeline.recognition.LandmarkAdapter
import com.example.apphear.pipeline.recognition.SigningConfig
import com.example.apphear.pipeline.recognition.SigningDetector
import com.example.apphear.pipeline.recognition.SigningEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The no-hands false-commit fix: S5 must NOT enter "signing" on pose arm-motion when the hand
 * landmarker saw nothing (pose wrists exist even with no hands). Pure JVM.
 */
class SigningHandGateTest {

    private fun cfg() = SigningConfig(
        thetaOn = 0.02, thetaOff = 0.01, kOn = 2, kOff = 2,
        raiseMargin = 0.10, smoothingWindow = 1, handAuxWeight = 0.5, requireHands = true,
    )

    /** Pose with shoulders (scale=1), and wrists raised above the hips (raised-gate open). */
    private fun pose(wristX: Float): FloatArray {
        val p = FloatArray(33 * 4) { Float.NaN }
        fun set(i: Int, x: Float, y: Float) { p[i * 4] = x; p[i * 4 + 1] = y; p[i * 4 + 3] = 1f }
        set(LEFT_SHOULDER, 0.0f, 0.5f)
        set(RIGHT_SHOULDER, 1.0f, 0.5f) // shoulder width = 1.0
        set(LEFT_HIP, 0.0f, 0.9f)
        set(RIGHT_HIP, 1.0f, 0.9f)
        set(LEFT_WRIST, wristX, 0.2f) // y=0.2 < hipY(0.9) - margin → raised
        set(RIGHT_WRIST, wristX, 0.2f)
        return p
    }

    private fun handsPresent(): FloatArray = FloatArray(2 * 21 * 3) { 0f } // slot0 wrist non-NaN
    private fun handsAbsent(): FloatArray = FloatArray(2 * 21 * 3) { Float.NaN }

    @Test
    fun noHandsDoesNotTriggerOnsetDespitePoseMotion() {
        val d = SigningDetector(cfg())
        var event = SigningEvent.NONE
        // Strong pose motion + raised wrists, but NO hands detected, for many frames.
        for (i in 0 until 10) {
            event = d.update(pose(0.2f + 0.1f * i), handsAbsent())
        }
        assertFalse("must not be signing without hands", d.isSigning)
        assertEquals(SigningEvent.NONE, event)
    }

    @Test
    fun handsPresentWithMotionDoesTriggerOnset() {
        val d = SigningDetector(cfg())
        var sawOnset = false
        for (i in 0 until 6) {
            if (d.update(pose(0.2f + 0.1f * i), handsPresent()) == SigningEvent.ONSET) sawOnset = true
        }
        assertTrue("hands + motion + raised should onset", sawOnset)
        assertTrue(d.isSigning)
    }

    @Test
    fun losingHandsMidSignReleases() {
        val d = SigningDetector(cfg())
        repeat(6) { i -> d.update(pose(0.2f + 0.1f * i), handsPresent()) }
        assertTrue("signing after hands+motion", d.isSigning)
        var released = false
        // Hands gone; kOff frames later it must release even if the arm keeps moving.
        for (i in 0 until 5) {
            if (d.update(pose(1.0f + 0.1f * i), handsAbsent()) == SigningEvent.RELEASE) released = true
        }
        assertTrue("losing hands ends the sign", released)
        assertFalse(d.isSigning)
    }

    @Test
    fun handsPresentHelperMatchesWristSlots() {
        assertFalse(LandmarkAdapter.handsPresent(FloatArray(2 * 21 * 3) { Float.NaN }))
        assertTrue(LandmarkAdapter.handsPresent(FloatArray(2 * 21 * 3) { 0f }))
    }

    @Test
    fun defaultDetectorStillResetsAcrossOneNonCandidateFrame() {
        val d = SigningDetector(cfg())
        d.update(pose(0.20f), handsPresent())
        d.update(pose(0.23f), handsPresent()) // candidate 1
        d.update(pose(0.245f), handsPresent()) // above theta_off, below theta_on
        val event = d.update(pose(0.275f), handsPresent()) // candidate 1 after reset
        assertEquals(SigningEvent.NONE, event)
        assertFalse(d.isSigning)
    }

    @Test
    fun experimentalDetectorBridgesExactlyOneHandsPresentNonRestGap() {
        val d = SigningDetector(cfg(), allowOneShortOnsetGap = true)
        d.update(pose(0.20f), handsPresent())
        d.update(pose(0.23f), handsPresent()) // candidate 1
        d.update(pose(0.245f), handsPresent()) // permitted interruption
        assertTrue(d.lastDiagnostics.onsetGapBridgedThisFrame)
        val event = d.update(pose(0.275f), handsPresent()) // candidate 2
        assertEquals(SigningEvent.ONSET, event)
        assertTrue(d.isSigning)
    }

    @Test
    fun experimentalDetectorDoesNotBridgeMissingHandsOrClearRest() {
        val missingHands = SigningDetector(cfg(), allowOneShortOnsetGap = true)
        missingHands.update(pose(0.20f), handsPresent())
        missingHands.update(pose(0.23f), handsPresent())
        missingHands.update(pose(0.245f), handsAbsent())
        assertFalse(missingHands.lastDiagnostics.onsetGapBridgedThisFrame)
        assertEquals(
            SigningEvent.NONE,
            missingHands.update(pose(0.275f), handsPresent()),
        )

        val clearRest = SigningDetector(cfg(), allowOneShortOnsetGap = true)
        clearRest.update(pose(0.20f), handsPresent())
        clearRest.update(pose(0.23f), handsPresent())
        clearRest.update(pose(0.235f), handsPresent()) // below theta_off
        assertFalse(clearRest.lastDiagnostics.onsetGapBridgedThisFrame)
        assertEquals(SigningEvent.NONE, clearRest.update(pose(0.265f), handsPresent()))
    }
}
