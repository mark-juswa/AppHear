package com.example.apphear.placement

import com.example.apphear.placement.PlacementGuard.Status
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PlacementGuardTest {
    private val region = PlacementGuard.Region(0.2f, 0.05f, 0.8f, 0.9f)
    private val shoulders = floatArrayOf(0.38f, 0.4f, 0.62f, 0.4f)

    /** A 21-joint hand spread around (x, y). */
    private fun hand(x: Float, y: Float, spread: Float = 0.03f) =
        PlacementGuard.Hand(FloatArray(42) { if (it % 2 == 0) x + spread * ((it / 2) % 5 - 2) / 2 else y })

    private fun frame(vararg hands: PlacementGuard.Hand, shoulders: FloatArray? = this.shoulders) =
        PlacementGuard.Frame(hands.toList(), shoulders)

    @Test
    fun handsInsideAreOkAndNoHandsIsResting() {
        val guard = PlacementGuard()
        assertEquals(Status.OK, guard.evaluate(frame(hand(0.5f, 0.5f)), region))
        assertEquals(Status.HANDS_DOWN, guard.evaluate(frame(), region))
    }

    @Test
    fun handPastLeftRightOrTopIsOutButBelowIsResting() {
        val guard = PlacementGuard()
        assertEquals(Status.HAND_OUT, guard.evaluate(frame(hand(0.19f, 0.5f)), region))
        assertEquals(Status.HAND_OUT, guard.evaluate(frame(hand(0.81f, 0.5f)), region))
        assertEquals(Status.HAND_OUT, guard.evaluate(frame(hand(0.5f, 0.02f)), region))
        assertEquals(Status.OK, guard.evaluate(frame(hand(0.5f, 0.97f)), region))
    }

    @Test
    fun partlyDetectedHandsAreIgnored() {
        val guard = PlacementGuard()
        val fewJoints = PlacementGuard.Hand(floatArrayOf(0.1f, 0.5f, 0.1f, 0.5f))
        assertEquals(Status.HANDS_DOWN, guard.evaluate(frame(fewJoints), region))
    }

    @Test
    fun distanceAndShouldersAreHintsOnly() {
        val guard = PlacementGuard()
        val wide = floatArrayOf(0.15f, 0.4f, 0.85f, 0.4f)
        assertEquals(Status.TOO_CLOSE, guard.evaluate(frame(hand(0.5f, 0.5f), shoulders = wide), region))
        assertEquals(Status.NO_SHOULDERS, guard.evaluate(frame(hand(0.5f, 0.5f), shoulders = null), region))
        repeat(10) { assertFalse(guard.update(Status.TOO_CLOSE).paused) }
        repeat(10) { assertFalse(guard.update(Status.NO_SHOULDERS).paused) }
    }

    @Test
    fun pausesOnlyAfterSustainedOutAndResumesOnceWithReset() {
        val guard = PlacementGuard(PlacementGuard.Config(enterFrames = 3, exitFrames = 2))
        assertFalse(guard.update(Status.HAND_OUT).paused)
        assertFalse(guard.update(Status.HAND_OUT).paused)
        assertTrue(guard.update(Status.HAND_OUT).paused)
        assertTrue(guard.update(Status.OK).paused)
        val resume = guard.update(Status.OK)
        assertTrue(resume.resumeNow)
        assertTrue("the resume frame is still skipped so the restart begins on the next frame", resume.paused)
        val after = guard.update(Status.OK)
        assertFalse(after.paused); assertFalse(after.resumeNow)
    }

    @Test
    fun aBriefSlipDoesNotPause() {
        val guard = PlacementGuard(PlacementGuard.Config(enterFrames = 3))
        guard.update(Status.HAND_OUT); guard.update(Status.HAND_OUT)
        guard.update(Status.OK)
        assertFalse(guard.update(Status.HAND_OUT).paused)
    }

    @Test
    fun handsDownResumesAPause() {
        val guard = PlacementGuard(PlacementGuard.Config(enterFrames = 1, exitFrames = 1))
        assertTrue(guard.update(Status.HAND_OUT).paused)
        assertTrue(guard.update(Status.HANDS_DOWN).resumeNow)
    }
}
