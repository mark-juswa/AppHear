package com.example.apphear.placement

import android.content.Context
import org.json.JSONObject

/**
 * Augmented signing position for the recognition screen (placementGuide / placementGate). Pure logic,
 * no Android types beyond loading [Policy]; the camera thread feeds it one frame at a time.
 *
 * Coordinates are normalized to the camera view as the signer sees it (front camera mirrored), so
 * "move left" means toward the left of the screen. The right position is the signer centered, with
 * their shoulders at a comfortable width.
 *
 * Only two states may pause recognition (placementGate): a raised hand cut off by the screen edge,
 * and the signer far off-center (hands near that edge leave the view mid-sign). Distance and a missing
 * shoulder line are hints only: a governed test found correct words even with no body reference in view.
 */
class PositionGuide(private val policy: Policy) {
    data class Policy(
        /** Torso center within this of the screen center counts as centered. */
        val centerTolerance: Float,
        /** Torso center further than this from the screen center pauses recognition. */
        val blockOffset: Float,
        /** Shoulder width (fraction of view width) below this: come closer. */
        val minShoulderWidth: Float,
        /** Shoulder width above this: step back. */
        val maxShoulderWidth: Float,
        /** Hand joints this close to the left, right or top edge count as cut off. */
        val edgeMargin: Float,
        /** Valid joints a hand needs before it counts as present. */
        val minValidJoints: Int,
        /** Consecutive blocking frames before recognition pauses. */
        val enterFrames: Int,
        /** Consecutive non-blocking frames before recognition resumes. */
        val exitFrames: Int,
        /** placementGate: whether blocking states pause recognition at all. */
        val gate: Boolean,
    ) {
        init {
            require(centerTolerance in 0.02f..0.3f && blockOffset > centerTolerance && blockOffset < 0.5f) {
                "[placement/policy] center tolerances out of range"
            }
            require(minShoulderWidth in 0.05f..0.5f && maxShoulderWidth in minShoulderWidth..0.95f) {
                "[placement/policy] shoulder widths out of range"
            }
            require(edgeMargin in 0f..0.1f && minValidJoints in 1..21 && enterFrames >= 1 && exitFrames >= 1) {
                "[placement/policy] edge or hysteresis out of range"
            }
        }

        companion object {
            const val ASSET = "placement/position_policy_v1.json"
            const val SCHEMA_VERSION = 1

            /** Fails loudly on a schema mismatch instead of guessing at the fields. */
            fun parse(schemaVersion: Int, value: (String) -> Double, gate: Boolean): Policy {
                require(schemaVersion == SCHEMA_VERSION) { "[placement/policy] schema mismatch" }
                return Policy(
                    centerTolerance = value("centerTolerance").toFloat(),
                    blockOffset = value("blockOffset").toFloat(),
                    minShoulderWidth = value("minShoulderWidth").toFloat(),
                    maxShoulderWidth = value("maxShoulderWidth").toFloat(),
                    edgeMargin = value("edgeMargin").toFloat(),
                    minValidJoints = value("minValidJoints").toInt(),
                    enterFrames = value("enterFrames").toInt(),
                    exitFrames = value("exitFrames").toInt(),
                    gate = gate,
                )
            }

            fun load(context: Context, gate: Boolean): Policy {
                val json = JSONObject(context.assets.open(ASSET).bufferedReader().use { it.readText() })
                return parse(json.getInt("schemaVersion"), json::getDouble, gate)
            }
        }
    }

    enum class Status { NO_PERSON, CENTERED, MOVE_LEFT, MOVE_RIGHT, STEP_BACK, COME_CLOSER, HAND_OUT }

    class Point(val x: Float, val y: Float)

    /** Shoulders and hips (null when not seen) and each visible hand's valid joints. */
    class Body(
        val leftShoulder: Point?,
        val rightShoulder: Point?,
        val leftHip: Point?,
        val rightHip: Point?,
        val hands: List<List<Point>>,
    )

    /** Where the signer's torso is, for drawing the guide around them. */
    data class Anchor(val centerX: Float, val shoulderY: Float, val shoulderWidth: Float, val hipY: Float?)

    data class Assessment(val status: Status, val blocking: Boolean, val anchor: Anchor?)

    data class Decision(
        val assessment: Assessment,
        /** True while recognition should skip frames. */
        val paused: Boolean,
        /** True on the frame the pause ends: the caller restarts the word session once here. */
        val resumeNow: Boolean,
        /** The paused state changed on this frame. */
        val pauseChanged: Boolean,
    )

    private var paused = false
    private var blockRun = 0
    private var clearRun = 0

    fun reset() {
        paused = false
        blockRun = 0
        clearRun = 0
    }

    fun assess(body: Body): Assessment {
        val handOut = body.hands.filter { it.size >= policy.minValidJoints }.any { hand ->
            hand.any { it.x < policy.edgeMargin || it.x > 1f - policy.edgeMargin || it.y < policy.edgeMargin }
        }
        val left = body.leftShoulder
        val right = body.rightShoulder
        val anchor = if (left != null && right != null) {
            val hips = listOfNotNull(body.leftHip, body.rightHip)
            Anchor(
                centerX = (left.x + right.x) / 2f,
                shoulderY = (left.y + right.y) / 2f,
                shoulderWidth = kotlin.math.abs(left.x - right.x),
                hipY = if (hips.size == 2) (hips[0].y + hips[1].y) / 2f else null,
            )
        } else null
        if (handOut) return Assessment(Status.HAND_OUT, blocking = true, anchor = anchor)
        if (anchor == null) return Assessment(Status.NO_PERSON, blocking = false, anchor = null)
        val offset = anchor.centerX - 0.5f
        val status = when {
            // On a mirrored selfie view, the signer moves toward the side they should go to.
            offset > policy.centerTolerance -> Status.MOVE_LEFT
            offset < -policy.centerTolerance -> Status.MOVE_RIGHT
            anchor.shoulderWidth > policy.maxShoulderWidth -> Status.STEP_BACK
            anchor.shoulderWidth < policy.minShoulderWidth -> Status.COME_CLOSER
            else -> Status.CENTERED
        }
        return Assessment(status, blocking = kotlin.math.abs(offset) > policy.blockOffset, anchor = anchor)
    }

    /** Hysteresis over [assess]: only a sustained blocking state pauses, and only with the gate on. */
    fun update(assessment: Assessment): Decision {
        val wasPaused = paused
        var resume = false
        if (policy.gate && assessment.blocking) {
            blockRun++
            clearRun = 0
            if (!paused && blockRun >= policy.enterFrames) paused = true
        } else {
            clearRun++
            blockRun = 0
            if (paused && clearRun >= policy.exitFrames) {
                paused = false
                resume = true
            }
        }
        return Decision(assessment, paused || resume, resume, pauseChanged = paused != wasPaused)
    }
}
