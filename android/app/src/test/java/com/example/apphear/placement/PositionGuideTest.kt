package com.example.apphear.placement

import com.example.apphear.placement.PositionGuide.Body
import com.example.apphear.placement.PositionGuide.Point
import com.example.apphear.placement.PositionGuide.Policy
import com.example.apphear.placement.PositionGuide.Status
import java.nio.file.Files
import java.nio.file.Path
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class PositionGuideTest {
    private val policy = Policy(centerTolerance = 0.1f, blockOffset = 0.28f, minShoulderWidth = 0.2f,
        maxShoulderWidth = 0.55f, edgeMargin = 0.02f, minValidJoints = 8, enterFrames = 4, exitFrames = 3, gate = true)

    /** A torso centered at [cx] with the given shoulder width, plus optional hands. */
    private fun body(cx: Float, width: Float = 0.35f, hands: List<List<Point>> = emptyList(), hips: Boolean = true) = Body(
        leftShoulder = Point(cx - width / 2, 0.35f), rightShoulder = Point(cx + width / 2, 0.35f),
        leftHip = if (hips) Point(cx - width / 3, 0.75f) else null, rightHip = if (hips) Point(cx + width / 3, 0.75f) else null,
        hands = hands,
    )

    private fun hand(x: Float, y: Float) = List(21) { Point(x + it * 0.001f, y) }

    @Test fun `centered signer at a comfortable distance is in position`() {
        val a = PositionGuide(policy).assess(body(0.52f))
        assertEquals(Status.CENTERED, a.status)
        assertFalse(a.blocking)
        assertEquals(0.52f, a.anchor!!.centerX, 1e-4f)
        assertEquals(0.75f, a.anchor!!.hipY!!, 1e-4f)
    }

    @Test fun `off-center signer is told which way to move on the mirrored screen`() {
        val guide = PositionGuide(policy)
        assertEquals(Status.MOVE_LEFT, guide.assess(body(0.68f)).status)
        assertEquals(Status.MOVE_RIGHT, guide.assess(body(0.32f)).status)
        assertFalse(guide.assess(body(0.68f)).blocking)
        assertTrue(guide.assess(body(0.85f)).blocking)
        assertTrue(guide.assess(body(0.15f)).blocking)
    }

    @Test fun `distance gives hints only`() {
        val guide = PositionGuide(policy)
        val close = guide.assess(body(0.5f, width = 0.7f))
        assertEquals(Status.STEP_BACK, close.status)
        assertFalse(close.blocking)
        val far = guide.assess(body(0.5f, width = 0.12f))
        assertEquals(Status.COME_CLOSER, far.status)
        assertFalse(far.blocking)
    }

    @Test fun `no shoulders means no person, which never blocks`() {
        val a = PositionGuide(policy).assess(Body(null, Point(0.5f, 0.3f), null, null, emptyList()))
        assertEquals(Status.NO_PERSON, a.status)
        assertFalse(a.blocking)
        assertNull(a.anchor)
    }

    @Test fun `a raised hand cut off by the edge blocks, a resting hand below does not`() {
        val guide = PositionGuide(policy)
        assertEquals(Status.HAND_OUT, guide.assess(body(0.5f, hands = listOf(hand(0.005f, 0.4f)))).status)
        assertTrue(guide.assess(body(0.5f, hands = listOf(hand(0.4f, 0.01f)))).blocking)
        assertEquals(Status.CENTERED, guide.assess(body(0.5f, hands = listOf(hand(0.45f, 0.995f)))).status)
        // Too few joints is not a hand.
        assertEquals(Status.CENTERED, guide.assess(body(0.5f, hands = listOf(List(5) { Point(0f, 0.4f) }))).status)
    }

    @Test fun `only a sustained blocking state pauses, and resuming needs a few clear frames`() {
        val guide = PositionGuide(policy)
        val out = guide.assess(body(0.9f))
        val ok = guide.assess(body(0.5f))
        repeat(3) { assertFalse(guide.update(out).paused) }
        val pause = guide.update(out)
        assertTrue(pause.paused)
        assertTrue(pause.pauseChanged)
        assertTrue(guide.update(ok).paused)
        assertTrue(guide.update(ok).paused)
        val resume = guide.update(ok)
        assertTrue(resume.resumeNow)
        assertTrue(resume.pauseChanged)
        assertFalse(guide.update(ok).paused)
    }

    @Test fun `with the gate off nothing ever pauses`() {
        val guide = PositionGuide(policy.copy(gate = false))
        val out = guide.assess(body(0.95f))
        repeat(10) { assertFalse(guide.update(out).paused) }
    }

    @Test fun `reset clears a pause`() {
        val guide = PositionGuide(policy)
        val out = guide.assess(body(0.9f))
        repeat(4) { guide.update(out) }
        guide.reset()
        assertFalse(guide.update(guide.assess(body(0.5f))).paused)
    }

    @Test fun `policy rejects impossible thresholds`() {
        assertThrows(IllegalArgumentException::class.java) { policy.copy(blockOffset = 0.05f) }
        assertThrows(IllegalArgumentException::class.java) { policy.copy(maxShoulderWidth = 0.1f) }
        assertThrows(IllegalArgumentException::class.java) { policy.copy(enterFrames = 0) }
    }

    @Test fun `shipped policy asset parses`() {
        val json = JsonParser.parseString(String(Files.readAllBytes(Path.of("src/main/assets").resolve(Policy.ASSET))))
            .asJsonObject
        assertEquals(policy, Policy.parse(json["schemaVersion"].asInt, { json[it].asDouble }, gate = true))
        assertThrows(IllegalArgumentException::class.java) { Policy.parse(2, { json[it].asDouble }, gate = true) }
    }
}
